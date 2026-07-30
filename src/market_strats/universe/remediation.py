"""Deterministic remediation primitives for free point-in-time universe evidence."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from market_strats.universe.contracts import (
    MembershipAction,
    MembershipEvent,
    TickerIdentityInterval,
)
from market_strats.universe.hashing import sha256_json
from market_strats.universe.identity import normalize_ticker

IDENTITY_STATUSES = {
    "resolved_sec_cik",
    "resolved_non_sec_security",
    "ambiguous_multiple_candidates",
    "unresolved_no_candidate",
    "source_unavailable",
}
CONFLICT_STATUSES = {
    "resolved_seed_correct",
    "resolved_wikimedia_correct",
    "resolved_official_announcement_authoritative",
    "resolved_identity_alias",
    "unresolved_source_disagreement",
    "unresolved_missing_evidence",
}
PRICE_FAILURE_STATUSES = {
    "provider_ticker_not_found",
    "possibly_delisted_no_history",
    "temporary_provider_failure",
    "insufficient_prior_history",
    "missing_membership_interval_prices",
    "stale_final_price",
    "identity_mapping_unresolved",
    "corporate_action_conflict",
}
TERMINAL_VALUE_STATUSES = {
    "cash_acquisition_value_verified",
    "stock_acquisition_ratio_verified",
    "successor_security_verified",
    "final_traded_price_verified",
    "bankruptcy_or_liquidation_value_verified",
    "provider_adjusted_terminal_return_available",
    "delisting_status_known_terminal_value_unknown",
    "unresolved_delisting",
}


@dataclass(frozen=True)
class MembershipExtensionEvent:
    announcement_timestamp: str | None
    effective_date: date
    added_ticker: str | None
    removed_ticker: str | None
    source_reference: str
    content_hash: str
    source_classification: str
    reconciliation_status: str


@dataclass(frozen=True)
class PriceAuditRequest:
    security_id: str
    provider_ticker: str
    membership_from: date
    membership_through: date
    request_from: date
    request_through: date

    @property
    def request_id(self) -> str:
        return sha256_json(asdict(self))


def membership_extensions_from_change_rows(
    rows: Iterable[Mapping[str, str]],
    *,
    after: date,
    through: date,
    source_reference: str,
    content_hash: str,
    source_classification: str,
) -> list[MembershipExtensionEvent]:
    """Build only explicit event rows; never infer changes from endpoint set differences."""

    events: list[MembershipExtensionEvent] = []
    for row in rows:
        raw_date = row.get("date") or row.get("effective date") or ""
        try:
            effective = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if not after < effective <= through:
            continue
        added = row.get("added ticker") or row.get("added") or None
        removed = row.get("removed ticker") or row.get("removed") or None
        if not added and not removed:
            continue
        events.append(
            MembershipExtensionEvent(
                announcement_timestamp=row.get("announcement timestamp") or None,
                effective_date=effective,
                added_ticker=normalize_ticker(added) if added else None,
                removed_ticker=normalize_ticker(removed) if removed else None,
                source_reference=source_reference,
                content_hash=content_hash,
                source_classification=source_classification,
                reconciliation_status="pending_independent_reconciliation",
            )
        )
    return sorted(events, key=lambda item: (item.effective_date, item.added_ticker or ""))


def apply_membership_extensions(
    *,
    active_tickers: set[str],
    extensions: Iterable[MembershipExtensionEvent],
) -> tuple[set[str], list[dict[str, str]]]:
    current = {normalize_ticker(item) for item in active_tickers}
    conflicts: list[dict[str, str]] = []
    for event in extensions:
        if event.removed_ticker:
            if event.removed_ticker not in current:
                conflicts.append(
                    {
                        "ticker": event.removed_ticker,
                        "effective_date": event.effective_date.isoformat(),
                        "status": "unresolved_source_disagreement",
                    }
                )
            else:
                current.remove(event.removed_ticker)
        if event.added_ticker:
            if event.added_ticker in current:
                conflicts.append(
                    {
                        "ticker": event.added_ticker,
                        "effective_date": event.effective_date.isoformat(),
                        "status": "resolved_identity_alias",
                    }
                )
            else:
                current.add(event.added_ticker)
    return current, conflicts


def resolve_membership_conflict(
    *,
    seed_present: bool,
    wikimedia_present: bool,
    official_announcement: str | None,
    identity_alias: bool = False,
) -> str:
    if identity_alias:
        return "resolved_identity_alias"
    if official_announcement == "seed":
        return "resolved_official_announcement_authoritative"
    if official_announcement == "wikimedia":
        return "resolved_official_announcement_authoritative"
    if seed_present == wikimedia_present:
        return "resolved_seed_correct"
    return (
        "unresolved_missing_evidence"
        if official_announcement is None
        else "unresolved_source_disagreement"
    )


def build_full_price_audit_requests(
    *,
    ticker_intervals: Iterable[TickerIdentityInterval],
    membership_bounds: Mapping[str, tuple[date, date]],
    endpoint: date,
    prior_calendar_days: int = 370,
) -> list[PriceAuditRequest]:
    requests = []
    for interval in ticker_intervals:
        bounds = membership_bounds.get(interval.security_id)
        if bounds is None:
            continue
        member_from, member_through = bounds
        ticker_from = max(member_from, interval.valid_from)
        ticker_through = min(member_through, interval.valid_through or endpoint, endpoint)
        if ticker_from > ticker_through:
            continue
        requests.append(
            PriceAuditRequest(
                security_id=interval.security_id,
                provider_ticker=interval.ticker,
                membership_from=ticker_from,
                membership_through=ticker_through,
                request_from=ticker_from - timedelta(days=prior_calendar_days),
                request_through=ticker_through,
            )
        )
    return sorted(requests, key=lambda item: (item.security_id, item.membership_from))


def classify_price_result(
    *,
    identity_resolved: bool,
    provider_status: str,
    first_available: date | None,
    last_available: date | None,
    request: PriceAuditRequest,
    corporate_action_conflict: bool = False,
) -> str:
    if not identity_resolved:
        return "identity_mapping_unresolved"
    if corporate_action_conflict:
        return "corporate_action_conflict"
    if provider_status == "provider_unavailable":
        return "temporary_provider_failure"
    if first_available is None or last_available is None:
        return "possibly_delisted_no_history"
    if first_available > request.membership_from:
        return "missing_membership_interval_prices"
    if last_available < request.membership_through:
        return "stale_final_price"
    if (request.membership_from - first_available).days < 300:
        return "insufficient_prior_history"
    return "available"


def load_completed_price_audits(cache_root: Path) -> dict[str, dict[str, Any]]:
    if not cache_root.exists():
        return {}
    completed: dict[str, dict[str, Any]] = {}
    for path in cache_root.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        request_id = str(payload.get("request_id", ""))
        if request_id and payload.get("status") == "available":
            completed[request_id] = payload
    return completed


def classify_terminal_value(
    *,
    cash_value_verified: bool = False,
    stock_ratio_verified: bool = False,
    successor_verified: bool = False,
    final_price_verified: bool = False,
    bankruptcy_value_verified: bool = False,
    adjusted_terminal_return_available: bool = False,
    delisting_status_known: bool = False,
) -> str:
    checks = (
        (cash_value_verified, "cash_acquisition_value_verified"),
        (stock_ratio_verified, "stock_acquisition_ratio_verified"),
        (successor_verified, "successor_security_verified"),
        (bankruptcy_value_verified, "bankruptcy_or_liquidation_value_verified"),
        (adjusted_terminal_return_available, "provider_adjusted_terminal_return_available"),
        (final_price_verified, "final_traded_price_verified"),
        (delisting_status_known, "delisting_status_known_terminal_value_unknown"),
    )
    return next((status for condition, status in checks if condition), "unresolved_delisting")


def earliest_qualified_interval(
    monthly_results: Iterable[tuple[date, bool, tuple[str, ...]]],
    *,
    endpoint: date,
    minimum_months: int = 156,
) -> tuple[tuple[date, date] | None, list[dict[str, Any]]]:
    ordered = sorted(item for item in monthly_results if item[0] <= endpoint)
    audit: list[dict[str, Any]] = []
    for index, (start, _, _) in enumerate(ordered):
        suffix = ordered[index:]
        contiguous = []
        for item in suffix:
            if not item[1]:
                break
            contiguous.append(item)
        passed = len(contiguous) >= minimum_months
        audit.append(
            {
                "candidate_start": start.isoformat(),
                "qualified_months": len(contiguous),
                "status": "passed" if passed else "failed",
                "reason": (
                    "minimum_156_months_satisfied"
                    if passed
                    else (
                        contiguous[-1][2][0]
                        if contiguous and contiguous[-1][2]
                        else "insufficient_contiguous_qualified_months"
                    )
                ),
            }
        )
        if passed:
            return (start, contiguous[-1][0]), audit
    return None, audit


def write_free_data_limit_document(
    *,
    path: Path,
    resolved: list[str],
    unavailable: list[str],
    earliest_partial_interval: str | None,
) -> Path:
    text = [
        "# Free Data Limit Reached",
        "",
        "The strict canonical point-in-time universe remains blocked after the final free-source "
        "remediation.",
        "",
        "## Resolved",
        *[f"- {item}" for item in resolved],
        "",
        "## Unavailable",
        *[f"- {item}" for item in unavailable],
        "",
        f"Earliest partially covered interval: {earliest_partial_interval or 'none established'}.",
        "",
        "A separately preregistered noncanonical research universe may be possible, but it must "
        "not be represented as canonical S&P 500 point-in-time evidence.",
        "",
        "Institutional or appropriately licensed historical constituent, delisting, and terminal-"
        "value data would be required for a canonical claim. Model training remains prohibited.",
        "",
    ]
    path.write_text("\n".join(text), encoding="utf-8")
    return path


def membership_events_from_extensions(
    extensions: Iterable[MembershipExtensionEvent],
    security_id_for_ticker: Mapping[str, str],
    *,
    source_id: str,
) -> list[MembershipEvent]:
    events: list[MembershipEvent] = []
    for row in extensions:
        announced = (
            datetime.fromisoformat(row.announcement_timestamp)
            if row.announcement_timestamp
            else None
        )
        for ticker, action in (
            (row.removed_ticker, MembershipAction.REMOVE),
            (row.added_ticker, MembershipAction.ADD),
        ):
            if not ticker or ticker not in security_id_for_ticker:
                continue
            source_event_id = f"{row.effective_date}|{action.value}|{ticker}"
            events.append(
                MembershipEvent(
                    event_id=sha256_json({"source": source_id, "event": source_event_id})[:24],
                    security_id=security_id_for_ticker[ticker],
                    ticker=ticker,
                    action=action,
                    effective_date=row.effective_date,
                    announced_at=announced,
                    source_id=source_id,
                    source_event_id=source_event_id,
                )
            )
    return events
