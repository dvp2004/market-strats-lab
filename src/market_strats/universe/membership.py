"""Deterministic membership-event and interval construction."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, timedelta

from market_strats.universe.contracts import (
    MembershipAction,
    MembershipEvent,
    MembershipInterval,
    UniverseContractError,
)
from market_strats.universe.hashing import sha256_json


def events_from_membership_snapshots(
    snapshots: Iterable[tuple[date, set[str]]],
    *,
    source_id: str,
    security_id_for_ticker: Callable[[str, date], str],
) -> list[MembershipEvent]:
    ordered = sorted((day, set(tickers)) for day, tickers in snapshots)
    if not ordered:
        raise UniverseContractError("Membership source contains no snapshots")
    events: list[MembershipEvent] = []
    previous: set[str] = set()
    for effective_date, current in ordered:
        for ticker in sorted(current - previous):
            security_id = security_id_for_ticker(ticker, effective_date)
            source_event_id = f"{effective_date.isoformat()}|addition|{ticker}"
            events.append(
                MembershipEvent(
                    event_id=sha256_json({"source": source_id, "event": source_event_id})[:24],
                    security_id=security_id,
                    ticker=ticker,
                    action=MembershipAction.ADD,
                    effective_date=effective_date,
                    announced_at=None,
                    source_id=source_id,
                    source_event_id=source_event_id,
                )
            )
        for ticker in sorted(previous - current):
            security_id = security_id_for_ticker(ticker, effective_date - timedelta(days=1))
            source_event_id = f"{effective_date.isoformat()}|removal|{ticker}"
            events.append(
                MembershipEvent(
                    event_id=sha256_json({"source": source_id, "event": source_event_id})[:24],
                    security_id=security_id,
                    ticker=ticker,
                    action=MembershipAction.REMOVE,
                    effective_date=effective_date,
                    announced_at=None,
                    source_id=source_id,
                    source_event_id=source_event_id,
                )
            )
        previous = current
    return sorted(
        events,
        key=lambda row: (
            row.effective_date,
            0 if row.action == MembershipAction.REMOVE else 1,
            row.ticker,
        ),
    )


def build_membership_intervals(
    events: Iterable[MembershipEvent],
) -> tuple[list[MembershipInterval], list[dict[str, str]]]:
    open_memberships: dict[str, MembershipEvent] = {}
    intervals: list[MembershipInterval] = []
    conflicts: list[dict[str, str]] = []
    ordered = sorted(
        events,
        key=lambda row: (
            row.effective_date,
            0 if row.action == MembershipAction.REMOVE else 1,
            row.security_id,
        ),
    )
    for event in ordered:
        if event.action == MembershipAction.ADD:
            if event.security_id in open_memberships:
                conflicts.append(
                    {
                        "security_id": event.security_id,
                        "effective_date": event.effective_date.isoformat(),
                        "conflict_type": "duplicate_addition_while_active",
                        "source_id": event.source_id,
                    }
                )
                continue
            open_memberships[event.security_id] = event
            continue

        addition = open_memberships.pop(event.security_id, None)
        if addition is None:
            conflicts.append(
                {
                    "security_id": event.security_id,
                    "effective_date": event.effective_date.isoformat(),
                    "conflict_type": "removal_without_active_addition",
                    "source_id": event.source_id,
                }
            )
            continue
        if event.effective_date <= addition.effective_date:
            conflicts.append(
                {
                    "security_id": event.security_id,
                    "effective_date": event.effective_date.isoformat(),
                    "conflict_type": "non_positive_membership_interval",
                    "source_id": event.source_id,
                }
            )
            continue
        intervals.append(
            MembershipInterval(
                security_id=event.security_id,
                ticker_at_addition=addition.ticker,
                effective_from=addition.effective_date,
                effective_through=event.effective_date - timedelta(days=1),
                source_id=addition.source_id,
                addition_event_id=addition.event_id,
                removal_event_id=event.event_id,
            )
        )
    for security_id, addition in sorted(open_memberships.items()):
        intervals.append(
            MembershipInterval(
                security_id=security_id,
                ticker_at_addition=addition.ticker,
                effective_from=addition.effective_date,
                effective_through=None,
                source_id=addition.source_id,
                addition_event_id=addition.event_id,
                removal_event_id=None,
            )
        )
    return sorted(intervals, key=lambda row: (row.effective_from, row.security_id)), conflicts


def active_members(
    intervals: Iterable[MembershipInterval],
    on_date: date,
) -> set[str]:
    return {
        row.security_id
        for row in intervals
        if row.effective_from <= on_date
        and (row.effective_through is None or on_date <= row.effective_through)
    }


def compare_membership_event_sets(
    primary: Iterable[MembershipEvent],
    secondary: Iterable[MembershipEvent],
) -> list[dict[str, str]]:
    def key(row: MembershipEvent) -> tuple[str, str, str]:
        return row.effective_date.isoformat(), row.action.value, row.ticker

    primary_by_key = {key(row): row for row in primary}
    secondary_by_key = {key(row): row for row in secondary}
    conflicts: list[dict[str, str]] = []
    for event_key in sorted(primary_by_key.keys() ^ secondary_by_key.keys()):
        in_primary = event_key in primary_by_key
        conflicts.append(
            {
                "effective_date": event_key[0],
                "action": event_key[1],
                "ticker": event_key[2],
                "conflict_type": (
                    "missing_from_secondary" if in_primary else "missing_from_primary"
                ),
            }
        )
    return conflicts
