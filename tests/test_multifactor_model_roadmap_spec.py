from pathlib import Path

import pandas as pd

from market_strats.analysis.multifactor_model_roadmap_spec import (
    build_phase13a_baseline_freeze_report,
    build_phase13a_transition_decision_report,
    build_phase13b_architecture_candidates,
    build_phase13b_feature_family_registry,
    save_phase13a_baseline_research_arc_freeze_spec,
    save_phase13b_multifactor_model_architecture_roadmap_spec,
)


def _write_phase12f_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 12F",
                "verdict": "Completed — final Phase 12 diagnostic score checkpoint passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase12f_final_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase12f_final_gate_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "claim": "score_to_signal_created",
                "expected": False,
                "actual": False,
                "passed": True,
            }
        ]
    ).to_csv(
        tmp_path / "phase12f_final_branch_closure_claims_check.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "diagnostic_score_state": "fragile",
                "candidate_promoted": False,
            }
        ]
    ).to_csv(tmp_path / "phase12c_score_aggregate_score.csv", index=False)


def _config(tmp_path: Path):
    return {
        "phase13a_baseline_research_arc_freeze_spec": {
            "enabled": True,
            "spec_role": "Baseline SPY research arc freeze and transition spec only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 12F",
            "proposed_next_phase": "Phase 13B",
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_new_data_ingestion": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase12f_conclusion": str(tmp_path / "phase12f_final_conclusion.csv"),
                "phase12f_gate_report": str(tmp_path / "phase12f_final_gate_report.csv"),
                "phase12f_branch_closure": str(
                    tmp_path / "phase12f_final_branch_closure_claims_check.csv"
                ),
                "phase12c_aggregate_score": str(
                    tmp_path / "phase12c_score_aggregate_score.csv"
                ),
            },
            "baseline_freeze": {
                "baseline_arc_name": "SPY regime-switch baseline research framework",
                "baseline_arc_status": "Frozen as benchmark and validation infrastructure",
                "final_candidate": "Phase 6B/6C 3D + deep_drawdown_guard + loose_relief",
                "final_candidate_role": (
                    "Best execution-realistic risk-adjusted candidate built so far, "
                    "not final project endpoint"
                ),
                "diagnostic_score_state": "fragile",
                "diagnostic_score_role": "Baseline research diagnostic, not signal",
                "hierarchy_changed": False,
                "candidate_promoted": False,
                "score_to_signal_created": False,
                "baseline_reusable_assets": [
                    "SPY Buy & Hold benchmark",
                    "pre-registration workflow",
                    "gate reports",
                ],
            },
            "transition_decision": {
                "decision": "Open a new multi-factor model architecture branch",
                "reason": "Baseline arc did not build the intended richer model.",
                "rejected_next_step": "Direct score-to-signal conversion from fragile Phase 12 score",
                "accepted_next_step": "Multi-factor model architecture roadmap spec",
                "burden_of_proof": "Future signal/backtest requires separate pre-registration.",
            },
            "phase13b_boundary": {
                "allowed_next_step": (
                    "Multi-factor long-term decision model architecture roadmap spec only"
                ),
                "forbidden_next_step": (
                    "feature ingestion, signal creation, allocation rule, strategy "
                    "backtest, empirical weighting, model training, paper-trading "
                    "deployment, candidate promotion, or final-candidate change"
                ),
                "phase13b_may_define_architecture": True,
                "phase13b_may_define_feature_families": True,
                "phase13b_may_define_walk_forward_design": True,
                "phase13b_may_define_visual_reports": True,
                "phase13b_may_define_paper_trading_requirements": True,
                "phase13b_may_ingest_data": False,
                "phase13b_may_train_model": False,
                "phase13b_may_create_signal": False,
                "phase13b_may_run_backtest": False,
                "phase13b_may_promote_candidate": False,
            },
        },
        "phase13b_multifactor_model_architecture_roadmap_spec": {
            "enabled": True,
            "spec_role": (
                "Multi-factor long-term decision model architecture roadmap spec only"
            ),
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13A",
            "proposed_next_phase": "Phase 13C",
            "ultimate_goal": (
                "Build and eventually paper-trade long-term decision models using "
                "technical, macro, fundamental, and sentiment indicators."
            ),
            "allow_feature_ingestion": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13a_conclusion": str(
                    tmp_path / "phase13a_baseline_freeze_conclusion.csv"
                ),
                "phase13a_gate_report": str(
                    tmp_path / "phase13a_baseline_freeze_gate_report.csv"
                ),
            },
            "feature_family_registry": [
                {
                    "family_id": "technical",
                    "status": "eligible",
                    "intended_role": "Technical context",
                    "immediate_action": "Feature contract",
                    "blocked_now": False,
                },
                {
                    "family_id": "macro",
                    "status": "eligible",
                    "intended_role": "Macro context",
                    "immediate_action": "Feature contract",
                    "blocked_now": False,
                },
                {
                    "family_id": "fundamental",
                    "status": "not_yet_audited",
                    "intended_role": "Fundamental context",
                    "immediate_action": "Source audit",
                    "blocked_now": True,
                },
                {
                    "family_id": "sentiment",
                    "status": "not_yet_audited",
                    "intended_role": "Sentiment context",
                    "immediate_action": "Source audit",
                    "blocked_now": True,
                },
                {
                    "family_id": "dissertation_integration",
                    "status": "methodology_candidate_only",
                    "intended_role": "Decision-support methodology",
                    "immediate_action": "Map methodology",
                    "blocked_now": False,
                },
            ],
            "architecture_candidates": [
                {
                    "architecture_id": "A1",
                    "role": "Interpretable score",
                    "description": "Transparent baseline layer",
                    "priority": 1,
                    "immediate_status": "roadmap_only",
                },
                {
                    "architecture_id": "A2",
                    "role": "Walk-forward classifier",
                    "description": "Future probabilistic model",
                    "priority": 2,
                    "immediate_status": "future",
                },
                {
                    "architecture_id": "A3",
                    "role": "Ensemble layer",
                    "description": "Future ensemble",
                    "priority": 3,
                    "immediate_status": "future",
                },
                {
                    "architecture_id": "A4",
                    "role": "Visual dashboard",
                    "description": "Decision dashboard",
                    "priority": 4,
                    "immediate_status": "required_reporting_layer",
                },
            ],
            "dissertation_integration_plan": [
                {
                    "item_id": "D1",
                    "integration_type": "methodological",
                    "planned_use": "Optimisation discipline",
                    "allowed_now": True,
                }
            ],
            "walk_forward_design": {
                "design_id": "walk_forward",
                "train_window_policy": "anchored_and_rolling",
                "validation_policy": "walk_forward_after_feature_contracts",
                "test_policy": "holdout_untouched",
                "rebalance_policy": "to_be_pre_registered",
                "leakage_controls": ["point-in-time", "release lag"],
            },
            "visual_reporting_plan": [
                {"report_id": "exposure", "purpose": "Exposure timeline"},
                {"report_id": "rationale", "purpose": "Decision rationale"},
                {"report_id": "trades", "purpose": "Trade markers"},
                {"report_id": "equity", "purpose": "Equity curve"},
                {"report_id": "drawdown", "purpose": "Drawdown comparison"},
            ],
            "paper_trading_readiness_plan": [
                {"gate_id": "PTR1", "requirement": "Feature contracts locked"},
                {"gate_id": "PTR2", "requirement": "Walk-forward results exist"},
                {"gate_id": "PTR3", "requirement": "Visual reports exist"},
                {"gate_id": "PTR4", "requirement": "No live-money claim"},
                {"gate_id": "PTR5", "requirement": "Model frozen before paper"},
            ],
            "phase13c_boundary": {
                "allowed_next_step": (
                    "Multi-factor feature-source inventory and leakage-feasibility "
                    "spec only"
                ),
                "forbidden_next_step": (
                    "actual feature ingestion, model training, signal creation, "
                    "allocation rule, strategy backtest, paper-trading deployment, "
                    "candidate promotion, or final-candidate change"
                ),
                "phase13c_may_define_data_inventory": True,
                "phase13c_may_define_feature_contracts": True,
                "phase13c_may_define_leakage_controls": True,
                "phase13c_may_ingest_features": False,
                "phase13c_may_train_model": False,
                "phase13c_may_create_signal": False,
                "phase13c_may_run_backtest": False,
                "phase13c_may_deploy_paper_trading": False,
                "phase13c_may_promote_candidate": False,
            },
        },
    }


def test_phase13a_freezes_baseline_and_rejects_score_to_signal(tmp_path):
    _write_phase12f_reports(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase13a_baseline_research_arc_freeze_spec"]

    freeze = build_phase13a_baseline_freeze_report(phase_config)
    decision = build_phase13a_transition_decision_report(phase_config)

    assert freeze.iloc[0]["diagnostic_score_state"] == "fragile"
    assert not bool(freeze.iloc[0]["score_to_signal_created"])
    assert "multi-factor" in decision.iloc[0]["accepted_next_step"].lower()


def test_phase13b_roadmap_contains_required_families_and_architectures(tmp_path):
    _write_phase12f_reports(tmp_path)
    config = _config(tmp_path)

    save_phase13a_baseline_research_arc_freeze_spec(
        config=config,
        reports_dir=tmp_path,
    )

    phase_config = config["phase13b_multifactor_model_architecture_roadmap_spec"]
    families = build_phase13b_feature_family_registry(phase_config)
    architectures = build_phase13b_architecture_candidates(phase_config)

    family_ids = set(families["family_id"].tolist())

    assert {"technical", "macro", "fundamental", "sentiment"}.issubset(family_ids)
    assert len(architectures) == 4


def test_phase13a_and_13b_save_reports(tmp_path):
    _write_phase12f_reports(tmp_path)
    config = _config(tmp_path)

    out_a = save_phase13a_baseline_research_arc_freeze_spec(
        config=config,
        reports_dir=tmp_path,
    )
    out_b = save_phase13b_multifactor_model_architecture_roadmap_spec(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_a["conclusion"].iloc[0]["all_gates_passed"]
    assert out_b["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13a_baseline_freeze_conclusion.csv").exists()
    assert (tmp_path / "phase13b_roadmap_conclusion.csv").exists()