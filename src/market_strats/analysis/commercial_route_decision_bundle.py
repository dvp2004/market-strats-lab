from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()

    if clean in {"true", "1", "yes", "y"}:
        return True

    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False

    return bool(value)


def _read_csv_if_exists(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def _gate_row(gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return config.get(key, {}) or {}


def _source_report_check(paths: dict[str, str]) -> pd.DataFrame:
    rows = []

    for report_key, path in paths.items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "report_key": report_key,
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": len(frame),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def _phase_result_check(
    conclusion_path: str,
    gate_path: str,
    phase_name: str,
) -> pd.DataFrame:
    conclusion = _read_csv_if_exists(conclusion_path)
    gate = _read_csv_if_exists(gate_path)

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_passed = (
        not gate.empty
        and "passed" in gate.columns
        and bool(gate["passed"].map(_bool_value).all())
    )

    out = pd.DataFrame(
        [
            {
                "check": f"{phase_name} conclusion passed",
                "passed": conclusion_passed,
                "detail": "conclusion",
            },
            {
                "check": f"{phase_name} gate report passed",
                "passed": gate_passed,
                "detail": "gate_report",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_model_training",
        "allow_model_repair_execution",
        "allow_holdout_prediction_generation",
        "allow_model_selection",
        "allow_feature_importance",
        "allow_signal_creation",
        "allow_allocation_rule_creation",
        "allow_strategy_backtest",
        "allow_visual_backtest_generation",
        "allow_paper_trading_deployment",
        "allow_candidate_promotion",
        "allow_final_candidate_change",
    ]

    rows = []
    for key in keys:
        value = _bool_value(section.get(key, False))
        rows.append({"scope_item": key, "value": value, "passed": not value})

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _best_real_model(success: pd.DataFrame) -> pd.Series | None:
    if success.empty:
        return None

    frame = success[success["is_real_model"].map(_bool_value)].copy()

    if frame.empty:
        return None

    frame["validation_balanced_accuracy"] = pd.to_numeric(
        frame["validation_balanced_accuracy"],
        errors="coerce",
    )
    frame["validation_macro_f1"] = pd.to_numeric(
        frame["validation_macro_f1"],
        errors="coerce",
    )

    frame = frame.sort_values(
        ["validation_balanced_accuracy", "validation_macro_f1"],
        ascending=[False, False],
    )

    return frame.iloc[0]


def _failure_summary(
    decision: pd.DataFrame,
    success: pd.DataFrame,
    overfit: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    best = _best_real_model(success)

    holdout_justified = (
        _bool_value(decision.iloc[0].get("holdout_preregistration_justified", False))
        if not decision.empty
        else False
    )

    if best is None:
        best_model = ""
        best_balanced_accuracy = 0.0
        best_macro_f1 = 0.0
        best_fragile_recall = 0.0
    else:
        best_model = str(best.get("model_id", ""))
        best_balanced_accuracy = float(best.get("validation_balanced_accuracy", 0.0))
        best_macro_f1 = float(best.get("validation_macro_f1", 0.0))
        best_fragile_recall = float(best.get("validation_fragile_recall", 0.0))

    overfit_gap = 0.0
    if not overfit.empty and best_model:
        row = overfit[overfit["model_id"].astype(str).eq(best_model)]
        if not row.empty:
            overfit_gap = float(row.iloc[0].get("balanced_accuracy_gap", 0.0))

    min_fragile = float(thresholds.get("min_fragile_recall_for_live_path", 0.20))
    max_gap = float(thresholds.get("max_overfit_gap_for_live_path", 0.30))
    min_ba = float(thresholds.get("min_validation_balanced_accuracy_for_continued_ml", 0.45))

    return pd.DataFrame(
        [
            {
                "ml_branch": "technical_macro_ml_v1",
                "holdout_preregistration_justified": holdout_justified,
                "diagnostic_leading_model": best_model,
                "best_validation_balanced_accuracy": best_balanced_accuracy,
                "best_validation_macro_f1": best_macro_f1,
                "best_validation_fragile_recall": best_fragile_recall,
                "best_balanced_accuracy_gap": overfit_gap,
                "fragile_recall_live_threshold": min_fragile,
                "max_overfit_gap_threshold": max_gap,
                "min_balanced_accuracy_for_continued_ml": min_ba,
                "fragile_recall_failed": best_fragile_recall < min_fragile,
                "overfit_failed": overfit_gap > max_gap,
                "continued_ml_accuracy_failed": best_balanced_accuracy < min_ba,
                "commercial_failure": (
                    not holdout_justified
                    and best_fragile_recall < min_fragile
                    and overfit_gap > max_gap
                ),
            }
        ]
    )


def _commercial_decision_report(
    failure_summary: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    branch_policy = section.get("branch_policy", {})
    failure = (
        _bool_value(failure_summary.iloc[0].get("commercial_failure", False))
        if not failure_summary.empty
        else True
    )

    if failure:
        status = branch_policy.get(
            "ml_v1_status_if_holdout_not_justified",
            "pause_or_kill_current_technical_macro_ml_v1",
        )
        decision = "pause_current_technical_macro_ml_v1"
        reason = (
            "Technical + macro ML v1 failed validation-to-holdout and should not "
            "receive more minor repair attempts."
        )
    else:
        status = "continue_only_if_holdout_preregistration_was_justified"
        decision = "continue_under_separate_holdout_preregistration"
        reason = "ML branch did not trigger commercial failure criteria."

    return pd.DataFrame(
        [
            {
                "decision": decision,
                "ml_v1_status": status,
                "decision_reason": reason,
                "minor_model_tuning_allowed": bool(
                    branch_policy.get("minor_model_tuning_allowed_after_failure", False)
                ),
                "future_ml_allowed_only_with_new_feature_families": bool(
                    section.get("commercial_thresholds", {}).get(
                        "allow_future_ml_only_with_new_feature_families",
                        True,
                    )
                ),
                "route_selection_required": bool(
                    branch_policy.get("route_selection_required", True)
                ),
                "holdout_predictions_generated": False,
                "model_selected": False,
                "feature_importance_permission": False,
                "signal_permission": False,
                "backtest_permission": False,
                "paper_trading_permission": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def _blocked_next_steps_report(section: dict[str, Any]) -> pd.DataFrame:
    blocked = _as_list(section.get("branch_policy", {}).get("blocked_next_steps"))
    rows = []

    reason_map = {
        "technical_macro_ml_minor_repair": "Blocked because simple redesign and registered model training failed validation gates.",
        "technical_macro_ml_direct_holdout": "Blocked because Phase 13AQ did not justify holdout pre-registration.",
        "technical_macro_ml_signal_mapping": "Blocked because no ML model earned holdout.",
        "technical_macro_ml_backtest": "Blocked because no ML signal exists.",
        "multi_asset_expansion_before_spy_candidate_decision": "Blocked because scope expansion would delay the fastest SPY paper-trading path.",
    }

    for item in blocked:
        step = str(item)
        rows.append(
            {
                "blocked_next_step": step,
                "blocked": True,
                "reason": reason_map.get(step, "Blocked by commercial decision policy."),
            }
        )

    return pd.DataFrame(rows)


def _phase13aw_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    boundary = section.get("phase13aw_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": "phase13aw_boundary_is_route_selection_only",
            "passed": "route selection" in allowed,
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": "phase13aw_boundary_blocks_forbidden_actions",
            "passed": bool(
                "model training" in forbidden
                and "holdout prediction" in forbidden
                and "strategy backtest" in forbidden
                and "paper-trading deployment" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def save_phase13av_ml_branch_commercial_decision(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13av_ml_branch_commercial_decision")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    source_check = _source_report_check(source_reports)
    phase13aq_check = _phase_result_check(
        source_reports["phase13aq_conclusion"],
        source_reports["phase13aq_gate_report"],
        "Phase 13AQ",
    )

    aq_decision = _read_csv_if_exists(source_reports["phase13aq_decision_report"])
    success = _read_csv_if_exists(source_reports["phase13ao_success_report"])
    overfit = _read_csv_if_exists(source_reports["phase13ao_overfit_report"])

    failure = _failure_summary(
        aq_decision,
        success,
        overfit,
        section.get("commercial_thresholds", {}),
    )
    commercial = _commercial_decision_report(failure, section)
    blocked = _blocked_next_steps_report(section)
    boundary = _phase13aw_boundary_check(section)
    scope = _scope_check(section)

    holdout_not_justified = (
        not _bool_value(aq_decision.iloc[0].get("holdout_preregistration_justified", True))
        if not aq_decision.empty
        else True
    )

    summary = pd.DataFrame(
        [
            {
                "decision_role": section.get("decision_role", ""),
                "implementation_classification": section.get(
                    "implementation_classification",
                    "",
                ),
                "phase13aq_passed": bool(phase13aq_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all())
                if not source_check.empty
                else False,
                "holdout_not_justified": holdout_not_justified,
                "commercial_failure": bool(failure.iloc[0]["commercial_failure"]),
                "commercial_decision": commercial.iloc[0]["decision"],
                "blocked_next_steps": len(blocked),
                "phase13aw_boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "visual_backtest_generation": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AQ passed",
                bool(summary.iloc[0]["phase13aq_passed"]),
                "phase13aq",
            ),
            _gate_row(
                "Holdout was not justified",
                holdout_not_justified,
                "holdout_preregistration_justified=False",
            ),
            _gate_row(
                "Failure summary report exists",
                len(failure) == 1,
                "failure summary",
            ),
            _gate_row(
                "Commercial decision report exists",
                len(commercial) == 1,
                str(commercial.iloc[0]["decision"]),
            ),
            _gate_row(
                "Blocked next steps report exists",
                len(blocked) > 0,
                f"rows={len(blocked)}",
            ),
            _gate_row(
                "Phase 13AW boundary is route-selection only",
                bool(boundary["passed"].all()),
                "phase13aw",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Decision role is correct",
                section.get("decision_role")
                == "ML branch commercial kill-or-pivot decision only",
                section.get("decision_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AV",
                "diagnostic": "ML branch commercial kill-or-pivot decision",
                "verdict": (
                    "Completed — ML branch commercial decision passed"
                    if bool(gate_report["passed"].all())
                    else "Failed ML branch commercial decision"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13aq_result_check": phase13aq_check,
        "failure_summary_report": failure,
        "commercial_decision_report": commercial,
        "blocked_next_steps_report": blocked,
        "phase13aw_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13av_commercial_decision_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AV commercial decision reports.")
    return outputs


def _normalise_route_registry(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)

    for col in frame.columns:
        frame[col] = frame[col].apply(
            lambda value: "; ".join(map(str, value))
            if isinstance(value, list)
            else value
        )

    return frame


def _route_selection_report(
    routes: pd.DataFrame,
    policy: dict[str, Any],
    commercial_decision: pd.DataFrame,
) -> pd.DataFrame:
    selected_id = str(policy.get("selected_route_id", ""))
    backup_id = str(policy.get("backup_route_id", ""))
    deferred_id = str(policy.get("deferred_route_id", ""))

    selected = routes[routes["route_id"].astype(str).eq(selected_id)]
    if selected.empty:
        return pd.DataFrame(
            [
                {
                    "selected_route_id": "",
                    "selected": False,
                    "selection_reason": "Configured selected route was not present.",
                    "backup_route_id": backup_id,
                    "deferred_route_id": deferred_id,
                    "next_phase": "",
                    "model_training_permission": False,
                    "holdout_prediction_permission": False,
                    "feature_importance_permission": False,
                    "signal_creation_permission": False,
                    "backtest_generation_permission": False,
                    "paper_trading_permission": False,
                    "candidate_promotion": False,
                }
            ]
        )

    selected_row = selected.iloc[0]
    status = str(selected_row.get("route_status", ""))
    uses_existing_candidate = _bool_value(
        selected_row.get("uses_existing_validated_non_ml_candidate", False)
    )
    requires_new_training = _bool_value(selected_row.get("requires_new_model_training", True))

    selected_ok = (
        status in {"preferred", "allowed"}
        and uses_existing_candidate
        and not requires_new_training
    )

    return pd.DataFrame(
        [
            {
                "selected_route_id": selected_id,
                "selected_route_label": selected_row.get("route_label", ""),
                "selected": selected_ok,
                "selection_reason": policy.get("primary_selection_rule", ""),
                "backup_route_id": backup_id,
                "deferred_route_id": deferred_id,
                "candidate_system_id": selected_row.get("candidate_system_id", ""),
                "next_phase": policy.get("next_phase_if_selected", ""),
                "ml_v1_reopened": False,
                "model_training_permission": False,
                "holdout_prediction_permission": False,
                "feature_importance_permission": False,
                "signal_creation_permission": False,
                "backtest_generation_permission": False,
                "paper_trading_permission": False,
                "candidate_promotion": False,
            }
        ]
    )


def _route_comparison_report(routes: pd.DataFrame) -> pd.DataFrame:
    if routes.empty:
        return pd.DataFrame()

    out = routes.copy()
    numeric_cols = ["paper_trading_speed_rank", "validation_strength_rank", "scope_risk_rank"]

    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(99)

    out["route_score"] = (
        out["paper_trading_speed_rank"]
        + out["validation_strength_rank"]
        + out["scope_risk_rank"]
    )
    out["fastest_responsible_path"] = out["route_score"] == out["route_score"].min()
    return out.sort_values("route_score").reset_index(drop=True)


def _config_flag_check(config: dict[str, Any], expected: dict[str, bool]) -> pd.DataFrame:
    rows = []

    for key, expected_value in expected.items():
        actual = config.get(key, {}).get("enabled")
        rows.append(
            {
                "config_key": key,
                "expected_enabled": expected_value,
                "actual_enabled": actual,
                "passed": actual is expected_value,
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _phase14a_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    boundary = section.get("phase14a_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": "phase14a_boundary_is_visual_backtest_preregistration_only",
            "passed": (
                "visual backtest" in allowed
                and ("pre-registration" in allowed or "preregistration" in allowed)
            ),
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": "phase14a_boundary_blocks_live_or_unregistered_actions",
            "passed": bool(
                "live trading" in forbidden
                and "real-money deployment" in forbidden
                and "unregistered model training" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def save_phase13aw_paper_trading_candidate_route_selection(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13aw_paper_trading_candidate_route_selection")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    source_check = _source_report_check(source_reports)
    phase13av_check = _phase_result_check(
        source_reports["phase13av_conclusion"],
        source_reports["phase13av_gate_report"],
        "Phase 13AV",
    )

    commercial_decision = _read_csv_if_exists(
        source_reports["phase13av_commercial_decision_report"]
    )
    blocked = _read_csv_if_exists(source_reports["phase13av_blocked_next_steps_report"])

    routes = _normalise_route_registry(section.get("route_registry", []))
    comparison = _route_comparison_report(routes)
    selection = _route_selection_report(
        routes,
        section.get("route_selection_policy", {}),
        commercial_decision,
    )
    config_check = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    boundary = _phase14a_boundary_check(section)
    scope = _scope_check(section)

    ml_minor_repair_blocked = (
        "technical_macro_ml_minor_repair"
        in set(blocked.get("blocked_next_step", pd.Series(dtype=str)).astype(str))
        if not blocked.empty
        else False
    )

    selected_route_allowed = (
        not selection.empty
        and _bool_value(selection.iloc[0].get("selected", False))
    )

    summary = pd.DataFrame(
        [
            {
                "decision_role": section.get("decision_role", ""),
                "implementation_classification": section.get(
                    "implementation_classification",
                    "",
                ),
                "phase13av_passed": bool(phase13av_check["passed"].all()),
                "config_flags_clean": bool(config_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all())
                if not source_check.empty
                else False,
                "route_registry_rows": len(routes),
                "selected_route_id": selection.iloc[0].get("selected_route_id", "")
                if not selection.empty
                else "",
                "selected_route_allowed": selected_route_allowed,
                "ml_v1_minor_repair_blocked": ml_minor_repair_blocked,
                "phase14a_boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "visual_backtest_generation": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AV passed",
                bool(summary.iloc[0]["phase13av_passed"]),
                "phase13av",
            ),
            _gate_row(
                "Config flags clean",
                bool(summary.iloc[0]["config_flags_clean"]),
                "runtime flags",
            ),
            _gate_row(
                "Route registry exists",
                len(routes) >= 3,
                f"rows={len(routes)}",
            ),
            _gate_row(
                "Route selection report exists",
                len(selection) == 1,
                "route selection",
            ),
            _gate_row(
                "Selected route is allowed",
                selected_route_allowed,
                str(summary.iloc[0]["selected_route_id"]),
            ),
            _gate_row(
                "ML v1 not reopened without new feature families",
                ml_minor_repair_blocked,
                "minor ML repair blocked",
            ),
            _gate_row(
                "Phase 14A boundary is visual-backtest preregistration only",
                bool(boundary["passed"].all()),
                "phase14a",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Decision role is correct",
                section.get("decision_role")
                == "Paper-trading candidate route selection only",
                section.get("decision_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AW",
                "diagnostic": "Paper-trading candidate route selection",
                "verdict": (
                    "Completed — paper-trading candidate route selection passed"
                    if bool(gate_report["passed"].all())
                    else "Failed paper-trading candidate route selection"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "selected_route_id": selection.iloc[0].get("selected_route_id", "")
                if not selection.empty
                else "",
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13av_result_check": phase13av_check,
        "config_flag_check": config_check,
        "route_registry_report": routes,
        "route_comparison_report": comparison,
        "route_selection_report": selection,
        "phase14a_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13aw_route_selection_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AW route selection reports.")
    return outputs