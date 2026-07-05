from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from market_strats.global_multi_asset import p1c_local_adjusted_price_snapshot as p1c


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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_p1_fixture(repo: Path) -> None:
    p1a_contract = {
        "phase_id": "p1a_manual_paper_contract_v1",
        "strategy_id": p1c.STRATEGY_ID,
        "parent_execution_reference": p1c.PARENT_EXECUTION_REFERENCE,
        "paper_mode": "manual_observation_only",
        "real_money": "prohibited",
        "broker_connection": "prohibited",
        "trade_execution": "prohibited",
        "automated_order_generation": "prohibited",
        "gma7_dependency": "none",
    }
    p1b_contract = {
        "phase_id": "p1b_manual_data_intake_preflight_v1",
        "strategy_id": p1c.STRATEGY_ID,
        "parent_execution_reference": p1c.PARENT_EXECUTION_REFERENCE,
    }
    p1a_parent_resolution = {
        "phase_id": "p1a_manual_paper_contract_v1",
        "strategy_id": p1c.STRATEGY_ID,
        "parent_execution_reference": p1c.PARENT_EXECUTION_REFERENCE,
        "parent_reference_manifest_sha256": "parent-hash",
    }
    _write_text(
        repo / p1c.P1_INPUTS["p1a_contract"],
        yaml.safe_dump(p1a_contract, sort_keys=False),
    )
    _write_text(
        repo / p1c.P1_INPUTS["p1b_contract"],
        yaml.safe_dump(p1b_contract, sort_keys=False),
    )
    _write_json(repo / p1c.P1_INPUTS["p1a_parent_resolution"], p1a_parent_resolution)
    _write_csv(repo / p1c.P1_INPUTS["p1a_ledger"], [], p1c.LEDGER_FIELDS)
    _write_csv(repo / p1c.P1_INPUTS["p1a_session_template"], [], p1c.LEDGER_FIELDS)
    p1a_lock = {
        "phase_id": "p1a_manual_paper_contract_v1",
        "strategy_id": p1c.STRATEGY_ID,
        "parent_execution_reference": p1c.PARENT_EXECUTION_REFERENCE,
        "paper_mode": "manual_observation_only",
        "real_money": "prohibited",
        "broker_connection": "prohibited",
        "trade_execution": "prohibited",
        "automated_order_generation": "prohibited",
        "gma7_dependency": "none",
        "ledger_row_count": 0,
    }
    _write_json(repo / p1c.P1_INPUTS["p1a_lock"], p1a_lock)
    p1b_dry_run = {
        "phase_id": "p1b_manual_data_intake_preflight_v1",
        "strategy_id": p1c.STRATEGY_ID,
        "parent_execution_reference": p1c.PARENT_EXECUTION_REFERENCE,
        "preflight_dry_run_status": "not_run_missing_preconditions",
        "paper_session_created": False,
        "manual_paper_ledger_modified": False,
        "target_generated": False,
        "performance_result_created": False,
        "broker_instruction_created": False,
        "real_money_action_created": False,
    }
    _write_json(repo / p1c.P1_INPUTS["p1b_dry_run"], p1b_dry_run)
    _write_json(
        repo / p1c.P1_INPUTS["p1b_execution_manifest"],
        {"phase_id": "p1b_manual_data_intake_preflight_v1", "post_processing_only": True},
    )
    _write_json(
        repo / p1c.P1_INPUTS["p1b_lock"],
        {
            "phase_id": "p1b_manual_data_intake_preflight_v1",
            "strategy_id": p1c.STRATEGY_ID,
            "parent_execution_reference": p1c.PARENT_EXECUTION_REFERENCE,
            "preflight_dry_run_status": "not_run_missing_preconditions",
            "paper_session_created": False,
            "manual_paper_ledger_modified": False,
        },
    )


def _write_gma5_refs(root: Path) -> dict[str, Path]:
    config = {
        "variants": [p1c.STRATEGY_ID],
        "atomic_sleeves": [
            {"trial_id": "gma4_abs_trend_12m_equal_weight_v1", "family": "absolute_trend"},
            {
                "trial_id": "gma4_xsmom_12m_top5_inverse_vol_v1",
                "family": "cross_sectional_momentum",
            },
            {
                "trial_id": "gma4_defensive_drawdown_guard_v1",
                "family": "defensive_risk_regime",
            },
            {
                "trial_id": "gma4_defensive_spy_200d_rotation_v1",
                "family": "defensive_risk_regime",
            },
        ],
    }
    refs = {
        "gma5_config": root / "gma5_atomic_sleeve_ensemble_v1.yaml",
        "clean_execution_manifest": root / "gma5_clean_execution_manifest_v1.json",
        "gma5_source_snapshot": root / "gma5_atomic_sleeve_ensemble.py",
    }
    _write_text(refs["gma5_config"], yaml.safe_dump(config, sort_keys=False))
    _write_json(
        refs["clean_execution_manifest"],
        {
            "clean_execution_run_id": p1c.PARENT_EXECUTION_REFERENCE,
            "runtime_replay_trace": {"variant_ids_replayed": [p1c.STRATEGY_ID]},
        },
    )
    _write_text(refs["gma5_source_snapshot"], "# Dummy\n")
    return refs


def _patch_refs(monkeypatch: pytest.MonkeyPatch, refs: dict[str, Path]) -> None:
    monkeypatch.setattr(p1c, "GMA5_REFERENCE_FILES", refs)


def _sessions(end: date, count: int) -> list[date]:
    sessions: list[date] = []
    current = end
    while len(sessions) < count:
        if current.weekday() < 5:
            sessions.append(current)
        current -= timedelta(days=1)
    return list(reversed(sessions))


def _session_provider(master_sessions: list[date]):
    def provider(start_date: date, end_date: date) -> list[date]:
        return [item for item in master_sessions if start_date <= item <= end_date]

    return provider


def _write_snapshot(path: Path, sessions: list[date], mutation: str | None = None) -> None:
    columns = p1c.SNAPSHOT_COLUMNS.copy()
    if mutation == "reordered_header":
        columns[1], columns[2] = columns[2], columns[1]
    if mutation == "substituted_ticker":
        columns[1] = "VOO"
    if mutation == "omitted_ticker":
        columns = columns[:-1]
    if mutation == "extra_ticker":
        columns.append("VTI")
    rows = []
    used_sessions = sessions.copy()
    if mutation == "duplicate_date":
        used_sessions[-1] = used_sessions[-2]
    if mutation == "unordered_date":
        used_sessions[-1], used_sessions[-2] = used_sessions[-2], used_sessions[-1]
    if mutation == "invalid_date":
        raw_dates = [item.isoformat() for item in used_sessions]
        raw_dates[-1] = "not-a-date"
    else:
        raw_dates = [item.isoformat() for item in used_sessions]
    for raw_date in raw_dates:
        row = {column: "100.0" for column in columns}
        row["session_date"] = raw_date
        rows.append(row)
    if mutation == "missing_price":
        rows[-1]["SPY"] = ""
    if mutation == "non_numeric_price":
        rows[-1]["SPY"] = "abc"
    if mutation == "non_finite_price":
        rows[-1]["SPY"] = "nan"
    if mutation == "zero_price":
        rows[-1]["SPY"] = "0"
    if mutation == "negative_price":
        rows[-1]["SPY"] = "-1"
    _write_csv(path, rows, columns)


def _write_manifest(repo: Path, snapshot: Path, scheduled: date, registry_hash: str = "x") -> Path:
    manifest = {
        "intake_id": "manual_intake_001",
        "manual_intake_timestamp_utc": "2026-01-30T21:00:00Z",
        "scheduled_decision_session_date": scheduled.isoformat(),
        "session_data_snapshot_path": str(snapshot),
        "session_data_snapshot_sha256": _sha256(snapshot),
        "data_source_description": "manual local adjusted close snapshot",
        "source_last_observed_session": scheduled.isoformat(),
        "data_cutoff_timestamp_utc": "2026-01-30T21:00:00Z",
        "snapshot_format": "csv_adjusted_close_wide_v1",
        "snapshot_schema_version": "p1c_adjusted_price_snapshot_v1",
        "operator_attestation": "operator supplied snapshot locally",
        "p1c_snapshot_schema_hash": hashlib.sha256(
            p1c.SNAPSHOT_HEADER_LINE.encode("utf-8")
        ).hexdigest(),
        "p1c_required_history_registry_hash": registry_hash,
    }
    path = repo / "manual" / "manifest.json"
    _write_json(path, manifest)
    return path


def test_p1a_and_p1b_parent_locks_and_boundaries_are_verified(tmp_path: Path):
    _write_p1_fixture(tmp_path)

    loaded = p1c.load_p1_inputs(tmp_path)

    assert loaded.p1a_lock["strategy_id"] == p1c.STRATEGY_ID
    assert loaded.p1b_dry_run["preflight_dry_run_status"] == "not_run_missing_preconditions"


def test_exact_22_ticker_header_order_is_required(tmp_path: Path):
    snapshot = tmp_path / "snapshot.csv"
    sessions = _sessions(date(2026, 1, 30), 253)
    _write_snapshot(snapshot, sessions)
    rows, failed, _dates = p1c.inspect_snapshot(snapshot)

    assert rows
    assert "snapshot_header_exact" not in failed


@pytest.mark.parametrize(
    "mutation",
    ["reordered_header", "substituted_ticker", "omitted_ticker", "extra_ticker"],
)
def test_reordered_substituted_omitted_or_extra_ticker_fails(tmp_path: Path, mutation: str):
    snapshot = tmp_path / "snapshot.csv"
    _write_snapshot(snapshot, _sessions(date(2026, 1, 30), 253), mutation)

    _rows, failed, _dates = p1c.inspect_snapshot(snapshot)

    assert "snapshot_header_exact" in failed


@pytest.mark.parametrize("mutation", ["duplicate_date", "unordered_date", "invalid_date"])
def test_duplicate_unordered_or_invalid_dates_fail(tmp_path: Path, mutation: str):
    snapshot = tmp_path / "snapshot.csv"
    _write_snapshot(snapshot, _sessions(date(2026, 1, 30), 253), mutation)

    _rows, failed, _dates = p1c.inspect_snapshot(snapshot)

    assert any(
        item.startswith("snapshot_session_dates") or item.endswith("duplicate_dates")
        for item in failed
    )


@pytest.mark.parametrize(
    "mutation",
    ["missing_price", "non_numeric_price", "non_finite_price", "zero_price", "negative_price"],
)
def test_bad_adjusted_prices_fail(tmp_path: Path, mutation: str):
    snapshot = tmp_path / "snapshot.csv"
    _write_snapshot(snapshot, _sessions(date(2026, 1, 30), 253), mutation)

    _rows, failed, _dates = p1c.inspect_snapshot(snapshot)

    assert (
        "snapshot_has_no_missing_values" in failed
        or "snapshot_has_only_positive_finite_adjusted_prices" in failed
    )


def test_snapshot_with_insufficient_parent_derived_history_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_p1_fixture(tmp_path)
    _patch_refs(monkeypatch, _write_gma5_refs(tmp_path / "refs"))
    sessions = _sessions(date(2026, 1, 30), 252)
    snapshot = tmp_path / "manual" / "snapshot.csv"
    _write_snapshot(snapshot, sessions)
    manifest = _write_manifest(tmp_path, snapshot, date(2026, 1, 30))

    result = p1c.validate_local_snapshot_intake(
        tmp_path, manifest, session_provider=_session_provider(sessions)
    )

    assert result.status == "invalid_local_snapshot_no_target_generated"
    assert "snapshot_history_meets_frozen_gma5_requirement" in result.failed_requirements


def test_synthetic_valid_snapshot_passes_without_target_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_p1_fixture(tmp_path)
    _patch_refs(monkeypatch, _write_gma5_refs(tmp_path / "refs"))
    sessions = _sessions(date(2026, 1, 30), 253)
    snapshot = tmp_path / "manual" / "snapshot.csv"
    _write_snapshot(snapshot, sessions)
    manifest = _write_manifest(tmp_path, snapshot, date(2026, 1, 30))

    result = p1c.validate_local_snapshot_intake(
        tmp_path, manifest, session_provider=_session_provider(sessions)
    )

    assert result.status == "validated_local_snapshot_no_target_generated"
    assert result.target_generated is False
    assert result.paper_session_created is False


def test_mid_month_stale_and_post_decision_snapshot_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_p1_fixture(tmp_path)
    _patch_refs(monkeypatch, _write_gma5_refs(tmp_path / "refs"))
    sessions = _sessions(date(2026, 1, 30), 253)
    provider = _session_provider(sessions)
    snapshot = tmp_path / "manual" / "snapshot.csv"
    _write_snapshot(snapshot, sessions)
    mid_manifest = _write_manifest(tmp_path, snapshot, date(2026, 1, 29))

    mid_result = p1c.validate_local_snapshot_intake(
        tmp_path, mid_manifest, session_provider=provider
    )
    assert "snapshot_cutoff_is_consistent" in mid_result.failed_requirements

    stale_rows = sessions[:-1]
    _write_snapshot(snapshot, stale_rows)
    stale_manifest = _write_manifest(tmp_path, snapshot, date(2026, 1, 30))
    stale_result = p1c.validate_local_snapshot_intake(
        tmp_path, stale_manifest, session_provider=provider
    )
    assert (
        "snapshot_last_session_matches_declared_source_last_observed_session"
        in stale_result.failed_requirements
    )


def test_non_session_inserted_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_p1_fixture(tmp_path)
    _patch_refs(monkeypatch, _write_gma5_refs(tmp_path / "refs"))
    sessions = _sessions(date(2026, 1, 30), 253)
    snapshot_sessions = sessions.copy()
    snapshot_sessions[-2] = date(2026, 1, 25)
    snapshot_sessions.sort()
    snapshot = tmp_path / "manual" / "snapshot.csv"
    _write_snapshot(snapshot, snapshot_sessions)
    manifest = _write_manifest(tmp_path, snapshot, date(2026, 1, 30))

    result = p1c.validate_local_snapshot_intake(
        tmp_path, manifest, session_provider=_session_provider(sessions)
    )

    assert "snapshot_session_dates_valid" in result.failed_requirements


def test_validator_never_calculates_targets_weights_performance_or_orders():
    source = Path(p1c.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    assert not any("gma5_atomic_sleeve_ensemble" in module for module in imported)
    assert calls.isdisjoint(
        {
            "calculate_signal",
            "calculate_signals",
            "calculate_weights",
            "calculate_targets",
            "calculate_returns",
            "calculate_performance",
            "generate_order",
        }
    )


def test_no_recursive_traversal_or_directory_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_p1_fixture(tmp_path)
    _patch_refs(monkeypatch, _write_gma5_refs(tmp_path / "refs"))

    def fail_recursive(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("recursive traversal is prohibited")

    monkeypatch.setattr(Path, "rglob", fail_recursive)
    monkeypatch.setattr(Path, "glob", fail_recursive)
    monkeypatch.setattr(os, "walk", fail_recursive)

    p1c.generate_p1c_files(tmp_path)
    with pytest.raises(p1c.P1CLocalSnapshotError, match="Refusing to hash a directory"):
        p1c.sha256_file(tmp_path)


def test_real_dry_run_has_exact_missing_manual_input_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_p1_fixture(tmp_path)
    _patch_refs(monkeypatch, _write_gma5_refs(tmp_path / "refs"))

    result = p1c.generate_p1c_files(tmp_path)

    assert result["dry_run"]["p1c_template_only_dry_run_status"] == (
        "not_run_no_manual_snapshot_or_manifest"
    )
    assert result["dry_run"]["failed_requirements"] == p1c.DRY_RUN_FAILED_REQUIREMENTS


def test_p1a_ledger_and_template_remain_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_p1_fixture(tmp_path)
    _patch_refs(monkeypatch, _write_gma5_refs(tmp_path / "refs"))
    ledger = tmp_path / p1c.P1_INPUTS["p1a_ledger"]
    template = tmp_path / p1c.P1_INPUTS["p1a_session_template"]
    before = (_sha256(ledger), _sha256(template))

    p1c.generate_p1c_files(tmp_path)

    assert (_sha256(ledger), _sha256(template)) == before


def test_generation_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_p1_fixture(first)
    _write_p1_fixture(second)
    refs = _write_gma5_refs(tmp_path / "refs")
    _patch_refs(monkeypatch, refs)

    p1c.generate_p1c_files(first)
    p1c.generate_p1c_files(second)

    for key, relative_path in p1c.OUTPUT_PATHS.items():
        assert (first / relative_path).read_text(encoding="utf-8") == (
            second / relative_path
        ).read_text(encoding="utf-8"), key
