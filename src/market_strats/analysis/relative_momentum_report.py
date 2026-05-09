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
from market_strats.strategies.relative_momentum_allocator import (
    run_relative_momentum_allocator,
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


def _get_price_data_from_buy_and_hold(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
) -> pd.DataFrame:
    return _get_strategy_result(
        ticker_outputs=ticker_outputs,
        ticker=ticker,
        strategy="Buy and Hold",
    )[["date", "adj_close"]].copy()


def _create_allocation_summary(
    allocator_result: pd.DataFrame,
    universe: list[str],
) -> pd.DataFrame:
    rows = []

    for ticker in universe:
        weight_column = f"{ticker}_weight"

        if weight_column not in allocator_result.columns:
            continue

        weights = allocator_result[weight_column].astype(float)

        rows.append(
            {
                "asset": ticker,
                "avg_weight_pct": weights.mean() * 100.0,
                "max_weight_pct": weights.max() * 100.0,
                "days_held": int((weights > 0.000001).sum()),
                "pct_days_held": (weights > 0.000001).mean() * 100.0,
                "final_weight_pct": weights.iloc[-1] * 100.0,
            }
        )

    summary = pd.DataFrame(rows)

    if summary.empty:
        return summary

    numeric_columns = summary.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        summary[column] = summary[column].round(3)

    return summary.sort_values("avg_weight_pct", ascending=False).reset_index(drop=True)


def _write_relative_momentum_markdown(
    name: str,
    universe: list[str],
    variant_config: dict,
    metrics: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    allocation_summary: pd.DataFrame,
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
    allocation_table = (
        allocation_summary.to_markdown(index=False)
        if not allocation_summary.empty
        else "No allocation summary available."
    )

    universe_text = ", ".join(universe)
    variant_table = pd.DataFrame([variant_config]).to_markdown(index=False)

    content = f"""# Relative Momentum Allocator: {name}

This report tests a Phase 2 tactical asset allocation model.

The allocator ranks broad asset classes by relative momentum and allocates to the strongest assets that also pass an absolute momentum filter.

## Universe

{universe_text}

## Variant Configuration

{variant_table}

## Rule

- Monthly decision frequency.
- Rank assets by trailing 12-month return.
- Keep only assets with positive momentum.
- Hold the top-N eligible assets.
- Weight selected assets according to the configured weighting method.
- If fewer than top-N assets qualify, unused capital remains in cash.
- Execute on the next trading day.
- Apply positions after execution.

## Full-Period Metrics

{metrics_table}

## Rolling-Window Summary

{rolling_table}

## Allocation Summary

{allocation_table}

## Charts

![Relative Momentum Equity Curves]({Path(equity_plot_path).as_posix()})

![Relative Momentum Drawdowns]({Path(drawdown_plot_path).as_posix()})

## Interpretation Notes

- This is still a tactical allocation baseline, not a machine-learning model.
- Equal-weight selection tests whether relative momentum alone helps.
- Inverse-volatility selection tests whether risk-aware sizing improves the allocator.
- BTC is deliberately excluded from this first tactical allocator branch.
- If risk-aware sizing does not improve the baseline, adding sentiment or macro features should not be assumed to fix it.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def _normalise_variants(allocator_config: dict) -> list[dict]:
    variants = allocator_config.get("variants")

    if variants:
        return [dict(variant) for variant in variants]

    return [
        {
            "name": allocator_config["name"],
            "lookback_months": allocator_config.get("lookback_months", 12),
            "top_n": allocator_config.get("top_n", 3),
            "min_momentum": allocator_config.get("min_momentum", 0.0),
            "weighting": allocator_config.get("weighting", "equal"),
            "volatility_lookback_days": allocator_config.get(
                "volatility_lookback_days",
                63,
            ),
        }
    ]


def _run_single_relative_momentum_variant(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: Path,
    allocator_config: dict,
    variant_config: dict,
) -> dict[str, pd.DataFrame]:
    name = str(variant_config["name"])
    universe = [str(ticker).upper() for ticker in allocator_config["universe"]]

    price_data_by_ticker = {
        ticker: _get_price_data_from_buy_and_hold(ticker_outputs, ticker)
        for ticker in universe
    }

    benchmark_ticker = "SPY"
    cash_returns = ticker_outputs.get(benchmark_ticker, {}).get("cash_returns")

    allocator_result = run_relative_momentum_allocator(
        price_data_by_ticker=price_data_by_ticker,
        initial_capital=float(config["initial_capital"]),
        lookback_months=int(variant_config.get("lookback_months", 12)),
        top_n=int(variant_config.get("top_n", 3)),
        min_momentum=float(variant_config.get("min_momentum", 0.0)),
        slippage_bps=float(config.get("slippage_bps", 0.0)),
        cash_returns=cash_returns,
        weighting=str(variant_config.get("weighting", "equal")),
        volatility_lookback_days=int(
            variant_config.get("volatility_lookback_days", 63)
        ),
    )

    common_dates = get_common_strategy_dates(
        {
            name: allocator_result,
        }
    )

    comparison_results: dict[str, pd.DataFrame] = {
        name: allocator_result,
    }

    for benchmark in allocator_config.get("benchmarks", []):
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

    metrics = pd.DataFrame(
        [
            calculate_metrics(result, strategy_name)
            for strategy_name, result in comparison_results.items()
        ]
    )

    rolling_metrics = calculate_rolling_window_metrics(comparison_results)
    rolling_summary = create_rolling_summary(rolling_metrics)

    allocation_summary = _create_allocation_summary(
        allocator_result=allocator_result,
        universe=universe,
    )

    safe_name = _safe_filename(name)

    result_path = reports_dir / f"relative_momentum_{safe_name}_daily_result.csv"
    metrics_path = reports_dir / f"relative_momentum_{safe_name}_metrics.csv"
    rolling_summary_path = (
        reports_dir / f"relative_momentum_{safe_name}_rolling_summary.csv"
    )
    allocation_summary_path = (
        reports_dir / f"relative_momentum_{safe_name}_allocation_summary.csv"
    )
    markdown_path = reports_dir / f"relative_momentum_{safe_name}.md"
    equity_plot_path = reports_dir / f"relative_momentum_{safe_name}_equity_curves.png"
    drawdown_plot_path = reports_dir / f"relative_momentum_{safe_name}_drawdowns.png"

    allocator_result.to_csv(result_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    rolling_summary.to_csv(rolling_summary_path, index=False)
    allocation_summary.to_csv(allocation_summary_path, index=False)

    plot_equity_curves(comparison_results, equity_plot_path)
    plot_drawdowns(comparison_results, drawdown_plot_path)

    _write_relative_momentum_markdown(
        name=name,
        universe=universe,
        variant_config=variant_config,
        metrics=metrics,
        rolling_summary=rolling_summary,
        allocation_summary=allocation_summary,
        output_path=markdown_path,
        equity_plot_path=equity_plot_path,
        drawdown_plot_path=drawdown_plot_path,
    )

    print(f"\nRelative momentum allocator comparison: {name}")
    print(metrics.to_string(index=False))

    print(f"\nRelative momentum allocator rolling summary: {name}")
    print(rolling_summary.to_string(index=False))

    print(f"\nRelative momentum allocator allocation summary: {name}")
    print(allocation_summary.to_string(index=False))

    print(f"\nSaved relative momentum allocator daily result to: {result_path}")
    print(f"Saved relative momentum allocator metrics to: {metrics_path}")
    print(f"Saved relative momentum allocator rolling summary to: {rolling_summary_path}")
    print(
        "Saved relative momentum allocator allocation summary to: "
        f"{allocation_summary_path}"
    )
    print(f"Saved relative momentum allocator report to: {markdown_path}")
    print(f"Saved relative momentum allocator equity chart to: {equity_plot_path}")
    print(f"Saved relative momentum allocator drawdown chart to: {drawdown_plot_path}")

    return {
        "allocator_result": allocator_result,
        "metrics": metrics,
        "rolling_summary": rolling_summary,
        "allocation_summary": allocation_summary,
    }


def run_relative_momentum_allocator_report(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, dict[str, pd.DataFrame]]:
    allocator_config = config.get("relative_momentum_allocator", {})

    if not allocator_config.get("enabled", False):
        return {}

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, dict[str, pd.DataFrame]] = {}

    for variant_config in _normalise_variants(allocator_config):
        name = str(variant_config["name"])

        outputs[name] = _run_single_relative_momentum_variant(
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
            allocator_config=allocator_config,
            variant_config=variant_config,
        )

    return outputs