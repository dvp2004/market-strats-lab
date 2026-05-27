from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE13K_CONFIG: dict[str, Any] = {
    "enabled": False,
    "planning_role": "Feature panel interpretation and model-readiness planning only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13J",
    "proposed_next_phase": "Phase 13L",
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "interpretation_policy": {},
    "model_readiness_plan": {},
    "phase13l_boundary": {},
    "gates": {
        "require_phase13j_passed": True,
        "require_source_reports_present": True,
        "require_feature_panel_loaded": True,
        "require_min_feature_panel_rows": True,
        "require_min_feature_ids": True,
        "require_required_families_present": True,
        "require_required_feature_ids_present": True,
        "require_state_distribution": True,
        "require_availability_summary": True,
        "require_leakage_clean": True,
        "require_model_readiness_plan": True,
        "require_phase13l_boundary_prereg_only": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_planning_role": (
            "Feature panel interpretation and model-readiness planning only"
        ),
    },
}


DEFAULT_PHASE13L_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Dataset split and ML target design pre-registration spec only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13K",
    "proposed_next_phase": "Phase 13M",
    "allow_dataset_assembly_execution": False,
    "allow_target_calculation": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_model_selection": False,
    "allow_feature_importance": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "phase13k_reports": {},
    "target_design": {},
    "secondary_target_design": {},
    "dataset_design": {},
    "split_design": {},
    "walk_forward_policy": {},
    "leakage_control_policy": [],
    "phase13m_boundary": {},
    "gates": {
        "require_phase13k_reports_present": True,
        "require_phase13k_conclusion_passed": True,
        "require_phase13k_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_primary_target_design": True,
        "require_secondary_target_design": True,
        "require_dataset_design": True,
        "require_split_design": True,
        "require_walk_forward_policy": True,
        "require_leakage_control_policy": True,
        "min_leakage_controls": 6,
        "require_phase13m_boundary_dataset_only": True,
        "require_no_dataset_assembly_execution": True,
        "require_no_target_calculation": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_feature_importance": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_spec_role": (
            "Dataset split and ML target design pre-registration spec only"
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


def _get_phase13k_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13K_CONFIG,
        config.get("phase13k_feature_panel_interpretation_model_readiness", {}),
    )


def _get_phase13l_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13L_CONFIG,
        config.get("phase13l_dataset_split_target_preregistration_spec", {}),
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


def build_phase13k_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase13k_phase13j_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13j_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13j_gate_report", ""))

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
                "check": "Phase 13J conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13J gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13k_feature_state_distribution(
    feature_panel: pd.DataFrame,
) -> pd.DataFrame:
    if feature_panel.empty:
        return pd.DataFrame(
            columns=[
                "family_id",
                "feature_id",
                "feature_state",
                "rows",
                "feature_state_ratio",
            ]
        )

    grouped = (
        feature_panel.groupby(["family_id", "feature_id", "feature_state"])
        .size()
        .reset_index(name="rows")
    )
    totals = grouped.groupby(["family_id", "feature_id"])["rows"].transform("sum")
    grouped["feature_state_ratio"] = grouped["rows"] / totals
    return grouped.sort_values(["family_id", "feature_id", "feature_state"])


def build_phase13k_feature_availability_summary(
    feature_panel: pd.DataFrame,
) -> pd.DataFrame:
    if feature_panel.empty:
        return pd.DataFrame(
            columns=[
                "family_id",
                "feature_id",
                "rows",
                "available_rows",
                "unavailable_rows",
                "available_ratio",
                "first_as_of_date",
                "last_as_of_date",
            ]
        )

    frame = feature_panel.copy()
    frame["is_available"] = frame["missingness_state"].astype(str).eq("available")

    out = (
        frame.groupby(["family_id", "feature_id"])
        .agg(
            rows=("feature_id", "size"),
            available_rows=("is_available", "sum"),
            first_as_of_date=("as_of_date", "min"),
            last_as_of_date=("as_of_date", "max"),
        )
        .reset_index()
    )
    out["unavailable_rows"] = out["rows"] - out["available_rows"]
    out["available_ratio"] = out["available_rows"] / out["rows"]
    return out[
        [
            "family_id",
            "feature_id",
            "rows",
            "available_rows",
            "unavailable_rows",
            "available_ratio",
            "first_as_of_date",
            "last_as_of_date",
        ]
    ]


def build_phase13k_family_coverage_summary(feature_panel: pd.DataFrame) -> pd.DataFrame:
    if feature_panel.empty:
        return pd.DataFrame(
            columns=[
                "family_id",
                "rows",
                "feature_count",
                "available_ratio",
                "first_as_of_date",
                "last_as_of_date",
            ]
        )

    frame = feature_panel.copy()
    frame["is_available"] = frame["missingness_state"].astype(str).eq("available")

    out = (
        frame.groupby("family_id")
        .agg(
            rows=("family_id", "size"),
            feature_count=("feature_id", "nunique"),
            available_ratio=("is_available", "mean"),
            first_as_of_date=("as_of_date", "min"),
            last_as_of_date=("as_of_date", "max"),
        )
        .reset_index()
    )
    return out


def build_phase13k_model_readiness_plan(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    plan = phase_config.get("model_readiness_plan", {})

    return pd.DataFrame(
        [
            {
                "dataset_unit": str(plan.get("dataset_unit", "")),
                "eligible_feature_inputs": _join_list(
                    plan.get("eligible_feature_inputs")
                ),
                "future_encoding_policy": _join_list(
                    plan.get("future_encoding_policy")
                ),
                "blocked_now": _join_list(plan.get("blocked_now")),
                "readiness_interpretation": str(
                    plan.get("readiness_interpretation", "")
                ),
            }
        ]
    )


def build_phase13k_phase13l_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13l_boundary", {})

    checks = [
        (
            "phase13l_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "pre-registration" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13l_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "model training" in str(boundary.get("forbidden_next_step", "")).lower()
            and "strategy backtest"
            in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation"
            in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13l_may_define_target",
            _bool_value(boundary.get("phase13l_may_define_target", False)),
            _bool_value(boundary.get("phase13l_may_define_target", False)),
        ),
        (
            "phase13l_may_define_split_policy",
            _bool_value(boundary.get("phase13l_may_define_split_policy", False)),
            _bool_value(boundary.get("phase13l_may_define_split_policy", False)),
        ),
        (
            "phase13l_may_assemble_dataset",
            _bool_value(boundary.get("phase13l_may_assemble_dataset", True)),
            not _bool_value(boundary.get("phase13l_may_assemble_dataset", True)),
        ),
        (
            "phase13l_may_train_model",
            _bool_value(boundary.get("phase13l_may_train_model", True)),
            not _bool_value(boundary.get("phase13l_may_train_model", True)),
        ),
        (
            "phase13l_may_create_signal",
            _bool_value(boundary.get("phase13l_may_create_signal", True)),
            not _bool_value(boundary.get("phase13l_may_create_signal", True)),
        ),
        (
            "phase13l_may_run_backtest",
            _bool_value(boundary.get("phase13l_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13l_may_run_backtest", True)),
        ),
        (
            "phase13l_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13l_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13l_may_deploy_paper_trading", True)),
        ),
        (
            "phase13l_may_promote_candidate",
            _bool_value(boundary.get("phase13l_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13l_may_promote_candidate", True)),
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


def build_phase13k_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13j_result_check: pd.DataFrame,
    feature_panel: pd.DataFrame,
    state_distribution: pd.DataFrame,
    availability_summary: pd.DataFrame,
    family_coverage_summary: pd.DataFrame,
    model_readiness_plan: pd.DataFrame,
    phase13l_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    policy = phase_config.get("interpretation_policy", {})
    required_ids = set(_as_list(policy.get("required_feature_ids")))
    actual_ids = (
        set(feature_panel["feature_id"].dropna().astype(str).tolist())
        if not feature_panel.empty and "feature_id" in feature_panel.columns
        else set()
    )
    required_families = set(_as_list(policy.get("required_families")))
    actual_families = (
        set(feature_panel["family_id"].dropna().astype(str).tolist())
        if not feature_panel.empty and "family_id" in feature_panel.columns
        else set()
    )
    leakage_flags = (
        int(feature_panel["leakage_flag"].map(_bool_value).sum())
        if not feature_panel.empty and "leakage_flag" in feature_panel.columns
        else 999999
    )
    available_ratio = (
        float(feature_panel["missingness_state"].astype(str).eq("available").mean())
        if not feature_panel.empty and "missingness_state" in feature_panel.columns
        else 0.0
    )

    return pd.DataFrame(
        [
            {
                "planning_role": str(phase_config.get("planning_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase13j_result_passed": bool(phase13j_result_check["passed"].all())
                if not phase13j_result_check.empty
                else False,
                "feature_panel_rows": int(len(feature_panel)),
                "feature_id_count": int(len(actual_ids)),
                "family_count": int(len(actual_families)),
                "required_feature_ids_present": required_ids.issubset(actual_ids),
                "required_families_present": required_families.issubset(
                    actual_families
                ),
                "available_ratio": available_ratio,
                "leakage_flag_count": leakage_flags,
                "state_distribution_rows": int(len(state_distribution)),
                "availability_summary_rows": int(len(availability_summary)),
                "family_coverage_rows": int(len(family_coverage_summary)),
                "model_readiness_plan_rows": int(len(model_readiness_plan)),
                "phase13l_boundary_passed": bool(
                    phase13l_boundary_check["passed"].all()
                )
                if not phase13l_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "signal_creation": False,
                "strategy_backtest": False,
                "model_training": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13k_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    policy = phase_config.get("interpretation_policy", {})

    if summary.empty:
        return pd.DataFrame(
            [_gate_row("Phase 13K summary exists", False, "No summary.")]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_planning_role",
            "Feature panel interpretation and model-readiness planning only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13J passed",
            (not gates.get("require_phase13j_passed", True))
            or bool(row["phase13j_result_passed"]),
            f"phase13j_result_passed={bool(row['phase13j_result_passed'])}",
        ),
        _gate_row(
            "Source reports are present",
            (not gates.get("require_source_reports_present", True))
            or bool(row["source_reports_present"]),
            f"source_reports_present={bool(row['source_reports_present'])}",
        ),
        _gate_row(
            "Feature panel loaded",
            (not gates.get("require_feature_panel_loaded", True))
            or int(row["feature_panel_rows"]) > 0,
            f"feature_panel_rows={int(row['feature_panel_rows'])}",
        ),
        _gate_row(
            "Minimum feature-panel rows reached",
            (not gates.get("require_min_feature_panel_rows", True))
            or int(row["feature_panel_rows"])
            >= int(policy.get("min_feature_panel_rows", 100)),
            f"feature_panel_rows={int(row['feature_panel_rows'])}",
        ),
        _gate_row(
            "Minimum feature IDs reached",
            (not gates.get("require_min_feature_ids", True))
            or int(row["feature_id_count"]) >= int(policy.get("min_feature_ids", 8)),
            f"feature_id_count={int(row['feature_id_count'])}",
        ),
        _gate_row(
            "Required families are present",
            (not gates.get("require_required_families_present", True))
            or bool(row["required_families_present"]),
            f"required_families_present={bool(row['required_families_present'])}",
        ),
        _gate_row(
            "Required feature IDs are present",
            (not gates.get("require_required_feature_ids_present", True))
            or bool(row["required_feature_ids_present"]),
            f"required_feature_ids_present="
            f"{bool(row['required_feature_ids_present'])}",
        ),
        _gate_row(
            "State distribution exists",
            (not gates.get("require_state_distribution", True))
            or int(row["state_distribution_rows"]) > 0,
            f"state_distribution_rows={int(row['state_distribution_rows'])}",
        ),
        _gate_row(
            "Availability summary exists",
            (not gates.get("require_availability_summary", True))
            or int(row["availability_summary_rows"]) > 0,
            f"availability_summary_rows={int(row['availability_summary_rows'])}",
        ),
        _gate_row(
            "Leakage remains clean",
            (not gates.get("require_leakage_clean", True))
            or int(row["leakage_flag_count"]) <= int(policy.get("max_leakage_flags", 0)),
            f"leakage_flag_count={int(row['leakage_flag_count'])}",
        ),
        _gate_row(
            "Model-readiness plan exists",
            (not gates.get("require_model_readiness_plan", True))
            or int(row["model_readiness_plan_rows"]) > 0,
            f"model_readiness_plan_rows={int(row['model_readiness_plan_rows'])}",
        ),
        _gate_row(
            "Phase 13L boundary is pre-registration-only",
            (not gates.get("require_phase13l_boundary_prereg_only", True))
            or bool(row["phase13l_boundary_passed"]),
            f"phase13l_boundary_passed={bool(row['phase13l_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks signal/model/backtest/paper-trading/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Planning role is correct",
            str(row["planning_role"]) == required_role,
            f"planning_role={row['planning_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13k_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — feature panel interpretation and model-readiness planning passed"
        if all_passed
        else "Failed feature panel interpretation and model-readiness planning"
    )
    interpretation = (
        "Phase 13K interpreted feature-state distributions, availability, "
        "family coverage, leakage cleanliness, and model-readiness boundaries. "
        "It did not assemble a model dataset, calculate a target, train a model, "
        "create a signal, run a backtest, deploy paper trading, promote a candidate, "
        "or change the final candidate."
        if all_passed
        else "Phase 13K found an interpretation, readiness, leakage, boundary, "
        "or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13K",
                "diagnostic": "Feature panel interpretation and model-readiness planning",
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


def save_phase13k_feature_panel_interpretation_model_readiness(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13k_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13k_source_report_check(phase_config)
    phase13j_result_check = build_phase13k_phase13j_result_check(phase_config)

    source_reports = phase_config.get("source_reports", {})
    feature_panel = _read_csv_if_exists(source_reports.get("feature_panel", ""))

    state_distribution = build_phase13k_feature_state_distribution(feature_panel)
    availability_summary = build_phase13k_feature_availability_summary(feature_panel)
    family_coverage_summary = build_phase13k_family_coverage_summary(feature_panel)
    model_readiness_plan = build_phase13k_model_readiness_plan(phase_config)
    phase13l_boundary_check = build_phase13k_phase13l_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13k_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13j_result_check=phase13j_result_check,
        feature_panel=feature_panel,
        state_distribution=state_distribution,
        availability_summary=availability_summary,
        family_coverage_summary=family_coverage_summary,
        model_readiness_plan=model_readiness_plan,
        phase13l_boundary_check=phase13l_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13k_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13k_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13j_result_check": phase13j_result_check,
        "feature_state_distribution": state_distribution,
        "feature_availability_summary": availability_summary,
        "family_coverage_summary": family_coverage_summary,
        "model_readiness_plan": model_readiness_plan,
        "phase13l_boundary_check": phase13l_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13k_interpretation_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13K — Feature Panel Interpretation / Model-Readiness Planning",
        sections={
            "Source Report Check": source_report_check,
            "Phase 13J Result Check": phase13j_result_check,
            "Feature State Distribution": state_distribution,
            "Feature Availability Summary": availability_summary,
            "Family Coverage Summary": family_coverage_summary,
            "Model Readiness Plan": model_readiness_plan,
            "Phase 13L Boundary Check": phase13l_boundary_check,
            "Scope Boundary Check": scope_boundary_check,
            "Summary": summary,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13k_feature_panel_interpretation_model_readiness.md",
    )

    print("Wrote Phase 13K feature panel interpretation/model-readiness reports.")
    return outputs


def build_phase13l_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("phase13k_reports", {}).items():
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


def build_phase13l_phase13k_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase13k_reports", {})
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
                "check": "Phase 13K conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13K gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13l_config_flag_check(
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


def _single_row_from_dict(data: dict[str, Any]) -> pd.DataFrame:
    row = {}

    for key, value in data.items():
        if isinstance(value, list):
            row[key] = _join_list(value)
        else:
            row[key] = value

    return pd.DataFrame([row])


def build_phase13l_leakage_control_policy(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("leakage_control_policy")):
        rows.append(
            {
                "control_id": str(item.get("control_id", "")),
                "control": str(item.get("control", "")),
                "required": _bool_value(item.get("required", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase13l_phase13m_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13m_boundary", {})

    checks = [
        (
            "phase13m_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "dataset assembly" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13m_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "model training" in str(boundary.get("forbidden_next_step", "")).lower()
            and "strategy backtest"
            in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation"
            in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13m_may_assemble_dataset",
            _bool_value(boundary.get("phase13m_may_assemble_dataset", False)),
            _bool_value(boundary.get("phase13m_may_assemble_dataset", False)),
        ),
        (
            "phase13m_may_calculate_registered_targets",
            _bool_value(
                boundary.get("phase13m_may_calculate_registered_targets", False)
            ),
            _bool_value(
                boundary.get("phase13m_may_calculate_registered_targets", False)
            ),
        ),
        (
            "phase13m_may_train_model",
            _bool_value(boundary.get("phase13m_may_train_model", True)),
            not _bool_value(boundary.get("phase13m_may_train_model", True)),
        ),
        (
            "phase13m_may_select_model",
            _bool_value(boundary.get("phase13m_may_select_model", True)),
            not _bool_value(boundary.get("phase13m_may_select_model", True)),
        ),
        (
            "phase13m_may_create_signal",
            _bool_value(boundary.get("phase13m_may_create_signal", True)),
            not _bool_value(boundary.get("phase13m_may_create_signal", True)),
        ),
        (
            "phase13m_may_run_backtest",
            _bool_value(boundary.get("phase13m_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13m_may_run_backtest", True)),
        ),
        (
            "phase13m_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13m_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13m_may_deploy_paper_trading", True)),
        ),
        (
            "phase13m_may_promote_candidate",
            _bool_value(boundary.get("phase13m_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13m_may_promote_candidate", True)),
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


def build_phase13l_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No dataset assembly execution", "allow_dataset_assembly_execution"),
        ("No target calculation", "allow_target_calculation"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No model training", "allow_model_training"),
        ("No model selection", "allow_model_selection"),
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


def build_phase13l_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13k_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    target_design: pd.DataFrame,
    secondary_target_design: pd.DataFrame,
    dataset_design: pd.DataFrame,
    split_design: pd.DataFrame,
    walk_forward_policy: pd.DataFrame,
    leakage_control_policy: pd.DataFrame,
    phase13m_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13k_reports_present": bool(
                    report_inventory_check["present"].all()
                )
                if not report_inventory_check.empty
                else False,
                "phase13k_result_passed": bool(phase13k_result_check["passed"].all())
                if not phase13k_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "primary_target_defined": not target_design.empty,
                "secondary_target_defined": not secondary_target_design.empty,
                "dataset_design_defined": not dataset_design.empty,
                "split_design_defined": not split_design.empty,
                "walk_forward_policy_defined": not walk_forward_policy.empty,
                "leakage_control_count": int(len(leakage_control_policy)),
                "leakage_controls_required": bool(
                    leakage_control_policy["required"].map(_bool_value).all()
                )
                if not leakage_control_policy.empty
                else False,
                "phase13m_boundary_passed": bool(
                    phase13m_boundary_check["passed"].all()
                )
                if not phase13m_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "dataset_assembly_execution": False,
                "target_calculation": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "model_training": False,
                "model_selection": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13l_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [_gate_row("Phase 13L summary exists", False, "No summary.")]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_spec_role",
            "Dataset split and ML target design pre-registration spec only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13K reports are present",
            (not gates.get("require_phase13k_reports_present", True))
            or bool(row["phase13k_reports_present"]),
            f"phase13k_reports_present={bool(row['phase13k_reports_present'])}",
        ),
        _gate_row(
            "Phase 13K conclusion and gates passed",
            (
                (not gates.get("require_phase13k_conclusion_passed", True))
                or bool(row["phase13k_result_passed"])
            )
            and (
                (not gates.get("require_phase13k_gate_report_passed", True))
                or bool(row["phase13k_result_passed"])
            ),
            f"phase13k_result_passed={bool(row['phase13k_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            (not gates.get("require_config_flags_clean_for_run", True))
            or bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Primary target design is defined",
            (not gates.get("require_primary_target_design", True))
            or bool(row["primary_target_defined"]),
            f"primary_target_defined={bool(row['primary_target_defined'])}",
        ),
        _gate_row(
            "Secondary target design is defined",
            (not gates.get("require_secondary_target_design", True))
            or bool(row["secondary_target_defined"]),
            f"secondary_target_defined={bool(row['secondary_target_defined'])}",
        ),
        _gate_row(
            "Dataset design is defined",
            (not gates.get("require_dataset_design", True))
            or bool(row["dataset_design_defined"]),
            f"dataset_design_defined={bool(row['dataset_design_defined'])}",
        ),
        _gate_row(
            "Split design is defined",
            (not gates.get("require_split_design", True))
            or bool(row["split_design_defined"]),
            f"split_design_defined={bool(row['split_design_defined'])}",
        ),
        _gate_row(
            "Walk-forward policy is defined",
            (not gates.get("require_walk_forward_policy", True))
            or bool(row["walk_forward_policy_defined"]),
            f"walk_forward_policy_defined={bool(row['walk_forward_policy_defined'])}",
        ),
        _gate_row(
            "Leakage controls are defined",
            (not gates.get("require_leakage_control_policy", True))
            or (
                int(row["leakage_control_count"])
                >= int(gates.get("min_leakage_controls", 6))
                and bool(row["leakage_controls_required"])
            ),
            f"leakage_control_count={int(row['leakage_control_count'])}",
        ),
        _gate_row(
            "Phase 13M boundary is dataset-only",
            (not gates.get("require_phase13m_boundary_dataset_only", True))
            or bool(row["phase13m_boundary_passed"]),
            f"phase13m_boundary_passed={bool(row['phase13m_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks dataset/model/signal/backtest/paper-trading/promotion",
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


def build_phase13l_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — dataset split and ML target pre-registration spec passed"
        if all_passed
        else "Failed dataset split and ML target pre-registration spec"
    )
    interpretation = (
        "Phase 13L pre-registered ML target design, dataset design, split design, "
        "walk-forward policy, and leakage controls. It did not assemble a dataset, "
        "calculate a target, train a model, select a model, create a signal, run a "
        "backtest, deploy paper trading, promote a candidate, or change the final "
        "candidate."
        if all_passed
        else "Phase 13L found a target, split, walk-forward, leakage, boundary, "
        "or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13L",
                "diagnostic": "Dataset split and ML target pre-registration spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def save_phase13l_dataset_split_target_preregistration_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13l_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase13l_report_inventory_check(phase_config)
    phase13k_result_check = build_phase13l_phase13k_result_check(phase_config)
    config_flag_check = build_phase13l_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )

    target_design = _single_row_from_dict(phase_config.get("target_design", {}))
    secondary_target_design = _single_row_from_dict(
        phase_config.get("secondary_target_design", {})
    )
    dataset_design = _single_row_from_dict(phase_config.get("dataset_design", {}))
    split_design = _single_row_from_dict(phase_config.get("split_design", {}))
    walk_forward_policy = _single_row_from_dict(
        phase_config.get("walk_forward_policy", {})
    )
    leakage_control_policy = build_phase13l_leakage_control_policy(phase_config)
    phase13m_boundary_check = build_phase13l_phase13m_boundary_check(phase_config)
    scope_boundary_check = build_phase13l_scope_boundary_check(phase_config)

    summary = build_phase13l_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13k_result_check=phase13k_result_check,
        config_flag_check=config_flag_check,
        target_design=target_design,
        secondary_target_design=secondary_target_design,
        dataset_design=dataset_design,
        split_design=split_design,
        walk_forward_policy=walk_forward_policy,
        leakage_control_policy=leakage_control_policy,
        phase13m_boundary_check=phase13m_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13l_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13l_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13k_result_check": phase13k_result_check,
        "config_flag_check": config_flag_check,
        "target_design": target_design,
        "secondary_target_design": secondary_target_design,
        "dataset_design": dataset_design,
        "split_design": split_design,
        "walk_forward_policy": walk_forward_policy,
        "leakage_control_policy": leakage_control_policy,
        "phase13m_boundary_check": phase13m_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13l_prereg_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13L — Dataset Split / ML Target Pre-Registration Spec",
        sections={
            "Report Inventory Check": report_inventory_check,
            "Phase 13K Result Check": phase13k_result_check,
            "Config Flag Check": config_flag_check,
            "Primary Target Design": target_design,
            "Secondary Target Design": secondary_target_design,
            "Dataset Design": dataset_design,
            "Split Design": split_design,
            "Walk-Forward Policy": walk_forward_policy,
            "Leakage Control Policy": leakage_control_policy,
            "Phase 13M Boundary Check": phase13m_boundary_check,
            "Scope Boundary Check": scope_boundary_check,
            "Summary": summary,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13l_dataset_split_target_preregistration_spec.md",
    )

    print("Wrote Phase 13L dataset split / ML target pre-registration reports.")
    return outputs