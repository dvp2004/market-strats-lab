"""Availability timestamp and decision-panel eligibility logic."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

SUPPORTED_EVIDENCE_LEVELS = {
    "provider_timestamp_verified",
    "release_calendar_verified",
    "contractual_assumption",
    "unverified",
}


def parse_session_close_rule(rule: str) -> tuple[time, ZoneInfo]:
    parts = rule.strip().split()
    if len(parts) != 2:
        raise ValueError(f"Expected '<HH:MM> <Timezone>' availability rule, got {rule!r}")
    hour_text, timezone_name = parts
    hour, minute = hour_text.split(":", maxsplit=1)
    return time(int(hour), int(minute)), ZoneInfo(timezone_name)


def session_cutoff_to_utc(session_date: date, rule: str) -> datetime:
    cutoff_time, cutoff_zone = parse_session_close_rule(rule)
    local_dt = datetime.combine(session_date, cutoff_time, tzinfo=cutoff_zone)
    return local_dt.astimezone(UTC)


def is_decision_panel_eligible(
    *,
    evidence_level: str,
    available_at_utc: datetime,
    decision_timestamp_utc: datetime,
    allowed_evidence_levels: set[str],
    contractual_assumption_approved: bool,
) -> tuple[bool, str]:
    if evidence_level not in SUPPORTED_EVIDENCE_LEVELS:
        return False, f"unsupported evidence level: {evidence_level}"
    if evidence_level == "unverified":
        return False, "unverified availability evidence is never decision-panel eligible"
    if evidence_level not in allowed_evidence_levels:
        return False, f"evidence level not allowed by MI-2 registry: {evidence_level}"
    if evidence_level == "contractual_assumption" and not contractual_assumption_approved:
        return False, "contractual assumption is not explicitly approved"
    if available_at_utc > decision_timestamp_utc:
        return False, "available_at_utc is after the decision timestamp"
    return True, ""
