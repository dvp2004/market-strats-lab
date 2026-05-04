from __future__ import annotations

from typing import Any

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics


DEFAULT_REGIMES: list[dict[str, str | None]] = [
    {
        "name": "1993-1999 Bull Market",
        "start": "1993-01-29",
        "end": "1999-12-31",
    },
    {
        "name": "2000-2002 Dot-Com Crash",
        "start": "2000-01-01",
        "end": "2002-12-31",
    },
    {
        "name": "2003-2007 Pre-GFC Recovery",
        "start": "2003-01-01",
        "end": "2007-12-31",
    },
    {
        "name": "2008-2009 Global Financial Crisis",
        "start": "2008-01-01",
        "end": "2009-12-31",
    },
    {
        "name": "2010-2019 Long Bull Market",
        "start": "2010-01-01",
        "end": "2019-12-31",
    },
    {
        "name": "2020 COVID Crash and Rebound",
        "start": "2020-01-01",
        "end": "2020-12-31",
    },
    {
        "name": "2021-2022 Inflation and Rate Shock",
        "start": "2021-01-01",
        "end": "2022-12-31",
    },
    {
        "name": "2023-Present Recent Market",
        "start": "2023-01-01",
        "end": None,
    },
]


def slice_result_by_period(
    result: pd.DataFrame,
    start_date: str,
    end_date: str | None,
) -> pd.DataFrame:
    """
    Slice a strategy result to a specific regime period.

    The equity curve is preserved, but period returns are recalculated from
    the sliced equity curve so that period metrics are not polluted by the
    return from the day before the period started.
    """
    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    start = pd.to_datetime(start_date)
    mask = df["date"] >= start

    if end_date is not None:
        end = pd.to_datetime(end_date)
        mask &= df["date"] <= end

    period_df = df.loc[mask].copy().reset_index(drop=True)

    if len(period_df) < 2:
        return pd.DataFrame()

    period_df["strategy_return"] = period_df["equity"].pct_change().fillna(0.0)

    return period_df


def calculate_regime_metrics(
    results: dict[str, pd.DataFrame],
    regimes: list[dict[str, str | None]] | None = None,
) -> pd.DataFrame:
    """
    Calculate metrics for every strategy across defined market regimes.

    Output format is long-form:
    one row per strategy per regime.
    """
    regimes_to_use = regimes if regimes is not None else DEFAULT_REGIMES

    rows: list[dict[str, Any]] = []

    for regime in regimes_to_use:
        regime_name = str(regime["name"])
        start_date = str(regime["start"])
        end_date = regime["end"]

        for strategy_name, result in results.items():
            period_result = slice_result_by_period(
                result=result,
                start_date=start_date,
                end_date=end_date,
            )

            if period_result.empty:
                continue

            metrics = calculate_metrics(period_result, strategy_name)

            row = {
                "period": regime_name,
                "period_start": start_date,
                "period_end": end_date if end_date is not None else "latest",
                **metrics,
            }

            rows.append(row)

    return pd.DataFrame(rows)


def create_regime_summary(regime_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Create a compact regime comparison table.

    This keeps the most important fields only, so the console output remains readable.
    """
    columns = [
        "period",
        "period_start",
        "period_end",
        "strategy",
        "start_date",
        "end_date",
        "cagr_pct",
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "sortino",
        "exposure_time_pct",
        "trade_count",
    ]

    available_columns = [col for col in columns if col in regime_metrics.columns]

    return regime_metrics[available_columns].copy()