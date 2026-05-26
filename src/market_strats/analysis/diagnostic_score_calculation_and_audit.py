from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE12C_CONFIG: dict[str, Any] = {
    "enabled": False,
    "calculation_role": "Diagnostic score calculation only",
    "phase_branch": "Phase 12 regime score calculation",
    "source_phase": "Phase 12B",
    "proposed_next_phase": "Phase 12D",
    "allow_diagnostic_score_calculation": True,
    "allow_numeric_score_output": False,
    "allow_empirical_return_weights": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "source_reports": {},
    "component_state_inputs": [],
    "scoring_policy": {
        "score_id": "pre_registered_three_component_regime_score",
        "allowed_states": ["supportive", "neutral", "fragile"],
        "formula_source": "Phase 12A pre-registered formula grammar",
        "calculation_scope": "static_branch_level_diagnostic_score",
        "aggregation_method": (
            "categorical_equal_vote_with_validation_risk_control"
        ),
        "empirical_weights_allowed": False,
        "numeric_weights_allowed": False,
        "returns_used": False,
        "validation_risk_control": {
            "enabled": True,
            "fragile_validation_risk_caps_supportive_score": True,
            "fragile_validation_risk_with_no_supportive_majority_forces_fragile": True,
        },
    },
    "phase12d_boundary": {},
    "gates": {
        "require_source_reports_present": True,
        "require_phase12b_passed": True,
        "require_eligible_components_present": True,
        "require_component_states_allowed": True,
        "require_blocked_components_excluded": True,
        "require_existing_project_sources_only": True,
        "require_no_numeric_score_output": True,
        "require_no_empirical_return_weights": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "require_phase12d_boundary_audit_only": True,
        "required_calculation_role": "Diagnostic score calculation only",
    },
}


DEFAULT_PHASE12D_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Diagnostic score distribution and content audit only",
    "phase_branch": "Phase 12 regime score calculation",
    "source_phase": "Phase 12C",
    "proposed_next_phase": "Phase 12E",
    "allow_score_interpretation": True,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "source_score_reports": {},
    "expected_score_states": ["supportive", "neutral", "fragile"],
    "expected_component_count": 3,
    "expected_aggregate_score_count": 1,
    "phase12e_boundary": {},
    "gates": {
        "require_phase12c_reports_present": True,
        "require_phase12c_conclusion_passed": True,
        "require_component_state_distribution": True,
        "require_aggregate_score_valid": True,
        "require_score_states_allowed": True,
        "require_component_count_expected": True,
        "require_single_aggregate_score": True,
        "require_no_numeric_score_columns": True,
        "require_no_signal_columns": True,
        "require_no_backtest_columns": True,
        "require_no_empirical_weight_columns": True,
        "require_no_candidate_promotion": True,
        "require_phase12e_boundary_interpretation_only": True,
        "required_audit_role": (
            "Diagnostic score distribution and content audit only"
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


def _get_phase12c_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE12C_CONFIG,
        config.get("phase12c_diagnostic_score_calculation", {}),
    )


def _get_phase12d_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE12D_CONFIG,
        config.get("phase12d_diagnostic_score_distribution_audit", {}),
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


def build_phase12c_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, path in phase_config.get("source_reports", {}).items():
        file_path = Path(str(path))
        frame = _read_csv_if_exists(file_path)
        rows.append(
            {
                "report_key": str(key),
                "path": str(file_path),
                "present": file_path.exists(),
                "rows": int(len(frame)),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12c_phase12b_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase12b_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase12b_gate_report", ""))

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
            "check": "Phase 12B conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 12B gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12c_component_state_panel(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in _as_list(phase_config.get("component_state_inputs")):
        rows.append(
            {
                "component_id": str(item.get("component_id", "")),
                "family": str(item.get("family", "")),
                "diagnostic_state": str(item.get("diagnostic_state", "")),
                "state_source": str(item.get("state_source", "")),
                "state_role": str(item.get("state_role", "")),
                "source_is_existing_project_report": _bool_value(
                    item.get("source_is_existing_project_report", False)
                ),
                "trading_allowed": _bool_value(item.get("trading_allowed", True)),
                "signal_allowed": _bool_value(item.get("signal_allowed", True)),
            }
        )
    return pd.DataFrame(rows)


def build_phase12c_component_state_distribution(
    component_state_panel: pd.DataFrame,
) -> pd.DataFrame:
    if component_state_panel.empty:
        return pd.DataFrame(columns=["diagnostic_state", "component_count"])

    return (
        component_state_panel.groupby("diagnostic_state", as_index=False)
        .size()
        .rename(columns={"size": "component_count"})
        .sort_values("diagnostic_state")
        .reset_index(drop=True)
    )


def _raw_vote_state(states: list[str]) -> str:
    counts = {
        "supportive": states.count("supportive"),
        "neutral": states.count("neutral"),
        "fragile": states.count("fragile"),
    }

    if counts["supportive"] > counts["neutral"] and counts["supportive"] > counts["fragile"]:
        return "supportive"

    if counts["fragile"] > counts["supportive"] and counts["fragile"] >= counts["neutral"]:
        return "fragile"

    return "neutral"


def _apply_validation_risk_control(
    *,
    raw_state: str,
    component_state_panel: pd.DataFrame,
    phase_config: dict[str, Any],
) -> tuple[str, str]:
    policy = phase_config.get("scoring_policy", {})
    control = policy.get("validation_risk_control", {})

    if not _bool_value(control.get("enabled", True)):
        return raw_state, "validation_risk_control_disabled"

    validation_rows = component_state_panel[
        component_state_panel["component_id"].astype(str)
        == "validation_risk_context"
    ]

    if validation_rows.empty:
        return "fragile", "validation_risk_missing_default_fragile"

    validation_state = str(validation_rows.iloc[0]["diagnostic_state"])

    if validation_state != "fragile":
        return raw_state, "validation_risk_not_fragile_no_override"

    supportive_count = int(
        component_state_panel["diagnostic_state"].astype(str).eq("supportive").sum()
    )

    if raw_state == "supportive" and _bool_value(
        control.get("fragile_validation_risk_caps_supportive_score", True)
    ):
        return "neutral", "validation_risk_fragile_capped_supportive_to_neutral"

    if supportive_count < 2 and _bool_value(
        control.get(
            "fragile_validation_risk_with_no_supportive_majority_forces_fragile",
            True,
        )
    ):
        return "fragile", "validation_risk_fragile_without_supportive_majority"

    return raw_state, "validation_risk_fragile_no_override"


def build_phase12c_aggregate_score(
    *,
    phase_config: dict[str, Any],
    component_state_panel: pd.DataFrame,
) -> pd.DataFrame:
    states = component_state_panel["diagnostic_state"].astype(str).tolist()
    raw_state = _raw_vote_state(states)
    final_state, override_reason = _apply_validation_risk_control(
        raw_state=raw_state,
        component_state_panel=component_state_panel,
        phase_config=phase_config,
    )

    policy = phase_config.get("scoring_policy", {})

    return pd.DataFrame(
        [
            {
                "score_id": str(policy.get("score_id", "")),
                "calculation_scope": str(policy.get("calculation_scope", "")),
                "aggregation_method": str(policy.get("aggregation_method", "")),
                "supportive_component_count": int(states.count("supportive")),
                "neutral_component_count": int(states.count("neutral")),
                "fragile_component_count": int(states.count("fragile")),
                "raw_vote_state": raw_state,
                "diagnostic_score_state": final_state,
                "validation_risk_override_reason": override_reason,
                "formula_source": str(policy.get("formula_source", "")),
                "empirical_weights_allowed": _bool_value(
                    policy.get("empirical_weights_allowed", True)
                ),
                "numeric_weights_allowed": _bool_value(
                    policy.get("numeric_weights_allowed", True)
                ),
                "returns_used": _bool_value(policy.get("returns_used", True)),
                "trading_signal_created": False,
                "strategy_backtest_run": False,
                "candidate_promoted": False,
            }
        ]
    )


def build_phase12c_phase12d_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase12d_boundary", {})
    rows = [
        {
            "boundary_item": "phase12d_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "distribution" in str(
                boundary.get("allowed_next_step", "")
            ).lower()
            and "audit" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase12d_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase12d_may_audit_score_distribution",
            "value": _bool_value(
                boundary.get("phase12d_may_audit_score_distribution", False)
            ),
            "passed": _bool_value(
                boundary.get("phase12d_may_audit_score_distribution", False)
            ),
        },
        {
            "boundary_item": "phase12d_may_create_signal",
            "value": _bool_value(boundary.get("phase12d_may_create_signal", True)),
            "passed": not _bool_value(
                boundary.get("phase12d_may_create_signal", True)
            ),
        },
        {
            "boundary_item": "phase12d_may_test_strategy",
            "value": _bool_value(boundary.get("phase12d_may_test_strategy", True)),
            "passed": not _bool_value(
                boundary.get("phase12d_may_test_strategy", True)
            ),
        },
        {
            "boundary_item": "phase12d_may_assign_empirical_weights",
            "value": _bool_value(
                boundary.get("phase12d_may_assign_empirical_weights", True)
            ),
            "passed": not _bool_value(
                boundary.get("phase12d_may_assign_empirical_weights", True)
            ),
        },
        {
            "boundary_item": "phase12d_may_train_model",
            "value": _bool_value(boundary.get("phase12d_may_train_model", True)),
            "passed": not _bool_value(
                boundary.get("phase12d_may_train_model", True)
            ),
        },
        {
            "boundary_item": "phase12d_may_ingest_new_data",
            "value": _bool_value(boundary.get("phase12d_may_ingest_new_data", True)),
            "passed": not _bool_value(
                boundary.get("phase12d_may_ingest_new_data", True)
            ),
        },
        {
            "boundary_item": "phase12d_may_promote_candidate",
            "value": _bool_value(
                boundary.get("phase12d_may_promote_candidate", True)
            ),
            "passed": not _bool_value(
                boundary.get("phase12d_may_promote_candidate", True)
            ),
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12c_scope_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    checks = [
        ("No numeric score output", "allow_numeric_score_output"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No model training", "allow_model_training"),
        ("No new data ingestion", "allow_new_data_ingestion"),
        ("No candidate promotion", "allow_candidate_promotion"),
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


def build_phase12c_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase12b_result_check: pd.DataFrame,
    component_state_panel: pd.DataFrame,
    aggregate_score: pd.DataFrame,
    blocked_components: pd.DataFrame,
    phase12d_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    allowed_states = set(
        str(item) for item in _as_list(
            phase_config.get("scoring_policy", {}).get("allowed_states")
        )
    )
    actual_states = set(
        component_state_panel["diagnostic_state"].dropna().astype(str).tolist()
    )
    aggregate_state = (
        str(aggregate_score.iloc[0]["diagnostic_score_state"])
        if not aggregate_score.empty
        else ""
    )
    blocked_ids = (
        set(blocked_components["component_id"].dropna().astype(str).tolist())
        if not blocked_components.empty
        else set()
    )
    used_component_ids = set(
        component_state_panel["component_id"].dropna().astype(str).tolist()
    )

    return pd.DataFrame(
        [
            {
                "calculation_role": str(phase_config.get("calculation_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase12b_result_passed": bool(phase12b_result_check["passed"].all())
                if not phase12b_result_check.empty
                else False,
                "component_count": int(len(component_state_panel)),
                "component_states_allowed": actual_states.issubset(allowed_states),
                "aggregate_score_state": aggregate_state,
                "aggregate_score_allowed": aggregate_state in allowed_states,
                "blocked_components_excluded": len(blocked_ids & used_component_ids)
                == 0,
                "existing_project_sources_only": bool(
                    component_state_panel["source_is_existing_project_report"]
                    .map(_bool_value)
                    .all()
                )
                if not component_state_panel.empty
                else False,
                "component_rows_non_signal": bool(
                    component_state_panel["trading_allowed"]
                    .map(_bool_value)
                    .eq(False)
                    .all()
                    and component_state_panel["signal_allowed"]
                    .map(_bool_value)
                    .eq(False)
                    .all()
                )
                if not component_state_panel.empty
                else False,
                "aggregate_no_empirical_weights": not _bool_value(
                    aggregate_score.iloc[0]["empirical_weights_allowed"]
                )
                if not aggregate_score.empty
                else False,
                "aggregate_no_numeric_weights": not _bool_value(
                    aggregate_score.iloc[0]["numeric_weights_allowed"]
                )
                if not aggregate_score.empty
                else False,
                "aggregate_no_returns_used": not _bool_value(
                    aggregate_score.iloc[0]["returns_used"]
                )
                if not aggregate_score.empty
                else False,
                "aggregate_no_signal_backtest_promotion": bool(
                    not _bool_value(aggregate_score.iloc[0]["trading_signal_created"])
                    and not _bool_value(
                        aggregate_score.iloc[0]["strategy_backtest_run"]
                    )
                    and not _bool_value(aggregate_score.iloc[0]["candidate_promoted"])
                )
                if not aggregate_score.empty
                else False,
                "phase12d_boundary_passed": bool(
                    phase12d_boundary_check["passed"].all()
                )
                if not phase12d_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "strategy_promotion": False,
                "candidate_promotion": False,
            }
        ]
    )


def build_phase12c_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 12C summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get("required_calculation_role", "Diagnostic score calculation only")
    )

    rows = [
        _gate_row(
            "Source reports are present",
            (not gates.get("require_source_reports_present", True))
            or bool(row["source_reports_present"]),
            f"source_reports_present={bool(row['source_reports_present'])}",
        ),
        _gate_row(
            "Phase 12B remains passed",
            (not gates.get("require_phase12b_passed", True))
            or bool(row["phase12b_result_passed"]),
            f"phase12b_result_passed={bool(row['phase12b_result_passed'])}",
        ),
        _gate_row(
            "Eligible components are present",
            (not gates.get("require_eligible_components_present", True))
            or int(row["component_count"]) >= 3,
            f"component_count={int(row['component_count'])}",
        ),
        _gate_row(
            "Component states are allowed",
            (not gates.get("require_component_states_allowed", True))
            or bool(row["component_states_allowed"])
            and bool(row["aggregate_score_allowed"]),
            (
                f"component_states_allowed={bool(row['component_states_allowed'])}; "
                f"aggregate_score_allowed={bool(row['aggregate_score_allowed'])}"
            ),
        ),
        _gate_row(
            "Blocked components are excluded",
            (not gates.get("require_blocked_components_excluded", True))
            or bool(row["blocked_components_excluded"]),
            f"blocked_components_excluded={bool(row['blocked_components_excluded'])}",
        ),
        _gate_row(
            "Only existing project sources are used",
            (not gates.get("require_existing_project_sources_only", True))
            or bool(row["existing_project_sources_only"]),
            (
                "existing_project_sources_only="
                f"{bool(row['existing_project_sources_only'])}"
            ),
        ),
        _gate_row(
            "No numeric score output / empirical weights / returns are used",
            bool(row["aggregate_no_empirical_weights"])
            and bool(row["aggregate_no_numeric_weights"])
            and bool(row["aggregate_no_returns_used"]),
            (
                f"no_empirical={bool(row['aggregate_no_empirical_weights'])}; "
                f"no_numeric_weights={bool(row['aggregate_no_numeric_weights'])}; "
                f"no_returns={bool(row['aggregate_no_returns_used'])}"
            ),
        ),
        _gate_row(
            "Component rows are non-signal",
            bool(row["component_rows_non_signal"]),
            f"component_rows_non_signal={bool(row['component_rows_non_signal'])}",
        ),
        _gate_row(
            "No signal/backtest/promotion exists",
            bool(row["aggregate_no_signal_backtest_promotion"]),
            (
                "aggregate_no_signal_backtest_promotion="
                f"{bool(row['aggregate_no_signal_backtest_promotion'])}"
            ),
        ),
        _gate_row(
            "Phase 12D boundary is audit-only",
            (not gates.get("require_phase12d_boundary_audit_only", True))
            or bool(row["phase12d_boundary_passed"]),
            f"phase12d_boundary_passed={bool(row['phase12d_boundary_passed'])}",
        ),
        _gate_row(
            "Scope boundary passed",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Calculation role is correct",
            str(row["calculation_role"]) == required_role,
            f"calculation_role={row['calculation_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())
    return gate_report


def build_phase12c_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    verdict = (
        "Completed — diagnostic score calculation passed"
        if all_passed
        else "Failed diagnostic score calculation"
    )
    interpretation = (
        "Phase 12C calculated a categorical diagnostic regime score from the "
        "pre-registered Phase 12A grammar. It did not create a signal, allocation "
        "rule, strategy backtest, empirical weights, model, new data ingestion, "
        "candidate promotion, or final-candidate change."
        if all_passed
        else "Phase 12C found a score-calculation, source, state, or boundary issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 12C",
                "diagnostic": "Diagnostic score calculation",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase12c_markdown(
    *,
    source_report_check: pd.DataFrame,
    phase12b_result_check: pd.DataFrame,
    component_state_panel: pd.DataFrame,
    component_state_distribution: pd.DataFrame,
    aggregate_score: pd.DataFrame,
    phase12d_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 12C — Diagnostic Score Calculation",
        "",
        "This phase calculates a categorical diagnostic score only. It does not "
        "create signals, allocation rules, backtests, models, new data ingestion, "
        "or candidate promotion.",
        "",
        "## Source Report Check",
        source_report_check.to_markdown(index=False),
        "",
        "## Phase 12B Result Check",
        phase12b_result_check.to_markdown(index=False),
        "",
        "## Component State Panel",
        component_state_panel.to_markdown(index=False),
        "",
        "## Component State Distribution",
        component_state_distribution.to_markdown(index=False),
        "",
        "## Aggregate Score",
        aggregate_score.to_markdown(index=False),
        "",
        "## Phase 12D Boundary Check",
        phase12d_boundary_check.to_markdown(index=False),
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


def save_phase12c_diagnostic_score_calculation(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase12c_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase12c_source_report_check(phase_config)
    phase12b_result_check = build_phase12c_phase12b_result_check(phase_config)
    component_state_panel = build_phase12c_component_state_panel(phase_config)
    component_state_distribution = build_phase12c_component_state_distribution(
        component_state_panel
    )
    aggregate_score = build_phase12c_aggregate_score(
        phase_config=phase_config,
        component_state_panel=component_state_panel,
    )
    blocked_components = _read_csv_if_exists(
        phase_config.get("source_reports", {}).get("phase12a_blocked_components", "")
    )
    phase12d_boundary_check = build_phase12c_phase12d_boundary_check(phase_config)
    scope_boundary_check = build_phase12c_scope_boundary_check(phase_config)
    summary = build_phase12c_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase12b_result_check=phase12b_result_check,
        component_state_panel=component_state_panel,
        aggregate_score=aggregate_score,
        blocked_components=blocked_components,
        phase12d_boundary_check=phase12d_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase12c_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase12c_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase12b_result_check": phase12b_result_check,
        "component_state_panel": component_state_panel,
        "component_state_distribution": component_state_distribution,
        "aggregate_score": aggregate_score,
        "phase12d_boundary_check": phase12d_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase12c_score_{name}.csv", index=False)

    write_phase12c_markdown(
        source_report_check=source_report_check,
        phase12b_result_check=phase12b_result_check,
        component_state_panel=component_state_panel,
        component_state_distribution=component_state_distribution,
        aggregate_score=aggregate_score,
        phase12d_boundary_check=phase12d_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase12c_diagnostic_score_calculation.md",
    )

    print("Wrote Phase 12C diagnostic score calculation reports.")
    return outputs


def build_phase12d_source_score_report_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, path in phase_config.get("source_score_reports", {}).items():
        file_path = Path(str(path))
        frame = _read_csv_if_exists(file_path)
        rows.append(
            {
                "report_key": str(key),
                "path": str(file_path),
                "present": file_path.exists(),
                "rows": int(len(frame)),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12d_phase12c_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_score_reports", {})
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
            "check": "Phase 12C conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 12C gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12d_distribution_check(
    *,
    component_state_panel: pd.DataFrame,
    component_state_distribution: pd.DataFrame,
    aggregate_score: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    expected_states = set(
        str(item) for item in _as_list(phase_config.get("expected_score_states"))
    )
    component_states = set(
        component_state_panel["diagnostic_state"].dropna().astype(str).tolist()
    )
    aggregate_state = (
        str(aggregate_score.iloc[0]["diagnostic_score_state"])
        if not aggregate_score.empty
        else ""
    )

    rows = [
        {
            "check": "Component state distribution exists",
            "passed": not component_state_distribution.empty,
            "detail": f"rows={len(component_state_distribution)}",
        },
        {
            "check": "Component states are allowed",
            "passed": component_states.issubset(expected_states),
            "detail": "states=" + "; ".join(sorted(component_states)),
        },
        {
            "check": "Aggregate score state is allowed",
            "passed": aggregate_state in expected_states,
            "detail": f"aggregate_score_state={aggregate_state}",
        },
        {
            "check": "Expected component count present",
            "passed": len(component_state_panel)
            == int(phase_config.get("expected_component_count", 3)),
            "detail": f"component_count={len(component_state_panel)}",
        },
        {
            "check": "Single aggregate score present",
            "passed": len(aggregate_score)
            == int(phase_config.get("expected_aggregate_score_count", 1)),
            "detail": f"aggregate_score_rows={len(aggregate_score)}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12d_forbidden_column_check(
    *,
    component_state_panel: pd.DataFrame,
    aggregate_score: pd.DataFrame,
) -> pd.DataFrame:
    frames = {
        "component_state_panel": component_state_panel,
        "aggregate_score": aggregate_score,
    }

    # These are actual prohibited output columns. Do not use broad substring
    # checks like "weight", "return", or "signal", because Phase 12C legitimately
    # includes boundary-control columns such as numeric_weights_allowed,
    # returns_used, trading_signal_created, and strategy_backtest_run.
    forbidden_columns_by_group = {
        "numeric_score_columns": {
            "numeric_score",
            "score_value",
            "score_points",
            "score_weight",
        },
        "signal_columns": {
            "signal",
            "trade_signal",
            "allocation_signal",
            "position",
            "target_position",
            "target_allocation",
        },
        "backtest_columns": {
            "daily_return",
            "strategy_return",
            "portfolio_return",
            "equity_curve",
            "drawdown",
            "max_drawdown",
            "cagr",
            "calmar",
        },
        "empirical_weight_columns": {
            "optimised_weight",
            "optimized_weight",
            "empirical_weight",
            "return_weight",
            "learned_weight",
        },
    }

    rows: list[dict[str, Any]] = []

    for frame_name, frame in frames.items():
        columns = {str(column).lower() for column in frame.columns}

        for group, forbidden_columns in forbidden_columns_by_group.items():
            matched = sorted(columns & forbidden_columns)
            rows.append(
                {
                    "frame": frame_name,
                    "forbidden_group": group,
                    "matched_columns": "; ".join(matched),
                    "passed": len(matched) == 0,
                }
            )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12d_phase12e_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase12e_boundary", {})
    rows = [
        {
            "boundary_item": "phase12e_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "interpretation" in str(
                boundary.get("allowed_next_step", "")
            ).lower()
            and "audit" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase12e_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase12e_may_interpret_score_diagnostically",
            "value": _bool_value(
                boundary.get("phase12e_may_interpret_score_diagnostically", False)
            ),
            "passed": _bool_value(
                boundary.get("phase12e_may_interpret_score_diagnostically", False)
            ),
        },
        {
            "boundary_item": "phase12e_may_create_signal",
            "value": _bool_value(boundary.get("phase12e_may_create_signal", True)),
            "passed": not _bool_value(
                boundary.get("phase12e_may_create_signal", True)
            ),
        },
        {
            "boundary_item": "phase12e_may_test_strategy",
            "value": _bool_value(boundary.get("phase12e_may_test_strategy", True)),
            "passed": not _bool_value(
                boundary.get("phase12e_may_test_strategy", True)
            ),
        },
        {
            "boundary_item": "phase12e_may_assign_empirical_weights",
            "value": _bool_value(
                boundary.get("phase12e_may_assign_empirical_weights", True)
            ),
            "passed": not _bool_value(
                boundary.get("phase12e_may_assign_empirical_weights", True)
            ),
        },
        {
            "boundary_item": "phase12e_may_train_model",
            "value": _bool_value(boundary.get("phase12e_may_train_model", True)),
            "passed": not _bool_value(
                boundary.get("phase12e_may_train_model", True)
            ),
        },
        {
            "boundary_item": "phase12e_may_ingest_new_data",
            "value": _bool_value(boundary.get("phase12e_may_ingest_new_data", True)),
            "passed": not _bool_value(
                boundary.get("phase12e_may_ingest_new_data", True)
            ),
        },
        {
            "boundary_item": "phase12e_may_promote_candidate",
            "value": _bool_value(
                boundary.get("phase12e_may_promote_candidate", True)
            ),
            "passed": not _bool_value(
                boundary.get("phase12e_may_promote_candidate", True)
            ),
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12d_summary(
    *,
    phase_config: dict[str, Any],
    source_score_report_check: pd.DataFrame,
    phase12c_result_check: pd.DataFrame,
    distribution_check: pd.DataFrame,
    forbidden_column_check: pd.DataFrame,
    phase12e_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase12c_reports_present": bool(
                    source_score_report_check["present"].all()
                )
                if not source_score_report_check.empty
                else False,
                "phase12c_result_passed": bool(
                    phase12c_result_check["passed"].all()
                )
                if not phase12c_result_check.empty
                else False,
                "distribution_check_passed": bool(
                    distribution_check["passed"].all()
                )
                if not distribution_check.empty
                else False,
                "forbidden_column_check_passed": bool(
                    forbidden_column_check["passed"].all()
                )
                if not forbidden_column_check.empty
                else False,
                "phase12e_boundary_passed": bool(
                    phase12e_boundary_check["passed"].all()
                )
                if not phase12e_boundary_check.empty
                else False,
                "strategy_promotion": False,
                "candidate_promotion": False,
            }
        ]
    )


def build_phase12d_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 12D summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_audit_role",
            "Diagnostic score distribution and content audit only",
        )
    )

    rows = [
        _gate_row(
            "Phase 12C reports are present",
            (not gates.get("require_phase12c_reports_present", True))
            or bool(row["phase12c_reports_present"]),
            f"phase12c_reports_present={bool(row['phase12c_reports_present'])}",
        ),
        _gate_row(
            "Phase 12C conclusion passed",
            (not gates.get("require_phase12c_conclusion_passed", True))
            or bool(row["phase12c_result_passed"]),
            f"phase12c_result_passed={bool(row['phase12c_result_passed'])}",
        ),
        _gate_row(
            "Score distribution and aggregate content are valid",
            bool(row["distribution_check_passed"]),
            f"distribution_check_passed={bool(row['distribution_check_passed'])}",
        ),
        _gate_row(
            "No forbidden score/signal/backtest/weight columns exist",
            bool(row["forbidden_column_check_passed"]),
            (
                "forbidden_column_check_passed="
                f"{bool(row['forbidden_column_check_passed'])}"
            ),
        ),
        _gate_row(
            "Phase 12E boundary is interpretation-audit only",
            (not gates.get("require_phase12e_boundary_interpretation_only", True))
            or bool(row["phase12e_boundary_passed"]),
            f"phase12e_boundary_passed={bool(row['phase12e_boundary_passed'])}",
        ),
        _gate_row(
            "Audit role is correct",
            str(row["audit_role"]) == required_role,
            f"audit_role={row['audit_role']}",
        ),
    ]
    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())
    return gate_report


def build_phase12d_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — diagnostic score distribution audit passed"
        if all_passed
        else "Failed diagnostic score distribution audit"
    )
    interpretation = (
        "Phase 12D audited the diagnostic score distribution and content quality. "
        "It confirmed the score is categorical and diagnostic-only, with no signal, "
        "strategy backtest, empirical weights, model, new data ingestion, candidate "
        "promotion, or final-candidate change."
        if all_passed
        else "Phase 12D found a score distribution, content, or boundary issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 12D",
                "diagnostic": "Diagnostic score distribution/content audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase12d_markdown(
    *,
    source_score_report_check: pd.DataFrame,
    phase12c_result_check: pd.DataFrame,
    distribution_check: pd.DataFrame,
    forbidden_column_check: pd.DataFrame,
    phase12e_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 12D — Diagnostic Score Distribution / Content Audit",
        "",
        "This phase audits diagnostic score distribution and content quality. It does "
        "not create signals, allocation rules, backtests, models, new data ingestion, "
        "or candidate promotion.",
        "",
        "## Source Score Report Check",
        source_score_report_check.to_markdown(index=False),
        "",
        "## Phase 12C Result Check",
        phase12c_result_check.to_markdown(index=False),
        "",
        "## Distribution Check",
        distribution_check.to_markdown(index=False),
        "",
        "## Forbidden Column Check",
        forbidden_column_check.to_markdown(index=False),
        "",
        "## Phase 12E Boundary Check",
        phase12e_boundary_check.to_markdown(index=False),
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


def save_phase12d_diagnostic_score_distribution_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase12d_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = phase_config.get("source_score_reports", {})
    component_state_panel = _read_csv_if_exists(
        reports.get("component_state_panel", "")
    )
    component_state_distribution = _read_csv_if_exists(
        reports.get("component_state_distribution", "")
    )
    aggregate_score = _read_csv_if_exists(reports.get("aggregate_score", ""))

    source_score_report_check = build_phase12d_source_score_report_check(
        phase_config
    )
    phase12c_result_check = build_phase12d_phase12c_result_check(phase_config)
    distribution_check = build_phase12d_distribution_check(
        component_state_panel=component_state_panel,
        component_state_distribution=component_state_distribution,
        aggregate_score=aggregate_score,
        phase_config=phase_config,
    )
    forbidden_column_check = build_phase12d_forbidden_column_check(
        component_state_panel=component_state_panel,
        aggregate_score=aggregate_score,
    )
    phase12e_boundary_check = build_phase12d_phase12e_boundary_check(phase_config)
    summary = build_phase12d_summary(
        phase_config=phase_config,
        source_score_report_check=source_score_report_check,
        phase12c_result_check=phase12c_result_check,
        distribution_check=distribution_check,
        forbidden_column_check=forbidden_column_check,
        phase12e_boundary_check=phase12e_boundary_check,
    )
    gate_report = build_phase12d_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase12d_conclusion(gate_report)

    outputs = {
        "source_score_report_check": source_score_report_check,
        "phase12c_result_check": phase12c_result_check,
        "distribution_check": distribution_check,
        "forbidden_column_check": forbidden_column_check,
        "phase12e_boundary_check": phase12e_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase12d_audit_{name}.csv", index=False)

    write_phase12d_markdown(
        source_score_report_check=source_score_report_check,
        phase12c_result_check=phase12c_result_check,
        distribution_check=distribution_check,
        forbidden_column_check=forbidden_column_check,
        phase12e_boundary_check=phase12e_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase12d_diagnostic_score_distribution_audit.md",
    )

    print("Wrote Phase 12D diagnostic score distribution audit reports.")
    return outputs