from market_strats.analysis.regime_scoring_rulebook_spec import (
    build_phase11c_audit_output_spec,
    build_phase11c_component_rulebook,
    build_phase11c_conceptual_direction_rulebook,
    build_phase11c_conclusion,
    build_phase11c_future_validation_gates,
    build_phase11c_gate_report,
    build_phase11c_missingness_rules,
    build_phase11c_phase11d_boundary_check,
    build_phase11c_scope_boundary_check,
    build_phase11c_score_state_rulebook,
    build_phase11c_source_architecture,
    build_phase11c_summary,
    build_phase11c_weighting_principles,
    save_phase11c_regime_scoring_rulebook_spec,
)


def _phase_config():
    return {
        "spec_role": "Regime scoring rulebook spec only",
        "phase_branch": "Phase 11 architecture review",
        "source_phase": "Phase 11B",
        "proposed_next_phase": "Phase 11D",
        "source_architecture": {
            "selected_architecture": "A2_regime_scoring_layer",
            "source_spec": "Phase 11B regime scoring architecture spec",
            "rationale": "Prior simple overlays failed.",
        },
        "allow_score_calculation": False,
        "allow_numeric_score_weights": False,
        "allow_empirical_return_weights": False,
        "allow_signal_creation": False,
        "allow_allocation_rule_creation": False,
        "allow_strategy_backtest": False,
        "allow_model_training": False,
        "allow_new_data_ingestion": False,
        "allow_candidate_promotion": False,
        "component_rulebook": [
            {
                "component_id": "technical_regime_context",
                "family": "technical",
                "rulebook_role": "active_conceptual_component",
                "source_evidence": "Technical branch diagnostic only.",
                "allowed_conceptual_inputs": ["trend"],
                "conceptual_directions": [
                    {
                        "direction_id": "technical_supportive",
                        "condition_family": "trend confirmation",
                        "conceptual_score_direction": "supportive",
                        "trading_allowed": False,
                    }
                ],
                "missingness_policy": "Flag unavailable.",
                "current_status": "conceptual_only",
            },
            {
                "component_id": "macro_regime_context",
                "family": "macro_rates_inflation",
                "rulebook_role": "active_conceptual_component",
                "source_evidence": "Macro branch diagnostic only.",
                "allowed_conceptual_inputs": ["rates"],
                "conceptual_directions": [
                    {
                        "direction_id": "macro_fragile",
                        "condition_family": "macro stress",
                        "conceptual_score_direction": "fragile",
                        "trading_allowed": False,
                    }
                ],
                "missingness_policy": "Flag unavailable.",
                "current_status": "conceptual_only",
            },
            {
                "component_id": "validation_risk_context",
                "family": "validation_risk",
                "rulebook_role": "required_control_component",
                "source_evidence": "Validation risks documented.",
                "allowed_conceptual_inputs": ["friction"],
                "conceptual_directions": [
                    {
                        "direction_id": "validation_fragile",
                        "condition_family": "high validation risk",
                        "conceptual_score_direction": "fragile",
                        "trading_allowed": False,
                    }
                ],
                "missingness_policy": "Default to caution.",
                "current_status": "conceptual_only",
            },
            {
                "component_id": "future_fundamental_context",
                "family": "fundamental_valuation",
                "rulebook_role": "blocked_future_component",
                "source_evidence": "Not audited.",
                "allowed_conceptual_inputs": ["valuation"],
                "conceptual_directions": [],
                "missingness_policy": "Blocked.",
                "current_status": "blocked",
            },
            {
                "component_id": "future_sentiment_context",
                "family": "sentiment_narrative",
                "rulebook_role": "blocked_future_component",
                "source_evidence": "Not audited.",
                "allowed_conceptual_inputs": ["sentiment"],
                "conceptual_directions": [],
                "missingness_policy": "Blocked.",
                "current_status": "blocked",
            },
        ],
        "missingness_rules": [
            {"rule_id": "r1", "rule": "No return inference.", "required": True},
            {"rule_id": "r2", "rule": "Flag unavailable.", "required": True},
            {"rule_id": "r3", "rule": "No silent fill.", "required": True},
            {"rule_id": "r4", "rule": "Exclude blocked families.", "required": True},
            {"rule_id": "r5", "rule": "Default to caution.", "required": True},
        ],
        "weighting_principles": [
            {"principle_id": "p1", "principle": "No returns weights.", "required": True},
            {"principle_id": "p2", "principle": "Pre-register policy.", "required": True},
            {"principle_id": "p3", "principle": "Separate components.", "required": True},
            {"principle_id": "p4", "principle": "No cutoff search.", "required": True},
            {"principle_id": "p5", "principle": "Validation can penalise.", "required": True},
        ],
        "score_state_rulebook": [
            {
                "state_id": "supportive",
                "conceptual_definition": "Supportive.",
                "current_role": "conceptual_state_only",
                "score_calculation_allowed": False,
                "trading_allowed": False,
            },
            {
                "state_id": "neutral",
                "conceptual_definition": "Neutral.",
                "current_role": "conceptual_state_only",
                "score_calculation_allowed": False,
                "trading_allowed": False,
            },
            {
                "state_id": "fragile",
                "conceptual_definition": "Fragile.",
                "current_role": "conceptual_state_only",
                "score_calculation_allowed": False,
                "trading_allowed": False,
            },
        ],
        "audit_output_spec": [
            {
                "output_id": "o1",
                "output_description": "Availability report.",
                "required_for_future_phase": True,
            },
            {
                "output_id": "o2",
                "output_description": "Direction report.",
                "required_for_future_phase": True,
            },
            {
                "output_id": "o3",
                "output_description": "Missingness report.",
                "required_for_future_phase": True,
            },
            {
                "output_id": "o4",
                "output_description": "Weighting policy report.",
                "required_for_future_phase": True,
            },
            {
                "output_id": "o5",
                "output_description": "Boundary report.",
                "required_for_future_phase": True,
            },
        ],
        "future_validation_gates": [
            {"gate_id": "g1", "gate": "Rulebook before score.", "required": True},
            {"gate_id": "g2", "gate": "Audit before aggregation.", "required": True},
            {"gate_id": "g3", "gate": "No return weighting.", "required": True},
            {"gate_id": "g4", "gate": "Diagnostic before strategy.", "required": True},
            {"gate_id": "g5", "gate": "Benchmark and liveability gates.", "required": True},
            {"gate_id": "g6", "gate": "Promotion block.", "required": True},
        ],
        "phase11d_boundary": {
            "allowed_next_step": "Regime scoring diagnostic panel design only",
            "forbidden_next_step": (
                "score calculation, signal creation, strategy backtest, "
                "model training, new data ingestion, or candidate promotion"
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


def test_phase11c_builds_rulebook_tables():
    phase_config = _phase_config()

    source = build_phase11c_source_architecture(phase_config)
    components = build_phase11c_component_rulebook(phase_config)
    directions = build_phase11c_conceptual_direction_rulebook(phase_config)
    missingness = build_phase11c_missingness_rules(phase_config)
    weighting = build_phase11c_weighting_principles(phase_config)
    states = build_phase11c_score_state_rulebook(phase_config)
    outputs = build_phase11c_audit_output_spec(phase_config)
    gates = build_phase11c_future_validation_gates(phase_config)
    boundary = build_phase11c_phase11d_boundary_check(phase_config)
    scope = build_phase11c_scope_boundary_check(phase_config)

    assert bool(source.iloc[0]["source_architecture_present"])
    assert len(components) == 5
    assert not directions.empty
    assert len(missingness) >= 5
    assert len(weighting) >= 5
    assert bool(states["trading_allowed"].eq(False).all())
    assert len(outputs) >= 5
    assert len(gates) >= 6
    assert bool(boundary["passed"].all())
    assert bool(scope["passed"].all())


def test_phase11c_gate_report_passes_valid_spec():
    phase_config = _phase_config()

    source = build_phase11c_source_architecture(phase_config)
    components = build_phase11c_component_rulebook(phase_config)
    directions = build_phase11c_conceptual_direction_rulebook(phase_config)
    missingness = build_phase11c_missingness_rules(phase_config)
    weighting = build_phase11c_weighting_principles(phase_config)
    states = build_phase11c_score_state_rulebook(phase_config)
    outputs = build_phase11c_audit_output_spec(phase_config)
    future_gates = build_phase11c_future_validation_gates(phase_config)
    boundary = build_phase11c_phase11d_boundary_check(phase_config)
    scope = build_phase11c_scope_boundary_check(phase_config)

    summary = build_phase11c_summary(
        phase_config=phase_config,
        source_architecture=source,
        component_rulebook=components,
        conceptual_direction_rulebook=directions,
        missingness_rules=missingness,
        weighting_principles=weighting,
        score_state_rulebook=states,
        audit_output_spec=outputs,
        future_validation_gates=future_gates,
        phase11d_boundary_check=boundary,
        scope_boundary_check=scope,
    )
    gate_report = build_phase11c_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11c_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — regime scoring rulebook spec passed"
    )


def test_phase11c_fails_if_score_calculation_allowed():
    phase_config = _phase_config()
    phase_config["allow_score_calculation"] = True

    source = build_phase11c_source_architecture(phase_config)
    components = build_phase11c_component_rulebook(phase_config)
    directions = build_phase11c_conceptual_direction_rulebook(phase_config)
    missingness = build_phase11c_missingness_rules(phase_config)
    weighting = build_phase11c_weighting_principles(phase_config)
    states = build_phase11c_score_state_rulebook(phase_config)
    outputs = build_phase11c_audit_output_spec(phase_config)
    future_gates = build_phase11c_future_validation_gates(phase_config)
    boundary = build_phase11c_phase11d_boundary_check(phase_config)
    scope = build_phase11c_scope_boundary_check(phase_config)

    summary = build_phase11c_summary(
        phase_config=phase_config,
        source_architecture=source,
        component_rulebook=components,
        conceptual_direction_rulebook=directions,
        missingness_rules=missingness,
        weighting_principles=weighting,
        score_state_rulebook=states,
        audit_output_spec=outputs,
        future_validation_gates=future_gates,
        phase11d_boundary_check=boundary,
        scope_boundary_check=scope,
    )
    gate_report = build_phase11c_gate_report(
        phase_config=phase_config,
        summary=summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase11c_writes_expected_reports(tmp_path):
    config = {
        "phase11c_regime_scoring_rulebook_spec": {
            "enabled": True,
            **_phase_config(),
        }
    }

    outputs = save_phase11c_regime_scoring_rulebook_spec(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase11c_regime_scoring_source_architecture.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_component_rulebook.csv").exists()
    assert (
        tmp_path / "phase11c_regime_scoring_conceptual_direction_rulebook.csv"
    ).exists()
    assert (tmp_path / "phase11c_regime_scoring_missingness_rules.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_weighting_principles.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_state_rulebook.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_audit_output_spec.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_future_validation_gates.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_phase11d_boundary_check.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_scope_boundary_check.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_summary.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_gate_report.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_conclusion.csv").exists()
    assert (tmp_path / "phase11c_regime_scoring_rulebook_spec.md").exists()