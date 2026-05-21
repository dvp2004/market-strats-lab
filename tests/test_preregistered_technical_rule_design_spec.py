from market_strats.analysis.preregistered_technical_rule_design_spec import (
    build_phase9c_allowed_inputs,
    build_phase9c_conclusion,
    build_phase9c_forbidden_actions,
    build_phase9c_forbidden_inputs,
    build_phase9c_gate_report,
    build_phase9c_hypothesis_spec,
    build_phase9c_summary,
    build_phase9c_validation_gates,
    save_phase9c_preregistered_technical_rule_design_spec,
)


def _sample_phase_config():
    return {
        "spec_role": "Pre-registered design spec only",
        "proposed_test_phase": "Phase 9D",
        "allow_strategy_test": False,
        "allow_parameter_optimisation": False,
        "allow_strategy_promotion": False,
        "allowed_input_registry": [
            "rsi_14",
            "rsi_oversold_below_30",
            "existing_final_candidate_signal",
        ],
        "forbidden_input_keywords": ["macro", "sentiment", "ml", "tax"],
        "forbidden_actions": [
            "No threshold search after seeing results.",
            "No strategy promotion.",
        ],
        "required_validation_gates": [
            "Must improve Calmar.",
            "Must avoid holdout damage.",
        ],
        "hypotheses": [
            {
                "hypothesis_id": "H1",
                "name": "Oversold RSI hypothesis",
                "source_evidence": ["Phase 9A evidence", "Phase 9B evidence"],
                "allowed_inputs": [
                    "rsi_14",
                    "rsi_oversold_below_30",
                    "existing_final_candidate_signal",
                ],
                "forbidden_inputs": ["macro", "sentiment", "ml", "tax"],
                "proposed_rule_logic": ["Use only pre-registered RSI bucket."],
                "validation_gates": ["Must improve Calmar."],
                "failure_conditions": ["Fails if drawdown worsens."],
                "readme_wording_if_passed": "Passed as research candidate only.",
                "readme_wording_if_mixed": "Mixed and diagnostic only.",
                "readme_wording_if_failed": "Failed and rejected.",
                "promotion_constraints": ["No production claim."],
            }
        ],
        "gates": {
            "min_hypotheses": 1,
            "max_hypotheses": 2,
            "require_source_evidence": True,
            "require_allowed_inputs": True,
            "require_forbidden_inputs": True,
            "require_proposed_rule_logic": True,
            "require_validation_gates": True,
            "require_failure_conditions": True,
            "require_readme_wording": True,
            "require_promotion_constraints": True,
            "require_no_forbidden_inputs": False,
            "require_no_strategy_test": True,
            "require_no_parameter_optimisation": True,
            "require_no_strategy_promotion": True,
            "required_spec_role": "Pre-registered design spec only",
        },
    }


def test_phase9c_spec_tables_are_created():
    phase_config = _sample_phase_config()

    hypothesis_spec = build_phase9c_hypothesis_spec(phase_config)
    allowed_inputs = build_phase9c_allowed_inputs(phase_config)
    forbidden_inputs = build_phase9c_forbidden_inputs(phase_config)
    validation_gates = build_phase9c_validation_gates(phase_config)
    forbidden_actions = build_phase9c_forbidden_actions(phase_config)

    assert not hypothesis_spec.empty
    assert not allowed_inputs.empty
    assert not forbidden_inputs.empty
    assert not validation_gates.empty
    assert not forbidden_actions.empty
    assert hypothesis_spec.iloc[0]["hypothesis_id"] == "H1"


def test_phase9c_gate_report_passes_for_valid_spec():
    phase_config = _sample_phase_config()

    hypothesis_spec = build_phase9c_hypothesis_spec(phase_config)
    allowed_inputs = build_phase9c_allowed_inputs(phase_config)
    forbidden_inputs = build_phase9c_forbidden_inputs(phase_config)
    validation_gates = build_phase9c_validation_gates(phase_config)
    forbidden_actions = build_phase9c_forbidden_actions(phase_config)
    summary = build_phase9c_summary(
        phase_config,
        hypothesis_spec,
        allowed_inputs,
        forbidden_inputs,
        validation_gates,
        forbidden_actions,
    )
    gate_report = build_phase9c_gate_report(
        phase_config,
        hypothesis_spec,
        summary,
    )
    conclusion = build_phase9c_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == "Completed — pre-registered spec only"


def test_phase9c_gate_report_fails_when_strategy_test_is_allowed():
    phase_config = _sample_phase_config()
    phase_config["allow_strategy_test"] = True

    hypothesis_spec = build_phase9c_hypothesis_spec(phase_config)
    allowed_inputs = build_phase9c_allowed_inputs(phase_config)
    forbidden_inputs = build_phase9c_forbidden_inputs(phase_config)
    validation_gates = build_phase9c_validation_gates(phase_config)
    forbidden_actions = build_phase9c_forbidden_actions(phase_config)
    summary = build_phase9c_summary(
        phase_config,
        hypothesis_spec,
        allowed_inputs,
        forbidden_inputs,
        validation_gates,
        forbidden_actions,
    )
    gate_report = build_phase9c_gate_report(
        phase_config,
        hypothesis_spec,
        summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase9c_writes_expected_reports(tmp_path):
    config = {
        "phase9c_preregistered_technical_rule_design_spec": {
            "enabled": True,
            **_sample_phase_config(),
        }
    }

    outputs = save_phase9c_preregistered_technical_rule_design_spec(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["hypothesis_spec"].empty
    assert (tmp_path / "phase9c_preregistered_rule_hypothesis_spec.csv").exists()
    assert (tmp_path / "phase9c_preregistered_rule_allowed_inputs.csv").exists()
    assert (tmp_path / "phase9c_preregistered_rule_forbidden_inputs.csv").exists()
    assert (tmp_path / "phase9c_preregistered_rule_validation_gates.csv").exists()
    assert (tmp_path / "phase9c_preregistered_rule_forbidden_actions.csv").exists()
    assert (tmp_path / "phase9c_preregistered_rule_summary.csv").exists()
    assert (tmp_path / "phase9c_preregistered_rule_gate_report.csv").exists()
    assert (tmp_path / "phase9c_preregistered_rule_conclusion.csv").exists()
    assert (
        tmp_path / "phase9c_preregistered_technical_rule_design_spec.md"
    ).exists()

def test_phase9c_forbidden_input_documentation_does_not_fail_keyword_gate():
    phase_config = _sample_phase_config()
    phase_config["gates"]["require_no_forbidden_inputs"] = True

    hypothesis_spec = build_phase9c_hypothesis_spec(phase_config)
    allowed_inputs = build_phase9c_allowed_inputs(phase_config)
    forbidden_inputs = build_phase9c_forbidden_inputs(phase_config)
    validation_gates = build_phase9c_validation_gates(phase_config)
    forbidden_actions = build_phase9c_forbidden_actions(phase_config)
    summary = build_phase9c_summary(
        phase_config,
        hypothesis_spec,
        allowed_inputs,
        forbidden_inputs,
        validation_gates,
        forbidden_actions,
    )
    gate_report = build_phase9c_gate_report(
        phase_config,
        hypothesis_spec,
        summary,
    )

    assert bool(summary.iloc[0]["forbidden_keywords_absent"])
    assert bool(gate_report["passed"].all())