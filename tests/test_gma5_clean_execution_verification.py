from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from market_strats.global_multi_asset.gma5_clean_execution_verification import (
    CORE_SNAPSHOT_PATHS,
    ORIGINAL_RUN_ID,
    STANDARD_OUTPUTS,
    CleanExecutionError,
    OriginalOutputReadGuard,
    compare_csv_artifact,
    run_clean_execution_verification,
    sha256_file,
)


@dataclass(frozen=True)
class FakeRunResult:
    run_dir: Path
    replay_call_strategy_ids: list[str]


def _write_csv(path: Path, rows: list[dict[str, str]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _make_core_sources(repo_root: Path) -> None:
    for relative in CORE_SNAPSHOT_PATHS:
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative}\n", encoding="utf-8")


def _standard_rows(name: str) -> list[dict[str, str]]:
    if name == "gma5_ensemble_monthly_etf_targets.csv":
        return [
            {
                "variant_id": "gma5_variant_a",
                "decision_date": "2020-01-31",
                "symbol": "SPY",
                "composite_etf_target_weight": "0.7",
            },
            {
                "variant_id": "gma5_variant_a",
                "decision_date": "2020-01-31",
                "symbol": "BIL",
                "composite_etf_target_weight": "0.3",
            },
        ]
    if name == "gma5_ensemble_monthly_sleeve_weights.csv":
        return [
            {
                "variant_id": "gma5_variant_a",
                "decision_date": "2020-01-31",
                "sleeve_id": "s1",
                "sleeve_allocation_weight": "1.0",
            }
        ]
    if name == "gma5_ensemble_monthly_features.csv":
        return [{"sleeve_id": "s1", "decision_date": "2020-01-31", "feature": "1.0"}]
    if name == "gma5_ensemble_training_audit.csv":
        return [{"decision_date": "2015-05-29", "sleeve_id": "s1", "prediction": "0.1"}]
    return [
        {
            "entity_id": "gma5_variant_a",
            "entity_type": "ensemble_variant",
            "cost_scenario": "baseline_1bps",
            "evaluation_scope": "full_common_oos",
            "start_date": "2012-05-31",
            "end_date": "2026-05-01",
            "net_cagr": "0.1",
            "max_drawdown": "-0.2",
            "status": "evaluated",
        }
    ]


def _write_standard_outputs(run_dir: Path, run_id: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for output in STANDARD_OUTPUTS:
        path = run_dir / output
        if output.endswith(".json"):
            path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "created_at_utc": "2026-06-22T00:00:00+00:00",
                        "first_ensemble_out_of_sample_date": "2012-05-31",
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        else:
            _write_csv(path, _standard_rows(output))


def _make_fixture(repo_root: Path) -> tuple[Path, Path, Path]:
    _make_core_sources(repo_root)
    gma5_root = (
        repo_root / "reports" / "global_multi_asset_alpha" / "gma5_atomic_sleeve_ensemble_v1"
    )
    original = gma5_root / "runs" / ORIGINAL_RUN_ID
    _write_standard_outputs(original, ORIGINAL_RUN_ID)
    gma4_run = (
        repo_root
        / "reports"
        / "global_multi_asset_alpha"
        / "gma4_cross_asset_tournament_v1"
        / "runs"
        / "gma4_20260621T163423Z"
    )
    gma4_run.mkdir(parents=True)
    (gma4_run / "gma4_run_manifest.json").write_text("fixture\n", encoding="utf-8")
    return gma5_root, gma4_run, repo_root / CORE_SNAPSHOT_PATHS[0]


def _fake_executor_factory(repo_root: Path, gma5_root: Path, read_original: bool = False):
    def fake_executor(_config_path: Path, clean_run_id: str) -> FakeRunResult:
        if read_original:
            (gma5_root / "runs" / ORIGINAL_RUN_ID / "gma5_ensemble_scoreboard.csv").read_text(
                encoding="utf-8"
            )
        clean_run_dir = gma5_root / "runs" / clean_run_id
        _write_standard_outputs(clean_run_dir, clean_run_id)
        return FakeRunResult(clean_run_dir, ["gma5_variant_a"])

    return fake_executor


def test_original_standard_output_reads_are_blocked_before_execution_finishes(tmp_path):
    gma5_root, _gma4_run, _config = _make_fixture(tmp_path)

    with OriginalOutputReadGuard(gma5_root / "runs" / ORIGINAL_RUN_ID, STANDARD_OUTPUTS):
        with pytest.raises(CleanExecutionError, match="blocked original standard output read"):
            (gma5_root / "runs" / ORIGINAL_RUN_ID / "gma5_ensemble_scoreboard.csv").read_text(
                encoding="utf-8"
            )


def test_clean_execution_rejects_executor_that_reads_original_outputs(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)

    with pytest.raises(CleanExecutionError, match="blocked original standard output read"):
        run_clean_execution_verification(
            tmp_path,
            gma5_root,
            gma4_run,
            config,
            executor=_fake_executor_factory(tmp_path, gma5_root, read_original=True),
        )


def test_verifier_source_does_not_use_standard_output_copying_helpers():
    source = Path(
        "src/market_strats/global_multi_asset/gma5_clean_execution_verification.py"
    ).read_text(encoding="utf-8")
    forbidden = [
        "shutil.copy",
        "copyfile",
        "copytree",
        "os.link",
        "symlink",
        "subprocess",
        "requests",
        "urllib",
    ]
    assert not any(term in source for term in forbidden)


def test_clean_execution_runtime_artifacts_are_linked_by_execution_uuid(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)

    result = run_clean_execution_verification(
        tmp_path,
        gma5_root,
        gma4_run,
        config,
        executor=_fake_executor_factory(tmp_path, gma5_root),
    )

    assert result.overall_status == "clean_execution_exact_reproduction_verified"
    journal = json.loads(
        (result.clean_run_dir / "gma5_clean_execution_journal_v1.json").read_text(encoding="utf-8")
    )
    trace = json.loads(
        (result.clean_run_dir / "gma5_runtime_replay_trace_v1.json").read_text(encoding="utf-8")
    )
    no_average = json.loads(
        (result.clean_run_dir / "gma5_no_equity_curve_averaging_trace_v2.json").read_text(
            encoding="utf-8"
        )
    )

    assert journal["execution_uuid"] == trace["execution_uuid"] == no_average["execution_uuid"]
    assert journal["standard_outputs_generated_by_execution"] is True
    assert journal["original_standard_outputs_read_before_execution_finished"] is False
    assert trace["replay_adapter_invocation_count"] > 0
    assert trace["composite_target_input_hashes_by_variant"]
    assert trace["composite_replay_ledger_hashes_by_variant"]
    assert no_average["allocation_input_type"] == "sleeve_etf_target_weights"
    assert no_average["replay_input_type"] == "netted_composite_etf_target_weights"
    assert no_average["equity_curve_averaging_invoked"] is False


def test_composite_target_weights_sum_to_one(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)

    result = run_clean_execution_verification(
        tmp_path,
        gma5_root,
        gma4_run,
        config,
        executor=_fake_executor_factory(tmp_path, gma5_root),
    )
    rows = _read_csv(result.clean_run_dir / "gma5_composite_target_netting_audit_v2.csv")

    assert sum(float(row["final_target_weight"]) for row in rows) == 1.0


def test_static_source_inspection_alone_cannot_generate_no_average_trace(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)
    result = run_clean_execution_verification(
        tmp_path,
        gma5_root,
        gma4_run,
        config,
        executor=_fake_executor_factory(tmp_path, gma5_root),
    )
    trace = json.loads(
        (result.clean_run_dir / "gma5_no_equity_curve_averaging_trace_v2.json").read_text(
            encoding="utf-8"
        )
    )

    assert "runtime_evidence" in trace
    assert "source_assertion" not in trace


def test_exact_comparison_passes_at_tolerance_and_mismatches_fail(tmp_path):
    original = tmp_path / "original.csv"
    clean = tmp_path / "clean.csv"
    fields = ["date", "name", "value"]
    _write_csv(original, [{"date": "2020-01-31", "name": "a", "value": "1.0"}], fields)
    _write_csv(clean, [{"date": "2020-01-31", "name": "a", "value": "1.0000000000005"}], fields)
    assert compare_csv_artifact(original, clean)["status"] == "pass"
    _write_csv(clean, [], fields)
    assert compare_csv_artifact(original, clean)["mismatch_type"] == "row_count_mismatch"
    _write_csv(clean, [{"date": "2020-02-29", "name": "a", "value": "1.0"}], fields)
    assert compare_csv_artifact(original, clean)["mismatch_type"] == "date_mismatch"
    _write_csv(clean, [{"date": "2020-01-31", "name": "b", "value": "1.0"}], fields)
    assert compare_csv_artifact(original, clean)["mismatch_type"] == "text_mismatch"
    _write_csv(clean, [{"date": "2020-01-31", "name": "a", "value": "1.000000000002"}], fields)
    assert compare_csv_artifact(original, clean)["mismatch_type"] == "numeric_mismatch"


def test_original_run_files_remain_unchanged(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)
    original_files = list((gma5_root / "runs" / ORIGINAL_RUN_ID).glob("*"))
    before = {path: sha256_file(path) for path in original_files}

    run_clean_execution_verification(
        tmp_path,
        gma5_root,
        gma4_run,
        config,
        executor=_fake_executor_factory(tmp_path, gma5_root),
    )

    assert {path: sha256_file(path) for path in original_files} == before


def test_clean_execution_run_id_is_distinct_from_original(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)

    with pytest.raises(CleanExecutionError, match="must differ"):
        run_clean_execution_verification(
            tmp_path,
            gma5_root,
            gma4_run,
            config,
            clean_run_id=ORIGINAL_RUN_ID,
            executor=_fake_executor_factory(tmp_path, gma5_root),
        )


def test_all_required_clean_outputs_are_written(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)

    result = run_clean_execution_verification(
        tmp_path,
        gma5_root,
        gma4_run,
        config,
        executor=_fake_executor_factory(tmp_path, gma5_root),
    )

    for name in [
        "gma5_clean_execution_manifest_v1.json",
        "gma5_clean_execution_journal_v1.json",
        "gma5_runtime_replay_trace_v1.json",
        "gma5_composite_target_netting_audit_v2.csv",
        "gma5_composite_replay_ledger_v2.csv",
        "gma5_no_equity_curve_averaging_trace_v2.json",
        "gma5_clean_execution_comparison_v1.csv",
        "gma5_clean_execution_comparison_v1.md",
    ]:
        assert (result.clean_run_dir / name).exists()


def test_no_forbidden_path_terms_in_clean_verifier_source():
    source = Path(
        "src/market_strats/global_multi_asset/gma5_clean_execution_verification.py"
    ).read_text(encoding="utf-8")
    forbidden = [
        "git add",
        "git commit",
        "git push",
        "fetch(",
        "broker",
        "paper_order",
        "candidate_record",
        "promotion_logic",
    ]
    assert not any(term in source for term in forbidden)
