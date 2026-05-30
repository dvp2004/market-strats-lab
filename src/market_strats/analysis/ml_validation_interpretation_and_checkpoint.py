from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE13W_CONFIG: dict[str, Any] = {
    "enabled": False,
    "interpretation_role": (
        "ML validation result interpretation and continuation decision only"
    ),
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13V",
    "proposed_next_phase": "Phase 13X",
    "allow_model_training": False,
    "allow_model_selection": False,
    "allow_prediction_generation": False,
    "allow_holdout_prediction_generation": False,
    "allow_feature_importance": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "interpretation_thresholds": {},
    "decision_policy": {},
    "phase13x_boundary": {},
    "phase13y_boundary": {},
    "gates": {
        "require_phase13v_passed": True,
        "require_source_reports_present": True,
        "require_validation_ranking_report": True,
        "require_dummy_comparison_report": True,
        "require_overfit_diagnostic_report": True,
        "require_class_recall_report": True,
        "require_continuation_decision_report": True,
        "require_phase13x_boundary_checkpoint_only": True,
        "require_phase13y_boundary_prereg_only": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_prediction_generation": True,
        "require_no_holdout_prediction_generation": True,
        "require_no_feature_importance": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_interpretation_role": (
            "ML validation result interpretation and continuation decision only"
        ),
    },
}


DEFAULT_PHASE13X_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "ML branch checkpoint and report-config consistency audit only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13W",
    "proposed_next_phase": "Phase 13Y",
    "allow_model_training": False,
    "allow_model_selection": False,
    "allow_prediction_generation": False,
    "allow_holdout_prediction_generation": False,
    "allow_feature_importance": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "phase13w_reports": {},
    "checkpoint_reports": {},
    "phase13y_boundary": {},
    "gates": {
        "require_phase13w_reports_present": True,
        "require_phase13w_conclusion_passed": True,
        "require_phase13w_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_checkpoint_reports_present": True,
        "require_interpretation_boundary_clean": True,
        "require_forbidden_overclaim_absent": True,
        "require_phase13y_boundary_prereg_only": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_prediction_generation": True,
        "require_no_holdout_prediction_generation": True,
        "require_no_feature_importance": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_audit_role": (
            "ML branch checkpoint and report-config consistency audit only"
        ),
    },
}


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _get_phase13w_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13W_CONFIG,
        config.get("phase13w_ml_validation_interpretation_decision", {}),
    )


def _get_phase13x_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13X_CONFIG,
        config.get("phase13x_ml_branch_checkpoint_audit", {}),
    )


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


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase13w_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for report_key, path in phase_config.get("source_reports", {}).items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "report_key": str(report_key),
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": int(len(frame)),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13w_phase13v_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13v_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13v_gate_report", ""))

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_report_passed = (
        not gate_report.empty
        and "passed" in gate_report.columns
        and bool(gate_report["passed"].map(_bool_value).all())
    )

    out = pd.DataFrame(
        [
            {
                "check": "Phase 13V conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13V gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13w_validation_ranking_report(
    metric_report: pd.DataFrame,
    baseline_comparison: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if metric_report.empty:
        return pd.DataFrame()

    validation = metric_report[
        metric_report["split_label"].astype(str).eq("validation")
    ].copy()
    keep = [
        "model_id",
        "rows",
        "accuracy",
        "balanced_accuracy",
        "macro_precision",
        "macro_recall",
        "macro_f1",
        "weighted_f1",
    ]
    validation = validation[[col for col in keep if col in validation.columns]].copy()

    if not baseline_comparison.empty:
        deltas = baseline_comparison[
            [
                "model_id",
                "delta_balanced_accuracy_vs_majority",
                "delta_macro_f1_vs_majority",
            ]
        ].copy()
        validation = validation.merge(deltas, on="model_id", how="left")

    thresholds = phase_config.get("interpretation_thresholds", {})
    real_model_ids = set(str(item) for item in _as_list(thresholds.get("real_model_ids")))
    validation["is_real_model"] = validation["model_id"].astype(str).isin(real_model_ids)
    validation["rank_by_validation_balanced_accuracy"] = (
        validation["balanced_accuracy"]
        .astype(float)
        .rank(ascending=False, method="dense")
        .astype(int)
    )
    validation["diagnostic_leading_model"] = False

    real_models = validation[validation["is_real_model"]].copy()
    if not real_models.empty:
        best_idx = real_models["balanced_accuracy"].astype(float).idxmax()
        validation.loc[best_idx, "diagnostic_leading_model"] = True

    validation["model_selected"] = False
    validation["candidate_promotion"] = False
    validation["signal_permission"] = False
    return validation.sort_values("rank_by_validation_balanced_accuracy")


def build_phase13w_dummy_comparison_report(
    ranking: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if ranking.empty:
        return pd.DataFrame()

    thresholds = phase_config.get("interpretation_thresholds", {})
    majority_id = str(thresholds.get("majority_baseline_model_id", "baseline_majority_class"))
    stratified_id = str(
        thresholds.get("stratified_baseline_model_id", "baseline_stratified_dummy")
    )
    real_model_ids = set(str(item) for item in _as_list(thresholds.get("real_model_ids")))

    majority = ranking[ranking["model_id"].astype(str).eq(majority_id)]
    stratified = ranking[ranking["model_id"].astype(str).eq(stratified_id)]
    real_models = ranking[ranking["model_id"].astype(str).isin(real_model_ids)]

    if real_models.empty:
        return pd.DataFrame()

    best = real_models.sort_values("balanced_accuracy", ascending=False).iloc[0]

    majority_bal_acc = float(majority.iloc[0]["balanced_accuracy"]) if not majority.empty else 0.0
    majority_macro_f1 = float(majority.iloc[0]["macro_f1"]) if not majority.empty else 0.0
    strat_bal_acc = (
        float(stratified.iloc[0]["balanced_accuracy"]) if not stratified.empty else 0.0
    )
    strat_macro_f1 = float(stratified.iloc[0]["macro_f1"]) if not stratified.empty else 0.0

    delta_bal_majority = float(best["balanced_accuracy"]) - majority_bal_acc
    delta_f1_majority = float(best["macro_f1"]) - majority_macro_f1
    delta_bal_stratified = float(best["balanced_accuracy"]) - strat_bal_acc
    delta_f1_stratified = float(best["macro_f1"]) - strat_macro_f1

    min_majority_bal = float(
        thresholds.get("min_material_delta_balanced_accuracy_vs_majority", 0.05)
    )
    min_majority_f1 = float(thresholds.get("min_material_delta_macro_f1_vs_majority", 0.05))
    min_strat_bal = float(thresholds.get("min_delta_balanced_accuracy_vs_stratified", 0.03))

    return pd.DataFrame(
        [
            {
                "diagnostic_leading_model": str(best["model_id"]),
                "validation_balanced_accuracy": float(best["balanced_accuracy"]),
                "validation_macro_f1": float(best["macro_f1"]),
                "majority_balanced_accuracy": majority_bal_acc,
                "majority_macro_f1": majority_macro_f1,
                "stratified_balanced_accuracy": strat_bal_acc,
                "stratified_macro_f1": strat_macro_f1,
                "delta_balanced_accuracy_vs_majority": delta_bal_majority,
                "delta_macro_f1_vs_majority": delta_f1_majority,
                "delta_balanced_accuracy_vs_stratified": delta_bal_stratified,
                "delta_macro_f1_vs_stratified": delta_f1_stratified,
                "beats_majority_materially": (
                    delta_bal_majority >= min_majority_bal
                    and delta_f1_majority >= min_majority_f1
                ),
                "beats_stratified_materially": delta_bal_stratified >= min_strat_bal,
                "model_selected": False,
                "diagnostic_only": True,
            }
        ]
    )


def build_phase13w_overfit_diagnostic_report(
    metric_report: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if metric_report.empty:
        return pd.DataFrame()

    thresholds = phase_config.get("interpretation_thresholds", {})
    max_bal_gap = float(thresholds.get("max_overfit_gap_balanced_accuracy_warning", 0.25))
    max_f1_gap = float(thresholds.get("max_overfit_gap_macro_f1_warning", 0.25))

    rows: list[dict[str, Any]] = []
    for model_id, group in metric_report.groupby("model_id"):
        train = group[group["split_label"].astype(str).eq("train")]
        validation = group[group["split_label"].astype(str).eq("validation")]
        if train.empty or validation.empty:
            continue

        train_bal = float(train.iloc[0]["balanced_accuracy"])
        val_bal = float(validation.iloc[0]["balanced_accuracy"])
        train_f1 = float(train.iloc[0]["macro_f1"])
        val_f1 = float(validation.iloc[0]["macro_f1"])

        rows.append(
            {
                "model_id": model_id,
                "train_balanced_accuracy": train_bal,
                "validation_balanced_accuracy": val_bal,
                "balanced_accuracy_gap": train_bal - val_bal,
                "train_macro_f1": train_f1,
                "validation_macro_f1": val_f1,
                "macro_f1_gap": train_f1 - val_f1,
                "overfit_warning": (train_bal - val_bal) > max_bal_gap
                or (train_f1 - val_f1) > max_f1_gap,
                "severe_overfit_note": (
                    "Validation degradation exceeds warning threshold."
                    if (train_bal - val_bal) > max_bal_gap
                    or (train_f1 - val_f1) > max_f1_gap
                    else "No severe overfit warning by configured threshold."
                ),
            }
        )

    return pd.DataFrame(rows).sort_values("balanced_accuracy_gap", ascending=False)


def build_phase13w_class_recall_report(
    confusion_report: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if confusion_report.empty:
        return pd.DataFrame()

    thresholds = phase_config.get("interpretation_thresholds", {})
    fragile_threshold = float(
        thresholds.get("fragile_class_min_validation_recall_warning", 0.20)
    )

    validation = confusion_report[
        confusion_report["split_label"].astype(str).eq("validation")
    ].copy()
    validation["count"] = pd.to_numeric(validation["count"], errors="coerce").fillna(0)

    rows: list[dict[str, Any]] = []
    for (model_id, true_label), group in validation.groupby(["model_id", "true_label"]):
        total = float(group["count"].sum())
        correct = float(
            group[
                group["true_label"].astype(str).eq(group["predicted_label"].astype(str))
            ]["count"].sum()
        )
        recall = correct / total if total > 0 else 0.0
        rows.append(
            {
                "model_id": model_id,
                "class_label": true_label,
                "validation_support": int(total),
                "validation_recall": recall,
                "fragile_recall_warning": (
                    str(true_label) == "fragile" and recall < fragile_threshold
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase13w_continuation_decision_report(
    *,
    dummy_comparison: pd.DataFrame,
    overfit_report: pd.DataFrame,
    class_recall_report: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    policy = phase_config.get("decision_policy", {})

    if dummy_comparison.empty:
        return pd.DataFrame(
            [
                {
                    "decision": "stop_ml_branch_or_return_to_features",
                    "decision_reason": "No real model comparison was available.",
                    "diagnostic_leading_model": "",
                    "holdout_preregistration_justified": False,
                    "model_selected": False,
                    "signal_permission": False,
                    "backtest_permission": False,
                    "candidate_promotion": False,
                }
            ]
        )

    row = dummy_comparison.iloc[0]
    leading_model = str(row["diagnostic_leading_model"])
    beats_majority = _bool_value(row["beats_majority_materially"])
    beats_stratified = _bool_value(row["beats_stratified_materially"])

    overfit_warning = False
    if not overfit_report.empty:
        model_overfit = overfit_report[
            overfit_report["model_id"].astype(str).eq(leading_model)
        ]
        overfit_warning = (
            _bool_value(model_overfit.iloc[0]["overfit_warning"])
            if not model_overfit.empty
            else False
        )

    fragile_warning = False
    if not class_recall_report.empty:
        model_fragile = class_recall_report[
            class_recall_report["model_id"].astype(str).eq(leading_model)
            & class_recall_report["class_label"].astype(str).eq("fragile")
        ]
        fragile_warning = (
            _bool_value(model_fragile.iloc[0]["fragile_recall_warning"])
            if not model_fragile.empty
            else False
        )

    if beats_majority and beats_stratified and not fragile_warning:
        decision = str(
            policy.get(
                "if_material_edge_and_boundaries_clean",
                "continue_to_holdout_preregistration",
            )
        )
        justified = True
        reason = (
            "Best real model materially beat dummy baselines on validation. "
            "Continuation is justified, but only to a future holdout "
            "pre-registration phase."
        )
    elif beats_majority and (overfit_warning or fragile_warning):
        decision = str(
            policy.get(
                "if_weak_edge_or_severe_class_failure",
                "continue_only_after_model_diagnostic_repair",
            )
        )
        justified = False
        reason = (
            "Validation edge exists, but overfit or fragile-class weakness requires "
            "interpretation/repair before any holdout pre-registration."
        )
    else:
        decision = str(
            policy.get("if_no_real_model_beats_dummy", "stop_ml_branch_or_return_to_features")
        )
        justified = False
        reason = "No real model beat dummy baselines strongly enough."

    return pd.DataFrame(
        [
            {
                "decision": decision,
                "decision_reason": reason,
                "diagnostic_leading_model": leading_model,
                "holdout_preregistration_justified": justified,
                "beats_majority_materially": beats_majority,
                "beats_stratified_materially": beats_stratified,
                "overfit_warning_for_leading_model": overfit_warning,
                "fragile_recall_warning_for_leading_model": fragile_warning,
                "model_selected": False,
                "signal_permission": False,
                "backtest_permission": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13w_boundary_check(
    phase_config: dict[str, Any],
    boundary_key: str,
    phase_label: str,
) -> pd.DataFrame:
    boundary = phase_config.get(boundary_key, {})
    allowed = str(
        boundary.get("allowed_next_step", boundary.get("allowed_future_step", ""))
    ).lower()
    forbidden = str(
        boundary.get("forbidden_next_step", boundary.get("forbidden_future_step", ""))
    ).lower()

    checks = [
        (
            f"{phase_label}_allowed_boundary",
            allowed,
            "checkpoint" in allowed
            or "pre-registration" in allowed
            or "preregistration" in allowed,
        ),
        (
            f"{phase_label}_forbidden_boundary",
            forbidden,
            "signal" in forbidden and "backtest" in forbidden,
        ),
        (
            f"{phase_label}_no_holdout_predictions",
            boundary.get(f"{phase_label.lower()}_may_generate_holdout_predictions", False),
            not _bool_value(
                boundary.get(f"{phase_label.lower()}_may_generate_holdout_predictions", False)
            ),
        ),
        (
            f"{phase_label}_no_signal",
            boundary.get(f"{phase_label.lower()}_may_create_signal", False),
            not _bool_value(boundary.get(f"{phase_label.lower()}_may_create_signal", False)),
        ),
        (
            f"{phase_label}_no_backtest",
            boundary.get(f"{phase_label.lower()}_may_run_backtest", False),
            not _bool_value(boundary.get(f"{phase_label.lower()}_may_run_backtest", False)),
        ),
        (
            f"{phase_label}_no_promotion",
            boundary.get(f"{phase_label.lower()}_may_promote_candidate", False),
            not _bool_value(
                boundary.get(f"{phase_label.lower()}_may_promote_candidate", False)
            ),
        ),
    ]

    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No model training", "allow_model_training"),
        ("No model selection", "allow_model_selection"),
        ("No prediction generation", "allow_prediction_generation"),
        ("No holdout prediction generation", "allow_holdout_prediction_generation"),
        ("No feature importance", "allow_feature_importance"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No paper trading deployment", "allow_paper_trading_deployment"),
        ("No candidate promotion", "allow_candidate_promotion"),
        ("No final candidate change", "allow_final_candidate_change"),
    ]

    rows = []
    for label, key in checks:
        value = _bool_value(phase_config.get(key, True))
        rows.append({"scope_item": label, "value": value, "passed": not value})

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13w_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13v_result_check: pd.DataFrame,
    ranking: pd.DataFrame,
    dummy_comparison: pd.DataFrame,
    overfit_report: pd.DataFrame,
    class_recall_report: pd.DataFrame,
    decision_report: pd.DataFrame,
    phase13x_boundary_check: pd.DataFrame,
    phase13y_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    leading_model = (
        str(decision_report.iloc[0]["diagnostic_leading_model"])
        if not decision_report.empty
        else ""
    )
    decision = str(decision_report.iloc[0]["decision"]) if not decision_report.empty else ""

    return pd.DataFrame(
        [
            {
                "interpretation_role": str(phase_config.get("interpretation_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase13v_result_passed": bool(phase13v_result_check["passed"].all())
                if not phase13v_result_check.empty
                else False,
                "validation_ranking_rows": int(len(ranking)),
                "dummy_comparison_rows": int(len(dummy_comparison)),
                "overfit_diagnostic_rows": int(len(overfit_report)),
                "class_recall_rows": int(len(class_recall_report)),
                "continuation_decision_rows": int(len(decision_report)),
                "diagnostic_leading_model": leading_model,
                "continuation_decision": decision,
                "holdout_preregistration_justified": _bool_value(
                    decision_report.iloc[0].get("holdout_preregistration_justified", False)
                )
                if not decision_report.empty
                else False,
                "phase13x_boundary_passed": bool(phase13x_boundary_check["passed"].all())
                if not phase13x_boundary_check.empty
                else False,
                "phase13y_boundary_passed": bool(phase13y_boundary_check["passed"].all())
                if not phase13y_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "model_training": False,
                "model_selection": False,
                "holdout_predictions_generated": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13w_gate_report(
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13W summary exists", False, "No summary.")])

    gates = phase_config.get("gates", {})
    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_interpretation_role",
            "ML validation result interpretation and continuation decision only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13V passed",
            bool(row["phase13v_result_passed"]),
            f"phase13v_result_passed={bool(row['phase13v_result_passed'])}",
        ),
        _gate_row(
            "Source reports are present",
            bool(row["source_reports_present"]),
            f"source_reports_present={bool(row['source_reports_present'])}",
        ),
        _gate_row(
            "Validation ranking report exists",
            int(row["validation_ranking_rows"]) > 0,
            f"validation_ranking_rows={int(row['validation_ranking_rows'])}",
        ),
        _gate_row(
            "Dummy comparison report exists",
            int(row["dummy_comparison_rows"]) > 0,
            f"dummy_comparison_rows={int(row['dummy_comparison_rows'])}",
        ),
        _gate_row(
            "Overfit diagnostic report exists",
            int(row["overfit_diagnostic_rows"]) > 0,
            f"overfit_diagnostic_rows={int(row['overfit_diagnostic_rows'])}",
        ),
        _gate_row(
            "Class recall report exists",
            int(row["class_recall_rows"]) > 0,
            f"class_recall_rows={int(row['class_recall_rows'])}",
        ),
        _gate_row(
            "Continuation decision report exists",
            int(row["continuation_decision_rows"]) > 0,
            f"continuation_decision={row['continuation_decision']}",
        ),
        _gate_row(
            "Phase 13X boundary is checkpoint-only",
            bool(row["phase13x_boundary_passed"]),
            f"phase13x_boundary_passed={bool(row['phase13x_boundary_passed'])}",
        ),
        _gate_row(
            "Phase 13Y boundary is preregistration-only",
            bool(row["phase13y_boundary_passed"]),
            f"phase13y_boundary_passed={bool(row['phase13y_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks model/signal/backtest/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Interpretation role is correct",
            str(row["interpretation_role"]) == required_role,
            f"interpretation_role={row['interpretation_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13w_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — ML validation interpretation/continuation decision passed"
        if all_passed
        else "Failed ML validation interpretation/continuation decision"
    )
    interpretation = (
        "Phase 13W interpreted validation-only ML evidence and decided whether the "
        "branch may proceed to a future holdout pre-registration phase. It did not "
        "train models, select a model, generate holdout predictions, calculate "
        "feature importance, create signals, run backtests, deploy paper trading, "
        "promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13W found an interpretation, boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13W",
                "diagnostic": "ML validation interpretation/continuation decision",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def _write_markdown(
    title: str,
    sections: dict[str, pd.DataFrame],
    output_path: Path,
) -> None:
    lines = [f"# {title}", ""]
    for heading, frame in sections.items():
        lines.extend([f"## {heading}", frame.to_markdown(index=False), ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13w_ml_validation_interpretation_decision(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13w_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = phase_config.get("source_reports", {})
    source_report_check = build_phase13w_source_report_check(phase_config)
    phase13v_result_check = build_phase13w_phase13v_result_check(phase_config)

    metric_report = _read_csv_if_exists(reports.get("metric_report", ""))
    baseline_comparison = _read_csv_if_exists(reports.get("baseline_comparison_report", ""))
    confusion_report = _read_csv_if_exists(reports.get("confusion_matrix_report", ""))

    ranking = build_phase13w_validation_ranking_report(
        metric_report=metric_report,
        baseline_comparison=baseline_comparison,
        phase_config=phase_config,
    )
    dummy_comparison = build_phase13w_dummy_comparison_report(
        ranking=ranking,
        phase_config=phase_config,
    )
    overfit_report = build_phase13w_overfit_diagnostic_report(
        metric_report=metric_report,
        phase_config=phase_config,
    )
    class_recall_report = build_phase13w_class_recall_report(
        confusion_report=confusion_report,
        phase_config=phase_config,
    )
    decision_report = build_phase13w_continuation_decision_report(
        dummy_comparison=dummy_comparison,
        overfit_report=overfit_report,
        class_recall_report=class_recall_report,
        phase_config=phase_config,
    )
    phase13x_boundary_check = build_phase13w_boundary_check(
        phase_config,
        "phase13x_boundary",
        "phase13x",
    )
    phase13y_boundary_check = build_phase13w_boundary_check(
        phase_config,
        "phase13y_boundary",
        "phase13y",
    )
    scope_boundary_check = build_scope_boundary_check(phase_config)

    summary = build_phase13w_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13v_result_check=phase13v_result_check,
        ranking=ranking,
        dummy_comparison=dummy_comparison,
        overfit_report=overfit_report,
        class_recall_report=class_recall_report,
        decision_report=decision_report,
        phase13x_boundary_check=phase13x_boundary_check,
        phase13y_boundary_check=phase13y_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13w_gate_report(phase_config, summary)
    conclusion = build_phase13w_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13v_result_check": phase13v_result_check,
        "validation_ranking_report": ranking,
        "dummy_comparison_report": dummy_comparison,
        "overfit_diagnostic_report": overfit_report,
        "class_recall_report": class_recall_report,
        "continuation_decision_report": decision_report,
        "phase13x_boundary_check": phase13x_boundary_check,
        "phase13y_boundary_check": phase13y_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13w_interpretation_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13W — ML Validation Interpretation / Continuation Decision",
        sections={
            "Validation Ranking Report": ranking,
            "Dummy Comparison Report": dummy_comparison,
            "Overfit Diagnostic Report": overfit_report,
            "Class Recall Report": class_recall_report,
            "Continuation Decision Report": decision_report,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13w_ml_validation_interpretation_decision.md",
    )

    print("Wrote Phase 13W ML validation interpretation reports.")
    return outputs


def build_phase13x_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for report_key, path in phase_config.get("phase13w_reports", {}).items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "report_key": report_key,
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": int(len(frame)),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13x_phase13w_result_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    reports = phase_config.get("phase13w_reports", {})
    conclusion = _read_csv_if_exists(reports.get("conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("gate_report", ""))

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_report_passed = (
        not gate_report.empty
        and "passed" in gate_report.columns
        and bool(gate_report["passed"].map(_bool_value).all())
    )

    out = pd.DataFrame(
        [
            {
                "check": "Phase 13W conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13W gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13x_config_flag_check(
    runtime_config: dict[str, Any],
    expected_flags: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    for key, expected in expected_flags.items():
        actual = runtime_config.get(key, {}).get("enabled")
        passed = actual is expected
        rows.append(
            {
                "config_key": key,
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )
    return pd.DataFrame(rows)


def build_phase13x_checkpoint_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for path in _as_list(
        phase_config.get("checkpoint_reports", {}).get("required_phase13_reports")
    ):
        report_path = Path(str(path))
        rows.append(
            {
                "path": str(report_path),
                "present": report_path.exists(),
                "result": "Passed" if report_path.exists() else "Failed",
            }
        )
    return pd.DataFrame(rows)


def build_phase13x_interpretation_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    reports = phase_config.get("phase13w_reports", {})
    decision = _read_csv_if_exists(reports.get("continuation_decision_report", ""))

    if decision.empty:
        return pd.DataFrame(
            [
                {
                    "check": "Continuation decision exists",
                    "passed": False,
                    "detail": "missing",
                    "result": "Failed",
                }
            ]
        )

    row = decision.iloc[0]
    checks = [
        (
            "Decision is interpretation-only",
            True,
            str(row.get("decision", "")),
        ),
        (
            "No model selected",
            not _bool_value(row.get("model_selected", True)),
            f"model_selected={row.get('model_selected')}",
        ),
        (
            "No signal permission",
            not _bool_value(row.get("signal_permission", True)),
            f"signal_permission={row.get('signal_permission')}",
        ),
        (
            "No backtest permission",
            not _bool_value(row.get("backtest_permission", True)),
            f"backtest_permission={row.get('backtest_permission')}",
        ),
        (
            "No candidate promotion",
            not _bool_value(row.get("candidate_promotion", True)),
            f"candidate_promotion={row.get('candidate_promotion')}",
        ),
    ]

    out = pd.DataFrame(
        [{"check": check, "passed": passed, "detail": detail} for check, passed, detail in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13x_forbidden_overclaim_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checkpoint = phase_config.get("checkpoint_reports", {})
    forbidden = [str(item).lower() for item in _as_list(checkpoint.get("forbidden_overclaim_phrases"))]
    rows = []

    report_paths = list(phase_config.get("phase13w_reports", {}).values())

    for phrase in forbidden:
        matched_paths = []
        for path in report_paths:
            report_path = Path(str(path))
            if not report_path.exists():
                continue
            text = report_path.read_text(encoding="utf-8", errors="ignore").lower()
            if phrase in text:
                matched_paths.append(str(report_path))

        rows.append(
            {
                "phrase": phrase,
                "matched_paths": "; ".join(matched_paths),
                "passed": len(matched_paths) == 0,
                "result": "Passed" if len(matched_paths) == 0 else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase13x_phase13y_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase13y_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    checks = [
        (
            "phase13y_allowed_next_step",
            allowed,
            "pre-registration" in allowed or "preregistration" in allowed,
        ),
        (
            "phase13y_forbidden_next_step",
            forbidden,
            "holdout prediction execution" in forbidden
            and "signal creation" in forbidden
            and "strategy backtest" in forbidden,
        ),
        (
            "phase13y_may_preregister_holdout_evaluation",
            boundary.get("phase13y_may_preregister_holdout_evaluation", False),
            _bool_value(boundary.get("phase13y_may_preregister_holdout_evaluation", False)),
        ),
        (
            "phase13y_may_generate_holdout_predictions",
            boundary.get("phase13y_may_generate_holdout_predictions", True),
            not _bool_value(boundary.get("phase13y_may_generate_holdout_predictions", True)),
        ),
        (
            "phase13y_may_select_model",
            boundary.get("phase13y_may_select_model", True),
            not _bool_value(boundary.get("phase13y_may_select_model", True)),
        ),
        (
            "phase13y_may_create_signal",
            boundary.get("phase13y_may_create_signal", True),
            not _bool_value(boundary.get("phase13y_may_create_signal", True)),
        ),
        (
            "phase13y_may_run_backtest",
            boundary.get("phase13y_may_run_backtest", True),
            not _bool_value(boundary.get("phase13y_may_run_backtest", True)),
        ),
        (
            "phase13y_may_promote_candidate",
            boundary.get("phase13y_may_promote_candidate", True),
            not _bool_value(boundary.get("phase13y_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13x_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13w_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    checkpoint_report_check: pd.DataFrame,
    interpretation_boundary_check: pd.DataFrame,
    forbidden_overclaim_check: pd.DataFrame,
    phase13y_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13w_reports_present": bool(report_inventory_check["present"].all())
                if not report_inventory_check.empty
                else False,
                "phase13w_result_passed": bool(phase13w_result_check["passed"].all())
                if not phase13w_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "checkpoint_reports_present": bool(checkpoint_report_check["present"].all())
                if not checkpoint_report_check.empty
                else False,
                "interpretation_boundary_clean": bool(
                    interpretation_boundary_check["passed"].all()
                )
                if not interpretation_boundary_check.empty
                else False,
                "forbidden_overclaim_absent": bool(
                    forbidden_overclaim_check["passed"].all()
                )
                if not forbidden_overclaim_check.empty
                else False,
                "phase13y_boundary_passed": bool(phase13y_boundary_check["passed"].all())
                if not phase13y_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "model_training": False,
                "model_selection": False,
                "holdout_predictions_generated": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13x_gate_report(
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13X summary exists", False, "No summary.")])

    gates = phase_config.get("gates", {})
    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_audit_role",
            "ML branch checkpoint and report-config consistency audit only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13W reports are present",
            bool(row["phase13w_reports_present"]),
            f"phase13w_reports_present={bool(row['phase13w_reports_present'])}",
        ),
        _gate_row(
            "Phase 13W conclusion and gates passed",
            bool(row["phase13w_result_passed"]),
            f"phase13w_result_passed={bool(row['phase13w_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Checkpoint reports are present",
            bool(row["checkpoint_reports_present"]),
            f"checkpoint_reports_present={bool(row['checkpoint_reports_present'])}",
        ),
        _gate_row(
            "Interpretation boundary is clean",
            bool(row["interpretation_boundary_clean"]),
            f"interpretation_boundary_clean={bool(row['interpretation_boundary_clean'])}",
        ),
        _gate_row(
            "Forbidden overclaim phrases are absent",
            bool(row["forbidden_overclaim_absent"]),
            f"forbidden_overclaim_absent={bool(row['forbidden_overclaim_absent'])}",
        ),
        _gate_row(
            "Phase 13Y boundary is preregistration-only",
            bool(row["phase13y_boundary_passed"]),
            f"phase13y_boundary_passed={bool(row['phase13y_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks model/signal/backtest/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Audit role is correct",
            str(row["audit_role"]) == required_role,
            f"audit_role={row['audit_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13x_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — ML branch checkpoint audit passed"
        if all_passed
        else "Failed ML branch checkpoint audit"
    )
    interpretation = (
        "Phase 13X checkpointed the ML branch after validation-only interpretation. "
        "It confirmed report/config consistency and preserved the no-holdout, "
        "no-signal, no-backtest, no-promotion boundary. It did not train models, "
        "select a model, generate predictions, calculate feature importance, create "
        "signals, run backtests, deploy paper trading, promote a candidate, or change "
        "the final candidate."
        if all_passed
        else "Phase 13X found a report, config, interpretation-boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13X",
                "diagnostic": "ML branch checkpoint audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def save_phase13x_ml_branch_checkpoint_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13x_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase13x_report_inventory_check(phase_config)
    phase13w_result_check = build_phase13x_phase13w_result_check(phase_config)
    config_flag_check = build_phase13x_config_flag_check(
        config,
        phase_config.get("expected_runtime_flags", {}),
    )
    checkpoint_report_check = build_phase13x_checkpoint_report_check(phase_config)
    interpretation_boundary_check = build_phase13x_interpretation_boundary_check(
        phase_config
    )
    forbidden_overclaim_check = build_phase13x_forbidden_overclaim_check(phase_config)
    phase13y_boundary_check = build_phase13x_phase13y_boundary_check(phase_config)
    scope_boundary_check = build_scope_boundary_check(phase_config)

    summary = build_phase13x_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13w_result_check=phase13w_result_check,
        config_flag_check=config_flag_check,
        checkpoint_report_check=checkpoint_report_check,
        interpretation_boundary_check=interpretation_boundary_check,
        forbidden_overclaim_check=forbidden_overclaim_check,
        phase13y_boundary_check=phase13y_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13x_gate_report(phase_config, summary)
    conclusion = build_phase13x_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13w_result_check": phase13w_result_check,
        "config_flag_check": config_flag_check,
        "checkpoint_report_check": checkpoint_report_check,
        "interpretation_boundary_check": interpretation_boundary_check,
        "forbidden_overclaim_check": forbidden_overclaim_check,
        "phase13y_boundary_check": phase13y_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13x_checkpoint_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13X — ML Branch Checkpoint Audit",
        sections={
            "Checkpoint Report Check": checkpoint_report_check,
            "Interpretation Boundary Check": interpretation_boundary_check,
            "Forbidden Overclaim Check": forbidden_overclaim_check,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path / "phase13x_ml_branch_checkpoint_audit.md",
    )

    print("Wrote Phase 13X ML branch checkpoint audit reports.")
    return outputs