from market_strats.analysis.regime_scoring_architecture_spec import (
    build_phase11b_component_registry,
    build_phase11b_conclusion,
    build_phase11b_future_validation_requirements,
    build_phase11b_gate_report,
    build_phase11b_phase11c_boundary_check,
    build_phase11b_scope_boundary_check,
    build_phase11b_score_state_design,
    build_phase11b_scoring_principles,
    build_phase11b_source_decision,
    build_phase11b_summary,
    save_phase11b_regime_scoring_architecture_spec,
)


def _phase_config():
    return {
        "spec_role": "Regime scoring architecture spec only",
        "phase_branch": "Phase 11 architecture review",
        "proposed_next_phase": "Phase 11C",
        "source_architecture_decision": {
            "source_phase": "Phase 11A",
            "selected_architecture": "A2_regime_scoring_layer",
            "rejected_immediate_architecture": "A1_continue_simple_rule_overlays",
            "rationale": "Prior simple rule overlays failed.",
        },
        "allow_score_calculation": False,
        "allow_score_weights": False,
        "allow_signal_creation": False,
        "allow_allocation_rule_creation": False,
        "allow_strategy_backtest": False,
        "allow_model_training": False,
        "allow_new_data_ingestion": False,
        "allow_candidate_promotion": False,
        "scoring_principles": [
            {
                "principle_id": "diagnostic_before_trading",
                "principle": "Diagnostic before trading.",
                "required": True,
            },
            {
                "principle_id": "continuous_not_binary_first",
                "principle": "Avoid immediate binary switches.",
                "required": True,
            },
            {
                "principle_id": "evidence_family_separation",
                "principle": "Keep families separately auditable.",
                "required": True,
            },
            {
                "principle_id": "no_post_hoc_weighting",
                "principle": "No post-hoc weighting.",
                "required": True,
            },
            {
                "principle_id": "benchmark_first_validation",
                "principle": "Compare to benchmarks.",
                "required": True,
            },
        ],
        "component_families": [
            {
                "component_id": "technical_regime_context",
                "family": "technical",
                "role": "diagnostic_candidate",
                "source_evidence": "Technical branch was diagnostic but failed rules.",
                "allowed_conceptual_inputs": ["trend", "momentum"],
                "forbidden_current_use": ["No technical score calculation."],
                "allowed_for_phase11c_spec": True,
            },
            {
                "component_id": "macro_regime_context",
                "family": "macro_rates_inflation",
                "role": "diagnostic_candidate",
                "source_evidence": "Macro branch was diagnostic but failed rules.",
                "allowed_conceptual_inputs": ["rates", "inflation"],
                "forbidden_current_use": ["No macro score calculation."],
                "allowed_for_phase11c_spec": True,
            },
            {
                "component_id": "validation_risk_context",
                "family": "validation_risk",
                "role": "required_control_layer",
                "source_evidence": "Validation risks are documented.",
                "allowed_conceptual_inputs": ["friction", "regret"],
                "forbidden_current_use": ["No penalty score calculation."],
                "allowed_for_phase11c_spec": True,
            },
            {
                "component_id": "future_fundamental_context",
                "family": "fundamental_valuation",
                "role": "future_candidate_not_active",
                "source_evidence": "Fundamentals not audited.",
                "allowed_conceptual_inputs": ["valuation"],
                "forbidden_current_use": ["No fundamental ingestion."],
                "allowed_for_phase11c_spec": False,
            },
            {
                "component_id": "future_sentiment_context",
                "family": "sentiment_narrative",
                "role": "future_candidate_not_active",
                "source_evidence": "Sentiment not audited.",
                "allowed_conceptual_inputs": ["sentiment"],
                "forbidden_current_use": ["No sentiment ingestion."],
                "allowed_for_phase11c_spec": False,
            },
        ],
        "score_state_design": [
            {
                "state_id": "supportive",
                "description": "Supportive context.",
                "allowed_current_role": "conceptual_state_only",
                "trading_allowed": False,
            },
            {
                "state_id": "neutral",
                "description": "Neutral context.",
                "allowed_current_role": "conceptual_state_only",
                "trading_allowed": False,
            },
            {
                "state_id": "fragile",
                "description": "Fragile context.",
                "allowed_current_role": "conceptual_state_only",
                "trading_allowed": False,
            },
        ],
        "future_validation_requirements": [
            {
                "requirement_id": "diagnostic_panel_first",
                "requirement": "Define rulebook before scoring.",
            },
            {
                "requirement_id": "no_returns_based_weight_selection",
                "requirement": "No returns-based weight selection.",
            },
            {
                "requirement_id": "separate_component_audit",
                "requirement": "Components must be auditable.",
            },
            {
                "requirement_id": "benchmark_comparison",
                "requirement": "Compare to benchmarks.",
            },
            {
                "requirement_id": "friction_liveability_validation",
                "requirement": "Survive friction and liveability gates.",
            },
        ],
        "phase11c_boundary": {
            "allowed_next_step": "Regime scoring rulebook spec only",
            "forbidden_next_step": (
                "score calculation, model training, strategy backtest, "
                "or candidate promotion"
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


def test_phase11b_builds_architecture_spec_tables():
    phase_config = _phase_config()

    source_decision = build_phase11b_source_decision(phase_config)
    principles = build_phase11b_scoring_principles(phase_config)
    components = build_phase11b_component_registry(phase_config)
    states = build_phase11b_score_state_design(phase_config)
    requirements = build_phase11b_future_validation_requirements(phase_config)
    boundary = build_phase11b_phase11c_boundary_check(phase_config)
    scope = build_phase11b_scope_boundary_check(phase_config)

    assert bool(source_decision.iloc[0]["source_decision_present"])
    assert len(principles) >= 5
    assert len(components) >= 4
    assert bool(states["trading_allowed"].eq(False).all())
    assert len(requirements) >= 5
    assert bool(boundary["passed"].all())
    assert bool(scope["passed"].all())


def test_phase11b_gate_report_passes_valid_spec():
    phase_config = _phase_config()

    source_decision = build_phase11b_source_decision(phase_config)
    principles = build_phase11b_scoring_principles(phase_config)
    components = build_phase11b_component_registry(phase_config)
    states = build_phase11b_score_state_design(phase_config)
    requirements = build_phase11b_future_validation_requirements(phase_config)
    boundary = build_phase11b_phase11c_boundary_check(phase_config)
    scope = build_phase11b_scope_boundary_check(phase_config)

    summary = build_phase11b_summary(
        phase_config=phase_config,
        source_decision=source_decision,
        scoring_principles=principles,
        component_registry=components,
        score_state_design=states,
        validation_requirements=requirements,
        phase11c_boundary_check=boundary,
        scope_boundary_check=scope,
    )
    gate_report = build_phase11b_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11b_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — regime scoring architecture spec passed"
    )


def test_phase11b_fails_if_score_calculation_allowed():
    phase_config = _phase_config()
    phase_config["allow_score_calculation"] = True

    source_decision = build_phase11b_source_decision(phase_config)
    principles = build_phase11b_scoring_principles(phase_config)
    components = build_phase11b_component_registry(phase_config)
    states = build_phase11b_score_state_design(phase_config)
    requirements = build_phase11b_future_validation_requirements(phase_config)
    boundary = build_phase11b_phase11c_boundary_check(phase_config)
    scope = build_phase11b_scope_boundary_check(phase_config)

    summary = build_phase11b_summary(
        phase_config=phase_config,
        source_decision=source_decision,
        scoring_principles=principles,
        component_registry=components,
        score_state_design=states,
        validation_requirements=requirements,
        phase11c_boundary_check=boundary,
        scope_boundary_check=scope,
    )
    gate_report = build_phase11b_gate_report(
        phase_config=phase_config,
        summary=summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase11b_writes_expected_reports(tmp_path):
    config = {
        "phase11b_regime_scoring_architecture_spec": {
            "enabled": True,
            **_phase_config(),
        }
    }

    outputs = save_phase11b_regime_scoring_architecture_spec(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase11b_regime_scoring_source_decision.csv").exists()
    assert (tmp_path / "phase11b_regime_scoring_principles.csv").exists()
    assert (tmp_path / "phase11b_regime_scoring_component_registry.csv").exists()
    assert (tmp_path / "phase11b_regime_scoring_state_design.csv").exists()
    assert (
        tmp_path / "phase11b_regime_scoring_validation_requirements.csv"
    ).exists()
    assert (
        tmp_path / "phase11b_regime_scoring_phase11c_boundary_check.csv"
    ).exists()
    assert (tmp_path / "phase11b_regime_scoring_scope_boundary_check.csv").exists()
    assert (tmp_path / "phase11b_regime_scoring_summary.csv").exists()
    assert (tmp_path / "phase11b_regime_scoring_gate_report.csv").exists()
    assert (tmp_path / "phase11b_regime_scoring_conclusion.csv").exists()
    assert (tmp_path / "phase11b_regime_scoring_architecture_spec.md").exists()