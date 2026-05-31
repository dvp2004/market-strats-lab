from pathlib import Path

import pandas as pd

from market_strats.analysis.visual_source_identity_decision_bundle import (
    save_phase14e_visual_backtest_interpretation_source_identity_audit,
    save_phase14f_candidate_source_correction_or_workflow_prereg_decision,
)


def _write_phase14_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 14D",
                "verdict": "Completed — non-ML visual backtest result audit passed",
                "all_gates_passed": True,
                "paper_trading_ready": False,
            }
        ]
    ).to_csv(tmp_path / "phase14d_visual_audit_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase14d_visual_audit_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "source_name": "relative_momentum_outputs.Top 3 Equal Weight Relative Momentum Allocator.allocator_result",
                "resolved": True,
                "score": 24,
                "rows": 5034,
                "date_col": "date",
                "candidate_return_col": "strategy_return",
                "benchmark_return_col": "SPY_return",
                "candidate_equity_col": "equity",
            }
        ]
    ).to_csv(
        tmp_path / "phase14c_visual_backtest_candidate_source_resolution_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "series": "candidate",
                "end_value": 55325.075568272296,
                "total_return": 4.5325075568272295,
                "cagr": 0.08940753564163506,
                "annualised_volatility": 0.1713064808283599,
                "sharpe_zero_rf": 0.5861417193392336,
                "max_drawdown": -0.35738851380513426,
                "calmar": 0.25016902387183165,
            },
            {
                "series": "benchmark_spy_buy_hold",
                "end_value": 79306.62045479809,
                "total_return": 6.930662045479809,
                "cagr": 0.10922351106857708,
                "annualised_volatility": 0.19429235853408508,
                "sharpe_zero_rf": 0.6308405103205309,
                "max_drawdown": -0.5518943478436933,
                "calmar": 0.19790655855658665,
            },
        ]
    ).to_csv(tmp_path / "phase14c_visual_backtest_benchmark_comparison.csv", index=False)

    pd.DataFrame([{"metric": "candidate_minus_benchmark_pnl", "value": -23981.54}]).to_csv(
        tmp_path / "phase14c_visual_backtest_money_made_lost_table.csv",
        index=False,
    )
    pd.DataFrame([{"trade_segment_id": 1}]).to_csv(
        tmp_path / "phase14c_visual_backtest_trade_log.csv",
        index=False,
    )
    pd.DataFrame([{"switch_event_id": 1}]).to_csv(
        tmp_path / "phase14c_visual_backtest_switch_event_log.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision_date": "2026-05-01",
                "mode": "1.0",
                "exposure": 0.0,
                "action_template": "cash_or_defensive_preview",
                "candidate_equity": 55325.075568272296,
                "benchmark_equity": 79306.62045479809,
                "paper_trading_status": "preview_only_not_deployment",
                "signal_source": "non_ml_overlay_mode_and_exposure",
                "live_trading_allowed": False,
                "real_money_allowed": False,
            }
        ]
    ).to_csv(
        tmp_path / "phase14c_visual_backtest_signal_template_preview.csv",
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


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase14a_non_ml_visual_backtest_preregistration": {"enabled": False},
        "phase14b_non_ml_visual_backtest_readiness_audit": {"enabled": False},
        "phase14c_non_ml_visual_backtest_report_execution": {"enabled": False},
        "phase14d_non_ml_visual_backtest_result_audit": {"enabled": False},
        "phase14e_visual_backtest_interpretation_source_identity_audit": {
            "enabled": True,
            "audit_role": "Visual backtest interpretation and candidate source identity audit only",
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
            "source_reports": {
                "phase14d_conclusion": str(tmp_path / "phase14d_visual_audit_conclusion.csv"),
                "phase14d_gate_report": str(tmp_path / "phase14d_visual_audit_gate_report.csv"),
                "phase14c_source_resolution": str(tmp_path / "phase14c_visual_backtest_candidate_source_resolution_report.csv"),
                "phase14c_benchmark_comparison": str(tmp_path / "phase14c_visual_backtest_benchmark_comparison.csv"),
                "phase14c_money_made_lost": str(tmp_path / "phase14c_visual_backtest_money_made_lost_table.csv"),
                "phase14c_trade_log": str(tmp_path / "phase14c_visual_backtest_trade_log.csv"),
                "phase14c_switch_event_log": str(tmp_path / "phase14c_visual_backtest_switch_event_log.csv"),
                "phase14c_signal_template_preview": str(tmp_path / "phase14c_visual_backtest_signal_template_preview.csv"),
                "phase13aw_route_selection": str(tmp_path / "phase13aw_route_selection_route_selection_report.csv"),
            },
            "source_identity_policy": {
                "expected_candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
                "required_source_name_fragments": ["phase6b", "loose", "relief"],
                "suspicious_source_name_fragments": [
                    "Top 3 Equal Weight Relative Momentum Allocator",
                    "allocator_result",
                    "relative_momentum_outputs",
                ],
            },
            "canonical_metric_reconciliation": {
                "tolerance": {
                    "cagr_abs_tolerance": 0.005,
                    "calmar_abs_tolerance": 0.025,
                    "max_drawdown_abs_tolerance": 0.025,
                    "final_value_relative_tolerance": 0.05,
                },
                "canonical_systems": [
                    {
                        "system_id": "spy_buy_hold",
                        "label": "SPY Buy & Hold",
                        "expected_cagr": 0.1090,
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
                        "compare_to_phase14c_candidate": True,
                    },
                ],
            },
            "phase14f_boundary": {
                "allowed_next_step_if_failed": "Candidate source correction and visual backtest re-run pre-registration only",
                "allowed_next_step_if_passed": "Paper-trading workflow pre-registration only",
                "forbidden_next_step": "live trading, real-money deployment, paper-trading deployment, candidate promotion",
            },
        },
        "phase14f_candidate_source_correction_or_workflow_prereg_decision": {
            "enabled": True,
            "decision_role": "Candidate source correction or paper-trading workflow pre-registration decision only",
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
            "expected_runtime_flags": {
                "phase14a_non_ml_visual_backtest_preregistration": False,
                "phase14b_non_ml_visual_backtest_readiness_audit": False,
                "phase14c_non_ml_visual_backtest_report_execution": False,
                "phase14d_non_ml_visual_backtest_result_audit": False,
                "phase14e_visual_backtest_interpretation_source_identity_audit": True,
                "phase14f_candidate_source_correction_or_workflow_prereg_decision": True,
                "relative_momentum_allocator": True,
            },
            "source_reports": {
                "phase14e_conclusion": str(tmp_path / "phase14e_source_identity_conclusion.csv"),
                "phase14e_gate_report": str(tmp_path / "phase14e_source_identity_gate_report.csv"),
                "phase14e_source_identity_report": str(tmp_path / "phase14e_source_identity_source_identity_report.csv"),
                "phase14e_metric_reconciliation_report": str(tmp_path / "phase14e_source_identity_metric_reconciliation_report.csv"),
                "phase14e_interpretation_decision_report": str(tmp_path / "phase14e_source_identity_interpretation_decision_report.csv"),
                "phase14e_current_signal_state_report": str(tmp_path / "phase14e_source_identity_current_signal_state_report.csv"),
            },
            "correction_policy": {
                "decision_if_source_identity_failed": "pre_register_candidate_source_correction_and_visual_rerun",
                "intended_candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
                "required_corrected_source_fragments": ["phase6b", "loose", "relief", "execution", "realistic"],
                "corrected_visual_rerun_required_reports": [
                    "equity_curve_vs_spy_buy_hold",
                    "drawdown_curve",
                    "exposure_regime_timeline",
                ],
            },
            "paper_workflow_prereg_policy": {
                "required_future_workflow_reports": [
                    "daily_signal_file_schema",
                    "paper_broker_manual_entry_template",
                ],
            },
            "phase14g_boundary": {
                "allowed_next_step_if_failed": "Candidate source correction implementation and visual backtest re-run only",
                "allowed_next_step_if_passed": "Paper-trading workflow pre-registration only",
                "forbidden_next_step": "live trading, real-money deployment, paper-trading deployment, candidate promotion",
            },
        },
    }


def test_phase14e_to_14f_blocks_paper_workflow_when_source_identity_fails(tmp_path):
    _write_phase14_reports(tmp_path)
    config = _config(tmp_path)

    out_e = save_phase14e_visual_backtest_interpretation_source_identity_audit(
        config=config,
        reports_dir=tmp_path,
    )
    out_f = save_phase14f_candidate_source_correction_or_workflow_prereg_decision(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_e["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_f["conclusion"].iloc[0]["all_gates_passed"])

    source_identity = out_e["source_identity_report"].iloc[0]
    assert bool(source_identity["source_identity_failed"])

    decision = out_f["decision_report"].iloc[0]
    assert decision["decision"] == "pre_register_candidate_source_correction_and_visual_rerun"
    assert bool(decision["correction_required"])
    assert not bool(decision["paper_trading_workflow_preregistration_allowed"])