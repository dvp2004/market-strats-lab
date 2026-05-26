from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE13E_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Technical and macro feature-contract schema design spec only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13D",
    "proposed_next_phase": "Phase 13F",
    "allow_feature_ingestion": False,
    "allow_feature_calculation": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "universal_panel_schema": [],
    "technical_feature_schema": [],
    "macro_feature_schema": [],
    "transform_policy": [],
    "missingness_policy": [],
    "feature_state_policy": {},
    "visual_report_templates": [],
    "phase13f_boundary": {},
    "gates": {
        "require_phase13d_passed": True,
        "require_universal_panel_schema": True,
        "min_universal_columns": 10,
        "require_technical_feature_schema": True,
        "min_technical_features": 4,
        "require_macro_feature_schema": True,
        "min_macro_features": 4,
        "require_transform_policy": True,
        "min_transform_policies": 6,
        "require_missingness_policy": True,
        "min_missingness_policies": 5,
        "require_feature_state_policy": True,
        "require_visual_report_templates": True,
        "min_visual_templates": 5,
        "require_ml_principles_present": True,
        "require_phase13f_boundary_template_audit_only": True,
        "require_no_feature_ingestion": True,
        "require_no_feature_calculation": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_spec_role": (
            "Technical and macro feature-contract schema design spec only"
        ),
    },
}


DEFAULT_PHASE13F_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Feature schema readiness and visual report template audit only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13E",
    "proposed_next_phase": "Phase 13G",
    "allow_feature_ingestion": False,
    "allow_feature_calculation": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "phase13e_reports": {},
    "readiness_claims": {},
    "phase13g_boundary": {},
    "gates": {
        "require_phase13e_reports_present": True,
        "require_phase13e_conclusion_passed": True,
        "require_phase13e_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_readiness_claims_locked": True,
        "require_schema_coverage": True,
        "require_visual_templates_ready": True,
        "require_ml_policy_ready": True,
        "require_phase13g_boundary_prereg_only": True,
        "require_no_feature_ingestion": True,
        "require_no_feature_calculation": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_audit_role": (
            "Feature schema readiness and visual report template audit only"
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


def _get_phase13e_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13E_CONFIG,
        config.get("phase13e_technical_macro_feature_schema_design_spec", {}),
    )


def _get_phase13f_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13F_CONFIG,
        config.get("phase13f_feature_schema_readiness_visual_template_audit", {}),
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


def build_phase13e_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
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


def build_phase13e_phase13d_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13d_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13d_gate_report", ""))

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

    rows = [
        {
            "check": "Phase 13D conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 13D gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13e_universal_panel_schema(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get("universal_panel_schema")):
        rows.append(
            {
                "column_name": str(item.get("column_name", "")),
                "dtype": str(item.get("dtype", "")),
                "required": _bool_value(item.get("required", False)),
                "description": str(item.get("description", "")),
            }
        )
    return pd.DataFrame(rows)


def build_phase13e_feature_schema(
    phase_config: dict[str, Any],
    schema_key: str,
) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get(schema_key)):
        rows.append(
            {
                "feature_id": str(item.get("feature_id", "")),
                "family_id": str(item.get("family_id", "")),
                "source_basis": str(item.get("source_basis", "")),
                "raw_inputs": _join_list(item.get("raw_inputs")),
                "transform_type": str(item.get("transform_type", "")),
                "timestamp_policy": str(item.get("timestamp_policy", "")),
                "lag_policy": str(item.get("lag_policy", "")),
                "revision_policy": str(item.get("revision_policy", "")),
                "missingness_policy": str(item.get("missingness_policy", "")),
                "allowed_states": _join_list(item.get("allowed_states")),
                "ml_feature_engineering_role": str(
                    item.get("ml_feature_engineering_role", "")
                ),
                "calculate_now": _bool_value(item.get("calculate_now", True)),
            }
        )
    return pd.DataFrame(rows)


def build_phase13e_transform_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get("transform_policy")):
        rows.append(
            {
                "transform_id": str(item.get("transform_id", "")),
                "policy": str(item.get("policy", "")),
                "ml_principle": str(item.get("ml_principle", "")),
                "required": _bool_value(item.get("required", False)),
            }
        )
    return pd.DataFrame(rows)


def build_phase13e_missingness_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get("missingness_policy")):
        rows.append(
            {
                "missingness_id": str(item.get("missingness_id", "")),
                "policy": str(item.get("policy", "")),
                "required": _bool_value(item.get("required", False)),
            }
        )
    return pd.DataFrame(rows)


def build_phase13e_feature_state_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    policy = phase_config.get("feature_state_policy", {})
    return pd.DataFrame(
        [
            {
                "allowed_feature_states": _join_list(
                    policy.get("allowed_feature_states")
                ),
                "state_direction_required": _bool_value(
                    policy.get("state_direction_required", False)
                ),
                "state_reason_required": _bool_value(
                    policy.get("state_reason_required", False)
                ),
                "no_state_may_directly_create_trade": _bool_value(
                    policy.get("no_state_may_directly_create_trade", False)
                ),
                "no_state_may_be_tuned_on_returns_now": _bool_value(
                    policy.get("no_state_may_be_tuned_on_returns_now", False)
                ),
            }
        ]
    )


def build_phase13e_visual_report_templates(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get("visual_report_templates")):
        rows.append(
            {
                "template_id": str(item.get("template_id", "")),
                "purpose": str(item.get("purpose", "")),
                "required_columns": _join_list(item.get("required_columns")),
                "calculate_now": _bool_value(item.get("calculate_now", True)),
            }
        )
    return pd.DataFrame(rows)


def build_phase13e_phase13f_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13f_boundary", {})
    checks = [
        (
            "phase13f_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "template audit" in str(boundary.get("allowed_next_step", "")).lower()
            or "readiness" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13f_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            (
                "feature ingestion"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "model training"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy backtest"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        ),
        (
            "phase13f_may_audit_schema",
            _bool_value(boundary.get("phase13f_may_audit_schema", False)),
            _bool_value(boundary.get("phase13f_may_audit_schema", False)),
        ),
        (
            "phase13f_may_audit_visual_templates",
            _bool_value(boundary.get("phase13f_may_audit_visual_templates", False)),
            _bool_value(boundary.get("phase13f_may_audit_visual_templates", False)),
        ),
        (
            "phase13f_may_audit_ml_feature_engineering_policy",
            _bool_value(
                boundary.get("phase13f_may_audit_ml_feature_engineering_policy", False)
            ),
            _bool_value(
                boundary.get("phase13f_may_audit_ml_feature_engineering_policy", False)
            ),
        ),
        (
            "phase13f_may_ingest_features",
            _bool_value(boundary.get("phase13f_may_ingest_features", True)),
            not _bool_value(boundary.get("phase13f_may_ingest_features", True)),
        ),
        (
            "phase13f_may_calculate_features",
            _bool_value(boundary.get("phase13f_may_calculate_features", True)),
            not _bool_value(boundary.get("phase13f_may_calculate_features", True)),
        ),
        (
            "phase13f_may_train_model",
            _bool_value(boundary.get("phase13f_may_train_model", True)),
            not _bool_value(boundary.get("phase13f_may_train_model", True)),
        ),
        (
            "phase13f_may_create_signal",
            _bool_value(boundary.get("phase13f_may_create_signal", True)),
            not _bool_value(boundary.get("phase13f_may_create_signal", True)),
        ),
        (
            "phase13f_may_run_backtest",
            _bool_value(boundary.get("phase13f_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13f_may_run_backtest", True)),
        ),
        (
            "phase13f_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13f_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13f_may_deploy_paper_trading", True)),
        ),
        (
            "phase13f_may_promote_candidate",
            _bool_value(boundary.get("phase13f_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13f_may_promote_candidate", True)),
        ),
    ]
    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No feature ingestion", "allow_feature_ingestion"),
        ("No feature calculation", "allow_feature_calculation"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No model training", "allow_model_training"),
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


def build_phase13e_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13d_result_check: pd.DataFrame,
    universal_panel_schema: pd.DataFrame,
    technical_feature_schema: pd.DataFrame,
    macro_feature_schema: pd.DataFrame,
    transform_policy: pd.DataFrame,
    missingness_policy: pd.DataFrame,
    feature_state_policy: pd.DataFrame,
    visual_report_templates: pd.DataFrame,
    phase13f_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    ml_policy_text = " ".join(transform_policy.get("ml_principle", pd.Series(dtype=str)).astype(str))
    ml_principles_present = (
        "leakage" in ml_policy_text.lower()
        and "overfitting" in ml_policy_text.lower()
        and "preprocessing" in ml_policy_text.lower()
    )
    feature_state_clean = (
        not feature_state_policy.empty
        and _bool_value(feature_state_policy.iloc[0]["state_direction_required"])
        and _bool_value(feature_state_policy.iloc[0]["state_reason_required"])
        and _bool_value(feature_state_policy.iloc[0]["no_state_may_directly_create_trade"])
        and _bool_value(feature_state_policy.iloc[0]["no_state_may_be_tuned_on_returns_now"])
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
                "phase13d_result_passed": bool(phase13d_result_check["passed"].all())
                if not phase13d_result_check.empty
                else False,
                "universal_column_count": int(len(universal_panel_schema)),
                "universal_required": bool(universal_panel_schema["required"].map(_bool_value).all())
                if not universal_panel_schema.empty
                else False,
                "technical_feature_count": int(len(technical_feature_schema)),
                "technical_calculate_now_false": bool(
                    technical_feature_schema["calculate_now"].map(_bool_value).eq(False).all()
                )
                if not technical_feature_schema.empty
                else False,
                "macro_feature_count": int(len(macro_feature_schema)),
                "macro_calculate_now_false": bool(
                    macro_feature_schema["calculate_now"].map(_bool_value).eq(False).all()
                )
                if not macro_feature_schema.empty
                else False,
                "transform_policy_count": int(len(transform_policy)),
                "transform_policy_required": bool(transform_policy["required"].map(_bool_value).all())
                if not transform_policy.empty
                else False,
                "missingness_policy_count": int(len(missingness_policy)),
                "missingness_policy_required": bool(missingness_policy["required"].map(_bool_value).all())
                if not missingness_policy.empty
                else False,
                "feature_state_policy_clean": feature_state_clean,
                "visual_template_count": int(len(visual_report_templates)),
                "visual_templates_not_calculated": bool(
                    visual_report_templates["calculate_now"].map(_bool_value).eq(False).all()
                )
                if not visual_report_templates.empty
                else False,
                "ml_principles_present": ml_principles_present,
                "phase13f_boundary_passed": bool(phase13f_boundary_check["passed"].all())
                if not phase13f_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "feature_ingestion": False,
                "feature_calculation": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "model_training": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13e_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13E summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_spec_role",
            "Technical and macro feature-contract schema design spec only",
        )
    )
    rows = [
        _gate_row(
            "Phase 13D passed",
            (not gates.get("require_phase13d_passed", True)) or bool(row["phase13d_result_passed"]),
            f"phase13d_result_passed={bool(row['phase13d_result_passed'])}",
        ),
        _gate_row(
            "Universal panel schema is complete enough",
            (not gates.get("require_universal_panel_schema", True))
            or (
                int(row["universal_column_count"]) >= int(gates.get("min_universal_columns", 10))
                and bool(row["universal_required"])
            ),
            f"universal_column_count={int(row['universal_column_count'])}",
        ),
        _gate_row(
            "Technical feature schema is complete enough",
            (not gates.get("require_technical_feature_schema", True))
            or (
                int(row["technical_feature_count"]) >= int(gates.get("min_technical_features", 4))
                and bool(row["technical_calculate_now_false"])
            ),
            f"technical_feature_count={int(row['technical_feature_count'])}",
        ),
        _gate_row(
            "Macro feature schema is complete enough",
            (not gates.get("require_macro_feature_schema", True))
            or (
                int(row["macro_feature_count"]) >= int(gates.get("min_macro_features", 4))
                and bool(row["macro_calculate_now_false"])
            ),
            f"macro_feature_count={int(row['macro_feature_count'])}",
        ),
        _gate_row(
            "Transform policy includes ML discipline",
            (not gates.get("require_transform_policy", True))
            or (
                int(row["transform_policy_count"]) >= int(gates.get("min_transform_policies", 6))
                and bool(row["transform_policy_required"])
                and bool(row["ml_principles_present"])
            ),
            (
                f"transform_policy_count={int(row['transform_policy_count'])}; "
                f"ml_principles_present={bool(row['ml_principles_present'])}"
            ),
        ),
        _gate_row(
            "Missingness policy is complete enough",
            (not gates.get("require_missingness_policy", True))
            or (
                int(row["missingness_policy_count"]) >= int(gates.get("min_missingness_policies", 5))
                and bool(row["missingness_policy_required"])
            ),
            f"missingness_policy_count={int(row['missingness_policy_count'])}",
        ),
        _gate_row(
            "Feature-state policy is clean",
            (not gates.get("require_feature_state_policy", True))
            or bool(row["feature_state_policy_clean"]),
            f"feature_state_policy_clean={bool(row['feature_state_policy_clean'])}",
        ),
        _gate_row(
            "Visual report templates are documented",
            (not gates.get("require_visual_report_templates", True))
            or (
                int(row["visual_template_count"]) >= int(gates.get("min_visual_templates", 5))
                and bool(row["visual_templates_not_calculated"])
            ),
            f"visual_template_count={int(row['visual_template_count'])}",
        ),
        _gate_row(
            "Phase 13F boundary is template-audit only",
            (not gates.get("require_phase13f_boundary_template_audit_only", True))
            or bool(row["phase13f_boundary_passed"]),
            f"phase13f_boundary_passed={bool(row['phase13f_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks feature/model/signal/backtest/paper-trading/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
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


def build_phase13e_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — technical and macro feature schema design spec passed"
        if all_passed
        else "Failed technical and macro feature schema design spec"
    )
    interpretation = (
        "Phase 13E defined technical and macro feature schemas, timestamp fields, "
        "lag/revision policies, missingness handling, transform policy, ML feature-"
        "engineering discipline, feature-state columns, and visual report templates. "
        "It did not ingest or calculate features, create signals, run backtests, train "
        "models, deploy paper trading, promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13E found a schema, ML-policy, visual-template, boundary, or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 13E",
                "diagnostic": "Technical and macro feature schema design spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase13e_markdown(
    *,
    source_report_check: pd.DataFrame,
    phase13d_result_check: pd.DataFrame,
    universal_panel_schema: pd.DataFrame,
    technical_feature_schema: pd.DataFrame,
    macro_feature_schema: pd.DataFrame,
    transform_policy: pd.DataFrame,
    missingness_policy: pd.DataFrame,
    feature_state_policy: pd.DataFrame,
    visual_report_templates: pd.DataFrame,
    phase13f_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 13E — Technical and Macro Feature Schema Design Spec",
        "",
        "This phase defines schemas and templates only. It does not ingest or calculate "
        "features, create signals, run backtests, train models, deploy paper trading, "
        "promote a candidate, or change the final candidate.",
        "",
        "## Source Report Check",
        source_report_check.to_markdown(index=False),
        "",
        "## Phase 13D Result Check",
        phase13d_result_check.to_markdown(index=False),
        "",
        "## Universal Panel Schema",
        universal_panel_schema.to_markdown(index=False),
        "",
        "## Technical Feature Schema",
        technical_feature_schema.to_markdown(index=False),
        "",
        "## Macro Feature Schema",
        macro_feature_schema.to_markdown(index=False),
        "",
        "## Transform Policy / ML Feature Engineering Discipline",
        transform_policy.to_markdown(index=False),
        "",
        "## Missingness Policy",
        missingness_policy.to_markdown(index=False),
        "",
        "## Feature State Policy",
        feature_state_policy.to_markdown(index=False),
        "",
        "## Visual Report Templates",
        visual_report_templates.to_markdown(index=False),
        "",
        "## Phase 13F Boundary Check",
        phase13f_boundary_check.to_markdown(index=False),
        "",
        "## Scope Boundary Check",
        scope_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        conclusion.to_markdown(index=False),
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13e_technical_macro_feature_schema_design_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13e_config(config)
    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13e_source_report_check(phase_config)
    phase13d_result_check = build_phase13e_phase13d_result_check(phase_config)
    universal_panel_schema = build_phase13e_universal_panel_schema(phase_config)
    technical_feature_schema = build_phase13e_feature_schema(
        phase_config,
        "technical_feature_schema",
    )
    macro_feature_schema = build_phase13e_feature_schema(
        phase_config,
        "macro_feature_schema",
    )
    transform_policy = build_phase13e_transform_policy(phase_config)
    missingness_policy = build_phase13e_missingness_policy(phase_config)
    feature_state_policy = build_phase13e_feature_state_policy(phase_config)
    visual_report_templates = build_phase13e_visual_report_templates(phase_config)
    phase13f_boundary_check = build_phase13e_phase13f_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13e_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13d_result_check=phase13d_result_check,
        universal_panel_schema=universal_panel_schema,
        technical_feature_schema=technical_feature_schema,
        macro_feature_schema=macro_feature_schema,
        transform_policy=transform_policy,
        missingness_policy=missingness_policy,
        feature_state_policy=feature_state_policy,
        visual_report_templates=visual_report_templates,
        phase13f_boundary_check=phase13f_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13e_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13e_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13d_result_check": phase13d_result_check,
        "universal_panel_schema": universal_panel_schema,
        "technical_feature_schema": technical_feature_schema,
        "macro_feature_schema": macro_feature_schema,
        "transform_policy": transform_policy,
        "missingness_policy": missingness_policy,
        "feature_state_policy": feature_state_policy,
        "visual_report_templates": visual_report_templates,
        "phase13f_boundary_check": phase13f_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13e_schema_{name}.csv", index=False)

    write_phase13e_markdown(
        source_report_check=source_report_check,
        phase13d_result_check=phase13d_result_check,
        universal_panel_schema=universal_panel_schema,
        technical_feature_schema=technical_feature_schema,
        macro_feature_schema=macro_feature_schema,
        transform_policy=transform_policy,
        missingness_policy=missingness_policy,
        feature_state_policy=feature_state_policy,
        visual_report_templates=visual_report_templates,
        phase13f_boundary_check=phase13f_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase13e_technical_macro_feature_schema_design_spec.md",
    )

    print("Wrote Phase 13E technical/macro feature schema design reports.")
    return outputs


def build_phase13f_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for report_key, path in phase_config.get("phase13e_reports", {}).items():
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


def build_phase13f_phase13e_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase13e_reports", {})
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
    rows = [
        {
            "check": "Phase 13E conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 13E gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13f_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, Any],
) -> pd.DataFrame:
    rows = []
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


def build_phase13f_readiness_claims_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    claims = phase_config.get("readiness_claims", {})
    expected_true = [
        "schema_defined",
        "technical_schema_defined",
        "macro_schema_defined",
        "timestamp_fields_defined",
        "lag_revision_policy_defined",
        "missingness_policy_defined",
        "transform_policy_defined",
        "ml_feature_engineering_policy_defined",
        "visual_templates_defined",
    ]
    expected_false = [
        "feature_ingested",
        "feature_calculated",
        "signal_created",
        "backtest_run",
        "model_trained",
        "paper_trading_deployed",
        "candidate_promoted",
        "final_candidate_changed",
    ]
    rows = []
    for claim in expected_true:
        actual = _bool_value(claims.get(claim, False))
        rows.append({"claim": claim, "expected": True, "actual": actual, "passed": actual})
    for claim in expected_false:
        actual = _bool_value(claims.get(claim, True))
        rows.append({"claim": claim, "expected": False, "actual": actual, "passed": not actual})
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13f_schema_coverage_check(
    *,
    universal_panel_schema: pd.DataFrame,
    technical_feature_schema: pd.DataFrame,
    macro_feature_schema: pd.DataFrame,
    transform_policy: pd.DataFrame,
    missingness_policy: pd.DataFrame,
) -> pd.DataFrame:
    universal_columns = (
        set(universal_panel_schema["column_name"].astype(str).tolist())
        if not universal_panel_schema.empty
        else set()
    )
    required_universal = {
        "as_of_date",
        "observation_date",
        "release_date",
        "availability_date",
        "decision_date",
        "family_id",
        "feature_id",
        "feature_state",
        "missingness_state",
        "leakage_flag",
    }
    rows = [
        {
            "check": "Required universal timestamp/state columns present",
            "passed": required_universal.issubset(universal_columns),
            "detail": "missing=" + "; ".join(sorted(required_universal - universal_columns)),
        },
        {
            "check": "Technical schema has at least four non-calculated features",
            "passed": len(technical_feature_schema) >= 4
            and bool(technical_feature_schema["calculate_now"].map(_bool_value).eq(False).all()),
            "detail": f"technical_features={len(technical_feature_schema)}",
        },
        {
            "check": "Macro schema has at least four non-calculated features",
            "passed": len(macro_feature_schema) >= 4
            and bool(macro_feature_schema["calculate_now"].map(_bool_value).eq(False).all()),
            "detail": f"macro_features={len(macro_feature_schema)}",
        },
        {
            "check": "Transform policy present and required",
            "passed": len(transform_policy) >= 6
            and bool(transform_policy["required"].map(_bool_value).all()),
            "detail": f"transform_rows={len(transform_policy)}",
        },
        {
            "check": "Missingness policy present and required",
            "passed": len(missingness_policy) >= 5
            and bool(missingness_policy["required"].map(_bool_value).all()),
            "detail": f"missingness_rows={len(missingness_policy)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13f_visual_template_check(
    visual_report_templates: pd.DataFrame,
) -> pd.DataFrame:
    required_templates = {
        "feature_availability_heatmap",
        "feature_state_timeline",
        "leakage_audit_panel",
        "model_feature_matrix_preview",
        "decision_rationale_template",
    }
    template_ids = (
        set(visual_report_templates["template_id"].astype(str).tolist())
        if not visual_report_templates.empty
        else set()
    )
    rows = [
        {
            "check": "Required visual templates present",
            "passed": required_templates.issubset(template_ids),
            "detail": "missing=" + "; ".join(sorted(required_templates - template_ids)),
        },
        {
            "check": "Visual templates are not calculated now",
            "passed": bool(visual_report_templates["calculate_now"].map(_bool_value).eq(False).all())
            if not visual_report_templates.empty
            else False,
            "detail": f"template_rows={len(visual_report_templates)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13f_ml_policy_check(transform_policy: pd.DataFrame) -> pd.DataFrame:
    joined = " ".join(transform_policy.get("ml_principle", pd.Series(dtype=str)).astype(str))
    checks = [
        ("Train-test leakage principle present", "leakage" in joined.lower()),
        ("Overfitting/data-snooping principle present", "overfitting" in joined.lower()),
        ("Preprocessing contract principle present", "preprocessing" in joined.lower()),
        ("Target leakage prevention present", "target leakage" in joined.lower()),
    ]
    out = pd.DataFrame(
        [{"check": name, "passed": passed, "result": "Passed" if passed else "Failed"} for name, passed in checks]
    )
    return out


def build_phase13f_phase13g_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13g_boundary", {})
    checks = [
        (
            "phase13g_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "pre-registration spec" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13g_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            (
                "direct feature calculation"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "model training"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy backtest"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        ),
        (
            "phase13g_may_preregister_feature_calculation",
            _bool_value(boundary.get("phase13g_may_preregister_feature_calculation", False)),
            _bool_value(boundary.get("phase13g_may_preregister_feature_calculation", False)),
        ),
        (
            "phase13g_may_calculate_features_immediately",
            _bool_value(boundary.get("phase13g_may_calculate_features_immediately", True)),
            not _bool_value(boundary.get("phase13g_may_calculate_features_immediately", True)),
        ),
        (
            "phase13g_may_train_model",
            _bool_value(boundary.get("phase13g_may_train_model", True)),
            not _bool_value(boundary.get("phase13g_may_train_model", True)),
        ),
        (
            "phase13g_may_create_signal",
            _bool_value(boundary.get("phase13g_may_create_signal", True)),
            not _bool_value(boundary.get("phase13g_may_create_signal", True)),
        ),
        (
            "phase13g_may_run_backtest",
            _bool_value(boundary.get("phase13g_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13g_may_run_backtest", True)),
        ),
        (
            "phase13g_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13g_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13g_may_deploy_paper_trading", True)),
        ),
        (
            "phase13g_may_promote_candidate",
            _bool_value(boundary.get("phase13g_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13g_may_promote_candidate", True)),
        ),
    ]
    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13f_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13e_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    readiness_claims_check: pd.DataFrame,
    schema_coverage_check: pd.DataFrame,
    visual_template_check: pd.DataFrame,
    ml_policy_check: pd.DataFrame,
    phase13g_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13e_reports_present": bool(report_inventory_check["present"].all())
                if not report_inventory_check.empty
                else False,
                "phase13e_result_passed": bool(phase13e_result_check["passed"].all())
                if not phase13e_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "readiness_claims_locked": bool(readiness_claims_check["passed"].all())
                if not readiness_claims_check.empty
                else False,
                "schema_coverage_passed": bool(schema_coverage_check["passed"].all())
                if not schema_coverage_check.empty
                else False,
                "visual_templates_ready": bool(visual_template_check["passed"].all())
                if not visual_template_check.empty
                else False,
                "ml_policy_ready": bool(ml_policy_check["passed"].all())
                if not ml_policy_check.empty
                else False,
                "phase13g_boundary_passed": bool(phase13g_boundary_check["passed"].all())
                if not phase13g_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "feature_ingestion": False,
                "feature_calculation": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "model_training": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13f_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13F summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_audit_role",
            "Feature schema readiness and visual report template audit only",
        )
    )
    rows = [
        _gate_row(
            "Phase 13E reports are present",
            (not gates.get("require_phase13e_reports_present", True))
            or bool(row["phase13e_reports_present"]),
            f"phase13e_reports_present={bool(row['phase13e_reports_present'])}",
        ),
        _gate_row(
            "Phase 13E conclusion and gates passed",
            (
                (not gates.get("require_phase13e_conclusion_passed", True))
                or bool(row["phase13e_result_passed"])
            )
            and (
                (not gates.get("require_phase13e_gate_report_passed", True))
                or bool(row["phase13e_result_passed"])
            ),
            f"phase13e_result_passed={bool(row['phase13e_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            (not gates.get("require_config_flags_clean_for_run", True))
            or bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Readiness claims are locked",
            (not gates.get("require_readiness_claims_locked", True))
            or bool(row["readiness_claims_locked"]),
            f"readiness_claims_locked={bool(row['readiness_claims_locked'])}",
        ),
        _gate_row(
            "Schema coverage passed",
            (not gates.get("require_schema_coverage", True))
            or bool(row["schema_coverage_passed"]),
            f"schema_coverage_passed={bool(row['schema_coverage_passed'])}",
        ),
        _gate_row(
            "Visual templates are ready",
            (not gates.get("require_visual_templates_ready", True))
            or bool(row["visual_templates_ready"]),
            f"visual_templates_ready={bool(row['visual_templates_ready'])}",
        ),
        _gate_row(
            "ML feature-engineering policy is ready",
            (not gates.get("require_ml_policy_ready", True))
            or bool(row["ml_policy_ready"]),
            f"ml_policy_ready={bool(row['ml_policy_ready'])}",
        ),
        _gate_row(
            "Phase 13G boundary is pre-registration-only",
            (not gates.get("require_phase13g_boundary_prereg_only", True))
            or bool(row["phase13g_boundary_passed"]),
            f"phase13g_boundary_passed={bool(row['phase13g_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks feature/model/signal/backtest/paper-trading/promotion",
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


def build_phase13f_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — feature schema readiness and visual template audit passed"
        if all_passed
        else "Failed feature schema readiness and visual template audit"
    )
    interpretation = (
        "Phase 13F verified technical/macro schema coverage, visual report templates, "
        "and ML feature-engineering policy readiness. It did not ingest or calculate "
        "features, create signals, run backtests, train models, deploy paper trading, "
        "promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13F found a schema readiness, visual-template, ML-policy, boundary, or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 13F",
                "diagnostic": "Feature schema readiness and visual template audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase13f_markdown(
    *,
    report_inventory_check: pd.DataFrame,
    phase13e_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    readiness_claims_check: pd.DataFrame,
    schema_coverage_check: pd.DataFrame,
    visual_template_check: pd.DataFrame,
    ml_policy_check: pd.DataFrame,
    phase13g_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 13F — Feature Schema Readiness / Visual Template Audit",
        "",
        "This phase audits schema and template readiness only. It does not ingest or "
        "calculate features, create signals, run backtests, train models, deploy paper "
        "trading, promote a candidate, or change the final candidate.",
        "",
        "## Report Inventory Check",
        report_inventory_check.to_markdown(index=False),
        "",
        "## Phase 13E Result Check",
        phase13e_result_check.to_markdown(index=False),
        "",
        "## Config Flag Check",
        config_flag_check.to_markdown(index=False),
        "",
        "## Readiness Claims Check",
        readiness_claims_check.to_markdown(index=False),
        "",
        "## Schema Coverage Check",
        schema_coverage_check.to_markdown(index=False),
        "",
        "## Visual Template Check",
        visual_template_check.to_markdown(index=False),
        "",
        "## ML Policy Check",
        ml_policy_check.to_markdown(index=False),
        "",
        "## Phase 13G Boundary Check",
        phase13g_boundary_check.to_markdown(index=False),
        "",
        "## Scope Boundary Check",
        scope_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        conclusion.to_markdown(index=False),
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13f_feature_schema_readiness_visual_template_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13f_config(config)
    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase13f_report_inventory_check(phase_config)
    phase13e_result_check = build_phase13f_phase13e_result_check(phase_config)
    config_flag_check = build_phase13f_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )
    readiness_claims_check = build_phase13f_readiness_claims_check(phase_config)

    reports = phase_config.get("phase13e_reports", {})
    universal_panel_schema = _read_csv_if_exists(
        reports.get("universal_panel_schema", "")
    )
    technical_feature_schema = _read_csv_if_exists(
        reports.get("technical_feature_schema", "")
    )
    macro_feature_schema = _read_csv_if_exists(reports.get("macro_feature_schema", ""))
    transform_policy = _read_csv_if_exists(reports.get("transform_policy", ""))
    missingness_policy = _read_csv_if_exists(reports.get("missingness_policy", ""))
    visual_report_templates = _read_csv_if_exists(
        reports.get("visual_report_templates", "")
    )

    schema_coverage_check = build_phase13f_schema_coverage_check(
        universal_panel_schema=universal_panel_schema,
        technical_feature_schema=technical_feature_schema,
        macro_feature_schema=macro_feature_schema,
        transform_policy=transform_policy,
        missingness_policy=missingness_policy,
    )
    visual_template_check = build_phase13f_visual_template_check(
        visual_report_templates
    )
    ml_policy_check = build_phase13f_ml_policy_check(transform_policy)
    phase13g_boundary_check = build_phase13f_phase13g_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13f_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13e_result_check=phase13e_result_check,
        config_flag_check=config_flag_check,
        readiness_claims_check=readiness_claims_check,
        schema_coverage_check=schema_coverage_check,
        visual_template_check=visual_template_check,
        ml_policy_check=ml_policy_check,
        phase13g_boundary_check=phase13g_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13f_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13f_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13e_result_check": phase13e_result_check,
        "config_flag_check": config_flag_check,
        "readiness_claims_check": readiness_claims_check,
        "schema_coverage_check": schema_coverage_check,
        "visual_template_check": visual_template_check,
        "ml_policy_check": ml_policy_check,
        "phase13g_boundary_check": phase13g_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13f_schema_audit_{name}.csv", index=False)

    write_phase13f_markdown(
        report_inventory_check=report_inventory_check,
        phase13e_result_check=phase13e_result_check,
        config_flag_check=config_flag_check,
        readiness_claims_check=readiness_claims_check,
        schema_coverage_check=schema_coverage_check,
        visual_template_check=visual_template_check,
        ml_policy_check=ml_policy_check,
        phase13g_boundary_check=phase13g_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase13f_feature_schema_readiness_visual_template_audit.md",
    )

    print("Wrote Phase 13F feature schema readiness / visual template audit reports.")
    return outputs