from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE13S_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": (
        "ML model training pre-registration and baseline model design spec only"
    ),
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13R",
    "proposed_next_phase": "Phase 13T",
    "allow_model_training": False,
    "allow_model_selection": False,
    "allow_prediction_generation": False,
    "allow_feature_importance": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "dataset_requirements": {},
    "target_policy": {},
    "model_family_registry": [],
    "preprocessing_policy": {},
    "split_usage_policy": {},
    "metric_registry": {},
    "report_templates": {},
    "phase13t_boundary": {},
    "gates": {
        "require_phase13r_passed": True,
        "require_source_reports_present": True,
        "require_dataset_schema_profile": True,
        "require_dataset_requirements_passed": True,
        "require_target_policy": True,
        "require_model_family_registry": True,
        "min_allowed_model_families": 4,
        "require_preprocessing_policy": True,
        "require_split_usage_policy": True,
        "require_metric_registry": True,
        "require_report_templates": True,
        "require_phase13t_boundary_readiness_only": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_prediction_generation": True,
        "require_no_feature_importance": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_spec_role": (
            "ML model training pre-registration and baseline model design spec only"
        ),
    },
}


DEFAULT_PHASE13T_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "ML training readiness and leakage boundary audit only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13S",
    "proposed_next_phase": "Phase 13U",
    "allow_model_training": False,
    "allow_model_selection": False,
    "allow_prediction_generation": False,
    "allow_feature_importance": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "phase13s_reports": {},
    "readiness_thresholds": {},
    "forbidden_output_paths": [],
    "phase13u_boundary": {},
    "gates": {
        "require_phase13s_reports_present": True,
        "require_phase13s_conclusion_passed": True,
        "require_phase13s_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_dataset_readiness": True,
        "require_training_protocol_completeness": True,
        "require_leakage_boundary_passed": True,
        "require_forbidden_outputs_absent": True,
        "require_phase13u_boundary_registered_training_only": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_prediction_generation": True,
        "require_no_feature_importance": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_audit_role": "ML training readiness and leakage boundary audit only",
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


def _get_phase13s_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13S_CONFIG,
        config.get("phase13s_ml_model_training_preregistration_spec", {}),
    )


def _get_phase13t_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13T_CONFIG,
        config.get("phase13t_ml_training_readiness_leakage_audit", {}),
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


def _join_list(value: Any) -> str:
    return "; ".join(str(item) for item in _as_list(value))


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


def build_phase13s_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase13s_phase13r_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13r_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13r_gate_report", ""))

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
                "check": "Phase 13R conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13R gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13s_dataset_schema_profile(
    *,
    dataset: pd.DataFrame,
    metadata: pd.DataFrame,
) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame(
            [
                {
                    "rows": 0,
                    "columns": 0,
                    "dataset_label": "",
                    "value_feature_columns": 0,
                    "macro_value_feature_columns": 0,
                    "state_feature_columns": 0,
                    "missingness_feature_columns": 0,
                    "target_columns": "",
                    "split_labels": "",
                }
            ]
        )

    value_cols = [col for col in dataset.columns if str(col).startswith("value__")]
    macro_value_cols = [col for col in value_cols if "macro_" in str(col)]
    state_cols = [col for col in dataset.columns if str(col).startswith("state__")]
    missingness_cols = [
        col for col in dataset.columns if str(col).startswith("missingness__")
    ]
    target_cols = [
        col
        for col in dataset.columns
        if str(col).startswith("future_") or str(col) == "target_available"
    ]
    split_labels = (
        sorted(dataset["split_label"].dropna().astype(str).unique())
        if "split_label" in dataset.columns
        else []
    )
    dataset_label = (
        str(dataset["dataset_label"].iloc[0])
        if "dataset_label" in dataset.columns and len(dataset) > 0
        else ""
    )

    if not metadata.empty and "dataset_label" in metadata.columns:
        dataset_label = str(metadata.iloc[0].get("dataset_label", dataset_label))

    return pd.DataFrame(
        [
            {
                "rows": int(len(dataset)),
                "columns": int(len(dataset.columns)),
                "dataset_label": dataset_label,
                "value_feature_columns": int(len(value_cols)),
                "macro_value_feature_columns": int(len(macro_value_cols)),
                "state_feature_columns": int(len(state_cols)),
                "missingness_feature_columns": int(len(missingness_cols)),
                "target_columns": "; ".join(target_cols),
                "split_labels": "; ".join(split_labels),
            }
        ]
    )


def build_phase13s_dataset_requirement_check(
    *,
    dataset: pd.DataFrame,
    schema_profile: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    req = phase_config.get("dataset_requirements", {})

    if schema_profile.empty:
        return pd.DataFrame(
            [
                {
                    "check": "Dataset schema profile exists",
                    "passed": False,
                    "detail": "missing",
                    "result": "Failed",
                }
            ]
        )

    row = schema_profile.iloc[0]
    required_targets = set(_as_list(req.get("required_target_columns")))
    actual_targets = set(
        str(col)
        for col in dataset.columns
        if str(col).startswith("future_") or str(col) == "target_available"
    )
    required_splits = set(_as_list(req.get("required_split_labels")))
    actual_splits = (
        set(dataset["split_label"].dropna().astype(str))
        if not dataset.empty and "split_label" in dataset.columns
        else set()
    )
    forbidden_fragments = [
        str(item).lower() for item in _as_list(req.get("forbidden_feature_fragments"))
    ]
    feature_cols = [
        str(col)
        for col in dataset.columns
        if str(col).startswith(("value__", "state__", "missingness__"))
    ]
    matched_forbidden = [
        col
        for col in feature_cols
        if any(fragment in col.lower() for fragment in forbidden_fragments)
    ]

    checks = [
        (
            "Dataset label is repaired technical + macro",
            str(row["dataset_label"]) == str(req.get("required_dataset_label")),
            f"dataset_label={row['dataset_label']}",
        ),
        (
            "Dataset has enough rows",
            int(row["rows"]) >= int(req.get("min_rows", 1000)),
            f"rows={int(row['rows'])}",
        ),
        (
            "Dataset has enough value feature columns",
            int(row["value_feature_columns"])
            >= int(req.get("min_value_feature_columns", 8)),
            f"value_feature_columns={int(row['value_feature_columns'])}",
        ),
        (
            "Dataset has enough macro value feature columns",
            int(row["macro_value_feature_columns"])
            >= int(req.get("min_macro_value_feature_columns", 4)),
            f"macro_value_feature_columns={int(row['macro_value_feature_columns'])}",
        ),
        (
            "Required target columns are present",
            required_targets.issubset(actual_targets),
            f"required_targets={'; '.join(sorted(required_targets))}",
        ),
        (
            "Required split labels are present",
            required_splits.issubset(actual_splits),
            f"actual_splits={'; '.join(sorted(actual_splits))}",
        ),
        (
            "No forbidden feature fragments are present",
            len(matched_forbidden) == 0,
            f"matched_forbidden={'; '.join(matched_forbidden)}",
        ),
    ]

    out = pd.DataFrame(
        [{"check": check, "passed": passed, "detail": detail} for check, passed, detail in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13s_target_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    policy = phase_config.get("target_policy", {})
    rows: list[dict[str, Any]] = []

    for key in ["primary_target", "secondary_target"]:
        target = policy.get(key, {})
        rows.append(
            {
                "target_slot": key,
                "target_id": str(target.get("target_id", "")),
                "target_type": str(target.get("target_type", "")),
                "allowed_classes": _join_list(target.get("allowed_classes")),
                "unavailable_class": str(target.get("unavailable_class", "")),
                "optimisation_role": str(target.get("optimisation_role", "")),
                "training_rows_allowed": str(target.get("training_rows_allowed", "")),
                "validation_rows_allowed": str(
                    target.get("validation_rows_allowed", "")
                ),
                "holdout_rows_allowed": str(target.get("holdout_rows_allowed", "")),
            }
        )

    return pd.DataFrame(rows)


def build_phase13s_model_family_registry(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("model_family_registry")):
        rows.append(
            {
                "model_id": str(item.get("model_id", "")),
                "family": str(item.get("family", "")),
                "allowed": _bool_value(item.get("allowed", False)),
                "role": str(item.get("role", "")),
                "selection_role": str(item.get("selection_role", "")),
                "trained_now": False,
                "selected_now": False,
            }
        )

    return pd.DataFrame(rows)


def build_phase13s_preprocessing_policy(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    policy = phase_config.get("preprocessing_policy", {})

    return pd.DataFrame(
        [
            {
                "fit_scope": str(policy.get("fit_scope", "")),
                "transform_scope": str(policy.get("transform_scope", "")),
                "categorical_encoding": str(policy.get("categorical_encoding", "")),
                "numeric_scaling": str(policy.get("numeric_scaling", "")),
                "imputation": str(policy.get("imputation", "")),
                "class_imbalance_policy": str(
                    policy.get("class_imbalance_policy", "")
                ),
                "leakage_controls": _join_list(policy.get("leakage_controls")),
                "training_execution_now": False,
            }
        ]
    )


def build_phase13s_split_usage_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    policy = phase_config.get("split_usage_policy", {})

    return pd.DataFrame(
        [
            {
                "train_split": str(policy.get("train_split", "")),
                "validation_split": str(policy.get("validation_split", "")),
                "holdout_split": str(policy.get("holdout_split", "")),
                "out_of_split_rows": str(policy.get("out_of_split_rows", "")),
                "walk_forward_now": _bool_value(policy.get("walk_forward_now", False)),
                "walk_forward_later_allowed_only_after_registration": _bool_value(
                    policy.get(
                        "walk_forward_later_allowed_only_after_registration",
                        True,
                    )
                ),
            }
        ]
    )


def build_phase13s_metric_registry(phase_config: dict[str, Any]) -> pd.DataFrame:
    registry = phase_config.get("metric_registry", {})
    rows: list[dict[str, Any]] = []

    for group_name in [
        "primary_metrics",
        "secondary_metrics",
        "calibration_metrics",
        "forbidden_metrics",
    ]:
        for metric in _as_list(registry.get(group_name)):
            rows.append(
                {
                    "metric_group": group_name,
                    "metric": str(metric),
                    "allowed_for_training_eval": group_name != "forbidden_metrics",
                    "trading_metric": group_name == "forbidden_metrics",
                }
            )

    return pd.DataFrame(rows)


def build_phase13s_report_template_registry(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    templates = phase_config.get("report_templates", {})
    rows: list[dict[str, Any]] = []

    for report_name in _as_list(templates.get("required_future_training_reports")):
        rows.append(
            {
                "report_name": str(report_name),
                "required_later": True,
                "forbidden_later": False,
                "created_now": False,
            }
        )

    for report_name in _as_list(templates.get("forbidden_future_training_reports")):
        rows.append(
            {
                "report_name": str(report_name),
                "required_later": False,
                "forbidden_later": True,
                "created_now": False,
            }
        )

    return pd.DataFrame(rows)


def build_phase13s_forbidden_action_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    checks = [
        ("No model training", "allow_model_training"),
        ("No model selection", "allow_model_selection"),
        ("No prediction generation", "allow_prediction_generation"),
        ("No feature importance", "allow_feature_importance"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No paper trading deployment", "allow_paper_trading_deployment"),
        ("No candidate promotion", "allow_candidate_promotion"),
        ("No final candidate change", "allow_final_candidate_change"),
    ]

    rows = [
        {
            "scope_item": label,
            "value": _bool_value(phase_config.get(key, True)),
            "passed": not _bool_value(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13s_phase13t_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13t_boundary", {})

    checks = [
        (
            "phase13t_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "readiness" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13t_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "model training execution"
            in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation"
            in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13t_may_audit_training_protocol",
            _bool_value(boundary.get("phase13t_may_audit_training_protocol", False)),
            _bool_value(boundary.get("phase13t_may_audit_training_protocol", False)),
        ),
        (
            "phase13t_may_train_model",
            _bool_value(boundary.get("phase13t_may_train_model", True)),
            not _bool_value(boundary.get("phase13t_may_train_model", True)),
        ),
        (
            "phase13t_may_select_model",
            _bool_value(boundary.get("phase13t_may_select_model", True)),
            not _bool_value(boundary.get("phase13t_may_select_model", True)),
        ),
        (
            "phase13t_may_generate_predictions",
            _bool_value(boundary.get("phase13t_may_generate_predictions", True)),
            not _bool_value(boundary.get("phase13t_may_generate_predictions", True)),
        ),
        (
            "phase13t_may_create_signal",
            _bool_value(boundary.get("phase13t_may_create_signal", True)),
            not _bool_value(boundary.get("phase13t_may_create_signal", True)),
        ),
        (
            "phase13t_may_run_backtest",
            _bool_value(boundary.get("phase13t_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13t_may_run_backtest", True)),
        ),
        (
            "phase13t_may_promote_candidate",
            _bool_value(boundary.get("phase13t_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13t_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [
            {"boundary_item": item, "value": value, "passed": passed}
            for item, value, passed in checks
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13s_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13r_result_check: pd.DataFrame,
    dataset_schema_profile: pd.DataFrame,
    dataset_requirement_check: pd.DataFrame,
    target_policy: pd.DataFrame,
    model_family_registry: pd.DataFrame,
    preprocessing_policy: pd.DataFrame,
    split_usage_policy: pd.DataFrame,
    metric_registry: pd.DataFrame,
    report_template_registry: pd.DataFrame,
    forbidden_action_check: pd.DataFrame,
    phase13t_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    allowed_models = (
        int(model_family_registry["allowed"].map(_bool_value).sum())
        if not model_family_registry.empty and "allowed" in model_family_registry.columns
        else 0
    )
    primary_metrics = (
        int(metric_registry["metric_group"].astype(str).eq("primary_metrics").sum())
        if not metric_registry.empty
        else 0
    )
    calibration_metrics = (
        int(metric_registry["metric_group"].astype(str).eq("calibration_metrics").sum())
        if not metric_registry.empty
        else 0
    )

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase13r_result_passed": bool(phase13r_result_check["passed"].all())
                if not phase13r_result_check.empty
                else False,
                "dataset_schema_profile_rows": int(len(dataset_schema_profile)),
                "dataset_requirements_passed": bool(
                    dataset_requirement_check["passed"].all()
                )
                if not dataset_requirement_check.empty
                else False,
                "target_policy_rows": int(len(target_policy)),
                "allowed_model_count": allowed_models,
                "preprocessing_policy_rows": int(len(preprocessing_policy)),
                "split_usage_policy_rows": int(len(split_usage_policy)),
                "primary_metric_count": primary_metrics,
                "calibration_metric_count": calibration_metrics,
                "report_template_rows": int(len(report_template_registry)),
                "forbidden_action_check_passed": bool(
                    forbidden_action_check["passed"].all()
                )
                if not forbidden_action_check.empty
                else False,
                "phase13t_boundary_passed": bool(
                    phase13t_boundary_check["passed"].all()
                )
                if not phase13t_boundary_check.empty
                else False,
                "model_training": False,
                "model_selection": False,
                "prediction_generation": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13s_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [_gate_row("Phase 13S summary exists", False, "No summary.")]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_spec_role",
            "ML model training pre-registration and baseline model design spec only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13R passed",
            bool(row["phase13r_result_passed"]),
            f"phase13r_result_passed={bool(row['phase13r_result_passed'])}",
        ),
        _gate_row(
            "Source reports are present",
            bool(row["source_reports_present"]),
            f"source_reports_present={bool(row['source_reports_present'])}",
        ),
        _gate_row(
            "Dataset schema profile exists",
            int(row["dataset_schema_profile_rows"]) > 0,
            f"dataset_schema_profile_rows={int(row['dataset_schema_profile_rows'])}",
        ),
        _gate_row(
            "Dataset requirements passed",
            bool(row["dataset_requirements_passed"]),
            f"dataset_requirements_passed="
            f"{bool(row['dataset_requirements_passed'])}",
        ),
        _gate_row(
            "Target policy exists",
            int(row["target_policy_rows"]) >= 2,
            f"target_policy_rows={int(row['target_policy_rows'])}",
        ),
        _gate_row(
            "Model family registry is sufficient",
            int(row["allowed_model_count"])
            >= int(gates.get("min_allowed_model_families", 4)),
            f"allowed_model_count={int(row['allowed_model_count'])}",
        ),
        _gate_row(
            "Preprocessing policy exists",
            int(row["preprocessing_policy_rows"]) > 0,
            f"preprocessing_policy_rows={int(row['preprocessing_policy_rows'])}",
        ),
        _gate_row(
            "Split usage policy exists",
            int(row["split_usage_policy_rows"]) > 0,
            f"split_usage_policy_rows={int(row['split_usage_policy_rows'])}",
        ),
        _gate_row(
            "Metric registry is sufficient",
            int(row["primary_metric_count"]) >= 3
            and int(row["calibration_metric_count"]) >= 1,
            f"primary_metrics={int(row['primary_metric_count'])}; "
            f"calibration_metrics={int(row['calibration_metric_count'])}",
        ),
        _gate_row(
            "Report templates exist",
            int(row["report_template_rows"]) > 0,
            f"report_template_rows={int(row['report_template_rows'])}",
        ),
        _gate_row(
            "Phase 13T boundary is readiness-only",
            bool(row["phase13t_boundary_passed"]),
            f"phase13t_boundary_passed={bool(row['phase13t_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks model/signal/backtest/promotion",
            bool(row["forbidden_action_check_passed"]),
            f"forbidden_action_check_passed="
            f"{bool(row['forbidden_action_check_passed'])}",
        ),
        _gate_row(
            "Spec role is correct",
            str(row["spec_role"]) == required_role,
            f"spec_role={row['spec_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13s_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — ML model training pre-registration spec passed"
        if all_passed
        else "Failed ML model training pre-registration spec"
    )
    interpretation = (
        "Phase 13S pre-registered model families, target usage, feature usage, "
        "preprocessing, split usage, metrics, calibration/confusion-matrix templates, "
        "and forbidden actions. It did not train models, select models, generate "
        "predictions, calculate feature importance, create signals, run backtests, "
        "deploy paper trading, promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13S found a dataset, target, model-family, metric, boundary, "
        "or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13S",
                "diagnostic": "ML model training pre-registration spec",
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
    *,
    title: str,
    sections: dict[str, pd.DataFrame],
    output_path: Path,
) -> None:
    lines = [f"# {title}", ""]

    for heading, frame in sections.items():
        lines.extend([f"## {heading}", frame.to_markdown(index=False), ""])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13s_ml_model_training_preregistration_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13s_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13s_source_report_check(phase_config)
    phase13r_result_check = build_phase13s_phase13r_result_check(phase_config)

    source_reports = phase_config.get("source_reports", {})
    dataset = _read_csv_if_exists(source_reports.get("repaired_dataset", ""))
    metadata = _read_csv_if_exists(source_reports.get("dataset_metadata", ""))

    dataset_schema_profile = build_phase13s_dataset_schema_profile(
        dataset=dataset,
        metadata=metadata,
    )
    dataset_requirement_check = build_phase13s_dataset_requirement_check(
        dataset=dataset,
        schema_profile=dataset_schema_profile,
        phase_config=phase_config,
    )
    target_policy = build_phase13s_target_policy(phase_config)
    model_family_registry = build_phase13s_model_family_registry(phase_config)
    preprocessing_policy = build_phase13s_preprocessing_policy(phase_config)
    split_usage_policy = build_phase13s_split_usage_policy(phase_config)
    metric_registry = build_phase13s_metric_registry(phase_config)
    report_template_registry = build_phase13s_report_template_registry(phase_config)
    forbidden_action_check = build_phase13s_forbidden_action_check(phase_config)
    phase13t_boundary_check = build_phase13s_phase13t_boundary_check(phase_config)

    summary = build_phase13s_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13r_result_check=phase13r_result_check,
        dataset_schema_profile=dataset_schema_profile,
        dataset_requirement_check=dataset_requirement_check,
        target_policy=target_policy,
        model_family_registry=model_family_registry,
        preprocessing_policy=preprocessing_policy,
        split_usage_policy=split_usage_policy,
        metric_registry=metric_registry,
        report_template_registry=report_template_registry,
        forbidden_action_check=forbidden_action_check,
        phase13t_boundary_check=phase13t_boundary_check,
    )
    gate_report = build_phase13s_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13s_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13r_result_check": phase13r_result_check,
        "dataset_schema_profile": dataset_schema_profile,
        "dataset_requirement_check": dataset_requirement_check,
        "target_policy": target_policy,
        "model_family_registry": model_family_registry,
        "preprocessing_policy": preprocessing_policy,
        "split_usage_policy": split_usage_policy,
        "metric_registry": metric_registry,
        "report_template_registry": report_template_registry,
        "forbidden_action_check": forbidden_action_check,
        "phase13t_boundary_check": phase13t_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13s_prereg_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13S — ML Model Training Pre-Registration Spec",
        sections={
            "Dataset Schema Profile": dataset_schema_profile,
            "Dataset Requirement Check": dataset_requirement_check,
            "Target Policy": target_policy,
            "Model Family Registry": model_family_registry,
            "Preprocessing Policy": preprocessing_policy,
            "Split Usage Policy": split_usage_policy,
            "Metric Registry": metric_registry,
            "Report Template Registry": report_template_registry,
            "Forbidden Action Check": forbidden_action_check,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13s_ml_model_training_preregistration_spec.md",
    )

    print("Wrote Phase 13S ML model training pre-registration reports.")
    return outputs


def build_phase13t_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("phase13s_reports", {}).items():
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


def build_phase13t_phase13s_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase13s_reports", {})
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
                "check": "Phase 13S conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13S gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13t_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for key, expected in expected_flags.items():
        actual = runtime_config.get(key, {}).get("enabled")
        passed = actual is expected
        rows.append(
            {
                "config_key": str(key),
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase13t_dataset_readiness_check(
    *,
    dataset_schema_profile: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    if dataset_schema_profile.empty:
        return pd.DataFrame(
            [
                {
                    "check": "Dataset schema profile exists",
                    "passed": False,
                    "detail": "missing",
                    "result": "Failed",
                }
            ]
        )

    row = dataset_schema_profile.iloc[0]

    checks = [
        (
            "Dataset label is technical + macro",
            str(row.get("dataset_label", ""))
            == str(thresholds.get("required_dataset_label", "")),
            f"dataset_label={row.get('dataset_label', '')}",
        ),
        (
            "Dataset has enough rows",
            int(row.get("rows", 0)) >= int(thresholds.get("min_rows", 1000)),
            f"rows={int(row.get('rows', 0))}",
        ),
        (
            "Dataset has enough value feature columns",
            int(row.get("value_feature_columns", 0))
            >= int(thresholds.get("min_value_feature_columns", 8)),
            f"value_feature_columns={int(row.get('value_feature_columns', 0))}",
        ),
    ]

    out = pd.DataFrame(
        [{"check": check, "passed": passed, "detail": detail} for check, passed, detail in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13t_training_protocol_check(
    *,
    model_family_registry: pd.DataFrame,
    metric_registry: pd.DataFrame,
    report_template_registry: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    allowed_models = (
        int(model_family_registry["allowed"].map(_bool_value).sum())
        if not model_family_registry.empty and "allowed" in model_family_registry.columns
        else 0
    )
    primary_metrics = (
        int(metric_registry["metric_group"].astype(str).eq("primary_metrics").sum())
        if not metric_registry.empty
        else 0
    )
    calibration_templates = (
        int(
            metric_registry["metric"]
            .astype(str)
            .str.contains("calibration", case=False, na=False)
            .sum()
        )
        if not metric_registry.empty and "metric" in metric_registry.columns
        else 0
    )
    confusion_templates = (
        int(
            report_template_registry["report_name"]
            .astype(str)
            .str.contains("confusion", case=False, na=False)
            .sum()
        )
        if not report_template_registry.empty
        and "report_name" in report_template_registry.columns
        else 0
    )

    checks = [
        (
            "Allowed model families are sufficient",
            allowed_models >= int(thresholds.get("min_allowed_model_families", 4)),
            f"allowed_model_count={allowed_models}",
        ),
        (
            "Primary metrics are sufficient",
            primary_metrics >= int(thresholds.get("min_primary_metrics", 3)),
            f"primary_metric_count={primary_metrics}",
        ),
        (
            "Calibration template exists",
            (not thresholds.get("require_calibration_template", True))
            or calibration_templates > 0,
            f"calibration_template_count={calibration_templates}",
        ),
        (
            "Confusion matrix template exists",
            (not thresholds.get("require_confusion_matrix_template", True))
            or confusion_templates > 0,
            f"confusion_template_count={confusion_templates}",
        ),
    ]

    out = pd.DataFrame(
        [{"check": check, "passed": passed, "detail": detail} for check, passed, detail in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13t_leakage_boundary_check(
    *,
    preprocessing_policy: pd.DataFrame,
    split_usage_policy: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    fit_scope = (
        str(preprocessing_policy.iloc[0].get("fit_scope", ""))
        if not preprocessing_policy.empty
        else ""
    )
    holdout_policy = (
        str(split_usage_policy.iloc[0].get("holdout_split", ""))
        if not split_usage_policy.empty
        else ""
    )
    walk_forward_now = (
        _bool_value(split_usage_policy.iloc[0].get("walk_forward_now", True))
        if not split_usage_policy.empty
        else True
    )

    checks = [
        (
            "Preprocessing is train-only",
            (not thresholds.get("require_train_only_preprocessing", True))
            or "train" in fit_scope.lower(),
            f"fit_scope={fit_scope}",
        ),
        (
            "Holdout remains locked",
            (not thresholds.get("require_holdout_locked", True))
            or (
                "untouched" in holdout_policy.lower()
                and "no model selection" in holdout_policy.lower()
            ),
            f"holdout_split={holdout_policy}",
        ),
        (
            "Walk-forward execution is not enabled now",
            not walk_forward_now,
            f"walk_forward_now={walk_forward_now}",
        ),
    ]

    out = pd.DataFrame(
        [{"check": check, "passed": passed, "detail": detail} for check, passed, detail in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13t_forbidden_output_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for path in _as_list(phase_config.get("forbidden_output_paths")):
        report_path = Path(str(path))
        rows.append(
            {
                "path": str(report_path),
                "present": report_path.exists(),
                "passed": not report_path.exists(),
                "result": "Passed" if not report_path.exists() else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase13t_phase13u_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13u_boundary", {})

    checks = [
        (
            "phase13u_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "registered" in str(boundary.get("allowed_next_step", "")).lower()
            and "training" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13u_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "signal creation" in str(boundary.get("forbidden_next_step", "")).lower()
            and "strategy backtest"
            in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13u_may_train_registered_models",
            _bool_value(boundary.get("phase13u_may_train_registered_models", False)),
            _bool_value(boundary.get("phase13u_may_train_registered_models", False)),
        ),
        (
            "phase13u_may_generate_holdout_predictions",
            _bool_value(boundary.get("phase13u_may_generate_holdout_predictions", True)),
            not _bool_value(
                boundary.get("phase13u_may_generate_holdout_predictions", True)
            ),
        ),
        (
            "phase13u_may_create_signal",
            _bool_value(boundary.get("phase13u_may_create_signal", True)),
            not _bool_value(boundary.get("phase13u_may_create_signal", True)),
        ),
        (
            "phase13u_may_run_backtest",
            _bool_value(boundary.get("phase13u_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13u_may_run_backtest", True)),
        ),
        (
            "phase13u_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13u_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13u_may_deploy_paper_trading", True)),
        ),
        (
            "phase13u_may_promote_candidate",
            _bool_value(boundary.get("phase13u_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13u_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [
            {"boundary_item": item, "value": value, "passed": passed}
            for item, value, passed in checks
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13t_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No model training", "allow_model_training"),
        ("No model selection", "allow_model_selection"),
        ("No prediction generation", "allow_prediction_generation"),
        ("No feature importance", "allow_feature_importance"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No paper trading deployment", "allow_paper_trading_deployment"),
        ("No candidate promotion", "allow_candidate_promotion"),
        ("No final candidate change", "allow_final_candidate_change"),
    ]

    rows = [
        {
            "scope_item": label,
            "value": _bool_value(phase_config.get(key, True)),
            "passed": not _bool_value(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13t_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13s_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    dataset_readiness_check: pd.DataFrame,
    training_protocol_check: pd.DataFrame,
    leakage_boundary_check: pd.DataFrame,
    forbidden_output_check: pd.DataFrame,
    phase13u_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13s_reports_present": bool(
                    report_inventory_check["present"].all()
                )
                if not report_inventory_check.empty
                else False,
                "phase13s_result_passed": bool(phase13s_result_check["passed"].all())
                if not phase13s_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "dataset_readiness_passed": bool(
                    dataset_readiness_check["passed"].all()
                )
                if not dataset_readiness_check.empty
                else False,
                "training_protocol_passed": bool(
                    training_protocol_check["passed"].all()
                )
                if not training_protocol_check.empty
                else False,
                "leakage_boundary_passed": bool(
                    leakage_boundary_check["passed"].all()
                )
                if not leakage_boundary_check.empty
                else False,
                "forbidden_outputs_absent": bool(forbidden_output_check["passed"].all())
                if not forbidden_output_check.empty
                else False,
                "phase13u_boundary_passed": bool(
                    phase13u_boundary_check["passed"].all()
                )
                if not phase13u_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "model_training": False,
                "model_selection": False,
                "prediction_generation": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13t_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(
            [_gate_row("Phase 13T summary exists", False, "No summary.")]
        )

    row = summary.iloc[0]
    required_role = str(
        phase_config.get("gates", {}).get(
            "required_audit_role",
            "ML training readiness and leakage boundary audit only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13S reports are present",
            bool(row["phase13s_reports_present"]),
            f"phase13s_reports_present={bool(row['phase13s_reports_present'])}",
        ),
        _gate_row(
            "Phase 13S conclusion and gates passed",
            bool(row["phase13s_result_passed"]),
            f"phase13s_result_passed={bool(row['phase13s_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Dataset readiness passed",
            bool(row["dataset_readiness_passed"]),
            f"dataset_readiness_passed={bool(row['dataset_readiness_passed'])}",
        ),
        _gate_row(
            "Training protocol completeness passed",
            bool(row["training_protocol_passed"]),
            f"training_protocol_passed={bool(row['training_protocol_passed'])}",
        ),
        _gate_row(
            "Leakage boundary passed",
            bool(row["leakage_boundary_passed"]),
            f"leakage_boundary_passed={bool(row['leakage_boundary_passed'])}",
        ),
        _gate_row(
            "Forbidden outputs are absent",
            bool(row["forbidden_outputs_absent"]),
            f"forbidden_outputs_absent={bool(row['forbidden_outputs_absent'])}",
        ),
        _gate_row(
            "Phase 13U boundary is registered-training-only",
            bool(row["phase13u_boundary_passed"]),
            f"phase13u_boundary_passed={bool(row['phase13u_boundary_passed'])}",
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


def build_phase13t_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — ML training readiness/leakage audit passed"
        if all_passed
        else "Failed ML training readiness/leakage audit"
    )
    interpretation = (
        "Phase 13T audited dataset readiness, model-training protocol completeness, "
        "train-only preprocessing controls, holdout lockout, forbidden outputs, and "
        "Phase 13U boundaries. It did not train models, select models, generate "
        "predictions, calculate feature importance, create signals, run backtests, "
        "deploy paper trading, promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13T found a dataset, protocol, leakage, forbidden-output, "
        "boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13T",
                "diagnostic": "ML training readiness/leakage audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def save_phase13t_ml_training_readiness_leakage_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13t_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = phase_config.get("phase13s_reports", {})
    thresholds = phase_config.get("readiness_thresholds", {})

    report_inventory_check = build_phase13t_report_inventory_check(phase_config)
    phase13s_result_check = build_phase13t_phase13s_result_check(phase_config)
    config_flag_check = build_phase13t_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )

    dataset_schema_profile = _read_csv_if_exists(
        reports.get("dataset_schema_profile", "")
    )
    model_family_registry = _read_csv_if_exists(
        reports.get("model_family_registry", "")
    )
    metric_registry = _read_csv_if_exists(reports.get("metric_registry", ""))
    report_template_registry = _read_csv_if_exists(
        reports.get("report_template_registry", "")
    )
    preprocessing_policy = _read_csv_if_exists(
        reports.get("preprocessing_policy", "")
    )
    split_usage_policy = _read_csv_if_exists(reports.get("split_usage_policy", ""))

    dataset_readiness_check = build_phase13t_dataset_readiness_check(
        dataset_schema_profile=dataset_schema_profile,
        thresholds=thresholds,
    )
    training_protocol_check = build_phase13t_training_protocol_check(
        model_family_registry=model_family_registry,
        metric_registry=metric_registry,
        report_template_registry=report_template_registry,
        thresholds=thresholds,
    )
    leakage_boundary_check = build_phase13t_leakage_boundary_check(
        preprocessing_policy=preprocessing_policy,
        split_usage_policy=split_usage_policy,
        thresholds=thresholds,
    )
    forbidden_output_check = build_phase13t_forbidden_output_check(phase_config)
    phase13u_boundary_check = build_phase13t_phase13u_boundary_check(phase_config)
    scope_boundary_check = build_phase13t_scope_boundary_check(phase_config)

    summary = build_phase13t_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13s_result_check=phase13s_result_check,
        config_flag_check=config_flag_check,
        dataset_readiness_check=dataset_readiness_check,
        training_protocol_check=training_protocol_check,
        leakage_boundary_check=leakage_boundary_check,
        forbidden_output_check=forbidden_output_check,
        phase13u_boundary_check=phase13u_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13t_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13t_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13s_result_check": phase13s_result_check,
        "config_flag_check": config_flag_check,
        "dataset_readiness_check": dataset_readiness_check,
        "training_protocol_check": training_protocol_check,
        "leakage_boundary_check": leakage_boundary_check,
        "forbidden_output_check": forbidden_output_check,
        "phase13u_boundary_check": phase13u_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13t_readiness_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13T — ML Training Readiness / Leakage Audit",
        sections={
            "Dataset Readiness Check": dataset_readiness_check,
            "Training Protocol Check": training_protocol_check,
            "Leakage Boundary Check": leakage_boundary_check,
            "Forbidden Output Check": forbidden_output_check,
            "Phase 13U Boundary Check": phase13u_boundary_check,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13t_ml_training_readiness_leakage_audit.md",
    )

    print("Wrote Phase 13T ML training readiness/leakage audit reports.")
    return outputs