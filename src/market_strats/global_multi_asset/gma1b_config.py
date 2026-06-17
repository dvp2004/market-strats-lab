"""GMA-1B macro/cash foundation configuration loader."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

GMA1B_TRACK_ID = "gma_alpha"
GMA1B_PHASE_ID = "gma1b_macro_cash_foundation"

TOP_LEVEL_KEYS = {
    "track",
    "provider",
    "point_in_time",
    "cash",
    "quality",
    "paths",
    "series",
}
TRACK_KEYS = {
    "track_id",
    "phase_id",
    "paper_only",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
}
PROVIDER_KEYS = {
    "primary_provider",
    "vintage_provider",
    "api_key_environment_variable",
    "timeout_seconds",
    "retry_count",
    "immutable_snapshots",
    "prohibit_unofficial_fallback",
}
PIT_KEYS = {
    "require_realtime_periods",
    "require_availability_timestamp",
    "conservative_missing_release_time_policy",
    "future_revision_policy",
    "unknown_publication_time_policy",
    "asof_query_policy",
}
CASH_KEYS = {
    "authoritative_series",
    "source_yield_convention",
    "annualisation_day_count",
    "accrual_calendar",
    "weekend_accrual_policy",
    "publication_lag_policy",
    "missing_rate_policy",
    "negative_rate_policy",
    "bil_role",
}
QUALITY_KEYS = {
    "required_series",
    "optional_series",
    "maximum_staleness_days",
    "maximum_missing_interior_observations",
    "require_series_metadata",
    "require_vintage_integrity",
    "require_hash_validation",
    "revision_materiality_tolerance",
}
PATH_KEYS = {
    "raw_root",
    "manifest_root",
    "canonical_root",
    "report_root",
    "state_root",
}
SERIES_KEYS = {
    "macro_id",
    "provider",
    "series_id",
    "display_name",
    "economic_role",
    "frequency",
    "units",
    "seasonal_adjustment",
    "native_observation_calendar",
    "expected_publication_frequency",
    "is_required",
    "is_vintage_aware",
    "revision_prone",
    "availability_timestamp_policy",
    "maximum_staleness_days",
    "transformation_policy",
    "notes",
}

APPROVED_PATH_PREFIXES = (
    Path("data/global_multi_asset_alpha/macro_raw"),
    Path("data/global_multi_asset_alpha/macro_manifests"),
    Path("data/global_multi_asset_alpha/canonical_macro"),
    Path("reports/global_multi_asset_alpha/macro_foundation"),
    Path("state/global_multi_asset_alpha"),
)


@dataclass(frozen=True)
class GMA1BConfig:
    path: Path
    raw: dict[str, Any]
    track: dict[str, Any]
    provider: dict[str, Any]
    point_in_time: dict[str, Any]
    cash: dict[str, Any]
    quality: dict[str, Any]
    paths: dict[str, Path]
    series: list[dict[str, Any]]


def _unknown_keys(section: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ValueError(f"Unknown keys in {name}: {unknown}")


def _must_be_false(section: dict[str, Any], key: str) -> None:
    if bool(section.get(key, True)):
        raise ValueError(f"{key} must be false for GMA-1B")


def is_approved_gma1b_output_path(path: str | Path) -> bool:
    candidate = Path(path)
    return any(candidate == prefix or prefix in candidate.parents for prefix in APPROVED_PATH_PREFIXES)


def validate_gma1b_config(raw: dict[str, Any], *, path: Path | None = None) -> GMA1BConfig:
    _unknown_keys(raw, TOP_LEVEL_KEYS, "config")
    missing_top = sorted(TOP_LEVEL_KEYS - set(raw))
    if missing_top:
        raise ValueError(f"Missing top-level config sections: {missing_top}")

    track = raw["track"] or {}
    provider = raw["provider"] or {}
    point_in_time = raw["point_in_time"] or {}
    cash = raw["cash"] or {}
    quality = raw["quality"] or {}
    paths_raw = raw["paths"] or {}
    series = raw["series"] or []

    _unknown_keys(track, TRACK_KEYS, "track")
    _unknown_keys(provider, PROVIDER_KEYS, "provider")
    _unknown_keys(point_in_time, PIT_KEYS, "point_in_time")
    _unknown_keys(cash, CASH_KEYS, "cash")
    _unknown_keys(quality, QUALITY_KEYS, "quality")
    _unknown_keys(paths_raw, PATH_KEYS, "paths")
    for item in series:
        _unknown_keys(item, SERIES_KEYS, f"series[{item.get('macro_id', '?')}]")

    if track.get("track_id") != GMA1B_TRACK_ID:
        raise ValueError(f"track.track_id must be {GMA1B_TRACK_ID!r}")
    if track.get("phase_id") != GMA1B_PHASE_ID:
        raise ValueError(f"track.phase_id must be {GMA1B_PHASE_ID!r}")
    if not bool(track.get("paper_only", False)):
        raise ValueError("track.paper_only must be true")
    _must_be_false(track, "live_trading_allowed")
    _must_be_false(track, "real_money_allowed")
    _must_be_false(track, "broker_api_integration_allowed")

    if provider.get("primary_provider") != "fred":
        raise ValueError("provider.primary_provider must be 'fred'")
    if provider.get("vintage_provider") != "alfred":
        raise ValueError("provider.vintage_provider must be 'alfred'")
    if not bool(provider.get("prohibit_unofficial_fallback", False)):
        raise ValueError("provider.prohibit_unofficial_fallback must be true")
    if cash.get("bil_role") == "authoritative_cash_source":
        raise ValueError("BIL must not be authoritative cash")
    if cash.get("authoritative_series") != "DGS3MO":
        raise ValueError("cash.authoritative_series must be DGS3MO")

    macro_ids = [str(item["macro_id"]) for item in series]
    series_ids = [str(item["series_id"]) for item in series]
    if len(macro_ids) != len(set(macro_ids)):
        raise ValueError("series macro_id values must be unique")
    if len(series_ids) != len(set(series_ids)):
        raise ValueError("series_id values must be unique")
    required = set(quality.get("required_series", []))
    missing_required = sorted(required - set(macro_ids))
    if missing_required:
        raise ValueError(f"quality.required_series missing from series: {missing_required}")
    if any(item.get("provider") != "fred" for item in series):
        raise ValueError("All configured macro series must use official FRED provider")

    paths = {key: Path(value) for key, value in paths_raw.items()}
    for key, value in paths.items():
        if not is_approved_gma1b_output_path(value):
            raise ValueError(f"paths.{key} is outside approved GMA-1B paths: {value}")

    return GMA1BConfig(
        path=path or Path(""),
        raw=raw,
        track=track,
        provider=provider,
        point_in_time=point_in_time,
        cash=cash,
        quality=quality,
        paths=paths,
        series=series,
    )


def load_gma1b_config(path: str | Path) -> GMA1BConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("GMA-1B config must be a mapping")
    return validate_gma1b_config(raw, path=config_path)
