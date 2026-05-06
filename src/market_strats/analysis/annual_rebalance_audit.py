from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_drawdown


def _future_return(
    df: pd.DataFrame,
    start_index: int,
    trading_days: int,
) -> float:
    target_index = min(start_index + trading_days, len(df) - 1)

    start_equity = float(df["equity"].iloc[start_index])
    end_equity = float(df["equity"].iloc[target_index])

    if start_equity == 0:
        return 0.0

    return (end_equity / start_equity) - 1.0


def create_annual_rebalance_audit(
    result: pd.DataFrame,
    strategy_name: str,
) -> pd.DataFrame:
    """
    Audit annual rebalance events for a rebalanced core-satellite strategy.

    This shows whether rebalancing happened when the portfolio was in drawdown,
    how far sleeve weights had drifted, and what happened over the following
    3, 6, and 12 months.
    """
    if result.empty:
        return pd.DataFrame()

    required_columns = {
        "date",
        "equity",
        "is_rebalance_day",
        "rebalance_turnover",
        "total_equity_before_rebalance",
        "core_sleeve_equity_before_rebalance",
        "satellite_sleeve_equity_before_rebalance",
        "core_weight_before_rebalance",
        "satellite_weight_before_rebalance",
        "current_core_weight",
        "current_satellite_weight",
        "position",
        "cash_position",
    }

    missing_columns = required_columns - set(result.columns)

    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    df["portfolio_drawdown"] = calculate_drawdown(df["equity"])

    rebalance_df = df[df["is_rebalance_day"]].copy()

    if rebalance_df.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for index, row in rebalance_df.iterrows():
        target_core_weight = float(row["core_initial_weight"])
        target_satellite_weight = float(row["satellite_initial_weight"])

        core_weight_before = float(row["core_weight_before_rebalance"])
        satellite_weight_before = float(row["satellite_weight_before_rebalance"])

        rows.append(
            {
                "strategy": strategy_name,
                "rebalance_date": row["date"].date().isoformat(),
                "portfolio_equity_before_rebalance": float(
                    row["total_equity_before_rebalance"]
                ),
                "portfolio_equity_after_rebalance": float(row["equity"]),
                "portfolio_drawdown_at_rebalance_pct": float(
                    row["portfolio_drawdown"] * 100.0
                ),
                "core_equity_before_rebalance": float(
                    row["core_sleeve_equity_before_rebalance"]
                ),
                "satellite_equity_before_rebalance": float(
                    row["satellite_sleeve_equity_before_rebalance"]
                ),
                "core_weight_before_rebalance_pct": core_weight_before * 100.0,
                "satellite_weight_before_rebalance_pct": satellite_weight_before * 100.0,
                "target_core_weight_pct": target_core_weight * 100.0,
                "target_satellite_weight_pct": target_satellite_weight * 100.0,
                "core_weight_drift_pct_points": (
                    core_weight_before - target_core_weight
                )
                * 100.0,
                "satellite_weight_drift_pct_points": (
                    satellite_weight_before - target_satellite_weight
                )
                * 100.0,
                "rebalance_turnover_pct": float(row["rebalance_turnover"] * 100.0),
                "portfolio_position_after_rebalance_pct": float(
                    row["position"] * 100.0
                ),
                "portfolio_cash_after_rebalance_pct": float(
                    row["cash_position"] * 100.0
                ),
                "next_3m_return_pct": _future_return(df, int(index), 63) * 100.0,
                "next_6m_return_pct": _future_return(df, int(index), 126) * 100.0,
                "next_12m_return_pct": _future_return(df, int(index), 252) * 100.0,
            }
        )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(2)

    return output.reset_index(drop=True)


def create_annual_rebalance_audit_summary(audit: pd.DataFrame) -> pd.DataFrame:
    if audit.empty:
        return pd.DataFrame()

    return pd.DataFrame(
        [
            {
                "rebalance_count": int(len(audit)),
                "avg_rebalance_turnover_pct": round(
                    float(audit["rebalance_turnover_pct"].mean()),
                    2,
                ),
                "max_rebalance_turnover_pct": round(
                    float(audit["rebalance_turnover_pct"].max()),
                    2,
                ),
                "avg_drawdown_at_rebalance_pct": round(
                    float(audit["portfolio_drawdown_at_rebalance_pct"].mean()),
                    2,
                ),
                "worst_drawdown_at_rebalance_pct": round(
                    float(audit["portfolio_drawdown_at_rebalance_pct"].min()),
                    2,
                ),
                "avg_next_3m_return_pct": round(
                    float(audit["next_3m_return_pct"].mean()),
                    2,
                ),
                "avg_next_6m_return_pct": round(
                    float(audit["next_6m_return_pct"].mean()),
                    2,
                ),
                "avg_next_12m_return_pct": round(
                    float(audit["next_12m_return_pct"].mean()),
                    2,
                ),
                "positive_next_12m_pct": round(
                    float((audit["next_12m_return_pct"] > 0).mean() * 100.0),
                    2,
                ),
            }
        ]
    )


def write_annual_rebalance_audit_markdown(
    audit: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if audit.empty:
        output_path.write_text(
            "# Annual Rebalance Audit\n\nNo rebalance events found.\n",
            encoding="utf-8",
        )
        return output_path

    summary_table = (
        summary.to_markdown(index=False) if not summary.empty else "No summary data."
    )

    worst_drawdown_rebalances = audit.sort_values(
        "portfolio_drawdown_at_rebalance_pct"
    ).head(10)

    largest_turnover_rebalances = audit.sort_values(
        "rebalance_turnover_pct",
        ascending=False,
    ).head(10)

    content = f"""# Annual Rebalance Audit

This report audits annual rebalance events for the rebalanced core-satellite strategy.

It helps answer whether rebalancing added value by buying after drawdowns or merely increased risk exposure.

## Summary

{summary_table}

## Rebalances During Worst Drawdowns

{worst_drawdown_rebalances.to_markdown(index=False)}

## Largest Rebalance Turnover Events

{largest_turnover_rebalances.to_markdown(index=False)}

## Interpretation Notes

- Negative core weight drift means the core had fallen below its target weight before rebalance.
- Positive satellite weight drift often means the satellite/cash sleeve had become overweight.
- Rebalancing during deep drawdowns can behave like forced averaging down.
- Positive next 12M returns after rebalance suggest rebalancing bought weakness profitably.
- This report is diagnostic only; it should not be used to optimise rebalance timing directly.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path