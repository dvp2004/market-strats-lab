from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from market_strats.global_multi_asset import gma6e_tournament_evidence_board as gma6e


MODULE_PATH = Path("src/market_strats/global_multi_asset/gma6e_tournament_evidence_board.py")


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _sync_root_latest(root: Path) -> None:
    run_dir = root / "runs" / gma6e.COMPLETED_RUN_ID
    for filename in gma6e.ROOT_LATEST_FILES:
        shutil.copy2(run_dir / filename, root / filename)


def _build_fixture(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "reports" / "global_multi_asset_alpha" / "gma6_cross_universe_tournament_v1"
    run_dir = root / "runs" / gma6e.COMPLETED_RUN_ID
    timeout_one = root / "runs" / "gma6d_20260623T200827Z"
    timeout_two = root / "runs" / "gma6d_20260623T204937Z"
    run_dir.mkdir(parents=True)
    timeout_one.mkdir(parents=True)
    timeout_two.mkdir(parents=True)
    lock = {
        "gma6b_data_bundle_manifest_hash": "bundle_hash",
        "control_universe_hash": "control_hash",
        "expanded_universe_hash": "expanded_hash",
        "trial_inventory_hash": "trial_hash",
        "cost_scenario_hash": "cost_hash",
        "methodology_regime_rules_hash": "method_hash",
    }
    lock_path = tmp_path / "gma6c_lock.json"
    _write_json(lock_path, lock)
    manifest = {
        **lock,
        "gma6c_lock_hash": gma6e._sha256_file(lock_path),
        "run_id": gma6e.COMPLETED_RUN_ID,
        "network_access_attempted": False,
    }
    _write_json(run_dir / "gma6d_run_manifest_v1.json", manifest)
    _write_json(
        run_dir / "gma6d_execution_provenance_v1.json",
        {"execution_status": "historical_research_execution_only"},
    )
    trials = [f"gma4_trial_{idx:02d}_v1" for idx in range(20)]
    families = {trial: ("family_a" if idx < 10 else "family_b") for idx, trial in enumerate(trials)}
    scoreboard_rows = []
    detail_rows = []
    sample_rows = []
    comparison_rows = []
    for universe, flag in [
        (gma6e.CONTROL_UNIVERSE_VERSION, gma6e.CONTROL_FLAG),
        (gma6e.EXPANDED_UNIVERSE_VERSION, gma6e.EXPANDED_USO_FLAG),
    ]:
        for trial in trials:
            for cost in gma6e.REQUIRED_COST_SCENARIOS:
                scoreboard_rows.append(
                    {
                        "run_id": gma6e.COMPLETED_RUN_ID,
                        "universe_version": universe,
                        "trial_id": trial,
                        "trial_family": families[trial],
                        "cost_scenario": cost,
                        "evaluation_scope": "full_history",
                        "window_id": "full_history",
                        "regime_id": "",
                        "period_start": "2007-05-30",
                        "period_end": "2026-05-01",
                        "effective_period_start": "2008-01-01",
                        "session_count": 100,
                        "net_cagr": 0.05,
                        "annualised_volatility": 0.10,
                        "sharpe": 0.5,
                        "sortino": 0.7,
                        "maximum_drawdown": -0.2,
                        "cumulative_net_return": 1.0,
                        "annualised_turnover": 2.0,
                        "cost_drag": 0.01,
                        "maximum_hhi": 0.3,
                        "methodology_regime_flag": flag,
                        "measurement_status": "valid",
                        "source_run_id": gma6e.COMPLETED_RUN_ID,
                    }
                )
                detail_rows.append(
                    {
                        "run_id": gma6e.COMPLETED_RUN_ID,
                        "universe_version": universe,
                        "source_gma4_trial_id": trial,
                        "arm_trial_id": f"{universe}__{trial}",
                        "cost_scenario": cost,
                    }
                )
    for idx, trial in enumerate(trials):
        for cost in gma6e.REQUIRED_COST_SCENARIOS:
            sample_rows.append(
                {
                    "trial_id": trial,
                    "cost_scenario": cost,
                    "evaluation_scope": "full_history",
                    "window_id": "full_history",
                    "core_effective_start": "2008-01-01",
                    "expanded_effective_start": "2008-01-01",
                    "core_period_end": "2026-05-01",
                    "expanded_period_end": "2026-05-01",
                    "sample_comparability_status": "identical_effective_sample",
                }
            )
            metric_values = {
                "net_cagr": (0.05, 0.06 if idx % 2 == 0 else 0.04),
                "annualised_volatility": (0.10, 0.09),
                "sharpe": (0.50, 0.55),
                "maximum_drawdown": (-0.20, -0.15),
                "annualised_turnover": (2.0, 1.5),
                "cost_drag": (0.01, 0.02 if idx % 2 == 0 else 0.005),
                "maximum_hhi": (0.30, 0.25),
            }
            for metric, (core, expanded) in metric_values.items():
                comparison_rows.append(
                    {
                        "trial_id": trial,
                        "cost_scenario": cost,
                        "evaluation_scope": "full_history",
                        "window_id": "full_history",
                        "period_start": "2007-05-30",
                        "period_end": "2026-05-01",
                        "core_22_metric": core,
                        "expanded_29_metric": expanded,
                        "difference": expanded - core,
                        "metric_name": metric,
                        "sample_comparability_status": "identical_effective_sample",
                        "interpretation_limit": "test",
                        "methodology_regime_flag": gma6e.EXPANDED_USO_FLAG,
                    }
                )
    sample_rows.append(
        {
            "trial_id": trials[0],
            "cost_scenario": "baseline_1bps",
            "evaluation_scope": "rolling_3y",
            "window_id": "2010_2012",
            "core_effective_start": "2010-01-01",
            "expanded_effective_start": "2011-01-01",
            "core_period_end": "2012-12-31",
            "expanded_period_end": "2012-12-31",
            "sample_comparability_status": "not_comparable_due_to_effective_start",
        }
    )
    for metric in gma6e.PRIMARY_METRICS:
        comparison_rows.append(
            {
                "trial_id": trials[0],
                "cost_scenario": "baseline_1bps",
                "evaluation_scope": "rolling_3y",
                "window_id": "2010_2012",
                "period_start": "2010-01-01",
                "period_end": "2012-12-31",
                "core_22_metric": 0.0,
                "expanded_29_metric": 100.0,
                "difference": 100.0,
                "metric_name": metric,
                "sample_comparability_status": "not_comparable_due_to_effective_start",
                "interpretation_limit": "test",
                "methodology_regime_flag": gma6e.EXPANDED_USO_FLAG,
            }
        )
    _write_csv(run_dir / "gma6d_tournament_scoreboard_v1.csv", scoreboard_rows)
    _write_csv(run_dir / "gma6d_evaluation_detail_v1.csv", detail_rows)
    _write_csv(run_dir / "gma6d_sample_comparability_audit_v1.csv", sample_rows)
    _write_csv(run_dir / "gma6d_cross_universe_comparison_v1.csv", comparison_rows)
    _write_csv(
        run_dir / "gma6d_uso_methodology_regime_detail_v1.csv",
        [
            {
                "methodology_slice": "pre_may_2020_uso_roll_methodology",
                "slice_start": "2007-05-30",
                "slice_end": "2020-04-30",
                "methodology_regime_flag": gma6e.EXPANDED_USO_FLAG,
                "result_row_count": 10,
                "interpretation_limit": "descriptive historical context only",
            },
            {
                "methodology_slice": "from_may_2020_uso_roll_methodology",
                "slice_start": "2020-05-01",
                "slice_end": "2026-05-01",
                "methodology_regime_flag": gma6e.EXPANDED_USO_FLAG,
                "result_row_count": 5,
                "interpretation_limit": "descriptive historical context only",
            },
        ],
    )
    for name in gma6e.REQUIRED_RUN_FILES:
        path = run_dir / name
        if not path.exists():
            body = gma6e.GMA4_LIMIT if name == "gma6d_results_discussion_v1.md" else "placeholder"
            path.write_text(body + "\n", encoding="utf-8")
    _sync_root_latest(root)
    return root, lock_path


def test_incomplete_timeout_directories_cannot_become_latest_reference(tmp_path: Path):
    root, _lock = _build_fixture(tmp_path)
    registry = gma6e.build_attempt_registry(root)
    statuses = registry.set_index("run_id")["attempt_status"].to_dict()
    assert statuses[gma6e.COMPLETED_RUN_ID] == "completed_verified_run"
    assert statuses["gma6d_20260623T200827Z"] == "aborted_or_incomplete_attempt"
    assert statuses["gma6d_20260623T204937Z"] == "aborted_or_incomplete_attempt"
    assert registry["eligible_for_latest_reference"].sum() == 1


def test_root_latest_file_mismatch_fails_integrity(tmp_path: Path):
    root, lock = _build_fixture(tmp_path)
    (root / "gma6d_tournament_scoreboard_v1.csv").write_text("changed\n", encoding="utf-8")
    audit = gma6e.build_integrity_audit(root=root, lock_path=lock)
    assert "fail" in set(audit["audit_status"])
    with pytest.raises(gma6e.GMA6EIntegrityError, match="root_latest_hash_matches"):
        gma6e.run_gma6e_evidence_board(root=root, lock_path=lock)


def test_missing_required_completed_run_output_fails_integrity(tmp_path: Path):
    root, lock = _build_fixture(tmp_path)
    (root / "runs" / gma6e.COMPLETED_RUN_ID / "gma6d_execution_provenance_v1.json").unlink()
    with pytest.raises(gma6e.GMA6EIntegrityError, match="execution_provenance"):
        gma6e.run_gma6e_evidence_board(root=root, lock_path=lock)


def test_primary_aggregates_exclude_non_comparable_rows(tmp_path: Path):
    root, lock = _build_fixture(tmp_path)
    result = gma6e.run_gma6e_evidence_board(root=root, lock_path=lock)
    assert int(result.detail_board["included_in_primary_summary"].sum()) == 20 * 4 * len(
        gma6e.PRIMARY_METRICS
    )
    assert int((~result.detail_board["included_in_primary_summary"]).sum()) == len(
        gma6e.PRIMARY_METRICS
    )
    net = result.family_summary.loc[
        (result.family_summary["family"] == "family_a")
        & (result.family_summary["cost_scenario"] == "baseline_1bps")
        & (result.family_summary["metric_name"] == "net_cagr")
    ].iloc[0]
    assert net["comparable_trial_count"] == 10


def test_family_directional_counts_follow_metric_direction(tmp_path: Path):
    root, lock = _build_fixture(tmp_path)
    summary = gma6e.run_gma6e_evidence_board(root=root, lock_path=lock).family_summary
    drawdown = summary.loc[
        (summary["family"] == "family_a")
        & (summary["cost_scenario"] == "baseline_1bps")
        & (summary["metric_name"] == "maximum_drawdown")
    ].iloc[0]
    assert drawdown["expanded_better_count"] == 10
    cost_drag = summary.loc[
        (summary["family"] == "family_a")
        & (summary["cost_scenario"] == "baseline_1bps")
        & (summary["metric_name"] == "cost_drag")
    ].iloc[0]
    assert cost_drag["core_better_count"] == 5
    assert cost_drag["expanded_better_count"] == 5


def test_expanded_rows_require_uso_flag(tmp_path: Path):
    root, lock = _build_fixture(tmp_path)
    path = root / "runs" / gma6e.COMPLETED_RUN_ID / "gma6d_tournament_scoreboard_v1.csv"
    frame = pd.read_csv(path)
    frame.loc[
        frame["universe_version"] == gma6e.EXPANDED_UNIVERSE_VERSION, "methodology_regime_flag"
    ] = "not_required"
    frame.to_csv(path, index=False)
    shutil.copy2(path, root / path.name)
    audit = gma6e.build_integrity_audit(root=root, lock_path=lock)
    assert (
        "expanded_outputs_carry_uso_methodology_flag"
        in audit.loc[audit["audit_status"] == "fail", "check_name"].tolist()
    )


def test_control_rows_require_no_uso_flag(tmp_path: Path):
    root, lock = _build_fixture(tmp_path)
    path = root / "runs" / gma6e.COMPLETED_RUN_ID / "gma6d_tournament_scoreboard_v1.csv"
    frame = pd.read_csv(path)
    frame.loc[
        frame["universe_version"] == gma6e.CONTROL_UNIVERSE_VERSION, "methodology_regime_flag"
    ] = gma6e.EXPANDED_USO_FLAG
    frame.to_csv(path, index=False)
    shutil.copy2(path, root / path.name)
    audit = gma6e.build_integrity_audit(root=root, lock_path=lock)
    assert (
        "control_outputs_use_no_uso_flag"
        in audit.loc[audit["audit_status"] == "fail", "check_name"].tolist()
    )


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


def test_repeated_board_generation_is_deterministic(tmp_path: Path):
    root, lock = _build_fixture(tmp_path)
    first = gma6e.run_gma6e_evidence_board(root=root, lock_path=lock)
    first_csv = (root / "gma6e_comparability_aware_evidence_board_v1.csv").read_text(
        encoding="utf-8"
    )
    second = gma6e.run_gma6e_evidence_board(root=root, lock_path=lock)
    second_csv = (root / "gma6e_comparability_aware_evidence_board_v1.csv").read_text(
        encoding="utf-8"
    )
    assert first_csv == second_csv
    pd.testing.assert_frame_equal(
        first.family_summary.reset_index(drop=True), second.family_summary.reset_index(drop=True)
    )


def test_prohibited_language_is_absent_from_generated_outputs(tmp_path: Path):
    root, lock = _build_fixture(tmp_path)
    gma6e.run_gma6e_evidence_board(root=root, lock_path=lock)
    combined = "\n".join(
        (root / name).read_text(encoding="utf-8").lower()
        for name in gma6e.OUTPUT_FILES
        if name.endswith(".md")
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
