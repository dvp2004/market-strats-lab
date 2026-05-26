from pathlib import Path

import pandas as pd

from market_strats.analysis.diagnostic_score_interpretation_closeout import (
    build_phase12e_closeout_claims_check,
    build_phase12e_score_interpretation,
    save_phase12e_diagnostic_score_interpretation_closeout,
    save_phase12f_final_diagnostic_score_checkpoint_audit,
)


def _write_phase12_source_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "component_id": "technical_regime_context",
                "diagnostic_state": "neutral",
            },
            {
                "component_id": "macro_regime_context",
                "diagnostic_state": "neutral",
            },
            {
                "component_id": "validation_risk_context",
                "diagnostic_state": "fragile",
            },
        ]
    ).to_csv(tmp_path / "phase12c_score_component_state_panel.csv", index=False)

    pd.DataFrame(
        [
            {"diagnostic_state": "neutral", "component_count": 2},
            {"diagnostic_state": "fragile", "component_count": 1},
        ]
    ).to_csv(
        tmp_path / "phase12c_score_component_state_distribution.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "diagnostic_score_state": "fragile",
                "raw_vote_state": "neutral",
                "candidate_promoted": False,
            }
        ]
    ).to_csv(tmp_path / "phase12c_score_aggregate_score.csv", index=False)

    for prefix, verdict in {
        "phase12a_prereg": "Completed — score-calculation pre-registration spec passed",
        "phase12b_readiness": "Completed — score-calculation readiness audit passed",
        "phase12c_score": "Completed — diagnostic score calculation passed",
        "phase12d_audit": "Completed — diagnostic score distribution audit passed",
    }.items():
        pd.DataFrame(
            [
                {
                    "phase": prefix,
                    "verdict": verdict,
                    "all_gates_passed": True,
                    "strategy_promotion": False,
                    "candidate_promotion": False,
                }
            ]
        ).to_csv(tmp_path / f"{prefix}_conclusion.csv", index=False)

        pd.DataFrame(
            [
                {
                    "gate": "dummy",
                    "passed": True,
                    "result": "Passed",
                    "all_gates_passed": True,
                }
            ]
        ).to_csv(tmp_path / f"{prefix}_gate_report.csv", index=False)

    for markdown in [
        "phase12a_score_calculation_preregistration_spec.md",
        "phase12b_score_calculation_readiness_audit.md",
        "phase12c_diagnostic_score_calculation.md",
        "phase12d_diagnostic_score_distribution_audit.md",
    ]:
        (tmp_path / markdown).write_text("# report\n", encoding="utf-8")


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase12a_score_calculation_preregistration_spec": {"enabled": False},
        "phase12b_score_calculation_readiness_audit": {"enabled": False},
        "phase12c_diagnostic_score_calculation": {"enabled": False},
        "phase12d_diagnostic_score_distribution_audit": {"enabled": False},
        "phase12e_diagnostic_score_interpretation_closeout": {
            "enabled": True,
            "audit_role": "Diagnostic score interpretation and closeout audit only",
            "phase_branch": "Phase 12 diagnostic regime score branch",
            "source_phase": "Phase 12D",
            "proposed_next_phase": "Phase 12F",
            "allow_score_interpretation": True,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_new_data_ingestion": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_score_reports": {
                "component_state_panel": str(
                    tmp_path / "phase12c_score_component_state_panel.csv"
                ),
                "component_state_distribution": str(
                    tmp_path / "phase12c_score_component_state_distribution.csv"
                ),
                "aggregate_score": str(
                    tmp_path / "phase12c_score_aggregate_score.csv"
                ),
                "phase12c_conclusion": str(
                    tmp_path / "phase12c_score_conclusion.csv"
                ),
                "phase12d_conclusion": str(
                    tmp_path / "phase12d_audit_conclusion.csv"
                ),
                "phase12d_gate_report": str(
                    tmp_path / "phase12d_audit_gate_report.csv"
                ),
            },
            "expected_aggregate_state": "fragile",
            "allowed_score_states": ["supportive", "neutral", "fragile"],
            "interpretation_policy": {
                "interpretation_role": "diagnostic-only research interpretation",
                "fragile_interpretation": (
                    "The diagnostic regime score is fragile because technical and "
                    "macro evidence are neutral while validation-risk context is fragile."
                ),
                "neutral_interpretation": "Neutral diagnostic interpretation.",
                "supportive_interpretation": "Supportive diagnostic interpretation.",
                "permitted_use": "Document research context and caveat stack only.",
                "prohibited_use": (
                    "Trading signal, allocation rule, strategy backtest, empirical "
                    "weighting, model training, live-trading recommendation, candidate "
                    "promotion, or final-candidate change."
                ),
            },
            "closeout_claims": {
                "diagnostic_score_interpreted": True,
                "score_to_signal_created": False,
                "allocation_rule_created": False,
                "strategy_backtest_run": False,
                "empirical_weights_assigned": False,
                "model_trained": False,
                "new_data_ingested": False,
                "candidate_promoted": False,
                "final_candidate_changed": False,
            },
            "phase12f_boundary": {
                "allowed_next_step": "Final Phase 12 checkpoint audit only",
                "forbidden_next_step": (
                    "score-to-signal conversion, allocation rule, strategy backtest, "
                    "empirical weighting, model training, new data ingestion, "
                    "candidate promotion, or final-candidate change"
                ),
                "phase12f_may_run_final_checkpoint": True,
                "phase12f_may_create_signal": False,
                "phase12f_may_test_strategy": False,
                "phase12f_may_assign_empirical_weights": False,
                "phase12f_may_train_model": False,
                "phase12f_may_ingest_new_data": False,
                "phase12f_may_promote_candidate": False,
                "phase12f_may_change_final_candidate": False,
            },
        },
        "phase12f_final_diagnostic_score_checkpoint_audit": {
            "enabled": True,
            "audit_role": "Final Phase 12 diagnostic score checkpoint audit only",
            "phase_branch": "Phase 12 diagnostic regime score branch",
            "checkpoint_status": (
                "Phase 12 closed — diagnostic regime score calculated, audited, "
                "interpreted, and bounded"
            ),
            "next_allowed_step": (
                "Separate future score-to-signal pre-registration spec only, if pursued"
            ),
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_new_data_ingestion": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase12a_score_calculation_preregistration_spec": False,
                "phase12b_score_calculation_readiness_audit": False,
                "phase12c_diagnostic_score_calculation": False,
                "phase12d_diagnostic_score_distribution_audit": False,
                "phase12e_diagnostic_score_interpretation_closeout": True,
                "phase12f_final_diagnostic_score_checkpoint_audit": True,
                "relative_momentum_allocator": True,
            },
            "expected_report_prefixes": [
                "phase12a_prereg",
                "phase12b_readiness",
                "phase12c_score",
                "phase12d_audit",
                "phase12e_interpretation",
            ],
            "expected_markdown_reports": [
                "phase12a_score_calculation_preregistration_spec.md",
                "phase12b_score_calculation_readiness_audit.md",
                "phase12c_diagnostic_score_calculation.md",
                "phase12d_diagnostic_score_distribution_audit.md",
                "phase12e_diagnostic_score_interpretation_closeout.md",
            ],
            "phase_conclusion_reports": {
                "phase12a": str(tmp_path / "phase12a_prereg_conclusion.csv"),
                "phase12b": str(tmp_path / "phase12b_readiness_conclusion.csv"),
                "phase12c": str(tmp_path / "phase12c_score_conclusion.csv"),
                "phase12d": str(tmp_path / "phase12d_audit_conclusion.csv"),
                "phase12e": str(tmp_path / "phase12e_interpretation_conclusion.csv"),
            },
            "phase_gate_reports": {
                "phase12a": str(tmp_path / "phase12a_prereg_gate_report.csv"),
                "phase12b": str(tmp_path / "phase12b_readiness_gate_report.csv"),
                "phase12c": str(tmp_path / "phase12c_score_gate_report.csv"),
                "phase12d": str(tmp_path / "phase12d_audit_gate_report.csv"),
                "phase12e": str(tmp_path / "phase12e_interpretation_gate_report.csv"),
            },
            "required_phase_verdict_fragments": {
                "phase12a": "score-calculation pre-registration spec passed",
                "phase12b": "score-calculation readiness audit passed",
                "phase12c": "diagnostic score calculation passed",
                "phase12d": "diagnostic score distribution audit passed",
                "phase12e": "diagnostic score interpretation closeout passed",
            },
            "branch_closure_claims": {
                "diagnostic_score_exists": True,
                "diagnostic_score_interpreted": True,
                "score_to_signal_created": False,
                "allocation_rule_created": False,
                "strategy_backtest_run": False,
                "empirical_weights_assigned": False,
                "model_trained": False,
                "new_data_ingested": False,
                "candidate_promoted": False,
                "final_candidate_changed": False,
            },
            "future_phase13_boundary": {
                "allowed_next_step": (
                    "Separate score-to-signal pre-registration spec only, if pursued"
                ),
                "forbidden_next_step": (
                    "direct signal creation, allocation rule, strategy backtest, "
                    "empirical weighting, model training, new data ingestion, "
                    "candidate promotion, or final-candidate change"
                ),
                "phase13_may_define_signal_spec": True,
                "phase13_may_create_signal_immediately": False,
                "phase13_may_test_strategy": False,
                "phase13_may_assign_empirical_weights": False,
                "phase13_may_train_model": False,
                "phase13_may_ingest_new_data": False,
                "phase13_may_promote_candidate": False,
                "phase13_may_change_final_candidate": False,
            },
        },
    }


def test_phase12e_interprets_fragile_score(tmp_path):
    _write_phase12_source_reports(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase12e_diagnostic_score_interpretation_closeout"]

    aggregate = pd.read_csv(tmp_path / "phase12c_score_aggregate_score.csv")
    component_panel = pd.read_csv(tmp_path / "phase12c_score_component_state_panel.csv")
    interpretation = build_phase12e_score_interpretation(
        phase_config=phase_config,
        aggregate_score=aggregate,
        component_state_panel=component_panel,
    )
    claims = build_phase12e_closeout_claims_check(phase_config)

    assert interpretation.iloc[0]["diagnostic_score_state"] == "fragile"
    assert "research" in interpretation.iloc[0]["interpretation_role"]
    assert bool(claims["passed"].all())


def test_phase12e_and_12f_save_reports(tmp_path):
    _write_phase12_source_reports(tmp_path)
    config = _config(tmp_path)

    out_e = save_phase12e_diagnostic_score_interpretation_closeout(
        config=config,
        reports_dir=tmp_path,
    )
    out_f = save_phase12f_final_diagnostic_score_checkpoint_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_e["conclusion"].iloc[0]["all_gates_passed"]
    assert out_f["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase12e_interpretation_conclusion.csv").exists()
    assert (tmp_path / "phase12f_final_conclusion.csv").exists()


def test_phase12e_fails_if_signal_created_claim_true(tmp_path):
    _write_phase12_source_reports(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase12e_diagnostic_score_interpretation_closeout"]
    phase_config["closeout_claims"]["score_to_signal_created"] = True

    claims = build_phase12e_closeout_claims_check(phase_config)

    assert not bool(claims["passed"].all())