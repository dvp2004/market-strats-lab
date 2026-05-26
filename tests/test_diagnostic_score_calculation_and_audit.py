from pathlib import Path

import pandas as pd

from market_strats.analysis.diagnostic_score_calculation_and_audit import (
    build_phase12c_aggregate_score,
    build_phase12c_component_state_distribution,
    build_phase12c_component_state_panel,
    build_phase12d_distribution_check,
    save_phase12c_diagnostic_score_calculation,
    save_phase12d_diagnostic_score_distribution_audit,
)


def _write_source_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {"component_id": "technical_regime_context"},
            {"component_id": "macro_regime_context"},
            {"component_id": "validation_risk_context"},
        ]
    ).to_csv(tmp_path / "phase12a_prereg_eligible_components.csv", index=False)

    pd.DataFrame(
        [
            {"component_id": "future_fundamental_context"},
            {"component_id": "future_sentiment_context"},
        ]
    ).to_csv(tmp_path / "phase12a_prereg_blocked_components.csv", index=False)

    for name in [
        "phase12a_prereg_formula_structure.csv",
        "phase12a_prereg_weighting_policy.csv",
        "phase12a_prereg_missingness_policy.csv",
        "phase12a_prereg_score_state_interpretation.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)

    pd.DataFrame(
        [
            {
                "phase": "Phase 12B",
                "verdict": "Completed — score-calculation readiness audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase12b_readiness_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True}]).to_csv(
        tmp_path / "phase12b_readiness_gate_report.csv",
        index=False,
    )


def _config(tmp_path: Path):
    return {
        "phase12c_diagnostic_score_calculation": {
            "enabled": True,
            "calculation_role": "Diagnostic score calculation only",
            "phase_branch": "Phase 12 regime score calculation",
            "source_phase": "Phase 12B",
            "proposed_next_phase": "Phase 12D",
            "allow_diagnostic_score_calculation": True,
            "allow_numeric_score_output": False,
            "allow_empirical_return_weights": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_model_training": False,
            "allow_new_data_ingestion": False,
            "allow_candidate_promotion": False,
            "source_reports": {
                "phase12a_eligible_components": str(
                    tmp_path / "phase12a_prereg_eligible_components.csv"
                ),
                "phase12a_blocked_components": str(
                    tmp_path / "phase12a_prereg_blocked_components.csv"
                ),
                "phase12a_formula_structure": str(
                    tmp_path / "phase12a_prereg_formula_structure.csv"
                ),
                "phase12a_weighting_policy": str(
                    tmp_path / "phase12a_prereg_weighting_policy.csv"
                ),
                "phase12a_missingness_policy": str(
                    tmp_path / "phase12a_prereg_missingness_policy.csv"
                ),
                "phase12a_score_state_interpretation": str(
                    tmp_path / "phase12a_prereg_score_state_interpretation.csv"
                ),
                "phase12b_conclusion": str(
                    tmp_path / "phase12b_readiness_conclusion.csv"
                ),
                "phase12b_gate_report": str(
                    tmp_path / "phase12b_readiness_gate_report.csv"
                ),
            },
            "component_state_inputs": [
                {
                    "component_id": "technical_regime_context",
                    "family": "technical",
                    "diagnostic_state": "neutral",
                    "state_source": "Phase 9 mixed evidence.",
                    "state_role": "eligible_component_state",
                    "source_is_existing_project_report": True,
                    "trading_allowed": False,
                    "signal_allowed": False,
                },
                {
                    "component_id": "macro_regime_context",
                    "family": "macro_rates_inflation",
                    "diagnostic_state": "neutral",
                    "state_source": "Phase 10 mixed evidence.",
                    "state_role": "eligible_component_state",
                    "source_is_existing_project_report": True,
                    "trading_allowed": False,
                    "signal_allowed": False,
                },
                {
                    "component_id": "validation_risk_context",
                    "family": "validation_risk",
                    "diagnostic_state": "fragile",
                    "state_source": "Validation risk caveats.",
                    "state_role": "eligible_control_state",
                    "source_is_existing_project_report": True,
                    "trading_allowed": False,
                    "signal_allowed": False,
                },
            ],
            "scoring_policy": {
                "score_id": "pre_registered_three_component_regime_score",
                "allowed_states": ["supportive", "neutral", "fragile"],
                "formula_source": "Phase 12A",
                "calculation_scope": "static_branch_level_diagnostic_score",
                "aggregation_method": (
                    "categorical_equal_vote_with_validation_risk_control"
                ),
                "empirical_weights_allowed": False,
                "numeric_weights_allowed": False,
                "returns_used": False,
                "validation_risk_control": {
                    "enabled": True,
                    "fragile_validation_risk_caps_supportive_score": True,
                    "fragile_validation_risk_with_no_supportive_majority_forces_fragile": True,
                },
            },
            "phase12d_boundary": {
                "allowed_next_step": (
                    "Diagnostic score distribution and content audit only"
                ),
                "forbidden_next_step": (
                    "trading signal creation, allocation rule, strategy backtest, "
                    "model training, new data ingestion, or candidate promotion"
                ),
                "phase12d_may_audit_score_distribution": True,
                "phase12d_may_create_signal": False,
                "phase12d_may_test_strategy": False,
                "phase12d_may_assign_empirical_weights": False,
                "phase12d_may_train_model": False,
                "phase12d_may_ingest_new_data": False,
                "phase12d_may_promote_candidate": False,
            },
        },
        "phase12d_diagnostic_score_distribution_audit": {
            "enabled": True,
            "audit_role": "Diagnostic score distribution and content audit only",
            "phase_branch": "Phase 12 regime score calculation",
            "source_phase": "Phase 12C",
            "proposed_next_phase": "Phase 12E",
            "allow_score_interpretation": True,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_new_data_ingestion": False,
            "allow_candidate_promotion": False,
            "source_score_reports": {
                "component_state_panel": str(
                    tmp_path / "phase12c_score_component_state_panel.csv"
                ),
                "aggregate_score": str(
                    tmp_path / "phase12c_score_aggregate_score.csv"
                ),
                "component_state_distribution": str(
                    tmp_path / "phase12c_score_component_state_distribution.csv"
                ),
                "gate_report": str(tmp_path / "phase12c_score_gate_report.csv"),
                "conclusion": str(tmp_path / "phase12c_score_conclusion.csv"),
            },
            "expected_score_states": ["supportive", "neutral", "fragile"],
            "expected_component_count": 3,
            "expected_aggregate_score_count": 1,
            "phase12e_boundary": {
                "allowed_next_step": (
                    "Diagnostic score interpretation and closeout audit only"
                ),
                "forbidden_next_step": (
                    "trading signal creation, allocation rule, strategy backtest, "
                    "model training, new data ingestion, or candidate promotion"
                ),
                "phase12e_may_interpret_score_diagnostically": True,
                "phase12e_may_create_signal": False,
                "phase12e_may_test_strategy": False,
                "phase12e_may_assign_empirical_weights": False,
                "phase12e_may_train_model": False,
                "phase12e_may_ingest_new_data": False,
                "phase12e_may_promote_candidate": False,
            },
        },
    }


def test_phase12c_calculates_fragile_diagnostic_score(tmp_path):
    _write_source_reports(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase12c_diagnostic_score_calculation"]

    panel = build_phase12c_component_state_panel(phase_config)
    distribution = build_phase12c_component_state_distribution(panel)
    aggregate = build_phase12c_aggregate_score(
        phase_config=phase_config,
        component_state_panel=panel,
    )

    assert len(panel) == 3
    assert int(distribution["component_count"].sum()) == 3
    assert aggregate.iloc[0]["diagnostic_score_state"] == "fragile"
    assert not bool(aggregate.iloc[0]["returns_used"])
    assert not bool(aggregate.iloc[0]["trading_signal_created"])


def test_phase12c_and_12d_save_reports(tmp_path):
    _write_source_reports(tmp_path)
    config = _config(tmp_path)

    out_c = save_phase12c_diagnostic_score_calculation(
        config=config,
        reports_dir=tmp_path,
    )
    out_d = save_phase12d_diagnostic_score_distribution_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_c["conclusion"].iloc[0]["all_gates_passed"]
    assert out_d["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase12c_score_aggregate_score.csv").exists()
    assert (tmp_path / "phase12d_audit_conclusion.csv").exists()


def test_phase12d_distribution_check_rejects_bad_state(tmp_path):
    phase_config = _config(tmp_path)[
        "phase12d_diagnostic_score_distribution_audit"
    ]

    panel = pd.DataFrame(
        [
            {
                "component_id": "technical_regime_context",
                "diagnostic_state": "invalid",
            }
        ]
    )
    distribution = pd.DataFrame(
        [{"diagnostic_state": "invalid", "component_count": 1}]
    )
    aggregate = pd.DataFrame(
        [{"diagnostic_score_state": "invalid"}]
    )

    check = build_phase12d_distribution_check(
        component_state_panel=panel,
        component_state_distribution=distribution,
        aggregate_score=aggregate,
        phase_config=phase_config,
    )

    assert not bool(check["passed"].all())