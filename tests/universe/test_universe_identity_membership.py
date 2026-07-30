from __future__ import annotations

from datetime import date, datetime

import pytest

from market_strats.universe.contracts import (
    IdentityResolutionError,
    MembershipAction,
    MembershipEvent,
    SecurityIdentity,
    TickerIdentityInterval,
)
from market_strats.universe.identity import IdentityMap, build_security_id, normalize_ticker
from market_strats.universe.membership import (
    active_members,
    build_membership_intervals,
    compare_membership_event_sets,
    events_from_membership_snapshots,
)


def _identity(stable: str, *, share_class: str | None = None) -> SecurityIdentity:
    security_id = build_security_id(
        namespace="test",
        stable_identifier=stable,
        share_class=share_class,
    )
    return SecurityIdentity(
        security_id=security_id,
        issuer_name=stable,
        cik=stable if stable.isdigit() else None,
        share_class=share_class,
        identity_status="synthetic",
        source_id="synthetic",
    )


def _event(
    security_id: str,
    action: MembershipAction,
    effective: date,
    ticker: str,
) -> MembershipEvent:
    return MembershipEvent(
        event_id=f"{ticker}-{action}-{effective}",
        security_id=security_id,
        ticker=ticker,
        action=action,
        effective_date=effective,
        announced_at=datetime(2020, 1, 1),
        source_id="synthetic",
        source_event_id=f"source-{ticker}-{effective}",
    )


def test_rename_preserves_same_security_identity() -> None:
    identity = _identity("0000000001")
    mapping = IdentityMap()
    mapping.add_identity(identity)
    mapping.add_ticker_interval(
        TickerIdentityInterval(
            identity.security_id, "OLD", "XNYS", date(2010, 1, 1), date(2019, 12, 31), "test"
        )
    )
    mapping.add_ticker_interval(
        TickerIdentityInterval(identity.security_id, "NEW", "XNYS", date(2020, 1, 1), None, "test")
    )
    assert mapping.resolve("OLD", date(2019, 6, 1)) == identity.security_id
    assert mapping.resolve("NEW", date(2020, 6, 1)) == identity.security_id


def test_ticker_reuse_maps_to_different_nonoverlapping_identities() -> None:
    first = _identity("first")
    second = _identity("second")
    mapping = IdentityMap()
    mapping.add_identity(first)
    mapping.add_identity(second)
    mapping.add_ticker_interval(
        TickerIdentityInterval(
            first.security_id, "ABC", None, date(2000, 1, 1), date(2010, 12, 31), "test"
        )
    )
    mapping.add_ticker_interval(
        TickerIdentityInterval(second.security_id, "ABC", None, date(2011, 1, 1), None, "test")
    )
    assert mapping.resolve("ABC", date(2005, 1, 1)) == first.security_id
    assert mapping.resolve("ABC", date(2020, 1, 1)) == second.security_id


def test_overlapping_ticker_reuse_fails_closed() -> None:
    first = _identity("first")
    second = _identity("second")
    mapping = IdentityMap()
    mapping.add_identity(first)
    mapping.add_identity(second)
    mapping.add_ticker_interval(
        TickerIdentityInterval(
            first.security_id, "ABC", None, date(2000, 1, 1), date(2015, 1, 1), "test"
        )
    )
    with pytest.raises(IdentityResolutionError, match="overlap"):
        mapping.add_ticker_interval(
            TickerIdentityInterval(second.security_id, "ABC", None, date(2010, 1, 1), None, "test")
        )


def test_separate_share_classes_have_separate_security_ids() -> None:
    class_a = build_security_id(
        namespace="sec_cik_share_class", stable_identifier="123", share_class="A"
    )
    class_b = build_security_id(
        namespace="sec_cik_share_class", stable_identifier="123", share_class="B"
    )
    assert class_a != class_b


def test_dot_and_hyphen_ticker_punctuation_normalize_to_one_alias() -> None:
    assert normalize_ticker("BF.B") == normalize_ticker("BF-B") == "BF-B"


def test_missing_cik_does_not_enable_ticker_only_false_match() -> None:
    mapping = IdentityMap()
    with pytest.raises(IdentityResolutionError, match="0 identity matches"):
        mapping.resolve("ABC", date(2020, 1, 1))


def test_merger_predecessor_and_successor_are_explicit() -> None:
    successor = _identity("successor")
    predecessor = SecurityIdentity(
        security_id=build_security_id(namespace="test", stable_identifier="predecessor"),
        issuer_name="Predecessor",
        cik=None,
        share_class=None,
        identity_status="synthetic",
        source_id="synthetic",
        successor_security_id=successor.security_id,
    )
    assert predecessor.security_id != successor.security_id
    assert predecessor.successor_security_id == successor.security_id


def test_addition_and_removal_build_one_closed_interval() -> None:
    identity = _identity("member")
    intervals, conflicts = build_membership_intervals(
        [
            _event(identity.security_id, MembershipAction.ADD, date(2020, 1, 2), "ABC"),
            _event(identity.security_id, MembershipAction.REMOVE, date(2020, 2, 3), "ABC"),
        ]
    )
    assert not conflicts
    assert len(intervals) == 1
    assert intervals[0].effective_from == date(2020, 1, 2)
    assert intervals[0].effective_through == date(2020, 2, 2)


def test_removal_without_addition_is_a_conflict() -> None:
    identity = _identity("member")
    intervals, conflicts = build_membership_intervals(
        [_event(identity.security_id, MembershipAction.REMOVE, date(2020, 2, 3), "ABC")]
    )
    assert not intervals
    assert conflicts[0]["conflict_type"] == "removal_without_active_addition"


def test_snapshot_delta_construction_is_deterministic() -> None:
    identities = {"A": _identity("A"), "B": _identity("B")}

    def resolver(ticker: str, observed: date) -> str:
        del observed
        return identities[ticker].security_id

    snapshots = [
        (date(2020, 1, 2), {"A"}),
        (date(2020, 2, 3), {"B"}),
    ]
    first = events_from_membership_snapshots(
        snapshots, source_id="seed", security_id_for_ticker=resolver
    )
    second = events_from_membership_snapshots(
        reversed(snapshots), source_id="seed", security_id_for_ticker=resolver
    )
    assert first == second
    assert [(row.action, row.ticker) for row in first] == [
        (MembershipAction.ADD, "A"),
        (MembershipAction.REMOVE, "A"),
        (MembershipAction.ADD, "B"),
    ]


def test_active_members_respects_effective_removal_boundary() -> None:
    identity = _identity("member")
    intervals, _ = build_membership_intervals(
        [
            _event(identity.security_id, MembershipAction.ADD, date(2020, 1, 2), "ABC"),
            _event(identity.security_id, MembershipAction.REMOVE, date(2020, 2, 3), "ABC"),
        ]
    )
    assert identity.security_id in active_members(intervals, date(2020, 2, 2))
    assert identity.security_id not in active_members(intervals, date(2020, 2, 3))


def test_conflicting_membership_sources_are_reported() -> None:
    identity = _identity("member")
    primary = [_event(identity.security_id, MembershipAction.ADD, date(2020, 1, 2), "ABC")]
    secondary = [_event(identity.security_id, MembershipAction.ADD, date(2020, 1, 3), "ABC")]
    conflicts = compare_membership_event_sets(primary, secondary)
    assert len(conflicts) == 2
    assert {row["conflict_type"] for row in conflicts} == {
        "missing_from_primary",
        "missing_from_secondary",
    }
