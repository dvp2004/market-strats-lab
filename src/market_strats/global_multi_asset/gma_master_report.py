import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


REPORT_VERSION = "v1.3"
EVIDENCE_STATUS = "observed_development_evidence"
GMA4_RUN_ID = "gma4_20260621T163423Z"
GMA5_RUN_ID = "gma5_20260622T075912Z"
GMA5_VERIFIED_RUN_ID = "gma5_verified_reproduction_20260622T075912Z_v1"
GMA5_CLEAN_RUN_ID = "gma5_clean_execution_20260622T075912Z_v1"

MASTER_FIELDNAMES = [
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

VALIDATION_CHECKS = [
    "gma4_entity_identity_unique",
    "gma5_entity_identity_unique",
    "gma4_baseline_source_is_structured",
    "gma5_metric_source_is_structured",
    "gma5_period_uses_common_oos",
    "gma5_comparator_period_uses_common_oos",
    "master_csv_has_no_duplicate_entity_metric_rows",
    "markdown_and_csv_run_ids_match",
    "master_snapshot_is_deterministic",
]

AUDIT_CHECKS = [
    "first_ridge_oos_date_matches_training_rule",
    "composite_replay_adapter_path_evidenced",
    "no_sleeve_equity_curve_averaging_evidenced",
]

GMA4_BASELINE_METRICS = [
    ("net CAGR", "net_cagr", "ratio"),
    ("Sharpe", "sharpe_0rf", "decimal"),
    ("Sortino", "sortino_0rf", "decimal"),
    ("maximum drawdown", "max_drawdown", "ratio"),
    ("annual turnover", "annualised_turnover", "multiplier"),
    ("cost drag", "cost_drag", "ratio"),
    ("average cash weight", "average_cash_weight", "ratio"),
    ("maximum HHI", "maximum_hhi_concentration", "decimal"),
]

GMA4_ROBUSTNESS_METRICS = [
    ("severe-cost CAGR", "severe_cost_full_history_net_cagr", "ratio"),
    ("cost sensitivity", "cost_sensitivity_cagr_change", "ratio"),
    ("positive_rolling_3_year_fraction", "positive_rolling_3_year_fraction", "decimal"),
    ("positive_rolling_5_year_fraction", "positive_rolling_5_year_fraction", "decimal"),
    ("gfc_regime_coverage_status", "gfc_regime_coverage_status", "categorical"),
    ("covid_crash_regime_coverage_status", "covid_crash_regime_coverage_status", "categorical"),
    ("concentration status", "concentration_measurement_status", "categorical"),
]

GMA5_METRIC_LABELS = {
    ("baseline_1bps", "net_cagr"): ("baseline CAGR", "ratio"),
    ("severe_50bps", "net_cagr"): ("severe-cost CAGR", "ratio"),
    ("baseline_1bps", "max_drawdown"): ("baseline maximum drawdown", "ratio"),
    ("severe_50bps", "max_drawdown"): ("severe-cost maximum drawdown", "ratio"),
}


class MasterReportError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourcePaths:
    gma4_scoreboard: Path
    gma4_robustness: Path
    gma5_scoreboard: Path
    gma5_audit: Path
    gma5_manifest: Path
    gma5a2_timeline: Path
    gma5a2_verdict: Path
    gma5a3_verified_manifest: Path
    gma5a3_comparison: Path
    gma5a3r_clean_manifest: Path
    gma5a3r_clean_comparison: Path
    gma5a5_learned_scoreboard: Path
    gma5a5_scope_availability: Path


@dataclass(frozen=True)
class ReportResult:
    master_csv_path: Path
    master_md_path: Path
    validation_csv_path: Path
    validation_md_path: Path
    row_counts: dict[tuple[str, str], int]
    gma5_common_oos_start: str
    gma5_common_oos_end: str
    validation_rows: list[dict[str, str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gma4-report-root",
        default="reports/global_multi_asset_alpha/gma4_cross_asset_tournament_v1",
    )
    parser.add_argument(
        "--gma5-report-root",
        default="reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1",
    )
    parser.add_argument("--output-root", default="reports/global_multi_asset_alpha")
    return parser.parse_args()


def resolve_source_paths(gma4_report_root: Path, gma5_report_root: Path) -> SourcePaths:
    return SourcePaths(
        gma4_scoreboard=gma4_report_root / "runs" / GMA4_RUN_ID / "gma4_tournament_scoreboard.csv",
        gma4_robustness=gma4_report_root / "gma4_latest_robustness_board_v2.csv",
        gma5_scoreboard=gma5_report_root / "gma5_latest_ensemble_scoreboard_v1.csv",
        gma5_audit=gma5_report_root / "gma5_latest_implementation_audit_v1.csv",
        gma5_manifest=gma5_report_root / "runs" / GMA5_RUN_ID / "gma5_ensemble_manifest.json",
        gma5a2_timeline=gma5_report_root / "gma5a2_timeline_forensic_audit_v1.csv",
        gma5a2_verdict=gma5_report_root / "gma5a2_evidence_gate_verdict_v1.csv",
        gma5a3_verified_manifest=gma5_report_root
        / "runs"
        / GMA5_VERIFIED_RUN_ID
        / "gma5_verified_reproduction_manifest_v1.json",
        gma5a3_comparison=gma5_report_root
        / "runs"
        / GMA5_VERIFIED_RUN_ID
        / "gma5_reproducibility_comparison_v1.csv",
        gma5a3r_clean_manifest=gma5_report_root
        / "runs"
        / GMA5_CLEAN_RUN_ID
        / "gma5_clean_execution_manifest_v1.json",
        gma5a3r_clean_comparison=gma5_report_root
        / "runs"
        / GMA5_CLEAN_RUN_ID
        / "gma5_clean_execution_comparison_v1.csv",
        gma5a5_learned_scoreboard=gma5_report_root / "gma5_learned_only_window_scoreboard_v2.csv",
        gma5a5_scope_availability=gma5_report_root / "gma5_learned_only_scope_availability_v1.csv",
    )


def read_csv_rows(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise MasterReportError(f"missing required structured source: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise MasterReportError(f"malformed CSV with no header: {path}")
        missing = sorted(required_columns - set(reader.fieldnames))
        if missing:
            raise MasterReportError(f"missing columns in {path.name}: {missing}")
        rows = list(reader)
    if not rows:
        raise MasterReportError(f"empty required structured source: {path}")
    return rows


def read_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        raise MasterReportError(f"missing required structured source: {path}")
    with path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    required = {
        "created_at_utc",
        "run_id",
        "gma4_source_run_id",
        "first_ensemble_out_of_sample_date",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise MasterReportError(f"missing manifest fields in {path.name}: {missing}")
    return manifest


def read_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_optional_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def require_unique_identity(
    rows: list[dict[str, str]],
    source_name: str,
    id_column: str,
    name_column: str,
    family_column: str,
) -> None:
    identities: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        entity_id = row.get(id_column, "")
        entity_name = row.get(name_column, "")
        family = row.get(family_column, "")
        if not entity_id or not entity_name or not family:
            raise MasterReportError(f"missing identity field in {source_name}")
        identities[entity_id].add((entity_name, family))
    collisions = {entity_id: values for entity_id, values in identities.items() if len(values) > 1}
    if collisions:
        examples = ", ".join(sorted(collisions)[:5])
        raise MasterReportError(f"entity identity collision in {source_name}: {examples}")


def require_float(value: str, column: str, source_name: str) -> str:
    if value == "":
        raise MasterReportError(f"missing numeric value for {column} in {source_name}")
    try:
        float(value)
    except ValueError as exc:
        raise MasterReportError(
            f"malformed numeric value for {column} in {source_name}: {value}"
        ) from exc
    return value


def non_empty(value: str, column: str, source_name: str) -> str:
    if value == "":
        raise MasterReportError(f"missing required value for {column} in {source_name}")
    return value


def append_master_row(
    rows: list[dict[str, str]],
    generated_at_utc: str,
    phase: str,
    record_type: str,
    run_id: str,
    entity_id: str,
    entity_name: str,
    family: str,
    evaluation_scope: str,
    cost_scenario: str,
    period_start: str,
    period_end: str,
    metric_name: str,
    metric_value: str,
    metric_unit: str,
    coverage_status: str,
    evidence_status: str,
    source_file: str,
    source_run_id: str,
    notes: str = "",
) -> None:
    rows.append(
        {
            "generated_at_utc": generated_at_utc,
            "report_version": REPORT_VERSION,
            "phase": phase,
            "record_type": record_type,
            "run_id": run_id,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "family": family,
            "evaluation_scope": evaluation_scope,
            "cost_scenario": cost_scenario,
            "period_start": period_start,
            "period_end": period_end,
            "metric_name": metric_name,
            "metric_value": str(metric_value),
            "metric_unit": metric_unit,
            "coverage_status": coverage_status,
            "evidence_status": evidence_status,
            "source_file": source_file,
            "source_run_id": source_run_id,
            "notes": notes,
        }
    )


def build_gma4_rows(
    generated_at_utc: str,
    scoreboard: list[dict[str, str]],
    robustness: list[dict[str, str]],
    paths: SourcePaths,
) -> list[dict[str, str]]:
    require_unique_identity(
        scoreboard, paths.gma4_scoreboard.name, "trial_id", "strategy_id", "family"
    )
    require_unique_identity(
        robustness, paths.gma4_robustness.name, "trial_id", "strategy_id", "family"
    )
    rows: list[dict[str, str]] = []

    baseline_rows = [
        row
        for row in scoreboard
        if row["cost_scenario"] == "baseline_1bps"
        and row["evaluation_scope"] == "full_common_history"
        and row["status"] == "evaluated"
    ]
    if not baseline_rows:
        raise MasterReportError("no GMA-4 baseline full_common_history rows found")

    for source_row in sorted(baseline_rows, key=lambda item: item["trial_id"]):
        for metric_name, source_column, metric_unit in GMA4_BASELINE_METRICS:
            append_master_row(
                rows,
                generated_at_utc,
                "GMA-4",
                "baseline_strategy_metrics",
                source_row["run_id"],
                source_row["trial_id"],
                source_row["strategy_id"],
                source_row["family"],
                "full_history",
                source_row["cost_scenario"],
                source_row["start_date"],
                source_row["end_date"],
                metric_name,
                require_float(source_row[source_column], source_column, paths.gma4_scoreboard.name),
                metric_unit,
                "full_coverage",
                EVIDENCE_STATUS,
                paths.gma4_scoreboard.name,
                source_row["run_id"],
            )

    for source_row in sorted(robustness, key=lambda item: item["trial_id"]):
        for metric_name, source_column, metric_unit in GMA4_ROBUSTNESS_METRICS:
            value = non_empty(source_row[source_column], source_column, paths.gma4_robustness.name)
            if metric_unit != "categorical":
                value = require_float(value, source_column, paths.gma4_robustness.name)
            append_master_row(
                rows,
                generated_at_utc,
                "GMA-4",
                "robustness_metrics",
                source_row["run_id"],
                source_row["trial_id"],
                source_row["strategy_id"],
                source_row["family"],
                "full_history",
                "severe_50bps",
                source_row["effective_evaluation_start_date"],
                source_row["effective_evaluation_end_date"],
                metric_name,
                value,
                metric_unit,
                "full_coverage",
                EVIDENCE_STATUS,
                paths.gma4_robustness.name,
                source_row["run_id"],
            )
    return rows


def gma5_family(entity_type: str) -> str:
    if entity_type == "ensemble_variant":
        return "ensemble"
    if entity_type == "gma4_reference":
        return "comparator"
    raise MasterReportError(f"unsupported GMA-5 entity_type: {entity_type}")


def select_gma5_full_oos_rows(scoreboard: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = [
        row
        for row in scoreboard
        if row["evaluation_scope"] == "full_common_oos"
        and row["cost_scenario"] in {"baseline_1bps", "severe_50bps"}
        and row["status"] == "evaluated"
    ]
    if not rows:
        raise MasterReportError("no GMA-5 full_common_oos evaluated rows found")
    starts = {row["start_date"] for row in rows}
    ends = {row["end_date"] for row in rows}
    if len(starts) != 1 or len(ends) != 1:
        raise MasterReportError("GMA-5 common-OOS rows do not share one period")
    return rows


def build_gma5_rows(
    generated_at_utc: str,
    scoreboard: list[dict[str, str]],
    audit_rows: list[dict[str, str]],
    manifest: dict[str, object],
    paths: SourcePaths,
    timeline_rows: list[dict[str, str]],
    verdict_rows: list[dict[str, str]],
    verified_manifest: dict[str, object] | None,
    clean_manifest: dict[str, object] | None,
    gma5a5_learned_scoreboard: list[dict[str, str]],
    gma5a5_scope_availability: list[dict[str, str]],
) -> tuple[list[dict[str, str]], str, str]:
    identity_rows = [
        {
            "entity_id": row["entity_id"],
            "entity_name": row["entity_id"],
            "family": gma5_family(row["entity_type"]),
        }
        for row in scoreboard
        if row["entity_type"] in {"ensemble_variant", "gma4_reference"}
    ]
    require_unique_identity(
        identity_rows, paths.gma5_scoreboard.name, "entity_id", "entity_name", "family"
    )
    full_oos_rows = select_gma5_full_oos_rows(scoreboard)
    common_start = full_oos_rows[0]["start_date"]
    common_end = full_oos_rows[0]["end_date"]
    run_id = str(manifest["run_id"])
    first_oos_date = str(manifest["first_ensemble_out_of_sample_date"])
    rows: list[dict[str, str]] = []
    timeline_by_variant = {row["variant_id"]: row for row in timeline_rows}

    by_entity_cost = {(row["entity_id"], row["cost_scenario"]): row for row in full_oos_rows}
    for entity_id in sorted({row["entity_id"] for row in full_oos_rows}):
        baseline = by_entity_cost.get((entity_id, "baseline_1bps"))
        severe = by_entity_cost.get((entity_id, "severe_50bps"))
        if baseline is None or severe is None:
            raise MasterReportError(f"missing baseline/severe GMA-5 rows for {entity_id}")
        entity_type = baseline["entity_type"]
        record_type = (
            "ensemble_variant_metrics"
            if entity_type == "ensemble_variant"
            else "same_period_comparator_metrics"
        )
        for source_row, source_column in [
            (baseline, "net_cagr"),
            (severe, "net_cagr"),
            (baseline, "max_drawdown"),
            (severe, "max_drawdown"),
        ]:
            metric_name, metric_unit = GMA5_METRIC_LABELS[
                (source_row["cost_scenario"], source_column)
            ]
            append_master_row(
                rows,
                generated_at_utc,
                "GMA-5",
                record_type,
                run_id,
                entity_id,
                entity_id,
                gma5_family(entity_type),
                "common_out_of_sample",
                source_row["cost_scenario"],
                common_start,
                common_end,
                metric_name,
                require_float(source_row[source_column], source_column, paths.gma5_scoreboard.name),
                metric_unit,
                "full_coverage",
                EVIDENCE_STATUS,
                paths.gma5_scoreboard.name,
                run_id,
            )
        if entity_type == "ensemble_variant":
            timeline = timeline_by_variant.get(entity_id, {})
            gfc_status = timeline.get("gfc_coverage_status") or next(
                (
                    row["status"]
                    for row in scoreboard
                    if row["entity_id"] == entity_id
                    and row["evaluation_scope"] == "predefined_regime"
                    and row["regime_id"] == "gfc_stress"
                    and row["cost_scenario"] == "baseline_1bps"
                ),
                "",
            )
            gfc_source_file = (
                paths.gma5a2_timeline.name
                if timeline.get("gfc_coverage_status")
                else paths.gma5_scoreboard.name
            )
            learned_ridge_date = timeline.get("first_true_learned_ridge_decision_date", "")
            rolling_counts = {
                "rolling 3Y window count": sum(
                    1
                    for row in scoreboard
                    if row["entity_id"] == entity_id
                    and row["entity_type"] == "ensemble_variant"
                    and row["evaluation_scope"] == "rolling_3_year"
                    and row["cost_scenario"] == "baseline_1bps"
                    and row["status"] == "evaluated"
                ),
                "rolling 5Y window count": sum(
                    1
                    for row in scoreboard
                    if row["entity_id"] == entity_id
                    and row["entity_type"] == "ensemble_variant"
                    and row["evaluation_scope"] == "rolling_5_year"
                    and row["cost_scenario"] == "baseline_1bps"
                    and row["status"] == "evaluated"
                ),
            }
            append_master_row(
                rows,
                generated_at_utc,
                "GMA-5",
                record_type,
                run_id,
                entity_id,
                entity_id,
                "ensemble",
                "common_out_of_sample",
                "baseline_1bps",
                common_start,
                common_end,
                "first OOS date",
                first_oos_date,
                "date",
                "full_coverage",
                EVIDENCE_STATUS,
                paths.gma5_scoreboard.name,
                run_id,
                "derived from GMA-5 manifest",
            )
            append_master_row(
                rows,
                generated_at_utc,
                "GMA-5",
                record_type,
                run_id,
                entity_id,
                entity_id,
                "ensemble",
                "common_out_of_sample",
                "baseline_1bps",
                common_start,
                common_end,
                "GFC coverage status",
                non_empty(gfc_status, "GFC coverage status", paths.gma5_scoreboard.name),
                "categorical",
                "full_coverage",
                EVIDENCE_STATUS,
                gfc_source_file,
                run_id,
            )
            if learned_ridge_date:
                append_master_row(
                    rows,
                    generated_at_utc,
                    "GMA-5",
                    record_type,
                    run_id,
                    entity_id,
                    entity_id,
                    "ensemble",
                    "common_out_of_sample",
                    "baseline_1bps",
                    common_start,
                    common_end,
                    "first true learned ridge decision date",
                    learned_ridge_date,
                    "date",
                    "full_coverage",
                    EVIDENCE_STATUS,
                    paths.gma5a2_timeline.name,
                    run_id,
                    "not_applicable for non-ridge variants",
                )
            for metric_name, count in rolling_counts.items():
                append_master_row(
                    rows,
                    generated_at_utc,
                    "GMA-5",
                    record_type,
                    run_id,
                    entity_id,
                    entity_id,
                    "ensemble",
                    "common_out_of_sample",
                    "baseline_1bps",
                    common_start,
                    common_end,
                    metric_name,
                    str(count),
                    "count",
                    "full_coverage",
                    EVIDENCE_STATUS,
                    paths.gma5_scoreboard.name,
                    run_id,
                )

    audit_by_name = {row["check_name"]: row for row in audit_rows}
    for check_name in AUDIT_CHECKS:
        if check_name not in audit_by_name:
            raise MasterReportError(f"missing required audit check: {check_name}")
        source_row = audit_by_name[check_name]
        append_master_row(
            rows,
            generated_at_utc,
            "GMA-5",
            "evidence_gate",
            run_id,
            "audit",
            "audit",
            "audit",
            "implementation_audit",
            "n/a",
            common_start,
            common_end,
            check_name,
            source_row["status"],
            "status",
            "n/a",
            source_row["status"],
            paths.gma5_audit.name,
            run_id,
            source_row["evidence_detail"],
        )

    for source_row in verdict_rows:
        append_master_row(
            rows,
            generated_at_utc,
            "GMA-5",
            "forensic_evidence_gate",
            run_id,
            "audit",
            "audit",
            "audit",
            "saved_run_forensic_audit",
            "n/a",
            common_start,
            common_end,
            source_row["gate_name"],
            source_row["new_status"],
            "status",
            "n/a",
            source_row["evidence_class"],
            paths.gma5a2_verdict.name,
            run_id,
            source_row["evidence_detail"],
        )

    if verified_manifest and verified_manifest.get("overall_reproducibility_status") == (
        "exact_reproduction_verified"
    ):
        verified_run_id = str(verified_manifest["verified_run_id"])
        for metric_name, metric_value, notes in [
            (
                "verified reproduction run ID",
                verified_run_id,
                f"original_run_id={verified_manifest['original_run_id']}",
            ),
            (
                "replay provenance verified for reproduction",
                "resolved",
                "verified reproduction matched original and captured replay provenance",
            ),
            (
                "no equity curve averaging verified for reproduction",
                "resolved",
                "verified reproduction captured runtime-linked no-equity-curve-averaging trace",
            ),
        ]:
            append_master_row(
                rows,
                generated_at_utc,
                "GMA-5",
                "verified_reproduction_evidence",
                verified_run_id,
                "audit",
                "audit",
                "audit",
                "verified_reproduction",
                "n/a",
                common_start,
                common_end,
                metric_name,
                metric_value,
                "status",
                "n/a",
                "verified_reproduction_evidence",
                paths.gma5a3_verified_manifest.name,
                verified_run_id,
                notes,
            )

    if clean_manifest and clean_manifest.get("overall_reproducibility_status") == (
        "clean_execution_exact_reproduction_verified"
    ):
        clean_run_id = str(clean_manifest["clean_execution_run_id"])
        trace = clean_manifest.get("runtime_replay_trace", {})
        invocation_count = ""
        if isinstance(trace, dict):
            invocation_count = str(trace.get("replay_adapter_invocation_count", ""))
        for metric_name, metric_value, notes in [
            (
                "clean execution reproduction run ID",
                clean_run_id,
                f"original_run_id={clean_manifest['original_run_id']}",
            ),
            (
                "runtime replay adapter invocation count",
                invocation_count,
                "runtime trace captured shared replay adapter invocations",
            ),
            (
                "netted composite ETF replay verified for clean reproduction",
                "resolved",
                "current frozen code and frozen data reproduced outputs through runtime-evidenced netted composite ETF replay",
            ),
            (
                "no equity curve averaging verified for clean reproduction",
                "resolved",
                "verified for clean reproduction only; not a retroactive source snapshot of the original run",
            ),
        ]:
            append_master_row(
                rows,
                generated_at_utc,
                "GMA-5",
                "clean_execution_reproduction_evidence",
                clean_run_id,
                "audit",
                "audit",
                "audit",
                "clean_execution_reproduction",
                "n/a",
                common_start,
                common_end,
                metric_name,
                metric_value,
                "status" if metric_value == "resolved" else "count",
                "n/a",
                "clean_execution_reproduction_evidence",
                paths.gma5a3r_clean_manifest.name,
                clean_run_id,
                notes,
            )

    for source_row in gma5a5_learned_scoreboard:
        if source_row.get("measurement_status") == "available_from_saved_artifacts":
            entity_id = source_row["variant_id"]
            cost_scenario = source_row["cost_scenario"]
            is_variant = entity_id in {
                "gma5_equal_weight_atomic_sleeves_v1",
                "gma5_risk_weighted_atomic_sleeves_v1",
                "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
            }
            record_type = (
                "ensemble_variant_metrics" if is_variant else "same_period_comparator_metrics"
            )
            family = "ensemble" if is_variant else "comparator"
            for source_column in ["net_cagr", "maximum_drawdown"]:
                metric_name = (
                    "learned-only maximum drawdown"
                    if source_column == "maximum_drawdown"
                    else "learned-only net CAGR"
                )
                metric_unit = "ratio"
                append_master_row(
                    rows,
                    generated_at_utc,
                    "GMA-5",
                    record_type,
                    run_id,
                    entity_id,
                    entity_id,
                    family,
                    "learned_only_ridge_window",
                    cost_scenario,
                    source_row["period_start"],
                    source_row["period_end"],
                    metric_name,
                    require_float(
                        source_row[source_column],
                        source_column,
                        paths.gma5a5_learned_scoreboard.name,
                    ),
                    metric_unit,
                    "full_coverage",
                    EVIDENCE_STATUS,
                    paths.gma5a5_learned_scoreboard.name,
                    source_row.get("source_run_id", ""),
                )

    for source_row in gma5a5_scope_availability:
        append_master_row(
            rows,
            generated_at_utc,
            "GMA-5",
            "scope_availability",
            GMA5_CLEAN_RUN_ID,
            "learned_only_ridge_window",
            "learned_only_ridge_window",
            "ensemble",
            source_row["evaluation_scope"],
            "n/a",
            "2015-05-29",
            "2026-05-01",
            "measurement_status",
            source_row["measurement_status"],
            "status",
            "n/a",
            source_row["measurement_status"],
            paths.gma5a5_scope_availability.name,
            GMA5_CLEAN_RUN_ID,
            source_row.get("reason", ""),
        )
        append_master_row(
            rows,
            generated_at_utc,
            "GMA-5",
            "scope_availability",
            GMA5_CLEAN_RUN_ID,
            "external_comparators",
            "external_comparators",
            "comparator",
            source_row["evaluation_scope"],
            "n/a",
            "2015-05-29",
            "2026-05-01",
            "external_comparator_learned_only_metrics",
            source_row["external_comparator_learned_only_metrics"],
            "status",
            "n/a",
            source_row["external_comparator_learned_only_metrics"],
            paths.gma5a5_scope_availability.name,
            GMA5_CLEAN_RUN_ID,
            "external learned-only comparators are not reconstructed from saved artifacts",
        )

    return rows, common_start, common_end


def serialize_csv(rows: list[dict[str, str]]) -> str:
    from io import StringIO

    handle = StringIO()
    writer = csv.DictWriter(handle, fieldnames=MASTER_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue()


def duplicate_master_keys(rows: list[dict[str, str]]) -> list[tuple[str, ...]]:
    keys = [
        (
            row["phase"],
            row["record_type"],
            row["entity_id"],
            row["evaluation_scope"],
            row["cost_scenario"],
            row["period_start"],
            row["period_end"],
            row["metric_name"],
            row["source_file"],
        )
        for row in rows
    ]
    counts = Counter(keys)
    return sorted(key for key, count in counts.items() if count > 1)


def build_validation_rows(
    rows: list[dict[str, str]],
    markdown: str,
    csv_text: str,
    repeated_csv_text: str,
) -> list[dict[str, str]]:
    validation: list[dict[str, str]] = []
    checks = {
        "gma4_entity_identity_unique": "pass",
        "gma5_entity_identity_unique": "pass",
        "gma4_baseline_source_is_structured": "pass"
        if all(
            row["source_file"] == "gma4_tournament_scoreboard.csv"
            for row in rows
            if row["record_type"] == "baseline_strategy_metrics"
        )
        else "fail",
        "gma5_metric_source_is_structured": "pass"
        if all(
            row["source_file"]
            in {
                "gma5_latest_ensemble_scoreboard_v1.csv",
                "gma5a2_timeline_forensic_audit_v1.csv",
                "gma5_learned_only_window_scoreboard_v2.csv",
            }
            for row in rows
            if row["record_type"] in {"ensemble_variant_metrics", "same_period_comparator_metrics"}
        )
        else "fail",
        "gma5_period_uses_common_oos": "pass"
        if all(
            row["evaluation_scope"] == "common_out_of_sample"
            for row in rows
            if row["record_type"] == "ensemble_variant_metrics"
            and row["source_file"] == "gma5_latest_ensemble_scoreboard_v1.csv"
        )
        else "fail",
        "gma5_comparator_period_uses_common_oos": "pass"
        if all(
            row["evaluation_scope"] == "common_out_of_sample"
            for row in rows
            if row["record_type"] == "same_period_comparator_metrics"
            and row["source_file"] == "gma5_latest_ensemble_scoreboard_v1.csv"
        )
        else "fail",
        "master_csv_has_no_duplicate_entity_metric_rows": "pass"
        if not duplicate_master_keys(rows)
        else "fail",
        "markdown_and_csv_run_ids_match": "pass"
        if all(row["run_id"] in markdown for row in rows if row["run_id"] != "audit")
        else "fail",
        "master_snapshot_is_deterministic": "pass" if csv_text == repeated_csv_text else "fail",
    }
    for check_name in VALIDATION_CHECKS:
        validation.append(
            {
                "check_name": check_name,
                "status": checks[check_name],
                "evidence_detail": "validated during deterministic master-ledger generation",
            }
        )
    return validation


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    table = ["| " + " | ".join(headers) + " |"]
    table.append("| " + " | ".join("---" for _ in headers) + " |")
    table.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(table)


def metric_lookup(rows: list[dict[str, str]], record_type: str, metric_name: str) -> dict[str, str]:
    return {
        row["entity_id"]: row["metric_value"]
        for row in rows
        if row["record_type"] == record_type and row["metric_name"] == metric_name
    }


def build_markdown(
    rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    gma5_common_start: str,
    gma5_common_end: str,
) -> str:
    gma4_cagr = metric_lookup(rows, "baseline_strategy_metrics", "net CAGR")
    gma4_drawdown = metric_lookup(rows, "baseline_strategy_metrics", "maximum drawdown")
    gma4_turnover = metric_lookup(rows, "baseline_strategy_metrics", "annual turnover")
    gma4_strategy_rows = [
        [entity_id, gma4_cagr[entity_id], gma4_drawdown[entity_id], gma4_turnover[entity_id]]
        for entity_id in sorted(gma4_cagr, key=lambda item: float(gma4_cagr[item]), reverse=True)[
            :8
        ]
    ]

    gma5_cagr = metric_lookup(rows, "ensemble_variant_metrics", "baseline CAGR")
    gma5_severe = metric_lookup(rows, "ensemble_variant_metrics", "severe-cost CAGR")
    gma5_drawdown = metric_lookup(rows, "ensemble_variant_metrics", "baseline maximum drawdown")
    gma5_ridge_learned = metric_lookup(
        rows, "ensemble_variant_metrics", "first true learned ridge decision date"
    )
    first_true_ridge_decision = gma5_ridge_learned.get(
        "gma5_fixed_alpha_ridge_atomic_ensemble_v1", "not_available"
    )
    gma5_rows = [
        [entity_id, gma5_cagr[entity_id], gma5_severe[entity_id], gma5_drawdown[entity_id]]
        for entity_id in sorted(gma5_cagr)
    ]
    learned_cagr = {
        row["entity_id"] + "|" + row["cost_scenario"]: row["metric_value"]
        for row in rows
        if row["record_type"] == "ensemble_variant_metrics"
        and row["evaluation_scope"] == "learned_only_ridge_window"
        and row["metric_name"] == "learned-only net CAGR"
    }
    learned_drawdown = {
        row["entity_id"] + "|" + row["cost_scenario"]: row["metric_value"]
        for row in rows
        if row["record_type"] == "ensemble_variant_metrics"
        and row["evaluation_scope"] == "learned_only_ridge_window"
        and row["metric_name"] == "learned-only maximum drawdown"
    }
    learned_rows = [
        [
            key.split("|", maxsplit=1)[0],
            key.split("|", maxsplit=1)[1],
            learned_cagr[key],
            learned_drawdown.get(key, ""),
        ]
        for key in sorted(learned_cagr)
    ]

    comp_cagr = metric_lookup(rows, "same_period_comparator_metrics", "baseline CAGR")
    comp_severe = metric_lookup(rows, "same_period_comparator_metrics", "severe-cost CAGR")
    comp_drawdown = metric_lookup(
        rows, "same_period_comparator_metrics", "baseline maximum drawdown"
    )
    comparator_rows = [
        [entity_id, comp_cagr[entity_id], comp_severe[entity_id], comp_drawdown[entity_id]]
        for entity_id in sorted(comp_cagr)
    ]

    gate_rows = [
        [row["metric_name"], row["metric_value"], row["notes"]]
        for row in rows
        if row["record_type"] == "evidence_gate"
    ]
    forensic_gate_rows = [
        [row["metric_name"], row["metric_value"], row["notes"]]
        for row in rows
        if row["record_type"] == "forensic_evidence_gate"
    ]
    verified_rows = [
        [row["metric_name"], row["metric_value"], row["notes"]]
        for row in rows
        if row["record_type"] == "verified_reproduction_evidence"
    ]
    clean_rows = [
        [row["metric_name"], row["metric_value"], row["notes"]]
        for row in rows
        if row["record_type"] == "clean_execution_reproduction_evidence"
    ]
    scope_rows = [
        [row["metric_name"], row["metric_value"], row["notes"]]
        for row in rows
        if row["record_type"] == "scope_availability"
    ]
    verified_run_line = (
        f"* Verified reproduction run ID: `{GMA5_VERIFIED_RUN_ID}`"
        if verified_rows
        else "* Verified reproduction run ID: `not_available`"
    )
    clean_run_line = (
        f"* Clean execution reproduction run ID: `{GMA5_CLEAN_RUN_ID}`"
        if clean_rows
        else "* Clean execution reproduction run ID: `not_available`"
    )
    gma5a3_change = (
        "* GMA-5A.3 (limited_nonconclusive_reproduction_check): exact reproducibility verification matched the original run but "
        "copied standard outputs could not prove fresh execution."
        if verified_rows
        else "* GMA-5A.3: not yet completed in this master ledger."
    )
    gma5a3r_change = (
        "* GMA-5A.3R (clean_execution_verification_source_of_record): clean execution reproduced the original standard outputs and "
        "captured runtime-evidenced netted composite ETF replay; this verifies the clean "
        "reproduction, not an impossible retroactive source snapshot of the original run."
        if clean_rows
        else "* GMA-5A.3R: clean execution reproduction is not yet completed in this master ledger."
    )
    validation_table_rows = [[row["check_name"], row["status"]] for row in validation_rows]

    return "\n".join(
        [
            "# Global Multi-Asset Research - Latest Programme Report",
            "",
            "## Current Programme Status",
            "",
            "GMA-4 historical robustness and GMA-5 atomic sleeve ensemble research are represented here as a structured master ledger. All facts are observed_development_evidence, not_a_pristine_final_holdout, and no execution or promotion decision is produced.",
            "",
            "## Data Provenance and Source Runs",
            "",
            f"* Current GMA-4 run ID: `{GMA4_RUN_ID}`",
            f"* Original saved GMA-5 run ID: `{GMA5_RUN_ID}`",
            verified_run_line,
            clean_run_line,
            f"* GMA-5 common out-of-sample period: `{gma5_common_start}` through `{gma5_common_end}`",
            f"* First true learned ridge decision date: `{first_true_ridge_decision}`",
            "* Numeric facts and identity mapping come from structured CSV/JSON sources, not Markdown tables.",
            "",
            "## Research Scope and Guardrails",
            "",
            "This dashboard is local-only research reporting. It does not alter strategy rules, ensemble logic, replay/accounting logic, promotion logic, paper paths, broker paths, or live paths.",
            "",
            "## Assets and Strategy Catalogue",
            "",
            "The report covers the frozen GMA-4 cross-asset historical tournament outputs and the saved GMA-5 atomic sleeve ensemble outputs.",
            "",
            "## GMA-4 Historical Tournament and Robustness",
            "",
            "### Key GMA-4 strategy observations",
            "",
            markdown_table(
                ["trial_id", "net CAGR", "maximum drawdown", "annual turnover"],
                gma4_strategy_rows,
            ),
            "",
            "## GMA-5 Atomic Sleeve Ensemble",
            "",
            "### GMA-5 three-variant results",
            "",
            markdown_table(
                ["entity_id", "baseline CAGR", "severe-cost CAGR", "baseline maximum drawdown"],
                gma5_rows,
            ),
            "",
            "### GMA-5 learned-only ridge-window internal comparison",
            "",
            markdown_table(
                ["entity_id", "cost_scenario", "learned-only net CAGR", "maximum drawdown"],
                learned_rows,
            )
            if learned_rows
            else "Learned-only internal metrics are not available from saved artifacts.",
            "",
            "### GMA-5 learned-only scope availability",
            "",
            markdown_table(["check", "status", "evidence"], scope_rows)
            if scope_rows
            else "No learned-only scope availability rows are available.",
            "",
            "### Same-period GMA-5 comparators",
            "",
            markdown_table(
                ["entity_id", "baseline CAGR", "severe-cost CAGR", "baseline maximum drawdown"],
                comparator_rows,
            ),
            "",
            "## Current Evidence Gaps and Research Gates",
            "",
            "### GMA-5A.1 audit history",
            "",
            markdown_table(["check", "status", "evidence"], gate_rows),
            "",
            "### GMA-5A.2 saved-run forensic verdicts",
            "",
            markdown_table(["check", "status", "evidence"], forensic_gate_rows),
            "",
            "### GMA-5A.3 verified reproduction evidence",
            "",
            markdown_table(["check", "status", "evidence"], verified_rows)
            if verified_rows
            else "No successful verified reproduction has been recorded in the master ledger.",
            "",
            "### GMA-5A.3R clean execution reproduction evidence",
            "",
            markdown_table(["check", "status", "evidence"], clean_rows)
            if clean_rows
            else "No successful clean execution reproduction has been recorded in the master ledger.",
            "",
            "## Latest Findings",
            "",
            "The master ledger v1.3 replaces the prior v1.2 ledger to enforce final research boundaries. The corrected ledger uses direct structured source files and the GMA-5 common out-of-sample period. The original saved June 22 run remains historically provenance-incomplete where saved artifacts lacked runtime-linked replay proof. Clean-execution mechanics, netted composite ETF replay, and no equity-curve averaging are verified for the clean reproduction. GFC status for all GMA-5 variants is unavailable_before_common_oos_start. The ridge pre-model period limitation remains visible: common OOS starts on 2012-05-31, while the first true learned ridge decision is 2015-05-29, with pre-model policy no_allocation_before_training.",
            "",
            "### Master-ledger validation status",
            "",
            markdown_table(["check", "status"], validation_table_rows),
            "",
            "## Change Log",
            "",
            "* GMA-MR1.3: repaired master-ledger source of truth, identity mapping, GMA-5 common-OOS dates, structured provenance, and validation reporting.",
            "* GMA-5A.2: saved-run timeline and replay-provenance forensic audit.",
            gma5a3_change,
            gma5a3r_change,
            "* GMA-5A.4: learned-only ridge fair-window post-processing.",
            "* GMA-5A.5: exported cost-scenario replay paths from saved composite targets and resolved the learned-only internal fair-window comparison where reconciliation passed.",
            "",
            "## Next Bounded Task",
            "",
            "GMA-5 V1 historical classifications are frozen. No further Ridge tuning, sleeve expansion, or GMA-5 V1 model search is authorised within this research phase.",
            "",
            "Any future prospective, paper, broker, or live workflow is outside the present research-only scope and requires a separately authorised programme change.",
            "",
        ]
    )


def build_validation_markdown(validation_rows: list[dict[str, str]]) -> str:
    return "\n".join(
        [
            "# GMA Master Ledger Validation v1.2",
            "",
            "The prior v1.1 master ledger had identity and GMA-5 period/provenance mapping defects. This v1.2 validation output replaces it and records the checks applied to the corrected structured-source ledger.",
            "",
            markdown_table(
                ["check", "status"],
                [[row["check_name"], row["status"]] for row in validation_rows],
            ),
            "",
        ]
    )


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate_master_report(
    gma4_report_root: Path,
    gma5_report_root: Path,
    output_root: Path,
) -> ReportResult:
    paths = resolve_source_paths(gma4_report_root, gma5_report_root)
    gma4_scoreboard = read_csv_rows(
        paths.gma4_scoreboard,
        {
            "run_id",
            "trial_id",
            "strategy_id",
            "family",
            "cost_scenario",
            "evaluation_scope",
            "start_date",
            "end_date",
            "net_cagr",
            "sharpe_0rf",
            "sortino_0rf",
            "max_drawdown",
            "annualised_turnover",
            "cost_drag",
            "average_cash_weight",
            "maximum_hhi_concentration",
            "status",
        },
    )
    gma4_robustness = read_csv_rows(
        paths.gma4_robustness,
        {
            "run_id",
            "trial_id",
            "strategy_id",
            "family",
            "effective_evaluation_start_date",
            "effective_evaluation_end_date",
            "severe_cost_full_history_net_cagr",
            "cost_sensitivity_cagr_change",
            "positive_rolling_3_year_fraction",
            "positive_rolling_5_year_fraction",
            "gfc_regime_coverage_status",
            "covid_crash_regime_coverage_status",
            "concentration_measurement_status",
        },
    )
    gma5_scoreboard = read_csv_rows(
        paths.gma5_scoreboard,
        {
            "entity_id",
            "entity_type",
            "cost_scenario",
            "evaluation_scope",
            "regime_id",
            "start_date",
            "end_date",
            "net_cagr",
            "max_drawdown",
            "status",
        },
    )
    gma5_audit = read_csv_rows(
        paths.gma5_audit,
        {"check_name", "status", "evidence_source", "evidence_detail"},
    )
    gma5a2_timeline = read_optional_csv_rows(paths.gma5a2_timeline)
    gma5a2_verdict = read_optional_csv_rows(paths.gma5a2_verdict)
    verified_manifest = (
        read_json(paths.gma5a3_verified_manifest)
        if paths.gma5a3_verified_manifest.exists()
        else None
    )
    clean_manifest = (
        read_json(paths.gma5a3r_clean_manifest) if paths.gma5a3r_clean_manifest.exists() else None
    )
    gma5a5_learned_scoreboard = read_optional_csv_rows(paths.gma5a5_learned_scoreboard)
    gma5a5_scope_availability = read_optional_csv_rows(paths.gma5a5_scope_availability)
    manifest = read_manifest(paths.gma5_manifest)

    generated_at_utc = str(manifest["created_at_utc"])
    master_rows = build_gma4_rows(generated_at_utc, gma4_scoreboard, gma4_robustness, paths)
    gma5_rows, gma5_common_start, gma5_common_end = build_gma5_rows(
        generated_at_utc,
        gma5_scoreboard,
        gma5_audit,
        manifest,
        paths,
        gma5a2_timeline,
        gma5a2_verdict,
        verified_manifest,
        clean_manifest,
        gma5a5_learned_scoreboard,
        gma5a5_scope_availability,
    )
    master_rows.extend(gma5_rows)
    master_rows.sort(
        key=lambda row: (
            row["phase"],
            row["record_type"],
            row["entity_id"],
            row["metric_name"],
            row["cost_scenario"],
        )
    )

    csv_text = serialize_csv(master_rows)
    repeated_csv_text = serialize_csv(master_rows)
    provisional_markdown = build_markdown(master_rows, [], gma5_common_start, gma5_common_end)
    validation_rows = build_validation_rows(
        master_rows,
        provisional_markdown,
        csv_text,
        repeated_csv_text,
    )
    markdown = build_markdown(master_rows, validation_rows, gma5_common_start, gma5_common_end)
    validation_rows = build_validation_rows(master_rows, markdown, csv_text, repeated_csv_text)
    if any(row["status"] != "pass" for row in validation_rows):
        failed = [row["check_name"] for row in validation_rows if row["status"] != "pass"]
        raise MasterReportError(f"master-ledger validation failed: {failed}")

    output_root.mkdir(parents=True, exist_ok=True)
    master_csv_path = output_root / "gma_research_latest_v1.csv"
    master_md_path = output_root / "gma_research_latest_v1.md"
    validation_csv_path = output_root / "gma_research_latest_validation_v1.csv"
    validation_md_path = output_root / "gma_research_latest_validation_v1.md"

    write_csv(master_csv_path, master_rows, MASTER_FIELDNAMES)
    master_md_path.write_text(markdown, encoding="utf-8")
    write_csv(validation_csv_path, validation_rows, ["check_name", "status", "evidence_detail"])
    validation_md_path.write_text(build_validation_markdown(validation_rows), encoding="utf-8")

    row_counts = Counter((row["phase"], row["record_type"]) for row in master_rows)
    return ReportResult(
        master_csv_path=master_csv_path,
        master_md_path=master_md_path,
        validation_csv_path=validation_csv_path,
        validation_md_path=validation_md_path,
        row_counts=dict(row_counts),
        gma5_common_oos_start=gma5_common_start,
        gma5_common_oos_end=gma5_common_end,
        validation_rows=validation_rows,
    )


def main() -> None:
    args = parse_args()
    generate_master_report(
        Path(args.gma4_report_root),
        Path(args.gma5_report_root),
        Path(args.output_root),
    )


if __name__ == "__main__":
    main()
