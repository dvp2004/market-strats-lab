from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import pytest
import yaml

from market_strats.global_multi_asset import gma7d_development_gate_integration as gma7d


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _base_parent_payload() -> dict[str, object]:
    return {
        "gma6_snapshot_manifest_hash": gma7d.EXPECTED_GMA6_SNAPSHOT_MANIFEST_HASH,
        "gma6b_data_bundle_manifest_hash": gma7d.EXPECTED_GMA6B_DATA_BUNDLE_MANIFEST_HASH,
        "normalised_bundle_hash": gma7d.EXPECTED_NORMALISED_BUNDLE_HASH,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _gate_rows(all_pass_model: str | None = None) -> list[dict[str, object]]:
    failure_by_model = {
        "bounded_gradient_boosted_tree_return_rank_model": {
            "aggregate_maximum_drawdown_worsening_vs_benchmark_lte_0_03"
        },
        "deterministic_cross_asset_regime_model": {
            "positive_chronological_test_folds_at_least_3",
            "maximum_single_fold_share_of_total_active_return_lte_0_50",
            "aggregate_active_return_positive",
        },
        "regularised_linear_return_rank_model": {
            "maximum_single_fold_share_of_total_active_return_lte_0_50",
            "aggregate_maximum_drawdown_worsening_vs_benchmark_lte_0_03",
        },
    }
    if all_pass_model:
        failure_by_model[all_pass_model] = set()
    rows = []
    for model_id in gma7d.RETURN_MODEL_IDS:
        for gate_name in gma7d.GATE_NAMES:
            rows.append(
                {
                    "model_id": model_id,
                    "gate_name": gate_name,
                    "gate_status": "fail" if gate_name in failure_by_model[model_id] else "pass",
                    "positive_chronological_test_folds": 3,
                    "single_fold_share": 0.4,
                    "aggregate_net_active_return": 0.1,
                    "notes": "development_only_no_execution_decision",
                }
            )
    return rows


def _write_csv_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_metric_rows(path: Path, count: int) -> None:
    rows = [
        {
            "model_id": "regularised_linear_return_rank_model",
            "cost_scenario": "stressed_10bps",
            "outer_fold_id": f"row_{idx}",
            "net_return": 0.0,
        }
        for idx in range(count)
    ]
    _write_csv_rows(path, rows)


def _write_fixture(root: Path, *, all_pass_model: str | None = None) -> None:
    for artifact_id, relative_path in gma7d.PARENT_ARTIFACTS.items():
        path = root / relative_path
        if artifact_id == "gma7c_contract":
            _write_text(
                path,
                yaml.safe_dump(
                    {
                        "phase_id": "gma7c_development_model_evaluation_v1",
                        "outer_folds": [{"fold_id": f"fold_{idx}"} for idx in range(1, 5)],
                    },
                    sort_keys=False,
                ),
            )
        elif artifact_id in {"gma7a_contract", "gma7b_contract"}:
            _write_text(path, "phase_id: synthetic_parent\n")
        elif artifact_id == "gma7a_lock":
            _write_json(path, {"phase_id": "gma7a_predictive_ensemble_contract_v1"})
        elif artifact_id in {"gma7b_manifest", "gma7b_lock"}:
            payload = {
                **_base_parent_payload(),
                "core22_universe_hash": "core22_hash",
                "monthly_feature_store_hash": "feature_store_hash",
                "feature_row_count": gma7d.EXPECTED_GMA7B_FEATURE_ROWS,
                "missing_feature_row_count": gma7d.EXPECTED_GMA7B_MISSING_FEATURE_ROWS,
            }
            _write_json(path, payload)
        elif artifact_id == "gma7c_label_manifest":
            _write_json(
                path,
                {
                    **_base_parent_payload(),
                    "label_row_count": gma7d.EXPECTED_GMA7C_LABEL_ROWS,
                    "lockbox_used": False,
                },
            )
        elif artifact_id in {"gma7c_execution_manifest", "gma7c_lock"}:
            _write_json(
                path,
                {
                    **_base_parent_payload(),
                    "label_row_count": gma7d.EXPECTED_GMA7C_LABEL_ROWS,
                    "score_row_count": gma7d.EXPECTED_GMA7C_SCORE_ROWS,
                    "component_metric_row_count": gma7d.EXPECTED_GMA7C_COMPONENT_METRIC_ROWS,
                    "risk_overlay_metric_row_count": gma7d.EXPECTED_GMA7C_RISK_METRIC_ROWS,
                    "gate_row_count": gma7d.EXPECTED_GMA7C_GATE_ROWS,
                    "lockbox_used": False,
                    "equal_weight_ensemble_built": False,
                    "paper_broker_or_live_path_created": False,
                    "gma7a_test_guard_change_disclosure": True,
                    "gma7a_test_guard_change_scope": gma7d.TEST_GUARD_SCOPE,
                },
            )
        elif artifact_id == "gma7c_gate_board":
            _write_csv_rows(path, _gate_rows(all_pass_model=all_pass_model))
        elif artifact_id == "gma7c_component_metrics":
            _write_metric_rows(path, gma7d.EXPECTED_GMA7C_COMPONENT_METRIC_ROWS)
        elif artifact_id == "gma7c_risk_overlay_metrics":
            _write_metric_rows(path, gma7d.EXPECTED_GMA7C_RISK_METRIC_ROWS)


def test_all_required_parent_artifacts_and_hashes_are_verified(tmp_path: Path):
    _write_fixture(tmp_path)
    evidence = gma7d.load_parent_evidence(tmp_path)
    verification = gma7d.build_parent_verification(evidence)

    assert set(evidence.hashes) == set(gma7d.PARENT_ARTIFACTS)
    assert len(verification) == len(gma7d.PARENT_ARTIFACTS)
    assert verification["verification_status"].eq("verified").all()
    assert verification["gma7a_test_guard_change_disclosure"].eq(True).all()


def test_gma7b_and_gma7c_count_checks_are_exact(tmp_path: Path):
    _write_fixture(tmp_path)
    manifest_path = tmp_path / gma7d.PARENT_ARTIFACTS["gma7b_manifest"]
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["feature_row_count"] = gma7d.EXPECTED_GMA7B_FEATURE_ROWS - 1
    _write_json(manifest_path, payload)

    with pytest.raises(gma7d.GMA7DIntegrationError, match="feature_row_count"):
        gma7d.load_parent_evidence(tmp_path)


def test_gma7c_lockbox_use_must_be_false(tmp_path: Path):
    _write_fixture(tmp_path)
    lock_path = tmp_path / gma7d.PARENT_ARTIFACTS["gma7c_lock"]
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    payload["lockbox_used"] = True
    _write_json(lock_path, payload)

    with pytest.raises(gma7d.GMA7DIntegrationError, match="lockbox_used"):
        gma7d.load_parent_evidence(tmp_path)


def test_three_return_models_and_exactly_fifteen_gate_rows_are_required(tmp_path: Path):
    _write_fixture(tmp_path)
    evidence = gma7d.load_parent_evidence(tmp_path)

    assert sorted(evidence.gate_board["model_id"].unique()) == gma7d.RETURN_MODEL_IDS
    assert len(evidence.gate_board) == 15


def test_exactly_five_gates_are_required_per_model_id(tmp_path: Path):
    _write_fixture(tmp_path)
    gate_path = tmp_path / gma7d.PARENT_ARTIFACTS["gma7c_gate_board"]
    rows = _gate_rows()[:-1]
    _write_csv_rows(gate_path, rows)

    with pytest.raises(gma7d.GMA7DIntegrationError, match="row count"):
        gma7d.load_parent_evidence(tmp_path)


def test_model_with_one_failed_gate_is_not_eligible(tmp_path: Path):
    _write_fixture(tmp_path)
    evidence = gma7d.load_parent_evidence(tmp_path)
    board = gma7d.build_component_freeze_board(evidence)
    tree = board[board["model_id"] == "bounded_gradient_boosted_tree_return_rank_model"].iloc[0]

    assert tree["fully_qualifying_status"] == "not_fully_qualifying"
    assert tree["fixed_ensemble_integration_status"] == gma7d.RETURN_BLOCK_STATUS
    assert "aggregate_maximum_drawdown_worsening" in tree["failed_gate_names"]


def test_only_all_pass_gate_groups_are_fully_qualifying(tmp_path: Path):
    _write_fixture(tmp_path, all_pass_model="bounded_gradient_boosted_tree_return_rank_model")
    evidence = gma7d.load_parent_evidence(tmp_path)
    group = evidence.gate_board[
        evidence.gate_board["model_id"] == "bounded_gradient_boosted_tree_return_rank_model"
    ]

    assert gma7d.model_is_fully_qualifying(group) is True
    with pytest.raises(gma7d.GMA7DIntegrationError, match="fully qualifying"):
        gma7d.build_component_freeze_board(evidence)


def test_current_frozen_source_outcome_requires_zero_eligible_models(tmp_path: Path):
    _write_fixture(tmp_path)
    evidence = gma7d.load_parent_evidence(tmp_path)
    board = gma7d.build_component_freeze_board(evidence)
    lock = gma7d.build_no_ensemble_lock(evidence, board)

    assert lock["fully_qualifying_component_count"] == 0
    assert lock["ensemble_status"] == gma7d.ENSEMBLE_STATUS
    assert lock["gma7_v1_development_state"] == gma7d.DEVELOPMENT_STATE


def test_risk_overlays_are_not_integrated_when_eligible_count_is_zero(tmp_path: Path):
    _write_fixture(tmp_path)
    evidence = gma7d.load_parent_evidence(tmp_path)
    board = gma7d.build_component_freeze_board(evidence)
    lock = gma7d.build_no_ensemble_lock(evidence, board)

    assert lock["risk_overlay_integration_status"] == gma7d.RISK_OVERLAY_STATUS


def test_no_model_fit_score_replay_performance_paper_broker_or_live_imports():
    source = Path(gma7d.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = [
        "sklearn",
        "gma4_replay_adapter",
        "gma5",
        "gma6",
        "gma7c_development_models",
        "broker",
        "live",
        "paper",
    ]
    assert not any(any(fragment in module for fragment in forbidden) for module in imported)


def test_output_paths_are_gma7d_only():
    assert all("gma7d" in str(path) for path in gma7d.OUTPUT_PATHS.values())


def test_output_generation_is_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_fixture(first)
    _write_fixture(second)

    gma7d.generate_gate_integration_files(first)
    gma7d.generate_gate_integration_files(second)

    for key, relative_path in gma7d.OUTPUT_PATHS.items():
        assert (first / relative_path).read_text(encoding="utf-8") == (
            second / relative_path
        ).read_text(encoding="utf-8"), key
