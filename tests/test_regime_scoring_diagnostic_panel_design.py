from market_strats.analysis.regime_scoring_diagnostic_panel_design import (
    build_phase11d_blocked_family_spec,
    build_phase11d_component_availability_spec,
    build_phase11d_conceptual_direction_spec,
    build_phase11d_conclusion,
    build_phase11d_gate_report,
    build_phase11d_missingness_policy_spec,
    build_phase11d_panel_layout_spec,
    build_phase11d_phase11e_boundary_check,
    build_phase11d_required_columns_spec,
    build_phase11d_scope_boundary_check,
    build_phase11d_source_rulebook,
    build_phase11d_summary,
    build_phase11d_weighting_policy_spec,
    save_phase11d_regime_scoring_diagnostic_panel_design,
)


def _phase_config():
    return {
        "design_role": "Regime scoring diagnostic panel design only",
        "phase_branch": "Phase 11 architecture review",
        "source_phase": "Phase 11C",
        "proposed_next_phase": "Phase 11E",
        "source_rulebook": {
            "source_spec": "Phase 11C regime scoring rulebook spec",
            "rulebook_status": "Completed — regime scoring rulebook spec passed",
            "rationale": "Rulebook exists before panel design.",
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
        "diagnostic_panel_sections": [
            {
                "panel_id": "component_availability_panel",
                "report_name": "component_availability_report",
                "purpose": "Availability.",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_columns": ["component_id", "family", "status"],
            },
            {
                "panel_id": "conceptual_direction_panel",
                "report_name": "component_direction_report",
                "purpose": "Directions.",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_columns": ["component_id", "direction", "trading_allowed"],
            },
            {
                "panel_id": "missingness_panel",
                "report_name": "missingness_report",
                "purpose": "Missingness.",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_columns": ["component_id", "missingness_reason"],
            },
            {
                "panel_id": "weighting_policy_panel",
                "report_name": "weighting_policy_report",
                "purpose": "Weighting policy.",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_columns": ["policy_id", "numeric_weight_allowed"],
            },
            {
                "panel_id": "blocked_family_panel",
                "report_name": "blocked_family_report",
                "purpose": "Blocked families.",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_columns": ["family", "blocked_status"],
            },
            {
                "panel_id": "boundary_panel",
                "report_name": "boundary_report",
                "purpose": "Boundaries.",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_columns": ["boundary_item", "passed"],
            },
        ],
        "component_availability_spec": [
            {
                "component_id": "technical_regime_context",
                "family": "technical",
                "expected_status": "conceptual_only",
                "source_dependency": "Phase 9/11C",
                "future_unblock_requirement": "Existing diagnostics only.",
            },
            {
                "component_id": "macro_regime_context",
                "family": "macro_rates_inflation",
                "expected_status": "conceptual_only",
                "source_dependency": "Phase 10/11C",
                "future_unblock_requirement": "Existing diagnostics only.",
            },
            {
                "component_id": "validation_risk_context",
                "family": "validation_risk",
                "expected_status": "conceptual_only",
                "source_dependency": "Phase 8/9/10/11C",
                "future_unblock_requirement": "Existing validation only.",
            },
            {
                "component_id": "future_fundamental_context",
                "family": "fundamental_valuation",
                "expected_status": "blocked",
                "source_dependency": "No audit.",
                "future_unblock_requirement": "Future feasibility audit.",
            },
            {
                "component_id": "future_sentiment_context",
                "family": "sentiment_narrative",
                "expected_status": "blocked",
                "source_dependency": "No audit.",
                "future_unblock_requirement": "Future feasibility audit.",
            },
        ],
        "conceptual_direction_spec": [
            {
                "component_id": "technical_regime_context",
                "family": "technical",
                "allowed_directions": ["supportive", "neutral", "fragile"],
                "trading_allowed": False,
                "signal_allowed": False,
            },
            {
                "component_id": "macro_regime_context",
                "family": "macro_rates_inflation",
                "allowed_directions": ["supportive", "neutral", "fragile"],
                "trading_allowed": False,
                "signal_allowed": False,
            },
            {
                "component_id": "validation_risk_context",
                "family": "validation_risk",
                "allowed_directions": ["supportive", "neutral", "fragile"],
                "trading_allowed": False,
                "signal_allowed": False,
            },
        ],
        "missingness_policy_spec": [
            {"policy_id": "m1", "policy": "No return inference.", "required": True},
            {"policy_id": "m2", "policy": "Flag unavailable.", "required": True},
            {"policy_id": "m3", "policy": "No silent fill.", "required": True},
            {"policy_id": "m4", "policy": "Exclude blocked.", "required": True},
            {"policy_id": "m5", "policy": "Default caution.", "required": True},
        ],
        "weighting_policy_spec": [
            {
                "policy_id": "w1",
                "policy": "No numeric weights.",
                "numeric_weight_allowed": False,
                "empirical_return_weight_allowed": False,
                "required": True,
            },
            {
                "policy_id": "w2",
                "policy": "No return weights.",
                "numeric_weight_allowed": False,
                "empirical_return_weight_allowed": False,
                "required": True,
            },
            {
                "policy_id": "w3",
                "policy": "Pre-register.",
                "numeric_weight_allowed": False,
                "empirical_return_weight_allowed": False,
                "required": True,
            },
            {
                "policy_id": "w4",
                "policy": "Separate components.",
                "numeric_weight_allowed": False,
                "empirical_return_weight_allowed": False,
                "required": True,
            },
            {
                "policy_id": "w5",
                "policy": "No cutoff search.",
                "numeric_weight_allowed": False,
                "empirical_return_weight_allowed": False,
                "required": True,
            },
        ],
        "blocked_family_spec": [
            {
                "family": "fundamental_valuation",
                "blocked_status": "blocked",
                "blocked_reason": "No audit.",
                "unblock_requires": "Future audit.",
                "current_use_allowed": False,
                "score_component_allowed": False,
            },
            {
                "family": "sentiment_narrative",
                "blocked_status": "blocked",
                "blocked_reason": "No audit.",
                "unblock_requires": "Future audit.",
                "current_use_allowed": False,
                "score_component_allowed": False,
            },
        ],
        "phase11e_boundary": {
            "allowed_next_step": (
                "Regime scoring diagnostic panel implementation audit only"
            ),
            "forbidden_next_step": (
                "score calculation, signal creation, strategy backtest, "
                "model training, new data ingestion, or candidate promotion"
            ),
            "phase11e_may_build_empty_panel_templates": True,
            "phase11e_may_calculate_scores": False,
            "phase11e_may_assign_weights": False,
            "phase11e_may_create_signal": False,
            "phase11e_may_test_strategy": False,
            "phase11e_may_train_model": False,
            "phase11e_may_ingest_new_data": False,
            "phase11e_may_promote_candidate": False,
        },
        "gates": {
            "require_source_rulebook": True,
            "require_panel_sections": True,
            "min_panel_sections": 6,
            "require_required_columns": True,
            "require_component_availability_spec": True,
            "require_conceptual_direction_spec": True,
            "require_missingness_policy_spec": True,
            "min_missingness_policies": 5,
            "require_weighting_policy_spec": True,
            "min_weighting_policies": 5,
            "require_blocked_family_spec": True,
            "min_blocked_families": 2,
            "require_all_panels_non_signal": True,
            "require_all_panels_no_returns": True,
            "require_phase11e_boundary_design_only": True,
            "require_no_score_calculation": True,
            "require_no_numeric_score_weights": True,
            "require_no_empirical_return_weights": True,
            "require_no_signal_creation": True,
            "require_no_allocation_rule_creation": True,
            "require_no_strategy_backtest": True,
            "require_no_model_training": True,
            "require_no_new_data_ingestion": True,
            "require_no_candidate_promotion": True,
            "required_design_role": "Regime scoring diagnostic panel design only",
        },
    }


def test_phase11d_builds_panel_design_tables():
    phase_config = _phase_config()

    source = build_phase11d_source_rulebook(phase_config)
    panels = build_phase11d_panel_layout_spec(phase_config)
    columns = build_phase11d_required_columns_spec(phase_config)
    availability = build_phase11d_component_availability_spec(phase_config)
    directions = build_phase11d_conceptual_direction_spec(phase_config)
    missingness = build_phase11d_missingness_policy_spec(phase_config)
    weighting = build_phase11d_weighting_policy_spec(phase_config)
    blocked = build_phase11d_blocked_family_spec(phase_config)
    boundary = build_phase11d_phase11e_boundary_check(phase_config)
    scope = build_phase11d_scope_boundary_check(phase_config)

    assert bool(source.iloc[0]["source_rulebook_present"])
    assert len(panels) == 6
    assert not columns.empty
    assert len(availability) == 5
    assert bool(directions["trading_allowed"].eq(False).all())
    assert len(missingness) >= 5
    assert bool(weighting["empirical_return_weight_allowed"].eq(False).all())
    assert len(blocked) == 2
    assert bool(boundary["passed"].all())
    assert bool(scope["passed"].all())


def test_phase11d_gate_report_passes_valid_design():
    phase_config = _phase_config()

    source = build_phase11d_source_rulebook(phase_config)
    panels = build_phase11d_panel_layout_spec(phase_config)
    columns = build_phase11d_required_columns_spec(phase_config)
    availability = build_phase11d_component_availability_spec(phase_config)
    directions = build_phase11d_conceptual_direction_spec(phase_config)
    missingness = build_phase11d_missingness_policy_spec(phase_config)
    weighting = build_phase11d_weighting_policy_spec(phase_config)
    blocked = build_phase11d_blocked_family_spec(phase_config)
    boundary = build_phase11d_phase11e_boundary_check(phase_config)
    scope = build_phase11d_scope_boundary_check(phase_config)

    summary = build_phase11d_summary(
        phase_config=phase_config,
        source_rulebook=source,
        panel_layout_spec=panels,
        required_columns_spec=columns,
        component_availability_spec=availability,
        conceptual_direction_spec=directions,
        missingness_policy_spec=missingness,
        weighting_policy_spec=weighting,
        blocked_family_spec=blocked,
        phase11e_boundary_check=boundary,
        scope_boundary_check=scope,
    )
    gate_report = build_phase11d_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11d_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — diagnostic panel design passed"
    )


def test_phase11d_fails_if_signal_creation_allowed():
    phase_config = _phase_config()
    phase_config["allow_signal_creation"] = True

    source = build_phase11d_source_rulebook(phase_config)
    panels = build_phase11d_panel_layout_spec(phase_config)
    columns = build_phase11d_required_columns_spec(phase_config)
    availability = build_phase11d_component_availability_spec(phase_config)
    directions = build_phase11d_conceptual_direction_spec(phase_config)
    missingness = build_phase11d_missingness_policy_spec(phase_config)
    weighting = build_phase11d_weighting_policy_spec(phase_config)
    blocked = build_phase11d_blocked_family_spec(phase_config)
    boundary = build_phase11d_phase11e_boundary_check(phase_config)
    scope = build_phase11d_scope_boundary_check(phase_config)

    summary = build_phase11d_summary(
        phase_config=phase_config,
        source_rulebook=source,
        panel_layout_spec=panels,
        required_columns_spec=columns,
        component_availability_spec=availability,
        conceptual_direction_spec=directions,
        missingness_policy_spec=missingness,
        weighting_policy_spec=weighting,
        blocked_family_spec=blocked,
        phase11e_boundary_check=boundary,
        scope_boundary_check=scope,
    )
    gate_report = build_phase11d_gate_report(
        phase_config=phase_config,
        summary=summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase11d_writes_expected_reports(tmp_path):
    config = {
        "phase11d_regime_scoring_diagnostic_panel_design": {
            "enabled": True,
            **_phase_config(),
        }
    }

    outputs = save_phase11d_regime_scoring_diagnostic_panel_design(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase11d_diagnostic_panel_source_rulebook.csv").exists()
    assert (tmp_path / "phase11d_diagnostic_panel_layout_spec.csv").exists()
    assert (
        tmp_path / "phase11d_diagnostic_panel_required_columns_spec.csv"
    ).exists()
    assert (
        tmp_path / "phase11d_diagnostic_panel_component_availability_spec.csv"
    ).exists()
    assert (
        tmp_path / "phase11d_diagnostic_panel_conceptual_direction_spec.csv"
    ).exists()
    assert (
        tmp_path / "phase11d_diagnostic_panel_missingness_policy_spec.csv"
    ).exists()
    assert (
        tmp_path / "phase11d_diagnostic_panel_weighting_policy_spec.csv"
    ).exists()
    assert (tmp_path / "phase11d_diagnostic_panel_blocked_family_spec.csv").exists()
    assert (
        tmp_path / "phase11d_diagnostic_panel_phase11e_boundary_check.csv"
    ).exists()
    assert (tmp_path / "phase11d_diagnostic_panel_scope_boundary_check.csv").exists()
    assert (tmp_path / "phase11d_diagnostic_panel_summary.csv").exists()
    assert (tmp_path / "phase11d_diagnostic_panel_gate_report.csv").exists()
    assert (tmp_path / "phase11d_diagnostic_panel_conclusion.csv").exists()
    assert (
        tmp_path / "phase11d_regime_scoring_diagnostic_panel_design.md"
    ).exists()