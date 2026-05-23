from market_strats.analysis.preregistered_macro_hypothesis_spec import (
    build_phase10e_allowed_inputs,
    build_phase10e_conclusion,
    build_phase10e_failure_conditions,
    build_phase10e_forbidden_inputs,
    build_phase10e_gate_report,
    build_phase10e_hypothesis_spec,
    build_phase10e_phase10f_boundary_check,
    build_phase10e_registry,
    build_phase10e_summary,
    build_phase10e_validation_gates,
    save_phase10e_preregistered_macro_hypothesis_spec,
)


def _sample_phase_config():
    return {
        "spec_role": "Pre-registered macro hypothesis design spec only",
        "proposed_test_phase": "Phase 10F",
        "allow_macro_signal_creation": False,
        "allow_allocation_rule_creation": False,
        "allow_model_feature_creation": False,
        "allow_model_training": False,
        "allow_strategy_test": False,
        "allow_strategy_promotion": False,
        "allowed_macro_input_registry": [
            "DGS2",
            "CPIAUCSL",
            "UNRATE",
            "short_rate_level",
            "inflation_yoy",
            "unemployment_level",
            "existing_final_candidate_mode",
            "existing_final_candidate_return",
        ],
        "allowed_evaluation_inputs": [
            "SPY Buy & Hold return",
            "SPY 12M Momentum return",
            "final candidate return",
        ],
        "forbidden_inputs": [
            "sentiment",
            "ML-generated regimes",
            "future returns",
            "post-hoc thresholds",
        ],
        "hypotheses": [
            {
                "hypothesis_id": "H1_supportive_low_rate_low_inflation_relief",
                "name": "Supportive low-rate / low-inflation macro relief hypothesis",
                "source_phase": "Phase 10D",
                "source_evidence": [
                    "Low short rates and low inflation were helpful in Phase 10D."
                ],
                "allowed_macro_inputs": [
                    "DGS2",
                    "CPIAUCSL",
                    "short_rate_level",
                    "inflation_yoy",
                    "existing_final_candidate_return",
                ],
                "fixed_macro_thresholds": {
                    "short_rate_level": "DGS2 below 1.5",
                    "inflation_yoy": "CPIAUCSL 252-trading-day inflation below 2%",
                },
                "proposed_phase10f_test_logic": "Pre-registered test only.",
                "forbidden_tuning": ["No threshold search."],
                "validation_gates": ["Must improve Calmar."],
                "failure_conditions": ["Fails if drawdown worsens."],
                "readme_wording_if_passed": "Passed for further validation only.",
                "readme_wording_if_mixed": "Mixed evidence; no promotion.",
                "readme_wording_if_failed": "Failed; do not tune.",
                "max_allowed_role_after_phase10f": "Candidate for further validation only",
            },
            {
                "hypothesis_id": "H2_high_rate_high_unemployment_stress_guard",
                "name": "High-rate / high-unemployment macro stress-guard hypothesis",
                "source_phase": "Phase 10D",
                "source_evidence": [
                    "High short rates and high unemployment were weak or mixed in Phase 10D."
                ],
                "allowed_macro_inputs": [
                    "DGS2",
                    "UNRATE",
                    "short_rate_level",
                    "unemployment_level",
                    "existing_final_candidate_return",
                ],
                "fixed_macro_thresholds": {
                    "short_rate_level": "DGS2 above 4.0",
                    "unemployment_level": "UNRATE above 6.0",
                },
                "proposed_phase10f_test_logic": "Pre-registered test only.",
                "forbidden_tuning": ["No threshold search."],
                "validation_gates": ["Must preserve drawdown."],
                "failure_conditions": ["Fails if holdout worsens."],
                "readme_wording_if_passed": "Passed for further validation only.",
                "readme_wording_if_mixed": "Mixed evidence; no promotion.",
                "readme_wording_if_failed": "Failed; do not tune.",
                "max_allowed_role_after_phase10f": "Candidate for further validation only",
            },
        ],
        "phase10f_boundary": {
            "allowed_next_step": "pre-registered macro-rule test only",
            "forbidden_next_step": "open-ended macro optimisation, ML model, or candidate promotion",
            "phase10f_may_test_only_preregistered_hypotheses": True,
            "phase10f_may_create_new_thresholds": False,
            "phase10f_may_add_new_inputs": False,
            "phase10f_may_train_model": False,
            "phase10f_may_promote_candidate": False,
        },
        "gates": {
            "min_hypotheses": 2,
            "max_hypotheses": 2,
            "require_source_evidence": True,
            "require_allowed_inputs": True,
            "require_allowed_inputs_inside_registry": True,
            "require_forbidden_inputs": True,
            "require_fixed_thresholds": True,
            "require_validation_gates": True,
            "require_failure_conditions": True,
            "require_readme_wording": True,
            "require_phase10f_boundary": True,
            "require_no_macro_signal_creation": True,
            "require_no_allocation_rule_creation": True,
            "require_no_model_feature_creation": True,
            "require_no_model_training": True,
            "require_no_strategy_test": True,
            "require_no_strategy_promotion": True,
            "required_spec_role": "Pre-registered macro hypothesis design spec only",
        },
    }


def test_phase10e_builds_preregistration_tables():
    phase_config = _sample_phase_config()

    registry = build_phase10e_registry(phase_config)
    hypothesis_spec = build_phase10e_hypothesis_spec(phase_config)
    allowed_inputs = build_phase10e_allowed_inputs(phase_config)
    forbidden_inputs = build_phase10e_forbidden_inputs(phase_config)
    validation_gates = build_phase10e_validation_gates(phase_config)
    failure_conditions = build_phase10e_failure_conditions(phase_config)
    boundary = build_phase10e_phase10f_boundary_check(phase_config)

    assert len(hypothesis_spec) == 2
    assert not registry.empty
    assert bool(allowed_inputs["registered"].all())
    assert not forbidden_inputs.empty
    assert not validation_gates.empty
    assert not failure_conditions.empty
    assert bool(boundary["passed"].all())


def test_phase10e_gate_report_passes_valid_spec():
    phase_config = _sample_phase_config()

    hypothesis_spec = build_phase10e_hypothesis_spec(phase_config)
    allowed_inputs = build_phase10e_allowed_inputs(phase_config)
    forbidden_inputs = build_phase10e_forbidden_inputs(phase_config)
    validation_gates = build_phase10e_validation_gates(phase_config)
    failure_conditions = build_phase10e_failure_conditions(phase_config)
    boundary = build_phase10e_phase10f_boundary_check(phase_config)
    summary = build_phase10e_summary(
        phase_config,
        hypothesis_spec,
        allowed_inputs,
        forbidden_inputs,
        validation_gates,
        failure_conditions,
        boundary,
    )
    gate_report = build_phase10e_gate_report(
        phase_config,
        hypothesis_spec,
        allowed_inputs,
        summary,
    )
    conclusion = build_phase10e_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — pre-registered macro hypothesis spec only"
    )


def test_phase10e_gate_report_fails_if_strategy_test_allowed():
    phase_config = _sample_phase_config()
    phase_config["allow_strategy_test"] = True

    hypothesis_spec = build_phase10e_hypothesis_spec(phase_config)
    allowed_inputs = build_phase10e_allowed_inputs(phase_config)
    forbidden_inputs = build_phase10e_forbidden_inputs(phase_config)
    validation_gates = build_phase10e_validation_gates(phase_config)
    failure_conditions = build_phase10e_failure_conditions(phase_config)
    boundary = build_phase10e_phase10f_boundary_check(phase_config)
    summary = build_phase10e_summary(
        phase_config,
        hypothesis_spec,
        allowed_inputs,
        forbidden_inputs,
        validation_gates,
        failure_conditions,
        boundary,
    )
    gate_report = build_phase10e_gate_report(
        phase_config,
        hypothesis_spec,
        allowed_inputs,
        summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase10e_writes_expected_reports(tmp_path):
    config = {
        "phase10e_preregistered_macro_hypothesis_spec": {
            "enabled": True,
            **_sample_phase_config(),
        }
    }

    outputs = save_phase10e_preregistered_macro_hypothesis_spec(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase10e_macro_input_registry.csv").exists()
    assert (tmp_path / "phase10e_macro_hypothesis_spec.csv").exists()
    assert (tmp_path / "phase10e_macro_allowed_inputs.csv").exists()
    assert (tmp_path / "phase10e_macro_forbidden_inputs.csv").exists()
    assert (tmp_path / "phase10e_macro_validation_gates.csv").exists()
    assert (tmp_path / "phase10e_macro_failure_conditions.csv").exists()
    assert (tmp_path / "phase10e_macro_phase10f_boundary_check.csv").exists()
    assert (tmp_path / "phase10e_macro_summary.csv").exists()
    assert (tmp_path / "phase10e_macro_gate_report.csv").exists()
    assert (tmp_path / "phase10e_macro_conclusion.csv").exists()
    assert (tmp_path / "phase10e_preregistered_macro_hypothesis_spec.md").exists()