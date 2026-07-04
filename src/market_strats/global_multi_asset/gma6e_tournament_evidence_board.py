"""GMA-6E comparability-aware evidence board for the frozen GMA-6D run.

This module reads saved GMA-6D outputs only. It does not fetch data, run
strategies, replay portfolios, fit models, or create operational decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_ROOT = Path("reports/global_multi_asset_alpha/gma6_cross_universe_tournament_v1")
COMPLETED_RUN_ID = "gma6d_20260624T061822Z"
CONTROL_UNIVERSE_VERSION = "gma6_core_22_control_v1"
EXPANDED_UNIVERSE_VERSION = "gma6_expanded_29_v1"
CONTROL_FLAG = "not_applicable_no_uso"
EXPANDED_USO_FLAG = "uso_roll_methodology_pre_may_2020_vs_from_may_2020"
REQUIRED_COST_SCENARIOS = ["baseline_1bps", "stressed_10bps", "stressed_25bps", "severe_50bps"]
VALID_SAMPLE_STATUSES = {
    "identical_effective_sample",
    "not_comparable_due_to_effective_start",
    "not_comparable_due_to_missing_measurement",
}
PRIMARY_METRICS = [
    "net_cagr",
    "annualised_volatility",
    "sharpe",
    "maximum_drawdown",
    "annualised_turnover",
    "cost_drag",
    "maximum_hhi",
]
LOWER_IS_BETTER = {"annualised_volatility", "annualised_turnover", "cost_drag", "maximum_hhi"}
HIGHER_IS_BETTER = {"net_cagr", "sharpe", "maximum_drawdown"}
REQUIRED_RUN_FILES = [
    "gma6d_run_manifest_v1.json",
    "gma6d_input_verification_v1.csv",
    "gma6d_input_verification_v1.md",
    "gma6d_tournament_scoreboard_v1.csv",
    "gma6d_tournament_scoreboard_v1.md",
    "gma6d_evaluation_detail_v1.csv",
    "gma6d_cross_universe_comparison_v1.csv",
    "gma6d_cross_universe_comparison_v1.md",
    "gma6d_sample_comparability_audit_v1.csv",
    "gma6d_sample_comparability_audit_v1.md",
    "gma6d_monthly_target_weights_v1.csv",
    "gma6d_uso_methodology_regime_detail_v1.csv",
    "gma6d_execution_provenance_v1.json",
    "gma6d_results_discussion_v1.md",
]
ROOT_LATEST_FILES = [
    "gma6d_run_manifest_v1.json",
    "gma6d_tournament_scoreboard_v1.csv",
    "gma6d_evaluation_detail_v1.csv",
    "gma6d_cross_universe_comparison_v1.csv",
    "gma6d_sample_comparability_audit_v1.csv",
    "gma6d_uso_methodology_regime_detail_v1.csv",
    "gma6d_execution_provenance_v1.json",
]
OUTPUT_FILES = [
    "gma6e_attempt_registry_v1.csv",
    "gma6e_attempt_registry_v1.md",
    "gma6e_completed_run_integrity_audit_v1.csv",
    "gma6e_completed_run_integrity_audit_v1.md",
    "gma6e_comparability_aware_evidence_board_v1.csv",
    "gma6e_comparability_aware_evidence_board_v1.md",
]
REQUIRED_WORDING = [
    "This is observed development evidence and not a pristine final holdout.",
    "No execution or promotion decision is produced.",
    "Highest historical CAGR or Sharpe alone is not a selection rule.",
    "The primary comparison is core-22 versus expanded-29 within the frozen GMA-6D run.",
    "Non-comparable effective samples are excluded from primary aggregates.",
    "USO and DBA are historical traded ETP return exposures, not spot commodity return series.",
]
FORBIDDEN_LANGUAGE = ["candidate", "winner", "approved", "recommended", "deployable", "live-ready"]
GMA4_LIMIT = "not_directly_numeric_comparable_to_prior_gma4_run_without_identical_data_snapshot"
INTERPRETATION_LIMIT = "descriptive core-versus-expanded evidence only; no universe classification or execution decision"


class GMA6EIntegrityError(ValueError):
    """Fail-closed GMA-6E integrity error."""


@dataclass(frozen=True)
class GMA6EResult:
    output_root: Path
    attempt_registry: pd.DataFrame
    integrity_audit: pd.DataFrame
    evidence_board: pd.DataFrame
    detail_board: pd.DataFrame
    family_summary: pd.DataFrame
    uso_detail: pd.DataFrame


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA6EIntegrityError(f"{path} must contain a JSON object")
    return raw


def _read_csv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        raise GMA6EIntegrityError(f"required CSV is missing or empty: {path}")
    frame = pd.read_csv(path)
    missing = required_columns - set(frame.columns)
    if missing:
        raise GMA6EIntegrityError(f"{path} missing columns: {sorted(missing)}")
    if frame.empty:
        raise GMA6EIntegrityError(f"required CSV has no rows: {path}")
    return frame


def _format_value(value: Any) -> str:
    if isinstance(value, list | tuple | dict | set):
        return json.dumps(value, sort_keys=True, default=str)
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(_format_value(item) for item in row) + " |" for row in rows),
    ]


def _write_markdown(path: Path, title: str, lines: list[str]) -> None:
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def build_attempt_registry(
    root: Path = DEFAULT_ROOT, completed_run_id: str = COMPLETED_RUN_ID
) -> pd.DataFrame:
    runs_root = root / "runs"
    rows: list[dict[str, Any]] = []
    for run_dir in sorted(runs_root.glob("gma6d_*")):
        if not run_dir.is_dir():
            continue
        manifest = run_dir / "gma6d_run_manifest_v1.json"
        scoreboard = run_dir / "gma6d_tournament_scoreboard_v1.csv"
        required_present = all(
            (run_dir / name).exists() and (run_dir / name).stat().st_size > 0
            for name in REQUIRED_RUN_FILES
        )
        scoreboard_nonempty = False
        if scoreboard.exists() and scoreboard.stat().st_size > 0:
            try:
                scoreboard_nonempty = not pd.read_csv(scoreboard, nrows=1).empty
            except (pd.errors.ParserError, UnicodeDecodeError, OSError):
                scoreboard_nonempty = False
        if run_dir.name == completed_run_id and required_present and scoreboard_nonempty:
            status = "completed_verified_run"
            eligible = True
            evidence = "all_required_artifacts_present_and_nonempty"
            notes = "completed GMA-6D run used as sole numerical source"
        elif run_dir.name != completed_run_id:
            status = "aborted_or_incomplete_attempt"
            eligible = False
            evidence = "not_the_verified_completed_run"
            notes = "timeout or superseded attempt retained for provenance; not cleaned up"
        else:
            status = "unclear_requires_manual_review"
            eligible = False
            evidence = "partial_completion_artifacts"
            notes = "completed run identifier lacks required completion evidence"
        rows.append(
            {
                "run_directory": str(run_dir),
                "run_id": run_dir.name,
                "attempt_status": status,
                "manifest_present": manifest.exists(),
                "scoreboard_present": scoreboard.exists(),
                "scoreboard_nonempty": scoreboard_nonempty,
                "completion_evidence": evidence,
                "eligible_for_latest_reference": eligible,
                "notes": notes,
            }
        )
    return pd.DataFrame(rows)


def _audit_row(
    check_name: str, passed: bool, expected: Any, observed: Any, notes: str = ""
) -> dict[str, Any]:
    return {
        "check_name": check_name,
        "audit_status": "pass" if passed else "fail",
        "expected": expected,
        "observed": observed,
        "notes": notes,
    }


def build_integrity_audit(
    *,
    root: Path = DEFAULT_ROOT,
    completed_run_id: str = COMPLETED_RUN_ID,
    lock_path: Path | None = None,
) -> pd.DataFrame:
    run_dir = root / "runs" / completed_run_id
    rows: list[dict[str, Any]] = []
    for filename in REQUIRED_RUN_FILES:
        path = run_dir / filename
        rows.append(
            _audit_row(
                f"completed_run_file_present:{filename}",
                path.exists() and path.stat().st_size > 0,
                "present_and_nonempty",
                "present_and_nonempty"
                if path.exists() and path.stat().st_size > 0
                else "missing_or_empty",
            )
        )
    for filename in ROOT_LATEST_FILES:
        run_file = run_dir / filename
        root_file = root / filename
        passed = (
            run_file.exists()
            and root_file.exists()
            and _sha256_file(run_file) == _sha256_file(root_file)
        )
        rows.append(
            _audit_row(
                f"root_latest_hash_matches_completed:{filename}",
                passed,
                _sha256_file(run_file) if run_file.exists() else "missing_completed_file",
                _sha256_file(root_file) if root_file.exists() else "missing_root_file",
            )
        )
    manifest = _load_json(run_dir / "gma6d_run_manifest_v1.json")
    lock_file = lock_path or Path(
        "reports/global_multi_asset_alpha/gma6c_cross_universe_tournament_lock_v1.json"
    )
    lock = _load_json(lock_file)
    lock_fields = [
        "gma6b_data_bundle_manifest_hash",
        "control_universe_hash",
        "expanded_universe_hash",
        "trial_inventory_hash",
        "cost_scenario_hash",
        "methodology_regime_rules_hash",
    ]
    for field in lock_fields:
        rows.append(
            _audit_row(
                f"manifest_lock_hash:{field}",
                manifest.get(field) == lock.get(field),
                lock.get(field),
                manifest.get(field),
            )
        )
    rows.append(
        _audit_row(
            "manifest_lock_file_hash",
            manifest.get("gma6c_lock_hash") == _sha256_file(lock_file),
            _sha256_file(lock_file),
            manifest.get("gma6c_lock_hash"),
        )
    )

    scoreboard = _read_csv(
        run_dir / "gma6d_tournament_scoreboard_v1.csv",
        {
            "universe_version",
            "trial_id",
            "cost_scenario",
            "methodology_regime_flag",
            "evaluation_scope",
        },
    )
    comparison = _read_csv(
        run_dir / "gma6d_cross_universe_comparison_v1.csv",
        {
            "sample_comparability_status",
            "metric_name",
            "trial_id",
            "cost_scenario",
            "evaluation_scope",
        },
    )
    sample_audit = _read_csv(
        run_dir / "gma6d_sample_comparability_audit_v1.csv",
        {
            "sample_comparability_status",
            "trial_id",
            "cost_scenario",
            "evaluation_scope",
            "window_id",
        },
    )
    detail = _read_csv(
        run_dir / "gma6d_evaluation_detail_v1.csv",
        {"universe_version", "source_gma4_trial_id", "cost_scenario"},
    )
    expected_arms = {CONTROL_UNIVERSE_VERSION, EXPANDED_UNIVERSE_VERSION}
    rows.append(
        _audit_row(
            "scoreboard_contains_two_expected_arms",
            set(scoreboard["universe_version"]) == expected_arms,
            sorted(expected_arms),
            sorted(scoreboard["universe_version"].unique()),
        )
    )
    trial_counts = scoreboard.groupby("universe_version")["trial_id"].nunique().to_dict()
    rows.append(
        _audit_row(
            "scoreboard_twenty_trials_per_arm",
            trial_counts == {CONTROL_UNIVERSE_VERSION: 20, EXPANDED_UNIVERSE_VERSION: 20},
            "20 per arm",
            trial_counts,
        )
    )
    rows.append(
        _audit_row(
            "scoreboard_four_frozen_cost_scenarios",
            sorted(scoreboard["cost_scenario"].unique()) == sorted(REQUIRED_COST_SCENARIOS),
            sorted(REQUIRED_COST_SCENARIOS),
            sorted(scoreboard["cost_scenario"].unique()),
        )
    )
    rows.append(
        _audit_row(
            "detail_four_frozen_cost_scenarios",
            sorted(detail["cost_scenario"].unique()) == sorted(REQUIRED_COST_SCENARIOS),
            sorted(REQUIRED_COST_SCENARIOS),
            sorted(detail["cost_scenario"].unique()),
        )
    )
    rows.append(
        _audit_row(
            "no_27_instrument_result",
            not scoreboard["universe_version"].astype(str).str.contains("27").any(),
            "no universe_version contains 27",
            sorted(scoreboard["universe_version"].unique()),
        )
    )
    expanded_flags = set(
        scoreboard.loc[
            scoreboard["universe_version"] == EXPANDED_UNIVERSE_VERSION, "methodology_regime_flag"
        ]
    )
    control_flags = set(
        scoreboard.loc[
            scoreboard["universe_version"] == CONTROL_UNIVERSE_VERSION, "methodology_regime_flag"
        ]
    )
    rows.append(
        _audit_row(
            "expanded_outputs_carry_uso_methodology_flag",
            expanded_flags == {EXPANDED_USO_FLAG},
            EXPANDED_USO_FLAG,
            sorted(expanded_flags),
        )
    )
    rows.append(
        _audit_row(
            "control_outputs_use_no_uso_flag",
            control_flags == {CONTROL_FLAG},
            CONTROL_FLAG,
            sorted(control_flags),
        )
    )
    observed_statuses = set(comparison["sample_comparability_status"]) | set(
        sample_audit["sample_comparability_status"]
    )
    rows.append(
        _audit_row(
            "valid_sample_comparability_statuses",
            observed_statuses <= VALID_SAMPLE_STATUSES,
            sorted(VALID_SAMPLE_STATUSES),
            sorted(observed_statuses),
        )
    )
    metric_count = comparison["metric_name"].nunique()
    rows.append(
        _audit_row(
            "comparison_rows_reconcile_to_sample_audit",
            len(comparison) == len(sample_audit) * metric_count,
            f"{len(sample_audit)} * {metric_count}",
            len(comparison),
        )
    )
    rows.append(
        _audit_row(
            "scoreboard_row_count_reconciles",
            len(scoreboard) == 9280 or len(scoreboard) == len(scoreboard.drop_duplicates()),
            "nonduplicated saved rows",
            len(scoreboard),
        )
    )
    discussion = (run_dir / "gma6d_results_discussion_v1.md").read_text(encoding="utf-8").lower()
    equality_claim_absent = "numerical equality" not in discussion and GMA4_LIMIT in discussion
    rows.append(
        _audit_row(
            "no_gma4_numerical_equality_claim",
            equality_claim_absent,
            "explicit non-comparability limit",
            "present" if equality_claim_absent else "missing_or_conflicting",
        )
    )
    return pd.DataFrame(rows)


def _better_counts(group: pd.DataFrame, metric_name: str) -> tuple[int, int, int]:
    diffs = pd.to_numeric(group["expanded_minus_core"], errors="coerce")
    if metric_name in LOWER_IS_BETTER:
        expanded_better = int((diffs < 0).sum())
        core_better = int((diffs > 0).sum())
    elif metric_name in HIGHER_IS_BETTER:
        expanded_better = int((diffs > 0).sum())
        core_better = int((diffs < 0).sum())
    else:
        raise GMA6EIntegrityError(f"unsupported metric direction: {metric_name}")
    tie = int((diffs == 0).sum())
    return expanded_better, core_better, tie


def build_evidence_boards(
    root: Path = DEFAULT_ROOT, completed_run_id: str = COMPLETED_RUN_ID
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    run_dir = root / "runs" / completed_run_id
    comparison = _read_csv(
        run_dir / "gma6d_cross_universe_comparison_v1.csv",
        {
            "trial_id",
            "cost_scenario",
            "evaluation_scope",
            "core_22_metric",
            "expanded_29_metric",
            "difference",
            "metric_name",
            "sample_comparability_status",
            "methodology_regime_flag",
        },
    )
    scoreboard = _read_csv(
        run_dir / "gma6d_tournament_scoreboard_v1.csv", {"trial_id", "trial_family"}
    )
    uso_detail = _read_csv(
        run_dir / "gma6d_uso_methodology_regime_detail_v1.csv",
        {
            "methodology_slice",
            "slice_start",
            "slice_end",
            "methodology_regime_flag",
            "result_row_count",
            "interpretation_limit",
        },
    )
    family_by_trial = (
        scoreboard[["trial_id", "trial_family"]]
        .drop_duplicates()
        .set_index("trial_id")["trial_family"]
    )
    detail = comparison.loc[comparison["metric_name"].isin(PRIMARY_METRICS)].copy()
    detail["trial_family"] = detail["trial_id"].map(family_by_trial)
    if detail["trial_family"].isna().any():
        missing = sorted(detail.loc[detail["trial_family"].isna(), "trial_id"].unique())
        raise GMA6EIntegrityError(f"comparison rows missing trial family: {missing}")
    if set(detail["methodology_regime_flag"]) != {EXPANDED_USO_FLAG}:
        raise GMA6EIntegrityError("comparison rows must carry expanded USO methodology flag")
    detail["core_22_value"] = pd.to_numeric(detail["core_22_metric"], errors="coerce")
    detail["expanded_29_value"] = pd.to_numeric(detail["expanded_29_metric"], errors="coerce")
    detail["expanded_minus_core"] = pd.to_numeric(detail["difference"], errors="coerce")
    detail["included_in_primary_summary"] = (
        detail["sample_comparability_status"] == "identical_effective_sample"
    )
    detail["interpretation_limit"] = INTERPRETATION_LIMIT
    detail = detail[
        [
            "trial_id",
            "trial_family",
            "cost_scenario",
            "evaluation_scope",
            "metric_name",
            "core_22_value",
            "expanded_29_value",
            "expanded_minus_core",
            "sample_comparability_status",
            "included_in_primary_summary",
            "interpretation_limit",
            "methodology_regime_flag",
        ]
    ].sort_values(["trial_family", "trial_id", "cost_scenario", "evaluation_scope", "metric_name"])
    comparable = detail.loc[
        (detail["included_in_primary_summary"]) & (detail["evaluation_scope"] == "full_history")
    ].copy()
    summary_rows: list[dict[str, Any]] = []
    for (family, cost, metric), group in comparable.groupby(
        ["trial_family", "cost_scenario", "metric_name"], dropna=False
    ):
        expanded_better, core_better, tie = _better_counts(group, str(metric))
        diffs = pd.to_numeric(group["expanded_minus_core"], errors="coerce")
        summary_rows.append(
            {
                "family": family,
                "cost_scenario": cost,
                "metric_name": metric,
                "comparable_trial_count": int(group["trial_id"].nunique()),
                "expanded_better_count": expanded_better,
                "core_better_count": core_better,
                "tie_count": tie,
                "median_difference": float(diffs.median()),
                "mean_difference": float(diffs.mean()),
                "minimum_difference": float(diffs.min()),
                "maximum_difference": float(diffs.max()),
            }
        )
    family_summary = pd.DataFrame(summary_rows).sort_values(
        ["family", "cost_scenario", "metric_name"]
    )
    combined_rows: list[dict[str, Any]] = []
    for row in detail.to_dict("records"):
        combined_rows.append({"record_type": "trial_metric", **row})
    for row in family_summary.to_dict("records"):
        combined_rows.append({"record_type": "family_summary", **row})
    evidence_board = pd.DataFrame(combined_rows)
    return evidence_board, detail, family_summary, uso_detail


def _write_outputs(result: GMA6EResult) -> None:
    root = result.output_root
    result.attempt_registry.to_csv(root / "gma6e_attempt_registry_v1.csv", index=False)
    result.integrity_audit.to_csv(root / "gma6e_completed_run_integrity_audit_v1.csv", index=False)
    result.evidence_board.to_csv(
        root / "gma6e_comparability_aware_evidence_board_v1.csv", index=False
    )
    attempt_rows = result.attempt_registry[
        [
            "run_id",
            "attempt_status",
            "manifest_present",
            "scoreboard_nonempty",
            "eligible_for_latest_reference",
        ]
    ].to_dict("records")
    _write_markdown(
        root / "gma6e_attempt_registry_v1.md",
        "GMA-6E Attempt Registry v1",
        [
            *REQUIRED_WORDING,
            "",
            *_markdown_table(
                ["run_id", "status", "manifest", "scoreboard_nonempty", "latest_ref"],
                [
                    [
                        row["run_id"],
                        row["attempt_status"],
                        row["manifest_present"],
                        row["scoreboard_nonempty"],
                        row["eligible_for_latest_reference"],
                    ]
                    for row in attempt_rows
                ],
            ),
        ],
    )
    verdict = "pass" if set(result.integrity_audit["audit_status"]) == {"pass"} else "fail"
    _write_markdown(
        root / "gma6e_completed_run_integrity_audit_v1.md",
        "GMA-6E Completed Run Integrity Audit v1",
        [
            *REQUIRED_WORDING,
            "",
            f"Completed-run integrity verdict: {verdict}",
            "",
            *_markdown_table(
                ["check", "status", "observed"],
                [
                    [row["check_name"], row["audit_status"], row["observed"]]
                    for row in result.integrity_audit.to_dict("records")
                ],
            ),
        ],
    )
    detail = result.detail_board
    comparable_count = int(detail["included_in_primary_summary"].sum())
    non_comparable_count = int((~detail["included_in_primary_summary"]).sum())
    summary = result.family_summary
    primary = summary.loc[
        summary["metric_name"].isin(["net_cagr", "maximum_drawdown", "cost_drag"])
    ].copy()
    uso = result.uso_detail
    expanded_value_summary = _expanded_value_statement(summary)
    lines = [
        *REQUIRED_WORDING,
        "",
        f"Comparable primary trial-metric observations: {comparable_count}",
        f"Non-comparable trial-metric observations excluded from primary aggregates: {non_comparable_count}",
        "",
        expanded_value_summary,
        "",
        "## Full-History Family Evidence Board",
        *_markdown_table(
            [
                "family",
                "cost",
                "metric",
                "trials",
                "expanded_better",
                "core_better",
                "tie",
                "median_diff",
            ],
            [
                [
                    row["family"],
                    row["cost_scenario"],
                    row["metric_name"],
                    row["comparable_trial_count"],
                    row["expanded_better_count"],
                    row["core_better_count"],
                    row["tie_count"],
                    row["median_difference"],
                ]
                for row in primary.to_dict("records")
            ],
        ),
        "",
        "## USO Methodology Slices",
        "These slices are methodology-context observations only and do not establish performance causation or a selection rule.",
        *_markdown_table(
            ["slice", "start", "end", "rows", "flag"],
            [
                [
                    row["methodology_slice"],
                    row["slice_start"],
                    row["slice_end"],
                    row["result_row_count"],
                    row["methodology_regime_flag"],
                ]
                for row in uso.to_dict("records")
            ],
        ),
    ]
    text = "\n".join(lines).lower()
    allowed = "no execution or promotion decision is produced."
    scrubbed = text.replace(allowed, "")
    forbidden_found = [word for word in FORBIDDEN_LANGUAGE if word in scrubbed]
    if forbidden_found:
        raise GMA6EIntegrityError(f"forbidden wording found: {forbidden_found}")
    _write_markdown(
        root / "gma6e_comparability_aware_evidence_board_v1.md",
        "GMA-6E Comparability-Aware Evidence Board v1",
        lines,
    )


def _expanded_value_statement(summary: pd.DataFrame) -> str:
    net = summary.loc[summary["metric_name"] == "net_cagr"]
    if net.empty:
        return "Expanded-universe incremental-value evidence is mixed because no comparable net CAGR rows were available."
    expanded_better = int(net["expanded_better_count"].sum())
    core_better = int(net["core_better_count"].sum())
    if expanded_better > core_better:
        return "Expanded-universe incremental-value evidence is directionally positive on comparable full-history net CAGR, subject to the stated limits."
    if core_better > expanded_better:
        return "Expanded-universe incremental-value evidence is not broad on comparable full-history net CAGR under the frozen GMA-6D trial set."
    return "Expanded-universe incremental-value evidence is mixed on comparable full-history net CAGR under the frozen GMA-6D trial set."


def run_gma6e_evidence_board(
    *,
    root: Path = DEFAULT_ROOT,
    completed_run_id: str = COMPLETED_RUN_ID,
    lock_path: Path | None = None,
) -> GMA6EResult:
    attempt_registry = build_attempt_registry(root, completed_run_id)
    integrity_audit = build_integrity_audit(
        root=root, completed_run_id=completed_run_id, lock_path=lock_path
    )
    if set(integrity_audit["audit_status"]) != {"pass"}:
        failed = integrity_audit.loc[
            integrity_audit["audit_status"] == "fail", "check_name"
        ].tolist()
        raise GMA6EIntegrityError(f"GMA-6E integrity audit failed: {failed}")
    evidence_board, detail_board, family_summary, uso_detail = build_evidence_boards(
        root, completed_run_id
    )
    result = GMA6EResult(
        root,
        attempt_registry,
        integrity_audit,
        evidence_board,
        detail_board,
        family_summary,
        uso_detail,
    )
    _write_outputs(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m market_strats.global_multi_asset.gma6e_tournament_evidence_board"
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--completed-run-id", default=COMPLETED_RUN_ID)
    args = parser.parse_args(argv)
    result = run_gma6e_evidence_board(root=args.root, completed_run_id=args.completed_run_id)
    comparable_count = int(result.detail_board["included_in_primary_summary"].sum())
    non_comparable_count = int((~result.detail_board["included_in_primary_summary"]).sum())
    print(f"completed_run_id: {args.completed_run_id}")
    print("integrity_verdict: pass")
    print(f"comparable_primary_observations: {comparable_count}")
    print(f"non_comparable_primary_observations: {non_comparable_count}")
    print(f"output_root: {result.output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
