from pathlib import Path

import pandas as pd

from market_strats.analysis.ml_training_prereg_and_readiness_audit import (
    build_phase13s_dataset_requirement_check,
    build_phase13s_dataset_schema_profile,
    save_phase13s_ml_model_training_preregistration_spec,
    save_phase13t_ml_training_readiness_leakage_audit,
)


def _write_phase13r_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13R",
                "verdict": "Completed — repaired macro dataset quality audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13r_quality_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13r_quality_gate_report.csv", index=False)

    for name in [
        "phase13q_repair_macro_availability_report.csv",
        "phase13q_repair_split_summary.csv",
        "phase13q_repair_target_summary.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _write_repaired_dataset(tmp_path: Path):
    rows = []
    for idx in range(1500):
        if idx < 1000:
            split = "train"
        elif idx < 1250:
            split = "validation"
        else:
            split = "holdout"

        rows.append(
            {
                "dataset_id": "phase13q_ml_feature_dataset_v1",
                "dataset_label": "multi_factor_technical_macro_dataset_v1",
                "macro_repair_passed": True,
                "decision_date": pd.Timestamp("2010-01-01")
                + pd.offsets.BDay(idx),
                "split_label": split,
                "future_return_63d": 0.01,
                "future_63d_spy_return_state": "neutral",
                "future_window_max_drawdown_63d": -0.02,
                "future_63d_drawdown_risk_state": "neutral",
                "target_available": True,
                "value__technical_trend_state": 1.0,
                "value__technical_momentum_state": 1.0,
                "value__technical_volatility_state": 1.0,
                "value__technical_drawdown_state": 1.0,
                "value__macro_short_rate_state": 1.0,
                "value__macro_yield_curve_state": 1.0,
                "value__macro_inflation_state": 1.0,
                "value__macro_labour_state": 1.0,
                "state__technical_trend_state": "supportive",
                "state__macro_short_rate_state": "supportive",
                "missingness__technical_trend_state": "available",
                "missingness__macro_short_rate_state": "available",
            }
        )

    pd.DataFrame(rows).to_csv(
        tmp_path / "phase13q_ml_feature_dataset_v1.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "dataset_id": "phase13q_ml_feature_dataset_v1",
                "dataset_label": "multi_factor_technical_macro_dataset_v1",
                "rows": 1500,
                "value_feature_columns": 8,
                "macro_value_feature_columns": 4,
                "state_feature_columns": 2,
                "missingness_feature_columns": 2,
                "macro_available_ratio": 0.97,
                "macro_repair_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13q_repair_dataset_metadata.csv", index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13q_macro_long_to_wide_repair_execution": {"enabled": False},
        "phase13r_repaired_macro_dataset_quality_audit": {"enabled": False},
        "phase13s_ml_model_training_preregistration_spec": {
            "enabled": True,
            "spec_role": (
                "ML model training pre-registration and baseline model "
                "design spec only"
            ),
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13R",
            "proposed_next_phase": "Phase 13T",
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13r_conclusion": str(
                    tmp_path / "phase13r_quality_conclusion.csv"
                ),
                "phase13r_gate_report": str(
                    tmp_path / "phase13r_quality_gate_report.csv"
                ),
                "repaired_dataset": str(
                    tmp_path / "phase13q_ml_feature_dataset_v1.csv"
                ),
                "dataset_metadata": str(
                    tmp_path / "phase13q_repair_dataset_metadata.csv"
                ),
                "macro_availability_report": str(
                    tmp_path / "phase13q_repair_macro_availability_report.csv"
                ),
                "split_summary": str(
                    tmp_path / "phase13q_repair_split_summary.csv"
                ),
                "target_summary": str(
                    tmp_path / "phase13q_repair_target_summary.csv"
                ),
            },
            "dataset_requirements": {
                "required_dataset_label": "multi_factor_technical_macro_dataset_v1",
                "min_rows": 1000,
                "min_value_feature_columns": 8,
                "min_macro_value_feature_columns": 4,
                "required_target_columns": [
                    "future_63d_spy_return_state",
                    "future_63d_drawdown_risk_state",
                ],
                "required_split_labels": ["train", "validation", "holdout"],
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
            "target_policy": {
                "primary_target": {
                    "target_id": "future_63d_spy_return_state",
                    "target_type": "classification",
                    "allowed_classes": ["supportive", "neutral", "fragile"],
                    "unavailable_class": "unavailable",
                    "optimisation_role": "primary supervised learning target only",
                },
                "secondary_target": {
                    "target_id": "future_63d_drawdown_risk_state",
                    "target_type": "classification",
                    "allowed_classes": ["neutral", "fragile"],
                    "unavailable_class": "unavailable",
                    "optimisation_role": "diagnostic risk target only",
                },
            },
            "model_family_registry": [
                {
                    "model_id": "baseline_majority_class",
                    "family": "dummy_classifier",
                    "allowed": True,
                    "role": "sanity baseline",
                    "selection_role": "benchmark only",
                },
                {
                    "model_id": "baseline_stratified_dummy",
                    "family": "dummy_classifier",
                    "allowed": True,
                    "role": "random baseline",
                    "selection_role": "benchmark only",
                },
                {
                    "model_id": "multinomial_logistic_regression",
                    "family": "linear_classifier",
                    "allowed": True,
                    "role": "interpretable baseline",
                    "selection_role": "candidate model family",
                },
                {
                    "model_id": "random_forest_classifier",
                    "family": "tree_ensemble",
                    "allowed": True,
                    "role": "non-linear baseline",
                    "selection_role": "candidate model family",
                },
            ],
            "preprocessing_policy": {
                "fit_scope": "train split only",
                "transform_scope": "train, validation, and holdout",
                "categorical_encoding": "one-hot",
                "numeric_scaling": "train-only scaling",
                "imputation": "train-only imputation",
                "class_imbalance_policy": "report balanced metrics",
                "leakage_controls": ["no future columns in X"],
            },
            "split_usage_policy": {
                "train_split": "fit preprocessing and model parameters",
                "validation_split": "compare registered model families",
                "holdout_split": (
                    "untouched; no model selection, threshold selection, "
                    "feature selection, or hyperparameter choice"
                ),
                "out_of_split_rows": "excluded",
                "walk_forward_now": False,
                "walk_forward_later_allowed_only_after_registration": True,
            },
            "metric_registry": {
                "primary_metrics": ["balanced_accuracy", "macro_f1", "macro_recall"],
                "secondary_metrics": ["accuracy", "confusion_matrix"],
                "calibration_metrics": ["calibration_curve_template"],
                "forbidden_metrics": ["strategy_return", "max_drawdown"],
            },
            "report_templates": {
                "required_future_training_reports": [
                    "confusion_matrix_report",
                    "calibration_report",
                    "class_support_report",
                ],
                "forbidden_future_training_reports": [
                    "signal_report",
                    "strategy_backtest_report",
                ],
            },
            "phase13t_boundary": {
                "allowed_next_step": (
                    "ML training readiness and leakage boundary audit only"
                ),
                "forbidden_next_step": (
                    "model training execution, model selection, prediction "
                    "generation, signal creation, strategy backtest"
                ),
                "phase13t_may_audit_training_protocol": True,
                "phase13t_may_train_model": False,
                "phase13t_may_select_model": False,
                "phase13t_may_generate_predictions": False,
                "phase13t_may_create_signal": False,
                "phase13t_may_run_backtest": False,
                "phase13t_may_promote_candidate": False,
            },
        },
        "phase13t_ml_training_readiness_leakage_audit": {
            "enabled": True,
            "audit_role": "ML training readiness and leakage boundary audit only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13S",
            "proposed_next_phase": "Phase 13U",
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13q_macro_long_to_wide_repair_execution": False,
                "phase13r_repaired_macro_dataset_quality_audit": False,
                "phase13s_ml_model_training_preregistration_spec": True,
                "phase13t_ml_training_readiness_leakage_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13s_reports": {
                "source_report_check": str(
                    tmp_path / "phase13s_prereg_source_report_check.csv"
                ),
                "phase13r_result_check": str(
                    tmp_path / "phase13s_prereg_phase13r_result_check.csv"
                ),
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
                "metric_registry": str(
                    tmp_path / "phase13s_prereg_metric_registry.csv"
                ),
                "report_template_registry": str(
                    tmp_path / "phase13s_prereg_report_template_registry.csv"
                ),
                "forbidden_action_check": str(
                    tmp_path / "phase13s_prereg_forbidden_action_check.csv"
                ),
                "phase13t_boundary_check": str(
                    tmp_path / "phase13s_prereg_phase13t_boundary_check.csv"
                ),
                "summary": str(tmp_path / "phase13s_prereg_summary.csv"),
                "gate_report": str(tmp_path / "phase13s_prereg_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13s_prereg_conclusion.csv"),
            },
            "readiness_thresholds": {
                "required_dataset_label": "multi_factor_technical_macro_dataset_v1",
                "min_rows": 1000,
                "min_value_feature_columns": 8,
                "min_allowed_model_families": 4,
                "min_primary_metrics": 3,
                "require_calibration_template": True,
                "require_confusion_matrix_template": True,
                "require_train_only_preprocessing": True,
                "require_holdout_locked": True,
            },
            "forbidden_output_paths": [
                str(tmp_path / "phase13u_model_predictions.csv"),
                str(tmp_path / "phase13u_signal_report.csv"),
            ],
            "phase13u_boundary": {
                "allowed_next_step": (
                    "Registered baseline ML model training execution and "
                    "train/validation evaluation only"
                ),
                "forbidden_next_step": (
                    "trading signal creation, allocation rule, strategy backtest, "
                    "paper-trading deployment, candidate promotion"
                ),
                "phase13u_may_train_registered_models": True,
                "phase13u_may_fit_train_only_preprocessing": True,
                "phase13u_may_evaluate_train_validation": True,
                "phase13u_may_generate_validation_predictions": True,
                "phase13u_may_generate_holdout_predictions": False,
                "phase13u_may_create_signal": False,
                "phase13u_may_run_backtest": False,
                "phase13u_may_deploy_paper_trading": False,
                "phase13u_may_promote_candidate": False,
            },
        },
    }


def test_phase13s_dataset_requirement_check(tmp_path):
    _write_phase13r_reports(tmp_path)
    _write_repaired_dataset(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase13s_ml_model_training_preregistration_spec"]

    dataset = pd.read_csv(tmp_path / "phase13q_ml_feature_dataset_v1.csv")
    metadata = pd.read_csv(tmp_path / "phase13q_repair_dataset_metadata.csv")
    profile = build_phase13s_dataset_schema_profile(
        dataset=dataset,
        metadata=metadata,
    )
    checks = build_phase13s_dataset_requirement_check(
        dataset=dataset,
        schema_profile=profile,
        phase_config=phase_config,
    )

    assert profile.iloc[0]["value_feature_columns"] == 8
    assert checks["passed"].all()


def test_phase13s_and_13t_save_reports(tmp_path):
    _write_phase13r_reports(tmp_path)
    _write_repaired_dataset(tmp_path)
    config = _config(tmp_path)

    out_s = save_phase13s_ml_model_training_preregistration_spec(
        config=config,
        reports_dir=tmp_path,
    )
    out_t = save_phase13t_ml_training_readiness_leakage_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_s["conclusion"].iloc[0]["all_gates_passed"]
    assert out_t["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13s_prereg_conclusion.csv").exists()
    assert (tmp_path / "phase13t_readiness_conclusion.csv").exists()