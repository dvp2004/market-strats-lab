from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.strategies.fixed_weight_portfolio import (
    rebase_strategy_result_to_dates,
)


def create_candidate_portfolio_sleeve_attribution(
    component_results: dict[str, pd.DataFrame],
    weights: dict[str, float],
    portfolio_result: pd.DataFrame,
    common_dates: list[pd.Timestamp],
    initial_capital: float,
) -> pd.DataFrame:
    """
    Attribute independent-sleeve portfolio results back to each component.

    Each component is rebased over the same common date range. The component's
    growth multiple is then applied to its starting sleeve allocation.

    This explains which sleeves contributed to terminal wealth, which sleeves
    dragged returns, and how far weights drifted without rebalancing.
    """
    if not component_results:
        return pd.DataFrame()

    if set(component_results) != set(weights):
        raise ValueError("component_results keys must match weights keys")

    if portfolio_result.empty:
        raise ValueError("portfolio_result cannot be empty")

    portfolio_end_value = float(portfolio_result["equity"].iloc[-1])

    rows: list[dict] = []

    for component_name, result in component_results.items():
        target_weight = float(weights[component_name])
        starting_sleeve_value = initial_capital * target_weight

        rebased_result = rebase_strategy_result_to_dates(
            result=result,
            dates=common_dates,
            initial_capital=initial_capital,
        )

        component_metrics = calculate_metrics(rebased_result, component_name)

        component_end_value_if_full_size = float(rebased_result["equity"].iloc[-1])
        component_growth_multiple = component_end_value_if_full_size / initial_capital

        ending_sleeve_value = starting_sleeve_value * component_growth_multiple
        final_weight = ending_sleeve_value / portfolio_end_value

        sleeve_profit = ending_sleeve_value - starting_sleeve_value
        contribution_to_portfolio_return_pct_points = (
            sleeve_profit / initial_capital
        ) * 100.0

        rows.append(
            {
                "component": component_name,
                "target_weight_pct": target_weight * 100.0,
                "final_weight_pct": final_weight * 100.0,
                "weight_drift_pct_points": (final_weight - target_weight) * 100.0,
                "starting_sleeve_value": starting_sleeve_value,
                "ending_sleeve_value": ending_sleeve_value,
                "sleeve_profit": sleeve_profit,
                "contribution_to_portfolio_return_pct_points": (
                    contribution_to_portfolio_return_pct_points
                ),
                "component_growth_multiple": component_growth_multiple,
                "component_cagr_pct": component_metrics["cagr_pct"],
                "component_max_drawdown_pct": component_metrics["max_drawdown_pct"],
                "component_volatility_pct": component_metrics["volatility_pct"],
                "component_sharpe": component_metrics["sharpe"],
                "component_sortino": component_metrics["sortino"],
                "component_exposure_time_pct": component_metrics["exposure_time_pct"],
                "component_trade_count": component_metrics["trade_count"],
            }
        )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(2)

    return output.sort_values(
        "contribution_to_portfolio_return_pct_points",
        ascending=False,
    ).reset_index(drop=True)


def create_candidate_portfolio_sleeve_summary(
    attribution: pd.DataFrame,
    portfolio_result: pd.DataFrame,
    initial_capital: float,
) -> pd.DataFrame:
    if attribution.empty:
        return pd.DataFrame()

    portfolio_end_value = float(portfolio_result["equity"].iloc[-1])
    portfolio_total_return_pct = ((portfolio_end_value / initial_capital) - 1.0) * 100.0

    top_contributor = attribution.sort_values(
        "contribution_to_portfolio_return_pct_points",
        ascending=False,
    ).iloc[0]
    weakest_contributor = attribution.sort_values(
        "contribution_to_portfolio_return_pct_points",
        ascending=True,
    ).iloc[0]
    largest_overweight = attribution.sort_values(
        "weight_drift_pct_points",
        ascending=False,
    ).iloc[0]
    largest_underweight = attribution.sort_values(
        "weight_drift_pct_points",
        ascending=True,
    ).iloc[0]

    return pd.DataFrame(
        [
            {
                "portfolio_end_value": round(portfolio_end_value, 2),
                "portfolio_total_return_pct": round(portfolio_total_return_pct, 2),
                "top_contributor": top_contributor["component"],
                "top_contribution_pct_points": top_contributor[
                    "contribution_to_portfolio_return_pct_points"
                ],
                "weakest_contributor": weakest_contributor["component"],
                "weakest_contribution_pct_points": weakest_contributor[
                    "contribution_to_portfolio_return_pct_points"
                ],
                "largest_overweight_component": largest_overweight["component"],
                "largest_overweight_drift_pct_points": largest_overweight[
                    "weight_drift_pct_points"
                ],
                "largest_underweight_component": largest_underweight["component"],
                "largest_underweight_drift_pct_points": largest_underweight[
                    "weight_drift_pct_points"
                ],
                "absolute_weight_drift_pct_points": round(
                    float(attribution["weight_drift_pct_points"].abs().sum()),
                    2,
                ),
            }
        ]
    )


def write_candidate_portfolio_attribution_markdown(
    attribution: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if attribution.empty:
        output_path.write_text(
            "# Candidate Portfolio Sleeve Attribution\n\nNo attribution data available.\n",
            encoding="utf-8",
        )
        return output_path

    display_columns = [
        "component",
        "target_weight_pct",
        "final_weight_pct",
        "weight_drift_pct_points",
        "starting_sleeve_value",
        "ending_sleeve_value",
        "sleeve_profit",
        "contribution_to_portfolio_return_pct_points",
        "component_cagr_pct",
        "component_max_drawdown_pct",
        "component_sharpe",
        "component_exposure_time_pct",
        "component_trade_count",
    ]

    available_columns = [
        column for column in display_columns if column in attribution.columns
    ]

    attribution_table = attribution[available_columns].to_markdown(index=False)
    summary_table = (
        summary.to_markdown(index=False) if not summary.empty else "No summary data."
    )

    content = f"""# Candidate Portfolio Sleeve Attribution

This report explains which sleeves contributed to the candidate portfolio's return and how sleeve weights drifted without rebalancing.

## Summary

{summary_table}

## Sleeve Attribution

{attribution_table}

## Interpretation Notes

- Contribution is measured as sleeve profit divided by total initial portfolio capital.
- Final weight drift shows how independent sleeves moved away from their starting allocation.
- A low-return defensive sleeve can improve drawdown while still dragging terminal wealth.
- This report is diagnostic only. It should not be used to optimise weights directly.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path