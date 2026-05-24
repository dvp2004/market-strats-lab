from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE11C_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Regime scoring rulebook spec only",
    "phase_branch": "Phase 11 architecture review",
    "source_phase": "Phase 11B",
    "proposed_next_phase": "Phase 11D",
    "source_architecture": {},
    "allow_score_calculation": False,
    "allow_numeric_score_weights": False,
    "allow_empirical_return_weights": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "component_rulebook": [],
    "missingness_rules": [],
    "weighting_principles": [],
    "score_state_rulebook": [],
    "audit_output_spec": [],
    "future_validation_gates": [],
    "phase11d_boundary": {
        "allowed_next_step": "Regime scoring diagnostic panel design only",
        "forbidden_next_step": (
            "score calculation, signal creation, strategy backtest, model training, "
            "new data ingestion, or candidate promotion"
        ),
        "phase11d_may_define_diagnostic_panel": True,
        "phase11d_may_calculate_scores": False,
        "phase11d_may_create_signal": False,
        "phase11d_may_test_strategy": False,
        "phase11d_may_train_model": False,
        "phase11d_may_ingest_new_data": False,
        "phase11d_may_promote_candidate": False,
    },
    "gates": {
        "require_source_architecture": True,
        "require_component_rulebook": True,
        "min_component_count": 5,
        "require_active_technical_macro_validation_components": True,
        "require_future_families_blocked": True,
        "require_conceptual_directions": True,
        "require_missingness_rules": True,
        "min_missingness_rules": 5,
        "require_weighting_principles": True,
        "min_weighting_principles": 5,
        "require_score_states_non_trading": True,
        "require_audit_output_spec": True,
        "min_audit_outputs": 5,
        "require_future_validation_gates": True,
        "min_future_validation_gates": 6,
        "require_phase11d_boundary_spec_only": True,
        "require_no_score_calculation": True,
        "require_no_numeric_score_weights": True,
        "require_no_empirical_return_weights": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "required_spec_role": "Regime scoring rulebook spec only",
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


def _get_phase_config(config: dict[str, Any]) -> dict[str, Any]:
    user_config = config.get("phase11c_regime_scoring_rulebook_spec", {})
    return _deep_merge_dict(DEFAULT_PHASE11C_CONFIG, user_config)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _join_list(value: Any) -> str:
    return "; ".join(str(item) for item in _as_list(value))


def build_phase11c_source_architecture(phase_config: dict[str, Any]) -> pd.DataFrame:
    source = phase_config.get("source_architecture", {})

    return pd.DataFrame(
        [
            {
                "selected_architecture": str(source.get("selected_architecture", "")),
                "source_spec": str(source.get("source_spec", "")),
                "rationale": str(source.get("rationale", "")),
                "source_architecture_present": bool(
                    str(source.get("selected_architecture", "")).strip()
                ),
                "source_phase": str(phase_config.get("source_phase", "")),
            }
        ]
    )


def build_phase11c_component_rulebook(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for component in _as_list(phase_config.get("component_rulebook")):
        rows.append(
            {
                "component_id": str(component.get("component_id", "")),
                "family": str(component.get("family", "")),
                "rulebook_role": str(component.get("rulebook_role", "")),
                "source_evidence": str(component.get("source_evidence", "")),
                "allowed_conceptual_inputs": _join_list(
                    component.get("allowed_conceptual_inputs")
                ),
                "conceptual_direction_count": len(
                    _as_list(component.get("conceptual_directions"))
                ),
                "missingness_policy": str(component.get("missingness_policy", "")),
                "current_status": str(component.get("current_status", "")),
                "is_blocked": str(component.get("current_status", "")).lower()
                == "blocked",
            }
        )

    return pd.DataFrame(rows)


def build_phase11c_conceptual_direction_rulebook(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for component in _as_list(phase_config.get("component_rulebook")):
        component_id = str(component.get("component_id", ""))
        family = str(component.get("family", ""))

        for direction in _as_list(component.get("conceptual_directions")):
            rows.append(
                {
                    "component_id": component_id,
                    "family": family,
                    "direction_id": str(direction.get("direction_id", "")),
                    "condition_family": str(direction.get("condition_family", "")),
                    "conceptual_score_direction": str(
                        direction.get("conceptual_score_direction", "")
                    ),
                    "trading_allowed": bool(direction.get("trading_allowed", True)),
                }
            )

    return pd.DataFrame(rows)


def build_phase11c_missingness_rules(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for rule in _as_list(phase_config.get("missingness_rules")):
        rows.append(
            {
                "rule_id": str(rule.get("rule_id", "")),
                "rule": str(rule.get("rule", "")),
                "required": bool(rule.get("required", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11c_weighting_principles(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for principle in _as_list(phase_config.get("weighting_principles")):
        rows.append(
            {
                "principle_id": str(principle.get("principle_id", "")),
                "principle": str(principle.get("principle", "")),
                "required": bool(principle.get("required", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11c_score_state_rulebook(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for state in _as_list(phase_config.get("score_state_rulebook")):
        rows.append(
            {
                "state_id": str(state.get("state_id", "")),
                "conceptual_definition": str(state.get("conceptual_definition", "")),
                "current_role": str(state.get("current_role", "")),
                "score_calculation_allowed": bool(
                    state.get("score_calculation_allowed", True)
                ),
                "trading_allowed": bool(state.get("trading_allowed", True)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11c_audit_output_spec(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for output in _as_list(phase_config.get("audit_output_spec")):
        rows.append(
            {
                "output_id": str(output.get("output_id", "")),
                "output_description": str(output.get("output_description", "")),
                "required_for_future_phase": bool(
                    output.get("required_for_future_phase", False)
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase11c_future_validation_gates(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for gate in _as_list(phase_config.get("future_validation_gates")):
        rows.append(
            {
                "gate_id": str(gate.get("gate_id", "")),
                "gate": str(gate.get("gate", "")),
                "required": bool(gate.get("required", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11c_phase11d_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase11d_boundary", {})

    rows = [
        {
            "boundary_item": "phase11d_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "design" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase11d_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "score calculation" in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion" in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase11d_may_define_diagnostic_panel",
            "value": bool(boundary.get("phase11d_may_define_diagnostic_panel", False)),
            "passed": bool(boundary.get("phase11d_may_define_diagnostic_panel", False)),
        },
        {
            "boundary_item": "phase11d_may_calculate_scores",
            "value": bool(boundary.get("phase11d_may_calculate_scores", True)),
            "passed": not bool(boundary.get("phase11d_may_calculate_scores", True)),
        },
        {
            "boundary_item": "phase11d_may_create_signal",
            "value": bool(boundary.get("phase11d_may_create_signal", True)),
            "passed": not bool(boundary.get("phase11d_may_create_signal", True)),
        },
        {
            "boundary_item": "phase11d_may_test_strategy",
            "value": bool(boundary.get("phase11d_may_test_strategy", True)),
            "passed": not bool(boundary.get("phase11d_may_test_strategy", True)),
        },
        {
            "boundary_item": "phase11d_may_train_model",
            "value": bool(boundary.get("phase11d_may_train_model", True)),
            "passed": not bool(boundary.get("phase11d_may_train_model", True)),
        },
        {
            "boundary_item": "phase11d_may_ingest_new_data",
            "value": bool(boundary.get("phase11d_may_ingest_new_data", True)),
            "passed": not bool(boundary.get("phase11d_may_ingest_new_data", True)),
        },
        {
            "boundary_item": "phase11d_may_promote_candidate",
            "value": bool(boundary.get("phase11d_may_promote_candidate", True)),
            "passed": not bool(boundary.get("phase11d_may_promote_candidate", True)),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11c_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No score calculation", "allow_score_calculation"),
        ("No numeric score weights", "allow_numeric_score_weights"),
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
            "value": bool(phase_config.get(key, True)),
            "passed": not bool(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11c_summary(
    *,
    phase_config: dict[str, Any],
    source_architecture: pd.DataFrame,
    component_rulebook: pd.DataFrame,
    conceptual_direction_rulebook: pd.DataFrame,
    missingness_rules: pd.DataFrame,
    weighting_principles: pd.DataFrame,
    score_state_rulebook: pd.DataFrame,
    audit_output_spec: pd.DataFrame,
    future_validation_gates: pd.DataFrame,
    phase11d_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    active_required_components = {
        "technical_regime_context",
        "macro_regime_context",
        "validation_risk_context",
    }
    active_components_present = active_required_components.issubset(
        set(component_rulebook["component_id"].tolist())
    ) if not component_rulebook.empty else False

    future_families_blocked = (
        bool(
            component_rulebook[
                component_rulebook["family"].isin(
                    ["fundamental_valuation", "sentiment_narrative"]
                )
            ]["is_blocked"]
            .eq(True)
            .all()
        )
        if not component_rulebook.empty
        else False
    )

    score_states_non_trading = (
        bool(
            score_state_rulebook["trading_allowed"].eq(False).all()
            and score_state_rulebook["score_calculation_allowed"].eq(False).all()
        )
        if not score_state_rulebook.empty
        else False
    )

    conceptual_directions_non_trading = (
        bool(conceptual_direction_rulebook["trading_allowed"].eq(False).all())
        if not conceptual_direction_rulebook.empty
        else False
    )

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_architecture_present": bool(
                    source_architecture.iloc[0]["source_architecture_present"]
                ) if not source_architecture.empty else False,
                "component_count": int(len(component_rulebook)),
                "active_required_components_present": active_components_present,
                "future_families_blocked": future_families_blocked,
                "conceptual_direction_count": int(len(conceptual_direction_rulebook)),
                "conceptual_directions_non_trading": conceptual_directions_non_trading,
                "missingness_rule_count": int(len(missingness_rules)),
                "required_missingness_rule_count": int(missingness_rules["required"].sum())
                if not missingness_rules.empty else 0,
                "weighting_principle_count": int(len(weighting_principles)),
                "required_weighting_principle_count": int(
                    weighting_principles["required"].sum()
                ) if not weighting_principles.empty else 0,
                "score_state_count": int(len(score_state_rulebook)),
                "score_states_non_trading": score_states_non_trading,
                "audit_output_count": int(len(audit_output_spec)),
                "required_audit_output_count": int(
                    audit_output_spec["required_for_future_phase"].sum()
                ) if not audit_output_spec.empty else 0,
                "future_validation_gate_count": int(len(future_validation_gates)),
                "required_future_validation_gate_count": int(
                    future_validation_gates["required"].sum()
                ) if not future_validation_gates.empty else 0,
                "phase11d_boundary_passed": bool(
                    phase11d_boundary_check["passed"].all()
                ) if not phase11d_boundary_check.empty else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty else False,
                "strategy_promotion": False,
                "candidate_promotion": False,
            }
        ]
    )


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase11c_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [_gate_row("Phase 11C summary exists", False, "No summary was created.")]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get("required_spec_role", "Regime scoring rulebook spec only")
    )

    rows = [
        _gate_row(
            "Source architecture is documented",
            (not gates.get("require_source_architecture", True))
            or bool(row["source_architecture_present"]),
            f"source_architecture_present={bool(row['source_architecture_present'])}",
        ),
        _gate_row(
            "Component rulebook is documented",
            (not gates.get("require_component_rulebook", True))
            or int(row["component_count"]) >= int(gates.get("min_component_count", 5)),
            f"component_count={int(row['component_count'])}",
        ),
        _gate_row(
            "Technical, macro, and validation components are present",
            (not gates.get("require_active_technical_macro_validation_components", True))
            or bool(row["active_required_components_present"]),
            (
                "active_required_components_present="
                f"{bool(row['active_required_components_present'])}"
            ),
        ),
        _gate_row(
            "Future unaudited families are blocked",
            (not gates.get("require_future_families_blocked", True))
            or bool(row["future_families_blocked"]),
            f"future_families_blocked={bool(row['future_families_blocked'])}",
        ),
        _gate_row(
            "Conceptual directions are documented and non-trading",
            (not gates.get("require_conceptual_directions", True))
            or (
                int(row["conceptual_direction_count"]) > 0
                and bool(row["conceptual_directions_non_trading"])
            ),
            (
                f"conceptual_direction_count={int(row['conceptual_direction_count'])}; "
                "conceptual_directions_non_trading="
                f"{bool(row['conceptual_directions_non_trading'])}"
            ),
        ),
        _gate_row(
            "Missingness rules are documented",
            (not gates.get("require_missingness_rules", True))
            or int(row["missingness_rule_count"])
            >= int(gates.get("min_missingness_rules", 5)),
            f"missingness_rule_count={int(row['missingness_rule_count'])}",
        ),
        _gate_row(
            "Weighting principles are documented",
            (not gates.get("require_weighting_principles", True))
            or int(row["weighting_principle_count"])
            >= int(gates.get("min_weighting_principles", 5)),
            f"weighting_principle_count={int(row['weighting_principle_count'])}",
        ),
        _gate_row(
            "Score states are non-trading concepts",
            (not gates.get("require_score_states_non_trading", True))
            or bool(row["score_states_non_trading"]),
            f"score_states_non_trading={bool(row['score_states_non_trading'])}",
        ),
        _gate_row(
            "Audit output spec is documented",
            (not gates.get("require_audit_output_spec", True))
            or int(row["audit_output_count"]) >= int(gates.get("min_audit_outputs", 5)),
            f"audit_output_count={int(row['audit_output_count'])}",
        ),
        _gate_row(
            "Future validation gates are documented",
            (not gates.get("require_future_validation_gates", True))
            or int(row["future_validation_gate_count"])
            >= int(gates.get("min_future_validation_gates", 6)),
            f"future_validation_gate_count={int(row['future_validation_gate_count'])}",
        ),
        _gate_row(
            "Phase 11D boundary is design-only",
            (not gates.get("require_phase11d_boundary_spec_only", True))
            or bool(row["phase11d_boundary_passed"]),
            f"phase11d_boundary_passed={bool(row['phase11d_boundary_passed'])}",
        ),
        _gate_row(
            "No score calculation is allowed",
            (not gates.get("require_no_score_calculation", True))
            or not bool(phase_config.get("allow_score_calculation", True)),
            f"allow_score_calculation={phase_config.get('allow_score_calculation')}",
        ),
        _gate_row(
            "No numeric score weights are allowed",
            (not gates.get("require_no_numeric_score_weights", True))
            or not bool(phase_config.get("allow_numeric_score_weights", True)),
            (
                "allow_numeric_score_weights="
                f"{phase_config.get('allow_numeric_score_weights')}"
            ),
        ),
        _gate_row(
            "No empirical return weights are allowed",
            (not gates.get("require_no_empirical_return_weights", True))
            or not bool(phase_config.get("allow_empirical_return_weights", True)),
            (
                "allow_empirical_return_weights="
                f"{phase_config.get('allow_empirical_return_weights')}"
            ),
        ),
        _gate_row(
            "No signal creation is allowed",
            (not gates.get("require_no_signal_creation", True))
            or not bool(phase_config.get("allow_signal_creation", True)),
            f"allow_signal_creation={phase_config.get('allow_signal_creation')}",
        ),
        _gate_row(
            "No allocation rule creation is allowed",
            (not gates.get("require_no_allocation_rule_creation", True))
            or not bool(phase_config.get("allow_allocation_rule_creation", True)),
            (
                "allow_allocation_rule_creation="
                f"{phase_config.get('allow_allocation_rule_creation')}"
            ),
        ),
        _gate_row(
            "No strategy backtest is allowed",
            (not gates.get("require_no_strategy_backtest", True))
            or not bool(phase_config.get("allow_strategy_backtest", True)),
            f"allow_strategy_backtest={phase_config.get('allow_strategy_backtest')}",
        ),
        _gate_row(
            "No model training is allowed",
            (not gates.get("require_no_model_training", True))
            or not bool(phase_config.get("allow_model_training", True)),
            f"allow_model_training={phase_config.get('allow_model_training')}",
        ),
        _gate_row(
            "No new data ingestion is allowed",
            (not gates.get("require_no_new_data_ingestion", True))
            or not bool(phase_config.get("allow_new_data_ingestion", True)),
            f"allow_new_data_ingestion={phase_config.get('allow_new_data_ingestion')}",
        ),
        _gate_row(
            "No candidate promotion is allowed",
            (not gates.get("require_no_candidate_promotion", True))
            or not bool(phase_config.get("allow_candidate_promotion", True)),
            f"allow_candidate_promotion={phase_config.get('allow_candidate_promotion')}",
        ),
        _gate_row(
            "Spec role is correct",
            str(row["spec_role"]) == required_role,
            f"spec_role={row['spec_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase11c_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    if all_passed:
        verdict = "Completed — regime scoring rulebook spec passed"
        interpretation = (
            "Phase 11C defined a regime-scoring rulebook spec only. It documented "
            "component categories, conceptual directions, missingness rules, "
            "weighting principles, audit outputs, and future validation gates, but "
            "did not calculate scores, create signals, test a strategy, train a "
            "model, ingest new data, or promote a candidate."
        )
    else:
        verdict = "Failed regime scoring rulebook spec discipline"
        interpretation = (
            "Phase 11C violated rulebook-spec boundaries or left required controls "
            "incomplete. Do not proceed to diagnostic-panel design."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 11C",
                "diagnostic": "Regime scoring rulebook spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase11c_markdown(
    *,
    source_architecture: pd.DataFrame,
    component_rulebook: pd.DataFrame,
    conceptual_direction_rulebook: pd.DataFrame,
    missingness_rules: pd.DataFrame,
    weighting_principles: pd.DataFrame,
    score_state_rulebook: pd.DataFrame,
    audit_output_spec: pd.DataFrame,
    future_validation_gates: pd.DataFrame,
    phase11d_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 11C — Regime Scoring Rulebook Spec",
        "",
        "## Purpose",
        "",
        (
            "This phase defines the future regime-scoring rulebook grammar without "
            "calculating scores, assigning empirical weights, creating signals, "
            "running strategy tests, ingesting new data, training models, or "
            "promoting a candidate."
        ),
        "",
        "## Source Architecture",
        "",
        source_architecture.to_markdown(index=False),
        "",
        "## Component Rulebook",
        "",
        component_rulebook.to_markdown(index=False),
        "",
        "## Conceptual Direction Rulebook",
        "",
        conceptual_direction_rulebook.to_markdown(index=False),
        "",
        "## Missingness Rules",
        "",
        missingness_rules.to_markdown(index=False),
        "",
        "## Weighting Principles",
        "",
        weighting_principles.to_markdown(index=False),
        "",
        "## Score State Rulebook",
        "",
        score_state_rulebook.to_markdown(index=False),
        "",
        "## Audit Output Spec",
        "",
        audit_output_spec.to_markdown(index=False),
        "",
        "## Future Validation Gates",
        "",
        future_validation_gates.to_markdown(index=False),
        "",
        "## Phase 11D Boundary Check",
        "",
        phase11d_boundary_check.to_markdown(index=False),
        "",
        "## Scope Boundary Check",
        "",
        scope_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        "",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        conclusion.to_markdown(index=False),
        "",
        "## Limitations",
        "",
        "- This is a rulebook spec only.",
        "- It does not calculate regime scores.",
        "- It does not assign empirical score weights.",
        "- It does not create signals or allocation rules.",
        "- It does not run a strategy backtest.",
        "- It does not ingest new data or train a model.",
        "- It does not promote a candidate.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase11c_regime_scoring_rulebook_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "source_architecture": empty,
            "component_rulebook": empty,
            "conceptual_direction_rulebook": empty,
            "missingness_rules": empty,
            "weighting_principles": empty,
            "score_state_rulebook": empty,
            "audit_output_spec": empty,
            "future_validation_gates": empty,
            "phase11d_boundary_check": empty,
            "scope_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_architecture = build_phase11c_source_architecture(phase_config)
    component_rulebook = build_phase11c_component_rulebook(phase_config)
    conceptual_direction_rulebook = build_phase11c_conceptual_direction_rulebook(
        phase_config
    )
    missingness_rules = build_phase11c_missingness_rules(phase_config)
    weighting_principles = build_phase11c_weighting_principles(phase_config)
    score_state_rulebook = build_phase11c_score_state_rulebook(phase_config)
    audit_output_spec = build_phase11c_audit_output_spec(phase_config)
    future_validation_gates = build_phase11c_future_validation_gates(phase_config)
    phase11d_boundary_check = build_phase11c_phase11d_boundary_check(phase_config)
    scope_boundary_check = build_phase11c_scope_boundary_check(phase_config)
    summary = build_phase11c_summary(
        phase_config=phase_config,
        source_architecture=source_architecture,
        component_rulebook=component_rulebook,
        conceptual_direction_rulebook=conceptual_direction_rulebook,
        missingness_rules=missingness_rules,
        weighting_principles=weighting_principles,
        score_state_rulebook=score_state_rulebook,
        audit_output_spec=audit_output_spec,
        future_validation_gates=future_validation_gates,
        phase11d_boundary_check=phase11d_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase11c_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11c_conclusion(gate_report)

    source_architecture.to_csv(
        reports_path / "phase11c_regime_scoring_source_architecture.csv",
        index=False,
    )
    component_rulebook.to_csv(
        reports_path / "phase11c_regime_scoring_component_rulebook.csv",
        index=False,
    )
    conceptual_direction_rulebook.to_csv(
        reports_path / "phase11c_regime_scoring_conceptual_direction_rulebook.csv",
        index=False,
    )
    missingness_rules.to_csv(
        reports_path / "phase11c_regime_scoring_missingness_rules.csv",
        index=False,
    )
    weighting_principles.to_csv(
        reports_path / "phase11c_regime_scoring_weighting_principles.csv",
        index=False,
    )
    score_state_rulebook.to_csv(
        reports_path / "phase11c_regime_scoring_state_rulebook.csv",
        index=False,
    )
    audit_output_spec.to_csv(
        reports_path / "phase11c_regime_scoring_audit_output_spec.csv",
        index=False,
    )
    future_validation_gates.to_csv(
        reports_path / "phase11c_regime_scoring_future_validation_gates.csv",
        index=False,
    )
    phase11d_boundary_check.to_csv(
        reports_path / "phase11c_regime_scoring_phase11d_boundary_check.csv",
        index=False,
    )
    scope_boundary_check.to_csv(
        reports_path / "phase11c_regime_scoring_scope_boundary_check.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase11c_regime_scoring_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase11c_regime_scoring_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase11c_regime_scoring_conclusion.csv",
        index=False,
    )

    write_phase11c_markdown(
        source_architecture=source_architecture,
        component_rulebook=component_rulebook,
        conceptual_direction_rulebook=conceptual_direction_rulebook,
        missingness_rules=missingness_rules,
        weighting_principles=weighting_principles,
        score_state_rulebook=score_state_rulebook,
        audit_output_spec=audit_output_spec,
        future_validation_gates=future_validation_gates,
        phase11d_boundary_check=phase11d_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase11c_regime_scoring_rulebook_spec.md",
    )

    print("Wrote Phase 11C regime scoring rulebook spec reports.")

    return {
        "source_architecture": source_architecture,
        "component_rulebook": component_rulebook,
        "conceptual_direction_rulebook": conceptual_direction_rulebook,
        "missingness_rules": missingness_rules,
        "weighting_principles": weighting_principles,
        "score_state_rulebook": score_state_rulebook,
        "audit_output_spec": audit_output_spec,
        "future_validation_gates": future_validation_gates,
        "phase11d_boundary_check": phase11d_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }