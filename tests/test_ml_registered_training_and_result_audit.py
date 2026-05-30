from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.ml_registered_training_and_result_audit import (
    run_phase13u_registered_training,
    save_phase13u_registered_baseline_ml_training,
    save_phase13v_ml_training_result_quality_audit,
)


def _write_phase13t_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13T",
                "verdict": "Completed — ML training readiness/leakage audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13t_readiness_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13t_readiness_gate_report.csv", index=False)

    for name in [
        "phase13s_prereg_dataset_schema_profile.csv",
        "phase13s_prereg_dataset_requirement_check.csv",
        "phase13s_prereg_target_policy.csv",
        "phase13s_prereg_model_family_registry.csv",
        "phase13s_prereg_preprocessing_policy.csv",
        "phase13s_prereg_split_usage_policy.csv",
        "phase13s_prereg_metric_registry.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _write_dataset(tmp_path: Path):
    rng = np.random.default_rng(42)
    rows = []

    for idx in range(1500):
        if idx < 1000:
            split = "train"
        elif idx < 1250:
            split = "validation"
        else:
            split = "holdout"

        trend = rng.normal()
        macro = rng.normal()
        if trend + macro > 0.75:
            target = "supportive"
        elif trend + macro < -0.75:
            target = "fragile"
        else:
            target = "neutral"

        rows.append(
            {
                "dataset_id": "phase13q_ml_feature_dataset_v1",
                "dataset_label": "multi_factor_technical_macro_dataset_v1",
                "decision_date": pd.Timestamp("2010-01-01")
                + pd.offsets.BDay(idx),
                "split_label": split,
                "future_return_63d": 0.01,
                "future_63d_spy_return_state": target,
                "future_window_max_drawdown_63d": -0.02,
                "future_63d_drawdown_risk_state": "neutral",
                "target_available": True,
                "value__technical_trend_state": trend,
                "value__technical_momentum_state": rng.normal(),
                "value__technical_volatility_state": rng.normal(),
                "value__technical_drawdown_state": rng.normal(),
                "value__macro_short_rate_state": macro,
                "value__macro_yield_curve_state": rng.normal(),
                "value__macro_inflation_state": rng.normal(),
                "value__macro_labour_state": rng.normal(),
                "state__technical_trend_state": "supportive",
                "state__technical_momentum_state": "neutral",
                "state__technical_volatility_state": "neutral",
                "state__technical_drawdown_state": "supportive",
                "state__macro_short_rate_state": "supportive",
                "state__macro_yield_curve_state": "neutral",
                "state__macro_inflation_state": "neutral",
                "state__macro_labour_state": "supportive",
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

    pd.DataFrame(rows).to_csv(
        tmp_path / "phase13q_ml_feature_dataset_v1.csv",
        index=False,
    )


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13s_ml_model_training_preregistration_spec": {"enabled": False},
        "phase13t_ml_training_readiness_leakage_audit": {"enabled": False},
        "phase13u_registered_baseline_ml_training": {
            "enabled": True,
            "execution_role": (
                "Registered baseline ML training execution and train/validation "
                "evaluation only"
            ),
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13T",
            "proposed_next_phase": "Phase 13V",
            "allow_model_training": True,
            "allow_train_only_preprocessing_fit": True,
            "allow_train_validation_evaluation": True,
            "allow_validation_prediction_generation": True,
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13t_conclusion": str(
                    tmp_path / "phase13t_readiness_conclusion.csv"
                ),
                "phase13t_gate_report": str(
                    tmp_path / "phase13t_readiness_gate_report.csv"
                ),
                "dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
                "dataset_schema_profile": str(
                    tmp_path / "phase13s_prereg_dataset_schema_profile.csv"
                ),
                "dataset_requirement_check": str(
                    tmp_path / "phase13s_prereg_dataset_requirement_check.csv"
                ),
                "target_policy": str(tmp_path / "phase13s_prereg_target_policy.csv"),
                "model_family_registry": str(
                    tmp_path / "phase13s_prereg_model_family_registry.csv"
                ),
                "preprocessing_policy": str(
                    tmp_path / "phase13s_prereg_preprocessing_policy.csv"
                ),
                "split_usage_policy": str(
                    tmp_path / "phase13s_prereg_split_usage_policy.csv"
                ),
                "metric_registry": str(tmp_path / "phase13s_prereg_metric_registry.csv"),
            },
            "dataset_policy": {
                "dataset_label_required": "multi_factor_technical_macro_dataset_v1",
                "primary_target_id": "future_63d_spy_return_state",
                "secondary_target_id": "future_63d_drawdown_risk_state",
                "target_available_column": "target_available",
                "train_split_label": "train",
                "validation_split_label": "validation",
                "holdout_split_label": "holdout",
                "allowed_target_classes": ["supportive", "neutral", "fragile"],
                "unavailable_target_class": "unavailable",
                "feature_prefixes": {
                    "numeric": ["value__technical_", "value__macro_"],
                    "categorical": [
                        "state__technical_",
                        "state__macro_",
                        "missingness__technical_",
                        "missingness__macro_",
                    ],
                },
                "forbidden_feature_fragments": [
                    "future_return",
                    "target",
                    "signal",
                    "allocation",
                    "model_prediction",
                    "strategy_return",
                    "backtest_return",
                ],
            },
            "training_policy": {
                "random_state": 42,
                "train_preprocessing_fit_only": True,
                "evaluate_train": True,
                "evaluate_validation": True,
                "generate_validation_predictions": True,
                "generate_holdout_predictions": False,
                "calculate_feature_importance": False,
                "select_model": False,
                "compare_to_dummy_baselines": True,
                "validation_comparison_is_diagnostic_only": True,
            },
            "model_registry": [
                {
                    "model_id": "baseline_majority_class",
                    "model_type": "dummy_most_frequent",
                    "enabled": True,
                    "role": "sanity baseline",
                },
                {
                    "model_id": "baseline_stratified_dummy",
                    "model_type": "dummy_stratified",
                    "enabled": True,
                    "role": "random baseline",
                },
                {
                    "model_id": "multinomial_logistic_regression",
                    "model_type": "logistic_regression",
                    "enabled": True,
                    "role": "linear baseline",
                },
                {
                    "model_id": "random_forest_classifier",
                    "model_type": "random_forest",
                    "enabled": True,
                    "role": "tree baseline",
                    "n_estimators": 20,
                    "max_depth": 3,
                    "min_samples_leaf": 10,
                },
                {
                    "model_id": "hist_gradient_boosting_classifier",
                    "model_type": "hist_gradient_boosting",
                    "enabled": True,
                    "role": "boosted tree baseline",
                    "max_iter": 20,
                    "learning_rate": 0.05,
                    "max_leaf_nodes": 7,
                },
            ],
            "phase13v_boundary": {
                "allowed_next_step": (
                    "ML training result quality and leakage audit only"
                ),
                "forbidden_next_step": (
                    "holdout prediction generation, feature importance, signal "
                    "creation, allocation rule, strategy backtest"
                ),
                "phase13v_may_audit_training_results": True,
                "phase13v_may_generate_holdout_predictions": False,
                "phase13v_may_calculate_feature_importance": False,
                "phase13v_may_create_signal": False,
                "phase13v_may_run_backtest": False,
                "phase13v_may_promote_candidate": False,
            },
        },
        "phase13v_ml_training_result_quality_audit": {
            "enabled": True,
            "audit_role": "ML training result quality and leakage audit only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13U",
            "proposed_next_phase": "Phase 13W",
            "allow_holdout_prediction_generation": False,
            "allow_model_selection": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13s_ml_model_training_preregistration_spec": False,
                "phase13t_ml_training_readiness_leakage_audit": False,
                "phase13u_registered_baseline_ml_training": True,
                "phase13v_ml_training_result_quality_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13u_reports": {
                "source_report_check": str(tmp_path / "phase13u_ml_source_report_check.csv"),
                "phase13t_result_check": str(tmp_path / "phase13u_ml_phase13t_result_check.csv"),
                "dataset_profile": str(tmp_path / "phase13u_ml_dataset_profile.csv"),
                "feature_matrix_profile": str(tmp_path / "phase13u_ml_feature_matrix_profile.csv"),
                "model_registry_execution_report": str(tmp_path / "phase13u_ml_model_registry_execution_report.csv"),
                "preprocessing_pipeline_report": str(tmp_path / "phase13u_ml_preprocessing_pipeline_report.csv"),
                "train_validation_metric_report": str(tmp_path / "phase13u_ml_train_validation_metric_report.csv"),
                "confusion_matrix_report": str(tmp_path / "phase13u_ml_confusion_matrix_report.csv"),
                "calibration_report": str(tmp_path / "phase13u_ml_calibration_report.csv"),
                "class_support_report": str(tmp_path / "phase13u_ml_class_support_report.csv"),
                "baseline_comparison_report": str(tmp_path / "phase13u_ml_baseline_comparison_report.csv"),
                "validation_predictions": str(tmp_path / "phase13u_ml_validation_predictions.csv"),
                "forbidden_output_check": str(tmp_path / "phase13u_ml_forbidden_output_check.csv"),
                "phase13v_boundary_check": str(tmp_path / "phase13u_ml_phase13v_boundary_check.csv"),
                "scope_boundary_check": str(tmp_path / "phase13u_ml_scope_boundary_check.csv"),
                "summary": str(tmp_path / "phase13u_ml_summary.csv"),
                "gate_report": str(tmp_path / "phase13u_ml_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13u_ml_conclusion.csv"),
            },
            "quality_thresholds": {
                "min_trained_models": 5,
                "min_metric_rows": 10,
                "min_confusion_matrix_rows": 45,
                "min_class_support_rows": 6,
                "forbidden_output_paths": [
                    str(tmp_path / "phase13u_feature_importance.csv"),
                    str(tmp_path / "phase13u_signal_report.csv"),
                    str(tmp_path / "phase13u_strategy_backtest.csv"),
                    str(tmp_path / "phase13u_holdout_predictions.csv"),
                ],
            },
            "phase13w_boundary": {
                "allowed_next_step": (
                    "ML validation result interpretation and model-continuation "
                    "decision only"
                ),
                "forbidden_next_step": (
                    "holdout prediction generation, signal creation, strategy backtest"
                ),
                "phase13w_may_interpret_validation_results": True,
                "phase13w_may_generate_holdout_predictions": False,
                "phase13w_may_create_signal": False,
                "phase13w_may_run_backtest": False,
                "phase13w_may_promote_candidate": False,
            },
        },
    }


def test_phase13u_trains_registered_models_without_holdout(tmp_path):
    _write_phase13t_reports(tmp_path)
    _write_dataset(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase13u_registered_baseline_ml_training"]
    dataset = pd.read_csv(tmp_path / "phase13q_ml_feature_dataset_v1.csv")

    outputs = run_phase13u_registered_training(
        dataset=dataset,
        phase_config=phase_config,
    )

    execution = outputs["model_registry_execution_report"]
    predictions = outputs["validation_predictions"]

    assert execution["trained"].all()
    assert not execution["holdout_predictions_generated"].any()
    assert set(predictions["split_label"]) == {"validation"}


def test_phase13u_and_13v_save_reports(tmp_path):
    _write_phase13t_reports(tmp_path)
    _write_dataset(tmp_path)
    config = _config(tmp_path)

    out_u = save_phase13u_registered_baseline_ml_training(
        config=config,
        reports_dir=tmp_path,
    )
    out_v = save_phase13v_ml_training_result_quality_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_u["conclusion"].iloc[0]["all_gates_passed"]
    assert out_v["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13u_ml_validation_predictions.csv").exists()
    assert (tmp_path / "phase13v_quality_conclusion.csv").exists()