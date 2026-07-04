"""GMA-8B.0 immutable manual source-pointer template and structural validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any

import yaml

CONTRACT_ID = "gma8b_source_pointer_intake_contract_v1"
MANUAL_ENTRY = "REQUIRED_MANUAL_ENTRY"
GRID_HASH = "513139855cb34a67f735170683dd548724574001d43b7e3c4e29c32ecead5f6a"
SNAPSHOT_LINEAGE_HASH = "e767cb622bfe41240a8a4536920f79def3d267092b1bd0dcb2e6a06865ecdc6a"
BUNDLE_LINEAGE_HASH = "b93bd9800ddfffa19f12100c4538a4668ae61c20b7e322fec8df9441f63a166b"
NORMALISED_LINEAGE_HASH = "3d3d920e9bafa430fb313fe0f494954826a73f8962a15eb8709d02f2bae14bb6"
REQUIRED_TEMPLATE_FIELDS = [
    "gma6_snapshot_manifest_path",
    "normalised_file_inventory_path",
    "adjusted_price_panel_path",
    "gma6_snapshot_manifest_sha256",
    "normalised_file_inventory_sha256",
    "adjusted_price_panel_sha256",
    "gma6_snapshot_manifest_expected_lineage_hash",
    "gma6b_data_bundle_manifest_expected_lineage_hash",
    "normalised_bundle_expected_lineage_hash",
    "operator_attestation",
    "created_timestamp_utc",
]
FAILED_DRY_RUN_REQUIREMENTS = [
    "submitted_source_pointer_intake_present",
    "gma6_snapshot_manifest_path_present",
    "normalised_file_inventory_path_present",
    "adjusted_price_panel_path_present",
    "gma6_snapshot_manifest_sha256_present",
    "normalised_file_inventory_sha256_present",
    "adjusted_price_panel_sha256_present",
    "operator_attestation_present",
]
PATH_FIELDS = [
    "gma6_snapshot_manifest_path",
    "normalised_file_inventory_path",
    "adjusted_price_panel_path",
]
HASH_FIELDS = [
    "gma6_snapshot_manifest_sha256",
    "normalised_file_inventory_sha256",
    "adjusted_price_panel_sha256",
]
OUTPUT_FILENAMES = [
    "gma8b_gma6_source_pointer_template_v1.json",
    "gma8b_source_pointer_requirement_registry_v1.csv",
    "gma8b_source_pointer_template_dry_run_v1.json",
    "gma8b_source_pointer_preregistration_v1.md",
    "gma8b_source_pointer_lock_v1.json",
    "gma8b_source_pointer_execution_manifest_v1.json",
]
REQUIRED_LANGUAGE = [
    "GMA-8B.0 defines the manual immutable source-pointer intake required to resolve the inherited GMA-6 adjusted-price evidence.",
    "No historical price panel, indicator, strategy signal, portfolio target, backtest result, strategy ranking, paper session, broker instruction, or real-money action is produced.",
    "The GMA-8B provenance resolver remains fail-closed until an operator supplies exact local source paths and matching hashes.",
    "Highest historical CAGR or Sharpe alone is not a selection rule.",
    "No execution or promotion decision is produced.",
]


class SourcePointerIntakeError(ValueError):
    """Raised when the manual source-pointer contract or submission fails closed."""


@dataclass(frozen=True)
class IntakeSettings:
    path: Path
    raw: dict[str, Any]
    worktree_root: Path
    gma8a_paths: dict[str, Path]
    gma7b_paths: dict[str, Path]


@dataclass(frozen=True)
class FrozenInputEvidence:
    base_strategy_template_count: int
    arm_trial_count: int
    strategy_grid_hash: str
    gma6_snapshot_manifest_hash: str
    gma6b_data_bundle_manifest_hash: str
    normalised_bundle_hash: str
    input_sha256: dict[str, str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SourcePointerIntakeError(f"required frozen input is missing: {path}")
    if path.suffix.casefold() in {".yaml", ".yml"}:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SourcePointerIntakeError(f"required frozen input is not a mapping: {path}")
    return value


def load_settings(path: str | Path, worktree_root: str | Path = ".") -> IntakeSettings:
    contract_path = Path(path).resolve()
    raw = _load_mapping(contract_path)
    if (raw.get("contract") or {}).get("contract_id") != CONTRACT_ID:
        raise SourcePointerIntakeError("source-pointer contract_id mismatch")
    root = Path(worktree_root).resolve()
    parent = raw.get("gma8a_parent") or {}
    lineage = raw.get("gma7b_lineage_evidence") or {}
    gma8a_paths = {
        field: (root / str(parent[field])).resolve()
        for field in ["config_path", "lock_path", "execution_manifest_path"]
        if parent.get(field)
    }
    gma7b_paths = {
        field: Path(str(lineage[field])).resolve()
        for field in ["config_path", "manifest_path", "lock_path"]
        if lineage.get(field)
    }
    if len(gma8a_paths) != 3 or len(gma7b_paths) != 3:
        raise SourcePointerIntakeError("frozen input allowlist is incomplete")
    return IntakeSettings(contract_path, raw, root, gma8a_paths, gma7b_paths)


def verify_frozen_inputs(settings: IntakeSettings) -> FrozenInputEvidence:
    parent_config = _load_mapping(settings.gma8a_paths["config_path"])
    parent_lock = _load_mapping(settings.gma8a_paths["lock_path"])
    parent_execution = _load_mapping(settings.gma8a_paths["execution_manifest_path"])
    grid = parent_config.get("strategy_grid") or {}
    expected_parent = settings.raw["gma8a_parent"]
    observed = {
        "base": grid.get("exact_base_strategy_template_count"),
        "arm": grid.get("exact_arm_trial_count"),
        "grid_hash": grid.get("strategy_grid_hash"),
    }
    expected = {
        "base": expected_parent["expected_base_strategy_template_count"],
        "arm": expected_parent["expected_arm_trial_count"],
        "grid_hash": expected_parent["expected_strategy_grid_hash"],
    }
    if observed != expected or expected != {"base": 80, "arm": 160, "grid_hash": GRID_HASH}:
        raise SourcePointerIntakeError("frozen GMA-8A counts or strategy-grid hash mismatch")
    if (
        parent_lock.get("exact_base_strategy_template_count") != 80
        or parent_lock.get("exact_arm_trial_count") != 160
        or parent_lock.get("strategy_grid_hash") != GRID_HASH
    ):
        raise SourcePointerIntakeError("GMA-8A lock mismatch")
    for field in [
        "data_download_performed",
        "market_data_read",
        "backtest_performed",
        "strategy_ranking_performed",
    ]:
        if parent_execution.get(field) is not False:
            raise SourcePointerIntakeError(f"GMA-8A execution field mismatch: {field}")
    _load_mapping(settings.gma7b_paths["config_path"])
    gma7b_manifest = _load_mapping(settings.gma7b_paths["manifest_path"])
    gma7b_lock = _load_mapping(settings.gma7b_paths["lock_path"])
    frozen = settings.raw.get("frozen_lineage") or {}
    expected_lineage = {
        "gma6_snapshot_manifest_hash": SNAPSHOT_LINEAGE_HASH,
        "gma6b_data_bundle_manifest_hash": BUNDLE_LINEAGE_HASH,
        "normalised_bundle_hash": NORMALISED_LINEAGE_HASH,
    }
    if frozen != expected_lineage:
        raise SourcePointerIntakeError("configured frozen GMA-6 lineage hashes mismatch")
    for field, value in expected_lineage.items():
        if gma7b_manifest.get(field) != value or gma7b_lock.get(field) != value:
            raise SourcePointerIntakeError(f"GMA-7B frozen lineage mismatch: {field}")
    all_paths = [*settings.gma8a_paths.values(), *settings.gma7b_paths.values()]
    return FrozenInputEvidence(
        base_strategy_template_count=80,
        arm_trial_count=160,
        strategy_grid_hash=GRID_HASH,
        gma6_snapshot_manifest_hash=SNAPSHOT_LINEAGE_HASH,
        gma6b_data_bundle_manifest_hash=BUNDLE_LINEAGE_HASH,
        normalised_bundle_hash=NORMALISED_LINEAGE_HASH,
        input_sha256={str(path): _sha256(path) for path in all_paths},
    )


def build_template(settings: IntakeSettings) -> dict[str, str]:
    template = settings.raw.get("manual_template")
    if not isinstance(template, dict) or list(template) != REQUIRED_TEMPLATE_FIELDS:
        raise SourcePointerIntakeError("manual source-pointer template fields are not exact")
    if any(value != MANUAL_ENTRY for value in template.values()):
        raise SourcePointerIntakeError("manual source-pointer template values must remain empty")
    return {field: MANUAL_ENTRY for field in REQUIRED_TEMPLATE_FIELDS}


def _validate_hash_text(value: Any, field: str) -> str:
    text = str(value)
    if len(text) != 64 or any(character not in "0123456789abcdefABCDEF" for character in text):
        raise SourcePointerIntakeError(f"{field} must be a SHA-256 hex digest")
    return text.casefold()


def _validate_utc_timestamp(value: Any) -> None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourcePointerIntakeError(
            "created_timestamp_utc must be an ISO UTC timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise SourcePointerIntakeError("created_timestamp_utc must use UTC")


def _mapping_contains(mapping: Any, field: str, expected: str) -> bool:
    if isinstance(mapping, dict):
        if mapping.get(field) == expected:
            return True
        return any(_mapping_contains(value, field, expected) for value in mapping.values())
    if isinstance(mapping, list):
        return any(_mapping_contains(value, field, expected) for value in mapping)
    return False


def validate_submitted_intake(
    intake: dict[str, Any], gma8_worktree_root: str | Path
) -> dict[str, Any]:
    if set(intake) != set(REQUIRED_TEMPLATE_FIELDS) or len(intake) != len(REQUIRED_TEMPLATE_FIELDS):
        raise SourcePointerIntakeError("submitted intake fields must exactly match the template")
    if any(intake[field] == MANUAL_ENTRY for field in REQUIRED_TEMPLATE_FIELDS):
        raise SourcePointerIntakeError(
            "the empty template is not a submitted source-pointer intake"
        )
    if not str(intake["operator_attestation"]).strip():
        raise SourcePointerIntakeError("operator_attestation is required")
    _validate_utc_timestamp(intake["created_timestamp_utc"])
    expected_lineage = {
        "gma6_snapshot_manifest_expected_lineage_hash": SNAPSHOT_LINEAGE_HASH,
        "gma6b_data_bundle_manifest_expected_lineage_hash": BUNDLE_LINEAGE_HASH,
        "normalised_bundle_expected_lineage_hash": NORMALISED_LINEAGE_HASH,
    }
    for field, expected in expected_lineage.items():
        if intake[field] != expected:
            raise SourcePointerIntakeError(f"submitted frozen lineage mismatch: {field}")
    root = Path(gma8_worktree_root).resolve()
    resolved_paths: dict[str, Path] = {}
    for field in PATH_FIELDS:
        raw_path = str(intake[field])
        if not PureWindowsPath(raw_path).is_absolute():
            raise SourcePointerIntakeError(f"{field} must be an absolute Windows path")
        path = Path(raw_path).resolve()
        if not path.is_file():
            raise SourcePointerIntakeError(f"{field} must reference an existing file")
        if path == root or root in path.parents:
            raise SourcePointerIntakeError(f"{field} must not point into a GMA-8 worktree")
        resolved_paths[field] = path
    declared_hashes = {field: _validate_hash_text(intake[field], field) for field in HASH_FIELDS}
    pairs = [
        ("gma6_snapshot_manifest_path", "gma6_snapshot_manifest_sha256"),
        ("normalised_file_inventory_path", "normalised_file_inventory_sha256"),
        ("adjusted_price_panel_path", "adjusted_price_panel_sha256"),
    ]
    for path_field, hash_field in pairs:
        if _sha256(resolved_paths[path_field]) != declared_hashes[hash_field]:
            raise SourcePointerIntakeError(f"file SHA-256 mismatch: {hash_field}")
    snapshot = _load_mapping(resolved_paths["gma6_snapshot_manifest_path"])
    inventory = _load_mapping(resolved_paths["normalised_file_inventory_path"])
    if not _mapping_contains(snapshot, "gma6_snapshot_manifest_hash", SNAPSHOT_LINEAGE_HASH):
        raise SourcePointerIntakeError("snapshot manifest does not evidence GMA-6 lineage")
    if not _mapping_contains(snapshot, "gma6b_data_bundle_manifest_hash", BUNDLE_LINEAGE_HASH):
        raise SourcePointerIntakeError("snapshot manifest does not evidence GMA-6B lineage")
    if not _mapping_contains(inventory, "normalised_bundle_hash", NORMALISED_LINEAGE_HASH):
        raise SourcePointerIntakeError("inventory does not evidence normalized-bundle lineage")
    panel_path = str(resolved_paths["adjusted_price_panel_path"])
    panel_hash = declared_hashes["adjusted_price_panel_sha256"]
    file_rows = inventory.get("files")
    if not isinstance(file_rows, list) or not any(
        isinstance(row, dict)
        and str(Path(str(row.get("path", ""))).resolve()) == panel_path
        and str(row.get("sha256", "")).casefold() == panel_hash
        and row.get("role") == "adjusted_price_source"
        for row in file_rows
    ):
        raise SourcePointerIntakeError(
            "inventory does not explicitly identify the submitted adjusted-price panel"
        )
    return {
        "validation_status": "structurally_valid_source_pointer_intake",
        "resolved_paths": {field: str(path) for field, path in resolved_paths.items()},
        "declared_sha256": declared_hashes,
        "historical_price_panel_parsed": False,
    }


def _csv_text(fieldnames: list[str], rows: list[dict[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def build_dry_run_artifacts(
    settings: IntakeSettings, evidence: FrozenInputEvidence
) -> dict[str, str]:
    template = build_template(settings)
    dry_run = {
        "source_pointer_dry_run_status": "not_run_missing_manual_source_pointers",
        "submitted_source_pointer_intake_present": False,
        "failed_requirements": FAILED_DRY_RUN_REQUIREMENTS,
        "historical_price_panel_read": False,
        "indicator_calculation_performed": False,
        "backtest_performed": False,
        "strategy_ranking_performed": False,
        "portfolio_target_generated": False,
        "paper_broker_or_live_path_created": False,
    }
    requirement_rows = []
    for field in REQUIRED_TEMPLATE_FIELDS:
        category = "metadata"
        if field in PATH_FIELDS:
            category = "absolute_local_file_path"
        elif field in HASH_FIELDS or field.endswith("_lineage_hash"):
            category = "sha256"
        requirement_rows.append(
            {
                "requirement_id": field,
                "category": category,
                "template_value": MANUAL_ENTRY,
                "required_for_submission": True,
                "dry_run_status": "missing_manual_entry",
            }
        )
    preregistration = "\n".join(
        [
            "# GMA-8B.0 Source-Pointer Preregistration V1",
            "",
            *REQUIRED_LANGUAGE,
            "",
            "The generated template is not a submitted intake. All values remain `REQUIRED_MANUAL_ENTRY`. Paths are never discovered or inferred. GMA-8B remains fail-closed.",
            "",
        ]
    )
    template_text = json.dumps(template, indent=2) + "\n"
    lock = {
        "contract_id": CONTRACT_ID,
        "base_strategy_template_count": evidence.base_strategy_template_count,
        "arm_trial_count": evidence.arm_trial_count,
        "strategy_grid_hash": evidence.strategy_grid_hash,
        "gma6_snapshot_manifest_hash": evidence.gma6_snapshot_manifest_hash,
        "gma6b_data_bundle_manifest_hash": evidence.gma6b_data_bundle_manifest_hash,
        "normalised_bundle_hash": evidence.normalised_bundle_hash,
        "frozen_input_sha256": evidence.input_sha256,
        "source_pointer_template_sha256": hashlib.sha256(template_text.encode()).hexdigest(),
        **dry_run,
    }
    execution = {
        "contract_id": CONTRACT_ID,
        "operation": "empty_manual_source_pointer_template_dry_run",
        "output_files": OUTPUT_FILENAMES,
        "deterministic_generation": True,
        "wall_clock_timestamp_recorded": False,
        **dry_run,
    }
    return {
        OUTPUT_FILENAMES[0]: template_text,
        OUTPUT_FILENAMES[1]: _csv_text(list(requirement_rows[0]), requirement_rows),
        OUTPUT_FILENAMES[2]: json.dumps(dry_run, indent=2, sort_keys=True) + "\n",
        OUTPUT_FILENAMES[3]: preregistration,
        OUTPUT_FILENAMES[4]: json.dumps(lock, indent=2, sort_keys=True) + "\n",
        OUTPUT_FILENAMES[5]: json.dumps(execution, indent=2, sort_keys=True) + "\n",
    }


def generate_empty_template_dry_run(
    contract_path: str | Path,
    output_root: str | Path,
    worktree_root: str | Path = ".",
) -> list[Path]:
    settings = load_settings(contract_path, worktree_root)
    evidence = verify_frozen_inputs(settings)
    artifacts = build_dry_run_artifacts(settings, evidence)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in OUTPUT_FILENAMES:
        path = root / name
        path.write_text(artifacts[name], encoding="utf-8", newline="")
        paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the empty GMA-8B.0 pointer template")
    parser.add_argument(
        "--config",
        default="configs/global_multi_asset_alpha/gma8b_source_pointer_intake_contract_v1.yaml",
    )
    parser.add_argument(
        "--output-root",
        default="reports/global_multi_asset_alpha/gma8b_source_pointer_intake_v1",
    )
    args = parser.parse_args()
    paths = generate_empty_template_dry_run(args.config, args.output_root)
    print("source_pointer_dry_run_status=not_run_missing_manual_source_pointers")
    print("submitted_source_pointer_intake_present=false")
    print("historical_price_panel_read=false")
    print("indicator_calculation_performed=false")
    print("backtest_performed=false")
    print("strategy_ranking_performed=false")
    print("portfolio_target_generated=false")
    print("paper_broker_or_live_path_created=false")
    for path in paths:
        print(f"output={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
