"""GMA-8B deterministic immutable 29-series provenance and availability audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

CONTRACT_ID = "gma8b_historical_data_provenance_contract_v1"
GRID_HASH = "513139855cb34a67f735170683dd548724574001d43b7e3c4e29c32ecead5f6a"
SNAPSHOT_MANIFEST_HASH = "e767cb622bfe41240a8a4536920f79def3d267092b1bd0dcb2e6a06865ecdc6a"
BUNDLE_MANIFEST_HASH = "b93bd9800ddfffa19f12100c4538a4668ae61c20b7e322fec8df9441f63a166b"
NORMALISED_BUNDLE_HASH = "3d3d920e9bafa430fb313fe0f494954826a73f8962a15eb8709d02f2bae14bb6"
ADJUSTED_PRICE_INTERPRETATION = (
    "historical_total_return_adjusted_price_evidence_under_inherited_convention"
)
SOURCE_KIND = "per_ticker_normalised_series_from_immutable_snapshot"
CORE_ARM_ID = "gma8_core_22_etf_v1"
EXPANDED_ARM_ID = "gma8_expanded_29_etp_v1"
CORE_22 = [
    "SPY",
    "QQQ",
    "IWM",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
    "EFA",
    "EEM",
    "BIL",
    "IEF",
    "TLT",
    "AGG",
    "LQD",
    "HYG",
    "GLD",
    "DBC",
]
EXPANDED_29 = [*CORE_22, "VNQ", "TIP", "USO", "DBA", "SLV", "EWG", "EWJ"]
DATE_FIELD = "date"
ADJUSTED_PRICE_FIELD = "adj_close"
EXACT_COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume"]
BUNDLE_CONFIG_RELATIVE_PATH = (
    "configs/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1.yaml"
)
BUNDLE_MANIFEST_RELATIVE_PATH = (
    "reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1/"
    "gma6b_data_bundle_manifest_v1.json"
)
OUTPUT_FILENAMES = [
    "gma8b_parent_data_reference_resolution_v1.json",
    "gma8b_adjusted_price_input_contract_v1.csv",
    "gma8b_universe_asset_availability_v1.csv",
    "gma8b_arm_coverage_summary_v1.csv",
    "gma8b_data_quality_audit_v1.csv",
    "gma8b_data_provenance_summary_v1.md",
    "gma8b_data_manifest_v1.json",
    "gma8b_data_lock_v1.json",
    "gma8b_execution_manifest_v1.json",
]
FALSE_OPERATION_FIELDS = [
    "data_download_performed",
    "indicator_calculation_performed",
    "model_fit_performed",
    "backtest_performed",
    "strategy_ranking_performed",
    "portfolio_target_generated",
    "paper_broker_or_live_path_created",
]


class GMA8BError(RuntimeError):
    """Base error for a failed GMA-8B audit."""


class GMA8BParentContractError(GMA8BError):
    """Raised when the frozen GMA-8A parent does not match."""


class GMA8BSourceResolutionError(GMA8BError):
    """Raised when deterministic hash-to-manifest resolution fails."""


class GMA8BDataQualityError(GMA8BError):
    """Raised when a resolved immutable normalized series is invalid."""


@dataclass(frozen=True)
class Settings:
    path: Path
    raw: dict[str, Any]
    worktree_root: Path
    parent_paths: dict[str, Path]
    snapshot_root: Path
    snapshot_manifest_path: Path
    inventory_path: Path


@dataclass(frozen=True)
class ResolvedSource:
    ticker: str
    snapshot_path: Path
    sha256: str
    relative_path: str
    source_path_provenance_only: str


@dataclass(frozen=True)
class Resolution:
    snapshot_manifest_sha256: str
    inventory_sha256: str
    bundle_config_path: Path
    bundle_config_sha256: str
    bundle_manifest_path: Path
    bundle_manifest_sha256: str
    sources: list[ResolvedSource]


@dataclass(frozen=True)
class AssetAvailability:
    ticker: str
    universe_arms: str
    immutable_snapshot_path: str
    normalised_series_sha256: str
    source_adjusted_price_field: str
    first_observed_session: str
    last_observed_session: str
    observed_session_count: int
    first_positive_finite_session: str
    last_positive_finite_session: str
    missing_value_count: int
    nonpositive_or_nonfinite_value_count: int
    duplicate_session_date_count: int
    first_253_session_eligible_date: str
    availability_status: str


@dataclass(frozen=True)
class AuditResult:
    settings: Settings
    gma8a_lock_sha256: str
    maximum_lookback: int
    required_sessions: int
    resolution: Resolution
    assets: list[AssetAvailability]
    arm_rows: list[dict[str, Any]]
    cross_arm_start: str
    source_first_session: str
    source_last_session: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GMA8BSourceResolutionError(f"required file is unavailable: {path}")
    value = (
        yaml.safe_load(path.read_text(encoding="utf-8"))
        if path.suffix.casefold() in {".yaml", ".yml"}
        else json.loads(path.read_text(encoding="utf-8"))
    )
    if not isinstance(value, dict):
        raise GMA8BSourceResolutionError(f"required mapping is malformed: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise GMA8BSourceResolutionError(f"required CSV is unavailable: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_settings(path: str | Path, worktree_root: str | Path = ".") -> Settings:
    contract_path = Path(path).resolve()
    raw = _read_mapping(contract_path)
    if (raw.get("contract") or {}).get("contract_id") != CONTRACT_ID:
        raise GMA8BParentContractError("GMA-8B contract_id mismatch")
    root = Path(worktree_root).resolve()
    parent = raw.get("gma8a_parent") or {}
    parent_fields = [
        "config_path",
        "universe_registry_path",
        "strategy_grid_registry_path",
        "lock_path",
        "execution_manifest_path",
    ]
    parent_paths = {
        field: (root / str(parent[field])).resolve() for field in parent_fields if parent.get(field)
    }
    if len(parent_paths) != len(parent_fields):
        raise GMA8BParentContractError("GMA-8A parent allowlist is incomplete")
    metadata = raw.get("frozen_metadata_roots") or {}
    return Settings(
        path=contract_path,
        raw=raw,
        worktree_root=root,
        parent_paths=parent_paths,
        snapshot_root=Path(str(metadata["immutable_snapshot_root"])).resolve(),
        snapshot_manifest_path=Path(str(metadata["snapshot_manifest_path"])).resolve(),
        inventory_path=Path(str(metadata["normalised_inventory_path"])).resolve(),
    )


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise GMA8BParentContractError(f"{label} mismatch: expected {expected!r}")


def validate_gma8a_parent(settings: Settings) -> tuple[str, int]:
    for label, path in settings.parent_paths.items():
        if not path.is_file():
            raise GMA8BParentContractError(f"missing allowlisted GMA-8A file: {label}")
    config = _read_mapping(settings.parent_paths["config_path"])
    grid = config.get("strategy_grid") or {}
    _require_equal(grid.get("exact_base_strategy_template_count"), 80, "base template count")
    _require_equal(grid.get("exact_arm_trial_count"), 160, "arm-trial count")
    _require_equal(grid.get("strategy_grid_hash"), GRID_HASH, "strategy-grid hash")
    lock_path = settings.parent_paths["lock_path"]
    lock_hash = _sha256(lock_path)
    _require_equal(
        lock_hash, settings.raw["gma8a_parent"]["expected_lock_sha256"], "GMA-8A lock hash"
    )
    lock = _read_mapping(lock_path)
    _require_equal(lock.get("exact_base_strategy_template_count"), 80, "locked template count")
    _require_equal(lock.get("exact_arm_trial_count"), 160, "locked arm-trial count")
    _require_equal(lock.get("strategy_grid_hash"), GRID_HASH, "locked strategy-grid hash")
    execution = _read_mapping(settings.parent_paths["execution_manifest_path"])
    for field in [
        "data_download_performed",
        "market_data_read",
        "backtest_performed",
        "strategy_ranking_performed",
    ]:
        _require_equal(execution.get(field), False, f"GMA-8A execution field {field}")
    universe_rows = _read_csv(settings.parent_paths["universe_registry_path"])
    core = [row["symbol"] for row in universe_rows if row["universe_arm"] == CORE_ARM_ID]
    expanded = [row["symbol"] for row in universe_rows if row["universe_arm"] == EXPANDED_ARM_ID]
    _require_equal(core, CORE_22, "Core-22 registry")
    _require_equal(expanded, EXPANDED_29, "Expanded-29 registry")
    grid_rows = _read_csv(settings.parent_paths["strategy_grid_registry_path"])
    _require_equal(len(grid_rows), 160, "strategy-grid registry rows")
    _require_equal(len({row["strategy_id"] for row in grid_rows}), 80, "base strategy IDs")
    lookbacks = [
        int(token)
        for row in grid_rows
        for token in row.get("lookback_sessions", "").split("|")
        if token.isdigit()
    ]
    if not lookbacks:
        raise GMA8BParentContractError("strategy-grid registry has no fixed lookbacks")
    maximum = max(lookbacks)
    _require_equal(maximum, 252, "maximum strategy lookback")
    return lock_hash, maximum


def _is_true(value: Any) -> bool:
    return str(value).strip().casefold() == "true"


def _confined_snapshot_path(raw_path: str, snapshot_root: Path) -> Path:
    path = Path(raw_path).resolve()
    if path == snapshot_root or snapshot_root not in path.parents:
        raise GMA8BSourceResolutionError(f"snapshot path is outside immutable root: {path}")
    if not path.is_file():
        raise GMA8BSourceResolutionError(f"resolved snapshot file is unavailable: {path}")
    return path


def _resolve_manifest_row(
    rows: list[dict[str, str]], relative_path: str, snapshot_root: Path
) -> tuple[dict[str, str], Path]:
    matches = [row for row in rows if row.get("relative_path") == relative_path]
    if len(matches) != 1:
        raise GMA8BSourceResolutionError(
            f"expected one snapshot-manifest row for {relative_path}; observed {len(matches)}"
        )
    row = matches[0]
    if not _is_true(row.get("hash_match")):
        raise GMA8BSourceResolutionError(f"snapshot hash_match is not true: {relative_path}")
    path = _confined_snapshot_path(row.get("snapshot_path", ""), snapshot_root)
    if _sha256(path) != row.get("snapshot_sha256"):
        raise GMA8BSourceResolutionError(f"snapshot SHA-256 mismatch: {relative_path}")
    return row, path


def resolve_sources(settings: Settings) -> Resolution:
    metadata = settings.raw.get("frozen_metadata_roots") or {}
    lineage = settings.raw.get("frozen_lineage") or {}
    if metadata.get("snapshot_manifest_sha256") != SNAPSHOT_MANIFEST_HASH:
        raise GMA8BSourceResolutionError("configured snapshot-manifest hash mismatch")
    if lineage != {
        "gma6_snapshot_manifest_hash": SNAPSHOT_MANIFEST_HASH,
        "gma6b_data_bundle_manifest_hash": BUNDLE_MANIFEST_HASH,
        "normalised_bundle_hash": NORMALISED_BUNDLE_HASH,
    }:
        raise GMA8BSourceResolutionError("configured inherited lineage hashes mismatch")
    if _sha256(settings.snapshot_manifest_path) != SNAPSHOT_MANIFEST_HASH:
        raise GMA8BSourceResolutionError("immutable snapshot-manifest SHA-256 mismatch")
    if _sha256(settings.inventory_path) != NORMALISED_BUNDLE_HASH:
        raise GMA8BSourceResolutionError("normalized inventory SHA-256 mismatch")
    manifest_rows = _read_csv(settings.snapshot_manifest_path)
    inventory_rows = _read_csv(settings.inventory_path)
    tickers = [row.get("ticker", "") for row in inventory_rows]
    if len(inventory_rows) != 29 or tickers != EXPANDED_29 or len(set(tickers)) != 29:
        raise GMA8BSourceResolutionError(
            "normalized inventory must contain ordered unique Expanded-29 tickers"
        )
    config_relative = str(metadata.get("gma6b_bundle_config_relative_path"))
    manifest_relative = str(metadata.get("gma6b_bundle_manifest_relative_path"))
    if config_relative != BUNDLE_CONFIG_RELATIVE_PATH:
        raise GMA8BSourceResolutionError("frozen bundle-config relative path mismatch")
    if manifest_relative != BUNDLE_MANIFEST_RELATIVE_PATH:
        raise GMA8BSourceResolutionError("frozen bundle-manifest relative path mismatch")
    _, bundle_config_path = _resolve_manifest_row(
        manifest_rows, config_relative, settings.snapshot_root
    )
    bundle_manifest_row, bundle_manifest_path = _resolve_manifest_row(
        manifest_rows, manifest_relative, settings.snapshot_root
    )
    if bundle_manifest_row.get("snapshot_sha256") != BUNDLE_MANIFEST_HASH:
        raise GMA8BSourceResolutionError("GMA-6B bundle-manifest lineage hash mismatch")
    bundle_config = _read_mapping(bundle_config_path)
    provider = bundle_config.get("provider") or {}
    if provider.get("auto_adjust") is not False or provider.get("actions") is not True:
        raise GMA8BSourceResolutionError("frozen GMA-6B provider adjustment contract mismatch")
    if (bundle_config.get("eligibility") or {}).get("required_tickers") != EXPANDED_29:
        raise GMA8BSourceResolutionError("frozen GMA-6B required ticker order mismatch")
    bundle_manifest = _read_mapping(bundle_manifest_path)
    if bundle_manifest.get("normalised_file_hashes_hash") != NORMALISED_BUNDLE_HASH:
        raise GMA8BSourceResolutionError("GMA-6B normalized-bundle hash mismatch")
    if bundle_manifest.get("requested_tickers") != EXPANDED_29:
        raise GMA8BSourceResolutionError("GMA-6B bundle-manifest ticker order mismatch")
    schema = settings.raw.get("frozen_normalised_schema") or {}
    if (
        schema.get("provider_auto_adjust_required") is not False
        or schema.get("provider_actions_required") is not True
        or schema.get("session_date_field") != DATE_FIELD
        or schema.get("adjusted_price_field") != ADJUSTED_PRICE_FIELD
        or schema.get("exact_csv_columns") != EXACT_COLUMNS
    ):
        raise GMA8BSourceResolutionError("frozen normalized schema contract mismatch")
    sources = []
    for inventory_row in inventory_rows:
        ticker = inventory_row["ticker"]
        expected_hash = inventory_row.get("normalised_series_file_hash", "")
        matches = [row for row in manifest_rows if row.get("snapshot_sha256") == expected_hash]
        if len(matches) != 1:
            raise GMA8BSourceResolutionError(
                f"inventory hash for {ticker} has {len(matches)} snapshot-manifest matches"
            )
        row = matches[0]
        if not _is_true(row.get("hash_match")):
            raise GMA8BSourceResolutionError(f"snapshot hash_match is false for {ticker}")
        snapshot_path = _confined_snapshot_path(
            row.get("snapshot_path", ""), settings.snapshot_root
        )
        if _sha256(snapshot_path) != expected_hash:
            raise GMA8BSourceResolutionError(f"resolved immutable series hash mismatch: {ticker}")
        sources.append(
            ResolvedSource(
                ticker=ticker,
                snapshot_path=snapshot_path,
                sha256=expected_hash,
                relative_path=row.get("relative_path", ""),
                source_path_provenance_only=row.get("source_path", ""),
            )
        )
    return Resolution(
        snapshot_manifest_sha256=SNAPSHOT_MANIFEST_HASH,
        inventory_sha256=NORMALISED_BUNDLE_HASH,
        bundle_config_path=bundle_config_path,
        bundle_config_sha256=_sha256(bundle_config_path),
        bundle_manifest_path=bundle_manifest_path,
        bundle_manifest_sha256=_sha256(bundle_manifest_path),
        sources=sources,
    )


def inspect_source(source: ResolvedSource, required_sessions: int) -> AssetAvailability:
    with source.snapshot_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXACT_COLUMNS:
            raise GMA8BDataQualityError(f"exact normalized schema mismatch for {source.ticker}")
        rows = list(reader)
    if not rows:
        raise GMA8BDataQualityError(f"empty normalized series for {source.ticker}")
    dates: list[date] = []
    missing = 0
    invalid = 0
    for ordinal, row in enumerate(rows, start=2):
        try:
            session = date.fromisoformat(str(row.get(DATE_FIELD, "")).strip())
        except ValueError as exc:
            raise GMA8BDataQualityError(
                f"session_dates_parseable failed for {source.ticker} row {ordinal}"
            ) from exc
        raw_price = str(row.get(ADJUSTED_PRICE_FIELD, "")).strip()
        if not raw_price:
            missing += 1
            continue
        try:
            price = float(raw_price)
        except ValueError as exc:
            raise GMA8BDataQualityError(
                f"price_values_numeric failed for {source.ticker} row {ordinal}"
            ) from exc
        if not math.isfinite(price) or price <= 0:
            invalid += 1
        dates.append(session)
    if missing:
        raise GMA8BDataQualityError(f"missing adjusted prices for {source.ticker}: {missing}")
    if invalid:
        raise GMA8BDataQualityError(
            f"nonpositive or nonfinite adjusted prices for {source.ticker}: {invalid}"
        )
    duplicate_count = len(dates) - len(set(dates))
    if duplicate_count:
        raise GMA8BDataQualityError(
            f"duplicate session dates for {source.ticker}: {duplicate_count}"
        )
    if any(current <= previous for previous, current in zip(dates, dates[1:])):
        raise GMA8BDataQualityError(f"session dates are not strictly ascending: {source.ticker}")
    if len(dates) < required_sessions:
        raise GMA8BDataQualityError(f"insufficient 253-session history for {source.ticker}")
    arms = EXPANDED_ARM_ID
    if source.ticker in CORE_22:
        arms = f"{CORE_ARM_ID}|{EXPANDED_ARM_ID}"
    return AssetAvailability(
        ticker=source.ticker,
        universe_arms=arms,
        immutable_snapshot_path=str(source.snapshot_path),
        normalised_series_sha256=source.sha256,
        source_adjusted_price_field=ADJUSTED_PRICE_FIELD,
        first_observed_session=dates[0].isoformat(),
        last_observed_session=dates[-1].isoformat(),
        observed_session_count=len(dates),
        first_positive_finite_session=dates[0].isoformat(),
        last_positive_finite_session=dates[-1].isoformat(),
        missing_value_count=0,
        nonpositive_or_nonfinite_value_count=0,
        duplicate_session_date_count=0,
        first_253_session_eligible_date=dates[required_sessions - 1].isoformat(),
        availability_status="eligible_after_253_observed_valid_sessions",
    )


def _arm_row(
    arm_id: str, tickers: list[str], assets: dict[str, AssetAvailability]
) -> dict[str, Any]:
    selected = [assets[ticker] for ticker in tickers]
    return {
        "universe_arm": arm_id,
        "asset_count": len(selected),
        "arm_first_asset_observed_session": min(row.first_observed_session for row in selected),
        "arm_last_asset_observed_session": max(row.last_observed_session for row in selected),
        "arm_first_all_assets_observed_session": max(
            row.first_observed_session for row in selected
        ),
        "arm_first_all_assets_253_session_eligible_date": max(
            row.first_253_session_eligible_date for row in selected
        ),
        "arm_final_all_assets_observed_session": min(row.last_observed_session for row in selected),
        "cross_arm_comparable_253_session_start": "pending_cross_arm_derivation",
    }


def audit(settings: Settings) -> AuditResult:
    lock_hash, maximum = validate_gma8a_parent(settings)
    resolution = resolve_sources(settings)
    required_sessions = maximum + 1
    assets = [inspect_source(source, required_sessions) for source in resolution.sources]
    by_ticker = {row.ticker: row for row in assets}
    arm_rows = [
        _arm_row(CORE_ARM_ID, CORE_22, by_ticker),
        _arm_row(EXPANDED_ARM_ID, EXPANDED_29, by_ticker),
    ]
    cross_start = max(row["arm_first_all_assets_253_session_eligible_date"] for row in arm_rows)
    for row in arm_rows:
        row["cross_arm_comparable_253_session_start"] = cross_start
    return AuditResult(
        settings=settings,
        gma8a_lock_sha256=lock_hash,
        maximum_lookback=maximum,
        required_sessions=required_sessions,
        resolution=resolution,
        assets=assets,
        arm_rows=arm_rows,
        cross_arm_start=cross_start,
        source_first_session=min(row.first_observed_session for row in assets),
        source_last_session=max(row.last_observed_session for row in assets),
    )


def _csv_text(fieldnames: list[str], rows: list[dict[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _false_operations() -> dict[str, bool]:
    return {field: False for field in FALSE_OPERATION_FIELDS}


def build_artifacts(result: AuditResult) -> dict[str, str]:
    resolution = result.resolution
    source_paths = [str(source.snapshot_path) for source in resolution.sources]
    source_hashes = {source.ticker: source.sha256 for source in resolution.sources}
    reference = {
        "resolution_status": "complete",
        "resolution_method": "inventory_hash_to_unique_snapshot_manifest_hash",
        "snapshot_manifest_path": str(result.settings.snapshot_manifest_path),
        "snapshot_manifest_sha256": resolution.snapshot_manifest_sha256,
        "normalised_inventory_path": str(result.settings.inventory_path),
        "normalised_inventory_sha256": resolution.inventory_sha256,
        "gma6b_bundle_config_path": str(resolution.bundle_config_path),
        "gma6b_bundle_config_sha256": resolution.bundle_config_sha256,
        "gma6b_bundle_manifest_path": str(resolution.bundle_manifest_path),
        "gma6b_bundle_manifest_sha256": resolution.bundle_manifest_sha256,
        "resolved_normalised_series_count": len(resolution.sources),
        "resolved_sources": [
            {
                "ticker": source.ticker,
                "immutable_snapshot_path": str(source.snapshot_path),
                "normalised_series_sha256": source.sha256,
                "manifest_relative_path": source.relative_path,
                "source_path_provenance_only": source.source_path_provenance_only,
            }
            for source in resolution.sources
        ],
    }
    input_rows = [
        {
            "ticker": source.ticker,
            "immutable_snapshot_path": source.snapshot_path,
            "normalised_series_sha256": source.sha256,
            "source_kind": SOURCE_KIND,
            "session_date_field": DATE_FIELD,
            "adjusted_price_field": ADJUSTED_PRICE_FIELD,
            "source_path_used_for_data_read": False,
        }
        for source in resolution.sources
    ]
    checks = {
        "snapshot_manifest_sha256_verified": True,
        "inventory_exact_29_unique_expanded_tickers": True,
        "inventory_hash_unique_manifest_match": True,
        "immutable_snapshot_path_confined": True,
        "actual_series_sha256_verified": True,
        "exact_normalised_schema_verified": True,
        "session_dates_parseable": True,
        "session_dates_strictly_ascending": True,
        "duplicate_session_dates": 0,
        "price_values_numeric": True,
        "price_values_finite": True,
        "price_values_positive": True,
        "missing_value_count": 0,
    }
    quality_rows = [
        {
            "check_id": key,
            "status": "pass",
            "observed_value": str(value).lower() if isinstance(value, bool) else value,
            "scope": "all_29_immutable_normalised_series",
        }
        for key, value in checks.items()
    ]
    summary = "\n".join(
        [
            "# GMA-8B Historical Data Provenance Summary V1",
            "",
            "GMA-8B freezes the inherited historical ETF/ETP adjusted-price evidence for the GMA-8 tournament.",
            "It does not calculate a strategy signal, portfolio target, backtest result, strategy ranking, paper decision, broker instruction, or real-money action.",
            "Highest historical CAGR or Sharpe alone is not a selection rule.",
            "No execution or promotion decision is produced.",
            "",
            f"- Resolved immutable normalized series: `{len(resolution.sources)}`",
            f"- Source first session: `{result.source_first_session}`",
            f"- Source last session: `{result.source_last_session}`",
            f"- Core-22 all-assets 253-session start: `{result.arm_rows[0]['arm_first_all_assets_253_session_eligible_date']}`",
            f"- Expanded-29 all-assets 253-session start: `{result.arm_rows[1]['arm_first_all_assets_253_session_eligible_date']}`",
            f"- Cross-arm comparable 253-session start: `{result.cross_arm_start}`",
            "",
            f"`adjusted_price_interpretation = {ADJUSTED_PRICE_INTERPRETATION}`",
            "",
            "`real_time_vendor_publication_timing_verified = false`",
            "",
            "All data reads used immutable snapshot paths resolved by exact hash. Source paths were provenance-only. No price row was modified or copied.",
            "",
        ]
    )
    common = {
        "contract_id": CONTRACT_ID,
        "gma8a_lock_sha256": result.gma8a_lock_sha256,
        "gma8a_strategy_grid_hash": GRID_HASH,
        "inherited_gma6_snapshot_manifest_hash": SNAPSHOT_MANIFEST_HASH,
        "inherited_gma6b_data_bundle_manifest_hash": BUNDLE_MANIFEST_HASH,
        "inherited_normalised_bundle_hash": NORMALISED_BUNDLE_HASH,
        "resolved_normalised_series_count": len(resolution.sources),
        "resolved_adjusted_price_source_kind": SOURCE_KIND,
        "resolved_normalised_series_paths": source_paths,
        "resolved_normalised_series_sha256": source_hashes,
        "source_first_session": result.source_first_session,
        "source_last_session": result.source_last_session,
        "maximum_strategy_lookback_sessions": result.maximum_lookback,
        "required_price_sessions_for_maximum_lookback": result.required_sessions,
        "core_22_arm_first_all_assets_253_session_eligible_date": result.arm_rows[0][
            "arm_first_all_assets_253_session_eligible_date"
        ],
        "expanded_29_arm_first_all_assets_253_session_eligible_date": result.arm_rows[1][
            "arm_first_all_assets_253_session_eligible_date"
        ],
        "cross_arm_comparable_253_session_start": result.cross_arm_start,
        "adjusted_price_interpretation": ADJUSTED_PRICE_INTERPRETATION,
        "real_time_vendor_publication_timing_verified": False,
        "inherited_historical_adjusted_price_files_read": True,
        **_false_operations(),
    }
    execution = {
        "contract_id": CONTRACT_ID,
        "operation": "immutable_29_series_provenance_quality_and_availability_audit",
        "metadata_root_file_count": 2,
        "inherited_historical_adjusted_price_files_read": True,
        "inherited_historical_adjusted_price_file_count": 29,
        "deterministic_generation": True,
        "wall_clock_timestamp_recorded": False,
        **_false_operations(),
    }
    asset_rows = [asdict(row) for row in result.assets]
    return {
        OUTPUT_FILENAMES[0]: json.dumps(reference, indent=2, sort_keys=True) + "\n",
        OUTPUT_FILENAMES[1]: _csv_text(list(input_rows[0]), input_rows),
        OUTPUT_FILENAMES[2]: _csv_text(list(asset_rows[0]), asset_rows),
        OUTPUT_FILENAMES[3]: _csv_text(list(result.arm_rows[0]), result.arm_rows),
        OUTPUT_FILENAMES[4]: _csv_text(list(quality_rows[0]), quality_rows),
        OUTPUT_FILENAMES[5]: summary,
        OUTPUT_FILENAMES[6]: json.dumps(
            {**common, "output_files": OUTPUT_FILENAMES}, indent=2, sort_keys=True
        )
        + "\n",
        OUTPUT_FILENAMES[7]: json.dumps(common, indent=2, sort_keys=True) + "\n",
        OUTPUT_FILENAMES[8]: json.dumps(execution, indent=2, sort_keys=True) + "\n",
    }


def generate(
    contract_path: str | Path,
    output_root: str | Path,
    worktree_root: str | Path = ".",
) -> list[Path]:
    result = audit(load_settings(contract_path, worktree_root))
    artifacts = build_artifacts(result)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in OUTPUT_FILENAMES:
        path = root / name
        path.write_text(artifacts[name], encoding="utf-8", newline="")
        paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit immutable GMA-6 normalized series")
    parser.add_argument(
        "--config",
        default="configs/global_multi_asset_alpha/gma8b_historical_data_provenance_contract_v1.yaml",
    )
    parser.add_argument(
        "--output-root",
        default="reports/global_multi_asset_alpha/gma8b_historical_data_provenance_v1",
    )
    args = parser.parse_args()
    paths = generate(args.config, args.output_root)
    print(f"contract_id={CONTRACT_ID}")
    print("resolution_status=complete")
    print("resolved_normalised_series_count=29")
    print("inherited_historical_adjusted_price_files_read=true")
    print("indicator_calculation_performed=false")
    print("backtest_performed=false")
    print("strategy_ranking_performed=false")
    for path in paths:
        print(f"output={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
