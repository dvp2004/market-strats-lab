from pathlib import Path

import pandas as pd

from market_strats.analysis.switch_source_attribution_fresh_data_prereg import (
    save_phase15e_operational_switch_source_attribution,
    save_phase15f_fresh_data_extension_preregistration,
)


def _write_source_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 15D",
                "verdict": "Completed — current signal freshness and switch mechanics audit passed",
                "all_gates_passed": True,
                "decision": "blocked_both_switch_and_signal_failed",
            }
        ]
    ).to_csv(tmp_path / "phase15d_signal_switch_audit_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase15d_signal_switch_audit_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "blocked_both_switch_and_signal_failed",
                "switch_reconstruction_passed": False,
                "current_signal_freshness_passed": False,
            }
        ]
    ).to_csv(
        tmp_path / "phase15d_signal_switch_audit_readiness_decision_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "source": "exported_daily_stream_mode_exposure_changes",
                "candidate_rows": 0,
                "distance_to_expected": 36,
                "selected": True,
            },
            {
                "source": str(tmp_path / "regime_switch_overlay_offensive_relief_changed_switch_audit.csv"),
                "candidate_rows": 94,
                "distance_to_expected": 58,
                "selected": False,
            },
        ]
    ).to_csv(
        tmp_path / "phase15c_operational_signal_switch_source_inventory.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "expected_switch_count": 36,
                "reconstructed_switch_count": 0,
                "switch_count_reconciled": False,
            }
        ]
    ).to_csv(tmp_path / "phase15c_switch_reconstruction_summary.csv", index=False)

    pd.DataFrame(
        [
            {
                "signal_determined": True,
                "signal_freshness_passed": False,
            }
        ]
    ).to_csv(tmp_path / "phase15c_current_signal_generation_summary.csv", index=False)

    pd.DataFrame(
        {
            "decision_date": pd.bdate_range("2020-01-01", periods=100),
            "strategy_return": 0.001,
            "SPY_return": 0.001,
            "candidate_equity": range(100),
            "benchmark_equity": range(100),
            "mode": "offensive_spy",
            "exposure": 1.0,
        }
    ).to_csv(
        tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv",
        index=False,
    )

    pd.DataFrame(
        {
            "switch_date": pd.bdate_range("2020-01-01", periods=94),
            "from_mode": "a",
            "to_mode": "b",
            "diagnostic": "changed switch audit row",
        }
    ).to_csv(
        tmp_path / "regime_switch_overlay_offensive_relief_changed_switch_audit.csv",
        index=False,
    )


def _config(tmp_path: Path):
    return {
        "phase15c_operational_switch_signal_reconstruction": {"enabled": False},
        "phase15d_current_signal_freshness_switch_audit": {"enabled": False},
        "phase15e_operational_switch_source_attribution": {
            "enabled": True,
            "attribution_role": "Operational switch source attribution and true 36-switch reconstruction spec only",
            "implementation_classification": "B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "exported_daily_file": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv"),
            "source_reports": {
                "phase15d_conclusion": str(tmp_path / "phase15d_signal_switch_audit_conclusion.csv"),
                "phase15d_gate_report": str(tmp_path / "phase15d_signal_switch_audit_gate_report.csv"),
                "phase15d_readiness_decision": str(tmp_path / "phase15d_signal_switch_audit_readiness_decision_report.csv"),
                "phase15c_switch_source_inventory": str(tmp_path / "phase15c_operational_signal_switch_source_inventory.csv"),
                "phase15c_switch_summary": str(tmp_path / "phase15c_switch_reconstruction_summary.csv"),
                "phase15c_current_signal_summary": str(tmp_path / "phase15c_current_signal_generation_summary.csv"),
            },
            "candidate_switch_source_files": [
                str(tmp_path / "regime_switch_overlay_offensive_relief_changed_switch_audit.csv"),
            ],
            "expected_final_switch_count": 36,
            "switch_count_abs_tolerance": 2,
            "required_final_switch_columns": [
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
            "reconstruction_spec_policy": {
                "preferred_patch_targets": [
                    "src/market_strats/analysis/regime_switch_overlay_final_candidate_decision.py",
                    "src/market_strats/analysis/bid_ask_market_impact_diagnostic.py",
                    "src/market_strats/run_backtest.py",
                ],
                "required_future_export_file": "reports/phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv",
                "required_future_export_source": "same reconstruction path as Phase 6B/6C final candidate daily stream export",
                "require_final_not_intermediate_switches": True,
                "require_reconciliation_to_expected_36_switches": True,
            },
            "allow_switch_log_execution_patch": False,
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
            "phase15f_boundary": {
                "allowed_next_step": "Fresh data extension pre-registration and current signal update spec only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15f_fresh_data_extension_preregistration": {
            "enabled": True,
            "preregistration_role": "Fresh data extension pre-registration and current signal update spec only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "audit_current_date": "2026-06-02",
            "source_reports": {
                "phase15e_conclusion": str(tmp_path / "phase15e_switch_source_attribution_conclusion.csv"),
                "phase15e_gate_report": str(tmp_path / "phase15e_switch_source_attribution_gate_report.csv"),
                "phase15e_attribution_decision": str(tmp_path / "phase15e_switch_source_attribution_attribution_decision.csv"),
            },
            "baseline_protection_policy": {
                "preserve_pinned_research_reports": True,
                "preserve_phase6b_canonical_metrics": True,
                "fresh_data_outputs_must_use_new_file_prefix": "phase15g_current_signal",
            },
            "fresh_data_source_policy": {
                "allowed_primary_source": "existing_project_market_data_pipeline",
                "allowed_fallback_source": "manual_fresh_spy_ohlcv_file",
                "minimum_required_fields": ["date", "SPY_close", "SPY_return"],
                "require_data_beyond_pinned_endpoint": True,
            },
            "current_signal_update_policy": {
                "output_file": "reports/phase15g_current_signal_file.csv",
                "max_signal_staleness_days": 3,
                "generation_frequency": "daily_on_market_days",
                "failed_data_pull_policy": "write_blocked_signal_file_with_failure_reason",
            },
            "required_current_signal_output_columns": [
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
                "paper_dry_run_allowed",
                "paper_trading_allowed",
                "paper_readiness_status",
                "blocking_warnings",
                "benchmark_spy_close_or_return_source",
            ],
            "cadence_policy": {
                "preferred_frequency": "daily_on_market_days",
                "acceptable_manual_frequency_until_automation": "weekly_review_with_daily_data_when_available",
                "block_if_latest_market_data_older_than_days": 3,
            },
            "failure_handling_policy": {
                "if_latest_data_missing": "block_signal_and_write_failure_reason",
                "if_switch_history_missing": "block_dry_run_even_if_signal_fresh",
            },
            "allow_data_pull_execution": False,
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
            "phase15g_boundary": {
                "allowed_next_step": "Fresh data extension implementation and current signal generation only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
    }


def test_phase15e_to_15f_attributes_missing_switch_source_and_preregisters_fresh_data(tmp_path):
    _write_source_reports(tmp_path)
    config = _config(tmp_path)

    out_e = save_phase15e_operational_switch_source_attribution(
        config=config,
        reports_dir=tmp_path,
    )
    out_f = save_phase15f_fresh_data_extension_preregistration(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_e["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_f["conclusion"].iloc[0]["all_gates_passed"])

    decision = out_e["attribution_decision"].iloc[0]
    assert decision["decision"] == "true_36_switch_source_not_found_patch_required"
    assert bool(decision["changed_switch_audit_classified_as_intermediate"])
    assert bool(decision["source_code_patch_required"])

    assert not bool(out_f["conclusion"].iloc[0]["data_pull_executed"])
    assert not bool(out_f["conclusion"].iloc[0]["paper_trading_ready"])