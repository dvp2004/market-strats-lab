"""Deterministic monthly US-equity decision and execution calendar."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pandas_market_calendars as mcal

from market_strats.universe.contracts import UniverseContractError


def build_monthly_decision_calendar(
    *,
    start: date,
    end: date,
    exchange_calendar: str = "XNYS",
    same_close_execution: str = "prohibited",
) -> pd.DataFrame:
    if same_close_execution != "prohibited":
        raise UniverseContractError("Same-close execution must remain prohibited")
    if end < start:
        raise UniverseContractError("Calendar end precedes start")
    calendar = mcal.get_calendar(exchange_calendar)
    schedule = calendar.schedule(start_date=start, end_date=end + timedelta(days=10))
    if schedule.empty:
        raise UniverseContractError("Exchange calendar produced no eligible sessions")
    sessions = pd.DatetimeIndex(schedule.index).tz_localize(None)
    endpoint_sessions = sessions[sessions.date <= end]
    if endpoint_sessions.empty:
        raise UniverseContractError("No eligible session exists on or before the endpoint")
    grouped = pd.Series(endpoint_sessions, index=endpoint_sessions).groupby(
        [endpoint_sessions.year, endpoint_sessions.month]
    )
    decisions = [group.max() for _, group in grouped]
    rows: list[dict[str, object]] = []
    for decision in decisions:
        next_sessions = sessions[sessions > decision]
        if next_sessions.empty:
            continue
        execution = next_sessions[0]
        rows.append(
            {
                "decision_date": decision.date(),
                "decision_time": "official_close",
                "execution_date": execution.date(),
                "execution_time": "official_open",
                "exchange_calendar": exchange_calendar,
                "same_close_execution": False,
            }
        )
    return pd.DataFrame(rows)
