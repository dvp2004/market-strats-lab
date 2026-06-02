from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.corrected_visual_source_rerun_bundle import (
    save_phase14g_candidate_source_correction_visual_rerun,
    save_phase14h_corrected_visual_backtest_audit_reconciliation_decision,
)


def _write_phase14f_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 14F",
                "verdict": "Completed — candidate source correction/workflow decision passed",
                "all_gates_passed": True,
                "correction_required": True,
                "paper_trading_workflow_preregistration_allowed": False,
            }
        ]
    ).to_csv(tmp_path / "phase14f_source_correction_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase14f_source_correction_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "pre_register_candidate_source_correction_and_visual_rerun",
                "correction_required": True,
                "visual_rerun_required": True,
                "paper_trading_workflow_preregistration_allowed": False,
            }
        ]
    ).to_csv(tmp_path / "phase14f_source_correction_decision_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "correction_required": True,
                "intended_candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
                "required_corrected_source_fragments": "phase6b; loose; relief; execution; realistic",
            }
        ]
    ).to_csv(
        tmp_path / "phase14f_source_correction_correction_spec_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "selected_route_id": "route_3_non_ml_overlay_visual_backtest_paper_readiness",
                "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
                "selected": True,
            }
        ]
    ).to_csv(tmp_path / "phase13aw_route_selection_route_selection_report.csv", index=False)


def _mock_outputs():
    dates = pd.bdate_range("2020-01-01", periods=1300)
    strategy_return = np.full(len(dates), 0.00062)
    benchmark_return = np.full(len(dates), 0.00042)
    exposure = np.where(np.arange(len(dates)) % 80 < 60, 1.0, 0.0)
    mode = np.where(exposure > 0.5, "risk_on", "risk_off")

    intended = pd.DataFrame(
        {
            "decision_date": dates,
            "strategy_return": strategy_return,
            "benchmark_return": benchmark_return,
            "exposure": exposure,
            "mode": mode,
        }
    )

    raw_allocator = pd.DataFrame(
        {
            "decision_date": dates,
            "strategy_return": strategy_return * 0.5,
            "benchmark_return": benchmark_return,
            "exposure": exposure,
            "mode": mode,
        }
    )

    return {
        "phase6b_loose_relief_execution_realistic_overlay": intended,
        "Top 3 Equal Weight Relative Momentum Allocator": {
            "allocator_result": raw_allocator,
        },
    }


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase14e_visual_backtest_interpretation_source_identity_audit": {
            "enabled": False,
        },
        "phase14f_candidate_source_correction_or_workflow_prereg_decision": {
            "enabled": False,
        },
        "phase14g_candidate_source_correction_visual_rerun": {
            "enabled": True,
            "execution_role": "Candidate source correction implementation and corrected visual backtest re-run only",
            "implementation_classification": "A/B",
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "source_reports": {
                "phase14f_conclusion": str(tmp_path / "phase14f_source_correction_conclusion.csv"),
                "phase14f_gate_report": str(tmp_path / "phase14f_source_correction_gate_report.csv"),
                "phase14f_decision_report": str(tmp_path / "phase14f_source_correction_decision_report.csv"),
                "phase14f_correction_spec_report": str(tmp_path / "phase14f_source_correction_correction_spec_report.csv"),
                "phase13aw_route_selection": str(tmp_path / "phase13aw_route_selection_route_selection_report.csv"),
            },
            "strict_source_resolution_policy": {
                "required_source_name_fragments": [
                    "phase6b",
                    "loose",
                    "relief",
                    "execution",
                    "realistic",
                ],
                "suspicious_raw_allocator_fragments": [
                    "Top 3 Equal Weight Relative Momentum Allocator",
                    "allocator_result",
                    "relative_momentum_outputs",
                ],
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
            "canonical_metric_reconciliation": {
                "tolerance": {
                    "cagr_abs_tolerance": 1.0,
                    "calmar_abs_tolerance": 100.0,
                    "max_drawdown_abs_tolerance": 1.0,
                    "final_value_relative_tolerance": 10.0,
                },
                "canonical_systems": [
                    {
                        "system_id": "spy_buy_hold",
                        "label": "SPY Buy & Hold",
                        "expected_cagr": 0.109,
                        "expected_calmar": 0.197,
                        "expected_max_drawdown": -0.5519,
                        "required_in_side_by_side": True,
                    },
                    {
                        "system_id": "spy_12m_momentum",
                        "label": "SPY 12M Momentum",
                        "expected_cagr": 0.0968,
                        "expected_calmar": 0.287,
                        "expected_max_drawdown": -0.3372,
                        "required_in_side_by_side": True,
                    },
                    {
                        "system_id": "phase4_deep_drawdown_guard_execution_realistic",
                        "label": "Phase 4 deep_drawdown_guard execution-realistic baseline",
                        "expected_cagr": 0.0993,
                        "expected_calmar": 0.412,
                        "expected_max_drawdown": -0.2412,
                        "required_in_side_by_side": True,
                    },
                    {
                        "system_id": "phase6b_loose_relief_execution_realistic_overlay",
                        "label": "Phase 6B/6C loose_relief execution-realistic candidate",
                        "expected_cagr": 0.1035,
                        "expected_calmar": 0.429,
                        "expected_max_drawdown": -0.2412,
                        "expected_final_value": 71779.16,
                        "required_in_side_by_side": True,
                        "compare_to_corrected_candidate": True,
                    },
                ],
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
            "phase14h_boundary": {
                "allowed_next_step": "Corrected visual backtest audit and reconciliation decision only",
                "forbidden_next_step": "paper-trading workflow pre-registration, live trading, real-money deployment, paper-trading deployment, candidate promotion",
            },
        },
        "phase14h_corrected_visual_backtest_audit_reconciliation_decision": {
            "enabled": True,
            "audit_role": "Corrected visual backtest audit and reconciliation decision only",
            "implementation_classification": "B",
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "expected_runtime_flags": {
                "phase14e_visual_backtest_interpretation_source_identity_audit": False,
                "phase14f_candidate_source_correction_or_workflow_prereg_decision": False,
                "phase14g_candidate_source_correction_visual_rerun": True,
                "phase14h_corrected_visual_backtest_audit_reconciliation_decision": True,
                "relative_momentum_allocator": True,
            },
            "phase14g_reports": {
                "conclusion": str(tmp_path / "phase14g_corrected_visual_conclusion.csv"),
                "gate_report": str(tmp_path / "phase14g_corrected_visual_gate_report.csv"),
                "strict_source_resolution_report": str(tmp_path / "phase14g_corrected_visual_strict_source_resolution_report.csv"),
                "rejected_source_report": str(tmp_path / "phase14g_corrected_visual_rejected_source_report.csv"),
                "benchmark_comparison": str(tmp_path / "phase14g_corrected_visual_benchmark_comparison.csv"),
                "metric_reconciliation_report": str(tmp_path / "phase14g_corrected_visual_metric_reconciliation_report.csv"),
                "side_by_side_comparison_report": str(tmp_path / "phase14g_corrected_visual_side_by_side_comparison_report.csv"),
                "current_signal_state_report": str(tmp_path / "phase14g_corrected_visual_current_signal_state_report.csv"),
                "equity_curve": str(tmp_path / "phase14g_corrected_visual_equity_curve.csv"),
                "drawdown_curve": str(tmp_path / "phase14g_corrected_visual_drawdown_curve.csv"),
                "exposure_timeline": str(tmp_path / "phase14g_corrected_visual_exposure_timeline.csv"),
                "trade_log": str(tmp_path / "phase14g_corrected_visual_trade_log.csv"),
                "switch_event_log": str(tmp_path / "phase14g_corrected_visual_switch_event_log.csv"),
                "money_made_lost": str(tmp_path / "phase14g_corrected_visual_money_made_lost_table.csv"),
                "rolling_relative_performance": str(tmp_path / "phase14g_corrected_visual_rolling_relative_performance.csv"),
                "signal_template_preview": str(tmp_path / "phase14g_corrected_visual_signal_template_preview.csv"),
            },
            "chart_files": [
                str(tmp_path / "phase14g_corrected_visual_equity_curve.png"),
                str(tmp_path / "phase14g_corrected_visual_drawdown_curve.png"),
                str(tmp_path / "phase14g_corrected_visual_exposure_timeline.png"),
                str(tmp_path / "phase14g_corrected_visual_rolling_relative_performance.png"),
            ],
            "decision_policy": {
                "decision_if_passed": "allow_paper_workflow_preregistration_next",
                "decision_if_failed": "block_paper_workflow_and_continue_source_correction",
            },
            "phase14i_boundary": {
                "allowed_next_step_if_passed": "Paper-trading workflow pre-registration only",
                "allowed_next_step_if_failed": "Candidate source export/correction or route pause only",
                "forbidden_next_step": "live trading, real-money deployment, paper-trading deployment, candidate promotion",
            },
        },
    }


def test_phase14g_to_14h_corrected_source_rerun(tmp_path):
    _write_phase14f_reports(tmp_path)
    config = _config(tmp_path)
    outputs = _mock_outputs()

    out_g = save_phase14g_candidate_source_correction_visual_rerun(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs=outputs,
    )
    out_h = save_phase14h_corrected_visual_backtest_audit_reconciliation_decision(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_g["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_h["conclusion"].iloc[0]["all_gates_passed"])

    source = out_g["strict_source_resolution_report"].iloc[0]
    assert bool(source["corrected_source_identity_passed"])
    assert "phase6b_loose_relief_execution_realistic_overlay" in source["source_name"]

    decision = out_h["reconciliation_decision_report"].iloc[0]
    assert bool(decision["corrected_source_identity_passed"])
    assert not bool(decision["paper_trading_ready"])