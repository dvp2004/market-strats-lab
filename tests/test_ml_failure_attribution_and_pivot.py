from pathlib import Path

import pandas as pd

from market_strats.analysis.ml_failure_attribution_and_pivot import (
    save_phase13ac_ml_failure_attribution_diagnostic,
    save_phase13ad_ml_failure_attribution_readiness_audit,
    save_phase13ae_ml_branch_continuation_architecture_pivot,
    save_phase13af_phase13_ml_branch_checkpoint_audit,
)


def _write_prior_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13AB",
                "verdict": "Completed — ML diagnostic repair result quality audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13ab_repair_audit_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13ab_repair_audit_gate_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "repair_id": "rf_repair_fragile_weighted",
                "validation_balanced_accuracy": 0.4157,
                "validation_macro_f1": 0.3919,
                "validation_fragile_recall": 0.0,
                "delta_balanced_accuracy_vs_majority": 0.0824,
                "delta_macro_f1_vs_majority": 0.1869,
                "balanced_accuracy_gap": 0.2786,
                "macro_f1_gap": 0.3077,
                "passes_fragile_recall_gate": False,
                "passes_majority_edge_gate": True,
                "passes_overfit_gate": True,
                "model_selected": False,
                "signal_permission": False,
                "holdout_permission": False,
            },
            {
                "repair_id": "histgb_repair_shallow_l2",
                "validation_balanced_accuracy": 0.3857,
                "validation_macro_f1": 0.3606,
                "validation_fragile_recall": 0.0098,
                "delta_balanced_accuracy_vs_majority": 0.0524,
                "delta_macro_f1_vs_majority": 0.1557,
                "balanced_accuracy_gap": 0.4890,
                "macro_f1_gap": 0.5103,
                "passes_fragile_recall_gate": False,
                "passes_majority_edge_gate": True,
                "passes_overfit_gate": False,
                "model_selected": False,
                "signal_permission": False,
                "holdout_permission": False,
            },
        ]
    ).to_csv(tmp_path / "phase13aa_repair_execution_success_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "repair_id": "rf_repair_fragile_weighted",
                "split_label": "validation",
                "rows": 1007,
                "balanced_accuracy": 0.4157,
                "macro_f1": 0.3919,
                "macro_recall": 0.4157,
                "model_selected": False,
                "signal_created": False,
            }
        ]
    ).to_csv(tmp_path / "phase13aa_repair_execution_metric_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "repair_id": "rf_repair_fragile_weighted",
                "class_label": "supportive",
                "validation_support": 458,
                "validation_recall": 0.5,
                "fragile_recall_warning": False,
            },
            {
                "repair_id": "rf_repair_fragile_weighted",
                "class_label": "neutral",
                "validation_support": 447,
                "validation_recall": 0.747,
                "fragile_recall_warning": False,
            },
            {
                "repair_id": "rf_repair_fragile_weighted",
                "class_label": "fragile",
                "validation_support": 102,
                "validation_recall": 0.0,
                "fragile_recall_warning": True,
            },
        ]
    ).to_csv(tmp_path / "phase13aa_repair_execution_class_recall_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "repair_id": "rf_repair_fragile_weighted",
                "train_balanced_accuracy": 0.6943,
                "validation_balanced_accuracy": 0.4157,
                "balanced_accuracy_gap": 0.2786,
                "train_macro_f1": 0.6995,
                "validation_macro_f1": 0.3919,
                "macro_f1_gap": 0.3077,
            }
        ]
    ).to_csv(tmp_path / "phase13aa_repair_execution_overfit_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "model_id": "random_forest_classifier",
                "split_label": "validation",
                "rows": 1007,
                "balanced_accuracy": 0.4253,
                "macro_f1": 0.4010,
            }
        ]
    ).to_csv(tmp_path / "phase13u_ml_train_validation_metric_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "diagnostic_leading_model": "random_forest_classifier",
                "delta_balanced_accuracy_vs_majority": 0.0920,
                "delta_macro_f1_vs_majority": 0.1960,
            }
        ]
    ).to_csv(tmp_path / "phase13u_ml_baseline_comparison_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "decision": "continue_only_after_model_diagnostic_repair",
                "holdout_preregistration_justified": False,
            }
        ]
    ).to_csv(tmp_path / "phase13w_interpretation_continuation_decision_report.csv", index=False)


def _write_dataset(tmp_path: Path):
    rows = []
    for i in range(120):
        split = "train" if i < 80 else "validation"
        if i % 10 == 0:
            cls = "fragile"
            future_ret = -0.08
        elif i % 3 == 0:
            cls = "supportive"
            future_ret = 0.06
        else:
            cls = "neutral"
            future_ret = 0.01

        rows.append(
            {
                "dataset_label": "multi_factor_technical_macro_dataset_v1",
                "split_label": split,
                "target_available": True,
                "future_63d_spy_return_state": cls,
                "future_return_63d": future_ret,
                "future_window_max_drawdown_63d": -0.12 if cls == "fragile" else -0.03,
            }
        )

    pd.DataFrame(rows).to_csv(tmp_path / "phase13q_ml_feature_dataset_v1.csv", index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13y_ml_diagnostic_repair_preregistration": {"enabled": False},
        "phase13z_ml_diagnostic_repair_readiness_audit": {"enabled": False},
        "phase13aa_registered_ml_diagnostic_repair_execution": {"enabled": False},
        "phase13ab_ml_diagnostic_repair_result_audit": {"enabled": False},
        "phase13ac_ml_failure_attribution_diagnostic": {
            "enabled": True,
            "diagnostic_role": "ML failure attribution and target-feature diagnostic only",
            "allow_model_training": False,
            "allow_repair_execution": False,
            "allow_model_selection": False,
            "allow_holdout_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13ab_conclusion": str(tmp_path / "phase13ab_repair_audit_conclusion.csv"),
                "phase13ab_gate_report": str(tmp_path / "phase13ab_repair_audit_gate_report.csv"),
                "repair_success_report": str(tmp_path / "phase13aa_repair_execution_success_report.csv"),
                "repair_metric_report": str(tmp_path / "phase13aa_repair_execution_metric_report.csv"),
                "repair_class_recall_report": str(tmp_path / "phase13aa_repair_execution_class_recall_report.csv"),
                "repair_overfit_report": str(tmp_path / "phase13aa_repair_execution_overfit_report.csv"),
                "original_metric_report": str(tmp_path / "phase13u_ml_train_validation_metric_report.csv"),
                "original_baseline_comparison_report": str(tmp_path / "phase13u_ml_baseline_comparison_report.csv"),
                "phase13w_decision_report": str(tmp_path / "phase13w_interpretation_continuation_decision_report.csv"),
                "dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
            },
            "diagnostic_thresholds": {
                "fragile_recall_success_threshold": 0.20,
                "min_fragile_support_warning_ratio": 0.15,
                "original_best_model_id": "random_forest_classifier",
                "original_best_validation_balanced_accuracy": 0.4253,
                "original_best_validation_macro_f1": 0.4010,
            },
            "attribution_families": [
                "target_definition",
                "horizon_63d",
                "fragile_threshold",
                "class_imbalance",
                "feature_insufficiency",
                "model_architecture",
                "missing_fundamental_sentiment",
            ],
            "phase13ad_boundary": {
                "allowed_next_step": "ML failure attribution readiness and report audit only",
                "forbidden_next_step": "model training, holdout prediction generation, signal creation, strategy backtest",
            },
            "phase13ae_boundary": {
                "allowed_future_step": "ML branch continuation and architecture pivot decision only",
                "forbidden_future_step": "model training, holdout prediction generation, signal creation, strategy backtest",
            },
        },
        "phase13ad_ml_failure_attribution_readiness_audit": {
            "enabled": True,
            "audit_role": "ML failure attribution readiness and report audit only",
            "allow_model_training": False,
            "allow_repair_execution": False,
            "allow_model_selection": False,
            "allow_holdout_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13y_ml_diagnostic_repair_preregistration": False,
                "phase13z_ml_diagnostic_repair_readiness_audit": False,
                "phase13aa_registered_ml_diagnostic_repair_execution": False,
                "phase13ab_ml_diagnostic_repair_result_audit": False,
                "phase13ac_ml_failure_attribution_diagnostic": True,
                "phase13ad_ml_failure_attribution_readiness_audit": True,
                "phase13ae_ml_branch_continuation_architecture_pivot": True,
                "phase13af_phase13_ml_branch_checkpoint_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13ac_reports": {
                "conclusion": str(tmp_path / "phase13ac_failure_attribution_conclusion.csv"),
                "gate_report": str(tmp_path / "phase13ac_failure_attribution_gate_report.csv"),
                "failure_summary_report": str(tmp_path / "phase13ac_failure_attribution_failure_summary_report.csv"),
                "target_distribution_report": str(tmp_path / "phase13ac_failure_attribution_target_distribution_report.csv"),
                "class_imbalance_report": str(tmp_path / "phase13ac_failure_attribution_class_imbalance_report.csv"),
                "target_outcome_profile_report": str(tmp_path / "phase13ac_failure_attribution_target_outcome_profile_report.csv"),
                "failure_attribution_report": str(tmp_path / "phase13ac_failure_attribution_failure_attribution_report.csv"),
                "continuation_options_report": str(tmp_path / "phase13ac_failure_attribution_continuation_options_report.csv"),
            },
        },
        "phase13ae_ml_branch_continuation_architecture_pivot": {
            "enabled": True,
            "decision_role": "ML branch continuation and architecture pivot decision only",
            "allow_model_training": False,
            "allow_repair_execution": False,
            "allow_model_selection": False,
            "allow_holdout_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13ad_conclusion": str(tmp_path / "phase13ad_failure_audit_conclusion.csv"),
                "phase13ad_gate_report": str(tmp_path / "phase13ad_failure_audit_gate_report.csv"),
                "failure_summary_report": str(tmp_path / "phase13ac_failure_attribution_failure_summary_report.csv"),
                "failure_attribution_report": str(tmp_path / "phase13ac_failure_attribution_failure_attribution_report.csv"),
                "continuation_options_report": str(tmp_path / "phase13ac_failure_attribution_continuation_options_report.csv"),
            },
            "decision_policy": {
                "if_fragile_recall_unresolved": "pivot_to_target_feature_redesign_preregistration",
                "default_decision": "pivot_to_target_feature_redesign_preregistration",
            },
            "next_phase_boundary": {
                "allowed_next_step": "Target-feature redesign pre-registration only",
                "forbidden_next_step": "model training, repair execution, holdout prediction generation, model selection, feature importance, signal creation, strategy backtest, candidate promotion",
                "may_preregister_target_feature_redesign": True,
                "may_train_model": False,
                "may_execute_repair": False,
                "may_generate_holdout_predictions": False,
                "may_select_model": False,
                "may_create_signal": False,
                "may_run_backtest": False,
                "may_promote_candidate": False,
            },
        },
        "phase13af_phase13_ml_branch_checkpoint_audit": {
            "enabled": True,
            "audit_role": "Phase 13 ML branch checkpoint audit only",
            "allow_model_training": False,
            "allow_repair_execution": False,
            "allow_model_selection": False,
            "allow_holdout_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13ac_ml_failure_attribution_diagnostic": True,
                "phase13ad_ml_failure_attribution_readiness_audit": True,
                "phase13ae_ml_branch_continuation_architecture_pivot": True,
                "phase13af_phase13_ml_branch_checkpoint_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13ae_reports": {
                "conclusion": str(tmp_path / "phase13ae_pivot_decision_conclusion.csv"),
                "gate_report": str(tmp_path / "phase13ae_pivot_decision_gate_report.csv"),
                "architecture_decision_report": str(tmp_path / "phase13ae_pivot_decision_architecture_decision_report.csv"),
            },
            "checkpoint_reports": {
                "required_reports": [
                    str(tmp_path / "phase13ac_failure_attribution_conclusion.csv"),
                    str(tmp_path / "phase13ad_failure_audit_conclusion.csv"),
                    str(tmp_path / "phase13ae_pivot_decision_conclusion.csv"),
                ],
                "forbidden_overclaim_phrases": [
                    "holdout ready",
                    "model selected",
                    "validated trading strategy",
                    "signal created",
                    "candidate promoted",
                ],
            },
            "phase13ag_boundary": {
                "allowed_next_step": "Target-feature redesign pre-registration only",
                "forbidden_next_step": "model training, holdout prediction generation, signal creation, strategy backtest, candidate promotion",
            },
        },
    }


def test_phase13ac_to_13af_failure_attribution_bundle(tmp_path):
    _write_prior_reports(tmp_path)
    _write_dataset(tmp_path)
    config = _config(tmp_path)

    out_ac = save_phase13ac_ml_failure_attribution_diagnostic(config=config, reports_dir=tmp_path)
    out_ad = save_phase13ad_ml_failure_attribution_readiness_audit(config=config, reports_dir=tmp_path)
    out_ae = save_phase13ae_ml_branch_continuation_architecture_pivot(config=config, reports_dir=tmp_path)
    out_af = save_phase13af_phase13_ml_branch_checkpoint_audit(config=config, reports_dir=tmp_path)

    assert bool(out_ac["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_ad["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_ae["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_af["conclusion"].iloc[0]["all_gates_passed"])

    decision = out_ae["architecture_decision_report"].iloc[0]["architecture_decision"]
    assert decision == "pivot_to_target_feature_redesign_preregistration"