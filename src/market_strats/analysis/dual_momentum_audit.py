from __future__ import annotations

from pathlib import Path

import pandas as pd


def create_holding_segments(
    result: pd.DataFrame,
    pair_name: str,
) -> pd.DataFrame:
    """
    Convert a dual momentum daily result into holding segments.

    A segment is a continuous period where the selected asset is unchanged.
    """
    if result.empty:
        return pd.DataFrame()

    required_columns = {"date", "selected_asset", "equity", "strategy_return"}

    missing_columns = required_columns - set(result.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["selected_asset"] = df["selected_asset"].fillna("UNKNOWN")

    if "cash_reason" not in df.columns:
        df["cash_reason"] = "UNKNOWN"

    segment_id = (df["selected_asset"] != df["selected_asset"].shift()).cumsum()
    df["segment_id"] = segment_id

    rows: list[dict] = []

    for segment_number, segment_df in df.groupby("segment_id"):
        selected_asset = str(segment_df["selected_asset"].iloc[0])
        start_date = segment_df["date"].iloc[0]
        end_date = segment_df["date"].iloc[-1]

        start_equity = float(segment_df["equity"].iloc[0])
        end_equity = float(segment_df["equity"].iloc[-1])

        if start_equity == 0:
            segment_return = 0.0
        else:
            segment_return = (end_equity / start_equity) - 1.0

        cash_reason = ""
        if selected_asset == "CASH":
            cash_reason = str(segment_df["cash_reason"].mode().iloc[0])

        rows.append(
            {
                "pair": pair_name,
                "segment_id": int(segment_number),
                "selected_asset": selected_asset,
                "cash_reason": cash_reason,
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "trading_days_held": int(len(segment_df)),
                "calendar_days_held": int((end_date - start_date).days) + 1,
                "start_equity": start_equity,
                "end_equity": end_equity,
                "segment_return_pct": round(float(segment_return * 100.0), 2),
            }
        )

    return pd.DataFrame(rows)


def create_allocation_audit(
    result: pd.DataFrame,
    pair_name: str,
) -> pd.DataFrame:
    """
    Summarise time spent in each selected asset and cash.
    """
    segments = create_holding_segments(result, pair_name)

    if segments.empty:
        return pd.DataFrame()

    total_days = segments["trading_days_held"].sum()

    rows: list[dict] = []

    for selected_asset, group in segments.groupby("selected_asset"):
        days_held = int(group["trading_days_held"].sum())
        segment_count = int(len(group))
        losing_segments = group[group["segment_return_pct"] < 0]
        short_losing_segments = losing_segments[losing_segments["trading_days_held"] <= 126]

        rows.append(
            {
                "pair": pair_name,
                "selected_asset": selected_asset,
                "days_held": days_held,
                "time_held_pct": round((days_held / total_days) * 100.0, 2),
                "switch_count": segment_count,
                "avg_holding_days": round(float(group["trading_days_held"].mean()), 2),
                "median_holding_days": round(float(group["trading_days_held"].median()), 2),
                "min_holding_days": int(group["trading_days_held"].min()),
                "max_holding_days": int(group["trading_days_held"].max()),
                "losing_segment_count": int(len(losing_segments)),
                "short_losing_segment_count": int(len(short_losing_segments)),
                "avg_segment_return_pct": round(float(group["segment_return_pct"].mean()), 2),
                "worst_segment_return_pct": round(float(group["segment_return_pct"].min()), 2),
                "best_segment_return_pct": round(float(group["segment_return_pct"].max()), 2),
            }
        )

    return pd.DataFrame(rows).sort_values("time_held_pct", ascending=False)


def create_cash_reason_summary(
    result: pd.DataFrame,
    pair_name: str,
) -> pd.DataFrame:
    """
    Summarise why the strategy held cash.

    Current valid cash reasons:
    - INSUFFICIENT_HISTORY
    - ABSOLUTE_FILTER
    """
    if result.empty:
        return pd.DataFrame()

    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])

    if "cash_reason" not in df.columns:
        df["cash_reason"] = "UNKNOWN"

    cash_df = df[df["selected_asset"] == "CASH"].copy()

    if cash_df.empty:
        return pd.DataFrame(
            columns=[
                "pair",
                "cash_reason",
                "days_held",
                "cash_time_pct",
                "total_strategy_time_pct",
            ]
        )

    total_days = len(df)
    total_cash_days = len(cash_df)

    rows: list[dict] = []

    for cash_reason, group in cash_df.groupby("cash_reason"):
        days_held = int(len(group))

        rows.append(
            {
                "pair": pair_name,
                "cash_reason": str(cash_reason),
                "days_held": days_held,
                "cash_time_pct": round((days_held / total_cash_days) * 100.0, 2),
                "total_strategy_time_pct": round((days_held / total_days) * 100.0, 2),
            }
        )

    return pd.DataFrame(rows).sort_values("days_held", ascending=False)


def write_dual_momentum_audit_markdown(
    allocation_audit: pd.DataFrame,
    holding_segments: pd.DataFrame,
    cash_summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """
    Write a compact markdown audit report.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    allocation_table = (
        allocation_audit.to_markdown(index=False)
        if not allocation_audit.empty
        else "No allocation audit data."
    )

    cash_table = (
        cash_summary.to_markdown(index=False)
        if not cash_summary.empty
        else "No cash periods."
    )

    worst_segments = holding_segments.sort_values("segment_return_pct").head(10)
    worst_segments_table = (
        worst_segments.to_markdown(index=False)
        if not worst_segments.empty
        else "No segment data."
    )

    content = f"""# Dual Momentum Allocation Audit

This report explains what the dual momentum strategy actually held over time.

## Allocation Summary

{allocation_table}

## Cash Reason Summary

{cash_table}

## Worst Holding Segments

{worst_segments_table}

## Interpretation Notes

- High cash time from INSUFFICIENT_HISTORY is expected at the beginning.
- Cash from ABSOLUTE_FILTER means the relative winner failed to beat cash.
- Short losing segments can indicate whipsaw.
- Long losing segments can indicate being trapped in the wrong asset during a regime shift.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path