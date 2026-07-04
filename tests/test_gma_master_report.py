from __future__ import annotations

import ast
import csv
from pathlib import Path

from market_strats.global_multi_asset import gma_master_report as report


LEDGER_COLUMNS = report.LEDGER_COLUMNS


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def base_ledger_row(phase: str, entity_id: str, metric_value: str) -> dict[str, str]:
    return {
        "generated_at_utc": "2026-06-22T08:14:19.221811+00:00",
        "report_version": "v1.3",
        "phase": phase,
        "record_type": "baseline_strategy_metrics",
        "run_id": f"{phase.lower()}_run",
        "entity_id": entity_id,
        "entity_name": entity_id,
        "family": "family",
        "evaluation_scope": "full_history",
        "cost_scenario": "baseline_1bps",
        "period_start": "2007-05-30",
        "period_end": "2026-05-01",
        "metric_name": "net CAGR",
        "metric_value": metric_value,
        "metric_unit": "ratio",
        "coverage_status": "full_coverage",
        "evidence_status": "observed_development_evidence",
        "source_file": "source.csv",
        "source_run_id": f"{phase.lower()}_run",
        "notes": "preserve me",
    }


def build_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    h2 = tmp_path / "h2"
    gma6 = tmp_path / "gma6"
    output = tmp_path / "out"
    write_csv(
        h2 / "reports/global_multi_asset_alpha/gma_research_latest_v1.csv",
        LEDGER_COLUMNS,
        [
            base_ledger_row("GMA-4", "gma4_metric", "0.123456789"),
            base_ledger_row("GMA-5", "gma5_metric", "0.987654321"),
        ],
    )
    markdown = """# Global Multi-Asset Research - Latest Programme Report

## Current Programme Status

GMA-4 historical robustness and GMA-5 atomic sleeve ensemble research are represented here as a structured master ledger. All facts are observed_development_evidence, not_a_pristine_final_holdout, and no execution or promotion decision is produced.

## Assets and Strategy Catalogue

The report covers the frozen GMA-4 cross-asset historical tournament outputs and the saved GMA-5 atomic sleeve ensemble outputs.

## Current Evidence Gaps and Research Gates

Existing content.

## Change Log

* Existing entry.

## Next Bounded Task

Old next task.
"""
    (h2 / "reports/global_multi_asset_alpha").mkdir(parents=True, exist_ok=True)
    (h2 / "reports/global_multi_asset_alpha/gma_research_latest_v1.md").write_text(
        markdown,
        encoding="utf-8",
    )
    write_csv(
        gma6 / "gma6_v1_attempt_status_registry_v1.csv",
        [
            "run_id",
            "source_path",
            "present_in_source",
            "attempt_status",
            "eligible_for_latest_reference",
            "eligible_for_classification_evidence",
            "copied_file_count",
        ],
        [
            {
                "run_id": report.COMPLETED_RUN_ID,
                "source_path": "run",
                "present_in_source": "true",
                "attempt_status": "completed_reference_run",
                "eligible_for_latest_reference": "true",
                "eligible_for_classification_evidence": "true",
                "copied_file_count": "14",
            },
            {
                "run_id": "gma6d_20260623T200827Z",
                "source_path": "attempt1",
                "present_in_source": "true",
                "attempt_status": "aborted_or_incomplete_attempt",
                "eligible_for_latest_reference": "false",
                "eligible_for_classification_evidence": "false",
                "copied_file_count": "14",
            },
            {
                "run_id": "gma6d_20260623T204937Z",
                "source_path": "attempt2",
                "present_in_source": "true",
                "attempt_status": "aborted_or_incomplete_attempt",
                "eligible_for_latest_reference": "false",
                "eligible_for_classification_evidence": "false",
                "copied_file_count": "14",
            },
        ],
    )
    base = gma6 / "reports/global_multi_asset_alpha/gma6_cross_universe_tournament_v1"
    write_csv(
        base / "gma6f_universe_classification_freeze_board_v1.csv",
        [
            "universe_version",
            "classification",
            "role",
            "gma6_v1_status",
            "rationale",
            "completed_run_id",
            "classification_scope",
            "known_limitations",
            "future_boundary",
        ],
        [
            {
                "universe_version": "gma6_core_22_control_v1",
                "classification": "frozen_research_reference",
                "role": "control_universe_baseline",
                "gma6_v1_status": "retained_as_cross_universe_control_reference",
                "rationale": "core retained",
                "completed_run_id": report.COMPLETED_RUN_ID,
                "classification_scope": "saved_output_only_cross_universe_research_reference",
                "known_limitations": "limitations",
                "future_boundary": "frozen",
            },
            {
                "universe_version": "gma6_expanded_29_v1",
                "classification": "archived_from_gma6_v1_expansion",
                "role": "documented_expansion_reference_no_broad_incremental_support",
                "gma6_v1_status": "no_further_gma6_v1_tuning_subsetting_or_expansion",
                "rationale": "expanded archived",
                "completed_run_id": report.COMPLETED_RUN_ID,
                "classification_scope": "saved_output_only_cross_universe_research_reference",
                "known_limitations": "limitations",
                "future_boundary": "frozen",
            },
        ],
    )
    write_csv(
        base / "gma6e_comparability_aware_evidence_board_v1.csv",
        [
            "record_type",
            "trial_id",
            "trial_family",
            "cost_scenario",
            "evaluation_scope",
            "metric_name",
            "sample_comparability_status",
            "included_in_primary_summary",
        ],
        [
            {
                "record_type": "trial_metric",
                "trial_id": "trial1",
                "trial_family": "family",
                "cost_scenario": "baseline_1bps",
                "evaluation_scope": "full_history",
                "metric_name": "net_cagr",
                "sample_comparability_status": "identical_effective_sample",
                "included_in_primary_summary": "True",
            },
            {
                "record_type": "trial_metric",
                "trial_id": "trial2",
                "trial_family": "family",
                "cost_scenario": "baseline_1bps",
                "evaluation_scope": "full_history",
                "metric_name": "net_cagr",
                "sample_comparability_status": "not_comparable_due_to_effective_start",
                "included_in_primary_summary": "False",
            },
            {
                "record_type": "family_summary",
                "trial_id": "",
                "trial_family": "",
                "cost_scenario": "baseline_1bps",
                "evaluation_scope": "",
                "metric_name": "net_cagr",
                "sample_comparability_status": "",
                "included_in_primary_summary": "",
            },
        ],
    )
    write_csv(
        base / "gma6e_completed_run_integrity_audit_v1.csv",
        ["check_name", "audit_status", "expected", "observed", "notes"],
        [
            {
                "check_name": "completed_run_file_present:gma6d_run_manifest_v1.json",
                "audit_status": "pass",
                "expected": "present_and_nonempty",
                "observed": "present_and_nonempty",
                "notes": "",
            }
        ],
    )
    return h2, gma6, output


def generate(tmp_path: Path) -> report.MasterReportResult:
    h2, gma6, output = build_fixture(tmp_path)
    return report.generate_master_report(
        h2_snapshot=h2,
        gma6_snapshot=gma6,
        output_root=output,
        expected_primary_count=1,
        expected_excluded_count=1,
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_report_revision_and_outputs_are_generated(tmp_path: Path) -> None:
    result = generate(tmp_path)
    assert result.report_version == "v1.4"
    assert result.ledger_csv.is_file()
    assert result.ledger_md.is_file()
    assert result.validation_csv.is_file()
    assert result.validation_md.is_file()
    assert {row["report_version"] for row in read_rows(result.ledger_csv)} == {"v1.4"}


def test_gma4_and_gma5_v13_metric_values_are_preserved(tmp_path: Path) -> None:
    result = generate(tmp_path)
    rows = read_rows(result.ledger_csv)
    assert [row for row in rows if row["entity_id"] == "gma4_metric"][0][
        "metric_value"
    ] == "0.123456789"
    assert [row for row in rows if row["entity_id"] == "gma5_metric"][0][
        "metric_value"
    ] == "0.987654321"
    assert [row for row in rows if row["entity_id"] == "gma4_metric"][0][
        "source_file"
    ] == "source.csv"


def test_gma6_completed_run_and_attempt_counts_are_exact(tmp_path: Path) -> None:
    result = generate(tmp_path)
    rows = read_rows(result.ledger_csv)
    metrics = {row["metric_name"]: row["metric_value"] for row in rows if row["phase"] == "GMA-6"}
    assert metrics["completed_run_id"] == report.COMPLETED_RUN_ID
    assert metrics["completed_verified_run_count"] == "1"
    assert metrics["incomplete_attempt_count"] == "2"
    assert metrics["completed_run_integrity_verdict"] == "pass"


def test_gma6_classification_rows_are_present_and_exact(tmp_path: Path) -> None:
    result = generate(tmp_path)
    rows = read_rows(result.ledger_csv)
    by_entity_metric = {(row["entity_id"], row["metric_name"]): row["metric_value"] for row in rows}
    assert (
        by_entity_metric[("gma6_core_22_control_v1", "classification")]
        == "frozen_research_reference"
    )
    assert by_entity_metric[("gma6_core_22_control_v1", "role")] == "control_universe_baseline"
    assert (
        by_entity_metric[("gma6_core_22_control_v1", "status")]
        == "retained_as_cross_universe_control_reference"
    )
    assert (
        by_entity_metric[("gma6_expanded_29_v1", "classification")]
        == "archived_from_gma6_v1_expansion"
    )
    assert (
        by_entity_metric[("gma6_expanded_29_v1", "role")]
        == "documented_expansion_reference_no_broad_incremental_support"
    )
    assert (
        by_entity_metric[("gma6_expanded_29_v1", "status")]
        == "no_further_gma6_v1_tuning_subsetting_or_expansion"
    )


def test_comparable_and_excluded_counts_reconcile(tmp_path: Path) -> None:
    result = generate(tmp_path)
    rows = read_rows(result.ledger_csv)
    metrics = {row["metric_name"]: row["metric_value"] for row in rows if row["phase"] == "GMA-6"}
    assert metrics["primary_comparable_observation_count"] == "1"
    assert metrics["non_comparable_excluded_observation_count"] == "1"


def test_no_duplicate_identity_metric_rows_exist(tmp_path: Path) -> None:
    result = generate(tmp_path)
    rows = read_rows(result.ledger_csv)
    assert report.duplicate_identity_rows(rows) == []


def test_markdown_and_csv_agree_on_gma6_identity_and_classifications(tmp_path: Path) -> None:
    result = generate(tmp_path)
    rows = read_rows(result.ledger_csv)
    markdown = result.ledger_md.read_text(encoding="utf-8")
    for required in [
        report.COMPLETED_RUN_ID,
        "gma6_core_22_control_v1",
        "frozen_research_reference",
        "gma6_expanded_29_v1",
        "archived_from_gma6_v1_expansion",
    ]:
        assert required in markdown
        assert any(required in value for row in rows for value in row.values())


def test_generation_is_deterministic(tmp_path: Path) -> None:
    first = generate(tmp_path / "a")
    second = generate(tmp_path / "b")
    assert first.ledger_csv.read_text(encoding="utf-8") == second.ledger_csv.read_text(
        encoding="utf-8"
    )
    assert first.ledger_md.read_text(encoding="utf-8") == second.ledger_md.read_text(
        encoding="utf-8"
    )
    assert first.validation_csv.read_text(encoding="utf-8") == second.validation_csv.read_text(
        encoding="utf-8"
    )


def test_no_strategy_replay_allocation_or_model_modules_are_imported() -> None:
    source = Path(report.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert not any("gma4_tournament" in module for module in imported_modules)
    assert not any("gma6d_cross_universe_tournament" in module for module in imported_modules)
    assert not any("replay" in module for module in imported_modules)
    assert not any("model" in module for module in imported_modules)


def test_required_language_present_and_prohibited_decision_language_absent(tmp_path: Path) -> None:
    result = generate(tmp_path)
    markdown = result.ledger_md.read_text(encoding="utf-8")
    assert "observed development evidence" in markdown
    assert "not a pristine final holdout" in markdown
    assert "no execution or promotion decision is produced" in markdown
    assert "Highest historical CAGR or Sharpe alone is not a selection rule." in markdown
    for term in report.PROHIBITED_DECISION_TERMS:
        assert term not in markdown.lower()


def test_validation_summary_all_passes(tmp_path: Path) -> None:
    result = generate(tmp_path)
    rows = read_rows(result.validation_csv)
    assert rows
    assert {row["status"] for row in rows} == {"pass"}
    assert "gma6_completed_run_id_exact" in {row["check_name"] for row in rows}
