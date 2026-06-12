from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.strategy_factory_report import (
    BENCHMARK_STRATEGY,
    _bool_value,
    _load_overlay_exposure,
    _load_price_data,
    _metrics_with_benchmark_comparison,
    _strategy_factory_config,
)
from market_strats.strategies.strategy_factory import (
    StrategyFactoryConfig,
    build_strategy_factory_price_panel,
    run_sf_spy_buy_hold,
    run_sf_spy_core_phase6_overlay_satellite_qqq,
    run_sf_spy_qqq_60_40_monthly_rebalanced,
    run_sf_spy_qqq_btc_capped_offensive,
    run_sf_spy_qqq_gld_tlt_risk_off_rotation,
    run_sf_spy_qqq_tactical_momentum,
    run_strategy_factory_candidates,
)


PHASE17B_SECTION = "phase17b_strategy_factory_robustness"
PHASE17A_SECTION = "phase17a_strategy_factory"

NON_BTC_STRATEGIES = [
    "sf_spy_buy_hold",
    "sf_spy_qqq_60_40_monthly_rebalanced",
    "sf_spy_qqq_tactical_momentum",
    "sf_spy_qqq_gld_tlt_risk_off_rotation",
    "sf_spy_core_phase6_overlay_satellite_qqq",
]

DEFAULT_FRICTION_SCENARIOS = {
    "no_extra_cost": 0.0,
    "low": 5.0,
    "moderate": 15.0,
    "realistic_stress": 25.0,
    "stress": 50.0,
}

DEFAULT_BTC_EXTRA_BPS = {
    "low": 10.0,
    "moderate": 25.0,
    "realistic_stress": 50.0,
    "stress": 75.0,
}

ROLLING_3Y_BEAT_REFERENCE_THRESHOLD = 60.0


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE17B_SECTION, {}) or {}


def _phase17a_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE17A_SECTION, {}) or {}


def _friction_scenarios(section: dict[str, Any]) -> dict[str, float]:
    raw = section.get("friction_scenarios", {}) or {}
    if not raw:
        return DEFAULT_FRICTION_SCENARIOS.copy()

    scenarios: dict[str, float] = {}
    for name, value in raw.items():
        if isinstance(value, dict):
            scenarios[str(name)] = float(value.get("bps_per_turnover", 0.0))
        else:
            scenarios[str(name)] = float(value)
    return scenarios


def _btc_extra_bps(section: dict[str, Any]) -> dict[str, float]:
    raw = section.get("btc_specific_extra_bps", {}) or {}
    if not raw:
        return DEFAULT_BTC_EXTRA_BPS.copy()
    return {str(name): float(value) for name, value in raw.items()}


def _safety_failed(section: dict[str, Any]) -> bool:
    return any(
        _bool_value(section.get(flag, False))
        for flag in [
            "live_trading_allowed",
            "real_money_allowed",
            "broker_api_integration_allowed",
        ]
    )


def _asset_weight_col(asset: str) -> str:
    return f"{asset.lower().replace('-', '_')}_weight"


def apply_turnover_friction(
    result: pd.DataFrame,
    *,
    bps_per_turnover: float,
    btc_specific_extra_bps: float = 0.0,
    scenario_name: str = "",
) -> pd.DataFrame:
    """Apply simple turnover-proportional return drag without changing positions."""
    if result.empty:
        return result.copy()

    out = result.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").reset_index(drop=True)

    turnover = out.get("turnover", pd.Series(0.0, index=out.index)).astype(float).clip(lower=0.0)
    friction_cost_return = turnover * (float(bps_per_turnover) / 10000.0)

    btc_turnover = pd.Series(0.0, index=out.index)
    if "btc_usd_weight" in out.columns and float(btc_specific_extra_bps) != 0.0:
        btc_weights = out["btc_usd_weight"].astype(float).clip(lower=0.0)
        btc_turnover = btc_weights.diff().abs().fillna(0.0)
        friction_cost_return = friction_cost_return + (
            btc_turnover * (float(btc_specific_extra_bps) / 10000.0)
        )

    if not friction_cost_return.empty:
        friction_cost_return.iloc[0] = 0.0

    gross_returns = out["strategy_return"].astype(float)
    net_returns = (gross_returns - friction_cost_return).clip(lower=-0.999999)
    start_equity = float(out["equity"].iloc[0])

    out["gross_strategy_return"] = gross_returns
    out["strategy_return"] = net_returns
    out["friction_cost_return"] = friction_cost_return
    out["btc_turnover_for_extra_cost"] = btc_turnover
    out["equity"] = start_equity * (1.0 + net_returns).cumprod()
    out["friction_scenario"] = scenario_name
    out["bps_per_turnover"] = float(bps_per_turnover)
    out["btc_specific_extra_bps"] = float(btc_specific_extra_bps)
    return out


def _metrics_table(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    metrics = pd.DataFrame(
        [calculate_metrics(result, strategy_name) for strategy_name, result in results.items()]
    )
    return _metrics_with_benchmark_comparison(metrics)


def _friction_metrics(
    results: dict[str, pd.DataFrame],
    section: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]:
    scenarios = _friction_scenarios(section)
    btc_extra = _btc_extra_bps(section)
    rows: list[pd.DataFrame] = []
    adjusted_results: dict[str, dict[str, pd.DataFrame]] = {}

    for scenario_name, bps in scenarios.items():
        scenario_results = {}
        for strategy, result in results.items():
            has_btc = "btc_usd_weight" in result.columns and float(result["btc_usd_weight"].max()) > 0.0
            extra_bps = btc_extra.get(scenario_name, 0.0) if has_btc else 0.0
            scenario_results[strategy] = apply_turnover_friction(
                result,
                bps_per_turnover=bps,
                btc_specific_extra_bps=extra_bps,
                scenario_name=scenario_name,
            )

        scenario_metrics = _metrics_table(scenario_results)
        scenario_metrics.insert(0, "friction_scenario", scenario_name)
        scenario_metrics.insert(1, "bps_per_turnover", float(bps))
        scenario_metrics.insert(2, "btc_specific_extra_bps", float(btc_extra.get(scenario_name, 0.0)))
        rows.append(scenario_metrics)
        adjusted_results[scenario_name] = scenario_results

    friction_metrics = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    comparison = _friction_scenario_comparison(friction_metrics)
    return friction_metrics, comparison, adjusted_results


def _friction_scenario_comparison(friction_metrics: pd.DataFrame) -> pd.DataFrame:
    if friction_metrics.empty:
        return pd.DataFrame()

    baseline = friction_metrics.loc[
        friction_metrics["friction_scenario"] == "no_extra_cost"
    ].set_index("strategy")
    rows = []
    for row in friction_metrics.to_dict(orient="records"):
        base = baseline.loc[row["strategy"]]
        rows.append(
            {
                "strategy": row["strategy"],
                "friction_scenario": row["friction_scenario"],
                "bps_per_turnover": row["bps_per_turnover"],
                "btc_specific_extra_bps": row["btc_specific_extra_bps"],
                "end_value": row["end_value"],
                "cagr_pct": row["cagr_pct"],
                "max_drawdown_pct": row["max_drawdown_pct"],
                "calmar": row["calmar"],
                "cagr_loss_vs_no_extra_pct_points": round(
                    float(row["cagr_pct"]) - float(base["cagr_pct"]),
                    2,
                ),
                "end_value_loss_vs_no_extra": round(
                    float(row["end_value"]) - float(base["end_value"]),
                    2,
                ),
                "candidate_minus_spy_end_value": row["candidate_minus_spy_end_value"],
                "candidate_minus_spy_cagr_pct": row["candidate_minus_spy_cagr_pct"],
                "candidate_max_drawdown_advantage_vs_spy_pct_points": row[
                    "candidate_max_drawdown_advantage_vs_spy_pct_points"
                ],
            }
        )
    return pd.DataFrame(rows)


def _with_zero_btc_return(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    if "BTC-USD" not in out.columns:
        out["BTC-USD"] = 1.0
    if "BTC-USD_return" not in out.columns:
        out["BTC-USD_return"] = 0.0
    return out


def _run_non_btc_results(
    panel: pd.DataFrame,
    strategy_config: StrategyFactoryConfig,
    *,
    overlay_exposure: pd.Series | None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    non_btc_panel = _with_zero_btc_return(panel)
    overlay_result, overlay_status = run_sf_spy_core_phase6_overlay_satellite_qqq(
        non_btc_panel,
        strategy_config,
        overlay_exposure=overlay_exposure,
    )
    results = {
        "sf_spy_buy_hold": run_sf_spy_buy_hold(non_btc_panel, strategy_config),
        "sf_spy_qqq_60_40_monthly_rebalanced": run_sf_spy_qqq_60_40_monthly_rebalanced(
            non_btc_panel,
            strategy_config,
        ),
        "sf_spy_qqq_tactical_momentum": run_sf_spy_qqq_tactical_momentum(
            non_btc_panel,
            strategy_config,
        ),
        "sf_spy_qqq_gld_tlt_risk_off_rotation": run_sf_spy_qqq_gld_tlt_risk_off_rotation(
            non_btc_panel,
            strategy_config,
        ),
        "sf_spy_core_phase6_overlay_satellite_qqq": overlay_result,
    }
    status = pd.DataFrame(
        [
            {
                "strategy": strategy,
                "implementation_status": (
                    overlay_status
                    if strategy == "sf_spy_core_phase6_overlay_satellite_qqq"
                    else "implemented_etf_only_long_period"
                ),
                "failure_reason": "",
            }
            for strategy in results
        ]
    )
    return results, status


def _non_btc_long_period_metrics(
    *,
    config: dict[str, Any],
    phase17a_section: dict[str, Any],
    reports_dir: Path,
    price_data: dict[str, pd.DataFrame] | None,
    cash_returns: pd.Series | None,
    provided_data_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Path]:
    non_btc_section = {
        **phase17a_section,
        "universe": [
            str(ticker).upper()
            for ticker in phase17a_section.get("universe", ["SPY", "QQQ", "GLD", "TLT"])
            if str(ticker).upper() != "BTC-USD"
        ],
    }
    if not non_btc_section["universe"]:
        non_btc_section["universe"] = ["SPY", "QQQ", "GLD", "TLT"]

    if price_data is None:
        non_btc_price_data, non_btc_cash_returns, data_dir = _load_price_data(
            config=config,
            section=non_btc_section,
        )
    else:
        non_btc_price_data = {
            ticker: frame
            for ticker, frame in price_data.items()
            if str(ticker).upper() != "BTC-USD"
        }
        non_btc_cash_returns = cash_returns
        data_dir = provided_data_dir or Path("in_memory_price_data")

    panel = build_strategy_factory_price_panel(
        non_btc_price_data,
        cash_returns=non_btc_cash_returns,
    )
    overlay_exposure, _overlay_status = _load_overlay_exposure(reports_dir, phase17a_section)
    strategy_config = _strategy_factory_config(phase17a_section)
    results, _status = _run_non_btc_results(
        panel,
        strategy_config,
        overlay_exposure=overlay_exposure,
    )
    metrics = _metrics_table(results)
    metrics.insert(0, "comparison_period", "non_btc_long_etf_only_period")
    metrics["btc_included"] = False
    metrics["btc_calendar_common_date_constraint"] = False
    metrics["data_dir"] = str(data_dir)
    return metrics, results, data_dir


def _btc_cap_sensitivity(
    panel: pd.DataFrame,
    phase17a_section: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    rows = []
    results = {}
    caps = [0.0, 0.05, float(phase17a_section.get("btc_max_weight", 0.10))]
    caps = sorted({round(cap, 4) for cap in caps})

    for cap in caps:
        strategy_name = f"sf_spy_qqq_btc_capped_offensive_cap_{int(round(cap * 100))}pct"
        strategy_config = StrategyFactoryConfig(
            initial_capital=float(phase17a_section.get("initial_capital", 10000)),
            btc_max_weight=float(cap),
            qqq_satellite_max_weight=float(phase17a_section.get("qqq_satellite_max_weight", 0.40)),
            momentum_lookback_days=int(phase17a_section.get("momentum_lookback_days", 126)),
            trend_lookback_days=int(phase17a_section.get("trend_lookback_days", 200)),
        )
        result = run_sf_spy_qqq_btc_capped_offensive(panel, strategy_config).copy()
        result["strategy"] = strategy_name
        results[strategy_name] = result
        row = calculate_metrics(result, strategy_name)
        row["btc_max_weight"] = float(cap)
        row["max_observed_btc_weight"] = round(float(result["btc_usd_weight"].max()), 4)
        rows.append(row)

    sensitivity = pd.DataFrame(rows)
    zero = sensitivity.loc[sensitivity["btc_max_weight"] == 0.0]
    if not zero.empty:
        zero_row = zero.iloc[0]
        sensitivity["candidate_minus_zero_cap_end_value"] = (
            sensitivity["end_value"].astype(float) - float(zero_row["end_value"])
        ).round(2)
        sensitivity["candidate_minus_zero_cap_cagr_pct"] = (
            sensitivity["cagr_pct"].astype(float) - float(zero_row["cagr_pct"])
        ).round(2)
    return sensitivity, results


def _btc_dependency_lookup(btc_sensitivity: pd.DataFrame) -> dict[str, bool]:
    if btc_sensitivity.empty or "btc_max_weight" not in btc_sensitivity.columns:
        return {"sf_spy_qqq_btc_capped_offensive": False}

    zero = btc_sensitivity.loc[btc_sensitivity["btc_max_weight"].astype(float) == 0.0]
    max_cap = btc_sensitivity.sort_values("btc_max_weight").tail(1)
    if zero.empty or max_cap.empty:
        return {"sf_spy_qqq_btc_capped_offensive": False}

    cagr_delta = float(max_cap.iloc[0]["cagr_pct"]) - float(zero.iloc[0]["cagr_pct"])
    end_delta = float(max_cap.iloc[0]["end_value"]) - float(zero.iloc[0]["end_value"])
    return {
        "sf_spy_qqq_btc_capped_offensive": bool(cagr_delta >= 2.0 or end_delta > 0.0)
    }


def create_btc_weekend_gap_diagnostic(
    btc_prices: pd.DataFrame | None,
    *,
    btc_source_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = {
        "diagnostic_available": False,
        "btc_source_path": str(btc_source_path),
        "btc_rows": 0,
        "btc_min_date": "",
        "btc_max_date": "",
        "weekend_gap_count": 0,
        "average_friday_to_monday_return": pd.NA,
        "median_friday_to_monday_return": pd.NA,
        "worst_friday_to_monday_return": pd.NA,
        "best_friday_to_monday_return": pd.NA,
        "gaps_worse_than_minus_5_pct": 0,
        "gaps_worse_than_minus_10_pct": 0,
        "strict_common_date_caveat": (
            "Strategy Factory returns use strict ETF-trading-day common-date alignment; "
            "this diagnostic is report-only and does not change returns."
        ),
        "non_monday_next_available_count": 0,
        "blocking_reason": "",
    }
    if btc_prices is None or btc_prices.empty:
        base["blocking_reason"] = "btc_price_data_missing"
        return pd.DataFrame([base]), pd.DataFrame()

    required = {"date", "adj_close"}
    missing = required - set(btc_prices.columns)
    if missing:
        base["blocking_reason"] = f"btc_price_data_missing_columns:{sorted(missing)}"
        return pd.DataFrame([base]), pd.DataFrame()

    prices = btc_prices[["date", "adj_close"]].copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices["adj_close"] = pd.to_numeric(prices["adj_close"], errors="coerce")
    prices = (
        prices.dropna(subset=["date", "adj_close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )
    if prices.empty:
        base["blocking_reason"] = "btc_price_data_empty_after_cleaning"
        return pd.DataFrame([base]), pd.DataFrame()

    base["btc_rows"] = int(len(prices))
    base["btc_min_date"] = prices["date"].min().date().isoformat()
    base["btc_max_date"] = prices["date"].max().date().isoformat()

    indexed = prices.set_index("date")["adj_close"]
    rows = []
    for row in prices[prices["date"].dt.weekday == 4].itertuples(index=False):
        friday_date = row.date
        monday_date = friday_date + pd.Timedelta(days=3)
        if monday_date in indexed.index:
            gap_date = monday_date
            used_next_available = False
        else:
            candidates = indexed.loc[
                (indexed.index > friday_date)
                & (indexed.index <= friday_date + pd.Timedelta(days=7))
            ]
            if candidates.empty:
                continue
            gap_date = candidates.index[0]
            used_next_available = True

        friday_close = float(row.adj_close)
        gap_close = float(indexed.loc[gap_date])
        if friday_close <= 0:
            continue
        gap_return = (gap_close / friday_close) - 1.0
        rows.append(
            {
                "friday_date": friday_date.date().isoformat(),
                "gap_end_date": gap_date.date().isoformat(),
                "gap_end_weekday": int(gap_date.weekday()),
                "used_next_available_after_friday": used_next_available,
                "friday_close": friday_close,
                "gap_end_close": gap_close,
                "friday_to_monday_return": gap_return,
                "friday_to_monday_return_pct": round(gap_return * 100.0, 4),
            }
        )

    gaps = pd.DataFrame(rows)
    if gaps.empty:
        base["blocking_reason"] = "no_friday_to_monday_gaps_computable"
        return pd.DataFrame([base]), gaps

    returns = gaps["friday_to_monday_return"].astype(float)
    summary = base.copy()
    summary.update(
        {
            "diagnostic_available": True,
            "weekend_gap_count": int(len(gaps)),
            "average_friday_to_monday_return": round(float(returns.mean()) * 100.0, 4),
            "median_friday_to_monday_return": round(float(returns.median()) * 100.0, 4),
            "worst_friday_to_monday_return": round(float(returns.min()) * 100.0, 4),
            "best_friday_to_monday_return": round(float(returns.max()) * 100.0, 4),
            "gaps_worse_than_minus_5_pct": int((returns <= -0.05).sum()),
            "gaps_worse_than_minus_10_pct": int((returns <= -0.10).sum()),
            "non_monday_next_available_count": int(
                gaps["used_next_available_after_friday"].astype(bool).sum()
            ),
        }
    )
    return pd.DataFrame([summary]), gaps


def _plot_btc_weekend_gap_distribution(
    gaps: pd.DataFrame,
    *,
    diagnostic_available: bool,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    if diagnostic_available and not gaps.empty:
        ax.hist(gaps["friday_to_monday_return_pct"].astype(float), bins=40, alpha=0.8)
        ax.axvline(0.0, color="black", linewidth=0.8)
        ax.set_xlabel("Friday-to-Monday BTC return %")
        ax.set_ylabel("Count")
        ax.set_title("Phase 17B BTC Weekend Gap Distribution")
    else:
        ax.text(
            0.5,
            0.5,
            "BTC weekend gap diagnostic unavailable",
            ha="center",
            va="center",
        )
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _rolling_relative_series(
    results: dict[str, pd.DataFrame],
    *,
    window: int,
) -> pd.DataFrame:
    benchmark = results[BENCHMARK_STRATEGY][["date", "equity"]].copy()
    benchmark["date"] = pd.to_datetime(benchmark["date"])
    benchmark = benchmark.rename(columns={"equity": "benchmark_equity"})
    rows = []
    annualisation = 252.0 / float(window)

    for strategy, result in results.items():
        candidate = result[["date", "equity"]].copy()
        candidate["date"] = pd.to_datetime(candidate["date"])
        merged = candidate.merge(benchmark, on="date", how="inner").sort_values("date")
        candidate_return = merged["equity"].pct_change(window)
        benchmark_return = merged["benchmark_equity"].pct_change(window)
        candidate_cagr = ((1.0 + candidate_return) ** annualisation) - 1.0
        benchmark_cagr = ((1.0 + benchmark_return) ** annualisation) - 1.0
        merged["strategy"] = strategy
        merged["window_trading_days"] = int(window)
        merged["candidate_rolling_cagr_pct"] = (candidate_cagr * 100.0).round(4)
        merged["benchmark_rolling_cagr_pct"] = (benchmark_cagr * 100.0).round(4)
        merged["rolling_relative_cagr_pct"] = (
            (candidate_cagr - benchmark_cagr) * 100.0
        ).round(4)
        rows.append(
            merged.dropna(
                subset=[
                    "candidate_rolling_cagr_pct",
                    "benchmark_rolling_cagr_pct",
                    "rolling_relative_cagr_pct",
                ]
            )[
                [
                    "date",
                    "strategy",
                    "window_trading_days",
                    "candidate_rolling_cagr_pct",
                    "benchmark_rolling_cagr_pct",
                    "rolling_relative_cagr_pct",
                ]
            ]
        )

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _rolling_relative_summary(
    results: dict[str, pd.DataFrame],
    windows: list[int],
) -> tuple[pd.DataFrame, dict[int, pd.DataFrame]]:
    series_by_window = {
        int(window): _rolling_relative_series(results, window=int(window)) for window in windows
    }
    rows = []
    for window, series in series_by_window.items():
        if series.empty:
            continue
        for strategy, group in series.groupby("strategy"):
            relative = group["rolling_relative_cagr_pct"].astype(float)
            rows.append(
                {
                    "strategy": strategy,
                    "window_trading_days": int(window),
                    "observation_count": int(len(group)),
                    "average_relative_cagr_pct": round(float(relative.mean()), 2),
                    "median_relative_cagr_pct": round(float(relative.median()), 2),
                    "latest_relative_cagr_pct": round(float(relative.iloc[-1]), 2),
                    "best_relative_cagr_pct": round(float(relative.max()), 2),
                    "worst_relative_cagr_pct": round(float(relative.min()), 2),
                    "positive_relative_window_pct": round(float((relative > 0).mean() * 100.0), 2),
                }
            )
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary, series_by_window

    field_map = {
        252: {
            "positive_relative_window_pct": "rolling_1y_candidate_beats_spy_pct",
            "worst_relative_cagr_pct": "worst_1y_active_cagr",
            "median_relative_cagr_pct": "median_1y_active_cagr",
            "latest_relative_cagr_pct": "latest_1y_active_cagr",
        },
        756: {
            "positive_relative_window_pct": "rolling_3y_candidate_beats_spy_pct",
            "worst_relative_cagr_pct": "worst_3y_active_cagr",
            "median_relative_cagr_pct": "median_3y_active_cagr",
            "latest_relative_cagr_pct": "latest_3y_active_cagr",
        },
    }
    for mapping in field_map.values():
        for target_field in mapping.values():
            summary[target_field] = pd.NA

    for window, mapping in field_map.items():
        window_rows = summary.loc[summary["window_trading_days"] == window]
        if window_rows.empty:
            continue
        lookup = window_rows.set_index("strategy")
        for source_field, target_field in mapping.items():
            summary[target_field] = summary["strategy"].map(lookup[source_field])

    return summary, series_by_window


def _slice_result(
    result: pd.DataFrame,
    *,
    start: str | None,
    end: str | None,
    initial_capital: float,
) -> pd.DataFrame:
    out = result.copy()
    out["date"] = pd.to_datetime(out["date"])
    if start:
        out = out[out["date"] >= pd.to_datetime(start)]
    if end:
        out = out[out["date"] <= pd.to_datetime(end)]
    out = out.sort_values("date").reset_index(drop=True)
    if len(out) < 2:
        return pd.DataFrame()

    period_returns = out["equity"].astype(float).pct_change().fillna(0.0)
    out["strategy_return"] = period_returns
    out["equity"] = float(initial_capital) * (1.0 + period_returns).cumprod()
    return out


def _subperiod_metrics(
    *,
    results: dict[str, pd.DataFrame],
    non_btc_results: dict[str, pd.DataFrame],
    section: dict[str, Any],
    phase17a_section: dict[str, Any],
) -> pd.DataFrame:
    initial_capital = float(phase17a_section.get("initial_capital", 10000))
    first_date = pd.to_datetime(results[BENCHMARK_STRATEGY]["date"]).min().date().isoformat()
    last_date = pd.to_datetime(results[BENCHMARK_STRATEGY]["date"]).max().date().isoformat()
    periods: dict[str, dict[str, str | None]] = {
        "full_phase17a_common_period": {"start": first_date, "end": last_date},
    }
    periods.update(
        {
            str(name): {"start": value.get("start"), "end": value.get("end")}
            for name, value in (section.get("subperiods", {}) or {}).items()
        }
    )

    rows = []
    for period_name, period in periods.items():
        period_results = {}
        for strategy, result in results.items():
            sliced = _slice_result(
                result,
                start=period.get("start"),
                end=period.get("end"),
                initial_capital=initial_capital,
            )
            if not sliced.empty:
                period_results[strategy] = sliced
        if BENCHMARK_STRATEGY in period_results:
            metrics = _metrics_table(period_results)
            metrics.insert(0, "subperiod", period_name)
            metrics["btc_included"] = True
            rows.append(metrics)

    non_btc_period_results = {}
    for strategy, result in non_btc_results.items():
        sliced = _slice_result(
            result,
            start=None,
            end=None,
            initial_capital=initial_capital,
        )
        if not sliced.empty:
            non_btc_period_results[strategy] = sliced
    if BENCHMARK_STRATEGY in non_btc_period_results:
        metrics = _metrics_table(non_btc_period_results)
        metrics.insert(0, "subperiod", "non_btc_long_etf_only_period")
        metrics["btc_included"] = False
        rows.append(metrics)

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def classify_phase17b_shortlist(
    strategy: str,
    strategy_metrics: pd.DataFrame,
    *,
    rolling_3y_beats_spy_pct: float | None = None,
) -> str:
    if strategy == BENCHMARK_STRATEGY:
        return "rejected"

    by_scenario = strategy_metrics.set_index("friction_scenario")
    required = {"no_extra_cost", "low", "realistic_stress"}
    if not required.issubset(by_scenario.index):
        return "rejected"

    no_cost = by_scenario.loc["no_extra_cost"]
    low = by_scenario.loc["low"]
    realistic_stress = by_scenario.loc["realistic_stress"]
    rolling_reported = rolling_3y_beats_spy_pct is not None and pd.notna(
        rolling_3y_beats_spy_pct
    )
    rolling_passed = bool(
        rolling_reported
        and float(rolling_3y_beats_spy_pct) >= ROLLING_3Y_BEAT_REFERENCE_THRESHOLD
    )

    low_growth = (
        float(low["candidate_minus_spy_end_value"]) > 0.0
        and float(low["candidate_minus_spy_cagr_pct"]) > 0.0
        and float(low["candidate_max_drawdown_advantage_vs_spy_pct_points"]) >= -5.0
    )
    realistic_stress_resilient = (
        float(realistic_stress["candidate_minus_spy_end_value"]) > 0.0
        and float(realistic_stress["candidate_minus_spy_cagr_pct"]) > 0.0
        and float(realistic_stress["candidate_max_drawdown_advantage_vs_spy_pct_points"]) >= -5.0
    )
    low_balanced = (
        float(low["candidate_minus_spy_cagr_pct"]) >= -0.75
        and float(low["candidate_max_drawdown_advantage_vs_spy_pct_points"]) >= 10.0
    )
    no_cost_growth = (
        float(no_cost["candidate_minus_spy_end_value"]) > 0.0
        and float(no_cost["candidate_minus_spy_cagr_pct"]) > 0.0
    )

    if low_growth and realistic_stress_resilient and rolling_passed:
        return "paper_watchlist_growth"
    if low_growth and (not realistic_stress_resilient or not rolling_passed):
        return "needs_friction_retest"
    if low_balanced and rolling_passed:
        return "paper_watchlist_balanced"
    if no_cost_growth:
        return "needs_friction_retest"
    if float(no_cost["candidate_minus_spy_cagr_pct"]) > -1.5:
        return "research_only"
    return "rejected"


def _shortlist_decision(
    friction_metrics: pd.DataFrame,
    *,
    rolling_summary: pd.DataFrame,
    btc_sensitivity: pd.DataFrame,
    btc_weekend_gap_diagnostic: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    rolling_lookup = (
        rolling_summary.drop_duplicates("strategy").set_index("strategy")
        if not rolling_summary.empty
        else pd.DataFrame()
    )
    btc_dependency = _btc_dependency_lookup(btc_sensitivity)
    btc_weekend_available = bool(
        not btc_weekend_gap_diagnostic.empty
        and bool(btc_weekend_gap_diagnostic.iloc[0].get("diagnostic_available", False))
    )

    for strategy, group in friction_metrics.groupby("strategy"):
        low = group.loc[group["friction_scenario"] == "low"]
        no_cost = group.loc[group["friction_scenario"] == "no_extra_cost"]
        moderate = group.loc[group["friction_scenario"] == "moderate"]
        realistic_stress = group.loc[group["friction_scenario"] == "realistic_stress"]
        stress = group.loc[group["friction_scenario"] == "stress"]
        rolling_row = (
            rolling_lookup.loc[strategy]
            if not rolling_lookup.empty and strategy in rolling_lookup.index
            else pd.Series(dtype=object)
        )
        rolling_3y_beats = rolling_row.get("rolling_3y_candidate_beats_spy_pct", pd.NA)
        rolling_passed = bool(
            pd.notna(rolling_3y_beats)
            and float(rolling_3y_beats) >= ROLLING_3Y_BEAT_REFERENCE_THRESHOLD
        )
        classification = classify_phase17b_shortlist(
            strategy,
            group,
            rolling_3y_beats_spy_pct=(
                float(rolling_3y_beats) if pd.notna(rolling_3y_beats) else None
            ),
        )
        paper_watchlist_only = classification.startswith("paper_watchlist")
        rows.append(
            {
                "strategy": strategy,
                "phase17b_classification": classification,
                "no_extra_cost_cagr_pct": (
                    float(no_cost.iloc[0]["cagr_pct"]) if not no_cost.empty else pd.NA
                ),
                "low_friction_cagr_pct": (
                    float(low.iloc[0]["cagr_pct"]) if not low.empty else pd.NA
                ),
                "moderate_friction_cagr_pct": (
                    float(moderate.iloc[0]["cagr_pct"]) if not moderate.empty else pd.NA
                ),
                "realistic_stress_friction_cagr_pct": (
                    float(realistic_stress.iloc[0]["cagr_pct"])
                    if not realistic_stress.empty
                    else pd.NA
                ),
                "stress_friction_cagr_pct": (
                    float(stress.iloc[0]["cagr_pct"]) if not stress.empty else pd.NA
                ),
                "low_candidate_minus_spy_cagr_pct": (
                    float(low.iloc[0]["candidate_minus_spy_cagr_pct"])
                    if not low.empty
                    else pd.NA
                ),
                "low_drawdown_advantage_vs_spy_pct_points": (
                    float(low.iloc[0]["candidate_max_drawdown_advantage_vs_spy_pct_points"])
                    if not low.empty
                    else pd.NA
                ),
                "realistic_stress_candidate_minus_spy_cagr_pct": (
                    float(realistic_stress.iloc[0]["candidate_minus_spy_cagr_pct"])
                    if not realistic_stress.empty
                    else pd.NA
                ),
                "rolling_3y_candidate_beats_spy_pct": rolling_3y_beats,
                "rolling_3y_beats_spy_reference_threshold": (
                    ROLLING_3Y_BEAT_REFERENCE_THRESHOLD
                ),
                "rolling_3y_beats_spy_reference_passed": rolling_passed,
                "btc_cap_dependency_flag": bool(btc_dependency.get(strategy, False)),
                "btc_weekend_gap_diagnostic_available": btc_weekend_available,
                "promotion_allowed": False,
                "paper_watchlist_only": paper_watchlist_only,
                "candidate_promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        )
    return pd.DataFrame(rows)


def _plot_grouped_metric(
    frame: pd.DataFrame,
    *,
    metric: str,
    title: str,
    ylabel: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    pivot = frame.pivot(index="strategy", columns="friction_scenario", values=metric)
    pivot.plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_btc_sensitivity(frame: pd.DataFrame, path: Path) -> None:
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(frame["btc_max_weight"], frame["cagr_pct"], marker="o", label="CAGR %")
    ax1.set_xlabel("BTC max weight")
    ax1.set_ylabel("CAGR %")
    ax1.grid(True, alpha=0.25)
    ax2 = ax1.twinx()
    ax2.plot(
        frame["btc_max_weight"],
        frame["max_drawdown_pct"],
        marker="s",
        color="tab:red",
        label="Max drawdown %",
    )
    ax2.set_ylabel("Max drawdown %")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, fontsize=8)
    ax1.set_title("Phase 17B BTC Cap Sensitivity")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_equity(results: dict[str, pd.DataFrame], path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for strategy, result in results.items():
        ax.plot(pd.to_datetime(result["date"]), result["equity"], label=strategy)
    ax.set_title(title)
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_rolling(series: pd.DataFrame, path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for strategy, group in series.groupby("strategy"):
        if strategy == BENCHMARK_STRATEGY:
            continue
        ax.plot(
            pd.to_datetime(group["date"]),
            group["rolling_relative_cagr_pct"],
            label=strategy,
        )
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel("Rolling relative CAGR %")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _write_dashboard_index(
    *,
    path: Path,
    shortlist: pd.DataFrame,
    summary: pd.DataFrame,
    btc_weekend_gap_diagnostic: pd.DataFrame,
) -> None:
    btc_weekend_available = bool(
        not btc_weekend_gap_diagnostic.empty
        and bool(btc_weekend_gap_diagnostic.iloc[0].get("diagnostic_available", False))
    )
    lines = [
        "# Strategy Factory Dashboard",
        "",
        "Research and paper-prep only. No Strategy Factory candidate is promoted.",
        "",
        "- Live trading allowed: False",
        "- Real money allowed: False",
        "- Broker/API integration allowed: False",
        "- Candidate promotion allowed: False",
        "",
        "## Phase 17A Tournament Outputs",
        "",
        "- `../phase17a_strategy_factory_metrics.csv`",
        "- `../equity_curves.csv`",
        "- `../drawdown_curves.csv`",
        "- `../allocation_timeline.csv`",
        "- `../charts/equity_curves.png`",
        "",
        "## Phase 17B Robustness Outputs",
        "",
        "- Friction scenarios include no cost, low, moderate, realistic-stress 25 bps, and stress.",
        "- `../phase17b_friction_metrics.csv`",
        "- `../phase17b_friction_scenario_comparison.csv`",
        "- `../phase17b_non_btc_long_period_metrics.csv`",
        "- `../phase17b_btc_cap_sensitivity.csv`",
        "- `../phase17b_btc_weekend_gap_diagnostic.csv`",
        "- `../phase17b_rolling_relative_summary.csv`",
        "- `../phase17b_subperiod_metrics.csv`",
        "- `../phase17b_shortlist_decision.csv`",
        "- `../charts/phase17b_friction_cagr.png`",
        "- `../charts/phase17b_friction_max_drawdown.png`",
        "- `../charts/phase17b_btc_cap_sensitivity.png`",
        "- `../charts/phase17b_btc_weekend_gap_distribution.png`",
        "- `../charts/phase17b_non_btc_long_period_equity.png`",
        "- `../charts/phase17b_rolling_relative_1y.png`",
        "- `../charts/phase17b_rolling_relative_3y.png`",
        "",
        "Rolling robustness includes active CAGR beat-rate versus SPY, with a visible 60% "
        "3Y reference threshold for shortlist decisions.",
        f"BTC weekend/gap diagnostic available: {btc_weekend_available}",
        "",
        "## Phase 17B Shortlist",
        "",
    ]
    for row in shortlist.to_dict(orient="records"):
        lines.append(f"- {row['strategy']}: {row['phase17b_classification']}")

    summary_row = summary.iloc[0] if not summary.empty else {}
    lines.extend(
        [
            "",
            "## Caveats",
            "",
            "- Friction is a simple turnover-proportional stress, not a full execution simulator.",
            "- BTC-USD uses strict ETF-trading-day common-date alignment; weekend-only BTC observations are excluded.",
            "- BTC cap dependency is marked separately in `phase17b_shortlist_decision.csv`.",
            "- Phase 17B is a shortlist decision only and does not replace the current final candidate.",
            f"- Phase 17B decision: {summary_row.get('decision', '')}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gate_report(
    *,
    section: dict[str, Any],
    friction_metrics: pd.DataFrame,
    non_btc_metrics: pd.DataFrame,
    btc_sensitivity: pd.DataFrame,
    btc_weekend_gap_diagnostic: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    shortlist: pd.DataFrame,
) -> pd.DataFrame:
    safety_failed = _safety_failed(section)
    rows = [
        {
            "gate": "safety_flags_false",
            "gate_status": "failed" if safety_failed else "passed",
            "details": "live/real-money/broker flags must remain false",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "candidate_promotion_allowed": False,
        },
        {
            "gate": "friction_metrics_generated",
            "gate_status": "passed" if not friction_metrics.empty else "failed",
            "details": f"rows={len(friction_metrics)}",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "candidate_promotion_allowed": False,
        },
        {
            "gate": "non_btc_long_period_generated",
            "gate_status": "passed" if not non_btc_metrics.empty else "failed",
            "details": f"rows={len(non_btc_metrics)}",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "candidate_promotion_allowed": False,
        },
        {
            "gate": "btc_cap_sensitivity_generated",
            "gate_status": "passed" if not btc_sensitivity.empty else "failed",
            "details": f"rows={len(btc_sensitivity)}",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "candidate_promotion_allowed": False,
        },
        {
            "gate": "btc_weekend_gap_diagnostic_written",
            "gate_status": "passed" if not btc_weekend_gap_diagnostic.empty else "failed",
            "details": f"rows={len(btc_weekend_gap_diagnostic)}",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "candidate_promotion_allowed": False,
        },
        {
            "gate": "rolling_relative_generated",
            "gate_status": "passed" if not rolling_summary.empty else "failed",
            "details": f"rows={len(rolling_summary)}",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "candidate_promotion_allowed": False,
        },
        {
            "gate": "shortlist_generated_no_promotion",
            "gate_status": "passed" if not shortlist.empty else "failed",
            "details": f"rows={len(shortlist)}",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "candidate_promotion_allowed": False,
        },
    ]
    return pd.DataFrame(rows)


def save_phase17b_strategy_factory_robustness(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    price_data: dict[str, pd.DataFrame] | None = None,
    cash_returns: pd.Series | None = None,
) -> dict[str, pd.DataFrame]:
    section = _phase_config(config)
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "summary": empty,
            "friction_metrics": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    phase17a_section = _phase17a_config(config)
    reports_path = Path(reports_dir)

    # Prefer the caller's reports_dir for tests and focused runs.  Older
    # configs may provide an explicit output_dir; when they do, respect it.
    # The extra mkdir immediately before writes below is intentional defensive
    # hardening against tests that use fresh tmp_path report roots.
    output_dir = Path(section.get("output_dir", reports_path / "strategy_factory"))
    chart_dir = Path(section.get("chart_dir", output_dir / "charts"))
    dashboard_dir = Path(section.get("dashboard_dir", output_dir / "dashboard"))
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    if price_data is None:
        price_data, cash_returns, data_dir = _load_price_data(
            config=config,
            section=phase17a_section,
        )
    else:
        data_dir = Path("in_memory_test_data")

    btc_prices = None
    for ticker, frame in price_data.items():
        if str(ticker).upper() == "BTC-USD":
            btc_prices = frame
            break
    btc_source_path = data_dir / "BTC-USD.parquet"
    if data_dir == Path("in_memory_test_data"):
        btc_source_path = Path("in_memory_test_data/BTC-USD")
    btc_weekend_gap_diagnostic, btc_weekend_gap_rows = create_btc_weekend_gap_diagnostic(
        btc_prices,
        btc_source_path=btc_source_path,
    )

    panel = build_strategy_factory_price_panel(price_data, cash_returns=cash_returns)
    overlay_exposure, overlay_status = _load_overlay_exposure(reports_path, phase17a_section)
    strategy_config = _strategy_factory_config(phase17a_section)
    results, status = run_strategy_factory_candidates(
        panel,
        config=strategy_config,
        overlay_exposure=overlay_exposure,
    )
    if BENCHMARK_STRATEGY not in results:
        raise ValueError("Phase 17B requires the Strategy Factory SPY benchmark")

    friction_metrics, friction_comparison, adjusted_results = _friction_metrics(results, section)
    non_btc_metrics, non_btc_results, non_btc_data_dir = _non_btc_long_period_metrics(
        config=config,
        phase17a_section=phase17a_section,
        reports_dir=reports_path,
        price_data=price_data,
        cash_returns=cash_returns,
        provided_data_dir=data_dir,
    )
    btc_sensitivity, btc_sensitivity_results = _btc_cap_sensitivity(panel, phase17a_section)
    rolling_windows = [
        int(window) for window in section.get("rolling_windows_trading_days", [252, 756])
    ]
    rolling_summary, rolling_series_by_window = _rolling_relative_summary(
        results,
        rolling_windows,
    )
    subperiod_metrics = _subperiod_metrics(
        results=results,
        non_btc_results=non_btc_results,
        section=section,
        phase17a_section=phase17a_section,
    )
    shortlist = _shortlist_decision(
        friction_metrics,
        rolling_summary=rolling_summary,
        btc_sensitivity=btc_sensitivity,
        btc_weekend_gap_diagnostic=btc_weekend_gap_diagnostic,
    )
    gate_report = _gate_report(
        section=section,
        friction_metrics=friction_metrics,
        non_btc_metrics=non_btc_metrics,
        btc_sensitivity=btc_sensitivity,
        btc_weekend_gap_diagnostic=btc_weekend_gap_diagnostic,
        rolling_summary=rolling_summary,
        shortlist=shortlist,
    )

    all_gates_passed = bool((gate_report["gate_status"] == "passed").all())
    best_growth = shortlist.loc[
        shortlist["phase17b_classification"] == "paper_watchlist_growth",
        "strategy",
    ]
    best_balanced = shortlist.loc[
        shortlist["phase17b_classification"] == "paper_watchlist_balanced",
        "strategy",
    ]

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 17B",
                "diagnostic": "Strategy Factory robustness, friction, and shortlist decision",
                "decision": (
                    "strategy_factory_robustness_completed_no_promotion"
                    if all_gates_passed
                    else "strategy_factory_robustness_failed_closed"
                ),
                "candidate_count": len(results),
                "friction_scenario_count": len(_friction_scenarios(section)),
                "rolling_windows_trading_days": ",".join(str(w) for w in rolling_windows),
                "subperiod_count": int(subperiod_metrics["subperiod"].nunique())
                if not subperiod_metrics.empty
                else 0,
                "non_btc_long_period_start": non_btc_metrics["start_date"].min()
                if not non_btc_metrics.empty
                else "",
                "non_btc_long_period_end": non_btc_metrics["end_date"].max()
                if not non_btc_metrics.empty
                else "",
                "phase17a_common_period_start": panel["date"].min().date().isoformat(),
                "phase17a_common_period_end": panel["date"].max().date().isoformat(),
                "btc_calendar_alignment": "strict_common_etf_trading_days_weekends_excluded",
                "btc_weekend_gap_diagnostic_available": bool(
                    btc_weekend_gap_diagnostic.iloc[0]["diagnostic_available"]
                )
                if not btc_weekend_gap_diagnostic.empty
                else False,
                "phase6_overlay_source_status": overlay_status,
                "non_btc_data_dir": str(non_btc_data_dir),
                "best_growth_watchlist_strategy": ",".join(best_growth.astype(str).tolist()),
                "best_balanced_watchlist_strategy": ",".join(best_balanced.astype(str).tolist()),
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "candidate_promotion_allowed": False,
                "all_gates_passed": all_gates_passed,
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 17B",
                "decision": summary.iloc[0]["decision"],
                "all_gates_passed": all_gates_passed,
                "shortlist_only": True,
                "candidate_promotion_allowed": False,
                "final_candidate_replaced": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    summary.to_csv(output_dir / "phase17b_strategy_factory_robustness_summary.csv", index=False)
    friction_metrics.to_csv(output_dir / "phase17b_friction_metrics.csv", index=False)
    friction_comparison.to_csv(
        output_dir / "phase17b_friction_scenario_comparison.csv",
        index=False,
    )
    non_btc_metrics.to_csv(output_dir / "phase17b_non_btc_long_period_metrics.csv", index=False)
    btc_sensitivity.to_csv(output_dir / "phase17b_btc_cap_sensitivity.csv", index=False)
    btc_weekend_gap_diagnostic.to_csv(
        output_dir / "phase17b_btc_weekend_gap_diagnostic.csv",
        index=False,
    )
    rolling_summary.to_csv(output_dir / "phase17b_rolling_relative_summary.csv", index=False)
    subperiod_metrics.to_csv(output_dir / "phase17b_subperiod_metrics.csv", index=False)
    shortlist.to_csv(output_dir / "phase17b_shortlist_decision.csv", index=False)
    gate_report.to_csv(output_dir / "phase17b_gate_report.csv", index=False)
    conclusion.to_csv(output_dir / "phase17b_conclusion.csv", index=False)

    _plot_grouped_metric(
        friction_metrics,
        metric="cagr_pct",
        title="Phase 17B Friction Stress: CAGR",
        ylabel="CAGR %",
        path=chart_dir / "phase17b_friction_cagr.png",
    )
    _plot_grouped_metric(
        friction_metrics,
        metric="max_drawdown_pct",
        title="Phase 17B Friction Stress: Max Drawdown",
        ylabel="Max drawdown %",
        path=chart_dir / "phase17b_friction_max_drawdown.png",
    )
    _plot_btc_sensitivity(
        btc_sensitivity,
        chart_dir / "phase17b_btc_cap_sensitivity.png",
    )
    _plot_btc_weekend_gap_distribution(
        btc_weekend_gap_rows,
        diagnostic_available=bool(
            not btc_weekend_gap_diagnostic.empty
            and bool(btc_weekend_gap_diagnostic.iloc[0]["diagnostic_available"])
        ),
        path=chart_dir / "phase17b_btc_weekend_gap_distribution.png",
    )
    _plot_equity(
        non_btc_results,
        chart_dir / "phase17b_non_btc_long_period_equity.png",
        "Phase 17B Non-BTC ETF-Only Long-Period Equity",
    )
    if 252 in rolling_series_by_window:
        _plot_rolling(
            rolling_series_by_window[252],
            chart_dir / "phase17b_rolling_relative_1y.png",
            "Phase 17B Rolling 1Y Relative CAGR vs SPY",
        )
    if 756 in rolling_series_by_window:
        _plot_rolling(
            rolling_series_by_window[756],
            chart_dir / "phase17b_rolling_relative_3y.png",
            "Phase 17B Rolling 3Y Relative CAGR vs SPY",
        )
    _write_dashboard_index(
        path=dashboard_dir / "index.md",
        shortlist=shortlist,
        summary=summary,
        btc_weekend_gap_diagnostic=btc_weekend_gap_diagnostic,
    )

    outputs = {
        "summary": summary,
        "friction_metrics": friction_metrics,
        "friction_scenario_comparison": friction_comparison,
        "non_btc_long_period_metrics": non_btc_metrics,
        "btc_cap_sensitivity": btc_sensitivity,
        "btc_weekend_gap_diagnostic": btc_weekend_gap_diagnostic,
        "btc_weekend_gap_rows": btc_weekend_gap_rows,
        "rolling_relative_summary": rolling_summary,
        "subperiod_metrics": subperiod_metrics,
        "shortlist_decision": shortlist,
        "gate_report": gate_report,
        "conclusion": conclusion,
        "implementation_status": status,
        "adjusted_results_no_extra_cost": adjusted_results.get("no_extra_cost", {}),
        "btc_sensitivity_results": btc_sensitivity_results,
    }
    print("Wrote Phase 17B Strategy Factory robustness reports.")
    return outputs
