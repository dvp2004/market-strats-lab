"""GMA-1A canonical snapshot selection and validation."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.global_multi_asset.data.manifests import (
    canonical_json,
    read_manifest,
    sha256_bytes,
    sha256_file,
)
from market_strats.global_multi_asset.gma1a_config import GMA1AConfig
from market_strats.global_multi_asset.universe import PROPOSED_INSTRUMENTS


def _manifest_candidates(manifest_root: Path) -> list[dict[str, Any]]:
    """Discover all manifest JSON files under the manifest root."""
    records: list[dict[str, Any]] = []
    for path in sorted(manifest_root.rglob("*_manifest.json")):
        try:
            manifest = read_manifest(path)
        except (OSError, ValueError):
            continue
        manifest["_manifest_path"] = str(path)
        records.append(manifest)
    return records


def _is_valid_live_yahoo_candidate(
    manifest: dict[str, Any],
    instrument_id: str,
    provider_symbol: str,
) -> tuple[bool, str]:
    """Check whether a manifest is a valid live Yahoo candidate for selection."""
    if manifest.get("track_id") != "gma_alpha":
        return False, "track_id_mismatch"
    if manifest.get("provider") != "yahoo_yfinance":
        return False, "not_yahoo_provider"
    if manifest.get("library_name") != "yfinance":
        return False, "not_yfinance_library"
    if manifest.get("provider_symbol") != provider_symbol:
        return False, "provider_symbol_mismatch"

    raw_path = Path(str(manifest.get("raw_file_path", "")))
    normalised_path = Path(str(manifest.get("normalised_file_path", "")))

    if not raw_path.exists():
        return False, "raw_file_missing"
    if not normalised_path.exists():
        return False, "normalised_file_missing"

    if "latest" in raw_path.name.lower():
        return False, "mutable_latest_source"
    if "latest" in normalised_path.name.lower():
        return False, "mutable_latest_source"

    manifest_path = Path(str(manifest.get("_manifest_path", "")))
    if "latest" in manifest_path.name.lower():
        return False, "mutable_latest_manifest"

    if sha256_file(raw_path) != manifest.get("raw_file_sha256"):
        return False, "raw_hash_invalid"
    if sha256_file(normalised_path) != manifest.get("normalised_file_sha256"):
        return False, "normalised_hash_invalid"

    expected_columns = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    manifest_columns = manifest.get("columns", [])
    if manifest_columns != expected_columns:
        return False, "schema_mismatch"

    row_count = manifest.get("row_count", 0)
    if not row_count or row_count < 1:
        return False, "empty_snapshot"

    return True, "valid"


def select_canonical_snapshots(
    config: GMA1AConfig,
    registry: dict[str, dict[str, Any]],
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Select exactly one canonical Yahoo snapshot per instrument.

    Returns (selection_df, selected_manifests_by_instrument).
    """
    manifest_root = config.paths.get("canonical_bundle_root", Path("")).parent / "manifests"
    manifest_root = Path(config.source_selection["gma0_manifest_root"])
    all_candidates = _manifest_candidates(manifest_root)

    rows: list[dict[str, Any]] = []
    selected_manifests: dict[str, dict[str, Any]] = {}

    for instrument_id in PROPOSED_INSTRUMENTS:
        entry = registry.get(instrument_id, {})
        provider_symbol = entry.get("provider_symbol", instrument_id)

        candidates = []
        rejected_count = 0
        reject_reasons: list[str] = []

        for manifest in all_candidates:
            if manifest.get("provider_symbol") != provider_symbol:
                continue
            valid, reason = _is_valid_live_yahoo_candidate(
                manifest, instrument_id, provider_symbol
            )
            if valid:
                candidates.append(manifest)
            else:
                rejected_count += 1
                reject_reasons.append(reason)

        if not candidates:
            rows.append({
                "instrument_id": instrument_id,
                "provider": "",
                "provider_symbol": provider_symbol,
                "selected_manifest_path": "",
                "selected_manifest_sha256": "",
                "selected_raw_snapshot_path": "",
                "selected_normalised_snapshot_path": "",
                "retrieved_at_utc": "",
                "raw_sha256": "",
                "normalised_sha256": "",
                "first_completed_date": "",
                "last_completed_date": "",
                "completed_row_count": 0,
                "selection_reason": "no_valid_candidates",
                "selection_status": "failed",
                "rejected_candidate_count": rejected_count,
                "selection_warning": ";".join(sorted(set(reject_reasons))),
            })
            continue

        # Deterministic selection: latest retrieved_at_utc, then manifest path hash
        def sort_key(m: dict[str, Any]) -> tuple[str, str]:
            return (
                str(m.get("retrieved_at_utc", "")),
                sha256_bytes(str(m.get("_manifest_path", "")).encode()),
            )

        candidates.sort(key=sort_key, reverse=True)
        selected = candidates[0]
        manifest_path = Path(str(selected["_manifest_path"]))
        raw_path = Path(str(selected["raw_file_path"]))
        normalised_path = Path(str(selected["normalised_file_path"]))

        # Compute completed history dates from normalised
        from market_strats.global_multi_asset.data.validation import (
            completed_history,
            normalise_price_frame,
        )

        normalised_frame = normalise_price_frame(pd.read_csv(normalised_path))
        completed = completed_history(
            normalised_frame, str(selected.get("retrieved_at_utc", ""))
        )
        first_date = ""
        last_date = ""
        completed_count = 0
        if not completed.empty:
            dates = pd.to_datetime(completed["date"]).sort_values()
            first_date = dates.iloc[0].date().isoformat()
            last_date = dates.iloc[-1].date().isoformat()
            completed_count = len(completed)

        selected_manifests[instrument_id] = selected

        rows.append({
            "instrument_id": instrument_id,
            "provider": str(selected.get("provider", "")),
            "provider_symbol": provider_symbol,
            "selected_manifest_path": str(manifest_path),
            "selected_manifest_sha256": sha256_file(manifest_path),
            "selected_raw_snapshot_path": str(raw_path),
            "selected_normalised_snapshot_path": str(normalised_path),
            "retrieved_at_utc": str(selected.get("retrieved_at_utc", "")),
            "raw_sha256": str(selected.get("raw_file_sha256", "")),
            "normalised_sha256": str(selected.get("normalised_file_sha256", "")),
            "first_completed_date": first_date,
            "last_completed_date": last_date,
            "completed_row_count": completed_count,
            "selection_reason": "latest_valid_live_yahoo_snapshot",
            "selection_status": "selected",
            "rejected_candidate_count": rejected_count,
            "selection_warning": "",
        })

    return pd.DataFrame(rows), selected_manifests


def compute_selection_set_hash(
    selection_df: pd.DataFrame,
) -> str:
    """Compute a deterministic SHA-256 over the sorted canonical identities and hashes."""
    identity_records: list[dict[str, str]] = []
    for _, row in selection_df.iterrows():
        if row.get("selection_status") != "selected":
            continue
        identity_records.append({
            "instrument_id": str(row["instrument_id"]),
            "raw_sha256": str(row["raw_sha256"]),
            "normalised_sha256": str(row["normalised_sha256"]),
            "selected_manifest_sha256": str(row["selected_manifest_sha256"]),
        })
    identity_records.sort(key=lambda r: r["instrument_id"])
    return sha256_bytes(canonical_json(identity_records).encode("utf-8"))


def build_selection_manifest(
    config: GMA1AConfig,
    selection_df: pd.DataFrame,
    selection_set_hash: str,
    commit_sha: str,
) -> dict[str, Any]:
    """Build the canonical selection manifest JSON structure."""
    config_hash = sha256_bytes(
        canonical_json(config.raw).encode("utf-8")
    )
    sources: dict[str, dict[str, str]] = {}
    for _, row in selection_df.iterrows():
        sources[str(row["instrument_id"])] = {
            "provider": str(row.get("provider", "")),
            "provider_symbol": str(row.get("provider_symbol", "")),
            "selected_manifest_path": str(row.get("selected_manifest_path", "")),
            "selected_manifest_sha256": str(row.get("selected_manifest_sha256", "")),
            "raw_sha256": str(row.get("raw_sha256", "")),
            "normalised_sha256": str(row.get("normalised_sha256", "")),
            "selection_status": str(row.get("selection_status", "")),
        }
    return {
        "track_id": "gma_alpha",
        "phase_id": "gma1a_market_data_foundation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_commit_sha": commit_sha,
        "configuration_hash": config_hash,
        "selection_policy": "latest_valid_live_yahoo_snapshot",
        "canonical_selection_set_hash": selection_set_hash,
        "sources": sources,
    }


def write_selection_reports(
    config: GMA1AConfig,
    selection_df: pd.DataFrame,
    selection_manifest: dict[str, Any],
    selection_set_hash: str,
) -> dict[str, Path]:
    """Write all selection-related report files."""
    report_root = Path(config.paths.get("report_root", Path("")))
    report_root.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Path] = {}

    csv_path = report_root / "canonical_snapshot_selection.csv"
    selection_df.to_csv(csv_path, index=False)
    outputs["canonical_snapshot_selection"] = csv_path

    json_path = report_root / "canonical_selection_manifest.json"
    json_path.write_text(
        json.dumps(selection_manifest, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    outputs["canonical_selection_manifest"] = json_path

    hash_path = report_root / "canonical_selection_hash.txt"
    hash_path.write_text(selection_set_hash + "\n", encoding="utf-8")
    outputs["canonical_selection_hash"] = hash_path

    return outputs
