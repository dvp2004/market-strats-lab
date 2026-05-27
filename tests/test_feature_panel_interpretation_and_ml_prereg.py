from pathlib import Path

import pandas as pd

from market_strats.analysis.feature_panel_interpretation_and_ml_prereg import (
    build_phase13k_feature_availability_summary,
    build_phase13k_feature_state_distribution,
    save_phase13k_feature_panel_interpretation_model_readiness,
    save_phase13l_dataset_split_target_preregistration_spec,
)


def _write_phase13j_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13J",
                "verdict": "Completed — feature panel quality and leakage audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13j_quality_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13j_quality_gate_report.csv", index=False)

    for name in [
        "phase13i_feature_state_timeline.csv",
        "phase13i_feature_availability_heatmap.csv",
        "phase13i_leakage_audit_panel.csv",
        "phase13i_model_feature_matrix_preview.csv",
        "phase13i_decision_rationale_template.csv",
        "phase13j_quality_feature_panel_quality_check.csv",
        "phase13j_quality_leakage_quality_check.csv",
        "phase13j_quality_forbidden_column_check.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _write_feature_panel(tmp_path: Path):
    dates = pd.date_range("2020-01-01", periods=20, freq="B")
    feature_ids = [
        "technical_trend_state",
        "technical_momentum_state",
        "technical_volatility_state",
        "technical_drawdown_state",
        "macro_short_rate_state",
        "macro_yield_curve_state",
        "macro_inflation_state",
        "macro_labour_state",
    ]

    rows = []
    for date in dates:
        for feature_id in feature_ids:
            family_id = "technical" if feature_id.startswith("technical") else "macro"
            rows.append(
                {
                    "as_of_date": date.date(),
                    "family_id": family_id,
                    "feature_id": feature_id,
                    "feature_state": "supportive",
                    "missingness_state": "available",
                    "leakage_flag": False,
                    "feature_value": 1.0,
                    "state_reason": "test",
                }
            )

    pd.DataFrame(rows).to_csv(tmp_path / "phase13i_feature_panel.csv", index=False)


def _config(tmp_path: Path):
    required_feature_ids = [
        "technical_trend_state",
        "technical_momentum_state",
        "technical_volatility_state",
        "technical_drawdown_state",
        "macro_short_rate_state",
        "macro_yield_curve_state",
        "macro_inflation_state",
        "macro_labour_state",
    ]

    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13i_feature_calculation_execution": {"enabled": False},
        "phase13j_feature_panel_quality_leakage_audit": {"enabled": False},
        "phase13k_feature_panel_interpretation_model_readiness": {
            "enabled": True,
            "planning_role": (
                "Feature panel interpretation and model-readiness planning only"
            ),
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13J",
            "proposed_next_phase": "Phase 13L",
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13j_conclusion": str(
                    tmp_path / "phase13j_quality_conclusion.csv"
                ),
                "phase13j_gate_report": str(
                    tmp_path / "phase13j_quality_gate_report.csv"
                ),
                "feature_panel": str(tmp_path / "phase13i_feature_panel.csv"),
                "feature_state_timeline": str(
                    tmp_path / "phase13i_feature_state_timeline.csv"
                ),
                "feature_availability_heatmap": str(
                    tmp_path / "phase13i_feature_availability_heatmap.csv"
                ),
                "leakage_audit_panel": str(
                    tmp_path / "phase13i_leakage_audit_panel.csv"
                ),
                "model_feature_matrix_preview": str(
                    tmp_path / "phase13i_model_feature_matrix_preview.csv"
                ),
                "decision_rationale_template": str(
                    tmp_path / "phase13i_decision_rationale_template.csv"
                ),
                "phase13j_feature_panel_quality_check": str(
                    tmp_path / "phase13j_quality_feature_panel_quality_check.csv"
                ),
                "phase13j_leakage_quality_check": str(
                    tmp_path / "phase13j_quality_leakage_quality_check.csv"
                ),
                "phase13j_forbidden_column_check": str(
                    tmp_path / "phase13j_quality_forbidden_column_check.csv"
                ),
            },
            "interpretation_policy": {
                "min_feature_panel_rows": 100,
                "min_feature_ids": 8,
                "required_families": ["technical", "macro"],
                "required_feature_ids": required_feature_ids,
                "max_leakage_flags": 0,
                "min_available_ratio": 0.20,
            },
            "model_readiness_plan": {
                "dataset_unit": "one row per decision date",
                "eligible_feature_inputs": [
                    "feature_state_categorical",
                    "feature_value_numeric",
                ],
                "future_encoding_policy": ["train-window-only encoding"],
                "blocked_now": ["model training", "signal creation"],
                "readiness_interpretation": "ready for target/split pre-registration",
            },
            "phase13l_boundary": {
                "allowed_next_step": (
                    "Dataset split and ML target design pre-registration spec only"
                ),
                "forbidden_next_step": (
                    "dataset assembly execution, signal creation, allocation rule, "
                    "strategy backtest, model training, paper-trading deployment, "
                    "candidate promotion, or final-candidate change"
                ),
                "phase13l_may_define_target": True,
                "phase13l_may_define_split_policy": True,
                "phase13l_may_assemble_dataset": False,
                "phase13l_may_train_model": False,
                "phase13l_may_create_signal": False,
                "phase13l_may_run_backtest": False,
                "phase13l_may_deploy_paper_trading": False,
                "phase13l_may_promote_candidate": False,
            },
        },
        "phase13l_dataset_split_target_preregistration_spec": {
            "enabled": True,
            "spec_role": "Dataset split and ML target design pre-registration spec only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13K",
            "proposed_next_phase": "Phase 13M",
            "allow_dataset_assembly_execution": False,
            "allow_target_calculation": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13i_feature_calculation_execution": False,
                "phase13j_feature_panel_quality_leakage_audit": False,
                "phase13k_feature_panel_interpretation_model_readiness": True,
                "phase13l_dataset_split_target_preregistration_spec": True,
                "relative_momentum_allocator": True,
            },
            "phase13k_reports": {
                "source_report_check": str(
                    tmp_path / "phase13k_interpretation_source_report_check.csv"
                ),
                "phase13j_result_check": str(
                    tmp_path / "phase13k_interpretation_phase13j_result_check.csv"
                ),
                "feature_state_distribution": str(
                    tmp_path
                    / "phase13k_interpretation_feature_state_distribution.csv"
                ),
                "feature_availability_summary": str(
                    tmp_path
                    / "phase13k_interpretation_feature_availability_summary.csv"
                ),
                "family_coverage_summary": str(
                    tmp_path / "phase13k_interpretation_family_coverage_summary.csv"
                ),
                "model_readiness_plan": str(
                    tmp_path / "phase13k_interpretation_model_readiness_plan.csv"
                ),
                "phase13l_boundary_check": str(
                    tmp_path / "phase13k_interpretation_phase13l_boundary_check.csv"
                ),
                "scope_boundary_check": str(
                    tmp_path / "phase13k_interpretation_scope_boundary_check.csv"
                ),
                "summary": str(tmp_path / "phase13k_interpretation_summary.csv"),
                "gate_report": str(
                    tmp_path / "phase13k_interpretation_gate_report.csv"
                ),
                "conclusion": str(
                    tmp_path / "phase13k_interpretation_conclusion.csv"
                ),
            },
            "target_design": {
                "primary_target_id": "future_63d_spy_return_state",
                "target_type": "classification",
                "target_calculated_now": False,
            },
            "secondary_target_design": {
                "secondary_target_id": "future_63d_drawdown_risk_state",
                "target_type": "classification",
                "target_calculated_now": False,
            },
            "dataset_design": {
                "dataset_id": "phase13m_ml_feature_dataset_v1",
                "dataset_assembled_now": False,
            },
            "split_design": {
                "initial_training_period": "2006-04-28 to 2016-12-30",
                "validation_period": "2017-01-03 to 2020-12-31",
                "untouched_holdout_period": "2021-01-01 to 2026-05-01",
                "split_calculated_now": False,
            },
            "walk_forward_policy": {
                "allowed_designs": ["anchored expanding training window"],
                "walk_forward_execution_now": False,
                "model_training_now": False,
            },
            "leakage_control_policy": [
                {"control_id": f"MLLC{i}", "control": "control", "required": True}
                for i in range(1, 7)
            ],
            "phase13m_boundary": {
                "allowed_next_step": "ML dataset assembly execution only",
                "forbidden_next_step": (
                    "model training, model selection, signal creation, allocation "
                    "rule, strategy backtest, paper-trading deployment, candidate "
                    "promotion, or final-candidate change"
                ),
                "phase13m_may_assemble_dataset": True,
                "phase13m_may_calculate_registered_targets": True,
                "phase13m_may_train_model": False,
                "phase13m_may_select_model": False,
                "phase13m_may_create_signal": False,
                "phase13m_may_run_backtest": False,
                "phase13m_may_deploy_paper_trading": False,
                "phase13m_may_promote_candidate": False,
            },
        },
    }


def test_phase13k_interpretation_summaries(tmp_path):
    _write_phase13j_reports(tmp_path)
    _write_feature_panel(tmp_path)
    panel = pd.read_csv(tmp_path / "phase13i_feature_panel.csv")

    state_distribution = build_phase13k_feature_state_distribution(panel)
    availability = build_phase13k_feature_availability_summary(panel)

    assert len(state_distribution) == 8
    assert len(availability) == 8
    assert availability["available_ratio"].min() == 1.0


def test_phase13k_and_13l_save_reports(tmp_path):
    _write_phase13j_reports(tmp_path)
    _write_feature_panel(tmp_path)
    config = _config(tmp_path)

    out_k = save_phase13k_feature_panel_interpretation_model_readiness(
        config=config,
        reports_dir=tmp_path,
    )
    out_l = save_phase13l_dataset_split_target_preregistration_spec(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_k["conclusion"].iloc[0]["all_gates_passed"]
    assert out_l["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13k_interpretation_conclusion.csv").exists()
    assert (tmp_path / "phase13l_prereg_conclusion.csv").exists()