from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE12A_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Score-calculation pre-registration spec only",
    "phase_branch": "Phase 12 regime score calculation preparation",
    "source_phase": "Phase 11G",
    "proposed_next_phase": "Phase 12B",
    "allow_score_calculation": False,
    "allow_numeric_score_output": False,
    "allow_empirical_return_weights": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "source_inputs": {},
    "eligible_components": [],
    "blocked_components": [],
    "formula_structure": {},
    "weighting_policy": {},
    "missingness_policy": {},
    "score_state_interpretation": [],
    "future_validation_gates": [],
    "failure_conditions": [],
    "phase12b_boundary": {},
    "gates": {
        "require_source_inputs": True,
        "require_eligible_components": True,
        "min_eligible_components": 3,
        "require_blocked_components": True,
        "min_blocked_components": 2,
        "require_formula_structure": True,
        "require_non_return_weighting_policy": True,
        "require_missingness_policy": True,
        "require_score_state_interpretation": True,
        "min_score_states": 3,
        "require_future_validation_gates": True,
        "min_future_validation_gates": 6,
        "require_failure_conditions": True,
        "min_failure_conditions": 6,
        "require_phase12b_boundary_readiness_only": True,
        "require_no_score_calculation": True,
        "require_no_numeric_score_output": True,
        "require_no_empirical_return_weights": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "required_spec_role": "Score-calculation pre-registration spec only",
    },
}


DEFAULT_PHASE12B_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Score-calculation readiness audit only",
    "phase_branch": "Phase 12 regime score calculation preparation",
    "source_phase": "Phase 12A",
    "proposed_next_phase": "Phase 12C",
    "allow_score_calculation": False,
    "allow_numeric_score_output": False,
    "allow_empirical_return_weights": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "expected_runtime_flags": {},
    "phase12a_reports": {},
    "readiness_claims": {},
    "phase12c_boundary": {},
    "gates": {
        "require_phase12a_reports_present": True,
        "require_phase12a_conclusion_passed": True,
        "require_phase12a_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_readiness_claims_locked": True,
        "require_phase12c_boundary_diagnostic_only": True,
        "require_no_score_calculation": True,
        "require_no_numeric_score_output": True,
        "require_no_empirical_return_weights": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "required_audit_role": "Score-calculation readiness audit only",
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


def _get_phase12a_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE12A_CONFIG,
        config.get("phase12a_score_calculation_preregistration_spec", {}),
    )


def _get_phase12b_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE12B_CONFIG,
        config.get("phase12b_score_calculation_readiness_audit", {}),
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


def build_phase12a_source_input_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for input_key, path in phase_config.get("source_inputs", {}).items():
        file_path = Path(str(path))
        rows.append(
            {
                "input_key": str(input_key),
                "path": str(file_path),
                "present": file_path.exists(),
                "rows": int(len(_read_csv_if_exists(file_path))),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["result"] = frame["present"].map({True: "Passed", False: "Failed"})
    return frame


def build_phase12a_eligible_components(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get("eligible_components")):
        rows.append(
            {
                "component_id": str(item.get("component_id", "")),
                "family": str(item.get("family", "")),
                "eligibility": str(item.get("eligibility", "")),
                "source_basis": str(item.get("source_basis", "")),
                "allowed_states": _join_list(item.get("allowed_states")),
                "may_affect_future_score": _bool_value(
                    item.get("may_affect_future_score", False)
                ),
                "may_create_signal_now": _bool_value(
                    item.get("may_create_signal_now", True)
                ),
            }
        )
    return pd.DataFrame(rows)


def build_phase12a_blocked_components(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get("blocked_components")):
        rows.append(
            {
                "component_id": str(item.get("component_id", "")),
                "family": str(item.get("family", "")),
                "blocked_reason": str(item.get("blocked_reason", "")),
                "unblock_requires": str(item.get("unblock_requires", "")),
                "may_affect_future_score": _bool_value(
                    item.get("may_affect_future_score", True)
                ),
            }
        )
    return pd.DataFrame(rows)


def build_phase12a_formula_structure(phase_config: dict[str, Any]) -> pd.DataFrame:
    formula = phase_config.get("formula_structure", {})
    return pd.DataFrame(
        [
            {
                "formula_id": str(formula.get("formula_id", "")),
                "formula_role": str(formula.get("formula_role", "")),
                "aggregation_policy": str(formula.get("aggregation_policy", "")),
                "allowed_component_states": _join_list(
                    formula.get("allowed_component_states")
                ),
                "score_state_output": _join_list(formula.get("score_state_output")),
                "numeric_score_values_defined": _bool_value(
                    formula.get("numeric_score_values_defined", True)
                ),
                "empirical_weights_allowed": _bool_value(
                    formula.get("empirical_weights_allowed", True)
                ),
                "returns_used_for_formula_design": _bool_value(
                    formula.get("returns_used_for_formula_design", True)
                ),
                "description": str(formula.get("description", "")),
            }
        ]
    )


def build_phase12a_weighting_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    policy = phase_config.get("weighting_policy", {})
    return pd.DataFrame(
        [
            {
                "policy_id": str(policy.get("policy_id", "")),
                "policy_type": str(policy.get("policy_type", "")),
                "eligible_component_scope": str(
                    policy.get("eligible_component_scope", "")
                ),
                "empirical_return_weighting_allowed": _bool_value(
                    policy.get("empirical_return_weighting_allowed", True)
                ),
                "optimisation_allowed": _bool_value(
                    policy.get("optimisation_allowed", True)
                ),
                "cutoff_search_allowed": _bool_value(
                    policy.get("cutoff_search_allowed", True)
                ),
                "numeric_weights_assigned_now": _bool_value(
                    policy.get("numeric_weights_assigned_now", True)
                ),
                "pre_registration_required_before_calculation": _bool_value(
                    policy.get("pre_registration_required_before_calculation", False)
                ),
            }
        ]
    )


def build_phase12a_missingness_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    policy = phase_config.get("missingness_policy", {})
    return pd.DataFrame(
        [
            {
                "policy_id": str(policy.get("policy_id", "")),
                "no_return_inference": _bool_value(
                    policy.get("no_return_inference", False)
                ),
                "no_silent_fill": _bool_value(policy.get("no_silent_fill", False)),
                "unavailable_component_action": str(
                    policy.get("unavailable_component_action", "")
                ),
                "blocked_component_action": str(
                    policy.get("blocked_component_action", "")
                ),
                "validation_risk_missing_action": str(
                    policy.get("validation_risk_missing_action", "")
                ),
                "score_calculation_allowed_with_missing_validation_risk": _bool_value(
                    policy.get(
                        "score_calculation_allowed_with_missing_validation_risk",
                        True,
                    )
                ),
            }
        ]
    )


def build_phase12a_score_state_interpretation(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get("score_state_interpretation")):
        rows.append(
            {
                "state": str(item.get("state", "")),
                "interpretation": str(item.get("interpretation", "")),
                "trading_allowed": _bool_value(item.get("trading_allowed", True)),
                "signal_allowed": _bool_value(item.get("signal_allowed", True)),
            }
        )
    return pd.DataFrame(rows)


def build_phase12a_future_validation_gates(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get("future_validation_gates")):
        rows.append(
            {
                "gate_id": str(item.get("gate_id", "")),
                "gate": str(item.get("gate", "")),
                "required": _bool_value(item.get("required", False)),
            }
        )
    return pd.DataFrame(rows)


def build_phase12a_failure_conditions(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in _as_list(phase_config.get("failure_conditions")):
        rows.append(
            {
                "condition_id": str(item.get("condition_id", "")),
                "condition": str(item.get("condition", "")),
            }
        )
    return pd.DataFrame(rows)


def build_phase12a_phase12b_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase12b_boundary", {})
    rows = [
        {
            "boundary_item": "phase12b_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "readiness audit" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase12b_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "score calculation" in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion" in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase12b_may_audit_preregistration",
            "value": _bool_value(boundary.get("phase12b_may_audit_preregistration", False)),
            "passed": _bool_value(boundary.get("phase12b_may_audit_preregistration", False)),
        },
        {
            "boundary_item": "phase12b_may_calculate_scores",
            "value": _bool_value(boundary.get("phase12b_may_calculate_scores", True)),
            "passed": not _bool_value(boundary.get("phase12b_may_calculate_scores", True)),
        },
        {
            "boundary_item": "phase12b_may_assign_empirical_weights",
            "value": _bool_value(boundary.get("phase12b_may_assign_empirical_weights", True)),
            "passed": not _bool_value(boundary.get("phase12b_may_assign_empirical_weights", True)),
        },
        {
            "boundary_item": "phase12b_may_create_signal",
            "value": _bool_value(boundary.get("phase12b_may_create_signal", True)),
            "passed": not _bool_value(boundary.get("phase12b_may_create_signal", True)),
        },
        {
            "boundary_item": "phase12b_may_test_strategy",
            "value": _bool_value(boundary.get("phase12b_may_test_strategy", True)),
            "passed": not _bool_value(boundary.get("phase12b_may_test_strategy", True)),
        },
        {
            "boundary_item": "phase12b_may_train_model",
            "value": _bool_value(boundary.get("phase12b_may_train_model", True)),
            "passed": not _bool_value(boundary.get("phase12b_may_train_model", True)),
        },
        {
            "boundary_item": "phase12b_may_ingest_new_data",
            "value": _bool_value(boundary.get("phase12b_may_ingest_new_data", True)),
            "passed": not _bool_value(boundary.get("phase12b_may_ingest_new_data", True)),
        },
        {
            "boundary_item": "phase12b_may_promote_candidate",
            "value": _bool_value(boundary.get("phase12b_may_promote_candidate", True)),
            "passed": not _bool_value(boundary.get("phase12b_may_promote_candidate", True)),
        },
    ]
    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})
    return frame


def build_phase12_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No score calculation", "allow_score_calculation"),
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
    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})
    return frame


def build_phase12a_summary(
    *,
    phase_config: dict[str, Any],
    source_input_check: pd.DataFrame,
    eligible_components: pd.DataFrame,
    blocked_components: pd.DataFrame,
    formula_structure: pd.DataFrame,
    weighting_policy: pd.DataFrame,
    missingness_policy: pd.DataFrame,
    score_state_interpretation: pd.DataFrame,
    future_validation_gates: pd.DataFrame,
    failure_conditions: pd.DataFrame,
    phase12b_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    formula_clean = (
        not formula_structure.empty
        and not _bool_value(formula_structure.iloc[0]["numeric_score_values_defined"])
        and not _bool_value(formula_structure.iloc[0]["empirical_weights_allowed"])
        and not _bool_value(formula_structure.iloc[0]["returns_used_for_formula_design"])
    )
    weighting_clean = (
        not weighting_policy.empty
        and not _bool_value(weighting_policy.iloc[0]["empirical_return_weighting_allowed"])
        and not _bool_value(weighting_policy.iloc[0]["optimisation_allowed"])
        and not _bool_value(weighting_policy.iloc[0]["cutoff_search_allowed"])
        and not _bool_value(weighting_policy.iloc[0]["numeric_weights_assigned_now"])
        and _bool_value(weighting_policy.iloc[0]["pre_registration_required_before_calculation"])
    )
    missingness_clean = (
        not missingness_policy.empty
        and _bool_value(missingness_policy.iloc[0]["no_return_inference"])
        and _bool_value(missingness_policy.iloc[0]["no_silent_fill"])
        and not _bool_value(
            missingness_policy.iloc[0][
                "score_calculation_allowed_with_missing_validation_risk"
            ]
        )
    )
    states_non_trading = (
        bool(
            score_state_interpretation["trading_allowed"].map(_bool_value).eq(False).all()
            and score_state_interpretation["signal_allowed"].map(_bool_value).eq(False).all()
        )
        if not score_state_interpretation.empty
        else False
    )
    eligible_non_signal = (
        bool(eligible_components["may_create_signal_now"].map(_bool_value).eq(False).all())
        if not eligible_components.empty
        else False
    )
    blocked_clean = (
        bool(blocked_components["may_affect_future_score"].map(_bool_value).eq(False).all())
        if not blocked_components.empty
        else False
    )

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_inputs_present": bool(source_input_check["present"].all()) if not source_input_check.empty else False,
                "eligible_component_count": int(len(eligible_components)),
                "eligible_components_non_signal": eligible_non_signal,
                "blocked_component_count": int(len(blocked_components)),
                "blocked_components_clean": blocked_clean,
                "formula_structure_clean": formula_clean,
                "weighting_policy_clean": weighting_clean,
                "missingness_policy_clean": missingness_clean,
                "score_state_count": int(len(score_state_interpretation)),
                "score_states_non_trading": states_non_trading,
                "future_validation_gate_count": int(len(future_validation_gates)),
                "failure_condition_count": int(len(failure_conditions)),
                "phase12b_boundary_passed": bool(phase12b_boundary_check["passed"].all()) if not phase12b_boundary_check.empty else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all()) if not scope_boundary_check.empty else False,
                "strategy_promotion": False,
                "candidate_promotion": False,
            }
        ]
    )


def build_phase12a_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 12A summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get("required_spec_role", "Score-calculation pre-registration spec only")
    )

    rows = [
        _gate_row("Source inputs are present", (not gates.get("require_source_inputs", True)) or bool(row["source_inputs_present"]), f"source_inputs_present={bool(row['source_inputs_present'])}"),
        _gate_row("Eligible components are locked", (not gates.get("require_eligible_components", True)) or int(row["eligible_component_count"]) >= int(gates.get("min_eligible_components", 3)), f"eligible_component_count={int(row['eligible_component_count'])}"),
        _gate_row("Eligible components are non-signal", bool(row["eligible_components_non_signal"]), f"eligible_components_non_signal={bool(row['eligible_components_non_signal'])}"),
        _gate_row("Blocked components are locked", (not gates.get("require_blocked_components", True)) or int(row["blocked_component_count"]) >= int(gates.get("min_blocked_components", 2)), f"blocked_component_count={int(row['blocked_component_count'])}"),
        _gate_row("Blocked components cannot affect future score", bool(row["blocked_components_clean"]), f"blocked_components_clean={bool(row['blocked_components_clean'])}"),
        _gate_row("Formula structure is clean", (not gates.get("require_formula_structure", True)) or bool(row["formula_structure_clean"]), f"formula_structure_clean={bool(row['formula_structure_clean'])}"),
        _gate_row("Weighting policy is non-return based", (not gates.get("require_non_return_weighting_policy", True)) or bool(row["weighting_policy_clean"]), f"weighting_policy_clean={bool(row['weighting_policy_clean'])}"),
        _gate_row("Missingness policy is clean", (not gates.get("require_missingness_policy", True)) or bool(row["missingness_policy_clean"]), f"missingness_policy_clean={bool(row['missingness_policy_clean'])}"),
        _gate_row("Score states are non-trading", (not gates.get("require_score_state_interpretation", True)) or (int(row["score_state_count"]) >= int(gates.get("min_score_states", 3)) and bool(row["score_states_non_trading"])), f"score_state_count={int(row['score_state_count'])}; score_states_non_trading={bool(row['score_states_non_trading'])}"),
        _gate_row("Future validation gates are documented", (not gates.get("require_future_validation_gates", True)) or int(row["future_validation_gate_count"]) >= int(gates.get("min_future_validation_gates", 6)), f"future_validation_gate_count={int(row['future_validation_gate_count'])}"),
        _gate_row("Failure conditions are documented", (not gates.get("require_failure_conditions", True)) or int(row["failure_condition_count"]) >= int(gates.get("min_failure_conditions", 6)), f"failure_condition_count={int(row['failure_condition_count'])}"),
        _gate_row("Phase 12B boundary is readiness-only", (not gates.get("require_phase12b_boundary_readiness_only", True)) or bool(row["phase12b_boundary_passed"]), f"phase12b_boundary_passed={bool(row['phase12b_boundary_passed'])}"),
        _gate_row("No score calculation/output/signal/backtest/model/data/promotion is allowed", bool(row["scope_boundary_passed"]), f"scope_boundary_passed={bool(row['scope_boundary_passed'])}"),
        _gate_row("Spec role is correct", str(row["spec_role"]) == required_role, f"spec_role={row['spec_role']}"),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())
    return gate_report


def build_phase12a_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — score-calculation pre-registration spec passed"
        if all_passed
        else "Failed score-calculation pre-registration spec"
    )
    interpretation = (
        "Phase 12A pre-registered eligible components, blocked components, formula "
        "structure, non-return weighting policy, missingness handling, score-state "
        "interpretation, validation gates, and failure conditions without calculating "
        "scores, assigning empirical weights, creating signals, running backtests, "
        "ingesting new data, training models, or promoting a candidate."
        if all_passed
        else "Phase 12A found a pre-registration, boundary, or scope issue. Do not proceed."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 12A",
                "diagnostic": "Score-calculation pre-registration spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase12a_markdown(
    *,
    source_input_check: pd.DataFrame,
    eligible_components: pd.DataFrame,
    blocked_components: pd.DataFrame,
    formula_structure: pd.DataFrame,
    weighting_policy: pd.DataFrame,
    missingness_policy: pd.DataFrame,
    score_state_interpretation: pd.DataFrame,
    future_validation_gates: pd.DataFrame,
    failure_conditions: pd.DataFrame,
    phase12b_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 12A — Score-Calculation Pre-Registration Spec",
        "",
        "This phase pre-registers the future diagnostic score-calculation design. It does not calculate scores, assign empirical weights, create signals, run backtests, ingest new data, train models, or promote a candidate.",
        "",
        "## Source Input Check",
        source_input_check.to_markdown(index=False),
        "",
        "## Eligible Components",
        eligible_components.to_markdown(index=False),
        "",
        "## Blocked Components",
        blocked_components.to_markdown(index=False),
        "",
        "## Formula Structure",
        formula_structure.to_markdown(index=False),
        "",
        "## Weighting Policy",
        weighting_policy.to_markdown(index=False),
        "",
        "## Missingness Policy",
        missingness_policy.to_markdown(index=False),
        "",
        "## Score State Interpretation",
        score_state_interpretation.to_markdown(index=False),
        "",
        "## Future Validation Gates",
        future_validation_gates.to_markdown(index=False),
        "",
        "## Failure Conditions",
        failure_conditions.to_markdown(index=False),
        "",
        "## Phase 12B Boundary Check",
        phase12b_boundary_check.to_markdown(index=False),
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


def save_phase12a_score_calculation_preregistration_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase12a_config(config)
    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_input_check = build_phase12a_source_input_check(phase_config)
    eligible_components = build_phase12a_eligible_components(phase_config)
    blocked_components = build_phase12a_blocked_components(phase_config)
    formula_structure = build_phase12a_formula_structure(phase_config)
    weighting_policy = build_phase12a_weighting_policy(phase_config)
    missingness_policy = build_phase12a_missingness_policy(phase_config)
    score_state_interpretation = build_phase12a_score_state_interpretation(phase_config)
    future_validation_gates = build_phase12a_future_validation_gates(phase_config)
    failure_conditions = build_phase12a_failure_conditions(phase_config)
    phase12b_boundary_check = build_phase12a_phase12b_boundary_check(phase_config)
    scope_boundary_check = build_phase12_scope_boundary_check(phase_config)
    summary = build_phase12a_summary(
        phase_config=phase_config,
        source_input_check=source_input_check,
        eligible_components=eligible_components,
        blocked_components=blocked_components,
        formula_structure=formula_structure,
        weighting_policy=weighting_policy,
        missingness_policy=missingness_policy,
        score_state_interpretation=score_state_interpretation,
        future_validation_gates=future_validation_gates,
        failure_conditions=failure_conditions,
        phase12b_boundary_check=phase12b_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase12a_gate_report(phase_config=phase_config, summary=summary)
    conclusion = build_phase12a_conclusion(gate_report)

    outputs = {
        "source_input_check": source_input_check,
        "eligible_components": eligible_components,
        "blocked_components": blocked_components,
        "formula_structure": formula_structure,
        "weighting_policy": weighting_policy,
        "missingness_policy": missingness_policy,
        "score_state_interpretation": score_state_interpretation,
        "future_validation_gates": future_validation_gates,
        "failure_conditions": failure_conditions,
        "phase12b_boundary_check": phase12b_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase12a_prereg_{name}.csv", index=False)

    write_phase12a_markdown(
        source_input_check=source_input_check,
        eligible_components=eligible_components,
        blocked_components=blocked_components,
        formula_structure=formula_structure,
        weighting_policy=weighting_policy,
        missingness_policy=missingness_policy,
        score_state_interpretation=score_state_interpretation,
        future_validation_gates=future_validation_gates,
        failure_conditions=failure_conditions,
        phase12b_boundary_check=phase12b_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase12a_score_calculation_preregistration_spec.md",
    )

    print("Wrote Phase 12A score-calculation pre-registration spec reports.")
    return outputs


def build_phase12b_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for report_key, path in phase_config.get("phase12a_reports", {}).items():
        file_path = Path(str(path))
        rows.append(
            {
                "report_key": str(report_key),
                "path": str(file_path),
                "present": file_path.exists(),
                "rows": int(len(_read_csv_if_exists(file_path))),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["result"] = frame["present"].map({True: "Passed", False: "Failed"})
    return frame


def build_phase12b_phase12a_result_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    reports = phase_config.get("phase12a_reports", {})
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
            "check": "Phase 12A conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", "")) if not conclusion.empty else "missing",
        },
        {
            "check": "Phase 12A gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]
    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})
    return frame


def build_phase12b_config_flag_check(
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


def build_phase12b_readiness_claims_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    claims = phase_config.get("readiness_claims", {})
    should_be_true = [
        "preregistration_exists",
        "eligible_components_locked",
        "blocked_components_locked",
        "formula_structure_locked",
        "weighting_policy_locked",
        "missingness_policy_locked",
        "failure_conditions_locked",
    ]
    should_be_false = [
        "score_calculated",
        "signal_created",
        "backtest_run",
        "model_trained",
        "new_data_ingested",
        "candidate_promoted",
    ]
    rows = []
    for claim in should_be_true:
        actual = _bool_value(claims.get(claim, False))
        rows.append({"claim": claim, "expected": True, "actual": actual, "passed": actual})
    for claim in should_be_false:
        actual = _bool_value(claims.get(claim, True))
        rows.append({"claim": claim, "expected": False, "actual": actual, "passed": not actual})
    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})
    return frame


def build_phase12b_phase12c_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase12c_boundary", {})
    rows = [
        {
            "boundary_item": "phase12c_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "diagnostic score calculation" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase12c_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion" in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase12c_may_calculate_diagnostic_scores",
            "value": _bool_value(boundary.get("phase12c_may_calculate_diagnostic_scores", False)),
            "passed": _bool_value(boundary.get("phase12c_may_calculate_diagnostic_scores", False)),
        },
        {
            "boundary_item": "phase12c_may_assign_empirical_weights",
            "value": _bool_value(boundary.get("phase12c_may_assign_empirical_weights", True)),
            "passed": not _bool_value(boundary.get("phase12c_may_assign_empirical_weights", True)),
        },
        {
            "boundary_item": "phase12c_may_create_signal",
            "value": _bool_value(boundary.get("phase12c_may_create_signal", True)),
            "passed": not _bool_value(boundary.get("phase12c_may_create_signal", True)),
        },
        {
            "boundary_item": "phase12c_may_test_strategy",
            "value": _bool_value(boundary.get("phase12c_may_test_strategy", True)),
            "passed": not _bool_value(boundary.get("phase12c_may_test_strategy", True)),
        },
        {
            "boundary_item": "phase12c_may_train_model",
            "value": _bool_value(boundary.get("phase12c_may_train_model", True)),
            "passed": not _bool_value(boundary.get("phase12c_may_train_model", True)),
        },
        {
            "boundary_item": "phase12c_may_ingest_new_data",
            "value": _bool_value(boundary.get("phase12c_may_ingest_new_data", True)),
            "passed": not _bool_value(boundary.get("phase12c_may_ingest_new_data", True)),
        },
        {
            "boundary_item": "phase12c_may_promote_candidate",
            "value": _bool_value(boundary.get("phase12c_may_promote_candidate", True)),
            "passed": not _bool_value(boundary.get("phase12c_may_promote_candidate", True)),
        },
    ]
    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})
    return frame


def build_phase12b_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase12a_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    readiness_claims_check: pd.DataFrame,
    phase12c_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase12a_reports_present": bool(report_inventory_check["present"].all()) if not report_inventory_check.empty else False,
                "phase12a_result_passed": bool(phase12a_result_check["passed"].all()) if not phase12a_result_check.empty else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all()) if not config_flag_check.empty else False,
                "readiness_claims_locked": bool(readiness_claims_check["passed"].all()) if not readiness_claims_check.empty else False,
                "phase12c_boundary_passed": bool(phase12c_boundary_check["passed"].all()) if not phase12c_boundary_check.empty else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all()) if not scope_boundary_check.empty else False,
                "strategy_promotion": False,
                "candidate_promotion": False,
            }
        ]
    )


def build_phase12b_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 12B summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(gates.get("required_audit_role", "Score-calculation readiness audit only"))

    rows = [
        _gate_row("Phase 12A reports are present", (not gates.get("require_phase12a_reports_present", True)) or bool(row["phase12a_reports_present"]), f"phase12a_reports_present={bool(row['phase12a_reports_present'])}"),
        _gate_row("Phase 12A conclusion and gates passed", ((not gates.get("require_phase12a_conclusion_passed", True)) or bool(row["phase12a_result_passed"])) and ((not gates.get("require_phase12a_gate_report_passed", True)) or bool(row["phase12a_result_passed"])), f"phase12a_result_passed={bool(row['phase12a_result_passed'])}"),
        _gate_row("Config flags are clean for combined run", (not gates.get("require_config_flags_clean_for_run", True)) or bool(row["config_flags_clean_for_run"]), f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}"),
        _gate_row("Readiness claims are locked", (not gates.get("require_readiness_claims_locked", True)) or bool(row["readiness_claims_locked"]), f"readiness_claims_locked={bool(row['readiness_claims_locked'])}"),
        _gate_row("Phase 12C boundary is diagnostic-only", (not gates.get("require_phase12c_boundary_diagnostic_only", True)) or bool(row["phase12c_boundary_passed"]), f"phase12c_boundary_passed={bool(row['phase12c_boundary_passed'])}"),
        _gate_row("No score output/signal/backtest/model/data/promotion is allowed", bool(row["scope_boundary_passed"]), f"scope_boundary_passed={bool(row['scope_boundary_passed'])}"),
        _gate_row("Audit role is correct", str(row["audit_role"]) == required_role, f"audit_role={row['audit_role']}"),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())
    return gate_report


def build_phase12b_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — score-calculation readiness audit passed"
        if all_passed
        else "Failed score-calculation readiness audit"
    )
    interpretation = (
        "Phase 12B verified that Phase 12A pre-registration is complete and locked. "
        "No scores, weights, signals, backtests, models, new data ingestion, or "
        "candidate promotion exist. Phase 12C may only calculate diagnostic scores."
        if all_passed
        else "Phase 12B found a report, config, readiness, boundary, or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 12B",
                "diagnostic": "Score-calculation readiness audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase12b_markdown(
    *,
    report_inventory_check: pd.DataFrame,
    phase12a_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    readiness_claims_check: pd.DataFrame,
    phase12c_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 12B — Score-Calculation Readiness Audit",
        "",
        "This phase verifies Phase 12A pre-registration readiness. It does not calculate scores, assign empirical weights, create signals, run backtests, ingest new data, train models, or promote a candidate.",
        "",
        "## Report Inventory Check",
        report_inventory_check.to_markdown(index=False),
        "",
        "## Phase 12A Result Check",
        phase12a_result_check.to_markdown(index=False),
        "",
        "## Config Flag Check",
        config_flag_check.to_markdown(index=False),
        "",
        "## Readiness Claims Check",
        readiness_claims_check.to_markdown(index=False),
        "",
        "## Phase 12C Boundary Check",
        phase12c_boundary_check.to_markdown(index=False),
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


def save_phase12b_score_calculation_readiness_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase12b_config(config)
    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase12b_report_inventory_check(phase_config)
    phase12a_result_check = build_phase12b_phase12a_result_check(phase_config)
    config_flag_check = build_phase12b_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )
    readiness_claims_check = build_phase12b_readiness_claims_check(phase_config)
    phase12c_boundary_check = build_phase12b_phase12c_boundary_check(phase_config)
    scope_boundary_check = build_phase12_scope_boundary_check(phase_config)
    summary = build_phase12b_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase12a_result_check=phase12a_result_check,
        config_flag_check=config_flag_check,
        readiness_claims_check=readiness_claims_check,
        phase12c_boundary_check=phase12c_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase12b_gate_report(phase_config=phase_config, summary=summary)
    conclusion = build_phase12b_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase12a_result_check": phase12a_result_check,
        "config_flag_check": config_flag_check,
        "readiness_claims_check": readiness_claims_check,
        "phase12c_boundary_check": phase12c_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase12b_readiness_{name}.csv", index=False)

    write_phase12b_markdown(
        report_inventory_check=report_inventory_check,
        phase12a_result_check=phase12a_result_check,
        config_flag_check=config_flag_check,
        readiness_claims_check=readiness_claims_check,
        phase12c_boundary_check=phase12c_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase12b_score_calculation_readiness_audit.md",
    )

    print("Wrote Phase 12B score-calculation readiness audit reports.")
    return outputs