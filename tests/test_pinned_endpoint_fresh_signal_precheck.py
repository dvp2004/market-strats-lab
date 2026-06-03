from pathlib import Path

import pandas as pd

from market_strats.analysis.pinned_endpoint_fresh_signal_precheck import (
    save_phase15k_pinned_endpoint_signal_consistency_audit,
    save_phase15l_fresh_data_current_signal_preimplementation_check,
)


def _write_source_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 15J",
                "verdict": "Completed — refined switch reconstruction audit passed",
                "all_gates_passed": True,
                "decision": "refined_canonical_switch_log_reconciled_fresh_signal_phase_allowed_next",
            }
        ]
    ).to_csv(tmp_path / "phase15j_refined_switch_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase15j_refined_switch_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "refined_canonical_switch_log_reconciled_fresh_signal_phase_allowed_next",
                "fresh_signal_generation_allowed_next": True,
            }
        ]
    ).to_csv(tmp_path / "phase15j_refined_switch_decision_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "switch_event_id": 36,
                "decision_date": "2026-04-13",
                "previous_mode": "defensive_or_cash",
                "current_mode": "offensive_spy",
                "previous_exposure": 0.0,
                "current_exposure": 1.0,
                "switch_triggered": True,
                "transition_type": "risk_increase",
                "switch_reason": "final_target_allocation_change_only",
                "raw_signal": "offensive_spy",
                "confirmed_signal": "offensive_spy",
                "deep_drawdown_guard_state": "not_exported",
                "loose_relief_state": "not_exported",
                "turnover": 1.0,
                "applied_overlay_slippage_bps": 5.0,
                "overlay_slippage_cost_pct": 0.0,
                "source_candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
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
                "expected_switch_count": 36,
                "reconstructed_switch_count": 36,
                "switch_count_reconciled": True,
            }
        ]
    ).to_csv(tmp_path / "phase15j_refined_switch_refined_switch_summary.csv", index=False)

    pd.DataFrame(
        [
            {
                "decision_date": "2026-05-01",
                "mode": "offensive_spy",
                "exposure": 1.0,
                "strategy_return": 0.001,
                "SPY_return": 0.001,
            }
        ]
    ).to_csv(
        tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {"policy": "baseline_protection_policy", "field": "preserve_pinned_research_reports", "value": True},
            {"policy": "baseline_protection_policy", "field": "preserve_phase6b_canonical_metrics", "value": True},
            {"policy": "baseline_protection_policy", "field": "fresh_outputs_must_use_prefix", "value": "phase15g_current_signal"},
        ]
    ).to_csv(tmp_path / "phase15f_fresh_data_extension_baseline_protection_policy.csv", index=False)

    pd.DataFrame(
        [
            {"policy": "fresh_data_source_policy", "field": "require_data_beyond_pinned_endpoint", "value": True},
            {"policy": "fresh_data_source_policy", "field": "require_data_source_timestamp_field", "value": True},
            {"policy": "fresh_data_source_policy", "field": "require_data_as_of_date_field", "value": True},
            {"policy": "fresh_data_source_policy", "field": "allowed_primary_source", "value": "existing_project_market_data_pipeline"},
        ]
    ).to_csv(tmp_path / "phase15f_fresh_data_extension_fresh_data_source_policy.csv", index=False)

    pd.DataFrame(
        [
            {"policy": "current_signal_update_policy", "field": "max_signal_staleness_days", "value": 3},
            {"policy": "current_signal_update_policy", "field": "failed_data_pull_policy", "value": "write_blocked_signal_file_with_failure_reason"},
            {"policy": "current_signal_update_policy", "field": "signal_must_include_data_source", "value": True},
        ]
    ).to_csv(tmp_path / "phase15f_fresh_data_extension_current_signal_update_policy.csv", index=False)

    schema_cols = [
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
    pd.DataFrame([{"column_name": col} for col in schema_cols]).to_csv(
        tmp_path / "phase15f_fresh_data_extension_current_signal_output_schema.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {"policy": "cadence_policy", "field": "preferred_frequency", "value": "daily_on_market_days"},
            {"policy": "cadence_policy", "field": "block_if_latest_market_data_older_than_days", "value": 3},
        ]
    ).to_csv(tmp_path / "phase15f_fresh_data_extension_cadence_policy.csv", index=False)

    pd.DataFrame(
        [
            {"policy": "failure_handling_policy", "field": "if_latest_data_missing", "value": "block_signal_and_write_failure_reason"},
            {"policy": "failure_handling_policy", "field": "if_benchmark_update_missing", "value": "block_signal_and_write_failure_reason"},
        ]
    ).to_csv(tmp_path / "phase15f_fresh_data_extension_failure_handling_policy.csv", index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase15i_final_candidate_column_semantics_diagnostic": {"enabled": False},
        "phase15j_refined_switch_reconstruction_audit": {"enabled": False},
        "phase15k_pinned_endpoint_signal_consistency_audit": {
            "enabled": True,
            "audit_role": "Pinned-endpoint operational signal consistency audit only",
            "implementation_classification": "B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "canonical_endpoint": "2026-05-01",
            "expected_latest_switch_date": "2026-04-13",
            "expected_previous_mode": "defensive_or_cash",
            "expected_current_mode": "offensive_spy",
            "expected_endpoint_mode": "offensive_spy",
            "expected_endpoint_exposure": 1.0,
            "source_reports": {
                "phase15j_conclusion": str(tmp_path / "phase15j_refined_switch_conclusion.csv"),
                "phase15j_gate_report": str(tmp_path / "phase15j_refined_switch_gate_report.csv"),
                "phase15j_decision_report": str(tmp_path / "phase15j_refined_switch_decision_report.csv"),
                "switch_log": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"),
                "switch_summary": str(tmp_path / "phase15j_refined_switch_refined_switch_summary.csv"),
                "exported_daily_stream": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv"),
            },
            "required_endpoint_signal_columns": [
                "endpoint_date",
                "candidate_system_id",
                "latest_switch_date",
                "latest_switch_previous_mode",
                "latest_switch_current_mode",
                "latest_switch_previous_exposure",
                "latest_switch_current_exposure",
                "endpoint_mode",
                "endpoint_exposure",
                "endpoint_signal_action",
                "preview_only",
                "paper_dry_run_allowed",
                "paper_trading_allowed",
                "signal_consistency_passed",
                "blocking_warnings",
            ],
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
            "phase15l_boundary": {
                "allowed_next_step": "Fresh data extension and current signal generation pre-implementation check only",
                "forbidden_next_step": "fresh data pull execution, current signal generation, paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15l_fresh_data_current_signal_preimplementation_check": {
            "enabled": True,
            "check_role": "Fresh data extension and current signal generation pre-implementation check only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "expected_runtime_flags": {
                "phase15i_final_candidate_column_semantics_diagnostic": False,
                "phase15j_refined_switch_reconstruction_audit": False,
                "phase15k_pinned_endpoint_signal_consistency_audit": True,
                "phase15l_fresh_data_current_signal_preimplementation_check": True,
                "relative_momentum_allocator": True,
            },
            "source_reports": {
                "phase15k_conclusion": str(tmp_path / "phase15k_endpoint_signal_conclusion.csv"),
                "phase15k_gate_report": str(tmp_path / "phase15k_endpoint_signal_gate_report.csv"),
                "phase15k_endpoint_signal": str(tmp_path / "phase15k_pinned_endpoint_signal_file.csv"),
                "phase15f_baseline_protection_policy": str(tmp_path / "phase15f_fresh_data_extension_baseline_protection_policy.csv"),
                "phase15f_fresh_data_source_policy": str(tmp_path / "phase15f_fresh_data_extension_fresh_data_source_policy.csv"),
                "phase15f_current_signal_update_policy": str(tmp_path / "phase15f_fresh_data_extension_current_signal_update_policy.csv"),
                "phase15f_current_signal_output_schema": str(tmp_path / "phase15f_fresh_data_extension_current_signal_output_schema.csv"),
                "phase15f_cadence_policy": str(tmp_path / "phase15f_fresh_data_extension_cadence_policy.csv"),
                "phase15f_failure_handling_policy": str(tmp_path / "phase15f_fresh_data_extension_failure_handling_policy.csv"),
                "switch_log": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"),
                "pinned_daily_stream": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv"),
            },
            "phase15m_current_signal_output": {
                "minimum_required_columns": [
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
            },
            "decision_policy": {
                "decision_if_ready": "fresh_current_signal_generation_allowed_next",
                "decision_if_failed": "blocked_fresh_signal_preimplementation_check_failed",
            },
            "phase15m_boundary": {
                "allowed_next_step": "Fresh current signal generation only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
            "allow_fresh_data_pull_execution": False,
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


def test_phase15k_to_15l_passes_endpoint_consistency_and_preimplementation(tmp_path):
    _write_source_reports(tmp_path)
    config = _config(tmp_path)

    out_k = save_phase15k_pinned_endpoint_signal_consistency_audit(
        config=config,
        reports_dir=tmp_path,
    )
    out_l = save_phase15l_fresh_data_current_signal_preimplementation_check(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_k["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_l["conclusion"].iloc[0]["all_gates_passed"])

    endpoint_signal = out_k["pinned_endpoint_signal_file"].iloc[0]
    assert endpoint_signal["latest_switch_date"] == "2026-04-13"
    assert endpoint_signal["endpoint_mode"] == "offensive_spy"
    assert float(endpoint_signal["endpoint_exposure"]) == 1.0
    assert bool(endpoint_signal["preview_only"])
    assert not bool(endpoint_signal["paper_dry_run_allowed"])

    decision = out_l["decision_report"].iloc[0]
    assert decision["decision"] == "fresh_current_signal_generation_allowed_next"
    assert bool(decision["fresh_current_signal_generation_allowed_next"])
    assert not bool(decision["current_signal_generated"])
    assert not bool(decision["paper_trading_ready"])