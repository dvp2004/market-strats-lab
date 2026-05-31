from pathlib import Path

import pandas as pd

from market_strats.analysis.commercial_route_decision_bundle import (
    save_phase13av_ml_branch_commercial_decision,
    save_phase13aw_paper_trading_candidate_route_selection,
)


def _write_phase13aq_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13AQ",
                "verdict": "Completed — validation-to-holdout decision passed",
                "all_gates_passed": True,
                "holdout_preregistration_justified": False,
            }
        ]
    ).to_csv(tmp_path / "phase13aq_holdout_decision_conclusion.csv", index=False)

    pd.DataFrame(
        [{"gate": "dummy", "passed": True, "result": "Passed"}]
    ).to_csv(tmp_path / "phase13aq_holdout_decision_gate_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "decision": "do_not_proceed_to_holdout",
                "decision_reason": "No real model passed all pre-registered validation gates.",
                "diagnostic_leading_model": "redesigned_random_forest_regularised",
                "holdout_preregistration_justified": False,
                "holdout_predictions_generated": False,
                "model_selected": False,
                "feature_importance_permission": False,
                "signal_permission": False,
                "backtest_permission": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    ).to_csv(tmp_path / "phase13aq_holdout_decision_decision_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "model_id": "redesigned_random_forest_regularised",
                "family": "random_forest",
                "is_real_model": True,
                "validation_balanced_accuracy": 0.3942,
                "validation_macro_f1": 0.3517,
                "validation_fragile_recall": 0.0090,
                "passes_all_validation_gates": False,
            },
            {
                "model_id": "redesigned_logistic_balanced",
                "family": "logistic_regression",
                "is_real_model": True,
                "validation_balanced_accuracy": 0.3516,
                "validation_macro_f1": 0.2735,
                "validation_fragile_recall": 0.0045,
                "passes_all_validation_gates": False,
            },
        ]
    ).to_csv(tmp_path / "phase13ao_model_training_success_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "model_id": "redesigned_random_forest_regularised",
                "validation_balanced_accuracy": 0.3942,
            }
        ]
    ).to_csv(tmp_path / "phase13aq_holdout_decision_validation_ranking_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "model_id": "redesigned_random_forest_regularised",
                "split_label": "validation",
                "balanced_accuracy": 0.3942,
            }
        ]
    ).to_csv(tmp_path / "phase13ao_model_training_metric_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "model_id": "redesigned_random_forest_regularised",
                "split_label": "validation",
                "class_label": "fragile",
                "recall": 0.0090,
            }
        ]
    ).to_csv(tmp_path / "phase13ao_model_training_class_recall_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "model_id": "redesigned_random_forest_regularised",
                "balanced_accuracy_gap": 0.3842,
                "macro_f1_gap": 0.4246,
            }
        ]
    ).to_csv(tmp_path / "phase13ao_model_training_overfit_report.csv", index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13ao_registered_redesigned_model_training": {"enabled": False},
        "phase13ap_redesigned_model_training_result_audit": {"enabled": False},
        "phase13aq_validation_to_holdout_decision": {"enabled": False},
        "phase13av_ml_branch_commercial_decision": {
            "enabled": True,
            "decision_role": "ML branch commercial kill-or-pivot decision only",
            "implementation_classification": "B - protects from wasting time on a failed ML candidate",
            "allow_model_training": False,
            "allow_model_repair_execution": False,
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_visual_backtest_generation": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13aq_conclusion": str(tmp_path / "phase13aq_holdout_decision_conclusion.csv"),
                "phase13aq_gate_report": str(tmp_path / "phase13aq_holdout_decision_gate_report.csv"),
                "phase13aq_decision_report": str(tmp_path / "phase13aq_holdout_decision_decision_report.csv"),
                "phase13aq_validation_ranking_report": str(tmp_path / "phase13aq_holdout_decision_validation_ranking_report.csv"),
                "phase13ao_metric_report": str(tmp_path / "phase13ao_model_training_metric_report.csv"),
                "phase13ao_class_recall_report": str(tmp_path / "phase13ao_model_training_class_recall_report.csv"),
                "phase13ao_overfit_report": str(tmp_path / "phase13ao_model_training_overfit_report.csv"),
                "phase13ao_success_report": str(tmp_path / "phase13ao_model_training_success_report.csv"),
            },
            "commercial_thresholds": {
                "min_fragile_recall_for_live_path": 0.20,
                "max_overfit_gap_for_live_path": 0.30,
                "min_validation_balanced_accuracy_for_continued_ml": 0.45,
                "allow_future_ml_only_with_new_feature_families": True,
            },
            "branch_policy": {
                "ml_v1_status_if_holdout_not_justified": "pause_or_kill_current_technical_macro_ml_v1",
                "minor_model_tuning_allowed_after_failure": False,
                "route_selection_required": True,
                "blocked_next_steps": [
                    "technical_macro_ml_minor_repair",
                    "technical_macro_ml_direct_holdout",
                    "technical_macro_ml_signal_mapping",
                    "technical_macro_ml_backtest",
                    "multi_asset_expansion_before_spy_candidate_decision",
                ],
            },
            "phase13aw_boundary": {
                "allowed_next_step": "Paper-trading candidate route selection only",
                "forbidden_next_step": "model training, holdout prediction generation, feature importance, signal creation, strategy backtest, paper-trading deployment",
            },
        },
        "phase13aw_paper_trading_candidate_route_selection": {
            "enabled": True,
            "decision_role": "Paper-trading candidate route selection only",
            "implementation_classification": "A - moves towards choosing the fastest paper-trading route",
            "allow_model_training": False,
            "allow_model_repair_execution": False,
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_visual_backtest_generation": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13ao_registered_redesigned_model_training": False,
                "phase13ap_redesigned_model_training_result_audit": False,
                "phase13aq_validation_to_holdout_decision": False,
                "phase13av_ml_branch_commercial_decision": True,
                "phase13aw_paper_trading_candidate_route_selection": True,
                "relative_momentum_allocator": True,
            },
            "source_reports": {
                "phase13av_conclusion": str(tmp_path / "phase13av_commercial_decision_conclusion.csv"),
                "phase13av_gate_report": str(tmp_path / "phase13av_commercial_decision_gate_report.csv"),
                "phase13av_commercial_decision_report": str(tmp_path / "phase13av_commercial_decision_commercial_decision_report.csv"),
                "phase13av_blocked_next_steps_report": str(tmp_path / "phase13av_commercial_decision_blocked_next_steps_report.csv"),
            },
            "route_registry": [
                {
                    "route_id": "route_1_pause_ml_move_validated_overlay_paper_prep",
                    "route_label": "Pause ML and prepare validated overlay.",
                    "classification": "A/B",
                    "paper_trading_speed_rank": 2,
                    "validation_strength_rank": 1,
                    "scope_risk_rank": 1,
                    "requires_new_data": False,
                    "requires_new_model_training": False,
                    "uses_existing_validated_non_ml_candidate": True,
                    "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
                    "route_status": "allowed",
                },
                {
                    "route_id": "route_2_bounded_ml_redesign_only_with_new_feature_families",
                    "route_label": "Bounded ML redesign only with new feature families.",
                    "classification": "B",
                    "paper_trading_speed_rank": 3,
                    "validation_strength_rank": 3,
                    "scope_risk_rank": 3,
                    "requires_new_data": True,
                    "requires_new_model_training": True,
                    "uses_existing_validated_non_ml_candidate": False,
                    "candidate_system_id": "none_currently",
                    "route_status": "defer",
                },
                {
                    "route_id": "route_3_non_ml_overlay_visual_backtest_paper_readiness",
                    "route_label": "Move best non-ML overlay into visual backtest and paper-readiness path.",
                    "classification": "A",
                    "paper_trading_speed_rank": 1,
                    "validation_strength_rank": 1,
                    "scope_risk_rank": 1,
                    "requires_new_data": False,
                    "requires_new_model_training": False,
                    "uses_existing_validated_non_ml_candidate": True,
                    "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
                    "route_status": "preferred",
                },
            ],
            "route_selection_policy": {
                "primary_selection_rule": "prefer fastest allowed route that uses existing validated non-ML candidate and avoids new ML training",
                "selected_route_id": "route_3_non_ml_overlay_visual_backtest_paper_readiness",
                "backup_route_id": "route_1_pause_ml_move_validated_overlay_paper_prep",
                "deferred_route_id": "route_2_bounded_ml_redesign_only_with_new_feature_families",
                "next_phase_if_selected": "Phase 14A - Non-ML paper-trading candidate visual backtest pre-registration",
            },
            "phase14a_boundary": {
                "allowed_next_step": "Non-ML paper-trading candidate visual backtest and signal-mapping pre-registration only",
                "forbidden_next_step": "live trading, real-money deployment, unregistered model training, holdout prediction generation, feature importance, candidate promotion",
            },
        },
    }


def test_phase13av_to_13aw_commercial_route_decision(tmp_path):
    _write_phase13aq_reports(tmp_path)
    config = _config(tmp_path)

    out_av = save_phase13av_ml_branch_commercial_decision(
        config=config,
        reports_dir=tmp_path,
    )
    out_aw = save_phase13aw_paper_trading_candidate_route_selection(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_av["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_aw["conclusion"].iloc[0]["all_gates_passed"])

    commercial = out_av["commercial_decision_report"].iloc[0]
    assert commercial["decision"] == "pause_current_technical_macro_ml_v1"
    assert not bool(commercial["minor_model_tuning_allowed"])

    selection = out_aw["route_selection_report"].iloc[0]
    assert selection["selected_route_id"] == "route_3_non_ml_overlay_visual_backtest_paper_readiness"
    assert not bool(selection["model_training_permission"])
    assert not bool(selection["paper_trading_permission"])