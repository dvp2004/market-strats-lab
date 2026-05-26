from pathlib import Path

import pandas as pd

from market_strats.analysis.feature_source_inventory_and_contract_audit import (
    build_phase13c_feature_source_inventory,
    build_phase13d_blocked_family_check,
    save_phase13c_multifactor_feature_source_inventory_spec,
    save_phase13d_feature_contract_readiness_audit,
)


def _write_phase13b_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13B",
                "verdict": "Completed — multi-factor model architecture roadmap spec passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13b_roadmap_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13b_roadmap_gate_report.csv", index=False)

    for name in [
        "phase13b_roadmap_feature_family_registry.csv",
        "phase13b_roadmap_walk_forward_design.csv",
        "phase13b_roadmap_visual_reporting_plan.csv",
        "phase13b_roadmap_paper_trading_readiness_plan.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13a_baseline_research_arc_freeze_spec": {"enabled": False},
        "phase13b_multifactor_model_architecture_roadmap_spec": {"enabled": False},
        "phase13c_multifactor_feature_source_inventory_spec": {
            "enabled": True,
            "spec_role": (
                "Multi-factor feature-source inventory and leakage-feasibility "
                "spec only"
            ),
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13B",
            "proposed_next_phase": "Phase 13D",
            "allow_feature_ingestion": False,
            "allow_feature_calculation": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13b_conclusion": str(
                    tmp_path / "phase13b_roadmap_conclusion.csv"
                ),
                "phase13b_gate_report": str(
                    tmp_path / "phase13b_roadmap_gate_report.csv"
                ),
                "phase13b_feature_family_registry": str(
                    tmp_path / "phase13b_roadmap_feature_family_registry.csv"
                ),
                "phase13b_walk_forward_design": str(
                    tmp_path / "phase13b_roadmap_walk_forward_design.csv"
                ),
                "phase13b_visual_reporting_plan": str(
                    tmp_path / "phase13b_roadmap_visual_reporting_plan.csv"
                ),
                "phase13b_paper_trading_readiness_plan": str(
                    tmp_path / "phase13b_roadmap_paper_trading_readiness_plan.csv"
                ),
            },
            "feature_source_inventory": [
                {
                    "family_id": "technical",
                    "family_status": "source_contract_feasible",
                    "candidate_sources": ["OHLCV"],
                    "feature_examples": ["trend"],
                    "timing_frequency": "daily",
                    "point_in_time_requirement": "lagged close",
                    "revision_risk": "low",
                    "leakage_risk": "medium",
                    "immediate_decision": "eligible",
                    "blocked_now": False,
                },
                {
                    "family_id": "macro",
                    "family_status": "source_contract_feasible_with_lagging",
                    "candidate_sources": ["FRED"],
                    "feature_examples": ["rates"],
                    "timing_frequency": "mixed",
                    "point_in_time_requirement": "release lag",
                    "revision_risk": "high",
                    "leakage_risk": "high",
                    "immediate_decision": "eligible_with_lagging",
                    "blocked_now": False,
                },
                {
                    "family_id": "fundamental",
                    "family_status": "requires_source_audit_before_use",
                    "candidate_sources": ["valuation"],
                    "feature_examples": ["earnings"],
                    "timing_frequency": "quarterly",
                    "point_in_time_requirement": "publication lag",
                    "revision_risk": "medium",
                    "leakage_risk": "high",
                    "immediate_decision": "blocked",
                    "blocked_now": True,
                },
                {
                    "family_id": "sentiment",
                    "family_status": "requires_source_audit_before_use",
                    "candidate_sources": ["news"],
                    "feature_examples": ["tone"],
                    "timing_frequency": "daily",
                    "point_in_time_requirement": "timestamped availability",
                    "revision_risk": "medium",
                    "leakage_risk": "very_high",
                    "immediate_decision": "blocked",
                    "blocked_now": True,
                },
                {
                    "family_id": "dissertation_integration",
                    "family_status": "methodology_only",
                    "candidate_sources": ["none"],
                    "feature_examples": ["optimisation"],
                    "timing_frequency": "not_applicable",
                    "point_in_time_requirement": "methodology only",
                    "revision_risk": "not_applicable",
                    "leakage_risk": "conceptual",
                    "immediate_decision": "methodology_only",
                    "blocked_now": False,
                },
            ],
            "feature_contract_requirements": [
                {
                    "requirement_id": f"FC{i}",
                    "requirement": "contract requirement",
                    "required": True,
                }
                for i in range(1, 9)
            ],
            "leakage_control_policy": [
                {
                    "control_id": f"LC{i}",
                    "control": "leakage control",
                    "required": True,
                }
                for i in range(1, 7)
            ],
            "blocked_family_policy": {
                "fundamental_blocked_until": "Dedicated audit passes.",
                "sentiment_blocked_until": "Dedicated audit passes.",
                "dissertation_direct_alpha_blocked_until": "Mapping justified.",
                "blocked_families_may_appear_in_roadmap": True,
                "blocked_families_may_be_ingested_now": False,
                "blocked_families_may_be_used_in_model_now": False,
            },
            "phase13d_boundary": {
                "allowed_next_step": (
                    "Feature contract and data availability readiness audit only"
                ),
                "forbidden_next_step": (
                    "actual feature ingestion, feature calculation, signal creation, "
                    "allocation rule, strategy backtest, model training, "
                    "paper-trading deployment, candidate promotion, or "
                    "final-candidate change"
                ),
                "phase13d_may_audit_inventory": True,
                "phase13d_may_audit_contract_requirements": True,
                "phase13d_may_ingest_features": False,
                "phase13d_may_calculate_features": False,
                "phase13d_may_train_model": False,
                "phase13d_may_create_signal": False,
                "phase13d_may_run_backtest": False,
                "phase13d_may_deploy_paper_trading": False,
                "phase13d_may_promote_candidate": False,
            },
        },
        "phase13d_feature_contract_readiness_audit": {
            "enabled": True,
            "audit_role": "Feature contract and data availability readiness audit only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13C",
            "proposed_next_phase": "Phase 13E",
            "allow_feature_ingestion": False,
            "allow_feature_calculation": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13a_baseline_research_arc_freeze_spec": False,
                "phase13b_multifactor_model_architecture_roadmap_spec": False,
                "phase13c_multifactor_feature_source_inventory_spec": True,
                "phase13d_feature_contract_readiness_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13c_reports": {
                "source_report_check": str(
                    tmp_path / "phase13c_inventory_source_report_check.csv"
                ),
                "phase13b_result_check": str(
                    tmp_path / "phase13c_inventory_phase13b_result_check.csv"
                ),
                "feature_source_inventory": str(
                    tmp_path / "phase13c_inventory_feature_source_inventory.csv"
                ),
                "feature_contract_requirements": str(
                    tmp_path / "phase13c_inventory_feature_contract_requirements.csv"
                ),
                "leakage_control_policy": str(
                    tmp_path / "phase13c_inventory_leakage_control_policy.csv"
                ),
                "blocked_family_policy": str(
                    tmp_path / "phase13c_inventory_blocked_family_policy.csv"
                ),
                "phase13d_boundary_check": str(
                    tmp_path / "phase13c_inventory_phase13d_boundary_check.csv"
                ),
                "scope_boundary_check": str(
                    tmp_path / "phase13c_inventory_scope_boundary_check.csv"
                ),
                "gate_report": str(tmp_path / "phase13c_inventory_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13c_inventory_conclusion.csv"),
            },
            "readiness_claims": {
                "phase13c_inventory_exists": True,
                "technical_contract_feasible": True,
                "macro_contract_feasible_with_lagging": True,
                "fundamental_blocked_until_audit": True,
                "sentiment_blocked_until_audit": True,
                "dissertation_methodology_only": True,
                "feature_ingested": False,
                "feature_calculated": False,
                "signal_created": False,
                "backtest_run": False,
                "model_trained": False,
                "paper_trading_deployed": False,
                "candidate_promoted": False,
                "final_candidate_changed": False,
            },
            "phase13e_boundary": {
                "allowed_next_step": (
                    "Technical and macro feature-contract schema design spec only"
                ),
                "forbidden_next_step": (
                    "actual feature ingestion, feature calculation, signal creation, "
                    "allocation rule, strategy backtest, model training, "
                    "paper-trading deployment, candidate promotion, or "
                    "final-candidate change"
                ),
                "phase13e_may_define_feature_schema": True,
                "phase13e_may_define_transform_rules": True,
                "phase13e_may_define_visual_feature_reports": True,
                "phase13e_may_ingest_features": False,
                "phase13e_may_calculate_features": False,
                "phase13e_may_train_model": False,
                "phase13e_may_create_signal": False,
                "phase13e_may_run_backtest": False,
                "phase13e_may_deploy_paper_trading": False,
                "phase13e_may_promote_candidate": False,
            },
        },
    }


def test_phase13c_inventory_blocks_fundamental_and_sentiment(tmp_path):
    _write_phase13b_reports(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase13c_multifactor_feature_source_inventory_spec"]

    inventory = build_phase13c_feature_source_inventory(phase_config)
    blocked_check = build_phase13d_blocked_family_check(inventory)

    assert len(inventory) == 5
    assert bool(blocked_check["passed"].all())


def test_phase13c_and_13d_save_reports(tmp_path):
    _write_phase13b_reports(tmp_path)
    config = _config(tmp_path)

    out_c = save_phase13c_multifactor_feature_source_inventory_spec(
        config=config,
        reports_dir=tmp_path,
    )
    out_d = save_phase13d_feature_contract_readiness_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_c["conclusion"].iloc[0]["all_gates_passed"]
    assert out_d["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13c_inventory_conclusion.csv").exists()
    assert (tmp_path / "phase13d_contract_conclusion.csv").exists()


def test_phase13d_fails_if_sentiment_unblocked(tmp_path):
    _write_phase13b_reports(tmp_path)
    config = _config(tmp_path)
    inventory = build_phase13c_feature_source_inventory(
        config["phase13c_multifactor_feature_source_inventory_spec"]
    )
    inventory.loc[inventory["family_id"] == "sentiment", "blocked_now"] = False

    blocked_check = build_phase13d_blocked_family_check(inventory)

    assert not bool(blocked_check["passed"].all())