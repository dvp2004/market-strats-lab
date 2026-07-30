"""Strict terminal qualification verdict selection."""

from __future__ import annotations

from datetime import date
from typing import Any

from market_strats.universe.contracts import QualificationVerdict


def minimum_segments_satisfied(
    monthly_decision_count: int,
    segment_minimums: dict[str, int],
) -> bool:
    required = (
        int(segment_minimums["training"])
        + int(segment_minimums["walk_forward_validation"])
        + int(segment_minimums["untouched_holdout"])
    )
    return monthly_decision_count >= required


def select_verdict(
    *,
    source_terms_failures: int,
    source_coverage_failures: int,
    unresolved_identity_mappings: int,
    unresolved_membership_conflicts: int,
    sampled_reconciliations_failed: int,
    price_coverage_failures: int,
    delisting_treatment_failures: int,
    evaluation_segments_satisfied: bool,
) -> QualificationVerdict:
    if source_terms_failures:
        return QualificationVerdict.SOURCE_TERMS
    if unresolved_identity_mappings:
        return QualificationVerdict.IDENTITY
    if unresolved_membership_conflicts or sampled_reconciliations_failed:
        return QualificationVerdict.MEMBERSHIP
    if price_coverage_failures or delisting_treatment_failures:
        return QualificationVerdict.PRICE_OR_DELISTING
    if source_coverage_failures or not evaluation_segments_satisfied:
        return QualificationVerdict.SOURCE_COVERAGE
    return QualificationVerdict.QUALIFIED


def build_qualification_summary(
    *,
    earliest_qualified_decision_date: date | None,
    latest_qualified_decision_date: date | None,
    monthly_decision_dates: int,
    unique_securities: int,
    additions_covered: int,
    removals_covered: int,
    unresolved_membership_conflicts: int,
    unresolved_identity_mappings: int,
    price_coverage_failures: int,
    delisting_treatment_failures: int,
    sampled_reconciliations_passed: int,
    sampled_reconciliations_failed: int,
    source_coverage_failures: int,
    source_terms_failures: int,
    segment_minimums: dict[str, int],
    blocking_reasons: list[str],
) -> dict[str, Any]:
    segments_ok = minimum_segments_satisfied(monthly_decision_dates, segment_minimums)
    verdict = select_verdict(
        source_terms_failures=source_terms_failures,
        source_coverage_failures=source_coverage_failures,
        unresolved_identity_mappings=unresolved_identity_mappings,
        unresolved_membership_conflicts=unresolved_membership_conflicts,
        sampled_reconciliations_failed=sampled_reconciliations_failed,
        price_coverage_failures=price_coverage_failures,
        delisting_treatment_failures=delisting_treatment_failures,
        evaluation_segments_satisfied=segments_ok,
    )
    return {
        "verdict": verdict.value,
        "earliest_qualified_decision_date": (
            None
            if earliest_qualified_decision_date is None
            else earliest_qualified_decision_date.isoformat()
        ),
        "latest_qualified_decision_date": (
            None
            if latest_qualified_decision_date is None
            else latest_qualified_decision_date.isoformat()
        ),
        "monthly_decision_dates": monthly_decision_dates,
        "unique_securities": unique_securities,
        "additions_covered": additions_covered,
        "removals_covered": removals_covered,
        "unresolved_membership_conflicts": unresolved_membership_conflicts,
        "unresolved_identity_mappings": unresolved_identity_mappings,
        "price_coverage_failures": price_coverage_failures,
        "delisting_treatment_failures": delisting_treatment_failures,
        "sampled_independent_reconciliations_passed": sampled_reconciliations_passed,
        "sampled_independent_reconciliations_failed": sampled_reconciliations_failed,
        "minimum_training_validation_holdout_lengths_satisfied": segments_ok,
        "model_training_authorized": verdict == QualificationVerdict.QUALIFIED,
        "blocking_reasons": sorted(set(blocking_reasons)),
    }
