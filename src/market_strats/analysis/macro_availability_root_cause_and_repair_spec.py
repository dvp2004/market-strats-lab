from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE13O_CONFIG: dict[str, Any] = {
    "enabled": False,
    "diagnostic_role": "Macro availability root-cause diagnostic only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13N",
    "proposed_next_phase": "Phase 13P",
    "allow_macro_diagnosis": True,
    "allow_macro_repair_decision": False,
    "allow_macro_feature_repair_execution": False,
    "allow_dataset_reassembly": False,
    "allow_target_recalculation": False,
    "allow_model_training": False,
    "allow_model_selection": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_feature_importance": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "macro_sources": {},
    "diagnosis_policy": {
        "min_rows_for_source_usable": 100,
        "min_numeric_non_null_per_macro_input": 100,
        "min_repaired_available_ratio_to_accept": 0.20,
    },
    "phase13p_boundary": {},
    "gates": {
        "require_phase13n_passed": True,
        "require_source_reports_present": True,
        "require_macro_source_checked": True,
        "require_macro_guard_loaded": True,
        "require_macro_repair_panel_loaded": True,
        "require_column_mapping_report": True,
        "require_root_cause_report": True,
        "require_phase13p_boundary_decision_only": True,
        "require_no_macro_repair_execution": True,
        "require_no_dataset_reassembly": True,
        "require_no_target_recalculation": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_feature_importance": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_diagnostic_role": "Macro availability root-cause diagnostic only",
    },
}


DEFAULT_PHASE13P_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Macro feature repair decision and repair spec only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13O",
    "proposed_next_phase": "Phase 13Q",
    "allow_macro_repair_execution": False,
    "allow_dataset_reassembly": False,
    "allow_target_recalculation": False,
    "allow_model_training": False,
    "allow_model_selection": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_feature_importance": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "phase13o_reports": {},
    "decision_policy": {},
    "repair_spec_template": {},
    "phase13q_boundary": {},
    "gates": {
        "require_phase13o_reports_present": True,
        "require_phase13o_conclusion_passed": True,
        "require_phase13o_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_root_cause_report": True,
        "require_repair_decision": True,
        "require_repair_spec": True,
        "require_dataset_label_blocked_until_repair": True,
        "require_phase13q_boundary_repair_only": True,
        "require_no_macro_repair_execution": True,
        "require_no_dataset_reassembly": True,
        "require_no_target_recalculation": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_feature_importance": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_spec_role": "Macro feature repair decision and repair spec only",
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


def _get_phase13o_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13O_CONFIG,
        config.get("phase13o_macro_availability_root_cause_diagnostic", {}),
    )


def _get_phase13p_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13P_CONFIG,
        config.get("phase13p_macro_feature_repair_decision_spec", {}),
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


def _load_first_existing_csv(paths: list[str]) -> tuple[pd.DataFrame, str]:
    for path in paths:
        frame = _read_csv_if_exists(path)
        if not frame.empty:
            return frame, path
    return pd.DataFrame(), ""


def _normalise_columns(frame: pd.DataFrame) -> dict[str, str]:
    return {str(col).strip().lower(): str(col) for col in frame.columns}


def _find_alias_column(frame: pd.DataFrame, aliases: list[str]) -> str:
    lookup = _normalise_columns(frame)

    for alias in aliases:
        clean = str(alias).strip().lower()
        if clean in lookup:
            return lookup[clean]

    for col in frame.columns:
        col_lower = str(col).strip().lower()
        for alias in aliases:
            if str(alias).strip().lower() in col_lower:
                return str(col)

    return ""


def build_phase13o_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase13o_phase13n_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13n_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13n_gate_report", ""))

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
                "check": "Phase 13N conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13N gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def load_phase13o_macro_source(
    phase_config: dict[str, Any],
) -> tuple[pd.DataFrame, str]:
    macro_sources = phase_config.get("macro_sources", {})
    candidates = [str(path) for path in _as_list(macro_sources.get("macro_aligned_candidates"))]
    return _load_first_existing_csv(candidates)


def build_phase13o_macro_source_inventory(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for path in _as_list(phase_config.get("macro_sources", {}).get("macro_aligned_candidates")):
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "candidate_path": str(report_path),
                "present": report_path.exists(),
                "rows": int(len(frame)),
                "columns": "; ".join(str(col) for col in frame.columns),
                "result": "Passed" if report_path.exists() and not frame.empty else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase13o_macro_source_schema_profile(
    *,
    macro_source: pd.DataFrame,
    macro_source_path: str,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if macro_source.empty:
        return pd.DataFrame(
            [
                {
                    "source_path": macro_source_path,
                    "rows": 0,
                    "column_count": 0,
                    "columns": "",
                    "date_columns_detected": "",
                    "numeric_columns_detected": "",
                    "object_columns_detected": "",
                }
            ]
        )

    date_candidates = [
        str(col)
        for col in macro_source.columns
        if "date" in str(col).lower() or str(col) in _as_list(
            phase_config.get("macro_sources", {}).get("date_column_candidates")
        )
    ]
    numeric_cols = [
        str(col)
        for col in macro_source.columns
        if pd.api.types.is_numeric_dtype(macro_source[col])
    ]
    object_cols = [
        str(col)
        for col in macro_source.columns
        if not pd.api.types.is_numeric_dtype(macro_source[col])
    ]

    return pd.DataFrame(
        [
            {
                "source_path": macro_source_path,
                "rows": int(len(macro_source)),
                "column_count": int(len(macro_source.columns)),
                "columns": "; ".join(str(col) for col in macro_source.columns),
                "date_columns_detected": "; ".join(date_candidates),
                "numeric_columns_detected": "; ".join(numeric_cols),
                "object_columns_detected": "; ".join(object_cols),
            }
        ]
    )


def build_phase13o_macro_column_mapping_report(
    *,
    macro_source: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    required = phase_config.get("macro_sources", {}).get("required_macro_inputs", {})
    min_non_null = int(
        phase_config.get("diagnosis_policy", {}).get(
            "min_numeric_non_null_per_macro_input",
            100,
        )
    )
    rows: list[dict[str, Any]] = []

    for canonical, spec in required.items():
        aliases = _as_list(spec.get("aliases", [])) if isinstance(spec, dict) else []
        matched = _find_alias_column(macro_source, aliases) if not macro_source.empty else ""

        if matched:
            numeric = pd.to_numeric(macro_source[matched], errors="coerce")
            numeric_non_null = int(numeric.notna().sum())
            raw_non_null = int(macro_source[matched].notna().sum())
            sample_values = "; ".join(
                str(value) for value in macro_source[matched].dropna().head(5).tolist()
            )
        else:
            numeric_non_null = 0
            raw_non_null = 0
            sample_values = ""

        rows.append(
            {
                "canonical_input": canonical,
                "aliases": "; ".join(aliases),
                "matched_column": matched,
                "matched": bool(matched),
                "raw_non_null": raw_non_null,
                "numeric_non_null": numeric_non_null,
                "numeric_usable": numeric_non_null >= min_non_null,
                "sample_values": sample_values,
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["numeric_usable"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13o_macro_long_format_diagnostic(
    *,
    macro_source: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    macro_sources = phase_config.get("macro_sources", {})
    series_candidates = _as_list(
        macro_sources.get("long_format_series_column_candidates")
    )
    value_candidates = _as_list(macro_sources.get("long_format_value_column_candidates"))

    series_col = _find_alias_column(macro_source, series_candidates) if not macro_source.empty else ""
    value_col = _find_alias_column(macro_source, value_candidates) if not macro_source.empty else ""

    unique_series = []
    numeric_value_non_null = 0

    if series_col:
        unique_series = [str(item) for item in macro_source[series_col].dropna().unique()[:20]]

    if value_col:
        numeric_value_non_null = int(
            pd.to_numeric(macro_source[value_col], errors="coerce").notna().sum()
        )

    long_format_detected = bool(series_col and value_col and numeric_value_non_null > 0)

    return pd.DataFrame(
        [
            {
                "series_column": series_col,
                "value_column": value_col,
                "numeric_value_non_null": numeric_value_non_null,
                "long_format_detected": long_format_detected,
                "sample_series_values": "; ".join(unique_series),
                "result": "Passed" if long_format_detected else "Not detected",
            }
        ]
    )


def build_phase13o_existing_repair_panel_profile(
    repair_panel: pd.DataFrame,
) -> pd.DataFrame:
    if repair_panel.empty:
        return pd.DataFrame(
            [
                {
                    "family_id": "macro",
                    "feature_id": "missing",
                    "rows": 0,
                    "feature_value_non_null": 0,
                    "raw_inputs_available_true": 0,
                    "available_rows": 0,
                    "available_ratio": 0.0,
                }
            ]
        )

    rows: list[dict[str, Any]] = []

    for feature_id, group in repair_panel.groupby("feature_id"):
        rows.append(
            {
                "family_id": str(group["family_id"].iloc[0])
                if "family_id" in group.columns
                else "",
                "feature_id": str(feature_id),
                "rows": int(len(group)),
                "feature_value_non_null": int(
                    pd.to_numeric(group.get("feature_value"), errors="coerce")
                    .notna()
                    .sum()
                )
                if "feature_value" in group.columns
                else 0,
                "raw_inputs_available_true": int(
                    group.get("raw_inputs_available", pd.Series(dtype=bool))
                    .map(_bool_value)
                    .sum()
                )
                if "raw_inputs_available" in group.columns
                else 0,
                "available_rows": int(
                    group.get("missingness_state", pd.Series(dtype=str))
                    .astype(str)
                    .eq("available")
                    .sum()
                )
                if "missingness_state" in group.columns
                else 0,
                "available_ratio": float(
                    group.get("missingness_state", pd.Series(dtype=str))
                    .astype(str)
                    .eq("available")
                    .mean()
                )
                if "missingness_state" in group.columns and len(group) > 0
                else 0.0,
            }
        )

    return pd.DataFrame(rows).sort_values("feature_id")


def build_phase13o_macro_guard_profile(guard_report: pd.DataFrame) -> pd.DataFrame:
    if guard_report.empty:
        return pd.DataFrame(
            [
                {
                    "current_macro_available_ratio": 0.0,
                    "repair_attempted": False,
                    "repaired_macro_available_ratio": 0.0,
                    "repaired_successfully": False,
                    "macro_blocked_for_dataset_v1": True,
                    "dataset_label": "",
                }
            ]
        )

    return guard_report.copy()


def build_phase13o_root_cause_report(
    *,
    macro_source_inventory: pd.DataFrame,
    column_mapping_report: pd.DataFrame,
    long_format_diagnostic: pd.DataFrame,
    repair_panel_profile: pd.DataFrame,
    macro_guard_profile: pd.DataFrame,
) -> pd.DataFrame:
    source_found = (
        not macro_source_inventory.empty
        and bool(macro_source_inventory["present"].map(_bool_value).any())
    )
    all_columns_numeric = (
        not column_mapping_report.empty
        and bool(column_mapping_report["numeric_usable"].map(_bool_value).all())
    )
    any_columns_numeric = (
        not column_mapping_report.empty
        and bool(column_mapping_report["numeric_usable"].map(_bool_value).any())
    )
    long_format_detected = (
        not long_format_diagnostic.empty
        and _bool_value(long_format_diagnostic.iloc[0].get("long_format_detected", False))
    )
    repair_panel_available = (
        not repair_panel_profile.empty
        and float(repair_panel_profile["available_ratio"].max()) > 0.0
    )
    macro_blocked = (
        not macro_guard_profile.empty
        and _bool_value(macro_guard_profile.iloc[0].get("macro_blocked_for_dataset_v1", True))
    )

    if not source_found:
        root_cause = "macro_source_missing"
        recommended_action = "keep_macro_blocked_and_find_valid_macro_source"
        repairability = "not_repairable_without_source"
    elif long_format_detected and not all_columns_numeric:
        root_cause = "macro_source_long_format_not_normalised"
        recommended_action = "implement_long_to_wide_macro_normalisation"
        repairability = "repairable_with_source_normalisation"
    elif not any_columns_numeric:
        root_cause = "macro_columns_not_detected_or_values_non_numeric"
        recommended_action = "fix_macro_alias_mapping_or_numeric_parsing"
        repairability = "repairable_if_valid_columns_exist"
    elif all_columns_numeric and not repair_panel_available:
        root_cause = "macro_repair_panel_logic_failed_despite_numeric_source"
        recommended_action = "patch_macro_repair_panel_feature_value_and_missingness_logic"
        repairability = "repairable_in_code"
    elif macro_blocked and repair_panel_available:
        root_cause = "macro_guard_threshold_or_summary_logic_failed"
        recommended_action = "patch_macro_guard_ratio_calculation"
        repairability = "repairable_in_code"
    else:
        root_cause = "macro_failure_not_fully_diagnosed"
        recommended_action = "manual_macro_source_and_repair_panel_inspection"
        repairability = "unknown"

    return pd.DataFrame(
        [
            {
                "source_found": source_found,
                "long_format_detected": long_format_detected,
                "all_required_columns_numeric_usable": all_columns_numeric,
                "any_required_columns_numeric_usable": any_columns_numeric,
                "repair_panel_has_available_rows": repair_panel_available,
                "macro_blocked_for_dataset_v1": macro_blocked,
                "root_cause": root_cause,
                "recommended_action": recommended_action,
                "repairability": repairability,
                "model_training_allowed": False,
                "dataset_label_must_remain_blocked_until_repair": True,
            }
        ]
    )


def build_phase13o_phase13p_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13p_boundary", {})
    checks = [
        (
            "phase13p_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "repair decision" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13p_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "repair execution" in str(boundary.get("forbidden_next_step", "")).lower()
            and "model training" in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13p_may_write_repair_decision",
            _bool_value(boundary.get("phase13p_may_write_repair_decision", False)),
            _bool_value(boundary.get("phase13p_may_write_repair_decision", False)),
        ),
        (
            "phase13p_may_write_repair_spec",
            _bool_value(boundary.get("phase13p_may_write_repair_spec", False)),
            _bool_value(boundary.get("phase13p_may_write_repair_spec", False)),
        ),
        (
            "phase13p_may_execute_repair",
            _bool_value(boundary.get("phase13p_may_execute_repair", True)),
            not _bool_value(boundary.get("phase13p_may_execute_repair", True)),
        ),
        (
            "phase13p_may_reassemble_dataset",
            _bool_value(boundary.get("phase13p_may_reassemble_dataset", True)),
            not _bool_value(boundary.get("phase13p_may_reassemble_dataset", True)),
        ),
        (
            "phase13p_may_train_model",
            _bool_value(boundary.get("phase13p_may_train_model", True)),
            not _bool_value(boundary.get("phase13p_may_train_model", True)),
        ),
        (
            "phase13p_may_create_signal",
            _bool_value(boundary.get("phase13p_may_create_signal", True)),
            not _bool_value(boundary.get("phase13p_may_create_signal", True)),
        ),
    ]

    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No macro repair execution", "allow_macro_feature_repair_execution"),
        ("No dataset reassembly", "allow_dataset_reassembly"),
        ("No target recalculation", "allow_target_recalculation"),
        ("No model training", "allow_model_training"),
        ("No model selection", "allow_model_selection"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No feature importance", "allow_feature_importance"),
        ("No paper trading deployment", "allow_paper_trading_deployment"),
        ("No candidate promotion", "allow_candidate_promotion"),
        ("No final candidate change", "allow_final_candidate_change"),
    ]

    rows = []
    for label, key in checks:
        if key not in phase_config:
            continue
        value = _bool_value(phase_config.get(key, True))
        rows.append(
            {
                "scope_item": label,
                "value": value,
                "passed": not value,
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13o_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13n_result_check: pd.DataFrame,
    macro_source_inventory: pd.DataFrame,
    column_mapping_report: pd.DataFrame,
    repair_panel_profile: pd.DataFrame,
    macro_guard_profile: pd.DataFrame,
    root_cause_report: pd.DataFrame,
    phase13p_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "diagnostic_role": str(phase_config.get("diagnostic_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase13n_result_passed": bool(phase13n_result_check["passed"].all())
                if not phase13n_result_check.empty
                else False,
                "macro_source_checked": bool(macro_source_inventory["present"].any())
                if not macro_source_inventory.empty
                else False,
                "column_mapping_rows": int(len(column_mapping_report)),
                "repair_panel_profile_rows": int(len(repair_panel_profile)),
                "macro_guard_rows": int(len(macro_guard_profile)),
                "root_cause_rows": int(len(root_cause_report)),
                "root_cause": str(root_cause_report.iloc[0]["root_cause"])
                if not root_cause_report.empty
                else "",
                "recommended_action": str(root_cause_report.iloc[0]["recommended_action"])
                if not root_cause_report.empty
                else "",
                "phase13p_boundary_passed": bool(
                    phase13p_boundary_check["passed"].all()
                )
                if not phase13p_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "macro_repair_execution": False,
                "dataset_reassembly": False,
                "target_recalculation": False,
                "model_training": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13o_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13O summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_diagnostic_role",
            "Macro availability root-cause diagnostic only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13N passed",
            (not gates.get("require_phase13n_passed", True))
            or bool(row["phase13n_result_passed"]),
            f"phase13n_result_passed={bool(row['phase13n_result_passed'])}",
        ),
        _gate_row(
            "Source reports are present",
            (not gates.get("require_source_reports_present", True))
            or bool(row["source_reports_present"]),
            f"source_reports_present={bool(row['source_reports_present'])}",
        ),
        _gate_row(
            "Macro source was checked",
            (not gates.get("require_macro_source_checked", True))
            or bool(row["macro_source_checked"]),
            f"macro_source_checked={bool(row['macro_source_checked'])}",
        ),
        _gate_row(
            "Macro guard was loaded",
            (not gates.get("require_macro_guard_loaded", True))
            or int(row["macro_guard_rows"]) > 0,
            f"macro_guard_rows={int(row['macro_guard_rows'])}",
        ),
        _gate_row(
            "Macro repair panel was loaded",
            (not gates.get("require_macro_repair_panel_loaded", True))
            or int(row["repair_panel_profile_rows"]) > 0,
            f"repair_panel_profile_rows={int(row['repair_panel_profile_rows'])}",
        ),
        _gate_row(
            "Column mapping report exists",
            (not gates.get("require_column_mapping_report", True))
            or int(row["column_mapping_rows"]) > 0,
            f"column_mapping_rows={int(row['column_mapping_rows'])}",
        ),
        _gate_row(
            "Root-cause report exists",
            (not gates.get("require_root_cause_report", True))
            or int(row["root_cause_rows"]) > 0,
            f"root_cause={row['root_cause']}",
        ),
        _gate_row(
            "Phase 13P boundary is decision-only",
            (not gates.get("require_phase13p_boundary_decision_only", True))
            or bool(row["phase13p_boundary_passed"]),
            f"phase13p_boundary_passed={bool(row['phase13p_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks repair/model/signal/backtest/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Diagnostic role is correct",
            str(row["diagnostic_role"]) == required_role,
            f"diagnostic_role={row['diagnostic_role']}",
        ),
    ]
    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13o_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — macro availability root-cause diagnostic passed"
        if all_passed
        else "Failed macro availability root-cause diagnostic"
    )
    interpretation = (
        "Phase 13O diagnosed the macro source, column mapping, long-format status, "
        "existing repair panel, macro guard output, and root cause. It did not execute "
        "a macro repair, reassemble a dataset, recalculate targets, train models, "
        "create signals, run backtests, deploy paper trading, promote a candidate, "
        "or change the final candidate."
        if all_passed
        else "Phase 13O found a source, root-cause, boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13O",
                "diagnostic": "Macro availability root-cause diagnostic",
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


def save_phase13o_macro_availability_root_cause_diagnostic(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13o_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13o_source_report_check(phase_config)
    phase13n_result_check = build_phase13o_phase13n_result_check(phase_config)
    macro_source_inventory = build_phase13o_macro_source_inventory(phase_config)
    macro_source, macro_source_path = load_phase13o_macro_source(phase_config)
    macro_source_schema_profile = build_phase13o_macro_source_schema_profile(
        macro_source=macro_source,
        macro_source_path=macro_source_path,
        phase_config=phase_config,
    )
    column_mapping_report = build_phase13o_macro_column_mapping_report(
        macro_source=macro_source,
        phase_config=phase_config,
    )
    long_format_diagnostic = build_phase13o_macro_long_format_diagnostic(
        macro_source=macro_source,
        phase_config=phase_config,
    )

    reports = phase_config.get("source_reports", {})
    repair_panel = _read_csv_if_exists(reports.get("macro_repair_panel", ""))
    macro_guard = _read_csv_if_exists(reports.get("macro_guard_report", ""))

    repair_panel_profile = build_phase13o_existing_repair_panel_profile(repair_panel)
    macro_guard_profile = build_phase13o_macro_guard_profile(macro_guard)
    root_cause_report = build_phase13o_root_cause_report(
        macro_source_inventory=macro_source_inventory,
        column_mapping_report=column_mapping_report,
        long_format_diagnostic=long_format_diagnostic,
        repair_panel_profile=repair_panel_profile,
        macro_guard_profile=macro_guard_profile,
    )
    phase13p_boundary_check = build_phase13o_phase13p_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13o_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13n_result_check=phase13n_result_check,
        macro_source_inventory=macro_source_inventory,
        column_mapping_report=column_mapping_report,
        repair_panel_profile=repair_panel_profile,
        macro_guard_profile=macro_guard_profile,
        root_cause_report=root_cause_report,
        phase13p_boundary_check=phase13p_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13o_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13o_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13n_result_check": phase13n_result_check,
        "macro_source_inventory": macro_source_inventory,
        "macro_source_schema_profile": macro_source_schema_profile,
        "macro_column_mapping_report": column_mapping_report,
        "macro_long_format_diagnostic": long_format_diagnostic,
        "existing_repair_panel_profile": repair_panel_profile,
        "macro_guard_profile": macro_guard_profile,
        "root_cause_report": root_cause_report,
        "phase13p_boundary_check": phase13p_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13o_macro_root_cause_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13O — Macro Availability Root-Cause Diagnostic",
        sections={
            "Macro Source Inventory": macro_source_inventory,
            "Macro Source Schema Profile": macro_source_schema_profile,
            "Macro Column Mapping Report": column_mapping_report,
            "Long Format Diagnostic": long_format_diagnostic,
            "Existing Repair Panel Profile": repair_panel_profile,
            "Macro Guard Profile": macro_guard_profile,
            "Root Cause Report": root_cause_report,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13o_macro_availability_root_cause_diagnostic.md",
    )

    print("Wrote Phase 13O macro availability root-cause reports.")
    return outputs


def build_phase13p_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("phase13o_reports", {}).items():
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


def build_phase13p_phase13o_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase13o_reports", {})
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
                "check": "Phase 13O conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13O gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13p_config_flag_check(
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


def build_phase13p_repair_decision(
    *,
    phase_config: dict[str, Any],
    root_cause_report: pd.DataFrame,
) -> pd.DataFrame:
    policy = phase_config.get("decision_policy", {})

    if root_cause_report.empty:
        root_cause = "missing_root_cause_report"
        recommended_action = "keep_macro_blocked_and_rerun_diagnostic"
        repairability = "unknown"
    else:
        row = root_cause_report.iloc[0]
        root_cause = str(row.get("root_cause", "unknown"))
        recommended_action = str(row.get("recommended_action", "manual_review"))
        repairability = str(row.get("repairability", "unknown"))

    dataset_label_until_repair = str(
        policy.get(
            "dataset_label_until_repair_validated",
            "technical_only_macro_blocked_dataset_v1",
        )
    )

    return pd.DataFrame(
        [
            {
                "root_cause": root_cause,
                "recommended_action": recommended_action,
                "repairability": repairability,
                "macro_repair_execution_now": False,
                "dataset_reassembly_now": False,
                "dataset_label_until_repair_validated": dataset_label_until_repair,
                "future_repaired_label_only_after_audit": str(
                    policy.get(
                        "repaired_dataset_label_only_after_future_audit",
                        "multi_factor_technical_macro_dataset_v1",
                    )
                ),
                "phase13q_required_before_multifactor_claim": _bool_value(
                    policy.get(
                        "require_future_phase13q_repair_execution_before_macro_dataset_claim",
                        True,
                    )
                ),
            }
        ]
    )


def build_phase13p_repair_spec(phase_config: dict[str, Any]) -> pd.DataFrame:
    template = phase_config.get("repair_spec_template", {})
    return pd.DataFrame(
        [
            {
                "repair_scope": str(template.get("repair_scope", "")),
                "required_inputs": _join_list(template.get("required_inputs")),
                "required_outputs": _join_list(template.get("required_outputs")),
                "required_checks": _join_list(template.get("required_checks")),
                "forbidden_actions": _join_list(template.get("forbidden_actions")),
            }
        ]
    )


def build_phase13p_phase13q_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13q_boundary", {})
    checks = [
        (
            "phase13q_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "repair execution" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13q_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "model training" in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation" in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13q_may_execute_macro_repair",
            _bool_value(boundary.get("phase13q_may_execute_macro_repair", False)),
            _bool_value(boundary.get("phase13q_may_execute_macro_repair", False)),
        ),
        (
            "phase13q_may_reassemble_dataset_with_guard",
            _bool_value(boundary.get("phase13q_may_reassemble_dataset_with_guard", False)),
            _bool_value(boundary.get("phase13q_may_reassemble_dataset_with_guard", False)),
        ),
        (
            "phase13q_may_train_model",
            _bool_value(boundary.get("phase13q_may_train_model", True)),
            not _bool_value(boundary.get("phase13q_may_train_model", True)),
        ),
        (
            "phase13q_may_select_model",
            _bool_value(boundary.get("phase13q_may_select_model", True)),
            not _bool_value(boundary.get("phase13q_may_select_model", True)),
        ),
        (
            "phase13q_may_create_signal",
            _bool_value(boundary.get("phase13q_may_create_signal", True)),
            not _bool_value(boundary.get("phase13q_may_create_signal", True)),
        ),
        (
            "phase13q_may_run_backtest",
            _bool_value(boundary.get("phase13q_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13q_may_run_backtest", True)),
        ),
        (
            "phase13q_may_promote_candidate",
            _bool_value(boundary.get("phase13q_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13q_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13p_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No macro repair execution", "allow_macro_repair_execution"),
        ("No dataset reassembly", "allow_dataset_reassembly"),
        ("No target recalculation", "allow_target_recalculation"),
        ("No model training", "allow_model_training"),
        ("No model selection", "allow_model_selection"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No feature importance", "allow_feature_importance"),
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


def build_phase13p_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13o_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    repair_decision: pd.DataFrame,
    repair_spec: pd.DataFrame,
    phase13q_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13o_reports_present": bool(
                    report_inventory_check["present"].all()
                )
                if not report_inventory_check.empty
                else False,
                "phase13o_result_passed": bool(phase13o_result_check["passed"].all())
                if not phase13o_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "repair_decision_rows": int(len(repair_decision)),
                "repair_spec_rows": int(len(repair_spec)),
                "dataset_label_blocked_until_repair": str(
                    repair_decision.iloc[0]["dataset_label_until_repair_validated"]
                )
                if not repair_decision.empty
                else "",
                "phase13q_boundary_passed": bool(
                    phase13q_boundary_check["passed"].all()
                )
                if not phase13q_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "macro_repair_execution": False,
                "dataset_reassembly": False,
                "target_recalculation": False,
                "model_training": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13p_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13P summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_spec_role",
            "Macro feature repair decision and repair spec only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13O reports are present",
            (not gates.get("require_phase13o_reports_present", True))
            or bool(row["phase13o_reports_present"]),
            f"phase13o_reports_present={bool(row['phase13o_reports_present'])}",
        ),
        _gate_row(
            "Phase 13O conclusion and gates passed",
            (
                (not gates.get("require_phase13o_conclusion_passed", True))
                or bool(row["phase13o_result_passed"])
            )
            and (
                (not gates.get("require_phase13o_gate_report_passed", True))
                or bool(row["phase13o_result_passed"])
            ),
            f"phase13o_result_passed={bool(row['phase13o_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Repair decision exists",
            (not gates.get("require_repair_decision", True))
            or int(row["repair_decision_rows"]) > 0,
            f"repair_decision_rows={int(row['repair_decision_rows'])}",
        ),
        _gate_row(
            "Repair spec exists",
            (not gates.get("require_repair_spec", True))
            or int(row["repair_spec_rows"]) > 0,
            f"repair_spec_rows={int(row['repair_spec_rows'])}",
        ),
        _gate_row(
            "Dataset label remains blocked until repair",
            (not gates.get("require_dataset_label_blocked_until_repair", True))
            or str(row["dataset_label_blocked_until_repair"])
            == "technical_only_macro_blocked_dataset_v1",
            f"dataset_label_blocked_until_repair={row['dataset_label_blocked_until_repair']}",
        ),
        _gate_row(
            "Phase 13Q boundary is repair-only",
            (not gates.get("require_phase13q_boundary_repair_only", True))
            or bool(row["phase13q_boundary_passed"]),
            f"phase13q_boundary_passed={bool(row['phase13q_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks repair/model/signal/backtest/promotion",
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


def build_phase13p_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — macro feature repair decision/spec passed"
        if all_passed
        else "Failed macro feature repair decision/spec"
    )
    interpretation = (
        "Phase 13P produced a macro repair decision and repair spec while keeping "
        "the dataset labelled technical-only/macro-blocked until a future repair "
        "execution and audit passes. It did not execute repair, reassemble a dataset, "
        "recalculate targets, train models, create signals, run backtests, deploy "
        "paper trading, promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13P found a repair decision, boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13P",
                "diagnostic": "Macro feature repair decision/spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def save_phase13p_macro_feature_repair_decision_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13p_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase13p_report_inventory_check(phase_config)
    phase13o_result_check = build_phase13p_phase13o_result_check(phase_config)
    config_flag_check = build_phase13p_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )

    root_cause_report = _read_csv_if_exists(
        phase_config.get("phase13o_reports", {}).get("root_cause_report", "")
    )
    repair_decision = build_phase13p_repair_decision(
        phase_config=phase_config,
        root_cause_report=root_cause_report,
    )
    repair_spec = build_phase13p_repair_spec(phase_config)
    phase13q_boundary_check = build_phase13p_phase13q_boundary_check(phase_config)
    scope_boundary_check = build_phase13p_scope_boundary_check(phase_config)

    summary = build_phase13p_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13o_result_check=phase13o_result_check,
        config_flag_check=config_flag_check,
        repair_decision=repair_decision,
        repair_spec=repair_spec,
        phase13q_boundary_check=phase13q_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13p_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13p_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13o_result_check": phase13o_result_check,
        "config_flag_check": config_flag_check,
        "repair_decision": repair_decision,
        "repair_spec": repair_spec,
        "phase13q_boundary_check": phase13q_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13p_repair_spec_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13P — Macro Feature Repair Decision / Spec",
        sections={
            "Repair Decision": repair_decision,
            "Repair Spec": repair_spec,
            "Phase 13Q Boundary Check": phase13q_boundary_check,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path / "phase13p_macro_feature_repair_decision_spec.md",
    )

    print("Wrote Phase 13P macro feature repair decision/spec reports.")
    return outputs