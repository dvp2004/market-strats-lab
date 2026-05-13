from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.plots import plot_drawdowns, plot_equity_curves
from market_strats.analysis.rolling import (
    calculate_rolling_window_metrics,
    create_rolling_summary,
)
from market_strats.strategies.fixed_weight_portfolio import (
    get_common_strategy_dates,
    rebase_strategy_result_to_dates,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _safe_filename(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


def _get_strategy_result(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
    strategy: str,
) -> pd.DataFrame:
    ticker = ticker.upper()

    if ticker not in ticker_outputs:
        raise ValueError(f"Ticker {ticker} not found in ticker outputs")

    strategy_results = ticker_outputs[ticker].get("strategy_results")

    if strategy_results is None:
        raise ValueError(f"Ticker {ticker} output is missing strategy_results")

    if strategy not in strategy_results:
        available = sorted(strategy_results.keys())
        raise ValueError(
            f"Strategy '{strategy}' not found for {ticker}. Available: {available}"
        )

    return strategy_results[strategy]


def _create_mode_summary(overlay_result: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for mode, group in overlay_result.groupby("selected_mode"):
        returns = group["strategy_return"].astype(float)

        rows.append(
            {
                "selected_mode": mode,
                "days": len(group),
                "pct_days": len(group) / len(overlay_result) * 100.0,
                "total_return_pct": ((1.0 + returns).prod() - 1.0) * 100.0,
                "avg_daily_return_pct": returns.mean() * 100.0,
                "worst_daily_return_pct": returns.min() * 100.0,
                "avg_position_pct": group["position"].astype(float).mean() * 100.0,
                "avg_cash_pct": group["cash_position"].astype(float).mean() * 100.0,
                "avg_overlay_turnover_pct": group["overlay_turnover"].astype(float).mean()
                * 100.0,
            }
        )

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.sort_values("pct_days", ascending=False).reset_index(drop=True)


def _write_regime_switch_overlay_markdown(
    name: str,
    metrics: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    mode_summary: pd.DataFrame,
    output_path: str | Path,
    equity_plot_path: str | Path,
    drawdown_plot_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_table = metrics.to_markdown(index=False)
    rolling_table = (
        rolling_summary.to_markdown(index=False)
        if not rolling_summary.empty
        else "No rolling summary available."
    )
    mode_table = (
        mode_summary.to_markdown(index=False)
        if not mode_summary.empty
        else "No mode summary available."
    )

    content = f"""# Regime Switch Overlay: {name}

This report tests the first regime-switching overlay.

## Rule

- If SPY is confirmed above its 200D SMA, hold SPY buy-and-hold.
- If SPY is confirmed below its 200D SMA, hold the constrained trend-confirmed relative momentum allocator.
- Confirmation is controlled by the configured `confirmation_days` parameter.
- Signal is observed using current close.
- Execution occurs on the next trading day.
- Position affects returns from the day after execution.

## Full-Period Metrics

{metrics_table}

## Rolling-Window Summary

{rolling_table}

## Mode Summary

{mode_table}

## Charts

![Regime Switch Equity Curves]({Path(equity_plot_path).as_posix()})

![Regime Switch Drawdowns]({Path(drawdown_plot_path).as_posix()})

## Interpretation Notes

- This is the first direct test of the regime diagnostic.
- It is intentionally simple: one regime signal and one defensive allocator.
- If it improves CAGR without destroying drawdown control, Phase 2 becomes much more interesting.
- If it fails, the allocator may be useful only as a defensive standalone portfolio, not a regime overlay.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def run_regime_switch_overlay_report(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    overlay_config = config.get("regime_switch_overlay", {})

    if not overlay_config.get("enabled", False):
        return {
            "overlay_result": pd.DataFrame(),
            "metrics": pd.DataFrame(),
            "rolling_summary": pd.DataFrame(),
            "mode_summary": pd.DataFrame(),
        }

    if not relative_momentum_outputs:
        return {
            "overlay_result": pd.DataFrame(),
            "metrics": pd.DataFrame(),
            "rolling_summary": pd.DataFrame(),
            "mode_summary": pd.DataFrame(),
        }

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    name = str(overlay_config["name"])
    benchmark_ticker = str(overlay_config.get("benchmark_ticker", "SPY")).upper()
    offensive_strategy = str(overlay_config.get("offensive_strategy", "Buy and Hold"))
    defensive_allocator_name = str(overlay_config["defensive_allocator_name"])

    if defensive_allocator_name not in relative_momentum_outputs:
        available = sorted(relative_momentum_outputs.keys())
        raise ValueError(
            f"Defensive allocator '{defensive_allocator_name}' not found. "
            f"Available: {available}"
        )

    defensive_result = relative_momentum_outputs[defensive_allocator_name][
        "allocator_result"
    ]

    defensive_dates = list(pd.to_datetime(defensive_result["date"]))

    offensive_result = rebase_strategy_result_to_dates(
        result=_get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=benchmark_ticker,
            strategy=offensive_strategy,
        ),
        dates=defensive_dates,
        initial_capital=float(config["initial_capital"]),
    )

    overlay_result = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        initial_capital=float(config["initial_capital"]),
        trend_sma_days=int(overlay_config.get("trend_sma_days", 200)),
        slippage_bps=float(config.get("slippage_bps", 0.0)),
        confirmation_days=int(overlay_config.get("confirmation_days", 1)),
    )

    common_dates = get_common_strategy_dates({name: overlay_result})

    comparison_results: dict[str, pd.DataFrame] = {
        name: overlay_result,
    }

    for benchmark in overlay_config.get("benchmarks", []):
        ticker = str(benchmark["ticker"]).upper()
        strategy = str(benchmark["strategy"])
        benchmark_name = f"{ticker} {strategy}"

        benchmark_result = _get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=ticker,
            strategy=strategy,
        )

        comparison_results[benchmark_name] = rebase_strategy_result_to_dates(
            result=benchmark_result,
            dates=common_dates,
            initial_capital=float(config["initial_capital"]),
        )

    for allocator_name in overlay_config.get("comparison_allocators", []):
        allocator_name = str(allocator_name)

        if allocator_name not in relative_momentum_outputs:
            continue

        comparison_results[allocator_name] = rebase_strategy_result_to_dates(
            result=relative_momentum_outputs[allocator_name]["allocator_result"],
            dates=common_dates,
            initial_capital=float(config["initial_capital"]),
        )

    metrics = pd.DataFrame(
        [
            calculate_metrics(result, strategy_name)
            for strategy_name, result in comparison_results.items()
        ]
    )

    rolling_metrics = calculate_rolling_window_metrics(comparison_results)
    rolling_summary = create_rolling_summary(rolling_metrics)
    mode_summary = _create_mode_summary(overlay_result)

    safe_name = _safe_filename(name)

    result_path = reports_dir / f"regime_switch_{safe_name}_daily_result.csv"
    metrics_path = reports_dir / f"regime_switch_{safe_name}_metrics.csv"
    rolling_summary_path = reports_dir / f"regime_switch_{safe_name}_rolling_summary.csv"
    mode_summary_path = reports_dir / f"regime_switch_{safe_name}_mode_summary.csv"
    markdown_path = reports_dir / f"regime_switch_{safe_name}.md"
    equity_plot_path = reports_dir / f"regime_switch_{safe_name}_equity_curves.png"
    drawdown_plot_path = reports_dir / f"regime_switch_{safe_name}_drawdowns.png"

    overlay_result.to_csv(result_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    rolling_summary.to_csv(rolling_summary_path, index=False)
    mode_summary.to_csv(mode_summary_path, index=False)

    plot_equity_curves(comparison_results, equity_plot_path)
    plot_drawdowns(comparison_results, drawdown_plot_path)

    _write_regime_switch_overlay_markdown(
        name=name,
        metrics=metrics,
        rolling_summary=rolling_summary,
        mode_summary=mode_summary,
        output_path=markdown_path,
        equity_plot_path=equity_plot_path,
        drawdown_plot_path=drawdown_plot_path,
    )

    print("\nRegime switch overlay comparison:")
    print(metrics.to_string(index=False))

    print("\nRegime switch overlay rolling summary:")
    print(rolling_summary.to_string(index=False))

    print("\nRegime switch overlay mode summary:")
    print(mode_summary.to_string(index=False))

    print(f"\nSaved regime switch overlay daily result to: {result_path}")
    print(f"Saved regime switch overlay metrics to: {metrics_path}")
    print(f"Saved regime switch overlay rolling summary to: {rolling_summary_path}")
    print(f"Saved regime switch overlay mode summary to: {mode_summary_path}")
    print(f"Saved regime switch overlay report to: {markdown_path}")
    print(f"Saved regime switch overlay equity chart to: {equity_plot_path}")
    print(f"Saved regime switch overlay drawdown chart to: {drawdown_plot_path}")

    return {
        "overlay_result": overlay_result,
        "metrics": metrics,
        "rolling_summary": rolling_summary,
        "mode_summary": mode_summary,
    }