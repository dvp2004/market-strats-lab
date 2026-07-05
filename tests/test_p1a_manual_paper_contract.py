from __future__ import annotations

import ast
import csv
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from market_strats.global_multi_asset import p1a_manual_paper_contract as p1a


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


def _write_parent_snapshot(root: Path) -> Path:
    config = {
        "variants": [
            "gma5_equal_weight_atomic_sleeves_v1",
            "gma5_risk_weighted_atomic_sleeves_v1",
        ],
        "atomic_sleeves": [
            {"trial_id": parent_trial_id, "family": sleeve_id}
            for sleeve_id, parent_trial_id in p1a.PARENT_TRIAL_IDS.items()
        ],
        "cost_scenarios": {
            "baseline_1bps": 1.0,
            "stressed_10bps": 10.0,
            "stressed_25bps": 25.0,
            "severe_50bps": 50.0,
        },
    }
    _write_text(
        root / p1a.PARENT_FILES["gma5_config"],
        yaml.safe_dump(config, sort_keys=False),
    )
    clean_manifest = {
        "clean_execution_run_id": p1a.PARENT_EXECUTION_REFERENCE,
        "runtime_replay_trace": {
            "variant_ids_replayed": [p1a.STRATEGY_ID],
            "composite_target_input_hashes_by_variant": {p1a.STRATEGY_ID: "target_hash"},
        },
    }
    _write_json(root / p1a.PARENT_FILES["clean_execution_manifest"], clean_manifest)
    _write_json(
        root / p1a.PARENT_FILES["ensemble_manifest"],
        {
            "run_id": p1a.PARENT_EXECUTION_REFERENCE,
            "composite_replay_method": "netted_underlying_etf_targets_through_shared_replay_adapter",
        },
    )
    trace = {
        "clean_execution_run_id": p1a.PARENT_EXECUTION_REFERENCE,
        "allocation_input_type": "sleeve_etf_target_weights",
        "replay_input_type": "netted_composite_etf_target_weights",
        "equity_curve_averaging_invoked": False,
        "runtime_evidence": {"variant_ids_replayed": [p1a.STRATEGY_ID]},
    }
    _write_json(root / p1a.PARENT_FILES["no_equity_curve_averaging_trace"], trace)
    _write_json(
        root / p1a.PARENT_FILES["runtime_replay_trace"],
        {"variant_ids_replayed": [p1a.STRATEGY_ID]},
    )
    _write_json(
        root / p1a.PARENT_FILES["cost_scenario_manifest"],
        {
            "cost_scenarios": [
                "baseline_1bps",
                "stressed_10bps",
                "stressed_25bps",
                "severe_50bps",
            ],
            "variants": [p1a.STRATEGY_ID],
        },
    )
    sleeve_rows = [
        {
            "variant_id": p1a.STRATEGY_ID,
            "decision_date": "2012-05-31",
            "sleeve_id": parent_trial_id,
            "sleeve_family": sleeve_id,
            "sleeve_allocation_weight": 0.25,
            "status": "available",
        }
        for sleeve_id, parent_trial_id in p1a.PARENT_TRIAL_IDS.items()
    ]
    _write_csv(
        root / p1a.PARENT_FILES["monthly_sleeve_weights"],
        sleeve_rows,
        [
            "variant_id",
            "decision_date",
            "sleeve_id",
            "sleeve_family",
            "sleeve_allocation_weight",
            "status",
        ],
    )
    netting_rows = [
        {
            "decision_date": "2012-05-31",
            "variant_id": p1a.STRATEGY_ID,
            "ticker": "SPY",
            "sleeve_weighted_target_sum": 1.0,
            "net_composite_target_weight": 1.0,
            "bil_residual_weight": 0.0,
            "final_target_weight": 1.0,
        }
    ]
    _write_csv(
        root / p1a.PARENT_FILES["composite_target_netting_audit"],
        netting_rows,
        [
            "decision_date",
            "variant_id",
            "ticker",
            "sleeve_weighted_target_sum",
            "net_composite_target_weight",
            "bil_residual_weight",
            "final_target_weight",
        ],
    )
    _write_csv(
        root / p1a.PARENT_FILES["monthly_etf_targets"],
        [
            {
                "variant_id": p1a.STRATEGY_ID,
                "decision_date": "2012-05-31",
                "symbol": "SPY",
                "composite_etf_target_weight": 1.0,
            }
        ],
        ["variant_id", "decision_date", "symbol", "composite_etf_target_weight"],
    )
    return root


def test_p1_worktree_is_detached_from_86a49fc():
    head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()

    assert head == "86a49fc"
    assert branch == ""


def test_frozen_gma5_parent_evidence_is_required_and_external_read_only(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    parent = p1a.resolve_parent_reference(snapshot)

    assert parent.hashes
    assert set(parent.hashes) == {
        "gma5_config",
        "clean_execution_manifest",
        "ensemble_manifest",
        "no_equity_curve_averaging_trace",
        "runtime_replay_trace",
        "cost_scenario_manifest",
    }
    assert p1a.PARENT_SNAPSHOT_ROOT.is_absolute()
    assert all(
        not str(path).startswith(str(snapshot / "reports/global_multi_asset_alpha/p1a"))
        for path in p1a.OUTPUT_PATHS.values()
    )


def test_parent_strategy_id_and_execution_reference_are_exact(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    parent = p1a.resolve_parent_reference(snapshot)
    payload = p1a.parent_resolution_payload(
        parent,
        snapshot,
        {name: snapshot / relative for name, relative in p1a.PARENT_FILES.items()},
    )

    assert payload["strategy_id"] == "gma5_equal_weight_atomic_sleeves_v1"
    assert payload["parent_execution_reference"] == "gma5_clean_execution_20260622T075912Z_v1"


def test_all_four_sleeve_ids_are_exact(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    parent = p1a.resolve_parent_reference(snapshot)
    payload = p1a.parent_resolution_payload(
        parent,
        snapshot,
        {name: snapshot / relative for name, relative in p1a.PARENT_FILES.items()},
    )

    assert [row["sleeve_id"] for row in payload["sleeves"]] == p1a.SLEEVE_IDS


def test_equal_weighting_across_all_four_sleeves_is_required(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    path = snapshot / p1a.PARENT_FILES["monthly_sleeve_weights"]
    rows = list(csv.DictReader(path.open("r", encoding="utf-8")))
    rows[0]["sleeve_allocation_weight"] = "0.30"
    _write_csv(path, rows, list(rows[0]))

    with pytest.raises(p1a.P1AContractError, match="sleeve weights"):
        p1a.resolve_parent_reference(snapshot)


def test_netted_composite_targets_are_required(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    path = snapshot / p1a.PARENT_FILES["composite_target_netting_audit"]
    rows = [{"variant_id": p1a.STRATEGY_ID, "decision_date": "2012-05-31"}]
    _write_csv(path, rows, list(rows[0]))

    with pytest.raises(p1a.P1AContractError, match="required columns"):
        p1a.resolve_parent_reference(snapshot)


def test_sleeve_equity_curve_averaging_is_prohibited(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    path = snapshot / p1a.PARENT_FILES["no_equity_curve_averaging_trace"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["equity_curve_averaging_invoked"] = True
    _write_json(path, payload)

    with pytest.raises(p1a.P1AContractError, match="equity_curve_averaging"):
        p1a.resolve_parent_reference(snapshot)


def test_gma7_dependency_is_exactly_none(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    parent = p1a.resolve_parent_reference(snapshot)
    contract = p1a.build_contract_yaml(parent)

    assert contract["gma7_dependency"] == "none"
    assert contract["gma7_outputs_can_modify_p1_rules"] is False
    assert contract["gma7_no_ensemble_result_changes_p1_strategy"] is False


def test_empty_manual_paper_ledger_has_zero_rows_and_exact_headers(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    p1a.generate_manual_paper_contract_files(tmp_path / "repo", snapshot)
    ledger = tmp_path / "repo" / p1a.OUTPUT_PATHS["ledger"]
    lines = ledger.read_text(encoding="utf-8").splitlines()

    assert lines == [",".join(p1a.LEDGER_FIELDS)]


def test_no_future_paper_session_or_target_file_exists(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    result = p1a.generate_manual_paper_contract_files(tmp_path / "repo", snapshot)

    assert result.lock["future_paper_session_created"] is False
    assert result.lock["target_generated"] is False
    assert not any("target_file" in str(path) for path in result.output_paths.values())


def test_every_future_preflight_requirement_is_mandatory():
    assert p1a.PREFLIGHT_REQUIREMENTS == [
        "parent_reference_verified",
        "strategy_identity_verified",
        "all_four_sleeves_verified",
        "netted_composite_target_method_verified",
        "input_snapshot_present",
        "input_snapshot_hash_verified",
        "source_last_observed_session_present",
        "monthly_decision_timing_verified",
        "target_weight_sum_valid",
        "no_discretionary_override",
        "paper_only_boundary_verified",
    ]


def test_failed_preflight_maps_to_skipped_manual_paper_status():
    assert p1a.failed_preflight_status(["input_snapshot_present"]) == {
        "manual_decision": "skipped_due_warning",
        "execution_status": "skipped",
        "paper_session_status": "invalid_or_skipped_manual_paper_session",
    }


def test_no_data_fetch_target_generation_performance_broker_execution_or_live_imports():
    source = Path(p1a.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = [
        "requests",
        "urllib",
        "yfinance",
        "pandas",
        "sklearn",
        "gma4_replay_adapter",
        "gma5_atomic_sleeve_ensemble",
        "broker",
        "live",
    ]
    assert not any(any(fragment in module for fragment in forbidden) for module in imported)


def test_generation_does_not_attempt_recursive_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")

    def fail_recursive(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("recursive traversal is prohibited")

    monkeypatch.setattr(Path, "rglob", fail_recursive)
    monkeypatch.setattr(Path, "glob", fail_recursive)

    p1a.generate_manual_paper_contract_files(tmp_path / "repo", snapshot)


def test_generation_uses_only_finite_parent_file_allowlist(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    result = p1a.generate_manual_paper_contract_files(tmp_path / "repo", snapshot)

    assert result.lock["parent_files_hashed_count"] == 6
    assert result.lock["bounded_history_rows_read"]["monthly_sleeve_weights"] == 4
    assert result.lock["bounded_history_rows_read"]["composite_target_netting_audit"] == 1
    assert result.lock["bounded_history_rows_read"]["monthly_etf_targets"] == 1
    assert result.lock["generated_artifact_hash_count_excluding_lock"] == 8


def test_no_prior_gma_or_master_file_is_modified():
    status = subprocess.check_output(["git", "status", "--short"], text=True).splitlines()
    changed_paths = [line[3:] for line in status]
    forbidden = ["gma4_", "gma5_", "gma6_", "gma7", "gma_research_", "master"]
    assert not any(any(fragment in path for fragment in forbidden) for path in changed_paths)


def test_generation_is_deterministic(tmp_path: Path):
    snapshot = _write_parent_snapshot(tmp_path / "snapshot")
    first = tmp_path / "first"
    second = tmp_path / "second"

    p1a.generate_manual_paper_contract_files(first, snapshot)
    p1a.generate_manual_paper_contract_files(second, snapshot)

    for key, relative_path in p1a.OUTPUT_PATHS.items():
        assert (first / relative_path).read_text(encoding="utf-8") == (
            second / relative_path
        ).read_text(encoding="utf-8"), key
