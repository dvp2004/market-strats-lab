from pathlib import Path

import pandas as pd

from market_strats.analysis.redesigned_model_preregistration_bundle import (
    save_phase13ak_target_feature_redesign_interpretation_decision,
    save_phase13al_target_feature_redesign_checkpoint_audit,
    save_phase13am_redesigned_model_run_preregistration,
    save_phase13an_redesigned_model_run_readiness_audit,
)


def _write_prior_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13AJ",
                "verdict": "Completed — target-feature diagnostic result audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13aj_redesign_audit_conclusion.csv", index=False)

    pd.DataFrame(
        [{"gate": "dummy", "passed": True, "result": "Passed"}]
    ).to_csv(tmp_path / "phase13aj_redesign_audit_gate_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "target_variant_id": "return_drawdown_63d_composite",
                "feasible": True,
                "live_classes": "fragile; neutral; supportive",
                "has_supportive_neutral_fragile": True,
            },
            {
                "target_variant_id": "drawdown_63d_fragile",
                "feasible": True,
                "live_classes": "fragile; neutral; supportive",
                "has_supportive_neutral_fragile": True,
            },
            {
                "target_variant_id": "original_63d_return_state",
                "feasible": True,
                "live_classes": "fragile; neutral; supportive",
                "has_supportive_neutral_fragile": True,
            },
        ]
    ).to_csv(
        tmp_path / "phase13ai_redesign_panel_target_variant_feasibility_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "target_variant_id": "return_drawdown_63d_composite",
                "train_fragile_ratio": 0.208,
                "validation_fragile_ratio": 0.2119,
                "train_balance_passed": True,
                "validation_balance_passed": True,
            },
            {
                "target_variant_id": "drawdown_63d_fragile",
                "train_fragile_ratio": 0.1897,
                "validation_fragile_ratio": 0.187,
                "train_balance_passed": True,
                "validation_balance_passed": True,
            },
            {
                "target_variant_id": "original_63d_return_state",
                "train_fragile_ratio": 0.1473,
                "validation_fragile_ratio": 0.0978,
                "train_balance_passed": True,
                "validation_balance_passed": False,
            },
        ]
    ).to_csv(
        tmp_path / "phase13ai_redesign_panel_class_balance_report.csv",
        index=False,
    )

    outcome_rows = []
    for target_id, fragile_ret, neutral_ret, supportive_ret in [
        ("return_drawdown_63d_composite", -0.0673, 0.015, 0.088),
        ("drawdown_63d_fragile", -0.0684, 0.014, 0.091),
        ("original_63d_return_state", -0.1122, 0.0134, 0.0903),
    ]:
        for class_label, ret in [
            ("fragile", fragile_ret),
            ("neutral", neutral_ret),
            ("supportive", supportive_ret),
        ]:
            outcome_rows.append(
                {
                    "target_variant_id": target_id,
                    "class_label": class_label,
                    "outcome_column": "future_return_63d",
                    "rows": 100,
                    "mean": ret,
                }
            )
            outcome_rows.append(
                {
                    "target_variant_id": target_id,
                    "class_label": class_label,
                    "outcome_column": "future_window_max_drawdown_63d",
                    "rows": 100,
                    "mean": -0.16 if class_label == "fragile" else -0.06,
                }
            )

    pd.DataFrame(outcome_rows).to_csv(
        tmp_path / "phase13ai_redesign_panel_target_outcome_profile_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "family_id": "technical",
                "value_feature_columns": 4,
                "state_feature_columns": 4,
                "missingness_feature_columns": 4,
                "available_for_current_panel": True,
            },
            {
                "family_id": "macro",
                "value_feature_columns": 4,
                "state_feature_columns": 4,
                "missingness_feature_columns": 4,
                "available_for_current_panel": True,
            },
            {
                "family_id": "fundamental",
                "value_feature_columns": 0,
                "state_feature_columns": 0,
                "missingness_feature_columns": 0,
                "available_for_current_panel": False,
            },
        ]
    ).to_csv(
        tmp_path / "phase13ai_redesign_panel_feature_family_availability_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "target_variant_id": "return_drawdown_63d_composite",
                "feasible": True,
                "train_balance_passed": True,
                "validation_balance_passed": True,
                "economic_return_ordering_passed": True,
                "fragile_drawdown_worse_than_neutral": True,
                "viable_for_future_interpretation": True,
                "target_variant_selected": False,
            },
            {
                "target_variant_id": "drawdown_63d_fragile",
                "feasible": True,
                "train_balance_passed": True,
                "validation_balance_passed": True,
                "economic_return_ordering_passed": True,
                "fragile_drawdown_worse_than_neutral": True,
                "viable_for_future_interpretation": True,
                "target_variant_selected": False,
            },
            {
                "target_variant_id": "original_63d_return_state",
                "feasible": True,
                "train_balance_passed": True,
                "validation_balance_passed": False,
                "economic_return_ordering_passed": True,
                "fragile_drawdown_worse_than_neutral": True,
                "viable_for_future_interpretation": False,
                "target_variant_selected": False,
            },
        ]
    ).to_csv(
        tmp_path / "phase13ai_redesign_panel_redesign_screen_report.csv",
        index=False,
    )


def _write_dataset_and_assignment(tmp_path: Path):
    rows = []
    assignments = []

    for i in range(1000):
        split = "train" if i < 700 else "validation"
        target = "fragile" if i % 5 == 0 else "supportive" if i % 3 == 0 else "neutral"

        row = {
            "decision_date": f"2020-01-{(i % 28) + 1:02d}",
            "split_label": split,
            "dataset_label": "multi_factor_technical_macro_dataset_v1",
            "value__technical_trend_state": float(i % 10),
            "value__technical_momentum_state": float(i % 7),
            "value__technical_volatility_state": float(i % 6),
            "value__technical_drawdown_state": float(i % 5),
            "value__macro_short_rate_state": float(i % 4),
            "value__macro_yield_curve_state": float(i % 3),
            "value__macro_inflation_state": float(i % 8),
            "value__macro_labour_state": float(i % 9),
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
        rows.append(row)

        assignments.append(
            {
                "decision_date": row["decision_date"],
                "split_label": split,
                "return_drawdown_63d_composite": target,
                "drawdown_63d_fragile": target,
                "return_63d_fragile_looser": target,
            }
        )

    pd.DataFrame(rows).to_csv(
        tmp_path / "phase13q_ml_feature_dataset_v1.csv",
        index=False,
    )
    pd.DataFrame(assignments).to_csv(
        tmp_path / "phase13ai_redesign_panel_target_assignment_panel.csv",
        index=False,
    )


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13ag_target_feature_redesign_preregistration": {"enabled": False},
        "phase13ah_target_feature_redesign_readiness_audit": {"enabled": False},
        "phase13ai_target_feature_diagnostic_panel_execution": {"enabled": False},
        "phase13aj_target_feature_diagnostic_result_audit": {"enabled": False},
        "phase13ak_target_feature_redesign_interpretation_decision": {
            "enabled": True,
            "decision_role": (
                "Target-feature redesign interpretation and candidate "
                "target decision only"
            ),
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
                "phase13aj_conclusion": str(
                    tmp_path / "phase13aj_redesign_audit_conclusion.csv"
                ),
                "phase13aj_gate_report": str(
                    tmp_path / "phase13aj_redesign_audit_gate_report.csv"
                ),
                "feasibility_report": str(
                    tmp_path
                    / "phase13ai_redesign_panel_target_variant_feasibility_report.csv"
                ),
                "class_balance_report": str(
                    tmp_path / "phase13ai_redesign_panel_class_balance_report.csv"
                ),
                "target_outcome_profile_report": str(
                    tmp_path
                    / "phase13ai_redesign_panel_target_outcome_profile_report.csv"
                ),
                "feature_family_availability_report": str(
                    tmp_path
                    / "phase13ai_redesign_panel_feature_family_availability_report.csv"
                ),
                "redesign_screen_report": str(
                    tmp_path / "phase13ai_redesign_panel_redesign_screen_report.csv"
                ),
            },
            "target_decision_policy": {
                "primary_decision": "pre_register_redesigned_model_run",
                "preferred_viable_target_order": [
                    "return_drawdown_63d_composite",
                    "drawdown_63d_fragile",
                    "return_63d_fragile_looser",
                ],
                "blocked_targets": [
                    "original_63d_return_state",
                    "return_21d_future_candidate",
                    "return_126d_future_candidate",
                ],
            },
            "phase13al_boundary": {
                "allowed_next_step": "Target-feature redesign checkpoint audit only",
                "forbidden_next_step": "model training, holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
            "phase13am_boundary": {
                "allowed_future_step": "Redesigned model run pre-registration only",
                "forbidden_future_step": "model training, holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
        "phase13al_target_feature_redesign_checkpoint_audit": {
            "enabled": True,
            "audit_role": "Target-feature redesign checkpoint audit only",
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
                "phase13ag_target_feature_redesign_preregistration": False,
                "phase13ah_target_feature_redesign_readiness_audit": False,
                "phase13ai_target_feature_diagnostic_panel_execution": False,
                "phase13aj_target_feature_diagnostic_result_audit": False,
                "phase13ak_target_feature_redesign_interpretation_decision": True,
                "phase13al_target_feature_redesign_checkpoint_audit": True,
                "phase13am_redesigned_model_run_preregistration": True,
                "phase13an_redesigned_model_run_readiness_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13ak_reports": {
                "conclusion": str(tmp_path / "phase13ak_target_decision_conclusion.csv"),
                "gate_report": str(tmp_path / "phase13ak_target_decision_gate_report.csv"),
                "candidate_target_decision_report": str(
                    tmp_path
                    / "phase13ak_target_decision_candidate_target_decision_report.csv"
                ),
                "blocked_target_report": str(
                    tmp_path / "phase13ak_target_decision_blocked_target_report.csv"
                ),
                "feature_family_status_report": str(
                    tmp_path
                    / "phase13ak_target_decision_feature_family_status_report.csv"
                ),
            },
            "forbidden_overclaim_phrases": [
                "model selected",
                "target promoted",
                "validated model",
                "holdout ready",
                "signal created",
                "backtest passed",
                "paper trading ready",
                "candidate promoted",
            ],
            "phase13am_boundary": {
                "allowed_next_step": "Redesigned model run pre-registration only",
                "forbidden_next_step": "model training, holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
        "phase13am_redesigned_model_run_preregistration": {
            "enabled": True,
            "spec_role": "Redesigned model run pre-registration spec only",
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_holdout_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13al_conclusion": str(
                    tmp_path / "phase13al_target_checkpoint_conclusion.csv"
                ),
                "phase13al_gate_report": str(
                    tmp_path / "phase13al_target_checkpoint_gate_report.csv"
                ),
                "candidate_target_decision_report": str(
                    tmp_path
                    / "phase13ak_target_decision_candidate_target_decision_report.csv"
                ),
                "target_assignment_panel": str(
                    tmp_path
                    / "phase13ai_redesign_panel_target_assignment_panel.csv"
                ),
                "dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
            },
            "redesigned_model_run": {
                "run_id": "phase13ao_redesigned_target_model_run_v1",
                "primary_target_variant_fallback": "return_drawdown_63d_composite",
                "holdout_locked": True,
            },
            "feature_policy": {
                "numeric_feature_prefixes": [
                    "value__technical_",
                    "value__macro_",
                ],
                "categorical_feature_prefixes": [
                    "state__technical_",
                    "state__macro_",
                    "missingness__technical_",
                    "missingness__macro_",
                ],
                "forbidden_feature_fragments": [
                    "future_return",
                    "future_window",
                    "target",
                    "signal",
                    "allocation",
                    "model_prediction",
                    "strategy_return",
                    "backtest_return",
                ],
            },
            "preprocessing_policy": {
                "fit_preprocessing_on_train_only": True,
                "numeric_imputation": "median",
            },
            "registered_model_families": [
                {"model_id": "baseline_majority_class", "family": "dummy"},
                {"model_id": "baseline_stratified_dummy", "family": "dummy"},
                {"model_id": "redesigned_logistic_balanced", "family": "logistic_regression"},
                {"model_id": "redesigned_random_forest_regularised", "family": "random_forest"},
                {"model_id": "redesigned_histgb_constrained", "family": "hist_gradient_boosting"},
            ],
            "validation_success_gates": {
                "min_validation_fragile_recall": 0.20,
                "require_no_holdout_predictions": True,
            },
            "phase13an_boundary": {
                "allowed_next_step": "Redesigned model run readiness and leakage audit only",
                "forbidden_next_step": "model training, holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
            "phase13ao_boundary": {
                "allowed_future_step": "Registered redesigned model training on train/validation only",
                "forbidden_future_step": "holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
        "phase13an_redesigned_model_run_readiness_audit": {
            "enabled": True,
            "audit_role": "Redesigned model run readiness and leakage audit only",
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_holdout_prediction_generation": False,
            "allow_feature_importance": False,
            "allow_signal_creation": False,
            "allow_strategy_backtest": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13ak_target_feature_redesign_interpretation_decision": True,
                "phase13al_target_feature_redesign_checkpoint_audit": True,
                "phase13am_redesigned_model_run_preregistration": True,
                "phase13an_redesigned_model_run_readiness_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13am_reports": {
                "conclusion": str(tmp_path / "phase13am_model_prereg_conclusion.csv"),
                "gate_report": str(tmp_path / "phase13am_model_prereg_gate_report.csv"),
                "model_run_spec": str(tmp_path / "phase13am_model_prereg_model_run_spec.csv"),
                "feature_policy": str(tmp_path / "phase13am_model_prereg_feature_policy.csv"),
                "preprocessing_policy": str(
                    tmp_path / "phase13am_model_prereg_preprocessing_policy.csv"
                ),
                "registered_model_families": str(
                    tmp_path / "phase13am_model_prereg_registered_model_families.csv"
                ),
                "validation_success_gates": str(
                    tmp_path / "phase13am_model_prereg_validation_success_gates.csv"
                ),
            },
            "source_reports": {
                "candidate_target_decision_report": str(
                    tmp_path
                    / "phase13ak_target_decision_candidate_target_decision_report.csv"
                ),
                "target_assignment_panel": str(
                    tmp_path
                    / "phase13ai_redesign_panel_target_assignment_panel.csv"
                ),
                "dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
            },
            "readiness_thresholds": {
                "min_train_rows": 500,
                "min_validation_rows": 200,
                "min_train_fragile_ratio": 0.12,
                "min_validation_fragile_ratio": 0.12,
                "min_numeric_features": 4,
                "min_categorical_features": 4,
            },
            "phase13ao_boundary": {
                "allowed_next_step": "Registered redesigned model training on train/validation only",
                "forbidden_next_step": "holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
    }


def test_phase13ak_to_13an_redesigned_model_preregistration_bundle(tmp_path):
    _write_prior_reports(tmp_path)
    _write_dataset_and_assignment(tmp_path)
    config = _config(tmp_path)

    out_ak = save_phase13ak_target_feature_redesign_interpretation_decision(
        config=config,
        reports_dir=tmp_path,
    )
    out_al = save_phase13al_target_feature_redesign_checkpoint_audit(
        config=config,
        reports_dir=tmp_path,
    )
    out_am = save_phase13am_redesigned_model_run_preregistration(
        config=config,
        reports_dir=tmp_path,
    )
    out_an = save_phase13an_redesigned_model_run_readiness_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_ak["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_al["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_am["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_an["conclusion"].iloc[0]["all_gates_passed"])

    decision = out_ak["candidate_target_decision_report"].iloc[0]
    assert decision["candidate_target_variant"] == "return_drawdown_63d_composite"
    assert not bool(decision["model_selected"])
    assert not bool(decision["signal_permission"])