from market_strats.analysis.feature_family_feasibility_spec import (
    build_phase10a_conclusion,
    build_phase10a_data_requirements,
    build_phase10a_family_spec,
    build_phase10a_gate_report,
    build_phase10a_leakage_controls,
    build_phase10a_recommendation,
    build_phase10a_scorecard,
    build_phase10a_summary,
    build_phase10a_validation_requirements,
    save_phase10a_feature_family_feasibility_spec,
)


def _sample_phase_config():
    return {
        "spec_role": "Feature-family feasibility spec only",
        "proposed_next_phase": "Phase 10B",
        "allow_data_ingestion": False,
        "allow_model_training": False,
        "allow_strategy_test": False,
        "allow_strategy_promotion": False,
        "expected_first_family": "macro_rates_inflation",
        "scoring_weights": {
            "conceptual_relevance": 1.0,
            "data_availability": 1.0,
            "leakage_control": 1.0,
            "update_frequency_fit": 1.0,
            "validation_clarity": 1.0,
            "overfit_resistance": 1.0,
            "implementation_readiness": 1.0,
        },
        "feature_families": [
            {
                "family_id": "macro_rates_inflation",
                "name": "Macro / rates / inflation",
                "role": "Feasibility candidate only",
                "candidate_priority": 1,
                "rationale": ["Clear economic regime relevance."],
                "allowed_feature_examples": ["yield_curve_proxy"],
                "data_requirements": [
                    {
                        "data_type": "macro_timeseries",
                        "frequency": "monthly_or_daily",
                        "timing_requirement": "release-date-aware alignment",
                        "revision_policy": "document vintage/revision handling",
                        "minimum_history_requirement": "canonical overlap preferred",
                    }
                ],
                "leakage_controls": ["No future macro values."],
                "validation_requirements": ["Run data-source audit first."],
                "scorecard": {
                    "conceptual_relevance": 5,
                    "data_availability": 4,
                    "leakage_control": 4,
                    "update_frequency_fit": 4,
                    "validation_clarity": 4,
                    "overfit_resistance": 4,
                    "implementation_readiness": 4,
                },
                "disqualifiers": [{"name": "No release-date handling", "active": False}],
            },
            {
                "family_id": "fundamental_valuation",
                "name": "Fundamental / valuation",
                "role": "Future feasibility candidate only",
                "candidate_priority": 2,
                "rationale": ["Useful long-horizon context."],
                "allowed_feature_examples": ["valuation_proxy"],
                "data_requirements": [
                    {
                        "data_type": "valuation_timeseries",
                        "frequency": "monthly",
                        "timing_requirement": "publication-lag aware",
                        "revision_policy": "document restatements",
                        "minimum_history_requirement": "enough cycles",
                    }
                ],
                "leakage_controls": ["No revised data leakage."],
                "validation_requirements": ["Audit data timing first."],
                "scorecard": {
                    "conceptual_relevance": 4,
                    "data_availability": 3,
                    "leakage_control": 3,
                    "update_frequency_fit": 3,
                    "validation_clarity": 3,
                    "overfit_resistance": 3,
                    "implementation_readiness": 3,
                },
                "disqualifiers": [],
            },
            {
                "family_id": "sentiment_narrative",
                "name": "Sentiment / narrative",
                "role": "Future feasibility candidate only",
                "candidate_priority": 3,
                "rationale": ["Risk appetite context but noisy."],
                "allowed_feature_examples": ["news_sentiment_proxy"],
                "data_requirements": [
                    {
                        "data_type": "timestamped_text",
                        "frequency": "daily",
                        "timing_requirement": "timestamped availability",
                        "revision_policy": "document source changes",
                        "minimum_history_requirement": "enough stress regimes",
                    }
                ],
                "leakage_controls": ["No post-decision text."],
                "validation_requirements": ["Timestamp audit first."],
                "scorecard": {
                    "conceptual_relevance": 3,
                    "data_availability": 2,
                    "leakage_control": 1,
                    "update_frequency_fit": 3,
                    "validation_clarity": 2,
                    "overfit_resistance": 1,
                    "implementation_readiness": 1,
                },
                "disqualifiers": [],
            },
            {
                "family_id": "ml_ensemble",
                "name": "ML / ensemble",
                "role": "Future research branch only",
                "candidate_priority": 4,
                "rationale": ["Premature without clean features."],
                "allowed_feature_examples": ["walk_forward_classifier"],
                "data_requirements": [
                    {
                        "data_type": "validated_feature_matrix",
                        "frequency": "source_dependent",
                        "timing_requirement": "point-in-time features",
                        "revision_policy": "inherits strictest input policy",
                        "minimum_history_requirement": "walk-forward support",
                    }
                ],
                "leakage_controls": ["No random time-series split."],
                "validation_requirements": ["Walk-forward validation required."],
                "scorecard": {
                    "conceptual_relevance": 4,
                    "data_availability": 1,
                    "leakage_control": 1,
                    "update_frequency_fit": 2,
                    "validation_clarity": 2,
                    "overfit_resistance": 1,
                    "implementation_readiness": 1,
                },
                "disqualifiers": [{"name": "No validated input features", "active": True}],
            },
        ],
        "gates": {
            "min_feature_families": 4,
            "max_feature_families": 4,
            "require_expected_first_family": True,
            "require_no_active_disqualifier_for_recommended_family": True,
            "require_data_requirements": True,
            "require_leakage_controls": True,
            "require_validation_requirements": True,
            "require_scorecard": True,
            "require_no_data_ingestion": True,
            "require_no_model_training": True,
            "require_no_strategy_test": True,
            "require_no_strategy_promotion": True,
            "required_spec_role": "Feature-family feasibility spec only",
        },
    }


def test_phase10a_builds_family_tables_and_recommendation():
    phase_config = _sample_phase_config()

    family_spec = build_phase10a_family_spec(phase_config)
    data_requirements = build_phase10a_data_requirements(phase_config)
    leakage_controls = build_phase10a_leakage_controls(phase_config)
    validation_requirements = build_phase10a_validation_requirements(phase_config)
    scorecard = build_phase10a_scorecard(phase_config)
    recommendation = build_phase10a_recommendation(
        family_spec,
        scorecard,
        phase_config,
    )

    assert len(family_spec) == 4
    assert not data_requirements.empty
    assert not leakage_controls.empty
    assert not validation_requirements.empty
    assert not scorecard.empty
    assert recommendation.iloc[0]["recommended_family_id"] == "macro_rates_inflation"


def test_phase10a_gate_report_passes_valid_spec():
    phase_config = _sample_phase_config()

    family_spec = build_phase10a_family_spec(phase_config)
    data_requirements = build_phase10a_data_requirements(phase_config)
    leakage_controls = build_phase10a_leakage_controls(phase_config)
    validation_requirements = build_phase10a_validation_requirements(phase_config)
    scorecard = build_phase10a_scorecard(phase_config)
    recommendation = build_phase10a_recommendation(
        family_spec,
        scorecard,
        phase_config,
    )
    summary = build_phase10a_summary(
        phase_config,
        family_spec,
        data_requirements,
        leakage_controls,
        validation_requirements,
        scorecard,
        recommendation,
    )
    gate_report = build_phase10a_gate_report(phase_config, family_spec, summary)
    conclusion = build_phase10a_conclusion(gate_report, recommendation)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — feature-family feasibility spec only"
    )


def test_phase10a_gate_report_fails_if_model_training_allowed():
    phase_config = _sample_phase_config()
    phase_config["allow_model_training"] = True

    family_spec = build_phase10a_family_spec(phase_config)
    data_requirements = build_phase10a_data_requirements(phase_config)
    leakage_controls = build_phase10a_leakage_controls(phase_config)
    validation_requirements = build_phase10a_validation_requirements(phase_config)
    scorecard = build_phase10a_scorecard(phase_config)
    recommendation = build_phase10a_recommendation(
        family_spec,
        scorecard,
        phase_config,
    )
    summary = build_phase10a_summary(
        phase_config,
        family_spec,
        data_requirements,
        leakage_controls,
        validation_requirements,
        scorecard,
        recommendation,
    )
    gate_report = build_phase10a_gate_report(phase_config, family_spec, summary)

    assert not bool(gate_report["passed"].all())


def test_save_phase10a_writes_expected_reports(tmp_path):
    config = {
        "phase10a_feature_family_feasibility_spec": {
            "enabled": True,
            **_sample_phase_config(),
        }
    }

    outputs = save_phase10a_feature_family_feasibility_spec(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase10a_feature_family_spec.csv").exists()
    assert (tmp_path / "phase10a_feature_family_data_requirements.csv").exists()
    assert (tmp_path / "phase10a_feature_family_leakage_controls.csv").exists()
    assert (tmp_path / "phase10a_feature_family_validation_requirements.csv").exists()
    assert (tmp_path / "phase10a_feature_family_scorecard.csv").exists()
    assert (tmp_path / "phase10a_feature_family_recommendation.csv").exists()
    assert (tmp_path / "phase10a_feature_family_summary.csv").exists()
    assert (tmp_path / "phase10a_feature_family_gate_report.csv").exists()
    assert (tmp_path / "phase10a_feature_family_conclusion.csv").exists()
    assert (tmp_path / "phase10a_feature_family_feasibility_spec.md").exists()