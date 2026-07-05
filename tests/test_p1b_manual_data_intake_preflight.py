from __future__ import annotations

import ast
import csv
import json
import os
from pathlib import Path

import pytest
import yaml

from market_strats.global_multi_asset import p1b_manual_data_intake_preflight as p1b


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_p1a_fixture(repo: Path) -> None:
    contract = {
        "phase_id": "p1a_manual_paper_contract_v1",
        "strategy_id": p1b.STRATEGY_ID,
        "parent_execution_reference": p1b.PARENT_EXECUTION_REFERENCE,
        "paper_mode": "manual_observation_only",
        "real_money": "prohibited",
        "broker_connection": "prohibited",
        "trade_execution": "prohibited",
        "automated_order_generation": "prohibited",
        "gma7_dependency": "none",
    }
    parent_resolution = {
        "phase_id": "p1a_manual_paper_contract_v1",
        "strategy_id": p1b.STRATEGY_ID,
        "parent_execution_reference": p1b.PARENT_EXECUTION_REFERENCE,
        "parent_reference_manifest_sha256": "parent-resolution-hash",
        "source_artifacts": {
            "external_gma5_path_is_provenance_only": {
                "path": "C:/external/gma5_snapshot/evidence.json",
                "sha256": "abc123",
            }
        },
        "gma7_dependency": "none",
    }
    _write_text(
        repo / p1b.P1A_INPUTS["p1a_contract"],
        yaml.safe_dump(contract, sort_keys=False),
    )
    _write_json(repo / p1b.P1A_INPUTS["p1a_parent_resolution"], parent_resolution)
    _write_csv(repo / p1b.P1A_INPUTS["p1a_ledger"], [], p1b.LEDGER_FIELDS)
    _write_csv(repo / p1b.P1A_INPUTS["p1a_session_template"], [], p1b.LEDGER_FIELDS)
    parent_hash = _sha256(repo / p1b.P1A_INPUTS["p1a_parent_resolution"])
    lock = {
        "phase_id": "p1a_manual_paper_contract_v1",
        "strategy_id": p1b.STRATEGY_ID,
        "parent_execution_reference": p1b.PARENT_EXECUTION_REFERENCE,
        "parent_reference_manifest_sha256": "parent-resolution-hash",
        "paper_mode": "manual_observation_only",
        "real_money": "prohibited",
        "broker_connection": "prohibited",
        "trade_execution": "prohibited",
        "automated_order_generation": "prohibited",
        "gma7_dependency": "none",
        "ledger_row_count": 0,
        "generated_artifact_hashes": {"parent_resolution": parent_hash},
    }
    _write_json(repo / p1b.P1A_INPUTS["p1a_lock"], lock)


def _valid_intake(repo: Path) -> Path:
    snapshot = repo / "manual_inputs" / "operator_snapshot.csv"
    _write_text(snapshot, "opaque operator supplied snapshot\n")
    manifest = {
        "intake_id": "manual_intake_001",
        "manual_intake_timestamp_utc": "2026-06-26T20:30:00Z",
        "scheduled_decision_session_date": "2026-06-26",
        "session_data_snapshot_path": str(snapshot),
        "session_data_snapshot_sha256": _sha256(snapshot),
        "data_source_description": "manual local operator snapshot",
        "source_last_observed_session": "2026-06-26",
        "data_cutoff_timestamp_utc": "2026-06-26T20:00:00Z",
        "snapshot_format": "csv",
        "snapshot_schema_version": "manual_v1",
        "operator_attestation": "operator supplied the file locally",
    }
    manifest_path = repo / "manual_inputs" / "intake_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def test_p1a_parent_lock_and_strategy_identity_are_verified(tmp_path: Path):
    _write_p1a_fixture(tmp_path)

    loaded = p1b.load_p1a_inputs(tmp_path)

    assert loaded.contract["strategy_id"] == "gma5_equal_weight_atomic_sleeves_v1"
    assert loaded.lock["parent_execution_reference"] == "gma5_clean_execution_20260622T075912Z_v1"


def test_p1a_ledger_remains_zero_row_and_unchanged(tmp_path: Path):
    _write_p1a_fixture(tmp_path)
    ledger = tmp_path / p1b.P1A_INPUTS["p1a_ledger"]
    before = ledger.read_text(encoding="utf-8")

    result = p1b.generate_preflight_files(tmp_path)

    assert result.dry_run["manual_paper_ledger_modified"] is False
    assert ledger.read_text(encoding="utf-8") == before
    assert list(csv.DictReader(ledger.open("r", encoding="utf-8"))) == []


def test_intake_template_is_never_accepted_as_submitted_intake(tmp_path: Path):
    _write_p1a_fixture(tmp_path)
    template_path = tmp_path / "p1b_template.json"
    _write_json(template_path, p1b.build_intake_template())

    with pytest.raises(p1b.P1BPreflightError, match="template is not a valid"):
        p1b.validate_future_intake_manifest(tmp_path, template_path)


def test_future_valid_synthetic_intake_passes_without_parsing_price_data(tmp_path: Path):
    _write_p1a_fixture(tmp_path)
    manifest_path = _valid_intake(tmp_path)

    result = p1b.validate_future_intake_manifest(tmp_path, manifest_path)

    assert result.status == "structural_preflight_passed_no_session_created"
    assert result.failed_requirements == []
    assert result.paper_session_created is False


def test_missing_intake_produces_exact_eight_failed_checks(tmp_path: Path):
    _write_p1a_fixture(tmp_path)

    result = p1b.validate_future_intake_manifest(tmp_path, None)

    assert result.failed_requirements == [
        "manual_intake_manifest_present",
        "session_data_snapshot_present",
        "session_data_snapshot_sha256_verified",
        "data_source_description_present",
        "source_last_observed_session_present",
        "data_cutoff_timestamp_present",
        "scheduled_decision_session_date_present",
        "operator_attestation_present",
    ]


def test_snapshot_hash_mismatch_fails_closed(tmp_path: Path):
    _write_p1a_fixture(tmp_path)
    manifest_path = _valid_intake(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["session_data_snapshot_sha256"] = "0" * 64
    _write_json(manifest_path, manifest)

    with pytest.raises(p1b.P1BPreflightError, match="sha256 mismatch"):
        p1b.validate_future_intake_manifest(tmp_path, manifest_path)


def test_recursive_traversal_globbing_and_walk_are_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_p1a_fixture(tmp_path)

    def fail_recursive(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("recursive traversal is prohibited")

    monkeypatch.setattr(Path, "rglob", fail_recursive)
    monkeypatch.setattr(Path, "glob", fail_recursive)
    monkeypatch.setattr(os, "walk", fail_recursive)

    p1b.generate_preflight_files(tmp_path)


def test_bulk_directory_hashing_is_prohibited(tmp_path: Path):
    with pytest.raises(p1b.P1BPreflightError, match="Refusing to hash a directory"):
        p1b.sha256_file(tmp_path)


def test_p1b_does_not_read_gma5_or_gma7_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_p1a_fixture(tmp_path)
    read_paths: list[str] = []
    original_read_text = Path.read_text

    def tracked_read_text(self: Path, *args: object, **kwargs: object) -> str:
        read_paths.append(str(self))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked_read_text)

    p1b.generate_preflight_files(tmp_path)

    assert not any("gma5_snapshot" in path or "gma7" in path.lower() for path in read_paths)


def test_p1b_cannot_calculate_targets_weights_performance_or_orders():
    source = Path(p1b.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    call_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)

    forbidden_imports = {"pandas", "numpy", "requests", "urllib", "yfinance", "sklearn"}
    forbidden_calls = {
        "calculate_target",
        "calculate_targets",
        "calculate_weights",
        "calculate_performance",
        "generate_order",
        "create_order",
        "run_backtest",
    }
    assert imported.isdisjoint(forbidden_imports)
    assert call_names.isdisjoint(forbidden_calls)


def test_p1b_cannot_write_p1a_ledger_or_session_template(tmp_path: Path):
    _write_p1a_fixture(tmp_path)
    ledger = tmp_path / p1b.P1A_INPUTS["p1a_ledger"]
    session_template = tmp_path / p1b.P1A_INPUTS["p1a_session_template"]
    before = (_sha256(ledger), _sha256(session_template))

    p1b.generate_preflight_files(tmp_path)

    assert (_sha256(ledger), _sha256(session_template)) == before


def test_real_dry_run_status_is_not_run_missing_preconditions(tmp_path: Path):
    _write_p1a_fixture(tmp_path)

    result = p1b.generate_preflight_files(tmp_path)

    assert result.dry_run["preflight_dry_run_status"] == "not_run_missing_preconditions"
    assert result.dry_run["paper_session_created"] is False
    assert result.dry_run["manual_paper_ledger_modified"] is False


def test_output_generation_is_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_p1a_fixture(first)
    _write_p1a_fixture(second)

    p1b.generate_preflight_files(first)
    p1b.generate_preflight_files(second)

    for key, relative_path in p1b.OUTPUT_PATHS.items():
        assert (first / relative_path).read_text(encoding="utf-8") == (
            second / relative_path
        ).read_text(encoding="utf-8"), key
