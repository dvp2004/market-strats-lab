from pathlib import Path

import numpy as np
import pandas as pd

import market_strats.analysis.refined_switch_reconstruction as refined
from market_strats.analysis.refined_switch_reconstruction import (
    save_phase15i_final_candidate_column_semantics_diagnostic,
    save_phase15j_refined_switch_reconstruction_audit,
)


def _mock_phase15h_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 15H",
                "verdict": "Completed — switch log reconciliation audit passed",
                "all_gates_passed": True,
                "decision": "blocked_true_switch_log_export_failed",
            }
        ]
    ).to_csv(tmp_path / "phase15h_switch_log_reconciliation_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase15h_switch_log_reconciliation_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "blocked_true_switch_log_export_failed",
                "switch_log_reconciled": False,
            }
        ]
    ).to_csv(
        tmp_path / "phase15h_switch_log_reconciliation_reconciliation_decision_report.csv",
        index=False,
    )


def _mock_final_candidate():
    dates = pd.bdate_range("2026-01-01", periods=80)

    target = []
    value = 1.0
    switches = 0
    for idx in range(len(dates)):
        if idx > 0 and switches < 36:
            value = 0.0 if value == 1.0 else 1.0
            switches += 1
        target.append(value)

    noisy_position = []
    noisy = 1.0
    for idx in range(len(dates)):
        if idx > 0 and idx <= 70:
            noisy = 0.5 if noisy == 1.0 else 1.0
        noisy_position.append(noisy)

    turnover = pd.Series(target).diff().abs().fillna(0.0)

    return pd.DataFrame(
        {
            "date": dates,
            "strategy_return": np.full(len(dates), 0.001),
            "equity": np.linspace(10000, 11000, len(dates)),
            "position": noisy_position,
            "cash_position": 1.0 - pd.Series(target),
            "offensive_weight": target,
            "defensive_weight": 1.0 - pd.Series(target),
            "target_offensive_weight": target,
            "target_defensive_weight": 1.0 - pd.Series(target),
            "turnover": turnover,
            "applied_overlay_slippage_bps": 5.0,
            "overlay_slippage_cost_pct": 0.0,
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
        "phase15g_true_final_switch_log_export": {"enabled": False},
        "phase15h_switch_log_reconciliation_audit": {"enabled": False},
        "phase15i_final_candidate_column_semantics_diagnostic": {
            "enabled": True,
            "diagnostic_role": "Final candidate column semantics and switch definition diagnostic only",
            "implementation_classification": "B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "canonical_endpoint": "2026-05-01",
            "source_reports": {
                "phase15h_conclusion": str(tmp_path / "phase15h_switch_log_reconciliation_conclusion.csv"),
                "phase15h_gate_report": str(tmp_path / "phase15h_switch_log_reconciliation_gate_report.csv"),
                "phase15h_decision": str(tmp_path / "phase15h_switch_log_reconciliation_reconciliation_decision_report.csv"),
            },
            "expected_switch_count": 36,
            "switch_count_abs_tolerance": 2,
            "inspected_columns": [
                "position",
                "cash_position",
                "offensive_weight",
                "defensive_weight",
                "target_offensive_weight",
                "target_defensive_weight",
                "turnover",
                "applied_overlay_slippage_bps",
                "overlay_slippage_cost_pct",
            ],
            "executable_exposure_candidate_columns": {
                "direct": [
                    "target_offensive_weight",
                    "offensive_weight",
                    "position",
                ],
                "inverse": [
                    "target_defensive_weight",
                    "defensive_weight",
                    "cash_position",
                ],
                "fallback_mode_like": [],
            },
            "selection_priority": [
                "target_offensive_weight",
                "offensive_weight",
                "target_defensive_weight",
                "defensive_weight",
                "cash_position",
                "position",
            ],
            "allow_switch_log_export": False,
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
            "phase15j_boundary": {
                "allowed_next_step": "Refined switch reconstruction implementation and audit only",
                "forbidden_next_step": "fresh data extension execution, current signal generation, paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15j_refined_switch_reconstruction_audit": {
            "enabled": True,
            "execution_role": "Refined 36-switch reconstruction implementation and audit only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "canonical_endpoint": "2026-05-01",
            "exported_switch_log_file": str(
                tmp_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"
            ),
            "source_reports": {
                "phase15i_conclusion": str(tmp_path / "phase15i_column_semantics_conclusion.csv"),
                "phase15i_gate_report": str(tmp_path / "phase15i_column_semantics_gate_report.csv"),
                "selected_switch_definition": str(tmp_path / "phase15i_column_semantics_selected_switch_definition.csv"),
            },
            "expected_switch_count": 36,
            "switch_count_abs_tolerance": 2,
            "required_switch_event_columns": required_cols,
            "auxiliary_column_policy": {
                "date_columns": ["date", "decision_date"],
                "raw_signal_columns": [],
                "confirmed_signal_columns": [],
                "deep_drawdown_guard_columns": [],
                "loose_relief_columns": [],
                "turnover_columns": ["turnover"],
                "slippage_bps_columns": ["applied_overlay_slippage_bps"],
                "slippage_cost_columns": ["overlay_slippage_cost_pct"],
            },
            "decision_policy": {
                "decision_if_reconciled": "refined_canonical_switch_log_reconciled_fresh_signal_phase_allowed_next",
                "decision_if_failed": "blocked_refined_switch_reconstruction_failed",
            },
            "phase15k_boundary": {
                "allowed_next_step_if_reconciled": "Pinned-endpoint signal consistency audit or fresh current-signal preparation only",
                "allowed_next_step_if_failed": "Final switch definition repair only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
            "allow_switch_log_export": True,
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
        },
    }


def test_phase15i_to_15j_selects_target_allocation_not_noisy_position(tmp_path, monkeypatch):
    _mock_phase15h_reports(tmp_path)
    config = _config(tmp_path)

    monkeypatch.setattr(
        refined,
        "_find_final_candidate_frame",
        lambda relative_momentum_outputs, ticker_outputs, config: _mock_final_candidate(),
    )

    out_i = save_phase15i_final_candidate_column_semantics_diagnostic(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs={},
        ticker_outputs={},
    )
    out_j = save_phase15j_refined_switch_reconstruction_audit(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert bool(out_i["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_j["conclusion"].iloc[0]["all_gates_passed"])

    selection = out_i["selected_switch_definition"].iloc[0]
    assert bool(selection["selected"])
    assert selection["selected_column"] == "target_offensive_weight"

    summary = out_j["refined_switch_summary"].iloc[0]
    assert int(summary["reconstructed_switch_count"]) == 36
    assert bool(summary["refined_switch_log_reconciled_and_usable"])

    decision = out_j["decision_report"].iloc[0]
    assert decision["decision"] == "refined_canonical_switch_log_reconciled_fresh_signal_phase_allowed_next"
    assert bool(decision["fresh_signal_generation_allowed_next"])
    assert not bool(decision["paper_trading_ready"])