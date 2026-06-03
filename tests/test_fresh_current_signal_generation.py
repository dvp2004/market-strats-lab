from pathlib import Path

import numpy as np
import pandas as pd

import market_strats.analysis.fresh_current_signal_generation as fresh_signal
from market_strats.analysis.fresh_current_signal_generation import (
    save_phase15m_fresh_current_signal_generation,
    save_phase15n_fresh_signal_audit_paper_dry_run_eligibility,
)


def _write_source_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 15L",
                "verdict": "Completed — fresh current-signal pre-implementation check passed",
                "all_gates_passed": True,
                "decision": "fresh_current_signal_generation_allowed_next",
            }
        ]
    ).to_csv(tmp_path / "phase15l_fresh_signal_precheck_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase15l_fresh_signal_precheck_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "fresh_current_signal_generation_allowed_next",
                "fresh_current_signal_generation_allowed_next": True,
            }
        ]
    ).to_csv(tmp_path / "phase15l_fresh_signal_precheck_decision_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "endpoint_date": "2026-05-01",
                "endpoint_mode": "offensive_spy",
                "endpoint_exposure": 1.0,
                "preview_only": True,
            }
        ]
    ).to_csv(tmp_path / "phase15k_pinned_endpoint_signal_file.csv", index=False)

    pd.DataFrame(
        [
            {
                "switch_event_id": 36,
                "decision_date": "2026-04-13",
                "previous_mode": "defensive_or_cash",
                "current_mode": "offensive_spy",
                "previous_exposure": 0.0,
                "current_exposure": 1.0,
                "signal_validity_flag": "pass",
            }
        ]
    ).to_csv(
        tmp_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "selected": True,
                "selected_column": "target_offensive_weight",
                "transform": "direct",
                "candidate_switch_count": 36,
                "count_reconciled": True,
            }
        ]
    ).to_csv(tmp_path / "phase15i_column_semantics_selected_switch_definition.csv", index=False)


def _mock_final_candidate():
    return pd.DataFrame(
        {
            "date": ["2026-05-29", "2026-06-01", "2026-06-02"],
            "target_offensive_weight": [1.0, 1.0, 1.0],
            "SPY_return": [0.001, -0.002, 0.003],
            "SPY_close": [600.0, 601.0, 603.0],
            "strategy_return": np.array([0.001, -0.002, 0.003]),
        }
    )


def _config(tmp_path: Path):
    required_cols = [
        "signal_date",
        "data_as_of_date",
        "generated_at_utc",
        "candidate_system_id",
        "data_source",
        "data_source_timestamp",
        "pinned_research_endpoint",
        "is_out_of_sample_extension",
        "current_mode",
        "previous_mode",
        "current_exposure",
        "previous_exposure",
        "target_action",
        "switch_triggered",
        "switch_reason",
        "signal_validity_flag",
        "data_freshness_flag",
        "benchmark_update_flag",
        "paper_dry_run_allowed",
        "paper_trading_allowed",
        "paper_readiness_status",
        "blocking_warnings",
        "benchmark_spy_close_or_return_source",
    ]

    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase15k_pinned_endpoint_signal_consistency_audit": {"enabled": False},
        "phase15l_fresh_data_current_signal_preimplementation_check": {"enabled": False},
        "phase15m_fresh_current_signal_generation": {
            "enabled": True,
            "execution_role": "Fresh current signal generation only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "audit_current_date": "2026-06-02",
            "max_signal_staleness_days": 3,
            "output_file": str(tmp_path / "phase15m_current_signal_file.csv"),
            "source_reports": {
                "phase15l_conclusion": str(tmp_path / "phase15l_fresh_signal_precheck_conclusion.csv"),
                "phase15l_gate_report": str(tmp_path / "phase15l_fresh_signal_precheck_gate_report.csv"),
                "phase15l_decision_report": str(tmp_path / "phase15l_fresh_signal_precheck_decision_report.csv"),
                "phase15k_endpoint_signal": str(tmp_path / "phase15k_pinned_endpoint_signal_file.csv"),
                "switch_log": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"),
                "selected_switch_definition": str(tmp_path / "phase15i_column_semantics_selected_switch_definition.csv"),
            },
            "fresh_candidate_stream_policy": {
                "preferred_fresh_candidate_stream_file": str(tmp_path / "missing_manual_file.csv"),
                "allow_in_memory_final_candidate_frame_if_post_endpoint_rows_exist": True,
            },
            "selected_exposure_fallback_priority": ["target_offensive_weight"],
            "required_current_signal_columns": required_cols,
            "benchmark_policy": {
                "acceptable_benchmark_columns": ["SPY_close", "SPY_return"]
            },
            "decision_policy": {
                "signal_status_if_valid": "fresh_signal_generated_pending_audit",
                "signal_status_if_blocked": "blocked_fresh_signal_unavailable_or_invalid",
            },
            "allow_current_signal_generation": True,
            "allow_fresh_data_pull_execution": False,
            "allow_canonical_report_mutation": False,
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
            "phase15n_boundary": {
                "allowed_next_step": "Fresh signal audit and paper dry-run eligibility decision only",
                "forbidden_next_step": "broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15n_fresh_signal_audit_paper_dry_run_eligibility": {
            "enabled": True,
            "audit_role": "Fresh signal audit and paper dry-run eligibility decision only",
            "implementation_classification": "B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "max_signal_staleness_days": 3,
            "expected_runtime_flags": {
                "phase15k_pinned_endpoint_signal_consistency_audit": False,
                "phase15l_fresh_data_current_signal_preimplementation_check": False,
                "phase15m_fresh_current_signal_generation": True,
                "phase15n_fresh_signal_audit_paper_dry_run_eligibility": True,
                "relative_momentum_allocator": True,
            },
            "phase15m_reports": {
                "conclusion": str(tmp_path / "phase15m_current_signal_conclusion.csv"),
                "gate_report": str(tmp_path / "phase15m_current_signal_gate_report.csv"),
                "current_signal_file": str(tmp_path / "phase15m_current_signal_file.csv"),
                "generation_summary": str(tmp_path / "phase15m_current_signal_generation_summary.csv"),
                "required_column_check": str(tmp_path / "phase15m_current_signal_required_column_check.csv"),
            },
            "source_reports": {
                "switch_log": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"),
                "pinned_endpoint_signal": str(tmp_path / "phase15k_pinned_endpoint_signal_file.csv"),
            },
            "required_current_signal_columns": required_cols,
            "decision_policy": {
                "decision_if_all_current_signal_gates_pass": "paper_dry_run_preregistration_allowed_next",
                "decision_if_any_current_signal_gate_fails": "blocked_fresh_signal_audit_failed",
            },
            "phase15o_boundary": {
                "allowed_next_step_if_passed": "Paper dry-run pre-registration only",
                "allowed_next_step_if_blocked": "Fresh current-signal repair only",
                "forbidden_next_step": "broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
            "allow_paper_dry_run_preregistration_if_passed": True,
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


def test_phase15m_to_15n_generates_and_audits_fresh_signal(tmp_path, monkeypatch):
    _write_source_reports(tmp_path)
    config = _config(tmp_path)

    monkeypatch.setattr(
        fresh_signal,
        "_find_final_candidate_frame",
        lambda relative_momentum_outputs, ticker_outputs, config: _mock_final_candidate(),
    )

    out_m = save_phase15m_fresh_current_signal_generation(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs={},
        ticker_outputs={},
    )
    out_n = save_phase15n_fresh_signal_audit_paper_dry_run_eligibility(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_m["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_n["conclusion"].iloc[0]["all_gates_passed"])

    signal = out_m["current_signal_file"].iloc[0]
    assert signal["data_as_of_date"] == "2026-06-02"
    assert signal["current_mode"] == "offensive_spy"
    assert signal["data_freshness_flag"] == "pass"
    assert signal["benchmark_update_flag"] == "pass"
    assert not bool(signal["paper_dry_run_allowed"])

    decision = out_n["decision_report"].iloc[0]
    assert decision["decision"] == "paper_dry_run_preregistration_allowed_next"
    assert bool(decision["paper_dry_run_preregistration_allowed_next"])
    assert not bool(decision["paper_trading_ready"])