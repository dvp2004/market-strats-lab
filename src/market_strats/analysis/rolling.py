from __future__ import annotations

from typing import Any

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics


def slice_result_by_rolling_window(
    result: pd.DataFrame,
    end_date: pd.Timestamp,
    years: int,
) -> pd.DataFrame:
    """
    Slice a strategy result into a rolling calendar-year window ending at end_date.

    The sliced return series is recalculated from the sliced equity curve so that
    each window starts cleanly at 0% return.
    """
    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    window_start = end_date - pd.DateOffset(years=years)

    mask = (df["date"] >= window_start) & (df["date"] <= end_date)
    window_df = df.loc[mask].copy().reset_index(drop=True)

    if len(window_df) < 252:
        return pd.DataFrame()

    window_df["strategy_return"] = window_df["equity"].pct_change().fillna(0.0)

    return window_df


def get_month_end_dates(result: pd.DataFrame) -> list[pd.Timestamp]:
    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    month_ends = df.set_index("date").resample("ME").last().index

    return list(month_ends)


def calculate_rolling_window_metrics(
    results: dict[str, pd.DataFrame],
    window_years: tuple[int, ...] = (3, 5),
) -> pd.DataFrame:
    """
    Calculate rolling-window metrics for each strategy.

    Output is long-form:
    one row per strategy per rolling window.
    """
    if not results:
        return pd.DataFrame()

    first_result = next(iter(results.values()))
    month_end_dates = get_month_end_dates(first_result)

    rows: list[dict[str, Any]] = []

    for years in window_years:
        for end_date in month_end_dates:
            for strategy_name, result in results.items():
                window_result = slice_result_by_rolling_window(
                    result=result,
                    end_date=end_date,
                    years=years,
                )

                if window_result.empty:
                    continue

                metrics = calculate_metrics(window_result, strategy_name)

                row = {
                    "window_years": years,
                    "window_start": metrics["start_date"],
                    "window_end": metrics["end_date"],
                    **metrics,
                }

                rows.append(row)

    return pd.DataFrame(rows)


def create_rolling_summary(rolling_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Summarise rolling-window behaviour by strategy and window length.
    """
    if rolling_metrics.empty:
        return pd.DataFrame()

    grouped = rolling_metrics.groupby(["window_years", "strategy"], as_index=False)

    summary = grouped.agg(
        windows_count=("cagr_pct", "count"),
        avg_cagr_pct=("cagr_pct", "mean"),
        median_cagr_pct=("cagr_pct", "median"),
        best_cagr_pct=("cagr_pct", "max"),
        worst_cagr_pct=("cagr_pct", "min"),
        positive_windows_pct=("cagr_pct", lambda x: (x > 0).mean() * 100),
        avg_max_drawdown_pct=("max_drawdown_pct", "mean"),
        worst_max_drawdown_pct=("max_drawdown_pct", "min"),
        avg_sharpe=("sharpe", "mean"),
        avg_exposure_time_pct=("exposure_time_pct", "mean"),
    )

    numeric_cols = [
        "avg_cagr_pct",
        "median_cagr_pct",
        "best_cagr_pct",
        "worst_cagr_pct",
        "positive_windows_pct",
        "avg_max_drawdown_pct",
        "worst_max_drawdown_pct",
        "avg_sharpe",
        "avg_exposure_time_pct",
    ]

    for col in numeric_cols:
        summary[col] = summary[col].round(2)

    return summary