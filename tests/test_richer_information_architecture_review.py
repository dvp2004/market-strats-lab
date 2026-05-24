from market_strats.analysis.richer_information_architecture_review import (
    build_phase11a_architecture_candidates,
    build_phase11a_architecture_risk_matrix,
    build_phase11a_boundary_check,
    build_phase11a_conclusion,
    build_phase11a_gate_report,
    build_phase11a_prior_branch_findings,
    build_phase11a_recommendation,
    build_phase11a_summary,
    save_phase11a_richer_information_architecture_review,
)


def _phase_config():
    return {
        "review_role": "Architecture review for richer information layers only",
        "phase_branch": "Phase 11 architecture review",
        "proposed_next_phase": "Phase 11B",
        "allow_new_indicator_rule": False,
        "allow_macro_rule_retry": False,
        "allow_sentiment_ingestion": False,
        "allow_fundamental_ingestion": False,
        "allow_model_training": False,
        "allow_strategy_backtest": False,
        "allow_candidate_promotion": False,
        "prior_branch_findings": {
            "technical_extension": {
                "branch": "Phase 9 technical indicator extension",
                "diagnostic_evidence": "Technical clusters were useful but unstable.",
                "preregistration": "Phase 9C pre-registered two hypotheses.",
                "rule_test_result": "Phase 9D failed; no technical rule passed.",
                "closeout": "Phase 9E/9F closed without promotion.",
                "implication": "Technical diagnostics did not validate overlays.",
            },
            "macro_extension": {
                "branch": "Phase 10 macro/rates/inflation extension",
                "diagnostic_evidence": "Macro evidence was feasible and informative.",
                "preregistration": "Phase 10E pre-registered two hypotheses.",
                "rule_test_result": "Phase 10F failed; no macro rule passed.",
                "closeout": "Phase 10G/10H closed without promotion.",
                "implication": "Macro diagnostics did not validate overlays.",
            },
        },
        "architecture_candidates": [
            {
                "architecture_id": "A1_continue_simple_rule_overlays",
                "name": "Continue simple if/then overlays",
                "description": "Keep adding binary overlays.",
                "allowed_as_next_branch": False,
                "reason": "Both prior rule-extension branches failed.",
                "complexity": "low",
                "overfit_risk": "high",
                "interpretability": "high",
                "validation_burden": "medium",
                "recommended_role": "reject_as_immediate_next_step",
            },
            {
                "architecture_id": "A2_regime_scoring_layer",
                "name": "Regime scoring layer",
                "description": "Diagnostic score before trading.",
                "allowed_as_next_branch": True,
                "reason": "Avoids blunt binary switches.",
                "complexity": "medium",
                "overfit_risk": "medium",
                "interpretability": "high",
                "validation_burden": "medium",
                "recommended_role": "preferred_next_architecture_spec_candidate",
            },
            {
                "architecture_id": "A3_probabilistic_allocation_confidence",
                "name": "Probabilistic allocation confidence",
                "description": "Confidence diagnostics.",
                "allowed_as_next_branch": True,
                "reason": "Matches uncertainty.",
                "complexity": "medium_high",
                "overfit_risk": "medium_high",
                "interpretability": "medium",
                "validation_burden": "high",
                "recommended_role": "secondary_architecture_candidate",
            },
            {
                "architecture_id": "A4_explainable_ensemble_decision_layer",
                "name": "Explainable ensemble",
                "description": "Long-term ensemble.",
                "allowed_as_next_branch": False,
                "reason": "Too broad now.",
                "complexity": "high",
                "overfit_risk": "high",
                "interpretability": "medium",
                "validation_burden": "high",
                "recommended_role": "long_term_candidate_not_next",
            },
            {
                "architecture_id": "A5_separate_successor_architecture",
                "name": "Separate successor architecture",
                "description": "Separate model architecture.",
                "allowed_as_next_branch": True,
                "reason": "Could avoid overlay bottleneck.",
                "complexity": "high",
                "overfit_risk": "medium_high",
                "interpretability": "medium",
                "validation_burden": "high",
                "recommended_role": "architecture_review_candidate",
            },
            {
                "architecture_id": "A6_freeze_spy_overlay_arc",
                "name": "Freeze SPY overlay arc",
                "description": "Pause current arc.",
                "allowed_as_next_branch": True,
                "reason": "Valid closure option.",
                "complexity": "low",
                "overfit_risk": "low",
                "interpretability": "high",
                "validation_burden": "low",
                "recommended_role": "valid_pause_option",
            },
        ],
        "recommended_next_step": {
            "recommendation_id": "phase11b_regime_scoring_architecture_spec",
            "phase": "Phase 11B",
            "title": "Regime Scoring Architecture Spec",
            "recommendation": "Design a diagnostic regime scoring layer before any strategy test.",
            "allowed_scope": [
                "Define score components.",
                "Define validation gates.",
            ],
            "forbidden_scope": [
                "No strategy test.",
                "No model training.",
                "No candidate promotion.",
            ],
        },
        "gates": {
            "require_prior_failures_documented": True,
            "require_architecture_candidates": True,
            "min_architecture_candidates": 5,
            "require_simple_overlay_rejected_as_immediate_next": True,
            "require_preferred_architecture_identified": True,
            "require_next_step_spec_only": True,
            "require_no_new_indicator_rule": True,
            "require_no_macro_rule_retry": True,
            "require_no_sentiment_ingestion": True,
            "require_no_fundamental_ingestion": True,
            "require_no_model_training": True,
            "require_no_strategy_backtest": True,
            "require_no_candidate_promotion": True,
            "required_review_role": "Architecture review for richer information layers only",
        },
    }


def test_phase11a_builds_architecture_review_tables():
    phase_config = _phase_config()

    prior = build_phase11a_prior_branch_findings(phase_config)
    candidates = build_phase11a_architecture_candidates(phase_config)
    risk = build_phase11a_architecture_risk_matrix(candidates)
    recommendation = build_phase11a_recommendation(phase_config)
    boundary = build_phase11a_boundary_check(phase_config)

    assert len(prior) == 2
    assert len(candidates) >= 5
    assert not risk.empty
    assert recommendation.iloc[0]["phase"] == "Phase 11B"
    assert bool(boundary["passed"].all())


def test_phase11a_gate_report_passes_valid_review():
    phase_config = _phase_config()

    prior = build_phase11a_prior_branch_findings(phase_config)
    candidates = build_phase11a_architecture_candidates(phase_config)
    recommendation = build_phase11a_recommendation(phase_config)
    boundary = build_phase11a_boundary_check(phase_config)
    summary = build_phase11a_summary(
        phase_config=phase_config,
        prior_branch_findings=prior,
        architecture_candidates=candidates,
        recommendation=recommendation,
        boundary_check=boundary,
    )
    gate_report = build_phase11a_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11a_conclusion(gate_report, summary)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == "Completed — architecture review passed"


def test_phase11a_fails_if_macro_retry_allowed():
    phase_config = _phase_config()
    phase_config["allow_macro_rule_retry"] = True

    prior = build_phase11a_prior_branch_findings(phase_config)
    candidates = build_phase11a_architecture_candidates(phase_config)
    recommendation = build_phase11a_recommendation(phase_config)
    boundary = build_phase11a_boundary_check(phase_config)
    summary = build_phase11a_summary(
        phase_config=phase_config,
        prior_branch_findings=prior,
        architecture_candidates=candidates,
        recommendation=recommendation,
        boundary_check=boundary,
    )
    gate_report = build_phase11a_gate_report(
        phase_config=phase_config,
        summary=summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase11a_writes_expected_reports(tmp_path):
    config = {
        "phase11a_richer_information_architecture_review": {
            "enabled": True,
            **_phase_config(),
        }
    }

    outputs = save_phase11a_richer_information_architecture_review(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase11a_architecture_prior_branch_findings.csv").exists()
    assert (tmp_path / "phase11a_architecture_candidates.csv").exists()
    assert (tmp_path / "phase11a_architecture_risk_matrix.csv").exists()
    assert (tmp_path / "phase11a_architecture_recommendation.csv").exists()
    assert (tmp_path / "phase11a_architecture_boundary_check.csv").exists()
    assert (tmp_path / "phase11a_architecture_summary.csv").exists()
    assert (tmp_path / "phase11a_architecture_gate_report.csv").exists()
    assert (tmp_path / "phase11a_architecture_conclusion.csv").exists()
    assert (tmp_path / "phase11a_richer_information_architecture_review.md").exists()