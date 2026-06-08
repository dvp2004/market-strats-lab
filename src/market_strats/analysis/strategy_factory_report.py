from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from market_strats.analysis.metrics import calculate_drawdown, calculate_metrics
from market_strats.data.cash_rates import (
    align_cash_returns_to_price_dates,
    fetch_cash_yield_rates,
    load_cash_rates_from_parquet,
    save_cash_rates_to_parquet,
)
from market_strats.data.fetch_yfinance import (
    fetch_daily_prices,
    load_prices_from_parquet,
    save_prices_to_parquet,
)
from market_strats.strategies.strategy_factory import (
    FACTORY_ASSETS,
    STRATEGY_FACTORY_CANDIDATES,
    StrategyFactoryConfig,
    build_strategy_factory_price_panel,
    run_strategy_factory_candidates,
)


BENCHMARK_STRATEGY = "sf_spy_buy_hold"


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("phase17a_strategy_factory", {}) or {}


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _safe_ticker_file(ticker: str) -> str:
    return f"{ticker.upper()}.parquet"


def _preferred_data_dir(universe: list[str], section: dict[str, Any]) -> Path:
    configured = section.get("data_dir")
    if configured:
        return Path(configured)

    fresh_dir = Path("data/fresh/processed")
    if all((fresh_dir / _safe_ticker_file(ticker)).exists() for ticker in universe):
        return fresh_dir

    return Path("data/processed")


def _load_or_fetch_prices(ticker: str, config: dict[str, Any], data_dir: Path) -> pd.DataFrame:
    ticker = ticker.upper()
    try:
        return load_prices_from_parquet(ticker, data_dir)
    except FileNotFoundError:
        prices = fetch_daily_prices(
            ticker=ticker,
            start_date=config["start_date"],
            end_date=config.get("end_date"),
        )
        save_prices_to_parquet(prices, ticker, data_dir)
        return prices


def _load_cash_returns(
    *,
    config: dict[str, Any],
    data_dir: Path,
    dates: pd.Series,
) -> pd.Series:
    if not bool(config.get("use_cash_yield", False)):
        return pd.Series(0.0, index=pd.to_datetime(dates), name="cash_return")

    ticker = str(config.get("cash_ticker", "^IRX"))
    try:
        cash_rates = load_cash_rates_from_parquet(ticker, data_dir)
    except FileNotFoundError:
        cash_rates = fetch_cash_yield_rates(
            ticker=ticker,
            start_date=config["start_date"],
            end_date=config.get("end_date"),
        )
        save_cash_rates_to_parquet(cash_rates, ticker, data_dir)

    return align_cash_returns_to_price_dates(cash_rates, dates)


def _load_price_data(
    *,
    config: dict[str, Any],
    section: dict[str, Any],
) -> tuple[dict[str, pd.DataFrame], pd.Series, Path]:
    universe = [str(ticker).upper() for ticker in section.get("universe", [])]
    if not universe:
        raise ValueError("phase17a_strategy_factory.universe cannot be empty")

    data_dir = _preferred_data_dir(universe, section)
    price_data = {
        ticker: _load_or_fetch_prices(ticker, config, data_dir)
        for ticker in universe
    }

    common_dates = next(iter(price_data.values()))["date"]
    for frame in price_data.values():
        common_dates = pd.Series(
            sorted(set(pd.to_datetime(common_dates)).intersection(pd.to_datetime(frame["date"])))
        )

    cash_returns = _load_cash_returns(config=config, data_dir=data_dir, dates=common_dates)
    return price_data, cash_returns, data_dir


def _load_overlay_exposure(reports_dir: Path, section: dict[str, Any]) -> tuple[pd.Series | None, str]:
    path = Path(
        section.get(
            "phase6_overlay_exposure_file",
            reports_dir / "phase14g_corrected_visual_exposure_timeline.csv",
        )
    )
    if not path.exists():
        return None, "phase14g_overlay_exposure_missing_simplified_prototype_used"

    frame = pd.read_csv(path)
    if frame.empty or "exposure" not in frame.columns:
        return None, "phase14g_overlay_exposure_invalid_simplified_prototype_used"

    date_col = "decision_date" if "decision_date" in frame.columns else "date"
    if date_col not in frame.columns:
        return None, "phase14g_overlay_exposure_no_date_simplified_prototype_used"

    series = frame[[date_col, "exposure"]].copy()
    series[date_col] = pd.to_datetime(series[date_col])
    return series.set_index(date_col)["exposure"].astype(float), "phase14g_overlay_exposure_loaded"


def _strategy_factory_config(section: dict[str, Any]) -> StrategyFactoryConfig:
    return StrategyFactoryConfig(
        initial_capital=float(section.get("initial_capital", 10000)),
        btc_max_weight=float(section.get("btc_max_weight", 0.10)),
        qqq_satellite_max_weight=float(section.get("qqq_satellite_max_weight", 0.40)),
        momentum_lookback_days=int(section.get("momentum_lookback_days", 126)),
        trend_lookback_days=int(section.get("trend_lookback_days", 200)),
    )


def _metrics_with_benchmark_comparison(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return metrics

    benchmark = metrics.loc[metrics["strategy"] == BENCHMARK_STRATEGY]
    if benchmark.empty:
        raise ValueError("Strategy Factory benchmark result is missing")

    bench = benchmark.iloc[0]
    out = metrics.copy()
    out["candidate_minus_spy_end_value"] = (
        out["end_value"].astype(float) - float(bench["end_value"])
    ).round(2)
    out["candidate_minus_spy_cagr_pct"] = (
        out["cagr_pct"].astype(float) - float(bench["cagr_pct"])
    ).round(2)
    out["candidate_max_drawdown_advantage_vs_spy_pct_points"] = (
        out["max_drawdown_pct"].astype(float) - float(bench["max_drawdown_pct"])
    ).round(2)
    out["candidate_calmar_advantage_vs_spy"] = (
        out["calmar"].astype(float) - float(bench["calmar"])
    ).round(3)
    return out


def classify_strategy(row: pd.Series, benchmark_row: pd.Series) -> str:
    cagr_delta = float(row["cagr_pct"]) - float(benchmark_row["cagr_pct"])
    end_value_delta = float(row["end_value"]) - float(benchmark_row["end_value"])
    drawdown_advantage = float(row["max_drawdown_pct"]) - float(
        benchmark_row["max_drawdown_pct"]
    )

    if end_value_delta > 0 and cagr_delta > 0 and drawdown_advantage >= -5.0:
        return "growth_candidate"

    if cagr_delta >= -0.50 and drawdown_advantage >= 10.0:
        return "balanced_candidate"

    if cagr_delta < 0 and drawdown_advantage >= 20.0:
        return "defensive_candidate"

    return "rejected"


def _gate_report(metrics: pd.DataFrame, status: pd.DataFrame, section: dict[str, Any]) -> pd.DataFrame:
    benchmark_row = metrics.loc[metrics["strategy"] == BENCHMARK_STRATEGY].iloc[0]
    rows = []
    status_lookup = status.set_index("strategy").to_dict(orient="index") if not status.empty else {}

    for row in metrics.to_dict(orient="records"):
        series = pd.Series(row)
        classification = classify_strategy(series, benchmark_row)
        implementation_status = status_lookup.get(row["strategy"], {}).get(
            "implementation_status",
            "",
        )
        rows.append(
            {
                "strategy": row["strategy"],
                "implementation_status": implementation_status,
                "classification": classification,
                "beats_spy_end_value": float(row["candidate_minus_spy_end_value"]) > 0,
                "beats_spy_cagr": float(row["candidate_minus_spy_cagr_pct"]) > 0,
                "drawdown_advantage_pct_points": row[
                    "candidate_max_drawdown_advantage_vs_spy_pct_points"
                ],
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
            }
        )

    safety_rows = [
        {
            "strategy": "phase17a_safety_gate",
            "implementation_status": "safety_check",
            "classification": (
                "passed"
                if not (
                    _bool_value(section.get("live_trading_allowed", False))
                    or _bool_value(section.get("real_money_allowed", False))
                    or _bool_value(section.get("broker_api_integration_allowed", False))
                )
                else "failed"
            ),
            "beats_spy_end_value": False,
            "beats_spy_cagr": False,
            "drawdown_advantage_pct_points": 0.0,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        }
    ]

    return pd.DataFrame([*rows, *safety_rows])


def _equity_curves(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for strategy, result in results.items():
        part = result[["date", "equity"]].copy()
        part["strategy"] = strategy
        rows.append(part)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _drawdown_curves(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for strategy, result in results.items():
        part = result[["date", "equity"]].copy()
        part["drawdown"] = calculate_drawdown(part["equity"])
        part["strategy"] = strategy
        rows.append(part[["date", "strategy", "drawdown"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _allocation_timeline(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    weight_cols = [f"{asset.lower().replace('-', '_')}_weight" for asset in FACTORY_ASSETS]
    for strategy, result in results.items():
        cols = ["date", *[col for col in weight_cols if col in result.columns]]
        wide = result[cols].copy()
        long = wide.melt("date", var_name="asset", value_name="weight")
        long["asset"] = long["asset"].str.replace("_weight", "", regex=False).str.upper()
        long["strategy"] = strategy
        rows.append(long[["date", "strategy", "asset", "weight"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _rolling_relative_performance(results: dict[str, pd.DataFrame], window: int = 252) -> pd.DataFrame:
    benchmark = results[BENCHMARK_STRATEGY][["date", "equity"]].copy()
    benchmark = benchmark.rename(columns={"equity": "benchmark_equity"})
    rows = []
    for strategy, result in results.items():
        merged = result[["date", "equity"]].merge(benchmark, on="date", how="inner")
        merged["strategy"] = strategy
        merged["candidate_rolling_return"] = merged["equity"].pct_change(window).fillna(0.0)
        merged["benchmark_rolling_return"] = (
            merged["benchmark_equity"].pct_change(window).fillna(0.0)
        )
        merged["rolling_relative_return"] = (
            merged["candidate_rolling_return"] - merged["benchmark_rolling_return"]
        )
        rows.append(
            merged[
                [
                    "date",
                    "strategy",
                    "candidate_rolling_return",
                    "benchmark_rolling_return",
                    "rolling_relative_return",
                ]
            ]
        )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _turnover_summary(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strategy": strategy,
                "trade_rebalance_count": int((result["turnover"].astype(float) > 0).sum()),
                "total_turnover": round(float(result["turnover"].astype(float).sum()), 2),
                "average_exposure": round(float(result["position"].astype(float).mean()), 4),
            }
            for strategy, result in results.items()
        ]
    )


def _money_made_lost(metrics: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    out = metrics[
        [
            "strategy",
            "start_value",
            "end_value",
            "candidate_minus_spy_end_value",
            "candidate_minus_spy_cagr_pct",
            "candidate_max_drawdown_advantage_vs_spy_pct_points",
        ]
    ].copy()
    out["money_made_lost"] = (out["end_value"].astype(float) - initial_capital).round(2)
    return out


def _plot_equity(equity: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for strategy, group in equity.groupby("strategy"):
        ax.plot(pd.to_datetime(group["date"]), group["equity"], label=strategy)
    ax.set_title("Strategy Factory Equity Curves")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_drawdown(drawdown: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for strategy, group in drawdown.groupby("strategy"):
        ax.plot(pd.to_datetime(group["date"]), group["drawdown"], label=strategy)
    ax.set_title("Strategy Factory Drawdowns")
    ax.set_ylabel("Drawdown")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_rolling(rolling: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for strategy, group in rolling.groupby("strategy"):
        if strategy == BENCHMARK_STRATEGY:
            continue
        ax.plot(pd.to_datetime(group["date"]), group["rolling_relative_return"], label=strategy)
    ax.set_title("Rolling Relative Performance vs SPY Buy & Hold")
    ax.set_ylabel("252D relative return")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_allocation(allocation: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    non_cash = allocation[allocation["asset"] != "CASH"].copy()
    exposure = (
        non_cash.groupby(["date", "strategy"], as_index=False)["weight"].sum()
        if not non_cash.empty
        else pd.DataFrame()
    )
    for strategy, group in exposure.groupby("strategy"):
        ax.plot(pd.to_datetime(group["date"]), group["weight"], label=strategy)
    ax.set_title("Strategy Factory Non-Cash Exposure")
    ax.set_ylabel("Exposure")
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _write_dashboard_index(
    *,
    path: Path,
    metrics: pd.DataFrame,
    gate_report: pd.DataFrame,
    data_dir: Path,
) -> None:
    class_rows = gate_report[gate_report["strategy"] != "phase17a_safety_gate"]
    lines = [
        "# Strategy Factory v1",
        "",
        "Visual portfolio candidate tournament. Research and paper-prep only.",
        "",
        "- Live trading allowed: False",
        "- Real money allowed: False",
        "- Broker/API integration allowed: False",
        "- Candidate promotion allowed: False",
        f"- Data directory: `{data_dir}`",
        "",
        "## Outputs",
        "",
        "- `equity_curves.csv` and `charts/equity_curves.png`",
        "- `drawdown_curves.csv` and `charts/drawdown_curves.png`",
        "- `allocation_timeline.csv` and `charts/allocation_timeline.png`",
        "- `rolling_relative_performance.csv` and `charts/rolling_relative_performance.png`",
        "",
        "## Classifications",
        "",
    ]
    for row in class_rows.to_dict(orient="records"):
        lines.append(f"- {row['strategy']}: {row['classification']}")

    best = metrics.sort_values("end_value", ascending=False).iloc[0]
    lines.extend(
        [
            "",
            "## Current Leader",
            "",
            f"- Best end value: {best['strategy']} ({best['end_value']})",
            "",
            "BTC caveat: BTC-USD is aligned through strict common-date intersection "
            "with ETF trading days, so weekend-only BTC observations are excluded.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_phase17a_strategy_factory_report(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    price_data: dict[str, pd.DataFrame] | None = None,
    cash_returns: pd.Series | None = None,
) -> dict[str, pd.DataFrame]:
    section = _phase_config(config)
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "metrics": empty, "gate_report": empty, "conclusion": empty}

    output_dir = Path(section.get("output_dir", "reports/strategy_factory"))
    chart_dir = Path(section.get("chart_dir", output_dir / "charts"))
    dashboard_dir = Path(section.get("dashboard_dir", output_dir / "dashboard"))
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    reports_path = Path(reports_dir)
    if price_data is None:
        price_data, cash_returns, data_dir = _load_price_data(config=config, section=section)
    else:
        data_dir = Path("in_memory_test_data")

    panel = build_strategy_factory_price_panel(price_data, cash_returns=cash_returns)
    overlay_exposure, overlay_status = _load_overlay_exposure(reports_path, section)

    strategy_config = _strategy_factory_config(section)
    results, status = run_strategy_factory_candidates(
        panel,
        config=strategy_config,
        overlay_exposure=overlay_exposure,
    )
    if BENCHMARK_STRATEGY not in results:
        raise ValueError("Strategy Factory benchmark failed to run")

    metrics = pd.DataFrame(
        [calculate_metrics(result, strategy_name) for strategy_name, result in results.items()]
    )
    metrics = _metrics_with_benchmark_comparison(metrics)
    benchmark_comparison = metrics[
        [
            "strategy",
            "end_value",
            "cagr_pct",
            "max_drawdown_pct",
            "calmar",
            "candidate_minus_spy_end_value",
            "candidate_minus_spy_cagr_pct",
            "candidate_max_drawdown_advantage_vs_spy_pct_points",
            "candidate_calmar_advantage_vs_spy",
        ]
    ].copy()
    gate_report = _gate_report(metrics, status, section)

    equity = _equity_curves(results)
    drawdown = _drawdown_curves(results)
    allocation = _allocation_timeline(results)
    rolling = _rolling_relative_performance(results)
    turnover = _turnover_summary(results)
    money = _money_made_lost(metrics, strategy_config.initial_capital)

    safety_failed = any(
        _bool_value(section.get(flag, False))
        for flag in [
            "live_trading_allowed",
            "real_money_allowed",
            "broker_api_integration_allowed",
        ]
    )
    all_strategies_present = set(STRATEGY_FACTORY_CANDIDATES).issubset(results)
    all_gates_passed = bool(all_strategies_present and not safety_failed)

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 17A",
                "candidate_count": len(results),
                "expected_candidate_count": len(STRATEGY_FACTORY_CANDIDATES),
                "start_date": panel["date"].min().date().isoformat(),
                "end_date": panel["date"].max().date().isoformat(),
                "strict_common_date_intersection": True,
                "btc_weekend_rows_excluded": True,
                "cash_return_source": "project_cash_yield" if cash_returns is not None else "zero_cash",
                "phase6_overlay_source_status": overlay_status,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
                "all_gates_passed": all_gates_passed,
            }
        ]
    )

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 17A",
                "diagnostic": "Strategy Factory v1 visual portfolio candidate tournament",
                "decision": (
                    "strategy_factory_tournament_completed_no_promotion"
                    if all_gates_passed
                    else "strategy_factory_tournament_incomplete_or_safety_blocked"
                ),
                "all_gates_passed": all_gates_passed,
                "candidate_promotion_allowed": False,
                "final_candidate_replaced": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )

    summary.to_csv(output_dir / "phase17a_strategy_factory_summary.csv", index=False)
    metrics.to_csv(output_dir / "phase17a_strategy_factory_metrics.csv", index=False)
    benchmark_comparison.to_csv(
        output_dir / "phase17a_strategy_factory_benchmark_comparison.csv",
        index=False,
    )
    gate_report.to_csv(output_dir / "phase17a_strategy_factory_gate_report.csv", index=False)
    conclusion.to_csv(output_dir / "phase17a_strategy_factory_conclusion.csv", index=False)
    equity.to_csv(output_dir / "equity_curves.csv", index=False)
    drawdown.to_csv(output_dir / "drawdown_curves.csv", index=False)
    allocation.to_csv(output_dir / "allocation_timeline.csv", index=False)
    rolling.to_csv(output_dir / "rolling_relative_performance.csv", index=False)
    turnover.to_csv(output_dir / "trade_turnover_summary.csv", index=False)
    money.to_csv(output_dir / "money_made_lost.csv", index=False)

    _plot_equity(equity, chart_dir / "equity_curves.png")
    _plot_drawdown(drawdown, chart_dir / "drawdown_curves.png")
    _plot_rolling(rolling, chart_dir / "rolling_relative_performance.png")
    _plot_allocation(allocation, chart_dir / "allocation_timeline.png")
    _write_dashboard_index(
        path=dashboard_dir / "index.md",
        metrics=metrics,
        gate_report=gate_report,
        data_dir=data_dir,
    )

    outputs = {
        "summary": summary,
        "metrics": metrics,
        "benchmark_comparison": benchmark_comparison,
        "gate_report": gate_report,
        "conclusion": conclusion,
        "equity_curves": equity,
        "drawdown_curves": drawdown,
        "allocation_timeline": allocation,
        "rolling_relative_performance": rolling,
        "trade_turnover_summary": turnover,
        "money_made_lost": money,
        "implementation_status": status,
    }
    print("Wrote Phase 17A Strategy Factory reports.")
    return outputs
