from pathlib import Path

import pandas as pd

from market_strats.analysis.score_calculation_prereg_and_readiness_audit import (
    build_phase12a_eligible_components,
    build_phase12a_formula_structure,
    build_phase12b_readiness_claims_check,
    save_phase12a_score_calculation_preregistration_spec,
    save_phase12b_score_calculation_readiness_audit,
)


def _touch_source_reports(tmp_path: Path):
    for name in [
        "phase11e_template_component_availability_report.csv",
        "phase11e_template_component_direction_report.csv",
        "phase11e_template_missingness_report.csv",
        "phase11e_template_weighting_policy_report.csv",
        "phase11e_template_blocked_family_report.csv",
        "phase11g_final_checkpoint_conclusion.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase12a_score_calculation_preregistration_spec": {
            "enabled": True,
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
            "source_inputs": {
                "component_availability_report": str(tmp_path / "phase11e_template_component_availability_report.csv"),
                "component_direction_report": str(tmp_path / "phase11e_template_component_direction_report.csv"),
                "missingness_report": str(tmp_path / "phase11e_template_missingness_report.csv"),
                "weighting_policy_report": str(tmp_path / "phase11e_template_weighting_policy_report.csv"),
                "blocked_family_report": str(tmp_path / "phase11e_template_blocked_family_report.csv"),
                "phase11g_conclusion": str(tmp_path / "phase11g_final_checkpoint_conclusion.csv"),
            },
            "eligible_components": [
                {"component_id": "technical_regime_context", "family": "technical", "eligibility": "eligible", "source_basis": "Phase 9", "allowed_states": ["supportive", "neutral", "fragile"], "may_affect_future_score": True, "may_create_signal_now": False},
                {"component_id": "macro_regime_context", "family": "macro", "eligibility": "eligible", "source_basis": "Phase 10", "allowed_states": ["supportive", "neutral", "fragile"], "may_affect_future_score": True, "may_create_signal_now": False},
                {"component_id": "validation_risk_context", "family": "validation", "eligibility": "eligible_control", "source_basis": "Phase 8", "allowed_states": ["supportive", "neutral", "fragile"], "may_affect_future_score": True, "may_create_signal_now": False},
            ],
            "blocked_components": [
                {"component_id": "future_fundamental_context", "family": "fundamental_valuation", "blocked_reason": "No audit.", "unblock_requires": "Future audit.", "may_affect_future_score": False},
                {"component_id": "future_sentiment_context", "family": "sentiment_narrative", "blocked_reason": "No audit.", "unblock_requires": "Future audit.", "may_affect_future_score": False},
            ],
            "formula_structure": {
                "formula_id": "pre_registered_three_component_regime_score",
                "formula_role": "future diagnostic grammar only",
                "aggregation_policy": "non_return_equal_component_vote",
                "allowed_component_states": ["supportive", "neutral", "fragile"],
                "score_state_output": ["supportive", "neutral", "fragile"],
                "numeric_score_values_defined": False,
                "empirical_weights_allowed": False,
                "returns_used_for_formula_design": False,
                "description": "future diagnostic score grammar only",
            },
            "weighting_policy": {
                "policy_id": "non_return_equal_component_policy",
                "policy_type": "pre_registered_non_return_based_policy",
                "eligible_component_scope": "technical_macro_validation",
                "empirical_return_weighting_allowed": False,
                "optimisation_allowed": False,
                "cutoff_search_allowed": False,
                "numeric_weights_assigned_now": False,
                "pre_registration_required_before_calculation": True,
            },
            "missingness_policy": {
                "policy_id": "explicit_missingness_caution_policy",
                "no_return_inference": True,
                "no_silent_fill": True,
                "unavailable_component_action": "mark_unavailable",
                "blocked_component_action": "exclude_and_flag_blocked",
                "validation_risk_missing_action": "default_to_caution",
                "score_calculation_allowed_with_missing_validation_risk": False,
            },
            "score_state_interpretation": [
                {"state": "supportive", "interpretation": "supportive", "trading_allowed": False, "signal_allowed": False},
                {"state": "neutral", "interpretation": "neutral", "trading_allowed": False, "signal_allowed": False},
                {"state": "fragile", "interpretation": "fragile", "trading_allowed": False, "signal_allowed": False},
            ],
            "future_validation_gates": [{"gate_id": f"g{i}", "gate": "gate", "required": True} for i in range(6)],
            "failure_conditions": [{"condition_id": f"f{i}", "condition": "fail"} for i in range(6)],
            "phase12b_boundary": {
                "allowed_next_step": "Score-calculation readiness audit only",
                "forbidden_next_step": "actual score calculation, signal creation, allocation rule, strategy backtest, model training, new data ingestion, or candidate promotion",
                "phase12b_may_audit_preregistration": True,
                "phase12b_may_calculate_scores": False,
                "phase12b_may_assign_empirical_weights": False,
                "phase12b_may_create_signal": False,
                "phase12b_may_test_strategy": False,
                "phase12b_may_train_model": False,
                "phase12b_may_ingest_new_data": False,
                "phase12b_may_promote_candidate": False,
            },
        },
        "phase12b_score_calculation_readiness_audit": {
            "enabled": True,
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
            "expected_runtime_flags": {
                "phase12a_score_calculation_preregistration_spec": True,
                "phase12b_score_calculation_readiness_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase12a_reports": {
                "gate_report": str(tmp_path / "phase12a_prereg_gate_report.csv"),
                "conclusion": str(tmp_path / "phase12a_prereg_conclusion.csv"),
                "eligible_components": str(tmp_path / "phase12a_prereg_eligible_components.csv"),
            },
            "readiness_claims": {
                "preregistration_exists": True,
                "eligible_components_locked": True,
                "blocked_components_locked": True,
                "formula_structure_locked": True,
                "weighting_policy_locked": True,
                "missingness_policy_locked": True,
                "failure_conditions_locked": True,
                "score_calculated": False,
                "signal_created": False,
                "backtest_run": False,
                "model_trained": False,
                "new_data_ingested": False,
                "candidate_promoted": False,
            },
            "phase12c_boundary": {
                "allowed_next_step": "Diagnostic score calculation only",
                "forbidden_next_step": "trading signal creation, allocation rule, strategy backtest, model training, new data ingestion, or candidate promotion",
                "phase12c_may_calculate_diagnostic_scores": True,
                "phase12c_may_assign_empirical_weights": False,
                "phase12c_may_create_signal": False,
                "phase12c_may_test_strategy": False,
                "phase12c_may_train_model": False,
                "phase12c_may_ingest_new_data": False,
                "phase12c_may_promote_candidate": False,
            },
        },
    }


def test_phase12a_and_12b_save_reports(tmp_path):
    _touch_source_reports(tmp_path)
    config = _config(tmp_path)

    out_a = save_phase12a_score_calculation_preregistration_spec(
        config=config,
        reports_dir=tmp_path,
    )
    out_b = save_phase12b_score_calculation_readiness_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_a["conclusion"].iloc[0]["all_gates_passed"]
    assert out_b["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase12a_prereg_conclusion.csv").exists()
    assert (tmp_path / "phase12b_readiness_conclusion.csv").exists()
    assert (tmp_path / "phase12a_score_calculation_preregistration_spec.md").exists()
    assert (tmp_path / "phase12b_score_calculation_readiness_audit.md").exists()


def test_phase12a_formula_blocks_empirical_weights(tmp_path):
    _touch_source_reports(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase12a_score_calculation_preregistration_spec"]

    eligible = build_phase12a_eligible_components(phase_config)
    formula = build_phase12a_formula_structure(phase_config)

    assert len(eligible) == 3
    assert not bool(formula.iloc[0]["empirical_weights_allowed"])
    assert not bool(formula.iloc[0]["returns_used_for_formula_design"])


def test_phase12b_readiness_claims_fail_if_score_already_calculated(tmp_path):
    config = _config(tmp_path)
    phase_config = config["phase12b_score_calculation_readiness_audit"]
    phase_config["readiness_claims"]["score_calculated"] = True

    claims = build_phase12b_readiness_claims_check(phase_config)

    assert not bool(claims["passed"].all())