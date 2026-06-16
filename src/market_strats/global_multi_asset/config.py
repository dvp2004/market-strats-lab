from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from market_strats.global_multi_asset.identifiers import validate_track_identifiers
from market_strats.global_multi_asset.universe import (
    PROPOSED_INSTRUMENTS,
    default_instrument_registry,
    validate_registry,
)

TOP_LEVEL_KEYS = {
    "track",
    "paths",
    "provider",
    "audit",
    "replay_start",
    "instruments",
}
TRACK_KEYS = {
    "track_id",
    "phase_id",
    "paper_only",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
}
PATH_KEYS = {
    "raw_root",
    "processed_root",
    "manifest_root",
    "report_root",
    "cache_root",
}
PROVIDER_KEYS = {
    "name",
    "fetch_enabled",
    "immutable_snapshots",
    "auto_adjust",
    "timeout_seconds",
}
AUDIT_KEYS = {
    "expected_price_columns",
    "minimum_history_observations",
    "momentum_warmup_months",
    "require_raw_open",
    "require_adjusted_close",
    "require_volume",
    "stale_price_threshold_days",
    "zero_volume_threshold_days",
    "hash_algorithm",
}
REPLAY_KEYS = {
    "required_core_instruments",
    "minimum_warmup_months",
    "provisional_first_signal_rule",
    "provisional_execution_rule",
    "benchmark_exemptions",
    "draft_governance_notes",
}

APPROVED_PATH_PREFIXES = (
    Path("data/global_multi_asset_alpha"),
    Path("reports/global_multi_asset_alpha/feasibility"),
)


@dataclass(frozen=True)
class GMAConfig:
    path: Path
    raw: dict[str, Any]
    track: dict[str, Any]
    paths: dict[str, Path]
    provider: dict[str, Any]
    audit: dict[str, Any]
    replay_start: dict[str, Any]
    instruments: dict[str, dict[str, Any]]


def _unknown_keys(section: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ValueError(f"Unknown keys in {name}: {unknown}")


def _must_be_false(section: dict[str, Any], key: str) -> None:
    if bool(section.get(key, True)):
        raise ValueError(f"{key} must be false for GMA-0")


def _as_project_path(value: str | Path) -> Path:
    return Path(value)


def _is_inside(path: Path, prefix: Path) -> bool:
    try:
        path.resolve().relative_to(prefix.resolve())
        return True
    except ValueError:
        return False


def _validate_paths(paths: dict[str, Path]) -> None:
    raw_root = paths["raw_root"]
    processed_root = paths["processed_root"]
    manifest_root = paths["manifest_root"]
    cache_root = paths["cache_root"]
    report_root = paths["report_root"]
    data_root = Path("data/global_multi_asset_alpha")
    report_prefix = Path("reports/global_multi_asset_alpha/feasibility")
    for key, path in [
        ("raw_root", raw_root),
        ("processed_root", processed_root),
        ("manifest_root", manifest_root),
        ("cache_root", cache_root),
    ]:
        if not _is_inside(path, data_root):
            raise ValueError(f"paths.{key} must stay under {data_root}")
    if not _is_inside(report_root, report_prefix):
        raise ValueError(f"paths.report_root must stay under {report_prefix}")


def validate_config(raw: dict[str, Any], *, path: Path | None = None) -> GMAConfig:
    _unknown_keys(raw, TOP_LEVEL_KEYS, "config")
    missing_top = sorted(TOP_LEVEL_KEYS - set(raw))
    if missing_top:
        raise ValueError(f"Missing top-level config sections: {missing_top}")

    track = raw["track"] or {}
    paths_raw = raw["paths"] or {}
    provider = raw["provider"] or {}
    audit = raw["audit"] or {}
    replay_start = raw["replay_start"] or {}
    instruments = raw["instruments"] or {}

    _unknown_keys(track, TRACK_KEYS, "track")
    _unknown_keys(paths_raw, PATH_KEYS, "paths")
    _unknown_keys(provider, PROVIDER_KEYS, "provider")
    _unknown_keys(audit, AUDIT_KEYS, "audit")
    _unknown_keys(replay_start, REPLAY_KEYS, "replay_start")

    validate_track_identifiers(
        str(track.get("track_id", "")),
        str(track.get("phase_id", "")),
    )
    if not bool(track.get("paper_only", False)):
        raise ValueError("track.paper_only must be true")
    _must_be_false(track, "live_trading_allowed")
    _must_be_false(track, "real_money_allowed")
    _must_be_false(track, "broker_api_integration_allowed")

    if provider.get("name") != "yahoo_yfinance":
        raise ValueError("provider.name must be yahoo_yfinance for GMA-0")
    if bool(provider.get("auto_adjust", True)):
        raise ValueError("provider.auto_adjust must be false")
    if not bool(provider.get("immutable_snapshots", False)):
        raise ValueError("provider.immutable_snapshots must be true")

    if audit.get("hash_algorithm") != "sha256":
        raise ValueError("audit.hash_algorithm must be sha256")
    expected_columns = list(audit.get("expected_price_columns", []))
    required_columns = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    if expected_columns != required_columns:
        raise ValueError(f"audit.expected_price_columns must be {required_columns}")

    default_registry = default_instrument_registry()
    unknown_instruments = sorted(set(instruments) - set(default_registry))
    if unknown_instruments:
        raise ValueError(f"Unknown GMA instruments: {unknown_instruments}")
    registry = {}
    for instrument_id in PROPOSED_INSTRUMENTS:
        registry[instrument_id] = {**default_registry[instrument_id], **instruments.get(instrument_id, {})}
    validate_registry(registry)

    required_core = list(replay_start.get("required_core_instruments", []))
    if not required_core:
        raise ValueError("replay_start.required_core_instruments must not be empty")
    missing_core = sorted(set(required_core) - set(registry))
    if missing_core:
        raise ValueError(f"Unknown required core instruments: {missing_core}")
    benchmark_core = [
        instrument_id
        for instrument_id in required_core
        if bool(registry[instrument_id].get("is_benchmark_only", False))
    ]
    if benchmark_core:
        raise ValueError(f"Benchmark-only instruments cannot be required core: {benchmark_core}")

    resolved_paths = {key: _as_project_path(value) for key, value in paths_raw.items()}
    missing_paths = sorted(PATH_KEYS - set(resolved_paths))
    if missing_paths:
        raise ValueError(f"Missing paths: {missing_paths}")
    _validate_paths(resolved_paths)

    return GMAConfig(
        path=path or Path(""),
        raw=raw,
        track=track,
        paths=resolved_paths,
        provider=provider,
        audit=audit,
        replay_start=replay_start,
        instruments=registry,
    )


def load_config(path: str | Path) -> GMAConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("GMA config must be a mapping")
    return validate_config(raw, path=config_path)
