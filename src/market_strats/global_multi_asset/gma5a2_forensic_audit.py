from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


RUN_ID = "gma5_20260622T075912Z"
VARIANT_IDS = [
    "gma5_equal_weight_atomic_sleeves_v1",
    "gma5_risk_weighted_atomic_sleeves_v1",
    "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
]
RIDGE_VARIANT_ID = "gma5_fixed_alpha_ridge_atomic_ensemble_v1"
GFC_END_DATE = "2009-03-09"
AUDIT_VERSION = "v1"

TIMELINE_FIELDS = [
    "variant_id",
    "first_common_ensemble_oos_date",
    "first_saved_weight_date",
    "first_saved_feature_date",
    "first_saved_training_audit_date",
    "first_model_fit_date",
    "first_model_prediction_date",
    "first_true_learned_ridge_decision_date",
    "pre_model_policy",
    "gfc_coverage_status",
    "gfc_unavailability_reason",
]

REPLAY_FIELDS = [
    "check_name",
    "status",
    "evidence_class",
    "evidence_source",
    "evidence_detail",
]

VERDICT_FIELDS = [
    "gate_name",
    "prior_status",
    "new_status",
    "evidence_class",
    "evidence_source",
    "evidence_detail",
    "required_next_action",
]


class GMA5A2AuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuditPaths:
    root_dir: Path
    run_dir: Path
    scoreboard: Path
    weights: Path
    etf_targets: Path
    features: Path
    training_audit: Path
    manifest: Path
    rejections: Path
    prior_audit: Path
    gma5_source: Path
    replay_source: Path


@dataclass(frozen=True)
class AuditResult:
    timeline_rows: list[dict[str, str]]
    replay_rows: list[dict[str, str]]
    verdict_rows: list[dict[str, str]]
    ridge_headline_classification: str
    timeline_csv_path: Path
    replay_csv_path: Path
    verdict_csv_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gma5-report-root",
        default="reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1",
    )
    parser.add_argument(
        "--gma5-source",
        default="src/market_strats/global_multi_asset/gma5_atomic_sleeve_ensemble.py",
    )
    parser.add_argument(
        "--replay-source",
        default="src/market_strats/global_multi_asset/gma4_replay_adapter.py",
    )
    return parser.parse_args()


def resolve_paths(gma5_report_root: Path, gma5_source: Path, replay_source: Path) -> AuditPaths:
    run_dir = gma5_report_root / "runs" / RUN_ID
    return AuditPaths(
        root_dir=gma5_report_root,
        run_dir=run_dir,
        scoreboard=run_dir / "gma5_ensemble_scoreboard.csv",
        weights=run_dir / "gma5_ensemble_monthly_sleeve_weights.csv",
        etf_targets=run_dir / "gma5_ensemble_monthly_etf_targets.csv",
        features=run_dir / "gma5_ensemble_monthly_features.csv",
        training_audit=run_dir / "gma5_ensemble_training_audit.csv",
        manifest=run_dir / "gma5_ensemble_manifest.json",
        rejections=run_dir / "gma5_ensemble_rejections.csv",
        prior_audit=gma5_report_root / "gma5_latest_implementation_audit_v1.csv",
        gma5_source=gma5_source,
        replay_source=replay_source,
    )


def read_csv_required(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise GMA5A2AuditError(f"missing required saved artifact: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise GMA5A2AuditError(f"malformed CSV with no header: {path}")
        missing = sorted(required_columns - set(reader.fieldnames))
        if missing:
            raise GMA5A2AuditError(f"missing columns in {path.name}: {missing}")
        return list(reader)


def read_json_required(path: Path) -> dict[str, object]:
    if not path.exists():
        raise GMA5A2AuditError(f"missing required saved artifact: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def min_nonempty(values: list[str]) -> str:
    clean = sorted(value for value in values if value)
    return clean[0] if clean else "insufficient_saved_evidence"


def first_common_oos_date(scoreboard: list[dict[str, str]]) -> str:
    dates = {
        row["start_date"]
        for row in scoreboard
        if row["evaluation_scope"] == "full_common_oos"
        and row["cost_scenario"] == "baseline_1bps"
        and row["entity_type"] == "ensemble_variant"
        and row["status"] == "evaluated"
    }
    if len(dates) != 1:
        raise GMA5A2AuditError("saved scoreboard does not contain one common OOS start date")
    return next(iter(dates))


def first_true_learned_ridge_date(training_rows: list[dict[str, str]]) -> str:
    candidates = []
    for row in training_rows:
        try:
            row_count = int(float(row["training_row_count"]))
        except ValueError:
            continue
        if row_count >= 60 and row.get("prediction", ""):
            candidates.append(row["decision_date"])
    return min_nonempty(candidates)


def classify_pre_model_policy(
    weights: list[dict[str, str]],
    common_oos_start: str,
    learned_date: str,
) -> str:
    if learned_date == "insufficient_saved_evidence":
        return "insufficient_saved_evidence"
    pre_model_rows = [
        row
        for row in weights
        if row["variant_id"] == RIDGE_VARIANT_ID
        and common_oos_start <= row["decision_date"] < learned_date
    ]
    if not pre_model_rows:
        return "not_applicable"
    weights_by_date: dict[str, list[float]] = defaultdict(list)
    statuses = set()
    for row in pre_model_rows:
        weights_by_date[row["decision_date"]].append(float(row["sleeve_allocation_weight"]))
        statuses.add(row["status"])
    if all(math.isclose(sum(values), 0.0, abs_tol=1e-10) for values in weights_by_date.values()):
        return "no_allocation_before_training"
    if statuses == {"fallback_equal_weight"}:
        return "fallback_equal_weight"
    if statuses == {"fallback_risk_weighted"}:
        return "fallback_risk_weighted"
    if statuses == {"fallback_bil"}:
        return "fallback_bil"
    if any(status.startswith("fallback_") for status in statuses):
        return "other_documented_fallback"
    return "insufficient_saved_evidence"


def build_timeline_rows(
    scoreboard: list[dict[str, str]],
    weights: list[dict[str, str]],
    features: list[dict[str, str]],
    training_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], str]:
    common_oos_start = first_common_oos_date(scoreboard)
    first_feature = min_nonempty([row["decision_date"] for row in features])
    first_training = min_nonempty([row["decision_date"] for row in training_rows])
    learned_ridge_date = first_true_learned_ridge_date(training_rows)
    ridge_prediction_date = learned_ridge_date
    pre_model_policy = classify_pre_model_policy(weights, common_oos_start, learned_ridge_date)

    rows = []
    for variant_id in VARIANT_IDS:
        first_weight = min_nonempty(
            [row["decision_date"] for row in weights if row["variant_id"] == variant_id]
        )
        is_ridge = variant_id == RIDGE_VARIANT_ID
        rows.append(
            {
                "variant_id": variant_id,
                "first_common_ensemble_oos_date": common_oos_start,
                "first_saved_weight_date": first_weight,
                "first_saved_feature_date": first_feature,
                "first_saved_training_audit_date": first_training if is_ridge else "not_applicable",
                "first_model_fit_date": "insufficient_saved_evidence"
                if is_ridge
                else "not_applicable",
                "first_model_prediction_date": ridge_prediction_date
                if is_ridge
                else "not_applicable",
                "first_true_learned_ridge_decision_date": learned_ridge_date
                if is_ridge
                else "not_applicable",
                "pre_model_policy": pre_model_policy if is_ridge else "not_applicable",
                "gfc_coverage_status": "unavailable_before_common_oos_start",
                "gfc_unavailability_reason": (
                    f"common_oos_start={common_oos_start} is after gfc_end={GFC_END_DATE}"
                ),
            }
        )
    return rows, pre_model_policy


def target_sums_to_one(target_rows: list[dict[str, str]]) -> bool:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for row in target_rows:
        totals[(row["variant_id"], row["decision_date"])] += float(
            row["composite_etf_target_weight"]
        )
    return bool(totals) and all(math.isclose(value, 1.0, abs_tol=1e-8) for value in totals.values())


def residual_bil_observed(target_rows: list[dict[str, str]]) -> bool:
    return any(
        row["symbol"] == "BIL" and float(row["composite_etf_target_weight"]) > 0.0
        for row in target_rows
    )


def target_rows_are_unique(target_rows: list[dict[str, str]]) -> bool:
    keys = [(row["variant_id"], row["decision_date"], row["symbol"]) for row in target_rows]
    return len(keys) == len(set(keys))


def current_source_has_composite_path(gma5_source: str, replay_source: str) -> bool:
    combined = gma5_source + "\n" + replay_source
    return "target_resolver" in combined and "_simulate_strategy" in combined


def current_source_has_no_averaging_path(gma5_source: str, replay_source: str) -> bool:
    combined = (gma5_source + "\n" + replay_source).lower()
    return "target_resolver" in combined and "average equity" not in combined


def replay_row(
    check_name: str,
    status: str,
    evidence_source: str,
    evidence_detail: str,
) -> dict[str, str]:
    evidence_class = (
        "saved_run_artifact"
        if status == "historically_evidenced"
        else "current_source_only"
        if status == "current_source_evidenced_only"
        else "insufficient_saved_evidence"
        if status == "insufficient_saved_evidence"
        else "failed_validation"
    )
    return {
        "check_name": check_name,
        "status": status,
        "evidence_class": evidence_class,
        "evidence_source": evidence_source,
        "evidence_detail": evidence_detail,
    }


def build_replay_rows(paths: AuditPaths, target_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    gma5_source = (
        paths.gma5_source.read_text(encoding="utf-8") if paths.gma5_source.exists() else ""
    )
    replay_source = (
        paths.replay_source.read_text(encoding="utf-8") if paths.replay_source.exists() else ""
    )
    manifest = read_json_required(paths.manifest)
    manifest_has_replay_hash = any("replay" in key and "hash" in key for key in manifest)
    manifest_has_no_averaging_proof = any("averaging" in key and "hash" in key for key in manifest)
    replay_ledger = paths.run_dir / "gma5_ensemble_composite_replay_ledger.csv"

    rows = [
        replay_row(
            "saved_monthly_etf_targets_exist",
            "historically_evidenced" if paths.etf_targets.exists() and target_rows else "fail",
            paths.etf_targets.name,
            f"saved rows={len(target_rows)}",
        ),
        replay_row(
            "monthly_etf_targets_sum_to_one",
            "historically_evidenced" if target_sums_to_one(target_rows) else "fail",
            paths.etf_targets.name,
            "variant/date composite ETF target weights sum to one",
        ),
        replay_row(
            "residual_bil_allocation_observed",
            "historically_evidenced" if residual_bil_observed(target_rows) else "fail",
            paths.etf_targets.name,
            "BIL rows with positive composite target weight observed",
        ),
        replay_row(
            "overlapping_etf_target_netting_observed",
            "historically_evidenced" if target_rows_are_unique(target_rows) else "fail",
            paths.etf_targets.name,
            "one target row per variant/date/symbol in saved composite target artifact",
        ),
        replay_row(
            "saved_composite_replay_ledger_exists",
            "historically_evidenced" if replay_ledger.exists() else "insufficient_saved_evidence",
            replay_ledger.name,
            "no saved composite replay ledger found"
            if not replay_ledger.exists()
            else "ledger found",
        ),
        replay_row(
            "historical_run_replay_adapter_hash_exists",
            "historically_evidenced" if manifest_has_replay_hash else "insufficient_saved_evidence",
            paths.manifest.name,
            "manifest lacks run-linked replay adapter source hash"
            if not manifest_has_replay_hash
            else "manifest contains replay hash",
        ),
        replay_row(
            "historical_run_no_equity_curve_averaging_proof_exists",
            "historically_evidenced"
            if manifest_has_no_averaging_proof
            else "insufficient_saved_evidence",
            paths.manifest.name,
            "manifest lacks run-linked no-equity-curve-averaging proof"
            if not manifest_has_no_averaging_proof
            else "manifest contains no-averaging proof",
        ),
        replay_row(
            "current_source_composite_target_replay_path_exists",
            "current_source_evidenced_only"
            if current_source_has_composite_path(gma5_source, replay_source)
            else "insufficient_saved_evidence",
            "static source inspection",
            "current source shows target-resolver replay path but does not bind it to the saved run",
        ),
        replay_row(
            "current_source_no_equity_curve_averaging_path_exists",
            "current_source_evidenced_only"
            if current_source_has_no_averaging_path(gma5_source, replay_source)
            else "insufficient_saved_evidence",
            "static source inspection",
            "current source suggests target-level replay; saved run lacks immutable no-averaging proof",
        ),
    ]
    return rows


def prior_statuses(prior_audit_path: Path) -> dict[str, str]:
    if not prior_audit_path.exists():
        return {}
    rows = read_csv_required(prior_audit_path, {"check_name", "status"})
    return {row["check_name"]: row["status"] for row in rows}


def ridge_headline_classification(timeline_rows: list[dict[str, str]]) -> str:
    ridge = next(row for row in timeline_rows if row["variant_id"] == RIDGE_VARIANT_ID)
    if ridge["first_true_learned_ridge_decision_date"] == "insufficient_saved_evidence":
        return "insufficient_saved_evidence"
    if ridge["first_true_learned_ridge_decision_date"] == ridge["first_common_ensemble_oos_date"]:
        return "fully_learned_from_first_reported_oos_date"
    return "includes_pre_model_fallback_period"


def build_verdict_rows(
    timeline_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    prior: dict[str, str],
) -> list[dict[str, str]]:
    ridge = next(row for row in timeline_rows if row["variant_id"] == RIDGE_VARIANT_ID)
    replay_by_name = {row["check_name"]: row for row in replay_rows}
    classification = ridge_headline_classification(timeline_rows)
    return [
        {
            "gate_name": "first_ridge_oos_date_matches_training_rule",
            "prior_status": prior.get("first_ridge_oos_date_matches_training_rule", "unknown"),
            "new_status": "resolved"
            if classification != "insufficient_saved_evidence"
            else "still_blocked",
            "evidence_class": "saved_run_artifact",
            "evidence_source": "gma5_ensemble_training_audit.csv",
            "evidence_detail": (
                f"common_oos_start={ridge['first_common_ensemble_oos_date']}; "
                f"first_true_learned_ridge_decision_date="
                f"{ridge['first_true_learned_ridge_decision_date']}; "
                f"headline_classification={classification}; "
                f"pre_model_policy={ridge['pre_model_policy']}"
            ),
            "required_next_action": (
                "future learned-only ridge comparison must begin at the first true learned "
                "decision date"
            ),
        },
        {
            "gate_name": "composite_replay_adapter_path_evidenced",
            "prior_status": prior.get("composite_replay_adapter_path_evidenced", "unknown"),
            "new_status": "still_blocked"
            if replay_by_name["historical_run_replay_adapter_hash_exists"]["status"]
            != "historically_evidenced"
            else "resolved",
            "evidence_class": "insufficient_saved_evidence",
            "evidence_source": "gma5_ensemble_manifest.json",
            "evidence_detail": "saved run lacks replay adapter source hash or replay ledger",
            "required_next_action": (
                "capture run-linked code hash and composite replay ledger in any exact "
                "reproducibility rerun"
            ),
        },
        {
            "gate_name": "no_sleeve_equity_curve_averaging_evidenced",
            "prior_status": prior.get("no_sleeve_equity_curve_averaging_evidenced", "unknown"),
            "new_status": "still_blocked"
            if replay_by_name["historical_run_no_equity_curve_averaging_proof_exists"]["status"]
            != "historically_evidenced"
            else "resolved",
            "evidence_class": "insufficient_saved_evidence",
            "evidence_source": "gma5_ensemble_manifest.json",
            "evidence_detail": "saved run lacks direct no-equity-curve-averaging proof",
            "required_next_action": (
                "capture explicit no-NAV-averaging provenance in any exact reproducibility rerun"
            ),
        },
    ]


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    output = ["| " + " | ".join(headers) + " |"]
    output.append("| " + " | ".join("---" for _ in headers) + " |")
    output.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(output)


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def timeline_markdown(rows: list[dict[str, str]], classification: str) -> str:
    return "\n".join(
        [
            "# GMA-5A.2 Timeline Forensic Audit",
            "",
            f"Ridge headline classification: `{classification}`.",
            "",
            markdown_table(
                TIMELINE_FIELDS, [[row[field] for field in TIMELINE_FIELDS] for row in rows]
            ),
            "",
            "GFC is unavailable for all three variants because the common GMA-5 OOS start is after the GFC window, not because of ridge minimum-training history.",
            "",
        ]
    )


def replay_markdown(rows: list[dict[str, str]]) -> str:
    return "\n".join(
        [
            "# GMA-5A.2 Replay Provenance Audit",
            "",
            markdown_table(
                REPLAY_FIELDS, [[row[field] for field in REPLAY_FIELDS] for row in rows]
            ),
            "",
            "Current source inspection is not historical saved-run proof.",
            "",
        ]
    )


def verdict_markdown(rows: list[dict[str, str]]) -> str:
    return "\n".join(
        [
            "# GMA-5A.2 Evidence Gate Verdict",
            "",
            markdown_table(
                VERDICT_FIELDS, [[row[field] for field in VERDICT_FIELDS] for row in rows]
            ),
            "",
        ]
    )


def copy_latest(run_path: Path, root_dir: Path) -> None:
    shutil.copyfile(run_path, root_dir / run_path.name)


def generate_forensic_audit(
    gma5_report_root: Path,
    gma5_source: Path,
    replay_source: Path,
) -> AuditResult:
    paths = resolve_paths(gma5_report_root, gma5_source, replay_source)
    scoreboard = read_csv_required(
        paths.scoreboard,
        {"entity_id", "entity_type", "cost_scenario", "evaluation_scope", "start_date", "status"},
    )
    weights = read_csv_required(
        paths.weights,
        {"variant_id", "decision_date", "sleeve_allocation_weight", "status"},
    )
    targets = read_csv_required(
        paths.etf_targets,
        {"variant_id", "decision_date", "symbol", "composite_etf_target_weight"},
    )
    features = read_csv_required(paths.features, {"sleeve_id", "decision_date"})
    training_rows = read_csv_required(
        paths.training_audit,
        {"decision_date", "sleeve_id", "training_row_count", "prediction"},
    )

    timeline_rows, _pre_model_policy = build_timeline_rows(
        scoreboard, weights, features, training_rows
    )
    replay_rows = build_replay_rows(paths, targets)
    verdict_rows = build_verdict_rows(timeline_rows, replay_rows, prior_statuses(paths.prior_audit))
    classification = ridge_headline_classification(timeline_rows)

    timeline_csv = paths.run_dir / "gma5a2_timeline_forensic_audit_v1.csv"
    replay_csv = paths.run_dir / "gma5a2_replay_provenance_audit_v1.csv"
    verdict_csv = paths.run_dir / "gma5a2_evidence_gate_verdict_v1.csv"
    timeline_md = paths.run_dir / "gma5a2_timeline_forensic_audit_v1.md"
    replay_md = paths.run_dir / "gma5a2_replay_provenance_audit_v1.md"
    verdict_md = paths.run_dir / "gma5a2_evidence_gate_verdict_v1.md"

    write_csv(timeline_csv, timeline_rows, TIMELINE_FIELDS)
    write_csv(replay_csv, replay_rows, REPLAY_FIELDS)
    write_csv(verdict_csv, verdict_rows, VERDICT_FIELDS)
    write_text(timeline_md, timeline_markdown(timeline_rows, classification))
    write_text(replay_md, replay_markdown(replay_rows))
    write_text(verdict_md, verdict_markdown(verdict_rows))
    for path in [timeline_csv, replay_csv, verdict_csv, timeline_md, replay_md, verdict_md]:
        copy_latest(path, paths.root_dir)

    return AuditResult(
        timeline_rows=timeline_rows,
        replay_rows=replay_rows,
        verdict_rows=verdict_rows,
        ridge_headline_classification=classification,
        timeline_csv_path=timeline_csv,
        replay_csv_path=replay_csv,
        verdict_csv_path=verdict_csv,
    )


def main() -> None:
    args = parse_args()
    generate_forensic_audit(
        Path(args.gma5_report_root),
        Path(args.gma5_source),
        Path(args.replay_source),
    )


if __name__ == "__main__":
    main()
