from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.rolling import (
    calculate_rolling_window_metrics,
    create_rolling_summary,
)
from market_strats.strategies.absolute_momentum import run_absolute_momentum_strategy


def run_momentum_window_robustness(
    prices: pd.DataFrame,
    initial_capital: float,
    lookback_months: list[int],
    slippage_bps: float,
    cash_returns: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    Run absolute momentum strategy across multiple lookback windows.

    This is a robustness check, not an optimisation routine.
    The goal is to see whether performance forms a stable plateau around
    the selected lookback, not to cherry-pick the best-performing value.
    """
    if not lookback_months:
        raise ValueError("lookback_months cannot be empty")

    if any(month <= 0 for month in lookback_months):
        raise ValueError("All lookback windows must be positive integers")

    sorted_lookbacks = sorted(set(int(month) for month in lookback_months))

    results: dict[str, pd.DataFrame] = {}
    metric_rows: list[dict] = []

    for lookback in sorted_lookbacks:
        strategy_name = f"{lookback}-Month Absolute Momentum"

        result = run_absolute_momentum_strategy(
            prices=prices,
            initial_capital=initial_capital,
            momentum_months=lookback,
            slippage_bps=slippage_bps,
            cash_returns=cash_returns,
        )

        results[strategy_name] = result

        metrics = calculate_metrics(result, strategy_name)
        metrics["lookback_months"] = lookback
        metric_rows.append(metrics)

    full_metrics = pd.DataFrame(metric_rows)

    rolling_metrics = calculate_rolling_window_metrics(results)
    rolling_summary = create_rolling_summary(rolling_metrics)

    enriched = enrich_momentum_robustness_metrics(full_metrics, rolling_summary)

    return enriched, rolling_summary, results


def _get_rolling_value(
    rolling_summary: pd.DataFrame,
    strategy: str,
    window_years: int,
    column: str,
) -> float:
    row = rolling_summary[
        (rolling_summary["strategy"] == strategy)
        & (rolling_summary["window_years"] == window_years)
    ]

    if row.empty:
        return float("nan")

    return float(row[column].iloc[0])


def enrich_momentum_robustness_metrics(
    full_metrics: pd.DataFrame,
    rolling_summary: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add rolling-window summary fields to the robustness table.
    """
    df = full_metrics.copy()

    df["rolling_3y_avg_cagr_pct"] = df["strategy"].apply(
        lambda strategy: _get_rolling_value(
            rolling_summary,
            strategy,
            3,
            "avg_cagr_pct",
        )
    )
    df["rolling_3y_worst_cagr_pct"] = df["strategy"].apply(
        lambda strategy: _get_rolling_value(
            rolling_summary,
            strategy,
            3,
            "worst_cagr_pct",
        )
    )
    df["rolling_3y_avg_max_drawdown_pct"] = df["strategy"].apply(
        lambda strategy: _get_rolling_value(
            rolling_summary,
            strategy,
            3,
            "avg_max_drawdown_pct",
        )
    )
    df["rolling_3y_positive_windows_pct"] = df["strategy"].apply(
        lambda strategy: _get_rolling_value(
            rolling_summary,
            strategy,
            3,
            "positive_windows_pct",
        )
    )

    df["rolling_5y_avg_cagr_pct"] = df["strategy"].apply(
        lambda strategy: _get_rolling_value(
            rolling_summary,
            strategy,
            5,
            "avg_cagr_pct",
        )
    )
    df["rolling_5y_worst_cagr_pct"] = df["strategy"].apply(
        lambda strategy: _get_rolling_value(
            rolling_summary,
            strategy,
            5,
            "worst_cagr_pct",
        )
    )
    df["rolling_5y_avg_max_drawdown_pct"] = df["strategy"].apply(
        lambda strategy: _get_rolling_value(
            rolling_summary,
            strategy,
            5,
            "avg_max_drawdown_pct",
        )
    )
    df["rolling_5y_positive_windows_pct"] = df["strategy"].apply(
        lambda strategy: _get_rolling_value(
            rolling_summary,
            strategy,
            5,
            "positive_windows_pct",
        )
    )

    ordered_columns = [
        "lookback_months",
        "strategy",
        "end_value",
        "total_return_pct",
        "cagr_pct",
        "volatility_pct",
        "sharpe",
        "sortino",
        "max_drawdown_pct",
        "exposure_time_pct",
        "trade_count",
        "rolling_3y_avg_cagr_pct",
        "rolling_3y_worst_cagr_pct",
        "rolling_3y_avg_max_drawdown_pct",
        "rolling_3y_positive_windows_pct",
        "rolling_5y_avg_cagr_pct",
        "rolling_5y_worst_cagr_pct",
        "rolling_5y_avg_max_drawdown_pct",
        "rolling_5y_positive_windows_pct",
    ]

    available_columns = [column for column in ordered_columns if column in df.columns]

    return df[available_columns].sort_values("lookback_months").reset_index(drop=True)


def classify_parameter_shape(robustness_metrics: pd.DataFrame) -> str:
    """
    Give a simple qualitative classification of the parameter surface.

    This does not replace judgement. It is a guardrail against blindly picking
    the highest-performing lookback.
    """
    df = robustness_metrics.copy()

    if df.empty:
        return "No robustness metrics available."

    if 12 not in set(df["lookback_months"]):
        return "12-month lookback was not included, so the current baseline cannot be assessed."

    baseline = df[df["lookback_months"] == 12].iloc[0]

    nearby = df[df["lookback_months"].isin([9, 10, 11, 12, 13])].copy()

    if len(nearby) < 3:
        return "Too few nearby lookbacks to judge whether a parameter plateau exists."

    nearby_min_cagr = float(nearby["cagr_pct"].min())
    nearby_max_cagr = float(nearby["cagr_pct"].max())
    nearby_cagr_spread = nearby_max_cagr - nearby_min_cagr

    nearby_worst_drawdown = float(nearby["max_drawdown_pct"].min())
    baseline_drawdown = float(baseline["max_drawdown_pct"])

    if nearby_cagr_spread <= 1.0 and nearby_worst_drawdown >= baseline_drawdown - 7.5:
        return (
            "Looks like a reasonable plateau around the 9-13 month region. "
            "Do not cherry-pick the best lookback; treat the cluster as broadly similar."
        )

    if nearby_cagr_spread <= 2.0:
        return (
            "Some variation exists, but the nearby lookbacks do not collapse. "
            "The 12-month result is not obviously a single-point spike."
        )

    return (
        "Potential fragility warning: nearby lookbacks vary materially. "
        "Inspect whether 12 months is a peak rather than part of a stable plateau."
    )


def write_momentum_robustness_markdown(
    robustness_metrics: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """
    Write a human-readable markdown robustness report.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    classification = classify_parameter_shape(robustness_metrics)

    display_columns = [
        "lookback_months",
        "end_value",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "sortino",
        "trade_count",
        "rolling_3y_worst_cagr_pct",
        "rolling_5y_worst_cagr_pct",
        "rolling_3y_avg_max_drawdown_pct",
        "rolling_5y_avg_max_drawdown_pct",
    ]

    available_columns = [
        column for column in display_columns if column in robustness_metrics.columns
    ]

    markdown_table = robustness_metrics[available_columns].to_markdown(index=False)

    content = f"""# Momentum Window Robustness Report

This report tests absolute momentum across multiple lookback windows.

The goal is not to select the best-performing lookback. The goal is to check whether the current 12-month momentum result sits inside a reasonably stable parameter plateau.

## Parameter Surface Assessment

{classification}

## Robustness Table

{markdown_table}

## Interpretation Rules

- A broad plateau is good.
- A single sharp peak is fragile.
- Shorter windows may trade more and suffer whipsaw.
- Longer windows may react too slowly and lag major turns.
- Do not treat the best row as the new strategy without out-of-sample justification.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path