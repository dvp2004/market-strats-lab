"""Point-in-time price, history, liquidity, and identity eligibility rules."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from statistics import median

from market_strats.universe.contracts import EligibilityResult, ExclusionReason


def evaluate_security_eligibility(
    *,
    security_id: str,
    decision_date: date,
    execution_date: date,
    price_rows: Iterable[dict[str, object]],
    identity_resolved: bool,
    membership_conflict: bool,
    delisting_outcome_required: bool = False,
    delisting_outcome_resolved: bool = True,
    minimum_history_sessions: int = 252,
    liquidity_window_sessions: int = 60,
    minimum_median_dollar_volume_usd: float = 20_000_000,
    minimum_decision_close_usd: float = 5,
) -> EligibilityResult:
    reasons: list[str] = []
    if not identity_resolved:
        reasons.append(ExclusionReason.UNRESOLVED_IDENTITY)
    if membership_conflict:
        reasons.append(ExclusionReason.UNRESOLVED_MEMBERSHIP)
    if delisting_outcome_required and not delisting_outcome_resolved:
        reasons.append(ExclusionReason.DELISTING_UNRESOLVED)

    ordered = sorted(
        (
            row
            for row in price_rows
            if row.get("security_id") == security_id
            and isinstance(row.get("session_date"), date)
            and row["session_date"] <= decision_date
        ),
        key=lambda row: row["session_date"],
    )
    valid = [
        row for row in ordered if row.get("raw_close") is not None and row.get("volume") is not None
    ]
    history_sessions = len(valid)
    decision_row = next(
        (row for row in reversed(valid) if row["session_date"] == decision_date),
        None,
    )
    decision_close = None if decision_row is None else float(decision_row["raw_close"])
    if decision_row is None:
        reasons.append(ExclusionReason.MISSING_PRICE)
    if valid and valid[-1]["session_date"] != decision_date:
        reasons.append(ExclusionReason.STALE_PRICE)
    if history_sessions < minimum_history_sessions:
        reasons.append(ExclusionReason.INSUFFICIENT_HISTORY)
    if decision_close is not None and decision_close < minimum_decision_close_usd:
        reasons.append(ExclusionReason.PRICE_THRESHOLD)

    trailing = valid[-liquidity_window_sessions:]
    median_dollar_volume = None
    if trailing:
        median_dollar_volume = float(
            median(float(row["raw_close"]) * float(row["volume"]) for row in trailing)
        )
        if (
            len(trailing) < liquidity_window_sessions
            or median_dollar_volume < minimum_median_dollar_volume_usd
        ):
            reasons.append(ExclusionReason.LIQUIDITY_THRESHOLD)
    else:
        reasons.append(ExclusionReason.LIQUIDITY_THRESHOLD)

    unique_reasons = tuple(sorted({str(reason) for reason in reasons}))
    return EligibilityResult(
        decision_date=decision_date,
        execution_date=execution_date,
        security_id=security_id,
        eligible=not unique_reasons,
        reason_codes=unique_reasons,
        history_sessions=history_sessions,
        decision_close_usd=decision_close,
        median_dollar_volume_usd=median_dollar_volume,
    )
