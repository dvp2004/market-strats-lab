from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.analysis.ml_registered_training_and_result_audit import (
    _bool_value,
    _read_csv_if_exists,
)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


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
    rows: list[dict[str, Any]] = []

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


def _phase_result_check(conclusion_path: str, gate_path: str, phase_name: str) -> pd.DataFrame:
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
        "allow_repair_execution",
        "allow_model_selection",
        "allow_holdout_prediction_generation",
        "allow_feature_importance",
        "allow_signal_creation",
        "allow_strategy_backtest",
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


def _best_repair_row(success: pd.DataFrame) -> pd.Series | None:
    if success.empty or "validation_balanced_accuracy" not in success.columns:
        return None

    frame = success.copy()
    frame["validation_balanced_accuracy"] = pd.to_numeric(
        frame["validation_balanced_accuracy"], errors="coerce"
    )
    if frame["validation_balanced_accuracy"].isna().all():
        return None

    return frame.sort_values("validation_balanced_accuracy", ascending=False).iloc[0]


def build_phase13ac_failure_summary_report(
    *,
    repair_success: pd.DataFrame,
    repair_class_recall: pd.DataFrame,
    repair_overfit: pd.DataFrame,
    original_metrics: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    best = _best_repair_row(repair_success)

    original_model = str(thresholds.get("original_best_model_id", "random_forest_classifier"))
    original_best_balanced_accuracy = float(
        thresholds.get("original_best_validation_balanced_accuracy", 0.4253)
    )
    original_best_macro_f1 = float(thresholds.get("original_best_validation_macro_f1", 0.4010))

    fragile_threshold = float(thresholds.get("fragile_recall_success_threshold", 0.20))
    max_overfit_gap = float(thresholds.get("max_acceptable_overfit_gap", 0.30))

    fragile_rows = (
        repair_class_recall[
            repair_class_recall["class_label"].astype(str).eq("fragile")
        ].copy()
        if not repair_class_recall.empty and "class_label" in repair_class_recall.columns
        else pd.DataFrame()
    )

    max_fragile_recall = (
        pd.to_numeric(fragile_rows["validation_recall"], errors="coerce").max()
        if not fragile_rows.empty
        else 0.0
    )

    overfit_pass_count = 0
    if not repair_overfit.empty and "balanced_accuracy_gap" in repair_overfit.columns:
        overfit_gap = pd.to_numeric(repair_overfit["balanced_accuracy_gap"], errors="coerce")
        overfit_pass_count = int((overfit_gap <= max_overfit_gap).sum())

    if best is None:
        best_repair_id = ""
        best_validation_balanced_accuracy = 0.0
        best_validation_macro_f1 = 0.0
        best_fragile_recall = 0.0
    else:
        best_repair_id = str(best.get("repair_id", ""))
        best_validation_balanced_accuracy = float(best.get("validation_balanced_accuracy", 0.0))
        best_validation_macro_f1 = float(best.get("validation_macro_f1", 0.0))
        best_fragile_recall = float(best.get("validation_fragile_recall", 0.0))

    return pd.DataFrame(
        [
            {
                "diagnostic": "repair_failure_summary",
                "original_best_model": original_model,
                "original_best_validation_balanced_accuracy": original_best_balanced_accuracy,
                "original_best_validation_macro_f1": original_best_macro_f1,
                "best_repair_id": best_repair_id,
                "best_repair_validation_balanced_accuracy": best_validation_balanced_accuracy,
                "best_repair_validation_macro_f1": best_validation_macro_f1,
                "best_repair_fragile_recall": best_fragile_recall,
                "max_repair_fragile_recall": float(max_fragile_recall),
                "fragile_recall_success_threshold": fragile_threshold,
                "any_repair_passed_fragile_recall": bool(max_fragile_recall >= fragile_threshold),
                "best_repair_beats_original_balanced_accuracy": bool(
                    best_validation_balanced_accuracy > original_best_balanced_accuracy
                ),
                "best_repair_beats_original_macro_f1": bool(
                    best_validation_macro_f1 > original_best_macro_f1
                ),
                "repair_variants_with_acceptable_overfit_gap": overfit_pass_count,
                "economic_repair_success": bool(
                    max_fragile_recall >= fragile_threshold
                    and best_validation_balanced_accuracy > original_best_balanced_accuracy
                ),
            }
        ]
    )


def build_phase13ac_target_distribution_report(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty or "split_label" not in dataset.columns:
        return pd.DataFrame()

    target_col = "future_63d_spy_return_state"
    if target_col not in dataset.columns:
        return pd.DataFrame()

    rows = []
    for split, group in dataset.groupby("split_label"):
        total = len(group)
        counts = group[target_col].astype(str).value_counts(dropna=False).to_dict()
        for class_label, count in counts.items():
            rows.append(
                {
                    "split_label": split,
                    "class_label": class_label,
                    "rows": int(count),
                    "split_rows": int(total),
                    "class_ratio": float(count / total) if total else 0.0,
                }
            )

    return pd.DataFrame(rows).sort_values(["split_label", "class_label"])


def build_phase13ac_class_imbalance_report(
    target_distribution: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    if target_distribution.empty:
        return pd.DataFrame()

    fragile_warning_ratio = float(thresholds.get("min_fragile_support_warning_ratio", 0.15))
    validation = target_distribution[
        target_distribution["split_label"].astype(str).eq("validation")
    ].copy()

    rows = []
    for _, row in validation.iterrows():
        is_fragile = str(row["class_label"]) == "fragile"
        ratio = float(row["class_ratio"])
        rows.append(
            {
                "split_label": row["split_label"],
                "class_label": row["class_label"],
                "rows": int(row["rows"]),
                "class_ratio": ratio,
                "fragile_support_warning": bool(is_fragile and ratio < fragile_warning_ratio),
                "class_imbalance_issue": bool(ratio < fragile_warning_ratio),
            }
        )

    return pd.DataFrame(rows)


def build_phase13ac_target_outcome_profile_report(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty or "future_63d_spy_return_state" not in dataset.columns:
        return pd.DataFrame()

    cols = [
        col
        for col in ["future_return_63d", "future_window_max_drawdown_63d"]
        if col in dataset.columns
    ]
    if not cols:
        return pd.DataFrame(
            [
                {
                    "class_label": "unavailable",
                    "metric": "future_outcome_columns",
                    "value": "missing",
                }
            ]
        )

    frame = dataset[dataset["target_available"].map(_bool_value)].copy()
    rows = []

    for class_label, group in frame.groupby("future_63d_spy_return_state"):
        for col in cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            rows.append(
                {
                    "class_label": class_label,
                    "outcome_column": col,
                    "rows": int(len(values)),
                    "mean": float(values.mean()) if len(values) else 0.0,
                    "median": float(values.median()) if len(values) else 0.0,
                    "min": float(values.min()) if len(values) else 0.0,
                    "max": float(values.max()) if len(values) else 0.0,
                    "std": float(values.std()) if len(values) > 1 else 0.0,
                }
            )

    return pd.DataFrame(rows)


def build_phase13ac_failure_attribution_report(
    *,
    failure_summary: pd.DataFrame,
    class_imbalance: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if failure_summary.empty:
        return pd.DataFrame()

    row = failure_summary.iloc[0]
    fragile_unresolved = not _bool_value(row["any_repair_passed_fragile_recall"])
    repair_did_not_beat_original = not _bool_value(row["best_repair_beats_original_balanced_accuracy"])
    class_imbalance_issue = (
        bool(class_imbalance["class_imbalance_issue"].map(_bool_value).any())
        if not class_imbalance.empty
        else False
    )

    families = set(_as_list(phase_config.get("attribution_families")))
    rows = []

    def add(family: str, severity: str, evidence: str, recommended_action: str):
        if family in families:
            rows.append(
                {
                    "attribution_family": family,
                    "severity": severity,
                    "evidence": evidence,
                    "recommended_action": recommended_action,
                    "holdout_allowed": False,
                    "signal_allowed": False,
                    "backtest_allowed": False,
                    "candidate_promotion": False,
                }
            )

    add(
        "target_definition",
        "high" if fragile_unresolved else "medium",
        "Fragile class remains unrecalled after registered repair variants.",
        "Pre-register target-definition audit before more model tuning.",
    )
    add(
        "horizon_63d",
        "medium",
        "Current target uses a 63D horizon; fragile events may be too sparse or poorly aligned.",
        "Compare alternative horizons only through a future pre-registration spec.",
    )
    add(
        "fragile_threshold",
        "high" if fragile_unresolved else "medium",
        "Fragile recall remained below success threshold.",
        "Audit whether fragile threshold creates a learnable class boundary.",
    )
    add(
        "class_imbalance",
        "high" if class_imbalance_issue else "medium",
        "Validation fragile support is low relative to other classes.",
        "Pre-register imbalance-aware target/label redesign rather than more ad hoc weighting.",
    )
    add(
        "feature_insufficiency",
        "high" if repair_did_not_beat_original and fragile_unresolved else "medium",
        "Technical + macro features failed to identify fragile regimes reliably.",
        "Consider fundamental/sentiment/market-stress feature-family expansion after target audit.",
    )
    add(
        "model_architecture",
        "medium",
        "Simple RF/logistic/HistGB variants did not solve the defect.",
        "Do not run another random repair bundle; architecture changes require pre-registration.",
    )
    add(
        "missing_fundamental_sentiment",
        "medium",
        "Current dataset is technical + macro only.",
        "Treat full multi-factor goal as unfinished; fundamental/sentiment feasibility remains open.",
    )

    return pd.DataFrame(rows)


def build_phase13ac_continuation_options_report(
    failure_attribution: pd.DataFrame,
) -> pd.DataFrame:
    high_issues = (
        failure_attribution[failure_attribution["severity"].astype(str).eq("high")]
        if not failure_attribution.empty
        else pd.DataFrame()
    )
    high_families = set(high_issues["attribution_family"].astype(str)) if not high_issues.empty else set()

    rows = [
        {
            "option_id": "target_feature_redesign_preregistration",
            "allowed_next": True,
            "reason": "Highest-risk issues point to fragile target/threshold/feature learnability, not merely model tuning.",
            "holdout_allowed": False,
            "signal_allowed": False,
            "backtest_allowed": False,
        },
        {
            "option_id": "another_simple_model_repair",
            "allowed_next": False,
            "reason": "Already failed simple class-weighting and regularisation repair.",
            "holdout_allowed": False,
            "signal_allowed": False,
            "backtest_allowed": False,
        },
        {
            "option_id": "direct_holdout_preregistration",
            "allowed_next": False,
            "reason": "Blocked because fragile recall remains unresolved.",
            "holdout_allowed": False,
            "signal_allowed": False,
            "backtest_allowed": False,
        },
        {
            "option_id": "feature_family_expansion_after_target_audit",
            "allowed_next": "feature_insufficiency" in high_families,
            "reason": "Possible, but only after target/label diagnosis prevents feature shopping.",
            "holdout_allowed": False,
            "signal_allowed": False,
            "backtest_allowed": False,
        },
    ]

    return pd.DataFrame(rows)


def _boundary_report(section: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for key in ["phase13ad_boundary", "phase13ae_boundary"]:
        boundary = section.get(key, {})
        allowed = str(boundary.get("allowed_next_step", boundary.get("allowed_future_step", "")))
        forbidden = str(boundary.get("forbidden_next_step", boundary.get("forbidden_future_step", "")))
        rows.append(
            {
                "boundary": key,
                "allowed": allowed,
                "forbidden": forbidden,
                "passed": bool(
                    ("audit" in allowed.lower() or "decision" in allowed.lower())
                    and "holdout prediction" in forbidden.lower()
                    and "signal creation" in forbidden.lower()
                    and "strategy backtest" in forbidden.lower()
                ),
            }
        )
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def save_phase13ac_ml_failure_attribution_diagnostic(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13ac_ml_failure_attribution_diagnostic")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    source_check = _source_report_check(source_reports)
    phase13ab_check = _phase_result_check(
        source_reports["phase13ab_conclusion"],
        source_reports["phase13ab_gate_report"],
        "Phase 13AB",
    )

    repair_success = _read_csv_if_exists(source_reports["repair_success_report"])
    repair_metric = _read_csv_if_exists(source_reports["repair_metric_report"])
    repair_class_recall = _read_csv_if_exists(source_reports["repair_class_recall_report"])
    repair_overfit = _read_csv_if_exists(source_reports["repair_overfit_report"])
    original_metrics = _read_csv_if_exists(source_reports["original_metric_report"])
    dataset = _read_csv_if_exists(source_reports["dataset"])

    thresholds = section.get("diagnostic_thresholds", {})

    failure_summary = build_phase13ac_failure_summary_report(
        repair_success=repair_success,
        repair_class_recall=repair_class_recall,
        repair_overfit=repair_overfit,
        original_metrics=original_metrics,
        thresholds=thresholds,
    )
    target_distribution = build_phase13ac_target_distribution_report(dataset)
    class_imbalance = build_phase13ac_class_imbalance_report(
        target_distribution,
        thresholds,
    )
    target_outcome_profile = build_phase13ac_target_outcome_profile_report(dataset)
    failure_attribution = build_phase13ac_failure_attribution_report(
        failure_summary=failure_summary,
        class_imbalance=class_imbalance,
        phase_config=section,
    )
    continuation_options = build_phase13ac_continuation_options_report(
        failure_attribution
    )
    boundary = _boundary_report(section)
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "diagnostic_role": section.get("diagnostic_role", ""),
                "phase13ab_passed": bool(phase13ab_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all()) if not source_check.empty else False,
                "failure_summary_rows": len(failure_summary),
                "target_distribution_rows": len(target_distribution),
                "class_imbalance_rows": len(class_imbalance),
                "target_outcome_profile_rows": len(target_outcome_profile),
                "failure_attribution_rows": len(failure_attribution),
                "continuation_options_rows": len(continuation_options),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "repair_execution": False,
                "holdout_predictions": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate = pd.DataFrame(
        [
            _gate_row("Phase 13AB passed", bool(summary.iloc[0]["phase13ab_passed"]), "phase13ab"),
            _gate_row("Source reports present", bool(summary.iloc[0]["source_reports_present"]), "source reports"),
            _gate_row("Failure summary report exists", len(failure_summary) > 0, f"rows={len(failure_summary)}"),
            _gate_row("Target distribution report exists", len(target_distribution) > 0, f"rows={len(target_distribution)}"),
            _gate_row("Class imbalance report exists", len(class_imbalance) > 0, f"rows={len(class_imbalance)}"),
            _gate_row("Target outcome profile report exists", len(target_outcome_profile) > 0, f"rows={len(target_outcome_profile)}"),
            _gate_row("Failure attribution report exists", len(failure_attribution) >= 6, f"rows={len(failure_attribution)}"),
            _gate_row("Continuation options report exists", len(continuation_options) > 0, f"rows={len(continuation_options)}"),
            _gate_row("Boundaries passed", bool(boundary["passed"].all()), "phase13ad/phase13ae"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row("Diagnostic role is correct", section.get("diagnostic_role") == "ML failure attribution and target-feature diagnostic only", section.get("diagnostic_role", "")),
        ]
    )
    gate["all_gates_passed"] = bool(gate["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AC",
                "diagnostic": "ML failure attribution and target-feature diagnostic",
                "verdict": "Completed — ML failure attribution diagnostic passed" if bool(gate["passed"].all()) else "Failed ML failure attribution diagnostic",
                "all_gates_passed": bool(gate["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13ab_result_check": phase13ab_check,
        "failure_summary_report": failure_summary,
        "target_distribution_report": target_distribution,
        "class_imbalance_report": class_imbalance,
        "target_outcome_profile_report": target_outcome_profile,
        "failure_attribution_report": failure_attribution,
        "continuation_options_report": continuation_options,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13ac_failure_attribution_{name}.csv", index=False)

    print("Wrote Phase 13AC ML failure attribution reports.")
    return outputs


def save_phase13ad_ml_failure_attribution_readiness_audit(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13ad_ml_failure_attribution_readiness_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    expected_flags = section.get("expected_runtime_flags", {})
    flag_rows = []
    for key, expected in expected_flags.items():
        actual = config.get(key, {}).get("enabled")
        flag_rows.append(
            {
                "config_key": key,
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": actual is expected,
            }
        )
    config_check = pd.DataFrame(flag_rows)
    config_check["result"] = config_check["passed"].map({True: "Passed", False: "Failed"})

    reports = section.get("phase13ac_reports", {})
    inventory = _source_report_check(reports)
    ac_check = _phase_result_check(reports["conclusion"], reports["gate_report"], "Phase 13AC")
    attribution = _read_csv_if_exists(reports["failure_attribution_report"])
    scope = _scope_check(section)

    required_families = {
        "target_definition",
        "horizon_63d",
        "fragile_threshold",
        "class_imbalance",
        "feature_insufficiency",
        "model_architecture",
    }
    actual_families = set(attribution["attribution_family"].astype(str)) if not attribution.empty else set()
    attribution_complete = required_families.issubset(actual_families)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "phase13ac_passed": bool(ac_check["passed"].all()),
                "config_flags_clean": bool(config_check["passed"].all()),
                "diagnostic_reports_present": bool(inventory["present"].all()) if not inventory.empty else False,
                "attribution_families_present": attribution_complete,
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "repair_execution": False,
                "holdout_predictions": False,
                "signal_creation": False,
                "strategy_backtest": False,
            }
        ]
    )

    gate = pd.DataFrame(
        [
            _gate_row("Phase 13AC passed", bool(summary.iloc[0]["phase13ac_passed"]), "phase13ac"),
            _gate_row("Config flags clean", bool(summary.iloc[0]["config_flags_clean"]), "flags"),
            _gate_row("Diagnostic reports present", bool(summary.iloc[0]["diagnostic_reports_present"]), "inventory"),
            _gate_row("Attribution families present", attribution_complete, f"families={'; '.join(sorted(actual_families))}"),
            _gate_row("Scope blocks forbidden actions", bool(summary.iloc[0]["scope_passed"]), "scope"),
            _gate_row("Audit role is correct", section.get("audit_role") == "ML failure attribution readiness and report audit only", section.get("audit_role", "")),
        ]
    )
    gate["all_gates_passed"] = bool(gate["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AD",
                "diagnostic": "ML failure attribution readiness audit",
                "verdict": "Completed — ML failure attribution readiness audit passed" if bool(gate["passed"].all()) else "Failed ML failure attribution readiness audit",
                "all_gates_passed": bool(gate["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "config_flag_check": config_check,
        "report_inventory_check": inventory,
        "phase13ac_result_check": ac_check,
        "attribution_family_check": pd.DataFrame(
            [
                {
                    "required_families": "; ".join(sorted(required_families)),
                    "actual_families": "; ".join(sorted(actual_families)),
                    "passed": attribution_complete,
                    "result": "Passed" if attribution_complete else "Failed",
                }
            ]
        ),
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13ad_failure_audit_{name}.csv", index=False)

    print("Wrote Phase 13AD ML failure attribution audit reports.")
    return outputs


def build_phase13ae_architecture_decision_report(
    *,
    failure_summary: pd.DataFrame,
    attribution: pd.DataFrame,
    options: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    policy = section.get("decision_policy", {})

    fragile_unresolved = True
    feature_insufficiency_likely = False

    if not failure_summary.empty:
        fragile_unresolved = not _bool_value(failure_summary.iloc[0].get("any_repair_passed_fragile_recall", False))

    if not attribution.empty:
        high = attribution[attribution["severity"].astype(str).eq("high")]
        feature_insufficiency_likely = "feature_insufficiency" in set(high["attribution_family"].astype(str))

    if fragile_unresolved:
        decision = policy.get("if_fragile_recall_unresolved", "pivot_to_target_feature_redesign_preregistration")
        reason = "Fragile recall remained unresolved after registered repair execution."
    elif feature_insufficiency_likely:
        decision = policy.get("if_feature_insufficiency_likely", "prioritise_feature_family_expansion_before_more_model_tuning")
        reason = "Feature insufficiency is a likely bottleneck."
    else:
        decision = policy.get("default_decision", "pivot_to_target_feature_redesign_preregistration")
        reason = "Defaulting to target-feature redesign before any holdout work."

    return pd.DataFrame(
        [
            {
                "architecture_decision": decision,
                "decision_reason": reason,
                "fragile_recall_unresolved": fragile_unresolved,
                "feature_insufficiency_likely": feature_insufficiency_likely,
                "direct_holdout_blocked": True,
                "another_random_repair_blocked": True,
                "model_selected": False,
                "feature_importance_permission": False,
                "signal_permission": False,
                "backtest_permission": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def _next_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    boundary = section.get("next_phase_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    checks = [
        (
            "allowed_next_step_is_redesign_preregistration",
            "target-feature redesign" in allowed and ("pre-registration" in allowed or "preregistration" in allowed),
            allowed,
        ),
        (
            "forbidden_next_step_blocks_holdout",
            "holdout prediction" in forbidden,
            forbidden,
        ),
        (
            "forbidden_next_step_blocks_signal_backtest",
            "signal creation" in forbidden and "strategy backtest" in forbidden,
            forbidden,
        ),
        (
            "may_preregister_target_feature_redesign",
            _bool_value(boundary.get("may_preregister_target_feature_redesign", False)),
            str(boundary.get("may_preregister_target_feature_redesign", "")),
        ),
        (
            "may_train_model_false",
            not _bool_value(boundary.get("may_train_model", True)),
            str(boundary.get("may_train_model", "")),
        ),
        (
            "may_generate_holdout_predictions_false",
            not _bool_value(boundary.get("may_generate_holdout_predictions", True)),
            str(boundary.get("may_generate_holdout_predictions", "")),
        ),
        (
            "may_create_signal_false",
            not _bool_value(boundary.get("may_create_signal", True)),
            str(boundary.get("may_create_signal", "")),
        ),
        (
            "may_run_backtest_false",
            not _bool_value(boundary.get("may_run_backtest", True)),
            str(boundary.get("may_run_backtest", "")),
        ),
        (
            "may_promote_candidate_false",
            not _bool_value(boundary.get("may_promote_candidate", True)),
            str(boundary.get("may_promote_candidate", "")),
        ),
    ]

    out = pd.DataFrame(
        [{"check": check, "passed": passed, "detail": detail} for check, passed, detail in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def save_phase13ae_ml_branch_continuation_architecture_pivot(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13ae_ml_branch_continuation_architecture_pivot")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    source_check = _source_report_check(source_reports)
    ad_check = _phase_result_check(
        source_reports["phase13ad_conclusion"],
        source_reports["phase13ad_gate_report"],
        "Phase 13AD",
    )

    failure_summary = _read_csv_if_exists(source_reports["failure_summary_report"])
    attribution = _read_csv_if_exists(source_reports["failure_attribution_report"])
    options = _read_csv_if_exists(source_reports["continuation_options_report"])

    decision = build_phase13ae_architecture_decision_report(
        failure_summary=failure_summary,
        attribution=attribution,
        options=options,
        section=section,
    )
    boundary = _next_boundary_check(section)
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "decision_role": section.get("decision_role", ""),
                "phase13ad_passed": bool(ad_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all()) if not source_check.empty else False,
                "architecture_decision": decision.iloc[0]["architecture_decision"] if not decision.empty else "",
                "direct_holdout_blocked": _bool_value(decision.iloc[0].get("direct_holdout_blocked", False)) if not decision.empty else False,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "repair_execution": False,
                "holdout_predictions": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate = pd.DataFrame(
        [
            _gate_row("Phase 13AD passed", bool(summary.iloc[0]["phase13ad_passed"]), "phase13ad"),
            _gate_row("Architecture decision exists", len(decision) == 1, f"decision={summary.iloc[0]['architecture_decision']}"),
            _gate_row("Holdout remains blocked", bool(summary.iloc[0]["direct_holdout_blocked"]), "holdout"),
            _gate_row("Next boundary is redesign preregistration only", bool(summary.iloc[0]["boundary_passed"]), "boundary"),
            _gate_row("Scope blocks forbidden actions", bool(summary.iloc[0]["scope_passed"]), "scope"),
            _gate_row("Decision role is correct", section.get("decision_role") == "ML branch continuation and architecture pivot decision only", section.get("decision_role", "")),
        ]
    )
    gate["all_gates_passed"] = bool(gate["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AE",
                "diagnostic": "ML branch continuation and architecture pivot decision",
                "verdict": "Completed — ML branch architecture pivot decision passed" if bool(gate["passed"].all()) else "Failed ML branch architecture pivot decision",
                "all_gates_passed": bool(gate["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13ad_result_check": ad_check,
        "architecture_decision_report": decision,
        "next_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13ae_pivot_decision_{name}.csv", index=False)

    print("Wrote Phase 13AE ML branch architecture pivot reports.")
    return outputs


def save_phase13af_phase13_ml_branch_checkpoint_audit(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13af_phase13_ml_branch_checkpoint_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    expected_flags = section.get("expected_runtime_flags", {})
    flag_rows = []
    for key, expected in expected_flags.items():
        actual = config.get(key, {}).get("enabled")
        flag_rows.append(
            {
                "config_key": key,
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": actual is expected,
            }
        )
    config_check = pd.DataFrame(flag_rows)
    config_check["result"] = config_check["passed"].map({True: "Passed", False: "Failed"})

    ae_reports = section.get("phase13ae_reports", {})
    ae_inventory = _source_report_check(ae_reports)
    ae_check = _phase_result_check(ae_reports["conclusion"], ae_reports["gate_report"], "Phase 13AE")

    checkpoint_paths = section.get("checkpoint_reports", {}).get("required_reports", [])
    checkpoint_rows = []
    for path in checkpoint_paths:
        p = Path(str(path))
        checkpoint_rows.append({"path": str(p), "present": p.exists(), "result": "Passed" if p.exists() else "Failed"})
    checkpoint_check = pd.DataFrame(checkpoint_rows)

    forbidden_phrases = [
        str(item).lower()
        for item in _as_list(section.get("checkpoint_reports", {}).get("forbidden_overclaim_phrases"))
    ]
    text_paths = list(ae_reports.values())
    overclaim_rows = []
    for phrase in forbidden_phrases:
        matched = []
        for path in text_paths:
            p = Path(str(path))
            if p.exists() and phrase in p.read_text(encoding="utf-8", errors="ignore").lower():
                matched.append(str(p))
        overclaim_rows.append(
            {
                "phrase": phrase,
                "matched_paths": "; ".join(matched),
                "passed": len(matched) == 0,
                "result": "Passed" if len(matched) == 0 else "Failed",
            }
        )
    overclaim_check = pd.DataFrame(overclaim_rows)

    boundary = section.get("phase13ag_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()
    phase13ag_boundary_check = pd.DataFrame(
        [
            {
                "check": "phase13ag_boundary_is_target_feature_redesign_prereg",
                "passed": bool("target-feature redesign" in allowed and "holdout prediction" in forbidden),
                "detail": boundary.get("allowed_next_step", ""),
                "result": "Passed" if "target-feature redesign" in allowed and "holdout prediction" in forbidden else "Failed",
            }
        ]
    )

    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "phase13ae_passed": bool(ae_check["passed"].all()),
                "config_flags_clean": bool(config_check["passed"].all()),
                "checkpoint_reports_present": bool(checkpoint_check["present"].all()) if not checkpoint_check.empty else False,
                "forbidden_overclaim_absent": bool(overclaim_check["passed"].all()) if not overclaim_check.empty else False,
                "phase13ag_boundary_passed": bool(phase13ag_boundary_check["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "repair_execution": False,
                "holdout_predictions": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate = pd.DataFrame(
        [
            _gate_row("Phase 13AE passed", bool(summary.iloc[0]["phase13ae_passed"]), "phase13ae"),
            _gate_row("Config flags clean", bool(summary.iloc[0]["config_flags_clean"]), "flags"),
            _gate_row("Checkpoint reports present", bool(summary.iloc[0]["checkpoint_reports_present"]), "reports"),
            _gate_row("Forbidden overclaim absent", bool(summary.iloc[0]["forbidden_overclaim_absent"]), "overclaim"),
            _gate_row("Phase 13AG boundary is redesign preregistration only", bool(summary.iloc[0]["phase13ag_boundary_passed"]), "phase13ag"),
            _gate_row("Scope blocks forbidden actions", bool(summary.iloc[0]["scope_passed"]), "scope"),
            _gate_row("Audit role is correct", section.get("audit_role") == "Phase 13 ML branch checkpoint audit only", section.get("audit_role", "")),
        ]
    )
    gate["all_gates_passed"] = bool(gate["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AF",
                "diagnostic": "Phase 13 ML branch checkpoint audit",
                "verdict": "Completed — Phase 13 ML branch checkpoint audit passed" if bool(gate["passed"].all()) else "Failed Phase 13 ML branch checkpoint audit",
                "all_gates_passed": bool(gate["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase13ae_result_check": ae_check,
        "config_flag_check": config_check,
        "checkpoint_report_check": checkpoint_check,
        "forbidden_overclaim_check": overclaim_check,
        "phase13ag_boundary_check": phase13ag_boundary_check,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13af_checkpoint_{name}.csv", index=False)

    print("Wrote Phase 13AF ML branch checkpoint reports.")
    return outputs