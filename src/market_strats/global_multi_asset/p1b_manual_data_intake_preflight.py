from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PHASE_ID = "p1b_manual_data_intake_preflight_v1"
P1A_PHASE_ID = "p1a_manual_paper_contract_v1"
STRATEGY_ID = "gma5_equal_weight_atomic_sleeves_v1"
PARENT_EXECUTION_REFERENCE = "gma5_clean_execution_20260622T075912Z_v1"
OUTPUT_DIR = Path("reports/global_multi_asset_alpha/p1b_manual_data_intake_preflight_v1")
PLACEHOLDER = "REQUIRED_MANUAL_ENTRY"

REQUIRED_LANGUAGE = [
    "P-1B is a manual data-intake and preflight dry-run only.",
    "No actual data snapshot was supplied to this run.",
    "No target, paper decision, paper session, performance result, broker instruction, or real-money action is produced.",
    "P-1 remains a separate manual-paper observation programme for the frozen GMA-5 equal-weight atomic sleeve portfolio.",
]

P1A_INPUTS = {
    "p1a_contract": Path("configs/global_multi_asset_alpha/p1a_manual_paper_contract_v1.yaml"),
    "p1a_parent_resolution": Path(
        "reports/global_multi_asset_alpha/p1a_manual_paper_contract_v1/"
        "p1a_parent_reference_resolution_v1.json"
    ),
    "p1a_session_template": Path(
        "reports/global_multi_asset_alpha/p1a_manual_paper_contract_v1/"
        "p1a_manual_paper_session_template_v1.csv"
    ),
    "p1a_ledger": Path(
        "reports/global_multi_asset_alpha/p1a_manual_paper_contract_v1/"
        "p1a_manual_paper_ledger_v1.csv"
    ),
    "p1a_lock": Path(
        "reports/global_multi_asset_alpha/p1a_manual_paper_contract_v1/p1a_manual_paper_lock_v1.json"
    ),
}

OUTPUT_PATHS = {
    "contract": Path(
        "configs/global_multi_asset_alpha/p1b_manual_data_intake_preflight_contract_v1.yaml"
    ),
    "docs": Path("docs/global_multi_asset_alpha/p1b_manual_data_intake_preflight_contract_v1.md"),
    "intake_template": OUTPUT_DIR / "p1b_manual_data_intake_template_v1.json",
    "requirement_registry": OUTPUT_DIR / "p1b_preflight_requirement_registry_v1.csv",
    "dry_run_json": OUTPUT_DIR / "p1b_preflight_dry_run_v1.json",
    "dry_run_md": OUTPUT_DIR / "p1b_preflight_dry_run_v1.md",
    "execution_manifest": OUTPUT_DIR / "p1b_execution_manifest_v1.json",
    "lock": OUTPUT_DIR / "p1b_preflight_lock_v1.json",
}

LEDGER_FIELDS = [
    "session_id",
    "scheduled_decision_session_date",
    "actual_decision_timestamp_utc",
    "data_cutoff_timestamp_utc",
    "source_last_observed_session",
    "session_data_snapshot_path",
    "session_data_snapshot_sha256",
    "parent_strategy_id",
    "parent_execution_reference",
    "parent_reference_manifest_sha256",
    "manual_preflight_validation_status",
    "manual_decision",
    "manual_decision_reason",
    "target_file_sha256",
    "target_row_count",
    "target_weight_sum",
    "execution_status",
    "paper_session_status",
    "warning_flags",
    "operator_notes",
    "ledger_created_timestamp_utc",
]

INTAKE_TEMPLATE_FIELDS = [
    "intake_id",
    "manual_intake_timestamp_utc",
    "scheduled_decision_session_date",
    "session_data_snapshot_path",
    "session_data_snapshot_sha256",
    "data_source_description",
    "source_last_observed_session",
    "data_cutoff_timestamp_utc",
    "snapshot_format",
    "snapshot_schema_version",
    "operator_attestation",
]

PREFLIGHT_REQUIREMENTS = [
    "p1a_parent_lock_hash_verified",
    "p1a_parent_strategy_verified",
    "p1a_zero_row_ledger_verified",
    "manual_intake_manifest_present",
    "session_data_snapshot_present",
    "session_data_snapshot_sha256_verified",
    "data_source_description_present",
    "source_last_observed_session_present",
    "data_cutoff_timestamp_present",
    "scheduled_decision_session_date_present",
    "operator_attestation_present",
    "paper_only_boundary_verified",
]

MISSING_INTAKE_FAILED_REQUIREMENTS = [
    "manual_intake_manifest_present",
    "session_data_snapshot_present",
    "session_data_snapshot_sha256_verified",
    "data_source_description_present",
    "source_last_observed_session_present",
    "data_cutoff_timestamp_present",
    "scheduled_decision_session_date_present",
    "operator_attestation_present",
]


class P1BPreflightError(ValueError):
    pass


@dataclass(frozen=True)
class P1AInputs:
    contract: dict[str, Any]
    parent_resolution: dict[str, Any]
    lock: dict[str, Any]
    ledger_rows: list[dict[str, str]]
    session_template_rows: list[dict[str, str]]
    input_hashes: dict[str, str]


@dataclass(frozen=True)
class ValidationResult:
    status: str
    passed_requirements: list[str]
    failed_requirements: list[str]
    paper_session_created: bool
    manual_paper_ledger_modified: bool


@dataclass(frozen=True)
class P1BResult:
    dry_run: dict[str, Any]
    output_paths: dict[str, Path]


def sha256_file(path: Path) -> str:
    if path.is_dir():
        raise P1BPreflightError(f"Refusing to hash a directory: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P1BPreflightError(f"Expected JSON object: {path}")
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P1BPreflightError(f"Expected YAML object: {path}")
    return payload


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _require_equal(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise P1BPreflightError(f"{name} mismatch: expected {expected!r}, got {actual!r}")


def _is_present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip() != PLACEHOLDER


def build_intake_template() -> dict[str, str]:
    return {field: PLACEHOLDER for field in INTAKE_TEMPLATE_FIELDS}


def load_p1a_inputs(repo_root: Path) -> P1AInputs:
    paths = {name: repo_root / relative for name, relative in P1A_INPUTS.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise P1BPreflightError("Missing required P-1A input(s): " + ", ".join(missing))
    hashes = {name: sha256_file(path) for name, path in paths.items()}
    contract = _read_yaml(paths["p1a_contract"])
    parent_resolution = _read_json(paths["p1a_parent_resolution"])
    lock = _read_json(paths["p1a_lock"])
    ledger_fields, ledger_rows = _read_csv(paths["p1a_ledger"])
    session_fields, session_template_rows = _read_csv(paths["p1a_session_template"])
    _require_equal("p1a_ledger_fields", ledger_fields, LEDGER_FIELDS)
    _require_equal("p1a_session_template_fields", session_fields, LEDGER_FIELDS)
    _require_equal("p1a_ledger_row_count", len(ledger_rows), 0)
    _require_equal("p1a_session_template_row_count", len(session_template_rows), 0)
    verify_parent_identity(contract, parent_resolution, lock, hashes)
    return P1AInputs(
        contract=contract,
        parent_resolution=parent_resolution,
        lock=lock,
        ledger_rows=ledger_rows,
        session_template_rows=session_template_rows,
        input_hashes=hashes,
    )


def verify_parent_identity(
    contract: dict[str, Any],
    parent_resolution: dict[str, Any],
    lock: dict[str, Any],
    hashes: dict[str, str],
) -> None:
    for source_name, source in (
        ("contract", contract),
        ("parent_resolution", parent_resolution),
        ("lock", lock),
    ):
        _require_equal(f"{source_name}.strategy_id", source.get("strategy_id"), STRATEGY_ID)
        _require_equal(
            f"{source_name}.parent_execution_reference",
            source.get("parent_execution_reference"),
            PARENT_EXECUTION_REFERENCE,
        )
    _require_equal("contract.paper_mode", contract.get("paper_mode"), "manual_observation_only")
    _require_equal("contract.real_money", contract.get("real_money"), "prohibited")
    _require_equal("contract.broker_connection", contract.get("broker_connection"), "prohibited")
    _require_equal("contract.trade_execution", contract.get("trade_execution"), "prohibited")
    _require_equal(
        "contract.automated_order_generation",
        contract.get("automated_order_generation"),
        "prohibited",
    )
    _require_equal("contract.gma7_dependency", contract.get("gma7_dependency"), "none")
    _require_equal("lock.paper_mode", lock.get("paper_mode"), "manual_observation_only")
    _require_equal("lock.real_money", lock.get("real_money"), "prohibited")
    _require_equal("lock.broker_connection", lock.get("broker_connection"), "prohibited")
    _require_equal("lock.trade_execution", lock.get("trade_execution"), "prohibited")
    _require_equal(
        "lock.automated_order_generation", lock.get("automated_order_generation"), "prohibited"
    )
    _require_equal("lock.gma7_dependency", lock.get("gma7_dependency"), "none")
    _require_equal("lock.ledger_row_count", lock.get("ledger_row_count"), 0)
    expected_parent_hash = lock.get("generated_artifact_hashes", {}).get("parent_resolution")
    if expected_parent_hash is not None:
        _require_equal(
            "p1a_parent_resolution_sha256",
            hashes["p1a_parent_resolution"],
            expected_parent_hash,
        )


def validate_future_intake_manifest(
    repo_root: Path, manifest_path: Path | None
) -> ValidationResult:
    load_p1a_inputs(repo_root)
    passed = [
        "p1a_parent_lock_hash_verified",
        "p1a_parent_strategy_verified",
        "p1a_zero_row_ledger_verified",
        "paper_only_boundary_verified",
    ]
    if manifest_path is None:
        return ValidationResult(
            status="not_run_missing_preconditions",
            passed_requirements=passed,
            failed_requirements=MISSING_INTAKE_FAILED_REQUIREMENTS.copy(),
            paper_session_created=False,
            manual_paper_ledger_modified=False,
        )
    manifest = _read_json(manifest_path)
    validate_intake_template_not_submitted(manifest)
    failed: list[str] = []
    if not manifest_path.is_file():
        failed.append("manual_intake_manifest_present")
    snapshot_path_value = manifest.get("session_data_snapshot_path")
    snapshot_path = Path(snapshot_path_value) if _is_present(snapshot_path_value) else None
    if snapshot_path is not None and not snapshot_path.is_absolute():
        snapshot_path = manifest_path.parent / snapshot_path
    if snapshot_path is None or not snapshot_path.is_file():
        failed.append("session_data_snapshot_present")
    expected_sha = manifest.get("session_data_snapshot_sha256")
    if snapshot_path is None or not snapshot_path.is_file() or not _is_present(expected_sha):
        failed.append("session_data_snapshot_sha256_verified")
    else:
        actual_sha = sha256_file(snapshot_path)
        if actual_sha != str(expected_sha):
            raise P1BPreflightError(
                "session_data_snapshot_sha256 mismatch for supplied manual intake snapshot"
            )
    if not _is_present(manifest.get("data_source_description")):
        failed.append("data_source_description_present")
    if not _is_present(manifest.get("source_last_observed_session")):
        failed.append("source_last_observed_session_present")
    if not _is_present(manifest.get("data_cutoff_timestamp_utc")):
        failed.append("data_cutoff_timestamp_present")
    if not _is_present(manifest.get("scheduled_decision_session_date")):
        failed.append("scheduled_decision_session_date_present")
    if not _is_present(manifest.get("operator_attestation")):
        failed.append("operator_attestation_present")
    if failed:
        return ValidationResult(
            status="not_run_missing_preconditions",
            passed_requirements=passed,
            failed_requirements=failed,
            paper_session_created=False,
            manual_paper_ledger_modified=False,
        )
    return ValidationResult(
        status="structural_preflight_passed_no_session_created",
        passed_requirements=PREFLIGHT_REQUIREMENTS.copy(),
        failed_requirements=[],
        paper_session_created=False,
        manual_paper_ledger_modified=False,
    )


def validate_intake_template_not_submitted(manifest: dict[str, Any]) -> None:
    if set(manifest) == set(INTAKE_TEMPLATE_FIELDS) and all(
        manifest.get(field) == PLACEHOLDER for field in INTAKE_TEMPLATE_FIELDS
    ):
        raise P1BPreflightError("The P-1B template is not a valid submitted intake manifest")


def build_requirement_registry_rows() -> list[dict[str, str]]:
    missing = set(MISSING_INTAKE_FAILED_REQUIREMENTS)
    return [
        {
            "requirement_id": requirement,
            "current_dry_run_status": "failed_missing_manual_input"
            if requirement in missing
            else "passed",
            "paper_session_created_when_failed": "false",
        }
        for requirement in PREFLIGHT_REQUIREMENTS
    ]


def build_contract_yaml(p1a: P1AInputs) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "p1a_phase_id": P1A_PHASE_ID,
        "strategy_id": STRATEGY_ID,
        "parent_execution_reference": PARENT_EXECUTION_REFERENCE,
        "parent_reference_manifest_sha256": p1a.lock["parent_reference_manifest_sha256"],
        "required_language": REQUIRED_LANGUAGE,
        "paper_mode": "manual_observation_only",
        "real_money": "prohibited",
        "broker_connection": "prohibited",
        "trade_execution": "prohibited",
        "automated_order_generation": "prohibited",
        "target_generation": "prohibited",
        "performance_calculation": "prohibited",
        "gma7_dependency": "none",
        "allowed_p1a_inputs": {name: str(path) for name, path in P1A_INPUTS.items()},
        "manual_intake_template_fields": INTAKE_TEMPLATE_FIELDS,
        "preflight_requirements": PREFLIGHT_REQUIREMENTS,
        "current_dry_run_expected_failed_requirements": MISSING_INTAKE_FAILED_REQUIREMENTS,
    }


def build_dry_run_payload(p1a: P1AInputs, validation: ValidationResult) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "strategy_id": STRATEGY_ID,
        "parent_execution_reference": PARENT_EXECUTION_REFERENCE,
        "parent_reference_manifest_sha256": p1a.lock["parent_reference_manifest_sha256"],
        "preflight_dry_run_status": validation.status,
        "paper_session_created": validation.paper_session_created,
        "manual_paper_ledger_modified": validation.manual_paper_ledger_modified,
        "target_generated": False,
        "paper_decision_created": False,
        "performance_result_created": False,
        "broker_instruction_created": False,
        "real_money_action_created": False,
        "required_language": REQUIRED_LANGUAGE,
        "passed_requirements": validation.passed_requirements,
        "failed_requirements": validation.failed_requirements,
        "p1a_input_hashes": p1a.input_hashes,
        "p1a_input_hash_count": len(p1a.input_hashes),
        "actual_data_snapshot_supplied": False,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_docs(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# P-1B Manual Data-Intake and Preflight Dry-Run Contract V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                "The eventual data snapshot must be manually supplied locally by the operator and cannot be downloaded, substituted, backfilled, or generated by P-1B.",
                "",
                "P-1B validates structure, parent lock continuity, an empty P-1A ledger, local snapshot existence, and supplied snapshot SHA-256 only.",
                "It does not inspect snapshot contents or calculate targets, weights, returns, performance, orders, broker instructions, or live actions.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_dry_run_markdown(path: Path, dry_run: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    failed = "\n".join(f"- `{item}`" for item in dry_run["failed_requirements"])
    passed = "\n".join(f"- `{item}`" for item in dry_run["passed_requirements"])
    path.write_text(
        "\n".join(
            [
                "# P-1B Preflight Dry Run V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                f"- preflight_dry_run_status: `{dry_run['preflight_dry_run_status']}`",
                f"- paper_session_created: `{str(dry_run['paper_session_created']).lower()}`",
                f"- manual_paper_ledger_modified: `{str(dry_run['manual_paper_ledger_modified']).lower()}`",
                "",
                "## Passed Requirements",
                "",
                passed,
                "",
                "## Failed Requirements",
                "",
                failed,
                "",
            ]
        ),
        encoding="utf-8",
    )


def generate_preflight_files(
    repo_root: Path = Path.cwd(), intake_manifest_path: Path | None = None
) -> P1BResult:
    p1a = load_p1a_inputs(repo_root)
    p1a_ledger_before = p1a.input_hashes["p1a_ledger"]
    p1a_template_before = p1a.input_hashes["p1a_session_template"]
    validation = validate_future_intake_manifest(repo_root, intake_manifest_path)
    dry_run = build_dry_run_payload(p1a, validation)
    write_json(repo_root / OUTPUT_PATHS["intake_template"], build_intake_template())
    write_csv(
        repo_root / OUTPUT_PATHS["requirement_registry"],
        build_requirement_registry_rows(),
        ["requirement_id", "current_dry_run_status", "paper_session_created_when_failed"],
    )
    write_json(repo_root / OUTPUT_PATHS["dry_run_json"], dry_run)
    write_dry_run_markdown(repo_root / OUTPUT_PATHS["dry_run_md"], dry_run)
    config_path = repo_root / OUTPUT_PATHS["contract"]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(build_contract_yaml(p1a), sort_keys=False), encoding="utf-8"
    )
    write_docs(repo_root / OUTPUT_PATHS["docs"])
    generated_hashes = {
        key: sha256_file(repo_root / path)
        for key, path in OUTPUT_PATHS.items()
        if key not in {"execution_manifest", "lock"} and (repo_root / path).is_file()
    }
    execution_manifest = {
        "phase_id": PHASE_ID,
        "post_processing_only": True,
        "actual_data_snapshot_supplied": False,
        "p1a_inputs_read": {name: str(path) for name, path in P1A_INPUTS.items()},
        "p1a_input_hashes": p1a.input_hashes,
        "generated_artifact_hashes_excluding_manifest_and_lock": generated_hashes,
        "files_hashed_count": len(p1a.input_hashes) + len(generated_hashes),
    }
    write_json(repo_root / OUTPUT_PATHS["execution_manifest"], execution_manifest)
    generated_hashes_with_manifest = {
        **generated_hashes,
        "execution_manifest": sha256_file(repo_root / OUTPUT_PATHS["execution_manifest"]),
    }
    lock = {
        "phase_id": PHASE_ID,
        "strategy_id": STRATEGY_ID,
        "parent_execution_reference": PARENT_EXECUTION_REFERENCE,
        "parent_reference_manifest_sha256": p1a.lock["parent_reference_manifest_sha256"],
        "preflight_dry_run_status": validation.status,
        "paper_session_created": False,
        "manual_paper_ledger_modified": False,
        "target_generated": False,
        "paper_decision_created": False,
        "performance_result_created": False,
        "broker_instruction_created": False,
        "real_money_action_created": False,
        "generated_artifact_hashes_excluding_lock": generated_hashes_with_manifest,
        "generated_artifact_hash_count_excluding_lock": len(generated_hashes_with_manifest),
        "files_hashed_count": len(p1a.input_hashes) + len(generated_hashes_with_manifest),
    }
    write_json(repo_root / OUTPUT_PATHS["lock"], lock)
    p1a_after = load_p1a_inputs(repo_root)
    _require_equal(
        "p1a_ledger_sha256_after_generation",
        p1a_after.input_hashes["p1a_ledger"],
        p1a_ledger_before,
    )
    _require_equal(
        "p1a_session_template_sha256_after_generation",
        p1a_after.input_hashes["p1a_session_template"],
        p1a_template_before,
    )
    return P1BResult(
        dry_run=dry_run,
        output_paths={name: repo_root / path for name, path in OUTPUT_PATHS.items()},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate P-1B manual intake preflight artifacts")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--intake-manifest", type=Path, default=None)
    args = parser.parse_args(argv)
    result = generate_preflight_files(args.repo_root, args.intake_manifest)
    print(f"phase_id={PHASE_ID}")
    print(f"strategy_id={STRATEGY_ID}")
    print(f"parent_execution_reference={PARENT_EXECUTION_REFERENCE}")
    print(f"preflight_dry_run_status={result.dry_run['preflight_dry_run_status']}")
    print(f"paper_session_created={str(result.dry_run['paper_session_created']).lower()}")
    print(
        "manual_paper_ledger_modified="
        f"{str(result.dry_run['manual_paper_ledger_modified']).lower()}"
    )
    print("failed_requirements=" + ",".join(result.dry_run["failed_requirements"]))
    for key, path in sorted(result.output_paths.items()):
        print(f"{key}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
