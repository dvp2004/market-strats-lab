from pathlib import Path

import pandas as pd

from market_strats.analysis.redesigned_model_training_bundle import (
    save_phase13ao_registered_redesigned_model_training,
    save_phase13ap_redesigned_model_training_result_audit,
    save_phase13aq_validation_to_holdout_decision,
)


def _write_prior_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13AN",
                "verdict": "Completed — redesigned model run readiness audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13an_model_readiness_conclusion.csv", index=False)

    pd.DataFrame(
        [{"gate": "dummy", "passed": True, "result": "Passed"}]
    ).to_csv(tmp_path / "phase13an_model_readiness_gate_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "candidate_target_variant": "return_drawdown_63d_composite",
                "model_selected": False,
                "signal_permission": False,
                "backtest_permission": False,
            }
        ]
    ).to_csv(
        tmp_path / "phase13ak_target_decision_candidate_target_decision_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "run_id": "phase13ao_redesigned_target_model_run_v1",
                "candidate_target_variant": "return_drawdown_63d_composite",
                "holdout_locked": True,
            }
        ]
    ).to_csv(tmp_path / "phase13am_model_prereg_model_run_spec.csv", index=False)

    pd.DataFrame(
        [
            {
                "policy_key": "numeric_feature_prefixes",
                "policy_value": "value__technical_; value__macro_",
            },
            {
                "policy_key": "categorical_feature_prefixes",
                "policy_value": (
                    "state__technical_; state__macro_; "
                    "missingness__technical_; missingness__macro_"
                ),
            },
            {
                "policy_key": "forbidden_feature_fragments",
                "policy_value": (
                    "future_return; future_window; target; signal; allocation; "
                    "model_prediction; strategy_return; backtest_return; paper_trade; "
                    "feature_importance"
                ),
            },
        ]
    ).to_csv(tmp_path / "phase13am_model_prereg_feature_policy.csv", index=False)

    pd.DataFrame(
        [{"policy_key": "fit_preprocessing_on_train_only", "policy_value": True}]
    ).to_csv(tmp_path / "phase13am_model_prereg_preprocessing_policy.csv", index=False)

    pd.DataFrame(
        [
            {"model_id": "baseline_majority_class", "family": "dummy", "strategy": "most_frequent"},
            {"model_id": "baseline_stratified_dummy", "family": "dummy", "strategy": "stratified"},
            {
                "model_id": "redesigned_logistic_balanced",
                "family": "logistic_regression",
                "class_weight": "balanced",
                "C": 0.5,
                "max_iter": 1000,
            },
            {
                "model_id": "redesigned_random_forest_regularised",
                "family": "random_forest",
                "class_weight": "balanced",
                "n_estimators": 30,
                "max_depth": 4,
                "min_samples_leaf": 10,
                "random_state": 42,
            },
            {
                "model_id": "redesigned_histgb_constrained",
                "family": "hist_gradient_boosting",
                "max_iter": 30,
                "learning_rate": 0.05,
                "max_leaf_nodes": 7,
                "l2_regularization": 1.0,
                "random_state": 42,
            },
        ]
    ).to_csv(
        tmp_path / "phase13am_model_prereg_registered_model_families.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {"policy_key": "min_validation_balanced_accuracy_delta_vs_majority", "policy_value": 0.01},
            {"policy_key": "min_validation_macro_f1_delta_vs_majority", "policy_value": 0.01},
            {"policy_key": "min_validation_fragile_recall", "policy_value": 0.10},
            {"policy_key": "max_balanced_accuracy_overfit_gap", "policy_value": 0.50},
            {"policy_key": "max_macro_f1_overfit_gap", "policy_value": 0.50},
            {"policy_key": "require_real_model_beats_stratified_on_balanced_accuracy", "policy_value": True},
        ]
    ).to_csv(
        tmp_path / "phase13am_model_prereg_validation_success_gates.csv",
        index=False,
    )


def _write_dataset_and_assignment(tmp_path: Path):
    rows = []
    assignment = []

    for i in range(900):
        split = "train" if i < 650 else "validation"
        x1 = (i % 10) / 10
        x2 = (i % 7) / 7

        if x1 < 0.25:
            target = "fragile"
        elif x1 > 0.65:
            target = "supportive"
        else:
            target = "neutral"

        rows.append(
            {
                "decision_date": f"2020-01-{(i % 28) + 1:02d}",
                "split_label": split,
                "value__technical_trend_state": x1,
                "value__technical_momentum_state": x2,
                "value__technical_volatility_state": x1 * 0.5,
                "value__technical_drawdown_state": x2 * 0.5,
                "value__macro_short_rate_state": x1 + x2,
                "value__macro_yield_curve_state": x1 - x2,
                "value__macro_inflation_state": x2,
                "value__macro_labour_state": x1,
                "state__technical_trend_state": "low" if x1 < 0.25 else "high",
                "state__technical_momentum_state": "neutral",
                "state__technical_volatility_state": "neutral",
                "state__technical_drawdown_state": "neutral",
                "state__macro_short_rate_state": "neutral",
                "state__macro_yield_curve_state": "neutral",
                "state__macro_inflation_state": "neutral",
                "state__macro_labour_state": "neutral",
                "missingness__technical_trend_state": "available",
                "missingness__technical_momentum_state": "available",
                "missingness__technical_volatility_state": "available",
                "missingness__technical_drawdown_state": "available",
                "missingness__macro_short_rate_state": "available",
                "missingness__macro_yield_curve_state": "available",
                "missingness__macro_inflation_state": "available",
                "missingness__macro_labour_state": "available",
            }
        )
        assignment.append(
            {
                "decision_date": f"2020-01-{(i % 28) + 1:02d}",
                "split_label": split,
                "return_drawdown_63d_composite": target,
            }
        )

    pd.DataFrame(rows).to_csv(tmp_path / "phase13q_ml_feature_dataset_v1.csv", index=False)
    pd.DataFrame(assignment).to_csv(
        tmp_path / "phase13ai_redesign_panel_target_assignment_panel.csv",
        index=False,
    )


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13ak_target_feature_redesign_interpretation_decision": {"enabled": False},
        "phase13al_target_feature_redesign_checkpoint_audit": {"enabled": False},
        "phase13am_redesigned_model_run_preregistration": {"enabled": False},
        "phase13an_redesigned_model_run_readiness_audit": {"enabled": False},
        "phase13ao_registered_redesigned_model_training": {
            "enabled": True,
            "execution_role": "Registered redesigned model training on train/validation only",
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13an_conclusion": str(tmp_path / "phase13an_model_readiness_conclusion.csv"),
                "phase13an_gate_report": str(tmp_path / "phase13an_model_readiness_gate_report.csv"),
                "model_run_spec": str(tmp_path / "phase13am_model_prereg_model_run_spec.csv"),
                "feature_policy": str(tmp_path / "phase13am_model_prereg_feature_policy.csv"),
                "preprocessing_policy": str(tmp_path / "phase13am_model_prereg_preprocessing_policy.csv"),
                "registered_model_families": str(tmp_path / "phase13am_model_prereg_registered_model_families.csv"),
                "validation_success_gates": str(tmp_path / "phase13am_model_prereg_validation_success_gates.csv"),
                "candidate_target_decision_report": str(
                    tmp_path / "phase13ak_target_decision_candidate_target_decision_report.csv"
                ),
                "target_assignment_panel": str(
                    tmp_path / "phase13ai_redesign_panel_target_assignment_panel.csv"
                ),
                "dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
            },
            "model_training_policy": {
                "allowed_target_classes": ["supportive", "neutral", "fragile"],
            },
            "phase13ap_boundary": {
                "allowed_next_step": "Redesigned model training result and leakage audit only",
                "forbidden_next_step": "holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
            "phase13aq_boundary": {
                "allowed_future_step": "Validation-to-holdout decision only",
                "forbidden_future_step": "holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
        "phase13ap_redesigned_model_training_result_audit": {
            "enabled": True,
            "audit_role": "Redesigned model training result and leakage audit only",
            "allow_model_training": False,
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13ak_target_feature_redesign_interpretation_decision": False,
                "phase13al_target_feature_redesign_checkpoint_audit": False,
                "phase13am_redesigned_model_run_preregistration": False,
                "phase13an_redesigned_model_run_readiness_audit": False,
                "phase13ao_registered_redesigned_model_training": True,
                "phase13ap_redesigned_model_training_result_audit": True,
                "phase13aq_validation_to_holdout_decision": True,
                "relative_momentum_allocator": True,
            },
            "phase13ao_reports": {
                "conclusion": str(tmp_path / "phase13ao_model_training_conclusion.csv"),
                "gate_report": str(tmp_path / "phase13ao_model_training_gate_report.csv"),
                "model_execution_report": str(tmp_path / "phase13ao_model_training_model_execution_report.csv"),
                "metric_report": str(tmp_path / "phase13ao_model_training_metric_report.csv"),
                "baseline_comparison_report": str(tmp_path / "phase13ao_model_training_baseline_comparison_report.csv"),
                "confusion_matrix_report": str(tmp_path / "phase13ao_model_training_confusion_matrix_report.csv"),
                "class_recall_report": str(tmp_path / "phase13ao_model_training_class_recall_report.csv"),
                "calibration_report": str(tmp_path / "phase13ao_model_training_calibration_report.csv"),
                "overfit_report": str(tmp_path / "phase13ao_model_training_overfit_report.csv"),
                "success_report": str(tmp_path / "phase13ao_model_training_success_report.csv"),
                "validation_predictions": str(tmp_path / "phase13ao_model_training_validation_predictions.csv"),
            },
            "forbidden_output_paths": [
                str(tmp_path / "phase13ao_model_training_holdout_predictions.csv"),
                str(tmp_path / "phase13ao_model_training_feature_importance.csv"),
                str(tmp_path / "phase13ao_model_training_signal_report.csv"),
            ],
            "phase13aq_boundary": {
                "allowed_next_step": "Validation-to-holdout decision only",
                "forbidden_next_step": "holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
        "phase13aq_validation_to_holdout_decision": {
            "enabled": True,
            "decision_role": "Validation-to-holdout decision only",
            "allow_model_training": False,
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13ap_conclusion": str(tmp_path / "phase13ap_model_audit_conclusion.csv"),
                "phase13ap_gate_report": str(tmp_path / "phase13ap_model_audit_gate_report.csv"),
                "metric_report": str(tmp_path / "phase13ao_model_training_metric_report.csv"),
                "baseline_comparison_report": str(tmp_path / "phase13ao_model_training_baseline_comparison_report.csv"),
                "class_recall_report": str(tmp_path / "phase13ao_model_training_class_recall_report.csv"),
                "overfit_report": str(tmp_path / "phase13ao_model_training_overfit_report.csv"),
                "success_report": str(tmp_path / "phase13ao_model_training_success_report.csv"),
            },
            "decision_policy": {
                "if_any_real_model_passes_all_validation_gates": "justify_holdout_preregistration",
                "if_no_real_model_passes_all_validation_gates": "do_not_proceed_to_holdout",
            },
            "phase13ar_boundary": {
                "allowed_next_step_if_passed": "Holdout evaluation pre-registration only",
                "allowed_next_step_if_failed": "Kill, pause, or redesign branch decision only",
                "forbidden_next_step": "holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
    }


def test_phase13ao_to_13aq_redesigned_model_training_bundle(tmp_path):
    _write_prior_reports(tmp_path)
    _write_dataset_and_assignment(tmp_path)
    config = _config(tmp_path)

    out_ao = save_phase13ao_registered_redesigned_model_training(
        config=config,
        reports_dir=tmp_path,
    )
    out_ap = save_phase13ap_redesigned_model_training_result_audit(
        config=config,
        reports_dir=tmp_path,
    )
    out_aq = save_phase13aq_validation_to_holdout_decision(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_ao["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_ap["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_aq["conclusion"].iloc[0]["all_gates_passed"])

    predictions = out_ao["validation_predictions"]
    assert set(predictions["split_label"].astype(str)) == {"validation"}
    assert not predictions["holdout_prediction"].map(bool).any()

    decision = out_aq["decision_report"].iloc[0]
    assert not bool(decision["model_selected"])
    assert not bool(decision["signal_permission"])