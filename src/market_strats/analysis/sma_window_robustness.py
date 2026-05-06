from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.rolling import (
    calculate_rolling_window_metrics,
    create_rolling_summary,
)
from market_strats.strategies.daily_sma_trend import run_daily_sma_trend_strategy


def _get_rolling_value(
    rolling_summary: pd.DataFrame,
    strategy: str,
    window_years: int,
    column: str,
) -> float:
    if rolling_summary.empty:
        return float("nan")

    row = rolling_summary[
        (rolling_summary["strategy"] == strategy)
        & (rolling_summary["window_years"] == window_years)
    ]

    if row.empty:
        return float("nan")

    return float(row[column].iloc[0])


def _classify_sma_window(
    cagr_delta_vs_buy_hold: float,
    drawdown_improvement_vs_buy_hold: float,
) -> str:
    if cagr_delta_vs_buy_hold >= 0.20 and drawdown_improvement_vs_buy_hold >= 0:
        return "Return-enhancing"

    if cagr_delta_vs_buy_hold >= -0.25 and drawdown_improvement_vs_buy_hold >= 10:
        return "Wealth-equivalent risk reducer"

    if cagr_delta_vs_buy_hold >= -1.50 and drawdown_improvement_vs_buy_hold >= 10:
        return "Risk-control candidate"

    if drawdown_improvement_vs_buy_hold >= 10:
        return "Risk-control only"

    return "Weak / rejected"


def run_sma_window_robustness(
    ticker: str,
    prices: pd.DataFrame,
    buy_hold_result: pd.DataFrame,
    initial_capital: float,
    sma_days: list[int],
    slippage_bps: float,
    cash_returns: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Test whether a daily SMA result is robust across neighbouring windows.

    This is designed for the EFA 200D SMA lead. It is not intended to optimise
    the best SMA parameter. It checks whether the apparent edge exists across
    nearby windows.
    """
    if not sma_days:
        raise ValueError("sma_days cannot be empty")

    buy_hold_metrics = calculate_metrics(buy_hold_result, "Buy and Hold")
    buy_hold_cagr = float(buy_hold_metrics["cagr_pct"])
    buy_hold_max_drawdown = float(buy_hold_metrics["max_drawdown_pct"])

    rows: list[dict] = []

    for sma_day in sma_days:
        strategy_name = f"{sma_day}-Day SMA"

        result = run_daily_sma_trend_strategy(
            prices=prices,
            initial_capital=initial_capital,
            sma_days=sma_day,
            slippage_bps=slippage_bps,
            cash_returns=cash_returns,
        )

        metrics = calculate_metrics(result, strategy_name)
        rolling_metrics = calculate_rolling_window_metrics({strategy_name: result})
        rolling_summary = create_rolling_summary(rolling_metrics)

        cagr_delta = float(metrics["cagr_pct"]) - buy_hold_cagr
        drawdown_improvement = (
            float(metrics["max_drawdown_pct"]) - buy_hold_max_drawdown
        )

        rows.append(
            {
                "ticker": ticker,
                "sma_days": sma_day,
                "strategy": strategy_name,
                "start_date": metrics["start_date"],
                "end_date": metrics["end_date"],
                "end_value": metrics["end_value"],
                "cagr_pct": metrics["cagr_pct"],
                "buy_hold_cagr_pct": buy_hold_cagr,
                "cagr_delta_vs_buy_hold_pct_points": cagr_delta,
                "volatility_pct": metrics["volatility_pct"],
                "sharpe": metrics["sharpe"],
                "sortino": metrics["sortino"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "buy_hold_max_drawdown_pct": buy_hold_max_drawdown,
                "drawdown_improvement_vs_buy_hold_pct_points": drawdown_improvement,
                "exposure_time_pct": metrics["exposure_time_pct"],
                "trade_count": metrics["trade_count"],
                "total_turnover": metrics["total_turnover"],
                "worst_3y_cagr_pct": round(
                    _get_rolling_value(
                        rolling_summary,
                        strategy_name,
                        3,
                        "worst_cagr_pct",
                    ),
                    2,
                ),
                "worst_5y_cagr_pct": round(
                    _get_rolling_value(
                        rolling_summary,
                        strategy_name,
                        5,
                        "worst_cagr_pct",
                    ),
                    2,
                ),
                "classification": _classify_sma_window(
                    cagr_delta_vs_buy_hold=cagr_delta,
                    drawdown_improvement_vs_buy_hold=drawdown_improvement,
                ),
            }
        )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(2)

    return output.sort_values("sma_days").reset_index(drop=True)


def create_sma_window_robustness_summary(
    robustness: pd.DataFrame,
    anchor_sma_days: int = 200,
) -> pd.DataFrame:
    if robustness.empty:
        return pd.DataFrame()

    if anchor_sma_days not in set(robustness["sma_days"]):
        raise ValueError(f"anchor_sma_days={anchor_sma_days} not found in results")

    anchor = robustness[robustness["sma_days"] == anchor_sma_days].iloc[0]

    neighbouring = robustness[
        robustness["sma_days"].isin(
            [anchor_sma_days - 50, anchor_sma_days, anchor_sma_days + 50]
        )
    ].copy()

    return pd.DataFrame(
        [
            {
                "anchor_sma_days": anchor_sma_days,
                "anchor_cagr_pct": float(anchor["cagr_pct"]),
                "anchor_cagr_delta_vs_buy_hold_pct_points": float(
                    anchor["cagr_delta_vs_buy_hold_pct_points"]
                ),
                "anchor_max_drawdown_pct": float(anchor["max_drawdown_pct"]),
                "anchor_drawdown_improvement_vs_buy_hold_pct_points": float(
                    anchor["drawdown_improvement_vs_buy_hold_pct_points"]
                ),
                "neighbour_count": int(len(neighbouring)),
                "neighbour_avg_cagr_delta_vs_buy_hold_pct_points": round(
                    float(neighbouring["cagr_delta_vs_buy_hold_pct_points"].mean()),
                    2,
                ),
                "neighbour_min_cagr_delta_vs_buy_hold_pct_points": round(
                    float(neighbouring["cagr_delta_vs_buy_hold_pct_points"].min()),
                    2,
                ),
                "neighbour_avg_drawdown_improvement_pct_points": round(
                    float(
                        neighbouring[
                            "drawdown_improvement_vs_buy_hold_pct_points"
                        ].mean()
                    ),
                    2,
                ),
                "neighbour_min_drawdown_improvement_pct_points": round(
                    float(
                        neighbouring[
                            "drawdown_improvement_vs_buy_hold_pct_points"
                        ].min()
                    ),
                    2,
                ),
                "windows_with_positive_cagr_delta": int(
                    (robustness["cagr_delta_vs_buy_hold_pct_points"] > 0).sum()
                ),
                "windows_with_drawdown_improvement_gt_10pts": int(
                    (
                        robustness[
                            "drawdown_improvement_vs_buy_hold_pct_points"
                        ]
                        >= 10
                    ).sum()
                ),
            }
        ]
    )


def write_sma_window_robustness_markdown(
    robustness: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if robustness.empty:
        output_path.write_text(
            "# SMA Window Robustness\n\nNo data available.\n",
            encoding="utf-8",
        )
        return output_path

    display_columns = [
        "ticker",
        "sma_days",
        "cagr_pct",
        "buy_hold_cagr_pct",
        "cagr_delta_vs_buy_hold_pct_points",
        "max_drawdown_pct",
        "buy_hold_max_drawdown_pct",
        "drawdown_improvement_vs_buy_hold_pct_points",
        "worst_3y_cagr_pct",
        "worst_5y_cagr_pct",
        "exposure_time_pct",
        "trade_count",
        "classification",
    ]

    available_columns = [column for column in display_columns if column in robustness]

    robustness_table = robustness[available_columns].to_markdown(index=False)
    summary_table = (
        summary.to_markdown(index=False) if not summary.empty else "No summary data."
    )

    content = f"""# SMA Window Robustness

This report tests whether a daily SMA result is robust across neighbouring windows.

It is designed to validate whether an observed result is part of a stable region or a one-off parameter spike.

## Robustness Table

{robustness_table}

## Summary

{summary_table}

## Interpretation Rules

- A robust result should not depend on one exact SMA window.
- If neighbouring windows also improve CAGR and drawdown, the lead becomes more credible.
- If only one window works and nearby windows collapse, the result should be treated as likely parameter noise.
- This is a validation check, not an instruction to optimise to the best-performing window.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path