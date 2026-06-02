from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.operational_signal_reconstruction import (
    save_phase15c_operational_switch_signal_reconstruction,
    save_phase15d_current_signal_freshness_switch_audit,
)


def _write_source_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 15B",
                "verdict": "Completed — paper-trading workflow readiness audit passed with readiness blocked",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase15b_paper_workflow_readiness_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase15b_paper_workflow_readiness_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "paper_trading_readiness_blocked_operational_repairs_required",
                "paper_trading_ready": False,
            }
        ]
    ).to_csv(
        tmp_path / "phase15b_paper_workflow_readiness_readiness_decision_report.csv",
        index=False,
    )

    dates = pd.bdate_range("2026-05-25", periods=7)
    exposure = [1, 1, 0, 0, 1, 1, 0]
    mode = ["offensive_spy" if x == 1 else "defensive_or_cash" for x in exposure]

    pd.DataFrame(
        {
            "decision_date": dates,
            "strategy_return": np.full(len(dates), 0.001),
            "SPY_return": np.full(len(dates), 0.001),
            "candidate_equity": np.linspace(10000, 10100, len(dates)),
            "benchmark_equity": np.linspace(10000, 10080, len(dates)),
            "exposure": exposure,
            "mode": mode,
            "turnover": pd.Series(exposure).diff().abs().fillna(0.0),
            "applied_overlay_slippage_bps": 5.0,
            "overlay_slippage_cost_pct": 0.0,
        }
    ).to_csv(
        tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv",
        index=False,
    )


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase15a_paper_trading_workflow_preregistration": {"enabled": False},
        "phase15b_paper_trading_workflow_readiness_audit": {"enabled": False},
        "phase15c_operational_switch_signal_reconstruction": {
            "enabled": True,
            "execution_role": "Operational switch and current signal reconstruction implementation only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "exported_daily_file": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv"),
            "source_reports": {
                "phase15b_conclusion": str(tmp_path / "phase15b_paper_workflow_readiness_conclusion.csv"),
                "phase15b_gate_report": str(tmp_path / "phase15b_paper_workflow_readiness_gate_report.csv"),
                "phase15b_readiness_decision": str(tmp_path / "phase15b_paper_workflow_readiness_readiness_decision_report.csv"),
            },
            "candidate_switch_source_files": [],
            "switch_reconstruction_policy": {
                "expected_switch_count": 3,
                "switch_count_abs_tolerance": 0,
            },
            "required_switch_event_columns": [
                "switch_event_id",
                "decision_date",
                "previous_mode",
                "current_mode",
                "previous_exposure",
                "current_exposure",
                "switch_triggered",
                "transition_type",
                "switch_reason",
                "raw_signal",
                "confirmed_signal",
                "deep_drawdown_guard_state",
                "loose_relief_state",
                "turnover",
                "applied_overlay_slippage_bps",
                "overlay_slippage_cost_pct",
                "source_candidate_system_id",
                "signal_validity_flag",
            ],
            "current_signal_policy": {
                "audit_current_date": "2026-06-02",
                "canonical_backtest_endpoint": "2026-05-01",
                "max_signal_staleness_days_for_readiness": 3,
                "require_data_beyond_canonical_endpoint": True,
            },
            "required_current_signal_columns": [
                "signal_date",
                "data_as_of_date",
                "generated_at_utc",
                "candidate_system_id",
                "data_source",
                "current_mode",
                "previous_mode",
                "current_exposure",
                "previous_exposure",
                "target_action",
                "switch_triggered",
                "switch_reason",
                "signal_validity_flag",
                "data_freshness_flag",
                "paper_trading_allowed",
                "paper_readiness_status",
                "blocking_warnings",
                "benchmark_spy_close_or_return_source",
            ],
            "allow_broker_api_integration": False,
            "allow_paper_trading_deployment": False,
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "phase15d_boundary": {
                "allowed_next_step": "Current signal freshness and switch mechanics audit only",
                "forbidden_next_step": "broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15d_current_signal_freshness_switch_audit": {
            "enabled": True,
            "audit_role": "Current signal freshness and switch mechanics audit only",
            "implementation_classification": "B",
            "allow_broker_api_integration": False,
            "allow_paper_trading_deployment": False,
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "expected_runtime_flags": {
                "phase15a_paper_trading_workflow_preregistration": False,
                "phase15b_paper_trading_workflow_readiness_audit": False,
                "phase15c_operational_switch_signal_reconstruction": True,
                "phase15d_current_signal_freshness_switch_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase15c_reports": {
                "conclusion": str(tmp_path / "phase15c_operational_signal_conclusion.csv"),
                "gate_report": str(tmp_path / "phase15c_operational_signal_gate_report.csv"),
                "switch_event_log": str(tmp_path / "phase15c_operational_switch_event_log.csv"),
                "switch_reconstruction_summary": str(tmp_path / "phase15c_switch_reconstruction_summary.csv"),
                "current_signal_file": str(tmp_path / "phase15c_current_signal_file.csv"),
                "current_signal_generation_summary": str(tmp_path / "phase15c_current_signal_generation_summary.csv"),
            },
            "required_switch_event_columns": [
                "switch_event_id",
                "decision_date",
                "previous_mode",
                "current_mode",
                "previous_exposure",
                "current_exposure",
                "switch_triggered",
                "transition_type",
                "switch_reason",
                "raw_signal",
                "confirmed_signal",
                "deep_drawdown_guard_state",
                "loose_relief_state",
                "turnover",
                "applied_overlay_slippage_bps",
                "overlay_slippage_cost_pct",
                "source_candidate_system_id",
                "signal_validity_flag",
            ],
            "required_current_signal_columns": [
                "signal_date",
                "data_as_of_date",
                "generated_at_utc",
                "candidate_system_id",
                "data_source",
                "current_mode",
                "previous_mode",
                "current_exposure",
                "previous_exposure",
                "target_action",
                "switch_triggered",
                "switch_reason",
                "signal_validity_flag",
                "data_freshness_flag",
                "paper_trading_allowed",
                "paper_readiness_status",
                "blocking_warnings",
                "benchmark_spy_close_or_return_source",
            ],
            "decision_policy": {
                "decision_if_all_passed": "paper_dry_run_preregistration_allowed_next",
                "decision_if_switch_failed": "blocked_switch_reconstruction_failed",
                "decision_if_signal_failed": "blocked_current_signal_stale_or_invalid",
                "decision_if_both_failed": "blocked_both_switch_and_signal_failed",
            },
            "phase15e_boundary": {
                "allowed_next_step_if_blocked": "Operational switch/signal repair only",
                "allowed_next_step_if_passed": "Paper dry-run pre-registration only",
                "forbidden_next_step": "broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
    }


def test_phase15c_to_15d_reconstructs_switches_and_allows_dry_run_prereg(tmp_path):
    _write_source_reports(tmp_path)
    config = _config(tmp_path)

    out_c = save_phase15c_operational_switch_signal_reconstruction(
        config=config,
        reports_dir=tmp_path,
    )
    out_d = save_phase15d_current_signal_freshness_switch_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_c["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_d["conclusion"].iloc[0]["all_gates_passed"])

    switch_summary = out_c["switch_reconstruction_summary"].iloc[0]
    assert bool(switch_summary["switch_count_reconciled"])

    decision = out_d["readiness_decision_report"].iloc[0]
    assert decision["decision"] == "paper_dry_run_preregistration_allowed_next"
    assert bool(decision["paper_dry_run_preregistration_allowed_next"])
    assert not bool(decision["paper_trading_ready"])