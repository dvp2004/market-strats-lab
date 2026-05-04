from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def minmax_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """
    Convert a numeric series to a 0-100 score.

    If all values are equal, every strategy gets 50.
    """
    values = pd.to_numeric(series, errors="coerce")
    min_value = values.min()
    max_value = values.max()

    if pd.isna(min_value) or pd.isna(max_value):
        return pd.Series(50.0, index=series.index)

    if np.isclose(max_value, min_value):
        return pd.Series(50.0, index=series.index)

    score = ((values - min_value) / (max_value - min_value)) * 100.0

    if not higher_is_better:
        score = 100.0 - score

    return score.round(2)


def get_rolling_value(
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
        return np.nan

    return float(row[column].iloc[0])


def create_strategy_scorecard(
    full_period_metrics: pd.DataFrame,
    rolling_summary: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create a strategy-level comparison scorecard.

    This combines full-period metrics with rolling-window metrics.

    The scorecard is a decision-support tool, not a statistical proof.
    Scores are deliberately simple and transparent.
    """
    scorecard = full_period_metrics.copy()

    scorecard["rolling_3y_avg_cagr_pct"] = scorecard["strategy"].apply(
        lambda strategy: get_rolling_value(
            rolling_summary,
            strategy,
            3,
            "avg_cagr_pct",
        )
    )
    scorecard["rolling_3y_worst_cagr_pct"] = scorecard["strategy"].apply(
        lambda strategy: get_rolling_value(
            rolling_summary,
            strategy,
            3,
            "worst_cagr_pct",
        )
    )
    scorecard["rolling_3y_avg_max_drawdown_pct"] = scorecard["strategy"].apply(
        lambda strategy: get_rolling_value(
            rolling_summary,
            strategy,
            3,
            "avg_max_drawdown_pct",
        )
    )
    scorecard["rolling_3y_positive_windows_pct"] = scorecard["strategy"].apply(
        lambda strategy: get_rolling_value(
            rolling_summary,
            strategy,
            3,
            "positive_windows_pct",
        )
    )

    scorecard["rolling_5y_avg_cagr_pct"] = scorecard["strategy"].apply(
        lambda strategy: get_rolling_value(
            rolling_summary,
            strategy,
            5,
            "avg_cagr_pct",
        )
    )
    scorecard["rolling_5y_worst_cagr_pct"] = scorecard["strategy"].apply(
        lambda strategy: get_rolling_value(
            rolling_summary,
            strategy,
            5,
            "worst_cagr_pct",
        )
    )
    scorecard["rolling_5y_avg_max_drawdown_pct"] = scorecard["strategy"].apply(
        lambda strategy: get_rolling_value(
            rolling_summary,
            strategy,
            5,
            "avg_max_drawdown_pct",
        )
    )
    scorecard["rolling_5y_positive_windows_pct"] = scorecard["strategy"].apply(
        lambda strategy: get_rolling_value(
            rolling_summary,
            strategy,
            5,
            "positive_windows_pct",
        )
    )

    # Full-period scores.
    scorecard["cagr_score"] = minmax_score(scorecard["cagr_pct"], higher_is_better=True)
    scorecard["sharpe_score"] = minmax_score(scorecard["sharpe"], higher_is_better=True)
    scorecard["drawdown_score"] = minmax_score(
        scorecard["max_drawdown_pct"],
        higher_is_better=True,
    )

    # Rolling consistency scores.
    scorecard["rolling_return_score"] = (
        minmax_score(scorecard["rolling_3y_avg_cagr_pct"], higher_is_better=True)
        + minmax_score(scorecard["rolling_5y_avg_cagr_pct"], higher_is_better=True)
    ) / 2.0

    scorecard["rolling_bad_period_score"] = (
        minmax_score(scorecard["rolling_3y_worst_cagr_pct"], higher_is_better=True)
        + minmax_score(scorecard["rolling_5y_worst_cagr_pct"], higher_is_better=True)
    ) / 2.0

    scorecard["rolling_drawdown_score"] = (
        minmax_score(scorecard["rolling_3y_avg_max_drawdown_pct"], higher_is_better=True)
        + minmax_score(scorecard["rolling_5y_avg_max_drawdown_pct"], higher_is_better=True)
    ) / 2.0

    scorecard["positive_window_score"] = (
        minmax_score(scorecard["rolling_3y_positive_windows_pct"], higher_is_better=True)
        + minmax_score(scorecard["rolling_5y_positive_windows_pct"], higher_is_better=True)
    ) / 2.0

    # Lower trade count is better, but we do not want to over-reward buy-and-hold blindly.
    scorecard["trade_efficiency_score"] = minmax_score(
        scorecard["trade_count"],
        higher_is_better=False,
    )

    # Composite score weights.
    # These are judgement calls, not laws.
    scorecard["composite_score"] = (
        0.25 * scorecard["cagr_score"]
        + 0.15 * scorecard["sharpe_score"]
        + 0.15 * scorecard["drawdown_score"]
        + 0.15 * scorecard["rolling_return_score"]
        + 0.15 * scorecard["rolling_bad_period_score"]
        + 0.10 * scorecard["rolling_drawdown_score"]
        + 0.05 * scorecard["trade_efficiency_score"]
    ).round(2)

    scorecard["composite_rank"] = scorecard["composite_score"].rank(
        ascending=False,
        method="min",
    ).astype(int)

    scorecard["cagr_rank"] = scorecard["cagr_pct"].rank(
        ascending=False,
        method="min",
    ).astype(int)

    scorecard["max_drawdown_rank"] = scorecard["max_drawdown_pct"].rank(
        ascending=False,
        method="min",
    ).astype(int)

    scorecard["sharpe_rank"] = scorecard["sharpe"].rank(
        ascending=False,
        method="min",
    ).astype(int)

    scorecard["trade_count_rank"] = scorecard["trade_count"].rank(
        ascending=True,
        method="min",
    ).astype(int)

    scorecard = scorecard.sort_values(
        ["composite_rank", "strategy"],
        ascending=[True, True],
    ).reset_index(drop=True)

    return scorecard


def create_strategy_verdicts(scorecard: pd.DataFrame) -> pd.DataFrame:
    """
    Add plain-English verdicts based on observable strategy behaviour.
    """
    verdicts = scorecard.copy()

    def verdict(row: pd.Series) -> str:
        strategy = str(row["strategy"])

        if strategy == "Buy and Hold":
            return "Best raw compounding benchmark, but worst drawdown pain."

        if "12-Month Absolute Momentum" in strategy:
            return "Best overall active candidate so far: strong return, lower drawdown, low turnover."

        if "10-Month SMA" in strategy:
            return "Useful defensive trend benchmark, but gives up too much upside."

        if "200-Day SMA" in strategy:
            return "Strong drawdown control, but noisy and trade-heavy."

        if strategy == "Drawdown Tranche":
            return "Weak: cash drag plus poor bear-market protection."

        if strategy == "Trend-Filtered Drawdown":
            return "Improves crash protection, but too under-invested to compound well."

        return "Needs manual review."

    verdicts["verdict"] = verdicts.apply(verdict, axis=1)

    return verdicts


def write_scorecard_markdown(
    scorecard: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """
    Write a human-readable markdown strategy comparison report.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    display_columns = [
        "composite_rank",
        "strategy",
        "composite_score",
        "end_value",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "trade_count",
        "rolling_3y_worst_cagr_pct",
        "rolling_5y_worst_cagr_pct",
        "rolling_3y_avg_max_drawdown_pct",
        "rolling_5y_avg_max_drawdown_pct",
        "verdict",
    ]

    existing_columns = [col for col in display_columns if col in scorecard.columns]
    markdown_table = scorecard[existing_columns].to_markdown(index=False)

    best_strategy = scorecard.sort_values("composite_rank").iloc[0]["strategy"]

    content = f"""# Strategy Comparison Scorecard

This report ranks strategies using full-period performance and rolling-window behaviour.

The composite score is a decision-support tool, not statistical proof. It is intended to make comparisons easier and expose trade-offs more clearly.

## Current Top-Ranked Strategy

**{best_strategy}**

## Scorecard

{markdown_table}

## Scoring Notes

Composite score weights:

- 25% full-period CAGR
- 15% full-period Sharpe
- 15% full-period max drawdown
- 15% rolling average CAGR
- 15% rolling worst CAGR
- 10% rolling average max drawdown
- 5% trade efficiency

These weights are deliberately simple. They should not be treated as permanent truth.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path