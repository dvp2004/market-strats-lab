from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.ml_dataset_assembly_and_quality_audit import (
    build_phase13m_macro_guard_report,
    build_phase13m_macro_repair_panel,
    save_phase13m_ml_dataset_assembly_execution,
    save_phase13n_ml_dataset_quality_leakage_audit,
)


def _write_phase13l_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13L",
                "verdict": (
                    "Completed — dataset split and ML target "
                    "pre-registration spec passed"
                ),
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13l_prereg_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13l_prereg_gate_report.csv", index=False)

    for name in [
        "phase13l_prereg_target_design.csv",
        "phase13l_prereg_secondary_target_design.csv",
        "phase13l_prereg_dataset_design.csv",
        "phase13l_prereg_split_design.csv",
        "phase13l_prereg_walk_forward_policy.csv",
        "phase13l_prereg_leakage_control_policy.csv",
        "phase13k_interpretation_feature_availability_summary.csv",
        "phase13k_interpretation_family_coverage_summary.csv",
        "phase13i_model_feature_matrix_preview.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _write_feature_panel(tmp_path: Path):
    dates = pd.bdate_range("2006-04-28", periods=900)
    technical_ids = [
        "technical_trend_state",
        "technical_momentum_state",
        "technical_volatility_state",
        "technical_drawdown_state",
    ]
    macro_ids = [
        "macro_short_rate_state",
        "macro_yield_curve_state",
        "macro_inflation_state",
        "macro_labour_state",
    ]

    rows = []
    for date in dates:
        for feature_id in technical_ids:
            rows.append(
                {
                    "as_of_date": date.date(),
                    "observation_date": date.date(),
                    "release_date": "",
                    "availability_date": date.date(),
                    "decision_date": (date + pd.offsets.BDay(1)).date(),
                    "family_id": "technical",
                    "feature_id": feature_id,
                    "formula_id": f"{feature_id}_formula",
                    "source_name": "test",
                    "source_version": "test",
                    "raw_inputs_available": True,
                    "feature_value": 1.0,
                    "feature_state": "supportive",
                    "state_reason": "test",
                    "missingness_state": "available",
                    "leakage_flag": False,
                    "contract_version": "test",
                }
            )

        for feature_id in macro_ids:
            rows.append(
                {
                    "as_of_date": date.date(),
                    "observation_date": date.date(),
                    "release_date": "",
                    "availability_date": date.date(),
                    "decision_date": (date + pd.offsets.BDay(1)).date(),
                    "family_id": "macro",
                    "feature_id": feature_id,
                    "formula_id": f"{feature_id}_formula",
                    "source_name": "test",
                    "source_version": "test",
                    "raw_inputs_available": False,
                    "feature_value": np.nan,
                    "feature_state": "unavailable",
                    "state_reason": "macro unavailable",
                    "missingness_state": "unavailable",
                    "leakage_flag": False,
                    "contract_version": "test",
                }
            )

    pd.DataFrame(rows).to_csv(tmp_path / "phase13i_feature_panel.csv", index=False)


def _write_price_and_macro(tmp_path: Path):
    dates = pd.bdate_range("2006-04-28", periods=1000)
    close = 100 * (1 + pd.Series(np.linspace(0.0001, 0.001, len(dates)))).cumprod()

    pd.DataFrame(
        {
            "date": dates,
            "adjusted_close": close.values,
        }
    ).to_csv(tmp_path / "spy_price_panel.csv", index=False)

    pd.DataFrame(
        {
            "date": dates,
            "DGS2": np.linspace(1.0, 5.0, len(dates)),
            "DGS10": np.linspace(2.0, 5.5, len(dates)),
            "CPIAUCSL": np.linspace(250, 280, len(dates)),
            "UNRATE": np.linspace(4.0, 6.5, len(dates)),
        }
    ).to_csv(tmp_path / "phase10c_macro_aligned_series.csv", index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13k_feature_panel_interpretation_model_readiness": {"enabled": False},
        "phase13l_dataset_split_target_preregistration_spec": {"enabled": False},
        "phase13m_ml_dataset_assembly_execution": {
            "enabled": True,
            "execution_role": (
                "ML dataset assembly execution with macro availability guard only"
            ),
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13L",
            "proposed_next_phase": "Phase 13N",
            "allow_dataset_assembly_execution": True,
            "allow_target_calculation": True,
            "allow_macro_availability_repair": True,
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
            "source_reports": {
                "phase13l_conclusion": str(
                    tmp_path / "phase13l_prereg_conclusion.csv"
                ),
                "phase13l_gate_report": str(
                    tmp_path / "phase13l_prereg_gate_report.csv"
                ),
                "phase13l_target_design": str(
                    tmp_path / "phase13l_prereg_target_design.csv"
                ),
                "phase13l_secondary_target_design": str(
                    tmp_path / "phase13l_prereg_secondary_target_design.csv"
                ),
                "phase13l_dataset_design": str(
                    tmp_path / "phase13l_prereg_dataset_design.csv"
                ),
                "phase13l_split_design": str(
                    tmp_path / "phase13l_prereg_split_design.csv"
                ),
                "phase13l_walk_forward_policy": str(
                    tmp_path / "phase13l_prereg_walk_forward_policy.csv"
                ),
                "phase13l_leakage_control_policy": str(
                    tmp_path / "phase13l_prereg_leakage_control_policy.csv"
                ),
                "feature_panel": str(tmp_path / "phase13i_feature_panel.csv"),
                "model_feature_matrix_preview": str(
                    tmp_path / "phase13i_model_feature_matrix_preview.csv"
                ),
                "phase13k_availability_summary": str(
                    tmp_path
                    / "phase13k_interpretation_feature_availability_summary.csv"
                ),
                "phase13k_family_coverage_summary": str(
                    tmp_path / "phase13k_interpretation_family_coverage_summary.csv"
                ),
            },
            "input_data": {
                "technical_price_candidates": [str(tmp_path / "spy_price_panel.csv")],
                "macro_aligned_candidates": [
                    str(tmp_path / "phase10c_macro_aligned_series.csv")
                ],
                "date_column_candidates": ["date", "as_of_date"],
                "close_column_candidates": ["adjusted_close", "close"],
                "macro_column_aliases": {
                    "DGS2": ["DGS2"],
                    "DGS10": ["DGS10"],
                    "CPIAUCSL": ["CPIAUCSL"],
                    "UNRATE": ["UNRATE"],
                },
            },
            "macro_availability_guard": {
                "min_macro_available_ratio_to_use": 0.20,
                "repair_attempt_required": True,
                "block_macro_if_repair_fails": True,
                "dataset_label_if_repaired": "multi_factor_technical_macro_dataset_v1",
                "dataset_label_if_blocked": "technical_only_macro_blocked_dataset_v1",
            },
            "dataset_policy": {
                "dataset_id": "phase13m_ml_feature_dataset_v1",
                "common_start_date": "2006-04-28",
                "canonical_endpoint": "2026-05-01",
                "target_horizon_trading_days": 63,
                "train_start": "2006-04-28",
                "train_end": "2007-04-30",
                "validation_start": "2007-05-01",
                "validation_end": "2007-12-31",
                "holdout_start": "2008-01-01",
                "holdout_end": "2026-05-01",
                "primary_supportive_threshold": 0.05,
                "primary_fragile_threshold": -0.05,
                "secondary_fragile_drawdown_threshold": -0.10,
            },
            "phase13n_boundary": {
                "allowed_next_step": "ML dataset quality and leakage audit only",
                "forbidden_next_step": (
                    "model training, model selection, signal creation, allocation "
                    "rule, strategy backtest, paper-trading deployment, candidate "
                    "promotion, or final-candidate change"
                ),
                "phase13n_may_audit_dataset": True,
                "phase13n_may_audit_macro_guard": True,
                "phase13n_may_train_model": False,
                "phase13n_may_select_model": False,
                "phase13n_may_create_signal": False,
                "phase13n_may_run_backtest": False,
                "phase13n_may_promote_candidate": False,
            },
        },
        "phase13n_ml_dataset_quality_leakage_audit": {
            "enabled": True,
            "audit_role": "ML dataset quality and leakage audit only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13M",
            "proposed_next_phase": "Phase 13O",
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_feature_importance": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13k_feature_panel_interpretation_model_readiness": False,
                "phase13l_dataset_split_target_preregistration_spec": False,
                "phase13m_ml_dataset_assembly_execution": True,
                "phase13n_ml_dataset_quality_leakage_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13m_reports": {
                "source_report_check": str(
                    tmp_path / "phase13m_dataset_source_report_check.csv"
                ),
                "phase13l_result_check": str(
                    tmp_path / "phase13m_dataset_phase13l_result_check.csv"
                ),
                "input_source_check": str(
                    tmp_path / "phase13m_dataset_input_source_check.csv"
                ),
                "macro_guard_report": str(
                    tmp_path / "phase13m_dataset_macro_guard_report.csv"
                ),
                "macro_repair_panel": str(
                    tmp_path / "phase13m_dataset_macro_repair_panel.csv"
                ),
                "family_usage_report": str(
                    tmp_path / "phase13m_dataset_family_usage_report.csv"
                ),
                "assembled_dataset": str(
                    tmp_path / "phase13m_ml_feature_dataset_v1.csv"
                ),
                "target_summary": str(
                    tmp_path / "phase13m_dataset_target_summary.csv"
                ),
                "split_summary": str(
                    tmp_path / "phase13m_dataset_split_summary.csv"
                ),
                "dataset_metadata": str(
                    tmp_path / "phase13m_dataset_dataset_metadata.csv"
                ),
                "phase13n_boundary_check": str(
                    tmp_path / "phase13m_dataset_phase13n_boundary_check.csv"
                ),
                "scope_boundary_check": str(
                    tmp_path / "phase13m_dataset_scope_boundary_check.csv"
                ),
                "summary": str(tmp_path / "phase13m_dataset_summary.csv"),
                "gate_report": str(tmp_path / "phase13m_dataset_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13m_dataset_conclusion.csv"),
            },
            "quality_thresholds": {
                "min_dataset_rows": 100,
                "min_feature_value_columns": 4,
                "min_target_available_ratio": 0.80,
                "forbidden_columns": [
                    "signal",
                    "allocation",
                    "model_prediction",
                    "strategy_return",
                    "backtest_return",
                    "paper_trade",
                    "feature_importance",
                ],
            },
            "phase13o_boundary": {
                "allowed_next_step": (
                    "ML model training pre-registration and baseline-model "
                    "design spec only"
                ),
                "forbidden_next_step": (
                    "model training execution, model selection, signal creation, "
                    "allocation rule, strategy backtest, paper-trading deployment, "
                    "candidate promotion, or final-candidate change"
                ),
                "phase13o_may_preregister_model_training": True,
                "phase13o_may_define_baseline_models": True,
                "phase13o_may_define_metrics": True,
                "phase13o_may_train_model": False,
                "phase13o_may_select_model": False,
                "phase13o_may_create_signal": False,
                "phase13o_may_run_backtest": False,
                "phase13o_may_deploy_paper_trading": False,
                "phase13o_may_promote_candidate": False,
            },
        },
    }


def test_phase13m_macro_guard_repairs_macro_availability(tmp_path):
    _write_feature_panel(tmp_path)
    _write_price_and_macro(tmp_path)
    config = _config(tmp_path)

    feature_panel = pd.read_csv(tmp_path / "phase13i_feature_panel.csv")
    macro_frame = pd.read_csv(tmp_path / "phase10c_macro_aligned_series.csv")
    macro_frame["as_of_date"] = pd.to_datetime(macro_frame["date"])

    repair_panel = build_phase13m_macro_repair_panel(
        macro_frame=macro_frame[["as_of_date", "DGS2", "DGS10", "CPIAUCSL", "UNRATE"]],
        macro_source="test_macro",
    )
    guard = build_phase13m_macro_guard_report(
        feature_panel=feature_panel,
        macro_repair_panel=repair_panel,
        phase_config=config["phase13m_ml_dataset_assembly_execution"],
    )

    assert guard.iloc[0]["current_macro_available_ratio"] == 0.0
    assert guard.iloc[0]["repaired_macro_available_ratio"] > 0.20
    assert bool(guard.iloc[0]["repaired_successfully"])


def test_phase13m_and_13n_save_reports(tmp_path):
    _write_phase13l_reports(tmp_path)
    _write_feature_panel(tmp_path)
    _write_price_and_macro(tmp_path)
    config = _config(tmp_path)

    out_m = save_phase13m_ml_dataset_assembly_execution(
        config=config,
        reports_dir=tmp_path,
    )
    out_n = save_phase13n_ml_dataset_quality_leakage_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_m["conclusion"].iloc[0]["all_gates_passed"]
    assert out_n["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13m_ml_feature_dataset_v1.csv").exists()
    assert (tmp_path / "phase13n_quality_conclusion.csv").exists()