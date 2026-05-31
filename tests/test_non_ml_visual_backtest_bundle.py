from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.non_ml_visual_backtest_bundle import (
    save_phase14a_non_ml_visual_backtest_preregistration,
    save_phase14b_non_ml_visual_backtest_readiness_audit,
    save_phase14c_non_ml_visual_backtest_report_execution,
    save_phase14d_non_ml_visual_backtest_result_audit,
)


def _write_phase13aw_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13AW",
                "verdict": "Completed — paper-trading candidate route selection passed",
                "all_gates_passed": True,
                "selected_route_id": "route_3_non_ml_overlay_visual_backtest_paper_readiness",
            }
        ]
    ).to_csv(tmp_path / "phase13aw_route_selection_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase13aw_route_selection_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "selected_route_id": "route_3_non_ml_overlay_visual_backtest_paper_readiness",
                "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
                "selected": True,
                "model_training_permission": False,
                "paper_trading_permission": False,
            }
        ]
    ).to_csv(tmp_path / "phase13aw_route_selection_route_selection_report.csv", index=False)


def _mock_outputs():
    dates = pd.bdate_range("2020-01-01", periods=1300)
    strategy_return = np.where(np.arange(len(dates)) % 20 < 12, 0.0007, -0.0002)
    benchmark_return = np.full(len(dates), 0.00045)
    exposure = np.where(np.arange(len(dates)) % 60 < 40, 1.0, 0.0)
    mode = np.where(exposure > 0.5, "risk_on", "risk_off")

    frame = pd.DataFrame(
        {
            "decision_date": dates,
            "strategy_return": strategy_return,
            "benchmark_return": benchmark_return,
            "exposure": exposure,
            "mode": mode,
        }
    )

    return {"phase6b_loose_relief_execution_realistic_overlay": frame}


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13av_ml_branch_commercial_decision": {"enabled": False},
        "phase13aw_paper_trading_candidate_route_selection": {"enabled": False},
        "phase14a_non_ml_visual_backtest_preregistration": {
            "enabled": True,
            "spec_role": "Non-ML paper-trading candidate visual backtest and signal-mapping pre-registration only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "candidate_route_id": "route_3_non_ml_overlay_visual_backtest_paper_readiness",
            "benchmark_id": "SPY Buy & Hold",
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_paper_trading_ready_claim": False,
            "source_reports": {
                "phase13aw_conclusion": str(tmp_path / "phase13aw_route_selection_conclusion.csv"),
                "phase13aw_gate_report": str(tmp_path / "phase13aw_route_selection_gate_report.csv"),
                "phase13aw_route_selection_report": str(tmp_path / "phase13aw_route_selection_route_selection_report.csv"),
            },
            "visual_source_policy": {
                "candidate_return_columns": ["strategy_return"],
                "benchmark_return_columns": ["benchmark_return"],
                "candidate_equity_columns": ["strategy_equity"],
                "benchmark_equity_columns": ["benchmark_equity"],
                "price_columns": ["close"],
                "exposure_columns": ["exposure"],
                "mode_columns": ["mode"],
                "date_columns": ["decision_date"],
            },
            "artefact_registry": [
                {"artefact_key": "equity_curve", "required": True, "csv_path": "x", "chart_path": "x"},
                {"artefact_key": "drawdown_curve", "required": True, "csv_path": "x", "chart_path": "x"},
                {"artefact_key": "exposure_timeline", "required": True, "csv_path": "x", "chart_path": "x"},
                {"artefact_key": "trade_log", "required": True, "csv_path": "x", "chart_path": ""},
                {"artefact_key": "switch_event_log", "required": True, "csv_path": "x", "chart_path": ""},
                {"artefact_key": "money_made_lost", "required": True, "csv_path": "x", "chart_path": ""},
                {"artefact_key": "benchmark_comparison", "required": True, "csv_path": "x", "chart_path": ""},
                {"artefact_key": "rolling_relative_performance", "required": True, "csv_path": "x", "chart_path": "x"},
                {"artefact_key": "paper_trading_signal_template_preview", "required": True, "csv_path": "x", "chart_path": ""},
            ],
            "signal_mapping_preview_policy": {
                "preview_only": True,
                "current_signal_source": "non_ml_overlay_mode_and_exposure",
            },
            "phase14b_boundary": {
                "allowed_next_step": "Non-ML visual backtest readiness audit only",
                "forbidden_next_step": "live trading, real-money deployment, feature importance, candidate promotion",
            },
            "phase14c_boundary": {
                "allowed_future_step": "Non-ML visual backtest report execution only",
                "forbidden_future_step": "live trading, real-money deployment, feature importance, candidate promotion",
            },
        },
        "phase14b_non_ml_visual_backtest_readiness_audit": {
            "enabled": True,
            "audit_role": "Non-ML visual backtest readiness audit only",
            "implementation_classification": "B",
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_paper_trading_ready_claim": False,
            "expected_runtime_flags": {
                "phase13av_ml_branch_commercial_decision": False,
                "phase13aw_paper_trading_candidate_route_selection": False,
                "phase14a_non_ml_visual_backtest_preregistration": True,
                "phase14b_non_ml_visual_backtest_readiness_audit": True,
                "phase14c_non_ml_visual_backtest_report_execution": True,
                "phase14d_non_ml_visual_backtest_result_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase14a_reports": {
                "conclusion": str(tmp_path / "phase14a_visual_prereg_conclusion.csv"),
                "gate_report": str(tmp_path / "phase14a_visual_prereg_gate_report.csv"),
                "artefact_registry": str(tmp_path / "phase14a_visual_prereg_artefact_registry.csv"),
                "signal_mapping_preview_policy": str(tmp_path / "phase14a_visual_prereg_signal_mapping_preview_policy.csv"),
                "visual_source_policy": str(tmp_path / "phase14a_visual_prereg_visual_source_policy.csv"),
            },
            "readiness_thresholds": {"min_rows": 1000},
            "phase14c_boundary": {
                "allowed_next_step": "Non-ML visual backtest report execution only",
                "forbidden_next_step": "live trading, real-money deployment, feature importance, candidate promotion",
            },
        },
        "phase14c_non_ml_visual_backtest_report_execution": {
            "enabled": True,
            "execution_role": "Non-ML visual backtest report execution only",
            "implementation_classification": "A",
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_paper_trading_ready_claim": False,
            "source_reports": {
                "phase14b_conclusion": str(tmp_path / "phase14b_visual_readiness_conclusion.csv"),
                "phase14b_gate_report": str(tmp_path / "phase14b_visual_readiness_gate_report.csv"),
                "artefact_registry": str(tmp_path / "phase14a_visual_prereg_artefact_registry.csv"),
                "visual_source_policy": str(tmp_path / "phase14a_visual_prereg_visual_source_policy.csv"),
            },
            "report_policy": {
                "initial_capital": 10000.0,
                "rolling_window_days": 63,
                "annualisation_days": 252,
                "preview_signal_rows": 25,
                "chart_dpi": 80,
                "chart_width": 8,
                "chart_height": 4,
            },
            "phase14d_boundary": {
                "allowed_next_step": "Non-ML visual backtest result audit only",
                "forbidden_next_step": "live trading, real-money deployment, feature importance, candidate promotion",
            },
        },
        "phase14d_non_ml_visual_backtest_result_audit": {
            "enabled": True,
            "audit_role": "Non-ML visual backtest result audit only",
            "implementation_classification": "B",
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_paper_trading_ready_claim": False,
            "phase14c_reports": {
                "conclusion": str(tmp_path / "phase14c_visual_backtest_conclusion.csv"),
                "gate_report": str(tmp_path / "phase14c_visual_backtest_gate_report.csv"),
                "equity_curve": str(tmp_path / "phase14c_visual_backtest_equity_curve.csv"),
                "drawdown_curve": str(tmp_path / "phase14c_visual_backtest_drawdown_curve.csv"),
                "exposure_timeline": str(tmp_path / "phase14c_visual_backtest_exposure_timeline.csv"),
                "trade_log": str(tmp_path / "phase14c_visual_backtest_trade_log.csv"),
                "switch_event_log": str(tmp_path / "phase14c_visual_backtest_switch_event_log.csv"),
                "money_made_lost": str(tmp_path / "phase14c_visual_backtest_money_made_lost_table.csv"),
                "benchmark_comparison": str(tmp_path / "phase14c_visual_backtest_benchmark_comparison.csv"),
                "rolling_relative_performance": str(tmp_path / "phase14c_visual_backtest_rolling_relative_performance.csv"),
                "signal_template_preview": str(tmp_path / "phase14c_visual_backtest_signal_template_preview.csv"),
            },
            "chart_files": [
                str(tmp_path / "phase14c_visual_backtest_equity_curve.png"),
                str(tmp_path / "phase14c_visual_backtest_drawdown_curve.png"),
                str(tmp_path / "phase14c_visual_backtest_exposure_timeline.png"),
                str(tmp_path / "phase14c_visual_backtest_rolling_relative_performance.png"),
            ],
            "forbidden_claims": [
                "paper_trading_ready",
                "live_trading_ready",
                "real_money_ready",
                "candidate_promoted",
            ],
            "phase14e_boundary": {
                "allowed_next_step": "Visual backtest interpretation and paper-trading readiness decision only",
                "forbidden_next_step": "live trading, real-money deployment, feature importance, candidate promotion",
            },
        },
    }


def test_phase14a_to_14d_visual_backtest_bundle(tmp_path):
    _write_phase13aw_reports(tmp_path)
    config = _config(tmp_path)
    outputs = _mock_outputs()

    out_a = save_phase14a_non_ml_visual_backtest_preregistration(
        config=config,
        reports_dir=tmp_path,
    )
    out_b = save_phase14b_non_ml_visual_backtest_readiness_audit(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs=outputs,
    )
    out_c = save_phase14c_non_ml_visual_backtest_report_execution(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs=outputs,
    )
    out_d = save_phase14d_non_ml_visual_backtest_result_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_a["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_b["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_c["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_d["conclusion"].iloc[0]["all_gates_passed"])

    assert len(out_c["equity_curve"]) == 1300
    assert not bool(out_d["conclusion"].iloc[0]["paper_trading_ready"])