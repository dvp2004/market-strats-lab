"""Dataclasses for MI-1 market-data records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class InstrumentRegistryEntry:
    instrument_id: str
    symbol: str
    asset_class: str
    currency: str
    exchange_calendar: str
    source_symbol: str
    eligible_from: date
    active: bool
    registry_version: int
    role: str


@dataclass(frozen=True)
class RawSnapshotManifest:
    snapshot_id: str
    source_name: str
    dataset_name: str
    request_parameters: dict[str, Any]
    retrieved_at_utc: datetime
    content_sha256: str
    parser_version: str
    raw_path: str
    publication_permission: str
    availability_evidence_level: str


@dataclass(frozen=True)
class MarketEodBar:
    instrument_id: str
    session_date: date
    open_raw: float
    high_raw: float
    low_raw: float
    close_raw: float
    volume_raw: int
    vendor_adjusted_close: float | None
    adjustment_basis: str
    available_at_utc: datetime
    availability_evidence_level: str
    availability_rule_id: str
    retrieved_at_utc: datetime
    snapshot_id: str


@dataclass(frozen=True)
class CorporateActionEvent:
    event_id: str
    instrument_id: str
    session_date: date
    action_type: str
    value: float
    source_name: str
    available_at_utc: datetime
    availability_evidence_level: str
    availability_rule_id: str
    retrieved_at_utc: datetime
    snapshot_id: str


@dataclass(frozen=True)
class CoverageAuditRow:
    run_id: str
    instrument_id: str
    first_observed_session: date | None
    last_observed_session: date | None
    eligible_sessions: int
    missing_sessions: int
    coverage_ratio: float
    continuous_history_sessions: int
    start_date_eligible: bool
    notes: str


@dataclass(frozen=True)
class AvailabilityAuditRow:
    decision_timestamp_utc: datetime
    dataset_row_id: str
    available_at_utc: datetime
    availability_evidence_level: str
    eligible: bool
    failure_reason: str


@dataclass(frozen=True)
class DataQualityEvent:
    run_id: str
    severity: str
    event_type: str
    instrument_id: str | None
    session_date: date | None
    message: str
    source: str
