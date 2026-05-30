from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.ml_diagnostic_repair_bundle import (
    save_phase13aa_registered_ml_diagnostic_repair_execution,
    save_phase13ab_ml_diagnostic_repair_result_audit,
    save_phase13y_ml_diagnostic_repair_preregistration,
    save_phase13z_ml_diagnostic_repair_readiness_audit,
)


def _write_prior_reports(tmp_path: Path):
    for name, phase, verdict in [
        ("phase13x_checkpoint_conclusion.csv", "Phase 13X", "Completed — ML branch checkpoint audit passed"),
        ("phase13x_checkpoint_gate_report.csv", "Phase 13X", "Passed"),
    ]:
        pd.DataFrame([{"phase": phase, "verdict": verdict, "all_gates_passed": True, "passed": True}]).to_csv(tmp_path / name, index=False)

    pd.DataFrame(
        [
            {
                "decision": "continue_only_after_model_diagnostic_repair",
                "diagnostic_leading_model": "random_forest_classifier",
                "holdout_preregistration_justified": False,
                "model_selected": False,
                "signal_permission": False,
                "backtest_permission": False,
                "candidate_promotion": False,
            }
        ]
    ).to_csv(tmp_path / "phase13w_interpretation_continuation_decision_report.csv", index=False)

    for name in [
        "phase13w_interpretation_overfit_diagnostic_report.csv",
        "phase13w_interpretation_class_recall_report.csv",
        "phase13w_interpretation_dummy_comparison_report.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _write_dataset(tmp_path: Path):
    rng = np.random.default_rng(7)
    rows = []
    for i in range(900):
        split = "train" if i < 600 else "validation"
        x1 = rng.normal()
        x2 = rng.normal()
        score = x1 + x2
        target = "supportive" if score > 0.7 else "fragile" if score < -1.0 else "neutral"
        rows.append(
            {
                "dataset_label": "multi_factor_technical_macro_dataset_v1",
                "decision_date": pd.Timestamp("2010-01-01") + pd.offsets.BDay(i),
                "split_label": split,
                "future_63d_spy_return_state": target,
                "target_available": True,
                "value__technical_trend_state": x1,
                "value__technical_momentum_state": rng.normal(),
                "value__technical_volatility_state": rng.normal(),
                "value__technical_drawdown_state": rng.normal(),
                "value__macro_short_rate_state": x2,
                "value__macro_yield_curve_state": rng.normal(),
                "value__macro_inflation_state": rng.normal(),
                "value__macro_labour_state": rng.normal(),
                "state__technical_trend_state": "neutral",
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
    pd.DataFrame(rows).to_csv(tmp_path / "phase13q_ml_feature_dataset_v1.csv", index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13w_ml_validation_interpretation_decision": {"enabled": False},
        "phase13x_ml_branch_checkpoint_audit": {"enabled": False},
        "phase13y_ml_diagnostic_repair_preregistration": {
            "enabled": True,
            "spec_role": "ML diagnostic repair pre-registration spec only",
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13x_conclusion": str(tmp_path / "phase13x_checkpoint_conclusion.csv"),
                "phase13x_gate_report": str(tmp_path / "phase13x_checkpoint_gate_report.csv"),
                "continuation_decision_report": str(tmp_path / "phase13w_interpretation_continuation_decision_report.csv"),
                "overfit_diagnostic_report": str(tmp_path / "phase13w_interpretation_overfit_diagnostic_report.csv"),
                "class_recall_report": str(tmp_path / "phase13w_interpretation_class_recall_report.csv"),
                "baseline_comparison_report": str(tmp_path / "phase13w_interpretation_dummy_comparison_report.csv"),
                "dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
            },
            "repair_targets": [{"target_id": "a"}, {"target_id": "b"}, {"target_id": "c"}],
            "registered_repair_hypotheses": [
                {"repair_id": "rf_repair_shallow_regularised", "base_model_family": "random_forest", "allowed": True, "max_depth": 2, "min_samples_leaf": 20, "n_estimators": 20},
                {"repair_id": "rf_repair_fragile_weighted", "base_model_family": "random_forest", "allowed": True, "max_depth": 3, "min_samples_leaf": 20, "n_estimators": 20},
                {"repair_id": "logistic_repair_high_regularisation", "base_model_family": "logistic_regression", "allowed": True, "C": 0.25, "max_iter": 500},
                {"repair_id": "histgb_repair_shallow_l2", "base_model_family": "hist_gradient_boosting", "allowed": True, "max_iter": 20, "learning_rate": 0.03, "max_leaf_nodes": 7, "l2_regularization": 1.0},
            ],
            "repair_success_gates": {
                "min_validation_fragile_recall": 0.20,
                "min_delta_balanced_accuracy_vs_majority": 0.05,
                "max_balanced_accuracy_overfit_gap": 0.30,
            },
            "phase13z_boundary": {"allowed_next_step": "ML diagnostic repair readiness and boundary audit only"},
            "phase13aa_boundary": {"allowed_future_step": "Registered ML diagnostic repair execution on train/validation only"},
        },
        "phase13z_ml_diagnostic_repair_readiness_audit": {
            "enabled": True,
            "audit_role": "ML diagnostic repair readiness and boundary audit only",
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13w_ml_validation_interpretation_decision": False,
                "phase13x_ml_branch_checkpoint_audit": False,
                "phase13y_ml_diagnostic_repair_preregistration": True,
                "phase13z_ml_diagnostic_repair_readiness_audit": True,
                "phase13aa_registered_ml_diagnostic_repair_execution": True,
                "phase13ab_ml_diagnostic_repair_result_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13y_reports": {
                "conclusion": str(tmp_path / "phase13y_repair_prereg_conclusion.csv"),
                "gate_report": str(tmp_path / "phase13y_repair_prereg_gate_report.csv"),
                "repair_hypothesis_registry": str(tmp_path / "phase13y_repair_prereg_hypothesis_registry.csv"),
                "repair_success_gate_registry": str(tmp_path / "phase13y_repair_prereg_success_gate_registry.csv"),
            },
        },
        "phase13aa_registered_ml_diagnostic_repair_execution": {
            "enabled": True,
            "execution_role": "Registered ML diagnostic repair execution on train/validation only",
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13z_conclusion": str(tmp_path / "phase13z_repair_readiness_conclusion.csv"),
                "phase13z_gate_report": str(tmp_path / "phase13z_repair_readiness_gate_report.csv"),
                "dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
            },
            "dataset_policy": {
                "primary_target_id": "future_63d_spy_return_state",
                "target_available_column": "target_available",
                "train_split_label": "train",
                "validation_split_label": "validation",
                "allowed_target_classes": ["supportive", "neutral", "fragile"],
                "unavailable_target_class": "unavailable",
                "feature_prefixes": {
                    "numeric": ["value__technical_", "value__macro_"],
                    "categorical": ["state__technical_", "state__macro_", "missingness__technical_", "missingness__macro_"],
                },
                "forbidden_feature_fragments": ["future_return", "target", "signal", "allocation", "model_prediction", "strategy_return", "backtest_return"],
            },
        },
        "phase13ab_ml_diagnostic_repair_result_audit": {
            "enabled": True,
            "audit_role": "ML diagnostic repair result quality and leakage audit only",
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "phase13aa_reports": {
                "conclusion": str(tmp_path / "phase13aa_repair_execution_conclusion.csv"),
                "gate_report": str(tmp_path / "phase13aa_repair_execution_gate_report.csv"),
                "repair_metric_report": str(tmp_path / "phase13aa_repair_execution_metric_report.csv"),
                "repair_class_recall_report": str(tmp_path / "phase13aa_repair_execution_class_recall_report.csv"),
                "repair_overfit_report": str(tmp_path / "phase13aa_repair_execution_overfit_report.csv"),
                "repair_success_report": str(tmp_path / "phase13aa_repair_execution_success_report.csv"),
                "validation_predictions": str(tmp_path / "phase13aa_repair_execution_validation_predictions.csv"),
            },
        },
    }


def test_phase13y_to_13ab_repair_bundle(tmp_path):
    _write_prior_reports(tmp_path)
    _write_dataset(tmp_path)
    config = _config(tmp_path)

    out_y = save_phase13y_ml_diagnostic_repair_preregistration(config=config, reports_dir=tmp_path)
    out_z = save_phase13z_ml_diagnostic_repair_readiness_audit(config=config, reports_dir=tmp_path)
    out_aa = save_phase13aa_registered_ml_diagnostic_repair_execution(config=config, reports_dir=tmp_path)
    out_ab = save_phase13ab_ml_diagnostic_repair_result_audit(config=config, reports_dir=tmp_path)

    assert out_y["conclusion"].iloc[0]["all_gates_passed"]
    assert out_z["conclusion"].iloc[0]["all_gates_passed"]
    assert out_aa["conclusion"].iloc[0]["all_gates_passed"]
    assert out_ab["conclusion"].iloc[0]["all_gates_passed"]