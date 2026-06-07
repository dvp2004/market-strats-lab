from pathlib import Path

import numpy as np
import pandas as pd

import market_strats.analysis.true_switch_log_export as switch_export
from market_strats.analysis.true_switch_log_export import (
    save_phase15g_true_final_switch_log_export,
    save_phase15h_switch_log_reconciliation_audit,
)


def _mock_phase15f_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 15F",
                "verdict": "Completed — fresh data extension pre-registration passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase15f_fresh_data_extension_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase15f_fresh_data_extension_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "true_36_switch_source_not_found_patch_required",
                "source_code_patch_required": True,
            }
        ]
    ).to_csv(
        tmp_path / "phase15e_switch_source_attribution_attribution_decision.csv",
        index=False,
    )


def _mock_final_candidate():
    dates = pd.bdate_range("2026-01-01", periods=80)
    exposure = []
    value = 1.0
    switches = 0

    for idx in range(len(dates)):
        if idx > 0 and switches < 36:
            value = 0.0 if value == 1.0 else 1.0
            switches += 1
        exposure.append(value)

    mode = ["offensive_spy" if item == 1.0 else "defensive_or_cash" for item in exposure]
    turnover = pd.Series(exposure).diff().abs().fillna(0.0)

    return pd.DataFrame(
        {
            "date": dates,
            "strategy_return": np.full(len(dates), 0.001),
            "equity": np.linspace(10000, 11000, len(dates)),
            "mode": mode,
            "exposure": exposure,
            "turnover": turnover,
            "applied_overlay_slippage_bps": 5.0,
            "overlay_slippage_cost_pct": 0.0,
            "raw_signal": mode,
            "confirmed_signal": mode,
            "deep_drawdown_guard_state": "inactive",
            "loose_relief_state": "active",
        }
    )


def _config(tmp_path: Path):
    required_cols = [
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
    ]

    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase15e_operational_switch_source_attribution": {"enabled": False},
        "phase15f_fresh_data_extension_preregistration": {"enabled": False},
        "phase15g_true_final_switch_log_export": {
            "enabled": True,
            "execution_role": "True final 36-switch operational log export implementation only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "canonical_endpoint": "2026-05-01",
            "exported_switch_log_file": str(
                tmp_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"
            ),
            "source_reports": {
                "phase15f_conclusion": str(tmp_path / "phase15f_fresh_data_extension_conclusion.csv"),
                "phase15f_gate_report": str(tmp_path / "phase15f_fresh_data_extension_gate_report.csv"),
                "phase15e_attribution_decision": str(tmp_path / "phase15e_switch_source_attribution_attribution_decision.csv"),
            },
            "switch_reconstruction_policy": {
                "expected_switch_count": 36,
                "switch_count_abs_tolerance": 0,
                "max_allowed_decision_date": "2026-05-01",
            },
            "required_switch_event_columns": required_cols,
            "candidate_column_policy": {
                "date_columns": ["date", "decision_date"],
                "mode_columns": ["mode"],
                "exposure_columns": ["exposure"],
                "raw_signal_columns": ["raw_signal"],
                "confirmed_signal_columns": ["confirmed_signal"],
                "deep_drawdown_guard_columns": ["deep_drawdown_guard_state"],
                "loose_relief_columns": ["loose_relief_state"],
                "turnover_columns": ["turnover"],
                "slippage_bps_columns": ["applied_overlay_slippage_bps"],
                "slippage_cost_columns": ["overlay_slippage_cost_pct"],
            },
            "allow_fresh_data_extension": False,
            "allow_current_signal_generation": False,
            "allow_paper_dry_run_preregistration": False,
            "allow_broker_api_integration": False,
            "allow_paper_trading_deployment": False,
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_optimisation": False,
            "allow_multi_asset_expansion": False,
            "allow_feature_importance": False,
            "phase15h_boundary": {
                "allowed_next_step": "Switch log reconciliation and fresh signal eligibility audit only",
                "forbidden_next_step": "fresh data extension execution, current signal generation, paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15h_switch_log_reconciliation_audit": {
            "enabled": True,
            "audit_role": "Switch log reconciliation and fresh signal eligibility audit only",
            "implementation_classification": "B",
            "expected_runtime_flags": {
                "phase15e_operational_switch_source_attribution": False,
                "phase15f_fresh_data_extension_preregistration": False,
                "phase15g_true_final_switch_log_export": True,
                "phase15h_switch_log_reconciliation_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase15g_reports": {
                "conclusion": str(tmp_path / "phase15g_true_switch_log_export_conclusion.csv"),
                "gate_report": str(tmp_path / "phase15g_true_switch_log_export_gate_report.csv"),
                "switch_log": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"),
                "switch_summary": str(tmp_path / "phase15g_true_switch_log_export_switch_summary.csv"),
                "column_selection_report": str(tmp_path / "phase15g_true_switch_log_export_column_selection_report.csv"),
            },
            "expected_switch_count": 36,
            "switch_count_abs_tolerance": 0,
            "canonical_endpoint": "2026-05-01",
            "required_switch_event_columns": required_cols,
            "decision_policy": {
                "decision_if_reconciled": "canonical_switch_log_reconciled_fresh_signal_phase_allowed_next",
                "decision_if_failed": "blocked_true_switch_log_export_failed",
            },
            "phase15i_boundary": {
                "allowed_next_step_if_reconciled": "Fresh data extension implementation and current signal generation only",
                "allowed_next_step_if_failed": "True switch log export repair only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
            "allow_paper_dry_run_preregistration": False,
            "allow_broker_api_integration": False,
            "allow_paper_trading_deployment": False,
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_optimisation": False,
            "allow_multi_asset_expansion": False,
            "allow_feature_importance": False,
        },
    }


def test_phase15g_to_15h_exports_and_audits_true_switch_log(tmp_path, monkeypatch):
    _mock_phase15f_reports(tmp_path)
    config = _config(tmp_path)

    monkeypatch.setattr(
        switch_export,
        "_find_final_candidate_frame",
        lambda relative_momentum_outputs, ticker_outputs, config: _mock_final_candidate(),
    )

    out_g = save_phase15g_true_final_switch_log_export(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs={},
        ticker_outputs={},
    )
    out_h = save_phase15h_switch_log_reconciliation_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_g["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_h["conclusion"].iloc[0]["all_gates_passed"])

    summary = out_g["switch_summary"].iloc[0]
    assert int(summary["reconstructed_switch_count"]) == 36
    assert bool(summary["switch_count_reconciled"])

    decision = out_h["reconciliation_decision_report"].iloc[0]
    assert decision["decision"] == "canonical_switch_log_reconciled_fresh_signal_phase_allowed_next"
    assert bool(decision["fresh_signal_generation_allowed_next"])
    assert not bool(decision["paper_trading_ready"])