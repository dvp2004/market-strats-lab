from __future__ import annotations

from pathlib import Path

import pandas as pd


def _get_dual_asset_names(result: pd.DataFrame) -> list[str]:
    asset_names = []

    for column in result.columns:
        if column.startswith("adj_close_") and column != "adj_close":
            asset_names.append(column.replace("adj_close_", "", 1))

    if len(asset_names) != 2:
        raise ValueError(
            "Dual momentum opportunity audit expects exactly two adj_close_<ASSET> columns"
        )

    return asset_names


def _compound_return(series: pd.Series) -> float:
    if series.empty:
        return 0.0

    return float((1.0 + series.astype(float)).prod() - 1.0)


def _price_return(segment_df: pd.DataFrame, column: str) -> float:
    start_price = float(segment_df[column].iloc[0])
    end_price = float(segment_df[column].iloc[-1])

    if start_price == 0:
        return 0.0

    return (end_price / start_price) - 1.0


def create_opportunity_cost_segments(
    result: pd.DataFrame,
    pair_name: str,
) -> pd.DataFrame:
    """
    Calculate opportunity cost for each continuous selected-asset segment.

    Positive missed-return values mean the strategy underperformed the comparison
    asset or the best available option during that segment.
    """
    if result.empty:
        return pd.DataFrame()

    required_columns = {"date", "selected_asset", "equity", "strategy_return"}

    missing_columns = required_columns - set(result.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    asset_a, asset_b = _get_dual_asset_names(result)

    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["selected_asset"] = df["selected_asset"].fillna("UNKNOWN")

    if "cash_reason" not in df.columns:
        df["cash_reason"] = ""

    if "cash_return" not in df.columns:
        df["cash_return"] = 0.0

    segment_id = (df["selected_asset"] != df["selected_asset"].shift()).cumsum()
    df["segment_id"] = segment_id

    rows: list[dict] = []

    for segment_number, segment_df in df.groupby("segment_id"):
        selected_asset = str(segment_df["selected_asset"].iloc[0])
        start_date = segment_df["date"].iloc[0]
        end_date = segment_df["date"].iloc[-1]

        start_equity = float(segment_df["equity"].iloc[0])
        end_equity = float(segment_df["equity"].iloc[-1])

        strategy_return = 0.0 if start_equity == 0 else (end_equity / start_equity) - 1.0

        asset_a_return = _price_return(segment_df, f"adj_close_{asset_a}")
        asset_b_return = _price_return(segment_df, f"adj_close_{asset_b}")
        cash_return = _compound_return(segment_df["cash_return"])

        available_returns = {
            asset_a: asset_a_return,
            asset_b: asset_b_return,
            "CASH": cash_return,
        }

        best_available_asset = max(available_returns, key=available_returns.get)
        best_available_return = available_returns[best_available_asset]

        cash_reason = ""
        if selected_asset == "CASH":
            cash_reason = str(segment_df["cash_reason"].mode().iloc[0])

        row = {
            "pair": pair_name,
            "segment_id": int(segment_number),
            "selected_asset": selected_asset,
            "cash_reason": cash_reason,
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "trading_days_held": int(len(segment_df)),
            "calendar_days_held": int((end_date - start_date).days) + 1,
            "strategy_segment_return_pct": strategy_return * 100.0,
            f"{asset_a}_return_pct": asset_a_return * 100.0,
            f"{asset_b}_return_pct": asset_b_return * 100.0,
            "cash_return_pct": cash_return * 100.0,
            "best_available_asset": best_available_asset,
            "best_available_return_pct": best_available_return * 100.0,
            f"missed_return_vs_{asset_a}_pct_points": (asset_a_return - strategy_return)
            * 100.0,
            f"missed_return_vs_{asset_b}_pct_points": (asset_b_return - strategy_return)
            * 100.0,
            "missed_return_vs_cash_pct_points": (cash_return - strategy_return)
            * 100.0,
            "missed_return_vs_best_pct_points": (
                best_available_return - strategy_return
            )
            * 100.0,
        }

        rows.append(row)

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(2)

    return output


def create_opportunity_cost_summary(
    opportunity_segments: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarise opportunity cost by selected asset.
    """
    if opportunity_segments.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for selected_asset, group in opportunity_segments.groupby("selected_asset"):
        positive_missed = group[group["missed_return_vs_best_pct_points"] > 0]

        rows.append(
            {
                "pair": group["pair"].iloc[0],
                "selected_asset": selected_asset,
                "segment_count": int(len(group)),
                "avg_holding_days": round(float(group["trading_days_held"].mean()), 2),
                "avg_strategy_segment_return_pct": round(
                    float(group["strategy_segment_return_pct"].mean()),
                    2,
                ),
                "avg_missed_return_vs_best_pct_points": round(
                    float(group["missed_return_vs_best_pct_points"].mean()),
                    2,
                ),
                "median_missed_return_vs_best_pct_points": round(
                    float(group["missed_return_vs_best_pct_points"].median()),
                    2,
                ),
                "worst_missed_return_vs_best_pct_points": round(
                    float(group["missed_return_vs_best_pct_points"].max()),
                    2,
                ),
                "segments_with_positive_opportunity_cost": int(len(positive_missed)),
                "positive_opportunity_cost_pct": round(
                    (len(positive_missed) / len(group)) * 100.0,
                    2,
                ),
            }
        )

    return pd.DataFrame(rows).sort_values(
        "avg_missed_return_vs_best_pct_points",
        ascending=False,
    )


def write_dual_momentum_opportunity_markdown(
    opportunity_segments: pd.DataFrame,
    opportunity_summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """
    Write a markdown report for dual momentum opportunity cost.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary_table = (
        opportunity_summary.to_markdown(index=False)
        if not opportunity_summary.empty
        else "No opportunity summary data."
    )

    worst_opportunity_segments = opportunity_segments.sort_values(
        "missed_return_vs_best_pct_points",
        ascending=False,
    ).head(10)

    worst_opportunity_table = (
        worst_opportunity_segments.to_markdown(index=False)
        if not worst_opportunity_segments.empty
        else "No opportunity segment data."
    )

    content = f"""# Dual Momentum Opportunity-Cost Audit

This report shows what the dual momentum strategy missed during each holding segment.

Positive missed-return values mean the strategy would have done better by holding the comparison asset or the best available option during the same segment.

## Opportunity-Cost Summary

{summary_table}

## Worst Missed-Opportunity Segments

{worst_opportunity_table}

## Interpretation Notes

- This is diagnostic, not a new trading rule.
- A large missed return versus SPY usually means the strategy gave up equity compounding.
- A large missed return versus best available asset shows how costly the selected asset was relative to the best hindsight alternative.
- Do not use this table to tune rules directly; use it to understand failure modes.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path