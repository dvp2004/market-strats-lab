"""Source-neutral records and frozen-contract validation for stock universes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

ALLOWED_COST_CLASSIFICATIONS = {
    "free_open_licence",
    "free_public_official",
    "free_personal_research_access",
}
REJECTED_COST_CLASSIFICATIONS = {
    "paid",
    "trial_requiring_payment",
    "commercial_subscription",
    "unknown_cost",
}


class UniverseContractError(ValueError):
    """Raised when a frozen universe contract fails closed."""


class IdentityResolutionError(UniverseContractError):
    """Raised when a ticker cannot be resolved to one security identity."""


class QualificationVerdict(StrEnum):
    QUALIFIED = "qualified_for_model_research"
    SOURCE_COVERAGE = "blocked_free_source_coverage_failure"
    IDENTITY = "blocked_identity_reconciliation_failure"
    MEMBERSHIP = "blocked_membership_reconciliation_failure"
    PRICE_OR_DELISTING = "blocked_price_or_delisting_failure"
    SOURCE_TERMS = "blocked_source_terms_failure"


class MembershipAction(StrEnum):
    ADD = "addition"
    REMOVE = "removal"


class ExclusionReason(StrEnum):
    NOT_MEMBER = "not_active_member"
    UNRESOLVED_IDENTITY = "unresolved_security_identity"
    UNRESOLVED_MEMBERSHIP = "unresolved_membership_conflict"
    MISSING_PRICE = "missing_decision_price"
    STALE_PRICE = "stale_decision_price"
    INSUFFICIENT_HISTORY = "insufficient_252_session_history"
    PRICE_THRESHOLD = "below_minimum_decision_close"
    LIQUIDITY_THRESHOLD = "below_minimum_median_dollar_volume"
    DELISTING_UNRESOLVED = "missing_delisting_outcome"


@dataclass(frozen=True)
class SourceRegistryEntry:
    source_id: str
    source_name: str
    source_type: str
    source_url_or_repository: str
    source_revision_or_commit: str
    retrieved_at_utc: str
    content_sha256: str
    licence_or_terms_classification: str
    cost_classification: str
    authentication_required: bool
    permitted_local_use: str
    redistribution_status: str
    known_limitations: tuple[str, ...]
    point_in_time_status: str
    canonical_status: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SecurityIdentity:
    security_id: str
    issuer_name: str
    cik: str | None
    share_class: str | None
    identity_status: str
    source_id: str
    predecessor_security_id: str | None = None
    successor_security_id: str | None = None


@dataclass(frozen=True)
class TickerIdentityInterval:
    security_id: str
    ticker: str
    exchange: str | None
    valid_from: date
    valid_through: date | None
    source_id: str


@dataclass(frozen=True)
class MembershipEvent:
    event_id: str
    security_id: str
    ticker: str
    action: MembershipAction
    effective_date: date
    announced_at: datetime | None
    source_id: str
    source_event_id: str


@dataclass(frozen=True)
class MembershipInterval:
    security_id: str
    ticker_at_addition: str
    effective_from: date
    effective_through: date | None
    source_id: str
    addition_event_id: str
    removal_event_id: str | None


@dataclass(frozen=True)
class CorporateActionEvent:
    event_id: str
    security_id: str
    provider_ticker: str
    action_type: str
    effective_date: date
    value: float | str | None
    source_id: str
    snapshot_sha256: str


@dataclass(frozen=True)
class EligibilityResult:
    decision_date: date
    execution_date: date
    security_id: str
    eligible: bool
    reason_codes: tuple[str, ...]
    history_sessions: int
    decision_close_usd: float | None
    median_dollar_volume_usd: float | None


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise UniverseContractError(f"Required YAML file is missing: {path.name}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise UniverseContractError(f"Expected a YAML mapping: {path.name}")
    return payload


def require_explicit_root(root: Path | None, label: str) -> Path:
    if root is None:
        raise UniverseContractError(f"{label} must be supplied explicitly")
    if not root.is_absolute():
        raise UniverseContractError(f"{label} must be an absolute path supplied explicitly")
    return root.resolve()


def require_safe_relative_path(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise UniverseContractError(f"{label} must be a safe relative path")
    return path


def load_source_registry(path: Path) -> tuple[dict[str, Any], dict[str, SourceRegistryEntry]]:
    payload = load_yaml_mapping(path)
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise UniverseContractError("Source registry must contain a non-empty sources list")
    entries: dict[str, SourceRegistryEntry] = {}
    required = {
        "source_id",
        "source_name",
        "source_type",
        "source_url_or_repository",
        "source_revision_or_commit",
        "retrieved_at_utc",
        "content_sha256",
        "licence_or_terms_classification",
        "cost_classification",
        "authentication_required",
        "permitted_local_use",
        "redistribution_status",
        "known_limitations",
        "point_in_time_status",
        "canonical_status",
    }
    for raw in sources:
        if not isinstance(raw, dict):
            raise UniverseContractError("Each source-registry row must be a mapping")
        missing = sorted(required - raw.keys())
        if missing:
            raise UniverseContractError(f"Source registry row missing fields: {', '.join(missing)}")
        cost = str(raw["cost_classification"])
        if cost not in ALLOWED_COST_CLASSIFICATIONS:
            raise UniverseContractError(f"Rejected source cost classification: {cost}")
        source_id = str(raw["source_id"])
        if source_id in entries:
            raise UniverseContractError(f"Duplicate source_id: {source_id}")
        metadata = {key: value for key, value in raw.items() if key not in required}
        entries[source_id] = SourceRegistryEntry(
            source_id=source_id,
            source_name=str(raw["source_name"]),
            source_type=str(raw["source_type"]),
            source_url_or_repository=str(raw["source_url_or_repository"]),
            source_revision_or_commit=str(raw["source_revision_or_commit"]),
            retrieved_at_utc=str(raw["retrieved_at_utc"]),
            content_sha256=str(raw["content_sha256"]).lower(),
            licence_or_terms_classification=str(raw["licence_or_terms_classification"]),
            cost_classification=cost,
            authentication_required=bool(raw["authentication_required"]),
            permitted_local_use=str(raw["permitted_local_use"]),
            redistribution_status=str(raw["redistribution_status"]),
            known_limitations=tuple(str(item) for item in raw["known_limitations"]),
            point_in_time_status=str(raw["point_in_time_status"]),
            canonical_status=str(raw["canonical_status"]),
            metadata=metadata,
        )
    return payload, entries


def load_universe_contract(path: Path) -> dict[str, Any]:
    contract = load_yaml_mapping(path)
    required_values = {
        "index_reference": "S&P 500",
        "decision_cadence": "monthly",
        "same_close_execution": "prohibited",
        "current_survivor_filtering": "prohibited",
        "missing_price_imputation": "prohibited",
        "missing_delisting_return_as_zero": "prohibited",
        "model_training_authorized": False,
    }
    for key, expected in required_values.items():
        if contract.get(key) != expected:
            raise UniverseContractError(f"{key} must remain frozen as {expected!r}")
    if int(contract.get("minimum_price_history_sessions", 0)) < 252:
        raise UniverseContractError("minimum_price_history_sessions cannot be below 252")
    segments = contract.get("evaluation_segment_minimum_monthly_decisions", {})
    for name, minimum in {
        "training": 60,
        "walk_forward_validation": 60,
        "untouched_holdout": 36,
        "prospective_shadow_after_authorization": 12,
    }.items():
        if int(segments.get(name, 0)) < minimum:
            raise UniverseContractError(f"{name} minimum cannot be shortened")
    return contract
