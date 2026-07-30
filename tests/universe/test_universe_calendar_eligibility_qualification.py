from __future__ import annotations

from datetime import date, timedelta

from market_strats.universe.calendar import build_monthly_decision_calendar
from market_strats.universe.contracts import ExclusionReason, QualificationVerdict
from market_strats.universe.eligibility import evaluate_security_eligibility
from market_strats.universe.hashing import sha256_json
from market_strats.universe.qualification import minimum_segments_satisfied, select_verdict


def _prices(
    *,
    security_id: str = "sec",
    sessions: int = 252,
    close: float = 100,
    volume: int = 1_000_000,
    end: date = date(2024, 1, 31),
) -> list[dict[str, object]]:
    return [
        {
            "security_id": security_id,
            "session_date": end - timedelta(days=sessions - index - 1),
            "raw_close": close,
            "volume": volume,
        }
        for index in range(sessions)
    ]


def _evaluate(rows: list[dict[str, object]], **kwargs: object):
    return evaluate_security_eligibility(
        security_id="sec",
        decision_date=date(2024, 1, 31),
        execution_date=date(2024, 2, 1),
        price_rows=rows,
        identity_resolved=bool(kwargs.pop("identity_resolved", True)),
        membership_conflict=bool(kwargs.pop("membership_conflict", False)),
        **kwargs,
    )


def test_monthly_calendar_is_deterministic_and_next_session_executes() -> None:
    first = build_monthly_decision_calendar(start=date(2024, 1, 1), end=date(2024, 3, 31))
    second = build_monthly_decision_calendar(start=date(2024, 1, 1), end=date(2024, 3, 31))
    assert first.equals(second)
    assert len(first) == 3
    assert all(first["execution_date"] > first["decision_date"])


def test_valid_security_is_eligible() -> None:
    result = _evaluate(_prices())
    assert result.eligible
    assert result.reason_codes == ()


def test_missing_price_fails_without_imputation() -> None:
    result = _evaluate(_prices()[:-1])
    assert ExclusionReason.MISSING_PRICE in result.reason_codes


def test_stale_price_is_reported() -> None:
    rows = _prices()
    rows[-1]["session_date"] = date(2024, 1, 30)
    result = _evaluate(rows)
    assert ExclusionReason.MISSING_PRICE in result.reason_codes
    assert ExclusionReason.STALE_PRICE in result.reason_codes


def test_insufficient_252_session_history_is_excluded() -> None:
    result = _evaluate(_prices(sessions=251))
    assert ExclusionReason.INSUFFICIENT_HISTORY in result.reason_codes


def test_price_threshold_is_excluded() -> None:
    result = _evaluate(_prices(close=4.99))
    assert ExclusionReason.PRICE_THRESHOLD in result.reason_codes


def test_liquidity_threshold_is_excluded() -> None:
    result = _evaluate(_prices(close=10, volume=100))
    assert ExclusionReason.LIQUIDITY_THRESHOLD in result.reason_codes


def test_unresolved_identity_is_excluded() -> None:
    result = _evaluate(_prices(), identity_resolved=False)
    assert ExclusionReason.UNRESOLVED_IDENTITY in result.reason_codes


def test_missing_delisting_outcome_is_excluded_not_zeroed() -> None:
    result = _evaluate(
        _prices(),
        delisting_outcome_required=True,
        delisting_outcome_resolved=False,
    )
    assert ExclusionReason.DELISTING_UNRESOLVED in result.reason_codes


def test_hashes_are_deterministic_across_mapping_order() -> None:
    assert sha256_json({"a": 1, "b": [2, 3]}) == sha256_json({"b": [2, 3], "a": 1})


def test_insufficient_history_for_required_segments_fails() -> None:
    minimums = {"training": 60, "walk_forward_validation": 60, "untouched_holdout": 36}
    assert not minimum_segments_satisfied(155, minimums)
    assert minimum_segments_satisfied(156, minimums)


def test_verdict_precedence_is_fail_closed() -> None:
    base = {
        "source_terms_failures": 0,
        "source_coverage_failures": 0,
        "unresolved_identity_mappings": 0,
        "unresolved_membership_conflicts": 0,
        "sampled_reconciliations_failed": 0,
        "price_coverage_failures": 0,
        "delisting_treatment_failures": 0,
        "evaluation_segments_satisfied": True,
    }
    assert select_verdict(**base) == QualificationVerdict.QUALIFIED
    assert (
        select_verdict(**{**base, "source_terms_failures": 1}) == QualificationVerdict.SOURCE_TERMS
    )
    assert (
        select_verdict(**{**base, "unresolved_identity_mappings": 1})
        == QualificationVerdict.IDENTITY
    )
    assert (
        select_verdict(**{**base, "unresolved_membership_conflicts": 1})
        == QualificationVerdict.MEMBERSHIP
    )
    assert (
        select_verdict(**{**base, "price_coverage_failures": 1})
        == QualificationVerdict.PRICE_OR_DELISTING
    )
    assert (
        select_verdict(**{**base, "evaluation_segments_satisfied": False})
        == QualificationVerdict.SOURCE_COVERAGE
    )
