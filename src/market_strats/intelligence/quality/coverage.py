"""U.S. equity-session coverage audit for MI-1 market data."""

from __future__ import annotations

from datetime import date

import pandas_market_calendars as mcal

from market_strats.intelligence.contracts import (
    CoverageAuditRow,
    DataQualityEvent,
    InstrumentRegistryEntry,
    MarketEodBar,
)


def us_equity_sessions(start: date, end: date) -> list[date]:
    calendar = mcal.get_calendar("XNYS")
    schedule = calendar.schedule(start_date=start.isoformat(), end_date=end.isoformat())
    return [session.date() for session in schedule.index]


def _longest_continuous_run(observed: set[date], expected_sessions: list[date]) -> int:
    longest = 0
    current = 0
    for session in expected_sessions:
        if session in observed:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _has_full_window(
    observed: set[date],
    all_sessions: list[date],
    end_index: int,
    minimum_sessions: int,
) -> bool:
    start_index = end_index - minimum_sessions + 1
    if start_index < 0:
        return False
    return all(session in observed for session in all_sessions[start_index : end_index + 1])


def determine_common_research_start_date(
    bars_by_instrument: dict[str, set[date]],
    all_sessions: list[date],
    minimum_sessions: int,
) -> tuple[date | None, str]:
    if not bars_by_instrument:
        return None, "no instruments available for coverage audit"
    for end_index, session in enumerate(all_sessions):
        if all(
            _has_full_window(observed, all_sessions, end_index, minimum_sessions)
            for observed in bars_by_instrument.values()
        ):
            return session, ""
    return None, f"no common date with {minimum_sessions} continuous eligible sessions"


def build_coverage_audit(
    *,
    run_id: str,
    instruments: list[InstrumentRegistryEntry],
    bars: list[MarketEodBar],
    start: date,
    end: date,
    minimum_common_history_sessions: int,
) -> tuple[list[CoverageAuditRow], list[DataQualityEvent], date | None, str]:
    sessions = us_equity_sessions(start, end)
    by_instrument: dict[str, set[date]] = {
        instrument.instrument_id: set() for instrument in instruments
    }
    for bar in bars:
        by_instrument.setdefault(bar.instrument_id, set()).add(bar.session_date)

    common_start, blocked_reason = determine_common_research_start_date(
        by_instrument,
        sessions,
        minimum_common_history_sessions,
    )

    events: list[DataQualityEvent] = []
    audit_rows: list[CoverageAuditRow] = []
    for instrument in instruments:
        observed = by_instrument[instrument.instrument_id]
        first_observed = min(observed) if observed else None
        last_observed = max(observed) if observed else None
        if first_observed is None or last_observed is None:
            eligible_sessions = 0
            missing_sessions = len(sessions)
            coverage_ratio = 0.0
            continuous = 0
            notes = "no observed sessions"
        else:
            expected = us_equity_sessions(first_observed, last_observed)
            missing = [session for session in expected if session not in observed]
            eligible_sessions = len(expected)
            missing_sessions = len(missing)
            coverage_ratio = 0.0 if not expected else (len(expected) - len(missing)) / len(expected)
            continuous = _longest_continuous_run(observed, expected)
            notes = "ok" if missing_sessions == 0 else "missing expected sessions"
            for session in missing:
                events.append(
                    DataQualityEvent(
                        run_id=run_id,
                        severity="warning",
                        event_type="missing_expected_session",
                        instrument_id=instrument.instrument_id,
                        session_date=session,
                        message="Expected U.S. equity session is absent from normalized bars",
                        source="coverage_audit",
                    )
                )
            if missing_sessions:
                events.append(
                    DataQualityEvent(
                        run_id=run_id,
                        severity="warning",
                        event_type="coverage_gap",
                        instrument_id=instrument.instrument_id,
                        session_date=None,
                        message=f"{missing_sessions} expected sessions are missing",
                        source="coverage_audit",
                    )
                )

        start_date_eligible = common_start is not None and _has_full_window(
            observed,
            sessions,
            sessions.index(common_start),
            minimum_common_history_sessions,
        )
        audit_rows.append(
            CoverageAuditRow(
                run_id=run_id,
                instrument_id=instrument.instrument_id,
                first_observed_session=first_observed,
                last_observed_session=last_observed,
                eligible_sessions=eligible_sessions,
                missing_sessions=missing_sessions,
                coverage_ratio=coverage_ratio,
                continuous_history_sessions=continuous,
                start_date_eligible=start_date_eligible,
                notes=notes,
            )
        )
    return audit_rows, events, common_start, blocked_reason
