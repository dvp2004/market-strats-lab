"""GMA-1A market-data-foundation configuration loader and validator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from market_strats.global_multi_asset.identifiers import FORBIDDEN_PHASE_PREFIXES

GMA1A_TRACK_ID = "gma_alpha"
GMA1A_PHASE_ID = "gma1a_market_data_foundation"

TOP_LEVEL_KEYS = {
    "track",
    "source_selection",
    "price_basis",
    "calendars",
    "cash",
    "quality",
    "paths",
}
TRACK_KEYS = {
    "track_id",
    "phase_id",
    "paper_only",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
}
SOURCE_SELECTION_KEYS = {
    "gma0_manifest_root",
    "gma0_report_root",
    "selection_policy",
    "require_live_yahoo_audit",
    "require_completed_history",
    "require_valid_hashes",
    "prohibit_mutable_latest_files",
    "require_provider_symbol_match",
    "require_registry_match",
}
PRICE_BASIS_KEYS = {
    "execution_price_basis",
    "execution_validation_basis",
    "signal_total_return_basis",
    "adjusted_close_role",
    "dividend_accounting",
    "split_accounting",
    "raw_price_split_basis_policy",
    "missing_action_policy",
}
CALENDAR_KEYS = {
    "etf_calendar",
    "bitcoin_calendar",
    "decision_timezone",
    "valuation_timezone",
    "incomplete_observation_policy",
}
CASH_KEYS = {
    "authoritative_source_type",
    "bil_role",
    "missing_rate_policy",
    "future_rate_phase",
}
QUALITY_KEYS = {
    "required_core_instruments",
    "maximum_missing_interior_rows",
    "maximum_duplicate_rows",
    "adjusted_close_reconciliation_tolerance_bps",
    "material_return_difference_tolerance_bps",
    "require_raw_open",
    "require_raw_ohlc",
    "require_adjusted_close",
    "require_volume",
    "require_action_capability",
    "required_core_failure_policy",
}
PATH_KEYS = {
    "canonical_bundle_root",
    "report_root",
    "state_root",
}

APPROVED_PATH_PREFIXES = (
    Path("src/market_strats/global_multi_asset"),
    Path("configs/global_multi_asset_alpha"),
    Path("tests/global_multi_asset"),
    Path("data/global_multi_asset_alpha"),
    Path("reports/global_multi_asset_alpha"),
    Path("state/global_multi_asset_alpha"),
)


@dataclass(frozen=True)
class GMA1AConfig:
    path: Path
    raw: dict[str, Any]
    track: dict[str, Any]
    source_selection: dict[str, Any]
    price_basis: dict[str, Any]
    calendars: dict[str, Any]
    cash: dict[str, Any]
    quality: dict[str, Any]
    paths: dict[str, Path]


def _unknown_keys(section: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ValueError(f"Unknown keys in {name}: {unknown}")


def _must_be_false(section: dict[str, Any], key: str) -> None:
    if bool(section.get(key, True)):
        raise ValueError(f"{key} must be false for GMA-1A")


def validate_gma1a_config(
    raw: dict[str, Any], *, path: Path | None = None
) -> GMA1AConfig:
    _unknown_keys(raw, TOP_LEVEL_KEYS, "config")
    missing_top = sorted(TOP_LEVEL_KEYS - set(raw))
    if missing_top:
        raise ValueError(f"Missing top-level config sections: {missing_top}")

    track = raw["track"] or {}
    source_selection = raw["source_selection"] or {}
    price_basis = raw["price_basis"] or {}
    calendars = raw["calendars"] or {}
    cash = raw["cash"] or {}
    quality = raw["quality"] or {}
    paths_raw = raw["paths"] or {}

    _unknown_keys(track, TRACK_KEYS, "track")
    _unknown_keys(source_selection, SOURCE_SELECTION_KEYS, "source_selection")
    _unknown_keys(price_basis, PRICE_BASIS_KEYS, "price_basis")
    _unknown_keys(calendars, CALENDAR_KEYS, "calendars")
    _unknown_keys(cash, CASH_KEYS, "cash")
    _unknown_keys(quality, QUALITY_KEYS, "quality")
    _unknown_keys(paths_raw, PATH_KEYS, "paths")

    if track.get("track_id") != GMA1A_TRACK_ID:
        raise ValueError(f"track.track_id must be {GMA1A_TRACK_ID!r}")
    if track.get("phase_id") != GMA1A_PHASE_ID:
        raise ValueError(f"track.phase_id must be {GMA1A_PHASE_ID!r}")

    for identifier in (str(track.get("track_id", "")), str(track.get("phase_id", ""))):
        if identifier.lower().startswith(FORBIDDEN_PHASE_PREFIXES):
            raise ValueError("GMA identifiers must not use frozen phase prefixes")

    if not bool(track.get("paper_only", False)):
        raise ValueError("track.paper_only must be true")
    _must_be_false(track, "live_trading_allowed")
    _must_be_false(track, "real_money_allowed")
    _must_be_false(track, "broker_api_integration_allowed")

    if cash.get("bil_role") == "authoritative_cash_source":
        raise ValueError("BIL must not be used as authoritative cash source")

    required_core = list(quality.get("required_core_instruments", []))
    if not required_core:
        raise ValueError("quality.required_core_instruments must not be empty")

    resolved_paths = {key: Path(value) for key, value in paths_raw.items()}

    return GMA1AConfig(
        path=path or Path(""),
        raw=raw,
        track=track,
        source_selection=source_selection,
        price_basis=price_basis,
        calendars=calendars,
        cash=cash,
        quality=quality,
        paths=resolved_paths,
    )


def load_gma1a_config(path: str | Path) -> GMA1AConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("GMA-1A config must be a mapping")
    return validate_gma1a_config(raw, path=config_path)


def is_approved_gma_path(path: str) -> bool:
    candidate = Path(path)
    return any(
        candidate == prefix or prefix in candidate.parents
        for prefix in APPROVED_PATH_PREFIXES
    )
