from pathlib import Path

import pandas as pd

from market_strats.analysis.target_feature_redesign_bundle import (
    save_phase13ag_target_feature_redesign_preregistration,
    save_phase13ah_target_feature_redesign_readiness_audit,
    save_phase13ai_target_feature_diagnostic_panel_execution,
    save_phase13aj_target_feature_diagnostic_result_audit,
)


def _write_prior_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13AF",
                "verdict": "Completed — Phase 13 ML branch checkpoint audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13af_checkpoint_conclusion.csv", index=False)

    pd.DataFrame(
        [{"gate": "dummy", "passed": True, "result": "Passed"}]
    ).to_csv(tmp_path / "phase13af_checkpoint_gate_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "architecture_decision": "pivot_to_target_feature_redesign_preregistration",
                "direct_holdout_blocked": True,
                "model_selected": False,
                "signal_permission": False,
                "backtest_permission": False,
            }
        ]
    ).to_csv(
        tmp_path / "phase13ae_pivot_decision_architecture_decision_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "attribution_family": "target_definition",
                "severity": "high",
                "evidence": "fragile unresolved",
            }
        ]
    ).to_csv(
        tmp_path / "phase13ac_failure_attribution_failure_attribution_report.csv",
        index=False,
    )


def _write_dataset(tmp_path: Path):
    rows = []

    for i in range(150):
        split = "train" if i < 90 else "validation"

        if i % 7 == 0:
            ret = -0.08
            dd = -0.14
            state = "fragile"
        elif i % 3 == 0:
            ret = 0.07
            dd = -0.03
            state = "supportive"
        else:
            ret = 0.01
            dd = -0.06
            state = "neutral"

        rows.append(
            {
                "decision_date": f"2020-01-{(i % 28) + 1:02d}",
                "split_label": split,
                "dataset_label": "multi_factor_technical_macro_dataset_v1",
                "future_63d_spy_return_state": state,
                "future_return_63d": ret,
                "future_window_max_drawdown_63d": dd,
                "value__technical_trend_state": float(i % 10),
                "value__technical_momentum_state": float(i % 5),
                "value__macro_short_rate_state": float(i % 4),
                "value__macro_inflation_state": float(i % 6),
                "state__technical_trend_state": "neutral",
                "state__macro_short_rate_state": "neutral",
                "missingness__technical_trend_state": "available",
                "missingness__macro_short_rate_state": "available",
            }
        )

    pd.DataFrame(rows).to_csv(
        tmp_path / "phase13q_ml_feature_dataset_v1.csv",
        index=False,
    )


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13ac_ml_failure_attribution_diagnostic": {"enabled": False},
        "phase13ad_ml_failure_attribution_readiness_audit": {"enabled": False},
        "phase13ae_ml_branch_continuation_architecture_pivot": {"enabled": False},
        "phase13af_phase13_ml_branch_checkpoint_audit": {"enabled": False},
        "phase13ag_target_feature_redesign_preregistration": {
            "enabled": True,
            "spec_role": "Target-feature redesign pre-registration spec only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13AF",
            "proposed_next_phase": "Phase 13AH",
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
                "phase13af_conclusion": str(
                    tmp_path / "phase13af_checkpoint_conclusion.csv"
                ),
                "phase13af_gate_report": str(
                    tmp_path / "phase13af_checkpoint_gate_report.csv"
                ),
                "architecture_decision_report": str(
                    tmp_path
                    / "phase13ae_pivot_decision_architecture_decision_report.csv"
                ),
                "failure_attribution_report": str(
                    tmp_path
                    / "phase13ac_failure_attribution_failure_attribution_report.csv"
                ),
                "dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
            },
            "target_variant_registry": [
                {
                    "target_variant_id": "original_63d_return_state",
                    "rule_type": "existing_state_column",
                    "required_columns": ["future_63d_spy_return_state"],
                    "source_column": "future_63d_spy_return_state",
                    "horizon_days": 63,
                    "enabled": True,
                },
                {
                    "target_variant_id": "return_63d_fragile_looser",
                    "rule_type": "return_63d_threshold",
                    "required_columns": ["future_return_63d"],
                    "horizon_days": 63,
                    "fragile_return_max": -0.03,
                    "supportive_return_min": 0.05,
                    "enabled": True,
                },
                {
                    "target_variant_id": "return_drawdown_63d_composite",
                    "rule_type": "return_drawdown_63d_composite",
                    "required_columns": [
                        "future_return_63d",
                        "future_window_max_drawdown_63d",
                    ],
                    "horizon_days": 63,
                    "fragile_return_max": -0.04,
                    "fragile_drawdown_max": -0.10,
                    "supportive_return_min": 0.05,
                    "supportive_drawdown_min": -0.08,
                    "enabled": True,
                },
                {
                    "target_variant_id": "return_21d_future_candidate",
                    "rule_type": "unavailable_future_horizon",
                    "required_columns": [
                        "future_return_21d",
                        "future_window_max_drawdown_21d",
                    ],
                    "horizon_days": 21,
                    "enabled": True,
                },
            ],
            "target_quality_policy": {
                "min_validation_fragile_ratio": 0.10,
                "max_validation_fragile_ratio": 0.35,
                "min_train_fragile_ratio": 0.10,
                "max_train_fragile_ratio": 0.35,
            },
            "feature_family_registry": [
                {
                    "family_id": "technical",
                    "status": "available_current_dataset",
                    "value_prefixes": ["value__technical_"],
                    "state_prefixes": ["state__technical_"],
                    "missingness_prefixes": ["missingness__technical_"],
                },
                {
                    "family_id": "macro",
                    "status": "available_current_dataset",
                    "value_prefixes": ["value__macro_"],
                    "state_prefixes": ["state__macro_"],
                    "missingness_prefixes": ["missingness__macro_"],
                },
                {
                    "family_id": "fundamental",
                    "status": "future_missing",
                    "value_prefixes": ["value__fundamental_"],
                    "state_prefixes": ["state__fundamental_"],
                    "missingness_prefixes": ["missingness__fundamental_"],
                },
                {
                    "family_id": "sentiment",
                    "status": "future_missing",
                    "value_prefixes": ["value__sentiment_"],
                    "state_prefixes": ["state__sentiment_"],
                    "missingness_prefixes": ["missingness__sentiment_"],
                },
                {
                    "family_id": "market_stress",
                    "status": "future_missing",
                    "value_prefixes": ["value__market_stress_"],
                    "state_prefixes": ["state__market_stress_"],
                    "missingness_prefixes": ["missingness__market_stress_"],
                },
            ],
            "diagnostic_panel_policy": {
                "descriptive_feature_target_separation_allowed": True,
                "feature_ranking_allowed": False,
                "feature_importance_allowed": False,
                "model_training_allowed": False,
            },
            "phase13ah_boundary": {
                "allowed_next_step": "Target-feature redesign readiness and boundary audit only",
                "forbidden_next_step": "diagnostic panel execution, model training, holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
            "phase13ai_boundary": {
                "allowed_future_step": "Target-feature diagnostic panel execution only",
                "forbidden_future_step": "model training, holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
        "phase13ah_target_feature_redesign_readiness_audit": {
            "enabled": True,
            "audit_role": "Target-feature redesign readiness and boundary audit only",
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
                "phase13ac_ml_failure_attribution_diagnostic": False,
                "phase13ad_ml_failure_attribution_readiness_audit": False,
                "phase13ae_ml_branch_continuation_architecture_pivot": False,
                "phase13af_phase13_ml_branch_checkpoint_audit": False,
                "phase13ag_target_feature_redesign_preregistration": True,
                "phase13ah_target_feature_redesign_readiness_audit": True,
                "phase13ai_target_feature_diagnostic_panel_execution": True,
                "phase13aj_target_feature_diagnostic_result_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13ag_reports": {
                "conclusion": str(tmp_path / "phase13ag_redesign_prereg_conclusion.csv"),
                "gate_report": str(tmp_path / "phase13ag_redesign_prereg_gate_report.csv"),
                "target_variant_registry": str(
                    tmp_path / "phase13ag_redesign_prereg_target_variant_registry.csv"
                ),
                "target_quality_policy": str(
                    tmp_path / "phase13ag_redesign_prereg_target_quality_policy.csv"
                ),
                "feature_family_registry": str(
                    tmp_path / "phase13ag_redesign_prereg_feature_family_registry.csv"
                ),
                "diagnostic_panel_policy": str(
                    tmp_path / "phase13ag_redesign_prereg_diagnostic_panel_policy.csv"
                ),
            },
        },
        "phase13ai_target_feature_diagnostic_panel_execution": {
            "enabled": True,
            "execution_role": "Target-feature diagnostic panel execution only",
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
                "phase13ah_conclusion": str(
                    tmp_path / "phase13ah_redesign_readiness_conclusion.csv"
                ),
                "phase13ah_gate_report": str(
                    tmp_path / "phase13ah_redesign_readiness_gate_report.csv"
                ),
                "dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
                "target_variant_registry": str(
                    tmp_path / "phase13ag_redesign_prereg_target_variant_registry.csv"
                ),
                "target_quality_policy": str(
                    tmp_path / "phase13ag_redesign_prereg_target_quality_policy.csv"
                ),
                "feature_family_registry": str(
                    tmp_path / "phase13ag_redesign_prereg_feature_family_registry.csv"
                ),
            },
            "panel_policy": {
                "max_feature_target_separation_rows": 10000,
            },
            "phase13aj_boundary": {
                "allowed_next_step": "Target-feature diagnostic result audit only",
                "forbidden_next_step": "model training, holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
        "phase13aj_target_feature_diagnostic_result_audit": {
            "enabled": True,
            "audit_role": "Target-feature diagnostic result audit only",
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
            "phase13ai_reports": {
                "conclusion": str(tmp_path / "phase13ai_redesign_panel_conclusion.csv"),
                "gate_report": str(tmp_path / "phase13ai_redesign_panel_gate_report.csv"),
                "target_variant_feasibility_report": str(
                    tmp_path
                    / "phase13ai_redesign_panel_target_variant_feasibility_report.csv"
                ),
                "target_assignment_panel": str(
                    tmp_path / "phase13ai_redesign_panel_target_assignment_panel.csv"
                ),
                "target_distribution_report": str(
                    tmp_path / "phase13ai_redesign_panel_target_distribution_report.csv"
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
                "feature_target_separation_report": str(
                    tmp_path
                    / "phase13ai_redesign_panel_feature_target_separation_report.csv"
                ),
                "redesign_screen_report": str(
                    tmp_path / "phase13ai_redesign_panel_redesign_screen_report.csv"
                ),
            },
            "forbidden_output_paths": [
                str(tmp_path / "phase13ai_model_training_report.csv"),
                str(tmp_path / "phase13ai_holdout_predictions.csv"),
                str(tmp_path / "phase13ai_feature_importance.csv"),
                str(tmp_path / "phase13ai_signal_report.csv"),
            ],
            "next_phase_boundary": {
                "allowed_next_step": "Target-feature redesign interpretation and continuation decision only",
                "forbidden_next_step": "model training, holdout prediction generation, feature importance, signal creation, strategy backtest",
            },
        },
    }


def test_phase13ag_to_13aj_target_feature_redesign_bundle(tmp_path):
    _write_prior_reports(tmp_path)
    _write_dataset(tmp_path)
    config = _config(tmp_path)

    out_ag = save_phase13ag_target_feature_redesign_preregistration(
        config=config,
        reports_dir=tmp_path,
    )
    out_ah = save_phase13ah_target_feature_redesign_readiness_audit(
        config=config,
        reports_dir=tmp_path,
    )
    out_ai = save_phase13ai_target_feature_diagnostic_panel_execution(
        config=config,
        reports_dir=tmp_path,
    )
    out_aj = save_phase13aj_target_feature_diagnostic_result_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_ag["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_ah["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_ai["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_aj["conclusion"].iloc[0]["all_gates_passed"])

    screen = out_ai["redesign_screen_report"]
    assert not screen.empty
    assert not screen["target_variant_selected"].map(bool).any()