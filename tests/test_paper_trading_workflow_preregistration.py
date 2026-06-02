from pathlib import Path

import pandas as pd

from market_strats.analysis.paper_trading_workflow_preregistration import (
    save_phase15a_paper_trading_workflow_preregistration,
    save_phase15b_paper_trading_workflow_readiness_audit,
)


def _write_phase14_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 14H",
                "verdict": "Completed — corrected visual backtest audit/reconciliation passed",
                "all_gates_passed": True,
                "paper_trading_ready": False,
            }
        ]
    ).to_csv(tmp_path / "phase14h_corrected_visual_audit_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "decision": "allow_paper_workflow_preregistration_next",
                "paper_workflow_preregistration_allowed": True,
                "paper_trading_ready": False,
            }
        ]
    ).to_csv(
        tmp_path / "phase14h_corrected_visual_audit_reconciliation_decision_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "signal_determined": True,
                "latest_decision_date": "2026-05-01",
                "current_mode": "offensive_spy",
                "current_exposure": 1.0,
                "current_candidate_action": "risk_on_preview",
                "preview_only": True,
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "data_timestamp_source": "phase14g_corrected_visual_signal_template_preview.csv",
                "warning": "",
            }
        ]
    ).to_csv(
        tmp_path / "phase14g_corrected_visual_current_signal_state_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision_date": "2026-05-01",
                "strategy_return": 0.001,
                "SPY_return": 0.001,
                "candidate_equity": 71779.16,
                "benchmark_equity": 79572.94,
                "exposure": 1.0,
                "mode": "offensive_spy",
                "turnover": 0.0,
                "applied_overlay_slippage_bps": 5.0,
                "overlay_slippage_cost_pct": 0.0,
            }
        ]
    ).to_csv(
        tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv",
        index=False,
    )


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase14i_phase6b_candidate_daily_stream_export": {"enabled": False},
        "phase14j_phase6b_candidate_export_audit": {"enabled": False},
        "phase14g_candidate_source_correction_visual_rerun": {"enabled": False},
        "phase14h_corrected_visual_backtest_audit_reconciliation_decision": {"enabled": False},
        "phase15a_paper_trading_workflow_preregistration": {
            "enabled": True,
            "preregistration_role": "Paper-trading workflow pre-registration only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "exported_daily_file": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv"),
            "corrected_current_signal_report": str(tmp_path / "phase14g_corrected_visual_current_signal_state_report.csv"),
            "corrected_visual_conclusion": str(tmp_path / "phase14h_corrected_visual_audit_conclusion.csv"),
            "corrected_visual_decision_report": str(tmp_path / "phase14h_corrected_visual_audit_reconciliation_decision_report.csv"),
            "allow_paper_trading_deployment": False,
            "allow_broker_api_integration": False,
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "endpoint_policy": {
                "audit_current_date": "2026-06-02",
                "canonical_backtest_endpoint": "2026-05-01",
                "max_signal_staleness_days_for_readiness": 3,
                "block_readiness_if_latest_signal_is_not_current": True,
            },
            "operational_switch_policy": {
                "expected_canonical_switch_count": 36,
                "exported_switch_count_observed": 0,
                "require_switch_reconstruction_before_readiness": True,
                "require_switch_event_log_before_readiness": True,
                "require_explainable_trade_segments_before_readiness": True,
                "failure_if_switch_mechanics_unresolved": True,
            },
            "daily_signal_file_schema": {
                "required_fields": ["signal_date", "data_as_of_date", "current_mode", "current_exposure", "target_action"]
            },
            "current_signal_state_fields": {
                "required_fields": ["latest_decision_date", "current_mode", "current_exposure", "current_candidate_action", "preview_only"]
            },
            "manual_paper_broker_entry_template": {
                "required_fields": ["entry_date", "ticker", "paper_account", "target_exposure", "no_real_money_confirmation"]
            },
            "monitoring_dashboard_schema": {
                "required_panels": ["current_signal_state", "candidate_equity_vs_spy", "data_freshness", "stop_condition_status"]
            },
            "execution_checklist": {
                "required_checks": ["confirm_signal_file_generated_today", "confirm_paper_account_only", "confirm_stop_conditions_not_triggered"]
            },
            "paper_trading_journal_template": {
                "required_fields": ["journal_date", "signal_date", "action_taken", "data_freshness_status"]
            },
            "stop_conditions": {
                "required_conditions": ["signal_file_missing_or_stale", "switch_reconstruction_missing", "unexpected_live_money_risk"]
            },
            "benchmark_update_rules": {
                "required_rules": ["update_spy_buy_hold_benchmark_each_signal_day", "store_candidate_vs_spy_equity_snapshot"]
            },
            "phase15b_boundary": {
                "allowed_next_step": "Paper-trading workflow readiness audit only",
                "forbidden_next_step": "paper-trading deployment, broker/API integration, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15b_paper_trading_workflow_readiness_audit": {
            "enabled": True,
            "audit_role": "Paper-trading workflow readiness audit only",
            "implementation_classification": "B",
            "allow_paper_trading_deployment": False,
            "allow_broker_api_integration": False,
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "expected_runtime_flags": {
                "phase14i_phase6b_candidate_daily_stream_export": False,
                "phase14j_phase6b_candidate_export_audit": False,
                "phase14g_candidate_source_correction_visual_rerun": False,
                "phase14h_corrected_visual_backtest_audit_reconciliation_decision": False,
                "phase15a_paper_trading_workflow_preregistration": True,
                "phase15b_paper_trading_workflow_readiness_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase15a_reports": {
                "conclusion": str(tmp_path / "phase15a_paper_workflow_conclusion.csv"),
                "gate_report": str(tmp_path / "phase15a_paper_workflow_gate_report.csv"),
                "daily_signal_file_schema": str(tmp_path / "phase15a_paper_workflow_daily_signal_file_schema.csv"),
                "current_signal_state_schema": str(tmp_path / "phase15a_paper_workflow_current_signal_state_schema.csv"),
                "operational_switch_policy": str(tmp_path / "phase15a_paper_workflow_operational_switch_policy.csv"),
                "endpoint_freshness_policy": str(tmp_path / "phase15a_paper_workflow_endpoint_freshness_policy.csv"),
                "manual_paper_broker_entry_template": str(tmp_path / "phase15a_paper_workflow_manual_paper_broker_entry_template.csv"),
                "monitoring_dashboard_schema": str(tmp_path / "phase15a_paper_workflow_monitoring_dashboard_schema.csv"),
                "execution_checklist": str(tmp_path / "phase15a_paper_workflow_execution_checklist.csv"),
                "paper_trading_journal_template": str(tmp_path / "phase15a_paper_workflow_paper_trading_journal_template.csv"),
                "stop_conditions": str(tmp_path / "phase15a_paper_workflow_stop_conditions.csv"),
                "benchmark_update_rules": str(tmp_path / "phase15a_paper_workflow_benchmark_update_rules.csv"),
                "failure_conditions": str(tmp_path / "phase15a_paper_workflow_failure_conditions.csv"),
            },
            "readiness_policy": {
                "require_switch_reconstruction_passed": True,
                "require_current_signal_not_stale": True,
                "require_current_signal_not_preview_only": True,
                "block_readiness_if_any_required_condition_fails": True,
            },
            "phase15c_boundary": {
                "allowed_next_step_if_not_ready": "Operational switch/signal reconstruction implementation or workflow blocker repair only",
                "allowed_next_step_if_ready": "Paper-trading dry-run pre-registration only",
                "forbidden_next_step": "paper-trading deployment, broker/API integration, live trading, real-money deployment, candidate promotion",
            },
        },
    }


def test_phase15a_to_15b_preregisters_workflow_but_blocks_readiness(tmp_path):
    _write_phase14_reports(tmp_path)
    config = _config(tmp_path)

    out_a = save_phase15a_paper_trading_workflow_preregistration(
        config=config,
        reports_dir=tmp_path,
    )
    out_b = save_phase15b_paper_trading_workflow_readiness_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_a["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_b["conclusion"].iloc[0]["all_gates_passed"])

    decision = out_b["readiness_decision_report"].iloc[0]
    assert decision["decision"] == "paper_trading_readiness_blocked_operational_repairs_required"
    assert not bool(decision["paper_trading_ready"])
    assert "operational_switch_mechanics_unresolved" in decision["blocking_reasons"]