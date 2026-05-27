from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.feature_calculation_execution_and_quality_audit import (
    build_phase13i_feature_panel,
    build_phase13j_feature_panel_quality_check,
    save_phase13i_feature_calculation_execution,
    save_phase13j_feature_panel_quality_leakage_audit,
)


def _write_phase13h_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13H",
                "verdict": "Completed — feature calculation readiness audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13h_readiness_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13h_readiness_gate_report.csv", index=False)

    for name in [
        "phase13g_prereg_calculation_registry.csv",
        "phase13g_prereg_output_column_schema.csv",
        "phase13g_prereg_missingness_behaviour.csv",
        "phase13g_prereg_leakage_checks.csv",
        "phase13g_prereg_visual_checks.csv",
        "phase13g_prereg_ml_feature_engineering_lock.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _write_input_data(tmp_path: Path):
    dates = pd.bdate_range("2020-01-01", periods=320)
    close = 100 * (1 + pd.Series(np.linspace(0.0001, 0.0010, len(dates)))).cumprod()

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
    required_feature_ids = [
        "technical_trend_state",
        "technical_momentum_state",
        "technical_volatility_state",
        "technical_drawdown_state",
        "macro_short_rate_state",
        "macro_yield_curve_state",
        "macro_inflation_state",
        "macro_labour_state",
    ]

    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13g_feature_calculation_preregistration_spec": {"enabled": False},
        "phase13h_feature_calculation_readiness_audit": {"enabled": False},
        "phase13i_feature_calculation_execution": {
            "enabled": True,
            "execution_role": "Technical and macro feature calculation execution only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13H",
            "proposed_next_phase": "Phase 13J",
            "allow_feature_calculation": True,
            "allow_feature_panel_creation": True,
            "allow_visual_feature_reports": True,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13h_conclusion": str(
                    tmp_path / "phase13h_readiness_conclusion.csv"
                ),
                "phase13h_gate_report": str(
                    tmp_path / "phase13h_readiness_gate_report.csv"
                ),
                "calculation_registry": str(
                    tmp_path / "phase13g_prereg_calculation_registry.csv"
                ),
                "output_column_schema": str(
                    tmp_path / "phase13g_prereg_output_column_schema.csv"
                ),
                "missingness_behaviour": str(
                    tmp_path / "phase13g_prereg_missingness_behaviour.csv"
                ),
                "leakage_checks": str(tmp_path / "phase13g_prereg_leakage_checks.csv"),
                "visual_checks": str(tmp_path / "phase13g_prereg_visual_checks.csv"),
                "ml_feature_engineering_lock": str(
                    tmp_path / "phase13g_prereg_ml_feature_engineering_lock.csv"
                ),
            },
            "input_data": {
                "technical_price_candidates": [str(tmp_path / "spy_price_panel.csv")],
                "macro_aligned_candidates": [
                    str(tmp_path / "phase10c_macro_aligned_series.csv")
                ],
                "date_column_candidates": ["date", "as_of_date"],
                "close_column_candidates": ["adjusted_close", "close"],
                "macro_columns": {
                    "dgs2": "DGS2",
                    "dgs10": "DGS10",
                    "cpi": "CPIAUCSL",
                    "unrate": "UNRATE",
                },
            },
            "calculation_policy": {
                "contract_version": "phase13g_v1",
                "source_version": "test_source",
                "required_feature_ids": required_feature_ids,
            },
            "phase13j_boundary": {
                "allowed_next_step": "Feature panel quality and leakage audit only",
                "forbidden_next_step": (
                    "signal creation, allocation rule, strategy backtest, "
                    "model training, paper-trading deployment, candidate promotion, "
                    "or final-candidate change"
                ),
                "phase13j_may_audit_feature_panel": True,
                "phase13j_may_audit_leakage": True,
                "phase13j_may_create_signal": False,
                "phase13j_may_train_model": False,
                "phase13j_may_run_backtest": False,
                "phase13j_may_deploy_paper_trading": False,
                "phase13j_may_promote_candidate": False,
            },
        },
        "phase13j_feature_panel_quality_leakage_audit": {
            "enabled": True,
            "audit_role": "Feature panel quality and leakage audit only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13I",
            "proposed_next_phase": "Phase 13K",
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13g_feature_calculation_preregistration_spec": False,
                "phase13h_feature_calculation_readiness_audit": False,
                "phase13i_feature_calculation_execution": True,
                "phase13j_feature_panel_quality_leakage_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13i_reports": {
                "input_source_check": str(tmp_path / "phase13i_input_source_check.csv"),
                "feature_panel": str(tmp_path / "phase13i_feature_panel.csv"),
                "feature_state_timeline": str(
                    tmp_path / "phase13i_feature_state_timeline.csv"
                ),
                "feature_availability_heatmap": str(
                    tmp_path / "phase13i_feature_availability_heatmap.csv"
                ),
                "leakage_audit_panel": str(
                    tmp_path / "phase13i_leakage_audit_panel.csv"
                ),
                "model_feature_matrix_preview": str(
                    tmp_path / "phase13i_model_feature_matrix_preview.csv"
                ),
                "decision_rationale_template": str(
                    tmp_path / "phase13i_decision_rationale_template.csv"
                ),
                "summary": str(tmp_path / "phase13i_summary.csv"),
                "gate_report": str(tmp_path / "phase13i_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13i_conclusion.csv"),
            },
            "quality_thresholds": {
                "min_feature_ids": 8,
                "min_panel_rows": 100,
                "max_leakage_flags": 0,
                "min_available_state_ratio": 0.20,
                "forbidden_columns": [
                    "signal",
                    "allocation",
                    "model_prediction",
                    "strategy_return",
                    "backtest_return",
                    "paper_trade",
                ],
            },
            "phase13k_boundary": {
                "allowed_next_step": (
                    "Feature panel interpretation and model-readiness planning only"
                ),
                "forbidden_next_step": (
                    "signal creation, allocation rule, strategy backtest, "
                    "model training, paper-trading deployment, candidate promotion, "
                    "or final-candidate change"
                ),
                "phase13k_may_interpret_features": True,
                "phase13k_may_plan_model_dataset": True,
                "phase13k_may_create_signal": False,
                "phase13k_may_train_model": False,
                "phase13k_may_run_backtest": False,
                "phase13k_may_deploy_paper_trading": False,
                "phase13k_may_promote_candidate": False,
            },
        },
    }


def test_phase13i_calculates_feature_panel(tmp_path):
    _write_phase13h_reports(tmp_path)
    _write_input_data(tmp_path)
    config = _config(tmp_path)

    price = pd.read_csv(tmp_path / "spy_price_panel.csv")
    price["as_of_date"] = pd.to_datetime(price["date"])
    macro = pd.read_csv(tmp_path / "phase10c_macro_aligned_series.csv")
    macro["as_of_date"] = pd.to_datetime(macro["date"])

    panel = build_phase13i_feature_panel(
        price_frame=price[["as_of_date", "adjusted_close"]],
        macro_frame=macro[["as_of_date", "DGS2", "DGS10", "CPIAUCSL", "UNRATE"]],
        price_source="test_price",
        macro_source="test_macro",
        phase_config=config["phase13i_feature_calculation_execution"],
    )

    assert len(panel) == 320 * 8
    assert panel["feature_id"].nunique() == 8
    assert not bool(panel["leakage_flag"].any())


def test_phase13i_and_13j_save_reports(tmp_path):
    _write_phase13h_reports(tmp_path)
    _write_input_data(tmp_path)
    config = _config(tmp_path)

    out_i = save_phase13i_feature_calculation_execution(
        config=config,
        reports_dir=tmp_path,
    )
    out_j = save_phase13j_feature_panel_quality_leakage_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_i["conclusion"].iloc[0]["all_gates_passed"]
    assert out_j["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13i_feature_panel.csv").exists()
    assert (tmp_path / "phase13j_quality_conclusion.csv").exists()


def test_phase13j_quality_fails_for_tiny_panel(tmp_path):
    tiny = pd.DataFrame(
        {
            "feature_id": ["x"],
            "missingness_state": ["available"],
        }
    )

    check = build_phase13j_feature_panel_quality_check(
        feature_panel=tiny,
        thresholds={"min_panel_rows": 100, "min_feature_ids": 8},
    )

    assert not bool(check["passed"].all())