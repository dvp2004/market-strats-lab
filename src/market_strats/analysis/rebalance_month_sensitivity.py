from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.annual_rebalance_audit import (
    create_annual_rebalance_audit,
    create_annual_rebalance_audit_summary,
)
from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.rolling import (
    calculate_rolling_window_metrics,
    create_rolling_summary,
)
from market_strats.strategies.core_satellite import (
    run_annual_rebalanced_core_satellite_strategy,
)


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


def run_rebalance_month_sensitivity(
    core_result: pd.DataFrame,
    satellite_result: pd.DataFrame,
    initial_capital: float,
    core_weight: float,
    satellite_weight: float,
    slippage_bps: float,
    rebalance_months: list[int],
) -> pd.DataFrame:
    """
    Test whether annual core-satellite results are sensitive to the rebalance month.

    This is a robustness test, not an optimisation sweep.
    The purpose is to check whether December year-end rebalancing was unusually lucky.
    """
    rows: list[dict] = []

    for rebalance_month in rebalance_months:
        strategy_name = (
            f"{int(core_weight * 100)}/{int(satellite_weight * 100)} "
            f"Annual Rebalanced M{rebalance_month:02d} Core-Satellite "
            "SPY B&H + 12M Momentum"
        )

        result = run_annual_rebalanced_core_satellite_strategy(
            core_result=core_result,
            satellite_result=satellite_result,
            initial_capital=initial_capital,
            core_weight=core_weight,
            satellite_weight=satellite_weight,
            strategy_name=strategy_name,
            slippage_bps=slippage_bps,
            rebalance_month=rebalance_month,
        )

        metrics = calculate_metrics(result, strategy_name)

        rolling_metrics = calculate_rolling_window_metrics({strategy_name: result})
        rolling_summary = create_rolling_summary(rolling_metrics)

        audit = create_annual_rebalance_audit(
            result=result,
            strategy_name=strategy_name,
        )
        audit_summary = create_annual_rebalance_audit_summary(audit)

        if audit_summary.empty:
            rebalance_count = 0
            avg_rebalance_turnover_pct = float("nan")
            max_rebalance_turnover_pct = float("nan")
            avg_drawdown_at_rebalance_pct = float("nan")
            worst_drawdown_at_rebalance_pct = float("nan")
            avg_next_12m_return_pct = float("nan")
            positive_next_12m_pct = float("nan")
        else:
            summary_row = audit_summary.iloc[0]
            rebalance_count = int(summary_row["rebalance_count"])
            avg_rebalance_turnover_pct = float(
                summary_row["avg_rebalance_turnover_pct"]
            )
            max_rebalance_turnover_pct = float(
                summary_row["max_rebalance_turnover_pct"]
            )
            avg_drawdown_at_rebalance_pct = float(
                summary_row["avg_drawdown_at_rebalance_pct"]
            )
            worst_drawdown_at_rebalance_pct = float(
                summary_row["worst_drawdown_at_rebalance_pct"]
            )
            avg_next_12m_return_pct = float(summary_row["avg_next_12m_return_pct"])
            positive_next_12m_pct = float(summary_row["positive_next_12m_pct"])

        rows.append(
            {
                "rebalance_month": rebalance_month,
                "strategy": strategy_name,
                "end_value": metrics["end_value"],
                "cagr_pct": metrics["cagr_pct"],
                "volatility_pct": metrics["volatility_pct"],
                "sharpe": metrics["sharpe"],
                "sortino": metrics["sortino"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "exposure_time_pct": metrics["exposure_time_pct"],
                "trade_count": metrics["trade_count"],
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
                "rebalance_count": rebalance_count,
                "avg_rebalance_turnover_pct": avg_rebalance_turnover_pct,
                "max_rebalance_turnover_pct": max_rebalance_turnover_pct,
                "avg_drawdown_at_rebalance_pct": avg_drawdown_at_rebalance_pct,
                "worst_drawdown_at_rebalance_pct": worst_drawdown_at_rebalance_pct,
                "avg_next_12m_return_pct": avg_next_12m_return_pct,
                "positive_next_12m_pct": positive_next_12m_pct,
            }
        )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(2)

    return output.sort_values("rebalance_month").reset_index(drop=True)


def write_rebalance_month_sensitivity_markdown(
    sensitivity: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if sensitivity.empty:
        output_path.write_text(
            "# Rebalance-Month Sensitivity\n\nNo data available.\n",
            encoding="utf-8",
        )
        return output_path

    display_columns = [
        "rebalance_month",
        "end_value",
        "cagr_pct",
        "max_drawdown_pct",
        "worst_3y_cagr_pct",
        "worst_5y_cagr_pct",
        "trade_count",
        "rebalance_count",
        "avg_rebalance_turnover_pct",
        "max_rebalance_turnover_pct",
        "avg_drawdown_at_rebalance_pct",
        "worst_drawdown_at_rebalance_pct",
        "avg_next_12m_return_pct",
        "positive_next_12m_pct",
    ]

    available_columns = [
        column for column in display_columns if column in sensitivity.columns
    ]

    markdown_table = sensitivity[available_columns].to_markdown(index=False)

    best_end_value = sensitivity.sort_values("end_value", ascending=False).iloc[0]
    best_drawdown = sensitivity.sort_values("max_drawdown_pct", ascending=False).iloc[0]

    content = f"""# Annual Core-Satellite Rebalance-Month Sensitivity

This report tests whether the annual rebalanced 60/40 core-satellite result is sensitive to the chosen rebalance month.

This is a robustness check, not an optimisation exercise.

## Sensitivity Table

{markdown_table}

## Key Checks

- Best terminal wealth month: {int(best_end_value["rebalance_month"])}
- Best max drawdown month: {int(best_drawdown["rebalance_month"])}

## Interpretation Notes

- If December is uniquely strong, the original annual-rebalanced result may be calendar-sensitive.
- If March, June, September, and December are broadly similar, the annual-rebalanced architecture is more robust.
- This test should not be used to choose the best month unless a first-principles reason exists.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path