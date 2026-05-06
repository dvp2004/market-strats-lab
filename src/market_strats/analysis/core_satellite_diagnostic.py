from __future__ import annotations

from pathlib import Path

import pandas as pd


def _get_strategy_row(metrics: pd.DataFrame, strategy: str) -> pd.Series:
    row = metrics[metrics["strategy"] == strategy]

    if row.empty:
        raise ValueError(f"Missing strategy row: {strategy}")

    return row.iloc[0]


def _get_rolling_value(
    rolling_summary: pd.DataFrame,
    strategy: str,
    window_years: int,
    column: str,
) -> float:
    if rolling_summary.empty:
        return float("nan")

    required_columns = {"strategy", "window_years", column}

    if not required_columns.issubset(set(rolling_summary.columns)):
        return float("nan")

    row = rolling_summary[
        (rolling_summary["strategy"] == strategy)
        & (rolling_summary["window_years"] == window_years)
    ]

    if row.empty:
        return float("nan")

    return float(row[column].iloc[0])


def _build_verdict(
    strategy: str,
    cagr_delta_vs_buy_hold: float,
    max_dd_improvement_vs_buy_hold: float,
    cagr_delta_vs_momentum: float,
    max_dd_delta_vs_momentum: float,
) -> str:
    if strategy == "Buy and Hold":
        return "Raw compounding benchmark; strongest simplicity, worst drawdown."

    if strategy == "12-Month Absolute Momentum":
        return (
            "Current leader: buy-and-hold-like compounding with materially lower "
            "drawdown and simple rules."
        )
    
    if "Annual Rebalanced Core-Satellite" in strategy:
        if cagr_delta_vs_momentum >= -0.25 and max_dd_delta_vs_momentum >= -2.0:
            return (
                "Annual rebalance did not materially damage the full-momentum trade-off; "
                "compare directly against independent sleeves."
            )

        return (
            "Annual rebalance needs caution: may reintroduce averaging-down behaviour "
            "and should be compared against independent sleeves."
        )

    if "Core-Satellite" in strategy:
        if cagr_delta_vs_momentum >= -0.25 and max_dd_delta_vs_momentum >= -2.0:
            return (
                "Strong behavioural compromise: close to full momentum, with more "
                "continuous SPY exposure."
            )

        if max_dd_improvement_vs_buy_hold > 15 and cagr_delta_vs_buy_hold > -0.50:
            return (
                "Useful compromise: preserves most compounding while reducing "
                "buy-and-hold drawdown."
            )

        return (
            "Middling blend: improves drawdown but does not clearly justify added "
            "complexity."
        )

    return "Needs review."


def create_core_satellite_diagnostic(
    metrics: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    core_satellite_strategy: str,
    annual_rebalanced_core_satellite_strategy: str | None = None,
    momentum_strategy: str = "12-Month Absolute Momentum",
    buy_hold_strategy: str = "Buy and Hold",
) -> pd.DataFrame:
    """
    Create a focused diagnostic comparing buy-and-hold, 12M momentum,
    and core-satellite.

    This is not a new backtest. It is a decision table for interpreting the
    existing core-satellite result.
    """
    if metrics.empty:
        return pd.DataFrame()

    buy_hold = _get_strategy_row(metrics, buy_hold_strategy)
    momentum = _get_strategy_row(metrics, momentum_strategy)
    core_satellite = _get_strategy_row(metrics, core_satellite_strategy)

    rows_to_compare = [buy_hold, momentum, core_satellite]

    if annual_rebalanced_core_satellite_strategy is not None:
        annual_rebalanced_core_satellite = _get_strategy_row(
            metrics,
            annual_rebalanced_core_satellite_strategy,
        )
        rows_to_compare.append(annual_rebalanced_core_satellite)

    rows = []

    for row in rows_to_compare:
        strategy = str(row["strategy"])

        cagr_delta_vs_buy_hold = float(row["cagr_pct"] - buy_hold["cagr_pct"])
        cagr_delta_vs_momentum = float(row["cagr_pct"] - momentum["cagr_pct"])

        max_dd_improvement_vs_buy_hold = float(
            row["max_drawdown_pct"] - buy_hold["max_drawdown_pct"]
        )
        max_dd_delta_vs_momentum = float(
            row["max_drawdown_pct"] - momentum["max_drawdown_pct"]
        )

        diagnostic_row = {
            "strategy": strategy,
            "end_value": float(row["end_value"]),
            "cagr_pct": float(row["cagr_pct"]),
            "volatility_pct": float(row["volatility_pct"]),
            "sharpe": float(row["sharpe"]),
            "sortino": float(row["sortino"]),
            "max_drawdown_pct": float(row["max_drawdown_pct"]),
            "exposure_time_pct": float(row["exposure_time_pct"]),
            "trade_count": int(row["trade_count"]),
            "cagr_delta_vs_buy_hold_pct_points": cagr_delta_vs_buy_hold,
            "cagr_delta_vs_12m_momentum_pct_points": cagr_delta_vs_momentum,
            "drawdown_improvement_vs_buy_hold_pct_points": (
                max_dd_improvement_vs_buy_hold
            ),
            "drawdown_delta_vs_12m_momentum_pct_points": max_dd_delta_vs_momentum,
            "avg_3y_cagr_pct": _get_rolling_value(
                rolling_summary,
                strategy,
                3,
                "avg_cagr_pct",
            ),
            "worst_3y_cagr_pct": _get_rolling_value(
                rolling_summary,
                strategy,
                3,
                "worst_cagr_pct",
            ),
            "avg_5y_cagr_pct": _get_rolling_value(
                rolling_summary,
                strategy,
                5,
                "avg_cagr_pct",
            ),
            "worst_5y_cagr_pct": _get_rolling_value(
                rolling_summary,
                strategy,
                5,
                "worst_cagr_pct",
            ),
            "avg_5y_max_drawdown_pct": _get_rolling_value(
                rolling_summary,
                strategy,
                5,
                "avg_max_drawdown_pct",
            ),
        }

        diagnostic_row["verdict"] = _build_verdict(
            strategy=strategy,
            cagr_delta_vs_buy_hold=cagr_delta_vs_buy_hold,
            max_dd_improvement_vs_buy_hold=max_dd_improvement_vs_buy_hold,
            cagr_delta_vs_momentum=cagr_delta_vs_momentum,
            max_dd_delta_vs_momentum=max_dd_delta_vs_momentum,
        )

        rows.append(diagnostic_row)

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(2)

    return output


def write_core_satellite_diagnostic_markdown(
    diagnostic: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if diagnostic.empty:
        output_path.write_text(
            "# Core-Satellite Diagnostic\n\nNo data available.\n",
            encoding="utf-8",
        )
        return output_path

    display_columns = [
        "strategy",
        "end_value",
        "cagr_pct",
        "volatility_pct",
        "sharpe",
        "sortino",
        "max_drawdown_pct",
        "exposure_time_pct",
        "trade_count",
        "worst_3y_cagr_pct",
        "worst_5y_cagr_pct",
        "cagr_delta_vs_buy_hold_pct_points",
        "drawdown_improvement_vs_buy_hold_pct_points",
        "cagr_delta_vs_12m_momentum_pct_points",
        "drawdown_delta_vs_12m_momentum_pct_points",
        "verdict",
    ]

    available_columns = [column for column in display_columns if column in diagnostic.columns]

    markdown_table = diagnostic[available_columns].to_markdown(index=False)

    content = f"""# Core-Satellite Diagnostic

This report compares SPY buy-and-hold, SPY 12-month absolute momentum, and the 60/40 independent core-satellite strategy.

The goal is to decide whether the core-satellite structure improves the return/drawdown/liveability trade-off enough to justify added complexity.

## Diagnostic Table

{markdown_table}

## Interpretation Notes

- Core-satellite is not a new asset class. It is variable SPY exposure.
- It should reduce drawdown versus buy-and-hold.
- It should preserve more continuous market participation than full momentum.
- It does not need to beat full momentum to be behaviourally useful.
- But if it merely sits in the middle without improving liveability, it is not worth adding complexity.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path