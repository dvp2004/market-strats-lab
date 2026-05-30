from pathlib import Path

import pandas as pd

from market_strats.analysis.ml_validation_interpretation_and_checkpoint import (
    build_phase13w_continuation_decision_report,
    build_phase13w_dummy_comparison_report,
    build_phase13w_overfit_diagnostic_report,
    build_phase13w_validation_ranking_report,
    save_phase13w_ml_validation_interpretation_decision,
    save_phase13x_ml_branch_checkpoint_audit,
)


def _write_phase13v_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13V",
                "verdict": "Completed — ML training result quality/leakage audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13v_quality_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13v_quality_gate_report.csv", index=False)


def _write_phase13u_reports(tmp_path: Path):
    metrics = pd.DataFrame(
        [
            {
                "model_id": "baseline_majority_class",
                "split_label": "train",
                "rows": 1000,
                "accuracy": 0.44,
                "balanced_accuracy": 0.3333,
                "macro_precision": 0.15,
                "macro_recall": 0.3333,
                "macro_f1": 0.205,
                "weighted_f1": 0.27,
                "model_selected": False,
            },
            {
                "model_id": "baseline_majority_class",
                "split_label": "validation",
                "rows": 400,
                "accuracy": 0.44,
                "balanced_accuracy": 0.3333,
                "macro_precision": 0.15,
                "macro_recall": 0.3333,
                "macro_f1": 0.205,
                "weighted_f1": 0.27,
                "model_selected": False,
            },
            {
                "model_id": "baseline_stratified_dummy",
                "split_label": "train",
                "rows": 1000,
                "accuracy": 0.39,
                "balanced_accuracy": 0.34,
                "macro_precision": 0.34,
                "macro_recall": 0.34,
                "macro_f1": 0.34,
                "weighted_f1": 0.39,
                "model_selected": False,
            },
            {
                "model_id": "baseline_stratified_dummy",
                "split_label": "validation",
                "rows": 400,
                "accuracy": 0.39,
                "balanced_accuracy": 0.347,
                "macro_precision": 0.34,
                "macro_recall": 0.347,
                "macro_f1": 0.341,
                "weighted_f1": 0.40,
                "model_selected": False,
            },
            {
                "model_id": "random_forest_classifier",
                "split_label": "train",
                "rows": 1000,
                "accuracy": 0.75,
                "balanced_accuracy": 0.77,
                "macro_precision": 0.76,
                "macro_recall": 0.77,
                "macro_f1": 0.76,
                "weighted_f1": 0.75,
                "model_selected": False,
            },
            {
                "model_id": "random_forest_classifier",
                "split_label": "validation",
                "rows": 400,
                "accuracy": 0.57,
                "balanced_accuracy": 0.425,
                "macro_precision": 0.40,
                "macro_recall": 0.425,
                "macro_f1": 0.401,
                "weighted_f1": 0.54,
                "model_selected": False,
            },
            {
                "model_id": "hist_gradient_boosting_classifier",
                "split_label": "train",
                "rows": 1000,
                "accuracy": 0.96,
                "balanced_accuracy": 0.97,
                "macro_precision": 0.97,
                "macro_recall": 0.97,
                "macro_f1": 0.97,
                "weighted_f1": 0.96,
                "model_selected": False,
            },
            {
                "model_id": "hist_gradient_boosting_classifier",
                "split_label": "validation",
                "rows": 400,
                "accuracy": 0.48,
                "balanced_accuracy": 0.36,
                "macro_precision": 0.35,
                "macro_recall": 0.36,
                "macro_f1": 0.33,
                "weighted_f1": 0.44,
                "model_selected": False,
            },
        ]
    )
    metrics.to_csv(tmp_path / "phase13u_ml_train_validation_metric_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "model_id": "baseline_majority_class",
                "validation_balanced_accuracy": 0.3333,
                "validation_macro_f1": 0.205,
                "majority_baseline_balanced_accuracy": 0.3333,
                "majority_baseline_macro_f1": 0.205,
                "delta_balanced_accuracy_vs_majority": 0.0,
                "delta_macro_f1_vs_majority": 0.0,
                "diagnostic_only": True,
                "model_selected": False,
            },
            {
                "model_id": "baseline_stratified_dummy",
                "validation_balanced_accuracy": 0.347,
                "validation_macro_f1": 0.341,
                "majority_baseline_balanced_accuracy": 0.3333,
                "majority_baseline_macro_f1": 0.205,
                "delta_balanced_accuracy_vs_majority": 0.0137,
                "delta_macro_f1_vs_majority": 0.136,
                "diagnostic_only": True,
                "model_selected": False,
            },
            {
                "model_id": "random_forest_classifier",
                "validation_balanced_accuracy": 0.425,
                "validation_macro_f1": 0.401,
                "majority_baseline_balanced_accuracy": 0.3333,
                "majority_baseline_macro_f1": 0.205,
                "delta_balanced_accuracy_vs_majority": 0.0917,
                "delta_macro_f1_vs_majority": 0.196,
                "diagnostic_only": True,
                "model_selected": False,
            },
            {
                "model_id": "hist_gradient_boosting_classifier",
                "validation_balanced_accuracy": 0.36,
                "validation_macro_f1": 0.33,
                "majority_baseline_balanced_accuracy": 0.3333,
                "majority_baseline_macro_f1": 0.205,
                "delta_balanced_accuracy_vs_majority": 0.0267,
                "delta_macro_f1_vs_majority": 0.125,
                "diagnostic_only": True,
                "model_selected": False,
            },
        ]
    ).to_csv(tmp_path / "phase13u_ml_baseline_comparison_report.csv", index=False)

    rows = []
    for model_id in [
        "baseline_majority_class",
        "baseline_stratified_dummy",
        "random_forest_classifier",
        "hist_gradient_boosting_classifier",
    ]:
        for true_label in ["supportive", "neutral", "fragile"]:
            for predicted_label in ["supportive", "neutral", "fragile"]:
                rows.append(
                    {
                        "model_id": model_id,
                        "split_label": "validation",
                        "true_label": true_label,
                        "predicted_label": predicted_label,
                        "count": 20 if true_label == predicted_label else 5,
                    }
                )
    pd.DataFrame(rows).to_csv(tmp_path / "phase13u_ml_confusion_matrix_report.csv", index=False)

    for name in [
        "phase13u_ml_calibration_report.csv",
        "phase13u_ml_class_support_report.csv",
        "phase13u_ml_validation_predictions.csv",
        "phase13u_ml_forbidden_output_check.csv",
        "phase13v_quality_forbidden_output_check.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _write_checkpoint_reports(tmp_path: Path):
    for name in [
        "phase13q_ml_feature_dataset_v1.csv",
        "phase13r_quality_conclusion.csv",
        "phase13s_prereg_conclusion.csv",
        "phase13t_readiness_conclusion.csv",
        "phase13u_ml_conclusion.csv",
    ]:
        pd.DataFrame([{"all_gates_passed": True}]).to_csv(tmp_path / name, index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13u_registered_baseline_ml_training": {"enabled": False},
        "phase13v_ml_training_result_quality_audit": {"enabled": False},
        "phase13w_ml_validation_interpretation_decision": {
            "enabled": True,
            "interpretation_role": (
                "ML validation result interpretation and continuation decision only"
            ),
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13V",
            "proposed_next_phase": "Phase 13X",
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_prediction_generation": False,
            "allow_holdout_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13v_conclusion": str(tmp_path / "phase13v_quality_conclusion.csv"),
                "phase13v_gate_report": str(tmp_path / "phase13v_quality_gate_report.csv"),
                "metric_report": str(tmp_path / "phase13u_ml_train_validation_metric_report.csv"),
                "baseline_comparison_report": str(tmp_path / "phase13u_ml_baseline_comparison_report.csv"),
                "confusion_matrix_report": str(tmp_path / "phase13u_ml_confusion_matrix_report.csv"),
                "calibration_report": str(tmp_path / "phase13u_ml_calibration_report.csv"),
                "class_support_report": str(tmp_path / "phase13u_ml_class_support_report.csv"),
                "validation_predictions": str(tmp_path / "phase13u_ml_validation_predictions.csv"),
                "phase13u_forbidden_output_check": str(tmp_path / "phase13u_ml_forbidden_output_check.csv"),
                "phase13v_forbidden_output_check": str(tmp_path / "phase13v_quality_forbidden_output_check.csv"),
            },
            "interpretation_thresholds": {
                "majority_baseline_model_id": "baseline_majority_class",
                "stratified_baseline_model_id": "baseline_stratified_dummy",
                "real_model_ids": [
                    "random_forest_classifier",
                    "hist_gradient_boosting_classifier",
                ],
                "min_material_delta_balanced_accuracy_vs_majority": 0.05,
                "min_material_delta_macro_f1_vs_majority": 0.05,
                "min_delta_balanced_accuracy_vs_stratified": 0.03,
                "max_overfit_gap_balanced_accuracy_warning": 0.25,
                "max_overfit_gap_macro_f1_warning": 0.25,
                "fragile_class_min_validation_recall_warning": 0.20,
            },
            "decision_policy": {
                "if_material_edge_and_boundaries_clean": "continue_to_holdout_preregistration",
                "if_weak_edge_or_severe_class_failure": "continue_only_after_model_diagnostic_repair",
                "if_no_real_model_beats_dummy": "stop_ml_branch_or_return_to_features",
            },
            "phase13x_boundary": {
                "allowed_next_step": "ML branch checkpoint and report-config consistency audit only",
                "forbidden_next_step": "new model training, model selection, holdout prediction generation, signal creation, strategy backtest",
                "phase13x_may_audit_reports": True,
                "phase13x_may_generate_holdout_predictions": False,
                "phase13x_may_create_signal": False,
                "phase13x_may_run_backtest": False,
                "phase13x_may_promote_candidate": False,
            },
            "phase13y_boundary": {
                "allowed_future_step": "Holdout evaluation pre-registration spec only",
                "forbidden_future_step": "holdout prediction execution, signal creation, strategy backtest",
                "phase13y_may_preregister_holdout_evaluation": True,
                "phase13y_may_generate_holdout_predictions": False,
                "phase13y_may_select_model": False,
                "phase13y_may_create_signal": False,
                "phase13y_may_run_backtest": False,
                "phase13y_may_promote_candidate": False,
            },
        },
        "phase13x_ml_branch_checkpoint_audit": {
            "enabled": True,
            "audit_role": "ML branch checkpoint and report-config consistency audit only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13W",
            "proposed_next_phase": "Phase 13Y",
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_prediction_generation": False,
            "allow_holdout_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13u_registered_baseline_ml_training": False,
                "phase13v_ml_training_result_quality_audit": False,
                "phase13w_ml_validation_interpretation_decision": True,
                "phase13x_ml_branch_checkpoint_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13w_reports": {
                "source_report_check": str(tmp_path / "phase13w_interpretation_source_report_check.csv"),
                "phase13v_result_check": str(tmp_path / "phase13w_interpretation_phase13v_result_check.csv"),
                "validation_ranking_report": str(tmp_path / "phase13w_interpretation_validation_ranking_report.csv"),
                "dummy_comparison_report": str(tmp_path / "phase13w_interpretation_dummy_comparison_report.csv"),
                "overfit_diagnostic_report": str(tmp_path / "phase13w_interpretation_overfit_diagnostic_report.csv"),
                "class_recall_report": str(tmp_path / "phase13w_interpretation_class_recall_report.csv"),
                "continuation_decision_report": str(tmp_path / "phase13w_interpretation_continuation_decision_report.csv"),
                "phase13x_boundary_check": str(tmp_path / "phase13w_interpretation_phase13x_boundary_check.csv"),
                "phase13y_boundary_check": str(tmp_path / "phase13w_interpretation_phase13y_boundary_check.csv"),
                "scope_boundary_check": str(tmp_path / "phase13w_interpretation_scope_boundary_check.csv"),
                "summary": str(tmp_path / "phase13w_interpretation_summary.csv"),
                "gate_report": str(tmp_path / "phase13w_interpretation_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13w_interpretation_conclusion.csv"),
            },
            "checkpoint_reports": {
                "required_phase13_reports": [
                    str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
                    str(tmp_path / "phase13r_quality_conclusion.csv"),
                    str(tmp_path / "phase13s_prereg_conclusion.csv"),
                    str(tmp_path / "phase13t_readiness_conclusion.csv"),
                    str(tmp_path / "phase13u_ml_conclusion.csv"),
                    str(tmp_path / "phase13v_quality_conclusion.csv"),
                    str(tmp_path / "phase13w_interpretation_conclusion.csv"),
                ],
                "forbidden_overclaim_phrases": [
                    "profitable strategy",
                    "validated trading strategy",
                    "candidate promoted",
                    "final candidate changed",
                ],
            },
            "phase13y_boundary": {
                "allowed_next_step": "Holdout evaluation pre-registration spec only",
                "forbidden_next_step": "holdout prediction execution, signal creation, strategy backtest",
                "phase13y_may_preregister_holdout_evaluation": True,
                "phase13y_may_generate_holdout_predictions": False,
                "phase13y_may_select_model": False,
                "phase13y_may_create_signal": False,
                "phase13y_may_run_backtest": False,
                "phase13y_may_promote_candidate": False,
            },
        },
    }


def test_phase13w_interprets_validation_edge_without_model_selection(tmp_path):
    _write_phase13v_reports(tmp_path)
    _write_phase13u_reports(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase13w_ml_validation_interpretation_decision"]

    metrics = pd.read_csv(tmp_path / "phase13u_ml_train_validation_metric_report.csv")
    baseline = pd.read_csv(tmp_path / "phase13u_ml_baseline_comparison_report.csv")

    ranking = build_phase13w_validation_ranking_report(metrics, baseline, phase_config)
    dummy = build_phase13w_dummy_comparison_report(ranking, phase_config)
    overfit = build_phase13w_overfit_diagnostic_report(metrics, phase_config)
    decision = build_phase13w_continuation_decision_report(
        dummy_comparison=dummy,
        overfit_report=overfit,
        class_recall_report=pd.DataFrame(
            [
                {
                    "model_id": "random_forest_classifier",
                    "class_label": "fragile",
                    "validation_recall": 0.5,
                    "fragile_recall_warning": False,
                }
            ]
        ),
        phase_config=phase_config,
    )

    assert ranking["diagnostic_leading_model"].sum() == 1
    assert dummy.iloc[0]["diagnostic_leading_model"] == "random_forest_classifier"
    assert not bool(decision.iloc[0]["model_selected"])
    assert not bool(decision.iloc[0]["signal_permission"])


def test_phase13w_and_13x_save_reports(tmp_path):
    _write_phase13v_reports(tmp_path)
    _write_phase13u_reports(tmp_path)
    _write_checkpoint_reports(tmp_path)
    config = _config(tmp_path)

    out_w = save_phase13w_ml_validation_interpretation_decision(
        config=config,
        reports_dir=tmp_path,
    )
    out_x = save_phase13x_ml_branch_checkpoint_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_w["conclusion"].iloc[0]["all_gates_passed"]
    assert out_x["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13w_interpretation_conclusion.csv").exists()
    assert (tmp_path / "phase13x_checkpoint_conclusion.csv").exists()