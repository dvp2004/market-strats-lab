from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE13G_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Technical and macro feature calculation pre-registration spec only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13F",
    "proposed_next_phase": "Phase 13H",
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
    "calculation_registry": [],
    "output_column_schema": [],
    "missingness_behaviour": [],
    "leakage_checks": [],
    "visual_checks": [],
    "ml_feature_engineering_lock": {},
    "phase13h_boundary": {},
    "gates": {
        "require_phase13f_passed": True,
        "require_calculation_registry": True,
        "min_registered_features": 8,
        "require_technical_macro_features": True,
        "require_exact_formula_fields": True,
        "require_output_column_schema": True,
        "min_output_columns": 15,
        "require_missingness_behaviour": True,
        "min_missingness_rules": 5,
        "require_leakage_checks": True,
        "min_leakage_checks": 6,
        "require_visual_checks": True,
        "min_visual_checks": 5,
        "require_ml_feature_engineering_lock": True,
        "require_no_calculate_now": True,
        "require_phase13h_boundary_readiness_only": True,
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
            "Technical and macro feature calculation pre-registration spec only"
        ),
    },
}


DEFAULT_PHASE13H_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Feature calculation readiness audit only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13G",
    "proposed_next_phase": "Phase 13I",
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
    "phase13g_reports": {},
    "readiness_claims": {},
    "phase13i_boundary": {},
    "gates": {
        "require_phase13g_reports_present": True,
        "require_phase13g_conclusion_passed": True,
        "require_phase13g_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_readiness_claims_locked": True,
        "require_formula_registry_locked": True,
        "require_output_schema_locked": True,
        "require_missingness_leakage_visual_checks_locked": True,
        "require_ml_lock_ready": True,
        "require_phase13i_boundary_feature_calculation_only": True,
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
        "required_audit_role": "Feature calculation readiness audit only",
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


def _get_phase13g_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13G_CONFIG,
        config.get("phase13g_feature_calculation_preregistration_spec", {}),
    )


def _get_phase13h_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13H_CONFIG,
        config.get("phase13h_feature_calculation_readiness_audit", {}),
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


def build_phase13g_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase13g_phase13f_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13f_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13f_gate_report", ""))

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
            "check": "Phase 13F conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 13F gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13g_calculation_registry(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in _as_list(phase_config.get("calculation_registry")):
        rows.append(
            {
                "feature_id": str(item.get("feature_id", "")),
                "family_id": str(item.get("family_id", "")),
                "formula_id": str(item.get("formula_id", "")),
                "raw_inputs": _join_list(item.get("raw_inputs")),
                "lookback_window": str(item.get("lookback_window", "")),
                "formula_description": str(item.get("formula_description", "")),
                "threshold_policy": str(item.get("threshold_policy", "")),
                "lag_policy": str(item.get("lag_policy", "")),
                "revision_policy": str(item.get("revision_policy", "")),
                "missingness_policy": str(item.get("missingness_policy", "")),
                "output_state_column": str(item.get("output_state_column", "")),
                "output_value_column": str(item.get("output_value_column", "")),
                "leakage_check_id": str(item.get("leakage_check_id", "")),
                "visual_check_id": str(item.get("visual_check_id", "")),
                "calculate_now": _bool_value(item.get("calculate_now", True)),
            }
        )
    return pd.DataFrame(rows)


def build_phase13g_simple_registry(
    phase_config: dict[str, Any],
    config_key: str,
    id_key: str,
    text_key: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in _as_list(phase_config.get(config_key)):
        rows.append(
            {
                id_key: str(item.get(id_key, "")),
                text_key: str(item.get(text_key, "")),
                "required": _bool_value(item.get("required", False)),
            }
        )
    return pd.DataFrame(rows)


def build_phase13g_output_column_schema(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in _as_list(phase_config.get("output_column_schema")):
        rows.append(
            {
                "column_name": str(item.get("column_name", "")),
                "dtype": str(item.get("dtype", "")),
                "required": _bool_value(item.get("required", False)),
            }
        )
    return pd.DataFrame(rows)


def build_phase13g_ml_feature_engineering_lock(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    lock = phase_config.get("ml_feature_engineering_lock", {})
    rows = []
    for key, value in lock.items():
        rows.append(
            {
                "lock_item": str(key),
                "expected": True,
                "actual": _bool_value(value),
                "passed": _bool_value(value) is True,
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13g_phase13h_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13h_boundary", {})
    checks = [
        (
            "phase13h_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "readiness audit" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13h_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "feature calculation"
            in str(boundary.get("forbidden_next_step", "")).lower()
            and "model training"
            in str(boundary.get("forbidden_next_step", "")).lower()
            and "strategy backtest"
            in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13h_may_audit_formula_registry",
            _bool_value(boundary.get("phase13h_may_audit_formula_registry", False)),
            _bool_value(boundary.get("phase13h_may_audit_formula_registry", False)),
        ),
        (
            "phase13h_may_audit_output_schema",
            _bool_value(boundary.get("phase13h_may_audit_output_schema", False)),
            _bool_value(boundary.get("phase13h_may_audit_output_schema", False)),
        ),
        (
            "phase13h_may_calculate_features",
            _bool_value(boundary.get("phase13h_may_calculate_features", True)),
            not _bool_value(boundary.get("phase13h_may_calculate_features", True)),
        ),
        (
            "phase13h_may_train_model",
            _bool_value(boundary.get("phase13h_may_train_model", True)),
            not _bool_value(boundary.get("phase13h_may_train_model", True)),
        ),
        (
            "phase13h_may_create_signal",
            _bool_value(boundary.get("phase13h_may_create_signal", True)),
            not _bool_value(boundary.get("phase13h_may_create_signal", True)),
        ),
        (
            "phase13h_may_run_backtest",
            _bool_value(boundary.get("phase13h_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13h_may_run_backtest", True)),
        ),
        (
            "phase13h_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13h_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13h_may_deploy_paper_trading", True)),
        ),
        (
            "phase13h_may_promote_candidate",
            _bool_value(boundary.get("phase13h_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13h_may_promote_candidate", True)),
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


def build_phase13g_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13f_result_check: pd.DataFrame,
    calculation_registry: pd.DataFrame,
    output_column_schema: pd.DataFrame,
    missingness_behaviour: pd.DataFrame,
    leakage_checks: pd.DataFrame,
    visual_checks: pd.DataFrame,
    ml_feature_engineering_lock: pd.DataFrame,
    phase13h_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    families = (
        set(calculation_registry["family_id"].dropna().astype(str).tolist())
        if not calculation_registry.empty
        else set()
    )
    required_formula_columns = [
        "feature_id",
        "family_id",
        "formula_id",
        "raw_inputs",
        "lookback_window",
        "formula_description",
        "threshold_policy",
        "lag_policy",
        "revision_policy",
        "missingness_policy",
        "output_state_column",
        "output_value_column",
    ]
    exact_formula_fields_present = (
        not calculation_registry.empty
        and all(
            calculation_registry[col].astype(str).str.len().gt(0).all()
            for col in required_formula_columns
        )
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
                "phase13f_result_passed": bool(phase13f_result_check["passed"].all())
                if not phase13f_result_check.empty
                else False,
                "registered_feature_count": int(len(calculation_registry)),
                "technical_macro_present": {"technical", "macro"}.issubset(families),
                "exact_formula_fields_present": exact_formula_fields_present,
                "no_calculate_now": bool(
                    calculation_registry["calculate_now"]
                    .map(_bool_value)
                    .eq(False)
                    .all()
                )
                if not calculation_registry.empty
                else False,
                "output_column_count": int(len(output_column_schema)),
                "output_columns_required": bool(
                    output_column_schema["required"].map(_bool_value).all()
                )
                if not output_column_schema.empty
                else False,
                "missingness_rule_count": int(len(missingness_behaviour)),
                "missingness_rules_required": bool(
                    missingness_behaviour["required"].map(_bool_value).all()
                )
                if not missingness_behaviour.empty
                else False,
                "leakage_check_count": int(len(leakage_checks)),
                "leakage_checks_required": bool(
                    leakage_checks["required"].map(_bool_value).all()
                )
                if not leakage_checks.empty
                else False,
                "visual_check_count": int(len(visual_checks)),
                "visual_checks_required": bool(
                    visual_checks["required"].map(_bool_value).all()
                )
                if not visual_checks.empty
                else False,
                "ml_lock_ready": bool(ml_feature_engineering_lock["passed"].all())
                if not ml_feature_engineering_lock.empty
                else False,
                "phase13h_boundary_passed": bool(
                    phase13h_boundary_check["passed"].all()
                )
                if not phase13h_boundary_check.empty
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


def build_phase13g_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13G summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_spec_role",
            "Technical and macro feature calculation pre-registration spec only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13F passed",
            (not gates.get("require_phase13f_passed", True))
            or bool(row["phase13f_result_passed"]),
            f"phase13f_result_passed={bool(row['phase13f_result_passed'])}",
        ),
        _gate_row(
            "Calculation registry is complete enough",
            (not gates.get("require_calculation_registry", True))
            or int(row["registered_feature_count"])
            >= int(gates.get("min_registered_features", 8)),
            f"registered_feature_count={int(row['registered_feature_count'])}",
        ),
        _gate_row(
            "Technical and macro features are registered",
            (not gates.get("require_technical_macro_features", True))
            or bool(row["technical_macro_present"]),
            f"technical_macro_present={bool(row['technical_macro_present'])}",
        ),
        _gate_row(
            "Exact formula fields are locked",
            (not gates.get("require_exact_formula_fields", True))
            or bool(row["exact_formula_fields_present"]),
            f"exact_formula_fields_present={bool(row['exact_formula_fields_present'])}",
        ),
        _gate_row(
            "No feature is calculated now",
            (not gates.get("require_no_calculate_now", True))
            or bool(row["no_calculate_now"]),
            f"no_calculate_now={bool(row['no_calculate_now'])}",
        ),
        _gate_row(
            "Output column schema is complete enough",
            (not gates.get("require_output_column_schema", True))
            or (
                int(row["output_column_count"]) >= int(gates.get("min_output_columns", 15))
                and bool(row["output_columns_required"])
            ),
            f"output_column_count={int(row['output_column_count'])}",
        ),
        _gate_row(
            "Missingness behaviour is locked",
            (not gates.get("require_missingness_behaviour", True))
            or (
                int(row["missingness_rule_count"])
                >= int(gates.get("min_missingness_rules", 5))
                and bool(row["missingness_rules_required"])
            ),
            f"missingness_rule_count={int(row['missingness_rule_count'])}",
        ),
        _gate_row(
            "Leakage checks are locked",
            (not gates.get("require_leakage_checks", True))
            or (
                int(row["leakage_check_count"])
                >= int(gates.get("min_leakage_checks", 6))
                and bool(row["leakage_checks_required"])
            ),
            f"leakage_check_count={int(row['leakage_check_count'])}",
        ),
        _gate_row(
            "Visual checks are locked",
            (not gates.get("require_visual_checks", True))
            or (
                int(row["visual_check_count"]) >= int(gates.get("min_visual_checks", 5))
                and bool(row["visual_checks_required"])
            ),
            f"visual_check_count={int(row['visual_check_count'])}",
        ),
        _gate_row(
            "ML feature-engineering lock is ready",
            (not gates.get("require_ml_feature_engineering_lock", True))
            or bool(row["ml_lock_ready"]),
            f"ml_lock_ready={bool(row['ml_lock_ready'])}",
        ),
        _gate_row(
            "Phase 13H boundary is readiness-only",
            (not gates.get("require_phase13h_boundary_readiness_only", True))
            or bool(row["phase13h_boundary_passed"]),
            f"phase13h_boundary_passed={bool(row['phase13h_boundary_passed'])}",
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


def build_phase13g_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — feature calculation pre-registration spec passed"
        if all_passed
        else "Failed feature calculation pre-registration spec"
    )
    interpretation = (
        "Phase 13G locked exact technical and macro feature formulas, raw inputs, "
        "lookbacks, thresholds, lag rules, output columns, missingness behaviour, "
        "leakage checks, visual checks, and ML feature-engineering safeguards. It "
        "did not ingest or calculate features, create signals, run backtests, train "
        "models, deploy paper trading, promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13G found a formula, output schema, leakage, visual, ML-lock, "
        "boundary, or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 13G",
                "diagnostic": "Feature calculation pre-registration spec",
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


def save_phase13g_feature_calculation_preregistration_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13g_config(config)
    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13g_source_report_check(phase_config)
    phase13f_result_check = build_phase13g_phase13f_result_check(phase_config)
    calculation_registry = build_phase13g_calculation_registry(phase_config)
    output_column_schema = build_phase13g_output_column_schema(phase_config)
    missingness_behaviour = build_phase13g_simple_registry(
        phase_config,
        "missingness_behaviour",
        "rule_id",
        "rule",
    )
    leakage_checks = build_phase13g_simple_registry(
        phase_config,
        "leakage_checks",
        "check_id",
        "check",
    )
    visual_checks = build_phase13g_simple_registry(
        phase_config,
        "visual_checks",
        "visual_check_id",
        "check",
    )
    ml_feature_engineering_lock = build_phase13g_ml_feature_engineering_lock(
        phase_config
    )
    phase13h_boundary_check = build_phase13g_phase13h_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13g_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13f_result_check=phase13f_result_check,
        calculation_registry=calculation_registry,
        output_column_schema=output_column_schema,
        missingness_behaviour=missingness_behaviour,
        leakage_checks=leakage_checks,
        visual_checks=visual_checks,
        ml_feature_engineering_lock=ml_feature_engineering_lock,
        phase13h_boundary_check=phase13h_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13g_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13g_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13f_result_check": phase13f_result_check,
        "calculation_registry": calculation_registry,
        "output_column_schema": output_column_schema,
        "missingness_behaviour": missingness_behaviour,
        "leakage_checks": leakage_checks,
        "visual_checks": visual_checks,
        "ml_feature_engineering_lock": ml_feature_engineering_lock,
        "phase13h_boundary_check": phase13h_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13g_prereg_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13G — Feature Calculation Pre-Registration Spec",
        sections={
            "Source Report Check": source_report_check,
            "Phase 13F Result Check": phase13f_result_check,
            "Calculation Registry": calculation_registry,
            "Output Column Schema": output_column_schema,
            "Missingness Behaviour": missingness_behaviour,
            "Leakage Checks": leakage_checks,
            "Visual Checks": visual_checks,
            "ML Feature Engineering Lock": ml_feature_engineering_lock,
            "Phase 13H Boundary Check": phase13h_boundary_check,
            "Scope Boundary Check": scope_boundary_check,
            "Summary": summary,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path / "phase13g_feature_calculation_preregistration_spec.md",
    )

    print("Wrote Phase 13G feature calculation pre-registration reports.")
    return outputs


def build_phase13h_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for report_key, path in phase_config.get("phase13g_reports", {}).items():
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


def build_phase13h_phase13g_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase13g_reports", {})
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
            "check": "Phase 13G conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 13G gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13h_config_flag_check(
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


def build_phase13h_readiness_claims_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    claims = phase_config.get("readiness_claims", {})
    expected_true = [
        "calculation_registry_locked",
        "output_schema_locked",
        "missingness_behaviour_locked",
        "leakage_checks_locked",
        "visual_checks_locked",
        "ml_feature_engineering_lock_present",
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

    rows: list[dict[str, Any]] = []
    for claim in expected_true:
        actual = _bool_value(claims.get(claim, False))
        rows.append(
            {"claim": claim, "expected": True, "actual": actual, "passed": actual}
        )
    for claim in expected_false:
        actual = _bool_value(claims.get(claim, True))
        rows.append(
            {
                "claim": claim,
                "expected": False,
                "actual": actual,
                "passed": not actual,
            }
        )
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13h_formula_registry_lock_check(
    calculation_registry: pd.DataFrame,
) -> pd.DataFrame:
    required_cols = {
        "feature_id",
        "family_id",
        "formula_id",
        "raw_inputs",
        "lookback_window",
        "formula_description",
        "threshold_policy",
        "lag_policy",
        "revision_policy",
        "missingness_policy",
        "output_state_column",
        "output_value_column",
        "calculate_now",
    }
    present_cols = set(calculation_registry.columns)
    families = (
        set(calculation_registry["family_id"].dropna().astype(str).tolist())
        if not calculation_registry.empty and "family_id" in calculation_registry.columns
        else set()
    )
    rows = [
        {
            "check": "Required formula columns present",
            "passed": required_cols.issubset(present_cols),
            "detail": "missing=" + "; ".join(sorted(required_cols - present_cols)),
        },
        {
            "check": "At least eight formulas registered",
            "passed": len(calculation_registry) >= 8,
            "detail": f"registered_features={len(calculation_registry)}",
        },
        {
            "check": "Technical and macro formula families present",
            "passed": {"technical", "macro"}.issubset(families),
            "detail": "families=" + "; ".join(sorted(families)),
        },
        {
            "check": "No registered formula calculates now",
            "passed": bool(
                calculation_registry["calculate_now"].map(_bool_value).eq(False).all()
            )
            if not calculation_registry.empty
            and "calculate_now" in calculation_registry.columns
            else False,
            "detail": "calculate_now must be false for every row",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13h_output_schema_lock_check(
    output_column_schema: pd.DataFrame,
) -> pd.DataFrame:
    required_cols = {
        "as_of_date",
        "observation_date",
        "release_date",
        "availability_date",
        "decision_date",
        "family_id",
        "feature_id",
        "formula_id",
        "feature_value",
        "feature_state",
        "state_reason",
        "missingness_state",
        "leakage_flag",
        "contract_version",
    }
    actual_cols = (
        set(output_column_schema["column_name"].dropna().astype(str).tolist())
        if not output_column_schema.empty
        else set()
    )
    rows = [
        {
            "check": "Required output columns present",
            "passed": required_cols.issubset(actual_cols),
            "detail": "missing=" + "; ".join(sorted(required_cols - actual_cols)),
        },
        {
            "check": "Output schema is complete enough",
            "passed": len(output_column_schema) >= 15,
            "detail": f"output_columns={len(output_column_schema)}",
        },
        {
            "check": "Output schema columns are required",
            "passed": bool(output_column_schema["required"].map(_bool_value).all())
            if not output_column_schema.empty
            else False,
            "detail": "required must be true for every output column",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13h_lock_rows_check(
    *,
    missingness_behaviour: pd.DataFrame,
    leakage_checks: pd.DataFrame,
    visual_checks: pd.DataFrame,
    ml_feature_engineering_lock: pd.DataFrame,
) -> pd.DataFrame:
    rows = [
        {
            "check": "Missingness rules locked",
            "passed": len(missingness_behaviour) >= 5
            and bool(missingness_behaviour["required"].map(_bool_value).all()),
            "detail": f"rows={len(missingness_behaviour)}",
        },
        {
            "check": "Leakage checks locked",
            "passed": len(leakage_checks) >= 6
            and bool(leakage_checks["required"].map(_bool_value).all()),
            "detail": f"rows={len(leakage_checks)}",
        },
        {
            "check": "Visual checks locked",
            "passed": len(visual_checks) >= 5
            and bool(visual_checks["required"].map(_bool_value).all()),
            "detail": f"rows={len(visual_checks)}",
        },
        {
            "check": "ML feature-engineering lock ready",
            "passed": bool(ml_feature_engineering_lock["passed"].all())
            if not ml_feature_engineering_lock.empty
            else False,
            "detail": f"rows={len(ml_feature_engineering_lock)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13h_phase13i_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13i_boundary", {})
    checks = [
        (
            "phase13i_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "feature calculation execution"
            in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13i_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "signal creation" in str(boundary.get("forbidden_next_step", "")).lower()
            and "model training" in str(boundary.get("forbidden_next_step", "")).lower()
            and "strategy backtest"
            in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13i_may_calculate_features",
            _bool_value(boundary.get("phase13i_may_calculate_features", False)),
            _bool_value(boundary.get("phase13i_may_calculate_features", False)),
        ),
        (
            "phase13i_may_create_feature_panels",
            _bool_value(boundary.get("phase13i_may_create_feature_panels", False)),
            _bool_value(boundary.get("phase13i_may_create_feature_panels", False)),
        ),
        (
            "phase13i_may_create_signal",
            _bool_value(boundary.get("phase13i_may_create_signal", True)),
            not _bool_value(boundary.get("phase13i_may_create_signal", True)),
        ),
        (
            "phase13i_may_train_model",
            _bool_value(boundary.get("phase13i_may_train_model", True)),
            not _bool_value(boundary.get("phase13i_may_train_model", True)),
        ),
        (
            "phase13i_may_run_backtest",
            _bool_value(boundary.get("phase13i_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13i_may_run_backtest", True)),
        ),
        (
            "phase13i_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13i_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13i_may_deploy_paper_trading", True)),
        ),
        (
            "phase13i_may_promote_candidate",
            _bool_value(boundary.get("phase13i_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13i_may_promote_candidate", True)),
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


def build_phase13h_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13g_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    readiness_claims_check: pd.DataFrame,
    formula_registry_lock_check: pd.DataFrame,
    output_schema_lock_check: pd.DataFrame,
    lock_rows_check: pd.DataFrame,
    phase13i_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13g_reports_present": bool(
                    report_inventory_check["present"].all()
                )
                if not report_inventory_check.empty
                else False,
                "phase13g_result_passed": bool(phase13g_result_check["passed"].all())
                if not phase13g_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "readiness_claims_locked": bool(
                    readiness_claims_check["passed"].all()
                )
                if not readiness_claims_check.empty
                else False,
                "formula_registry_locked": bool(
                    formula_registry_lock_check["passed"].all()
                )
                if not formula_registry_lock_check.empty
                else False,
                "output_schema_locked": bool(output_schema_lock_check["passed"].all())
                if not output_schema_lock_check.empty
                else False,
                "missingness_leakage_visual_ml_locked": bool(
                    lock_rows_check["passed"].all()
                )
                if not lock_rows_check.empty
                else False,
                "phase13i_boundary_passed": bool(
                    phase13i_boundary_check["passed"].all()
                )
                if not phase13i_boundary_check.empty
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


def build_phase13h_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13H summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get("required_audit_role", "Feature calculation readiness audit only")
    )
    rows = [
        _gate_row(
            "Phase 13G reports are present",
            (not gates.get("require_phase13g_reports_present", True))
            or bool(row["phase13g_reports_present"]),
            f"phase13g_reports_present={bool(row['phase13g_reports_present'])}",
        ),
        _gate_row(
            "Phase 13G conclusion and gates passed",
            (
                (not gates.get("require_phase13g_conclusion_passed", True))
                or bool(row["phase13g_result_passed"])
            )
            and (
                (not gates.get("require_phase13g_gate_report_passed", True))
                or bool(row["phase13g_result_passed"])
            ),
            f"phase13g_result_passed={bool(row['phase13g_result_passed'])}",
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
            "Formula registry is locked",
            (not gates.get("require_formula_registry_locked", True))
            or bool(row["formula_registry_locked"]),
            f"formula_registry_locked={bool(row['formula_registry_locked'])}",
        ),
        _gate_row(
            "Output schema is locked",
            (not gates.get("require_output_schema_locked", True))
            or bool(row["output_schema_locked"]),
            f"output_schema_locked={bool(row['output_schema_locked'])}",
        ),
        _gate_row(
            "Missingness/leakage/visual/ML checks are locked",
            (not gates.get("require_missingness_leakage_visual_checks_locked", True))
            or bool(row["missingness_leakage_visual_ml_locked"]),
            (
                "missingness_leakage_visual_ml_locked="
                f"{bool(row['missingness_leakage_visual_ml_locked'])}"
            ),
        ),
        _gate_row(
            "Phase 13I boundary is feature-calculation-only",
            (not gates.get("require_phase13i_boundary_feature_calculation_only", True))
            or bool(row["phase13i_boundary_passed"]),
            f"phase13i_boundary_passed={bool(row['phase13i_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks signal/model/backtest/paper-trading/promotion",
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


def build_phase13h_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — feature calculation readiness audit passed"
        if all_passed
        else "Failed feature calculation readiness audit"
    )
    interpretation = (
        "Phase 13H verified that feature calculation formulas, output schema, "
        "missingness behaviour, leakage checks, visual checks, and ML locks are ready "
        "for a future feature-calculation execution phase. It did not ingest or "
        "calculate features, create signals, run backtests, train models, deploy "
        "paper trading, promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13H found a readiness, formula, output-schema, lock, boundary, "
        "or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 13H",
                "diagnostic": "Feature calculation readiness audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def save_phase13h_feature_calculation_readiness_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13h_config(config)
    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase13h_report_inventory_check(phase_config)
    phase13g_result_check = build_phase13h_phase13g_result_check(phase_config)
    config_flag_check = build_phase13h_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )
    readiness_claims_check = build_phase13h_readiness_claims_check(phase_config)

    reports = phase_config.get("phase13g_reports", {})
    calculation_registry = _read_csv_if_exists(reports.get("calculation_registry", ""))
    output_column_schema = _read_csv_if_exists(reports.get("output_column_schema", ""))
    missingness_behaviour = _read_csv_if_exists(reports.get("missingness_behaviour", ""))
    leakage_checks = _read_csv_if_exists(reports.get("leakage_checks", ""))
    visual_checks = _read_csv_if_exists(reports.get("visual_checks", ""))
    ml_feature_engineering_lock = _read_csv_if_exists(
        reports.get("ml_feature_engineering_lock", "")
    )

    formula_registry_lock_check = build_phase13h_formula_registry_lock_check(
        calculation_registry
    )
    output_schema_lock_check = build_phase13h_output_schema_lock_check(
        output_column_schema
    )
    lock_rows_check = build_phase13h_lock_rows_check(
        missingness_behaviour=missingness_behaviour,
        leakage_checks=leakage_checks,
        visual_checks=visual_checks,
        ml_feature_engineering_lock=ml_feature_engineering_lock,
    )
    phase13i_boundary_check = build_phase13h_phase13i_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13h_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13g_result_check=phase13g_result_check,
        config_flag_check=config_flag_check,
        readiness_claims_check=readiness_claims_check,
        formula_registry_lock_check=formula_registry_lock_check,
        output_schema_lock_check=output_schema_lock_check,
        lock_rows_check=lock_rows_check,
        phase13i_boundary_check=phase13i_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13h_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13h_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13g_result_check": phase13g_result_check,
        "config_flag_check": config_flag_check,
        "readiness_claims_check": readiness_claims_check,
        "formula_registry_lock_check": formula_registry_lock_check,
        "output_schema_lock_check": output_schema_lock_check,
        "lock_rows_check": lock_rows_check,
        "phase13i_boundary_check": phase13i_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13h_readiness_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13H — Feature Calculation Readiness Audit",
        sections={
            "Report Inventory Check": report_inventory_check,
            "Phase 13G Result Check": phase13g_result_check,
            "Config Flag Check": config_flag_check,
            "Readiness Claims Check": readiness_claims_check,
            "Formula Registry Lock Check": formula_registry_lock_check,
            "Output Schema Lock Check": output_schema_lock_check,
            "Lock Rows Check": lock_rows_check,
            "Phase 13I Boundary Check": phase13i_boundary_check,
            "Scope Boundary Check": scope_boundary_check,
            "Summary": summary,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path / "phase13h_feature_calculation_readiness_audit.md",
    )

    print("Wrote Phase 13H feature calculation readiness audit reports.")
    return outputs