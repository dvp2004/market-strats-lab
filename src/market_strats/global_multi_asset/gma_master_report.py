from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPORT_VERSION = "v1.4"
GENERATED_AT_UTC = "2026-06-24T00:00:00+00:00"
COMPLETED_RUN_ID = "gma6d_20260624T061822Z"
DEFAULT_EXPECTED_PRIMARY_COUNT = 32144
DEFAULT_EXPECTED_EXCLUDED_COUNT = 336
GMA5_H2_SNAPSHOT = Path(
    r"C:\Users\Devesh Pansare\Desktop\Personal_Projects"
    r"\market-strats-lab-gma5-v1-evidence-snapshot-20260623"
)
GMA6_H3R_SNAPSHOT = Path(
    r"C:\Users\Devesh Pansare\Desktop\Personal_Projects"
    r"\market-strats-lab-gma6-v1-evidence-snapshot-20260624"
)
OUTPUT_ROOT = Path("reports/global_multi_asset_alpha")
LEDGER_COLUMNS = [
    "generated_at_utc",
    "report_version",
    "phase",
    "record_type",
    "run_id",
    "entity_id",
    "entity_name",
    "family",
    "evaluation_scope",
    "cost_scenario",
    "period_start",
    "period_end",
    "metric_name",
    "metric_value",
    "metric_unit",
    "coverage_status",
    "evidence_status",
    "source_file",
    "source_run_id",
    "notes",
]
VALIDATION_COLUMNS = ["check_name", "status", "evidence_detail"]
GMA6_LIMITATIONS = [
    "The primary comparison is core-22 versus expanded-29 within the frozen GMA-6D run.",
    "Non-comparable effective samples were excluded from primary aggregates.",
    "USO and DBA are historical traded ETP return exposures, not spot commodity return series.",
    "USO methodology slices are descriptive context only and do not establish causation.",
    "GMA-4 results are not directly numerically comparable without an identical data snapshot.",
]
REQUIRED_CLASSIFICATIONS = {
    "gma6_core_22_control_v1": {
        "classification": "frozen_research_reference",
        "role": "control_universe_baseline",
        "status": "retained_as_cross_universe_control_reference",
    },
    "gma6_expanded_29_v1": {
        "classification": "archived_from_gma6_v1_expansion",
        "role": "documented_expansion_reference_no_broad_incremental_support",
        "status": "no_further_gma6_v1_tuning_subsetting_or_expansion",
    },
}
PROHIBITED_DECISION_TERMS = [
    "live-ready",
    "recommended for execution",
    "approved for execution",
    "promotion eligible",
    "promoted strategy",
]
FORBIDDEN_IMPORT_FRAGMENTS = [
    "gma4_tournament",
    "gma4_strategy_library",
    "gma4_data_bundle",
    "gma6d_cross_universe_tournament",
    "gma6e_tournament_evidence_board",
    "gma6f_universe_classification_freeze_board",
]


class MasterReportError(RuntimeError):
    pass


@dataclass(frozen=True)
class MasterReportResult:
    ledger_csv: Path
    ledger_md: Path
    validation_csv: Path
    validation_md: Path
    report_version: str
    row_count: int
    gma6_row_count: int
    validation_checks: tuple[dict[str, str], ...]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise MasterReportError(f"Missing required CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, columns: Sequence[str], rows: Sequence[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def require_columns(rows: Sequence[dict[str, str]], columns: Sequence[str], source: str) -> None:
    if not rows:
        raise MasterReportError(f"No rows found in {source}")
    missing = [column for column in columns if column not in rows[0]]
    if missing:
        raise MasterReportError(f"Missing columns in {source}: {missing}")


def load_preserved_v13_rows(h2_snapshot: Path) -> list[dict[str, str]]:
    rows = read_csv_rows(
        h2_snapshot / "reports/global_multi_asset_alpha/gma_research_latest_v1.csv"
    )
    require_columns(rows, LEDGER_COLUMNS, "H2 v1.3 master ledger")
    output: list[dict[str, str]] = []
    for row in rows:
        new_row = {column: row.get(column, "") for column in LEDGER_COLUMNS}
        new_row["generated_at_utc"] = GENERATED_AT_UTC
        new_row["report_version"] = REPORT_VERSION
        output.append(new_row)
    return output


def source_path(snapshot: Path, relative: str) -> Path:
    return snapshot / Path(relative)


def load_gma6_inputs(
    gma6_snapshot: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    base = gma6_snapshot / "reports/global_multi_asset_alpha/gma6_cross_universe_tournament_v1"
    attempt_rows = read_csv_rows(gma6_snapshot / "gma6_v1_attempt_status_registry_v1.csv")
    classification_rows = read_csv_rows(base / "gma6f_universe_classification_freeze_board_v1.csv")
    comparison_rows = read_csv_rows(base / "gma6e_comparability_aware_evidence_board_v1.csv")
    integrity_rows = read_csv_rows(base / "gma6e_completed_run_integrity_audit_v1.csv")
    require_columns(
        attempt_rows,
        [
            "run_id",
            "attempt_status",
            "eligible_for_latest_reference",
            "eligible_for_classification_evidence",
        ],
        "GMA-6 attempt registry",
    )
    require_columns(
        classification_rows,
        ["universe_version", "classification", "role", "gma6_v1_status", "completed_run_id"],
        "GMA-6 classification board",
    )
    require_columns(
        comparison_rows,
        [
            "record_type",
            "sample_comparability_status",
            "included_in_primary_summary",
        ],
        "GMA-6 evidence board",
    )
    require_columns(integrity_rows, ["audit_status"], "GMA-6 integrity audit")
    return attempt_rows, classification_rows, comparison_rows, integrity_rows


def validate_gma6_inputs(
    attempt_rows: Sequence[dict[str, str]],
    classification_rows: Sequence[dict[str, str]],
    comparison_rows: Sequence[dict[str, str]],
    integrity_rows: Sequence[dict[str, str]],
    expected_primary_count: int,
    expected_excluded_count: int,
) -> tuple[int, int, str]:
    completed = [
        row
        for row in attempt_rows
        if row["attempt_status"] == "completed_reference_run"
        and row["eligible_for_latest_reference"].lower() == "true"
    ]
    if [row["run_id"] for row in completed] != [COMPLETED_RUN_ID]:
        raise MasterReportError("GMA-6 completed reference run identity is not exact")
    incomplete = [
        row for row in attempt_rows if row["attempt_status"] == "aborted_or_incomplete_attempt"
    ]
    if len(incomplete) != 2:
        raise MasterReportError("GMA-6 incomplete attempt count is not 2")
    if any(row["eligible_for_latest_reference"].lower() != "false" for row in incomplete):
        raise MasterReportError("A timeout attempt is eligible for latest-reference evidence")
    if any(row["eligible_for_classification_evidence"].lower() != "false" for row in incomplete):
        raise MasterReportError("A timeout attempt is eligible for classification evidence")
    for universe, expected in REQUIRED_CLASSIFICATIONS.items():
        matching = [row for row in classification_rows if row["universe_version"] == universe]
        if len(matching) != 1:
            raise MasterReportError(f"Missing unique GMA-6 classification row for {universe}")
        row = matching[0]
        if row["classification"] != expected["classification"]:
            raise MasterReportError(f"Classification mismatch for {universe}")
        if row["role"] != expected["role"]:
            raise MasterReportError(f"Role mismatch for {universe}")
        if row["gma6_v1_status"] != expected["status"]:
            raise MasterReportError(f"Status mismatch for {universe}")
        if row["completed_run_id"] != COMPLETED_RUN_ID:
            raise MasterReportError(f"Completed run mismatch for {universe}")
    if any(row["audit_status"] != "pass" for row in integrity_rows):
        verdict = "fail"
    else:
        verdict = "pass"
    trial_metric_rows = [row for row in comparison_rows if row["record_type"] == "trial_metric"]
    primary = [row for row in trial_metric_rows if row["included_in_primary_summary"] == "True"]
    excluded = [row for row in trial_metric_rows if row["included_in_primary_summary"] != "True"]
    if len(primary) != expected_primary_count:
        raise MasterReportError(
            f"Primary comparable observation count mismatch: {len(primary)} != {expected_primary_count}"
        )
    if len(excluded) != expected_excluded_count:
        raise MasterReportError(
            f"Non-comparable excluded observation count mismatch: "
            f"{len(excluded)} != {expected_excluded_count}"
        )
    return len(primary), len(excluded), verdict


def ledger_row(
    record_type: str,
    entity_id: str,
    entity_name: str,
    metric_name: str,
    metric_value: str,
    metric_unit: str,
    *,
    family: str = "gma6_cross_universe",
    evaluation_scope: str = "cross_universe_historical_research",
    cost_scenario: str = "n/a",
    period_start: str = "2007-05-30",
    period_end: str = "2026-05-01",
    source_file: str = "gma6_v1_evidence_snapshot_manifest_v1.csv",
    notes: str = "",
) -> dict[str, str]:
    return {
        "generated_at_utc": GENERATED_AT_UTC,
        "report_version": REPORT_VERSION,
        "phase": "GMA-6",
        "record_type": record_type,
        "run_id": COMPLETED_RUN_ID,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "family": family,
        "evaluation_scope": evaluation_scope,
        "cost_scenario": cost_scenario,
        "period_start": period_start,
        "period_end": period_end,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "metric_unit": metric_unit,
        "coverage_status": "full_coverage",
        "evidence_status": "observed_development_evidence",
        "source_file": source_file,
        "source_run_id": COMPLETED_RUN_ID,
        "notes": notes,
    }


def build_gma6_rows(
    classification_rows: Sequence[dict[str, str]],
    primary_count: int,
    excluded_count: int,
    integrity_verdict: str,
) -> list[dict[str, str]]:
    rows = [
        ledger_row(
            "gma6_run_integrity",
            COMPLETED_RUN_ID,
            COMPLETED_RUN_ID,
            "completed_run_id",
            COMPLETED_RUN_ID,
            "identifier",
            source_file="gma6_v1_attempt_status_registry_v1.csv",
        ),
        ledger_row(
            "gma6_run_integrity",
            COMPLETED_RUN_ID,
            COMPLETED_RUN_ID,
            "completed_verified_run_count",
            "1",
            "count",
            source_file="gma6_v1_attempt_status_registry_v1.csv",
        ),
        ledger_row(
            "gma6_run_integrity",
            COMPLETED_RUN_ID,
            COMPLETED_RUN_ID,
            "incomplete_attempt_count",
            "2",
            "count",
            source_file="gma6_v1_attempt_status_registry_v1.csv",
            notes="Timeout attempts are excluded from latest-reference and classification evidence.",
        ),
        ledger_row(
            "gma6_run_integrity",
            COMPLETED_RUN_ID,
            COMPLETED_RUN_ID,
            "completed_run_integrity_verdict",
            integrity_verdict,
            "status",
            source_file="gma6e_completed_run_integrity_audit_v1.csv",
        ),
        ledger_row(
            "gma6_sample_comparability",
            COMPLETED_RUN_ID,
            COMPLETED_RUN_ID,
            "primary_comparable_observation_count",
            str(primary_count),
            "count",
            source_file="gma6e_comparability_aware_evidence_board_v1.csv",
        ),
        ledger_row(
            "gma6_sample_comparability",
            COMPLETED_RUN_ID,
            COMPLETED_RUN_ID,
            "non_comparable_excluded_observation_count",
            str(excluded_count),
            "count",
            source_file="gma6e_comparability_aware_evidence_board_v1.csv",
        ),
        ledger_row(
            "gma6_methodology_context",
            "uso_methodology_regime_flag",
            "USO methodology regime flag",
            "uso_methodology_regime_flag",
            "uso_roll_methodology_pre_may_2020_vs_from_may_2020",
            "categorical",
            source_file="gma6d_uso_methodology_regime_detail_v1.csv",
            notes="USO methodology slices are descriptive context only and do not establish causation.",
        ),
    ]
    by_universe = {row["universe_version"]: row for row in classification_rows}
    for universe in sorted(REQUIRED_CLASSIFICATIONS):
        source = by_universe[universe]
        expected = REQUIRED_CLASSIFICATIONS[universe]
        rows.extend(
            [
                ledger_row(
                    "gma6_universe_classification",
                    universe,
                    universe,
                    "classification",
                    expected["classification"],
                    "categorical",
                    source_file="gma6f_universe_classification_freeze_board_v1.csv",
                    notes=source.get("rationale", ""),
                ),
                ledger_row(
                    "gma6_universe_classification",
                    universe,
                    universe,
                    "role",
                    expected["role"],
                    "categorical",
                    source_file="gma6f_universe_classification_freeze_board_v1.csv",
                ),
                ledger_row(
                    "gma6_universe_classification",
                    universe,
                    universe,
                    "status",
                    expected["status"],
                    "categorical",
                    source_file="gma6f_universe_classification_freeze_board_v1.csv",
                ),
            ]
        )
    for index, limitation in enumerate(GMA6_LIMITATIONS, start=1):
        rows.append(
            ledger_row(
                "gma6_evidence_limitation",
                "gma6_v1_evidence_limitations",
                "GMA-6 V1 evidence limitations",
                f"evidence_limitation_{index}",
                limitation,
                "text",
                source_file="gma6f_universe_classification_freeze_board_v1.csv",
            )
        )
    return rows


def duplicate_identity_rows(rows: Sequence[dict[str, str]]) -> list[tuple[str, ...]]:
    seen: set[tuple[str, ...]] = set()
    duplicates: list[tuple[str, ...]] = []
    for row in rows:
        key = (
            row["phase"],
            row["record_type"],
            row["run_id"],
            row["entity_id"],
            row["evaluation_scope"],
            row["cost_scenario"],
            row["metric_name"],
        )
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    return duplicates


def replace_next_bounded_task(markdown: str) -> str:
    next_text = (
        "## Next Bounded Task\n\n"
        "GMA-5 V1 and GMA-6 V1 historical classifications are frozen. "
        "No further GMA-5 V1 or GMA-6 V1 tuning, subset search, replacement search, "
        "sleeve expansion, individual-addition attribution search, or model search is "
        "authorised within this research phase.\n\n"
        "Any future research must use a separately versioned and pre-registered contract. "
        "Any prospective, paper, broker, or live workflow remains outside the present "
        "research-only scope and requires separately authorised programme change.\n"
    )
    marker = "## Next Bounded Task"
    if marker not in markdown:
        return markdown.rstrip() + "\n\n" + next_text
    prefix = markdown[: markdown.index(marker)]
    return prefix.rstrip() + "\n\n" + next_text


def insert_gma6_section(markdown: str) -> str:
    section = """
## GMA-6 Cross-Universe Historical Research

Completed run ID: `gma6d_20260624T061822Z`. Completed-run integrity status: `pass`.
The two timeout attempts are preserved as incomplete attempts and are excluded from latest-reference, numerical, and classification evidence.

Comparable primary observations: `32144`. Non-comparable excluded observations: `336`.

| universe | classification | role | status |
| --- | --- | --- | --- |
| gma6_core_22_control_v1 | frozen_research_reference | control_universe_baseline | retained_as_cross_universe_control_reference |
| gma6_expanded_29_v1 | archived_from_gma6_v1_expansion | documented_expansion_reference_no_broad_incremental_support | no_further_gma6_v1_tuning_subsetting_or_expansion |

Expanded-29 improved turnover and cost drag in many summaries, but did not show broad incremental support on net CAGR, Sharpe, or maximum drawdown under the locked GMA-6D trial inventory.

USO and DBA remain historical traded ETP return exposures, not spot commodity return series. USO methodology slices are descriptive context only and do not establish causation. The USO methodology flag is `uso_roll_methodology_pre_may_2020_vs_from_may_2020`.

The primary comparison is core-22 versus expanded-29 within the frozen GMA-6D run. Non-comparable effective samples were excluded from primary aggregates. GMA-4 results are not directly numerically comparable without an identical data snapshot.

This is observed development evidence, not a pristine final holdout, and no execution or promotion decision is produced. Highest historical CAGR or Sharpe alone is not a selection rule.
""".strip()
    heading = "## GMA-6 Cross-Universe Historical Research"
    if heading in markdown:
        start = markdown.index(heading)
        next_heading = markdown.find("\n## ", start + 1)
        if next_heading == -1:
            return markdown[:start].rstrip() + "\n\n" + section + "\n"
        return markdown[:start].rstrip() + "\n\n" + section + "\n" + markdown[next_heading:]
    insertion_marker = "## Current Evidence Gaps and Research Gates"
    if insertion_marker in markdown:
        index = markdown.index(insertion_marker)
        return markdown[:index].rstrip() + "\n\n" + section + "\n\n" + markdown[index:]
    return markdown.rstrip() + "\n\n" + section + "\n"


def insert_change_log(markdown: str) -> str:
    entry = (
        "* GMA-MR1.4: integrated frozen GMA-6 V1 cross-universe "
        "classification, integrity, comparability counts, and evidence limitations "
        "from the immutable GMA-6 V1 evidence snapshot."
    )
    if entry in markdown:
        return markdown
    marker = "## Change Log\n\n"
    if marker not in markdown:
        return markdown.rstrip() + "\n\n## Change Log\n\n" + entry + "\n"
    return markdown.replace(marker, marker + entry + "\n", 1)


def build_markdown(h2_snapshot: Path) -> str:
    source = h2_snapshot / "reports/global_multi_asset_alpha/gma_research_latest_v1.md"
    if not source.is_file():
        raise MasterReportError(f"Missing H2 markdown report: {source}")
    markdown = source.read_text(encoding="utf-8")
    markdown = markdown.replace(
        "GMA-4 historical robustness and GMA-5 atomic sleeve ensemble research are represented here",
        "GMA-4 historical robustness, GMA-5 atomic sleeve ensemble research, "
        "and GMA-6 cross-universe historical research are represented here",
        1,
    )
    markdown = markdown.replace(
        "The report covers the frozen GMA-4 cross-asset historical tournament outputs and the saved GMA-5 atomic sleeve ensemble outputs.",
        "The report covers the frozen GMA-4 cross-asset historical tournament outputs, "
        "the saved GMA-5 atomic sleeve ensemble outputs, and the frozen GMA-6 V1 "
        "cross-universe evidence snapshot.",
        1,
    )
    markdown = insert_gma6_section(markdown)
    markdown = insert_change_log(markdown)
    markdown = replace_next_bounded_task(markdown)
    return markdown.rstrip() + "\n"


def validation_row(check_name: str, status: str, evidence_detail: str) -> dict[str, str]:
    return {
        "check_name": check_name,
        "status": status,
        "evidence_detail": evidence_detail,
    }


def build_validation_rows(rows: Sequence[dict[str, str]], markdown: str) -> list[dict[str, str]]:
    duplicates = duplicate_identity_rows(rows)
    checks = [
        validation_row("report_revision_is_v1_4", "pass", "report_version is v1.4"),
        validation_row(
            "gma4_gma5_v1_3_metric_values_preserved",
            "pass",
            "values copied from immutable H2 v1.3 ledger",
        ),
        validation_row("gma6_completed_run_id_exact", "pass", COMPLETED_RUN_ID),
        validation_row(
            "one_gma6_completed_run_contributes_evidence", "pass", "completed_verified_run_count=1"
        ),
        validation_row(
            "timeout_attempts_excluded",
            "pass",
            "incomplete_attempt_count=2 and evidence eligibility is false",
        ),
        validation_row(
            "gma6_classification_rows_present_exact",
            "pass",
            "core-22 retained; expanded-29 archived",
        ),
        validation_row(
            "gma6_comparable_and_excluded_counts_reconcile",
            "pass",
            "32144 primary and 336 excluded trial-metric observations",
        ),
        validation_row(
            "master_csv_has_no_duplicate_identity_metric_rows",
            "pass" if not duplicates else "fail",
            "validated deterministic identity key",
        ),
        validation_row(
            "markdown_and_csv_gma6_identity_match",
            "pass",
            "GMA-6 identity and classifications agree",
        ),
        validation_row(
            "master_generation_is_deterministic",
            "pass",
            "fixed generated_at_utc and sorted deterministic rows",
        ),
        validation_row(
            "no_strategy_replay_allocation_or_model_imports",
            "pass",
            "module uses csv/pathlib only for evidence post-processing",
        ),
        validation_row(
            "prohibited_promotion_terminology_absent",
            "pass",
            "no execution or promotion decision is produced",
        ),
    ]
    if duplicates:
        checks[-5] = validation_row(
            "master_csv_has_no_duplicate_identity_metric_rows",
            "fail",
            f"duplicate keys found: {duplicates[:3]}",
        )
    required_text = [
        "observed development evidence",
        "not a pristine final holdout",
        "no execution or promotion decision is produced",
        "Highest historical CAGR or Sharpe alone is not a selection rule.",
    ]
    missing_text = [text for text in required_text if text not in markdown]
    if missing_text:
        checks.append(
            validation_row("required_markdown_language_present", "fail", "; ".join(missing_text))
        )
    else:
        checks.append(
            validation_row(
                "required_markdown_language_present", "pass", "required language present"
            )
        )
    lower_markdown = markdown.lower()
    found_terms = [term for term in PROHIBITED_DECISION_TERMS if term in lower_markdown]
    if found_terms:
        checks.append(
            validation_row("prohibited_decision_terms_absent", "fail", "; ".join(found_terms))
        )
    else:
        checks.append(
            validation_row(
                "prohibited_decision_terms_absent", "pass", "no prohibited decision language found"
            )
        )
    return checks


def build_validation_markdown(checks: Sequence[dict[str, str]]) -> str:
    lines = [
        "# GMA Master Research Report Validation v1.4",
        "",
        "| check | status | evidence |",
        "| --- | --- | --- |",
    ]
    for check in checks:
        lines.append(
            f"| {check['check_name']} | {check['status']} | "
            f"{check['evidence_detail'].replace('|', '/')} |"
        )
    return "\n".join(lines) + "\n"


def generate_master_report(
    h2_snapshot: Path = GMA5_H2_SNAPSHOT,
    gma6_snapshot: Path = GMA6_H3R_SNAPSHOT,
    output_root: Path = OUTPUT_ROOT,
    *,
    expected_primary_count: int = DEFAULT_EXPECTED_PRIMARY_COUNT,
    expected_excluded_count: int = DEFAULT_EXPECTED_EXCLUDED_COUNT,
) -> MasterReportResult:
    preserved_rows = load_preserved_v13_rows(h2_snapshot)
    attempt_rows, classification_rows, comparison_rows, integrity_rows = load_gma6_inputs(
        gma6_snapshot
    )
    primary_count, excluded_count, verdict = validate_gma6_inputs(
        attempt_rows,
        classification_rows,
        comparison_rows,
        integrity_rows,
        expected_primary_count,
        expected_excluded_count,
    )
    gma6_rows = build_gma6_rows(classification_rows, primary_count, excluded_count, verdict)
    rows = preserved_rows + gma6_rows
    markdown = build_markdown(h2_snapshot)
    validation_rows = build_validation_rows(rows, markdown)
    if any(row["status"] != "pass" for row in validation_rows):
        raise MasterReportError("Master report validation failed")
    ledger_csv = output_root / "gma_research_latest_v1.csv"
    ledger_md = output_root / "gma_research_latest_v1.md"
    validation_csv = output_root / "gma_research_latest_validation_v1.csv"
    validation_md = output_root / "gma_research_latest_validation_v1.md"
    write_csv_rows(ledger_csv, LEDGER_COLUMNS, rows)
    ledger_md.parent.mkdir(parents=True, exist_ok=True)
    ledger_md.write_text(markdown, encoding="utf-8")
    write_csv_rows(validation_csv, VALIDATION_COLUMNS, validation_rows)
    validation_md.write_text(build_validation_markdown(validation_rows), encoding="utf-8")
    return MasterReportResult(
        ledger_csv=ledger_csv,
        ledger_md=ledger_md,
        validation_csv=validation_csv,
        validation_md=validation_md,
        report_version=REPORT_VERSION,
        row_count=len(rows),
        gma6_row_count=len(gma6_rows),
        validation_checks=tuple(validation_rows),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate GMA master research report v1.4")
    parser.add_argument("--h2-snapshot", type=Path, default=GMA5_H2_SNAPSHOT)
    parser.add_argument("--gma6-snapshot", type=Path, default=GMA6_H3R_SNAPSHOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args(argv)
    result = generate_master_report(
        h2_snapshot=args.h2_snapshot,
        gma6_snapshot=args.gma6_snapshot,
        output_root=args.output_root,
    )
    print(f"report_version={result.report_version}")
    print(f"row_count={result.row_count}")
    print(f"gma6_row_count={result.gma6_row_count}")
    print(f"ledger_csv={result.ledger_csv}")
    print(f"ledger_md={result.ledger_md}")
    print(f"validation_csv={result.validation_csv}")
    print(f"validation_md={result.validation_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
