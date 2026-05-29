from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.macro_long_to_wide_repair_and_reaudit import (
    build_phase13q_macro_repair_panel,
    build_phase13q_macro_wide_panel,
    save_phase13q_macro_long_to_wide_repair_execution,
    save_phase13r_repaired_macro_dataset_quality_audit,
)


def _write_phase13p_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13P",
                "verdict": "Completed — macro feature repair decision/spec passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13p_repair_spec_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13p_repair_spec_gate_report.csv", index=False)

    for name in [
        "phase13p_repair_spec_repair_decision.csv",
        "phase13p_repair_spec_repair_spec.csv",
        "phase13m_ml_feature_dataset_v1.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _write_feature_panel(tmp_path: Path):
    dates = pd.bdate_range("2006-04-28", periods=520)
    technical_ids = [
        "technical_trend_state",
        "technical_momentum_state",
        "technical_volatility_state",
        "technical_drawdown_state",
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
                    "decision_date": date.date(),
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

    pd.DataFrame(rows).to_csv(tmp_path / "phase13i_feature_panel.csv", index=False)


def _write_price_and_long_macro(tmp_path: Path):
    dates = pd.bdate_range("2006-04-28", periods=620)
    close = 100 * (1 + pd.Series(np.linspace(0.0001, 0.001, len(dates)))).cumprod()

    pd.DataFrame(
        {
            "date": dates,
            "adjusted_close": close.values,
        }
    ).to_csv(tmp_path / "spy_price_panel.csv", index=False)

    rows = []
    for date in dates:
        for series_id, value in {
            "DGS2": 2.0,
            "DGS10": 3.0,
            "CPIAUCSL": 250.0 + len(rows) * 0.0001,
            "UNRATE": 4.5,
        }.items():
            rows.append(
                {
                    "source_id": "test",
                    "series_id": series_id,
                    "trading_date": date.date(),
                    "value": value,
                    "available_date": date.date(),
                    "availability_lag_trading_days": 1,
                    "conservative_lag_applied": True,
                }
            )

    pd.DataFrame(rows).to_csv(tmp_path / "phase10c_macro_aligned_series.csv", index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13o_macro_availability_root_cause_diagnostic": {"enabled": False},
        "phase13p_macro_feature_repair_decision_spec": {"enabled": False},
        "phase13q_macro_long_to_wide_repair_execution": {
            "enabled": True,
            "execution_role": (
                "Macro long-to-wide repair execution and guarded dataset "
                "reassembly only"
            ),
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13P",
            "proposed_next_phase": "Phase 13R",
            "allow_macro_repair_execution": True,
            "allow_dataset_reassembly": True,
            "allow_target_recalculation": True,
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
            "source_reports": {
                "phase13p_conclusion": str(
                    tmp_path / "phase13p_repair_spec_conclusion.csv"
                ),
                "phase13p_gate_report": str(
                    tmp_path / "phase13p_repair_spec_gate_report.csv"
                ),
                "phase13p_repair_decision": str(
                    tmp_path / "phase13p_repair_spec_repair_decision.csv"
                ),
                "phase13p_repair_spec": str(
                    tmp_path / "phase13p_repair_spec_repair_spec.csv"
                ),
                "feature_panel": str(tmp_path / "phase13i_feature_panel.csv"),
                "technical_only_dataset": str(
                    tmp_path / "phase13m_ml_feature_dataset_v1.csv"
                ),
            },
            "input_data": {
                "macro_aligned_candidates": [
                    str(tmp_path / "phase10c_macro_aligned_series.csv")
                ],
                "technical_price_candidates": [str(tmp_path / "spy_price_panel.csv")],
                "date_column_candidates": ["trading_date", "date", "as_of_date"],
                "series_column_candidates": ["series_id"],
                "value_column_candidates": ["value"],
                "available_date_column_candidates": ["available_date"],
                "close_column_candidates": ["adjusted_close", "close"],
                "required_macro_series": ["DGS2", "DGS10", "CPIAUCSL", "UNRATE"],
            },
            "macro_repair_policy": {
                "min_macro_available_ratio_to_use": 0.20,
                "min_macro_feature_value_non_null_ratio": 0.20,
                "dataset_label_if_repaired": "multi_factor_technical_macro_dataset_v1",
                "dataset_label_if_blocked": "technical_only_macro_blocked_dataset_v1",
            },
            "dataset_policy": {
                "dataset_id": "phase13q_ml_feature_dataset_v1",
                "common_start_date": "2006-04-28",
                "canonical_endpoint": "2026-05-01",
                "target_horizon_trading_days": 63,
                "primary_supportive_threshold": 0.05,
                "primary_fragile_threshold": -0.05,
                "secondary_fragile_drawdown_threshold": -0.10,
                "train_start": "2006-04-28",
                "train_end": "2007-04-30",
                "validation_start": "2007-05-01",
                "validation_end": "2007-12-31",
                "holdout_start": "2008-01-01",
                "holdout_end": "2026-05-01",
            },
            "phase13r_boundary": {
                "allowed_next_step": (
                    "Repaired macro dataset quality and leakage audit only"
                ),
                "forbidden_next_step": (
                    "model training, model selection, signal creation, allocation "
                    "rule, strategy backtest, paper-trading deployment, candidate "
                    "promotion, or final-candidate change"
                ),
                "phase13r_may_audit_dataset": True,
                "phase13r_may_audit_macro_repair": True,
                "phase13r_may_train_model": False,
                "phase13r_may_create_signal": False,
                "phase13r_may_run_backtest": False,
                "phase13r_may_promote_candidate": False,
            },
        },
        "phase13r_repaired_macro_dataset_quality_audit": {
            "enabled": True,
            "audit_role": "Repaired macro dataset quality and leakage audit only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13Q",
            "proposed_next_phase": "Phase 13S",
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
                "phase13o_macro_availability_root_cause_diagnostic": False,
                "phase13p_macro_feature_repair_decision_spec": False,
                "phase13q_macro_long_to_wide_repair_execution": True,
                "phase13r_repaired_macro_dataset_quality_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13q_reports": {
                "source_report_check": str(tmp_path / "phase13q_repair_source_report_check.csv"),
                "phase13p_result_check": str(tmp_path / "phase13q_repair_phase13p_result_check.csv"),
                "macro_source_check": str(tmp_path / "phase13q_repair_macro_source_check.csv"),
                "macro_wide_panel": str(tmp_path / "phase13q_repair_macro_wide_panel.csv"),
                "macro_repair_panel": str(tmp_path / "phase13q_repair_macro_repair_panel.csv"),
                "macro_availability_report": str(tmp_path / "phase13q_repair_macro_availability_report.csv"),
                "family_usage_report": str(tmp_path / "phase13q_repair_family_usage_report.csv"),
                "reassembled_dataset": str(tmp_path / "phase13q_ml_feature_dataset_v1.csv"),
                "target_summary": str(tmp_path / "phase13q_repair_target_summary.csv"),
                "split_summary": str(tmp_path / "phase13q_repair_split_summary.csv"),
                "dataset_metadata": str(tmp_path / "phase13q_repair_dataset_metadata.csv"),
                "phase13r_boundary_check": str(tmp_path / "phase13q_repair_phase13r_boundary_check.csv"),
                "scope_boundary_check": str(tmp_path / "phase13q_repair_scope_boundary_check.csv"),
                "summary": str(tmp_path / "phase13q_repair_summary.csv"),
                "gate_report": str(tmp_path / "phase13q_repair_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13q_repair_conclusion.csv"),
            },
            "quality_thresholds": {
                "min_dataset_rows": 100,
                "min_value_feature_columns": 8,
                "min_macro_value_feature_columns": 4,
                "min_target_available_ratio": 0.80,
                "min_macro_available_ratio": 0.20,
                "required_dataset_label": "multi_factor_technical_macro_dataset_v1",
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
            "phase13s_boundary": {
                "allowed_next_step": (
                    "ML model training pre-registration and baseline-model "
                    "design spec only"
                ),
                "forbidden_next_step": (
                    "model training execution, model selection, signal creation, "
                    "allocation rule, strategy backtest, paper-trading deployment, "
                    "candidate promotion, or final-candidate change"
                ),
                "phase13s_may_preregister_model_training": True,
                "phase13s_may_define_baseline_models": True,
                "phase13s_may_train_model": False,
                "phase13s_may_create_signal": False,
                "phase13s_may_run_backtest": False,
                "phase13s_may_promote_candidate": False,
            },
        },
    }


def test_phase13q_long_to_wide_macro_repair(tmp_path):
    _write_phase13p_reports(tmp_path)
    _write_feature_panel(tmp_path)
    _write_price_and_long_macro(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase13q_macro_long_to_wide_repair_execution"]

    macro_source = pd.read_csv(tmp_path / "phase10c_macro_aligned_series.csv")
    wide = build_phase13q_macro_wide_panel(
        macro_source=macro_source,
        phase_config=phase_config,
    )
    repair_panel = build_phase13q_macro_repair_panel(
        macro_wide_panel=wide,
        macro_source_path="test_macro",
        phase_config=phase_config,
    )

    assert {"DGS2", "DGS10", "CPIAUCSL", "UNRATE"}.issubset(wide.columns)
    assert repair_panel["feature_id"].nunique() == 4
    assert repair_panel["missingness_state"].eq("available").mean() > 0.20


def test_phase13q_and_13r_save_reports(tmp_path):
    _write_phase13p_reports(tmp_path)
    _write_feature_panel(tmp_path)
    _write_price_and_long_macro(tmp_path)
    config = _config(tmp_path)

    out_q = save_phase13q_macro_long_to_wide_repair_execution(
        config=config,
        reports_dir=tmp_path,
    )
    out_r = save_phase13r_repaired_macro_dataset_quality_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_q["conclusion"].iloc[0]["all_gates_passed"]
    assert out_r["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13q_ml_feature_dataset_v1.csv").exists()
    assert (tmp_path / "phase13r_quality_conclusion.csv").exists()