from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE11B_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Regime scoring architecture spec only",
    "phase_branch": "Phase 11 architecture review",
    "proposed_next_phase": "Phase 11C",
    "source_architecture_decision": {},
    "allow_score_calculation": False,
    "allow_score_weights": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "scoring_principles": [],
    "component_families": [],
    "score_state_design": [],
    "future_validation_requirements": [],
    "phase11c_boundary": {
        "allowed_next_step": "Regime scoring rulebook spec only",
        "forbidden_next_step": (
            "score calculation, model training, strategy backtest, or candidate promotion"
        ),
        "phase11c_may_define_score_components": True,
        "phase11c_may_define_weighting_policy": True,
        "phase11c_may_calculate_scores": False,
        "phase11c_may_test_strategy": False,
        "phase11c_may_train_model": False,
        "phase11c_may_ingest_new_data": False,
        "phase11c_may_promote_candidate": False,
    },
    "gates": {
        "require_source_architecture_decision": True,
        "require_scoring_principles": True,
        "min_scoring_principles": 5,
        "require_component_families": True,
        "min_component_families": 4,
        "require_validation_risk_context": True,
        "require_future_data_families_blocked": True,
        "require_score_states_non_trading": True,
        "require_future_validation_requirements": True,
        "min_future_validation_requirements": 5,
        "require_phase11c_boundary_spec_only": True,
        "require_no_score_calculation": True,
        "require_no_score_weights": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "required_spec_role": "Regime scoring architecture spec only",
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
    user_config = config.get("phase11b_regime_scoring_architecture_spec", {})
    return _deep_merge_dict(DEFAULT_PHASE11B_CONFIG, user_config)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _join_list(value: Any) -> str:
    return "; ".join(str(item) for item in _as_list(value))


def build_phase11b_source_decision(phase_config: dict[str, Any]) -> pd.DataFrame:
    decision = phase_config.get("source_architecture_decision", {})

    return pd.DataFrame(
        [
            {
                "source_phase": str(decision.get("source_phase", "")),
                "selected_architecture": str(decision.get("selected_architecture", "")),
                "rejected_immediate_architecture": str(
                    decision.get("rejected_immediate_architecture", "")
                ),
                "rationale": str(decision.get("rationale", "")),
                "source_decision_present": bool(
                    str(decision.get("selected_architecture", "")).strip()
                ),
                "simple_overlay_rejected": "simple" in str(
                    decision.get("rejected_immediate_architecture", "")
                ).lower(),
            }
        ]
    )


def build_phase11b_scoring_principles(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for principle in _as_list(phase_config.get("scoring_principles")):
        rows.append(
            {
                "principle_id": str(principle.get("principle_id", "")),
                "principle": str(principle.get("principle", "")),
                "required": bool(principle.get("required", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11b_component_registry(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for component in _as_list(phase_config.get("component_families")):
        rows.append(
            {
                "component_id": str(component.get("component_id", "")),
                "family": str(component.get("family", "")),
                "role": str(component.get("role", "")),
                "source_evidence": str(component.get("source_evidence", "")),
                "allowed_conceptual_inputs": _join_list(
                    component.get("allowed_conceptual_inputs")
                ),
                "forbidden_current_use": _join_list(
                    component.get("forbidden_current_use")
                ),
                "allowed_for_phase11c_spec": bool(
                    component.get("allowed_for_phase11c_spec", False)
                ),
                "currently_active": bool(component.get("currently_active", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11b_score_state_design(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for state in _as_list(phase_config.get("score_state_design")):
        rows.append(
            {
                "state_id": str(state.get("state_id", "")),
                "description": str(state.get("description", "")),
                "allowed_current_role": str(state.get("allowed_current_role", "")),
                "trading_allowed": bool(state.get("trading_allowed", True)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11b_future_validation_requirements(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for requirement in _as_list(phase_config.get("future_validation_requirements")):
        rows.append(
            {
                "requirement_id": str(requirement.get("requirement_id", "")),
                "requirement": str(requirement.get("requirement", "")),
            }
        )

    return pd.DataFrame(rows)


def build_phase11b_phase11c_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase11c_boundary", {})

    rows = [
        {
            "boundary_item": "phase11c_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "spec" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase11c_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
                or "model" in str(boundary.get("forbidden_next_step", "")).lower()
                or "promotion" in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase11c_may_define_score_components",
            "value": bool(boundary.get("phase11c_may_define_score_components", False)),
            "passed": bool(boundary.get("phase11c_may_define_score_components", False)),
        },
        {
            "boundary_item": "phase11c_may_define_weighting_policy",
            "value": bool(boundary.get("phase11c_may_define_weighting_policy", False)),
            "passed": bool(boundary.get("phase11c_may_define_weighting_policy", False)),
        },
        {
            "boundary_item": "phase11c_may_calculate_scores",
            "value": bool(boundary.get("phase11c_may_calculate_scores", True)),
            "passed": not bool(boundary.get("phase11c_may_calculate_scores", True)),
        },
        {
            "boundary_item": "phase11c_may_test_strategy",
            "value": bool(boundary.get("phase11c_may_test_strategy", True)),
            "passed": not bool(boundary.get("phase11c_may_test_strategy", True)),
        },
        {
            "boundary_item": "phase11c_may_train_model",
            "value": bool(boundary.get("phase11c_may_train_model", True)),
            "passed": not bool(boundary.get("phase11c_may_train_model", True)),
        },
        {
            "boundary_item": "phase11c_may_ingest_new_data",
            "value": bool(boundary.get("phase11c_may_ingest_new_data", True)),
            "passed": not bool(boundary.get("phase11c_may_ingest_new_data", True)),
        },
        {
            "boundary_item": "phase11c_may_promote_candidate",
            "value": bool(boundary.get("phase11c_may_promote_candidate", True)),
            "passed": not bool(boundary.get("phase11c_may_promote_candidate", True)),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11b_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "scope_item": "No score calculation",
            "value": bool(phase_config.get("allow_score_calculation", True)),
            "passed": not bool(phase_config.get("allow_score_calculation", True)),
        },
        {
            "scope_item": "No score weights",
            "value": bool(phase_config.get("allow_score_weights", True)),
            "passed": not bool(phase_config.get("allow_score_weights", True)),
        },
        {
            "scope_item": "No signal creation",
            "value": bool(phase_config.get("allow_signal_creation", True)),
            "passed": not bool(phase_config.get("allow_signal_creation", True)),
        },
        {
            "scope_item": "No allocation rule creation",
            "value": bool(phase_config.get("allow_allocation_rule_creation", True)),
            "passed": not bool(phase_config.get("allow_allocation_rule_creation", True)),
        },
        {
            "scope_item": "No strategy backtest",
            "value": bool(phase_config.get("allow_strategy_backtest", True)),
            "passed": not bool(phase_config.get("allow_strategy_backtest", True)),
        },
        {
            "scope_item": "No model training",
            "value": bool(phase_config.get("allow_model_training", True)),
            "passed": not bool(phase_config.get("allow_model_training", True)),
        },
        {
            "scope_item": "No new data ingestion",
            "value": bool(phase_config.get("allow_new_data_ingestion", True)),
            "passed": not bool(phase_config.get("allow_new_data_ingestion", True)),
        },
        {
            "scope_item": "No candidate promotion",
            "value": bool(phase_config.get("allow_candidate_promotion", True)),
            "passed": not bool(phase_config.get("allow_candidate_promotion", True)),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11b_summary(
    *,
    phase_config: dict[str, Any],
    source_decision: pd.DataFrame,
    scoring_principles: pd.DataFrame,
    component_registry: pd.DataFrame,
    score_state_design: pd.DataFrame,
    validation_requirements: pd.DataFrame,
    phase11c_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    validation_context_present = (
        "validation_risk_context" in component_registry["component_id"].tolist()
        if not component_registry.empty
        else False
    )
    future_families_blocked = (
        bool(
            component_registry[
                component_registry["family"].isin(
                    ["fundamental_valuation", "sentiment_narrative"]
                )
            ]["allowed_for_phase11c_spec"]
            .eq(False)
            .all()
        )
        if not component_registry.empty
        else False
    )
    score_states_non_trading = (
        bool(score_state_design["trading_allowed"].eq(False).all())
        if not score_state_design.empty
        else False
    )

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_decision_present": bool(
                    source_decision.iloc[0]["source_decision_present"]
                )
                if not source_decision.empty
                else False,
                "simple_overlay_rejected": bool(
                    source_decision.iloc[0]["simple_overlay_rejected"]
                )
                if not source_decision.empty
                else False,
                "scoring_principle_count": int(len(scoring_principles)),
                "required_scoring_principle_count": int(
                    scoring_principles["required"].sum()
                )
                if not scoring_principles.empty
                else 0,
                "component_family_count": int(len(component_registry)),
                "validation_risk_context_present": validation_context_present,
                "future_data_families_blocked": future_families_blocked,
                "score_state_count": int(len(score_state_design)),
                "score_states_non_trading": score_states_non_trading,
                "future_validation_requirement_count": int(
                    len(validation_requirements)
                ),
                "phase11c_boundary_passed": bool(
                    phase11c_boundary_check["passed"].all()
                )
                if not phase11c_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
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


def build_phase11b_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 11B summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get("required_spec_role", "Regime scoring architecture spec only")
    )

    rows = [
        _gate_row(
            "Source architecture decision is documented",
            (not gates.get("require_source_architecture_decision", True))
            or bool(row["source_decision_present"]),
            f"source_decision_present={bool(row['source_decision_present'])}",
        ),
        _gate_row(
            "Scoring principles are documented",
            (not gates.get("require_scoring_principles", True))
            or int(row["scoring_principle_count"])
            >= int(gates.get("min_scoring_principles", 5)),
            f"scoring_principle_count={int(row['scoring_principle_count'])}",
        ),
        _gate_row(
            "Component families are documented",
            (not gates.get("require_component_families", True))
            or int(row["component_family_count"])
            >= int(gates.get("min_component_families", 4)),
            f"component_family_count={int(row['component_family_count'])}",
        ),
        _gate_row(
            "Validation-risk context is included",
            (not gates.get("require_validation_risk_context", True))
            or bool(row["validation_risk_context_present"]),
            (
                "validation_risk_context_present="
                f"{bool(row['validation_risk_context_present'])}"
            ),
        ),
        _gate_row(
            "Future unaudited data families are blocked",
            (not gates.get("require_future_data_families_blocked", True))
            or bool(row["future_data_families_blocked"]),
            (
                "future_data_families_blocked="
                f"{bool(row['future_data_families_blocked'])}"
            ),
        ),
        _gate_row(
            "Score states are non-trading concepts",
            (not gates.get("require_score_states_non_trading", True))
            or bool(row["score_states_non_trading"]),
            f"score_states_non_trading={bool(row['score_states_non_trading'])}",
        ),
        _gate_row(
            "Future validation requirements are documented",
            (not gates.get("require_future_validation_requirements", True))
            or int(row["future_validation_requirement_count"])
            >= int(gates.get("min_future_validation_requirements", 5)),
            (
                "future_validation_requirement_count="
                f"{int(row['future_validation_requirement_count'])}"
            ),
        ),
        _gate_row(
            "Phase 11C boundary is spec-only",
            (not gates.get("require_phase11c_boundary_spec_only", True))
            or bool(row["phase11c_boundary_passed"]),
            f"phase11c_boundary_passed={bool(row['phase11c_boundary_passed'])}",
        ),
        _gate_row(
            "No score calculation is allowed",
            (not gates.get("require_no_score_calculation", True))
            or not bool(phase_config.get("allow_score_calculation", True)),
            f"allow_score_calculation={phase_config.get('allow_score_calculation')}",
        ),
        _gate_row(
            "No score weights are allowed",
            (not gates.get("require_no_score_weights", True))
            or not bool(phase_config.get("allow_score_weights", True)),
            f"allow_score_weights={phase_config.get('allow_score_weights')}",
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


def build_phase11b_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    if all_passed:
        verdict = "Completed — regime scoring architecture spec passed"
        interpretation = (
            "Phase 11B defined a design-only regime scoring architecture. It did "
            "not calculate scores, create signals, run backtests, ingest new data, "
            "train models, or promote a candidate. Phase 11C may only define a "
            "score rulebook spec."
        )
    else:
        verdict = "Failed regime scoring architecture spec discipline"
        interpretation = (
            "Phase 11B violated architecture-spec boundaries or left required "
            "design controls incomplete. Do not proceed to scoring implementation."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 11B",
                "diagnostic": "Regime scoring architecture spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase11b_markdown(
    *,
    source_decision: pd.DataFrame,
    scoring_principles: pd.DataFrame,
    component_registry: pd.DataFrame,
    score_state_design: pd.DataFrame,
    validation_requirements: pd.DataFrame,
    phase11c_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 11B — Regime Scoring Architecture Spec",
        "",
        "## Purpose",
        "",
        (
            "This phase defines the design boundaries for a future regime scoring "
            "layer after simple technical and macro rule overlays failed validation."
        ),
        "",
        (
            "It does not calculate scores, create signals, create allocation rules, "
            "run strategy backtests, ingest new data, train models, or promote a "
            "candidate."
        ),
        "",
        "## Source Architecture Decision",
        "",
        source_decision.to_markdown(index=False),
        "",
        "## Scoring Principles",
        "",
        scoring_principles.to_markdown(index=False),
        "",
        "## Component Registry",
        "",
        component_registry.to_markdown(index=False),
        "",
        "## Score State Design",
        "",
        score_state_design.to_markdown(index=False),
        "",
        "## Future Validation Requirements",
        "",
        validation_requirements.to_markdown(index=False),
        "",
        "## Phase 11C Boundary Check",
        "",
        phase11c_boundary_check.to_markdown(index=False),
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
        "- This is an architecture spec only.",
        "- It does not calculate a regime score.",
        "- It does not create a tradable signal.",
        "- It does not test a strategy.",
        "- It does not train a model.",
        "- It does not promote a candidate.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase11b_regime_scoring_architecture_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "source_decision": empty,
            "scoring_principles": empty,
            "component_registry": empty,
            "score_state_design": empty,
            "validation_requirements": empty,
            "phase11c_boundary_check": empty,
            "scope_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_decision = build_phase11b_source_decision(phase_config)
    scoring_principles = build_phase11b_scoring_principles(phase_config)
    component_registry = build_phase11b_component_registry(phase_config)
    score_state_design = build_phase11b_score_state_design(phase_config)
    validation_requirements = build_phase11b_future_validation_requirements(
        phase_config
    )
    phase11c_boundary_check = build_phase11b_phase11c_boundary_check(phase_config)
    scope_boundary_check = build_phase11b_scope_boundary_check(phase_config)
    summary = build_phase11b_summary(
        phase_config=phase_config,
        source_decision=source_decision,
        scoring_principles=scoring_principles,
        component_registry=component_registry,
        score_state_design=score_state_design,
        validation_requirements=validation_requirements,
        phase11c_boundary_check=phase11c_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase11b_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11b_conclusion(gate_report)

    source_decision.to_csv(
        reports_path / "phase11b_regime_scoring_source_decision.csv",
        index=False,
    )
    scoring_principles.to_csv(
        reports_path / "phase11b_regime_scoring_principles.csv",
        index=False,
    )
    component_registry.to_csv(
        reports_path / "phase11b_regime_scoring_component_registry.csv",
        index=False,
    )
    score_state_design.to_csv(
        reports_path / "phase11b_regime_scoring_state_design.csv",
        index=False,
    )
    validation_requirements.to_csv(
        reports_path / "phase11b_regime_scoring_validation_requirements.csv",
        index=False,
    )
    phase11c_boundary_check.to_csv(
        reports_path / "phase11b_regime_scoring_phase11c_boundary_check.csv",
        index=False,
    )
    scope_boundary_check.to_csv(
        reports_path / "phase11b_regime_scoring_scope_boundary_check.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase11b_regime_scoring_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase11b_regime_scoring_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase11b_regime_scoring_conclusion.csv",
        index=False,
    )

    write_phase11b_markdown(
        source_decision=source_decision,
        scoring_principles=scoring_principles,
        component_registry=component_registry,
        score_state_design=score_state_design,
        validation_requirements=validation_requirements,
        phase11c_boundary_check=phase11c_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase11b_regime_scoring_architecture_spec.md",
    )

    print("Wrote Phase 11B regime scoring architecture spec reports.")

    return {
        "source_decision": source_decision,
        "scoring_principles": scoring_principles,
        "component_registry": component_registry,
        "score_state_design": score_state_design,
        "validation_requirements": validation_requirements,
        "phase11c_boundary_check": phase11c_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }