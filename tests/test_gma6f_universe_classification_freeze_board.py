from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from market_strats.global_multi_asset import gma6f_universe_classification_freeze_board as gma6f

MODULE_PATH = Path(
    "src/market_strats/global_multi_asset/gma6f_universe_classification_freeze_board.py"
)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _build_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "reports" / "global_multi_asset_alpha" / "gma6_cross_universe_tournament_v1"
    run_dir = root / "runs" / gma6f.COMPLETED_RUN_ID
    run_dir.mkdir(parents=True)
    lock_path = tmp_path / "gma6c_lock.json"
    lock = {"locked": True}
    _write_json(lock_path, lock)
    b2_path = tmp_path / "gma6b2.csv"
    _write_csv(
        b2_path,
        [
            {"ticker": "USO", "required_later_regime_flag": gma6f.USO_FLAG},
            {"ticker": "DBA", "required_later_regime_flag": "not_required"},
        ],
    )
    manifest = {
        "run_id": gma6f.COMPLETED_RUN_ID,
        "gma6b_data_bundle_manifest_hash": "bundle_hash",
        "trial_inventory_hash": "trial_hash",
        "cost_scenario_hash": "cost_hash",
        "control_universe_hash": "control_hash",
        "expanded_universe_hash": "expanded_hash",
    }
    _write_json(run_dir / "gma6d_run_manifest_v1.json", manifest)
    _write_json(
        run_dir / "gma6d_execution_provenance_v1.json",
        {"status": "historical_research_execution_only"},
    )
    _write_csv(
        root / "gma6e_attempt_registry_v1.csv",
        [
            {
                "run_id": "gma6d_20260623T200827Z",
                "attempt_status": "aborted_or_incomplete_attempt",
                "eligible_for_latest_reference": False,
            },
            {
                "run_id": "gma6d_20260623T204937Z",
                "attempt_status": "aborted_or_incomplete_attempt",
                "eligible_for_latest_reference": False,
            },
            {
                "run_id": gma6f.COMPLETED_RUN_ID,
                "attempt_status": "completed_verified_run",
                "eligible_for_latest_reference": True,
            },
        ],
    )
    _write_csv(
        root / "gma6e_completed_run_integrity_audit_v1.csv",
        [{"check_name": "all", "audit_status": "pass"}],
    )
    rows = []
    for idx in range(gma6f.EXPECTED_IDENTICAL_EFFECTIVE_SAMPLE_COUNT):
        rows.append(
            {
                "record_type": "trial_metric",
                "included_in_primary_summary": True,
                "sample_comparability_status": "identical_effective_sample",
                "row_id": idx,
            }
        )
    for idx in range(gma6f.EXPECTED_NON_COMPARABLE_EXCLUDED_COUNT):
        rows.append(
            {
                "record_type": "trial_metric",
                "included_in_primary_summary": False,
                "sample_comparability_status": "not_comparable_due_to_effective_start",
                "row_id": idx + 40000,
            }
        )
    rows.append(
        {
            "record_type": "family_summary",
            "included_in_primary_summary": "",
            "sample_comparability_status": "",
            "row_id": 99999,
        }
    )
    _write_csv(root / "gma6e_comparability_aware_evidence_board_v1.csv", rows)
    (root / "gma6e_comparability_aware_evidence_board_v1.md").write_text(
        "observed development evidence\n", encoding="utf-8"
    )
    return root, lock_path, b2_path


def test_exactly_one_completed_verified_run_is_required(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    path = root / "gma6e_attempt_registry_v1.csv"
    frame = pd.read_csv(path)
    frame.loc[len(frame)] = {
        "run_id": "gma6d_extra",
        "attempt_status": "completed_verified_run",
        "eligible_for_latest_reference": True,
    }
    frame.to_csv(path, index=False)
    with pytest.raises(gma6f.GMA6FClassificationError, match="exactly one"):
        gma6f.run_gma6f_classification_freeze_board(
            root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
        )


def test_timeout_attempts_cannot_contribute_evidence(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    path = root / "gma6e_attempt_registry_v1.csv"
    frame = pd.read_csv(path)
    frame.loc[frame["run_id"] == "gma6d_20260623T200827Z", "attempt_status"] = (
        "unclear_requires_manual_review"
    )
    frame.to_csv(path, index=False)
    with pytest.raises(gma6f.GMA6FClassificationError, match="timeout attempts"):
        gma6f.run_gma6f_classification_freeze_board(
            root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
        )


def test_integrity_verdict_must_pass(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    _write_csv(
        root / "gma6e_completed_run_integrity_audit_v1.csv",
        [{"check_name": "bad", "audit_status": "fail"}],
    )
    with pytest.raises(gma6f.GMA6FClassificationError, match="integrity verdict"):
        gma6f.run_gma6f_classification_freeze_board(
            root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
        )


def test_comparable_and_non_comparable_counts_must_reconcile(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    path = root / "gma6e_comparability_aware_evidence_board_v1.csv"
    frame = pd.read_csv(path)
    drop_index = frame.loc[
        frame["included_in_primary_summary"].astype(str).str.lower() == "false"
    ].index[0]
    frame = frame.drop(index=drop_index)
    frame.to_csv(path, index=False)
    with pytest.raises(gma6f.GMA6FClassificationError, match="non_comparable"):
        gma6f.run_gma6f_classification_freeze_board(
            root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
        )


def test_exactly_two_universe_classifications_exist(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    result = gma6f.run_gma6f_classification_freeze_board(
        root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
    )
    assert len(result.classification) == 2
    assert set(result.classification["universe_version"]) == {
        gma6f.CONTROL_UNIVERSE,
        gma6f.EXPANDED_UNIVERSE,
    }


def test_core_22_has_fixed_control_reference_classification(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    result = gma6f.run_gma6f_classification_freeze_board(
        root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
    )
    core = result.classification.set_index("universe_version").loc[gma6f.CONTROL_UNIVERSE]
    assert core["classification"] == "frozen_research_reference"
    assert core["role"] == "control_universe_baseline"
    assert core["gma6_v1_status"] == "retained_as_cross_universe_control_reference"


def test_expanded_29_has_fixed_archived_classification_and_rationale(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    result = gma6f.run_gma6f_classification_freeze_board(
        root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
    )
    expanded = result.classification.set_index("universe_version").loc[gma6f.EXPANDED_UNIVERSE]
    assert expanded["classification"] == "archived_from_gma6_v1_expansion"
    assert expanded["role"] == "documented_expansion_reference_no_broad_incremental_support"
    assert "lower turnover and cost drag" in expanded["rationale"]
    assert (
        "did not show broad incremental support on net CAGR, Sharpe, or maximum drawdown"
        in expanded["rationale"]
    )


def test_uso_methodology_context_is_retained(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    result = gma6f.run_gma6f_classification_freeze_board(
        root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
    )
    assert result.lock["uso_methodology_regime_flag"] == gma6f.USO_FLAG
    assert any(gma6f.USO_FLAG in item for item in result.lock["known_limitations"])


def test_lock_output_is_deterministic(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    first = gma6f.run_gma6f_classification_freeze_board(
        root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
    )
    first_text = (root / gma6f.OUTPUT_LOCK).read_text(encoding="utf-8")
    second = gma6f.run_gma6f_classification_freeze_board(
        root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
    )
    second_text = (root / gma6f.OUTPUT_LOCK).read_text(encoding="utf-8")
    assert first_text == second_text
    assert first.lock == second.lock


def test_no_provider_strategy_replay_allocation_or_model_imports():
    source = MODULE_PATH.read_text(encoding="utf-8")
    import_lines = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    blocked = [
        "yfinance",
        "requests",
        "urllib",
        "gma4_replay_adapter",
        "gma4_strategy_library",
        "allocation",
        "model",
        "sklearn",
    ]
    assert not any(term in line for term in blocked for line in import_lines)


def test_promotional_or_execution_oriented_terminology_is_absent(tmp_path: Path):
    root, lock, b2 = _build_fixture(tmp_path)
    gma6f.run_gma6f_classification_freeze_board(
        root=root, gma6c_lock_path=lock, gma6b2_continuity_path=b2
    )
    combined = "\n".join(
        (root / name).read_text(encoding="utf-8").lower()
        for name in [gma6f.OUTPUT_MD, gma6f.OUTPUT_LOCK]
    )
    scrubbed = combined.replace("no execution or promotion decision is produced.", "")
    for word in [
        "candidate",
        "winner",
        "approved",
        "recommended",
        "deployable",
        "live-ready",
        "promotion",
    ]:
        assert word not in scrubbed
