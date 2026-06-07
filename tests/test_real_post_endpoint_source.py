from pathlib import Path

import pandas as pd

from market_strats.analysis.real_post_endpoint_source import (
    save_phase15q_post_endpoint_data_source_creation,
    save_phase15r_real_post_endpoint_stream_validation,
)


def _write_source_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 15P",
                "verdict": "Completed — extended candidate stream audit passed",
                "all_gates_passed": True,
                "decision": "blocked_extended_candidate_stream_invalid",
            }
        ]
    ).to_csv(tmp_path / "phase15p_extended_stream_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase15p_extended_stream_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "blocked_extended_candidate_stream_invalid",
                "fresh_signal_rerun_allowed_next": False,
            }
        ]
    ).to_csv(tmp_path / "phase15p_extended_stream_decision_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "endpoint_date": "2026-05-01",
                "endpoint_mode": "offensive_spy",
                "endpoint_exposure": 1.0,
            }
        ]
    ).to_csv(tmp_path / "phase15k_pinned_endpoint_signal_file.csv", index=False)

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


def _write_valid_rule_generated_source(tmp_path: Path):
    fresh_dir = tmp_path / "data" / "fresh"
    fresh_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "date": "2026-05-29",
                "SPY_close": 600.0,
                "SPY_return": 0.001,
                "target_offensive_weight": 1.0,
                "target_weight_source": "phase6b_rule_engine",
                "data_source_timestamp": "2026-05-29",
            },
            {
                "date": "2026-06-02",
                "SPY_close": 603.0,
                "SPY_return": 0.003,
                "target_offensive_weight": 1.0,
                "target_weight_source": "phase6b_rule_engine",
                "data_source_timestamp": "2026-06-02",
            },
        ]
    ).to_csv(fresh_dir / "phase15q_rule_generated_candidate_stream.csv", index=False)


def _write_valid_wxyz_rule_generated_source(tmp_path: Path):
    fresh_dir = tmp_path / "data" / "fresh"
    fresh_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "date": "2026-05-29",
                "SPY_close": 600.0,
                "SPY_return": 0.001,
                "target_offensive_weight": 1.0,
                "target_weight_source": "verified_project_generated",
                "data_source_timestamp": "2026-05-29",
            },
            {
                "date": "2026-06-02",
                "SPY_close": 603.0,
                "SPY_return": 0.003,
                "target_offensive_weight": 0.0,
                "target_weight_source": "verified_project_generated",
                "data_source_timestamp": "2026-06-02",
            },
        ]
    ).to_csv(fresh_dir / "phase15q_rule_generated_candidate_stream.csv", index=False)


def _write_invalid_raw_spy_only_source(tmp_path: Path):
    fresh_dir = tmp_path / "data" / "fresh"
    fresh_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "date": "2026-06-02",
                "SPY_close": 603.0,
                "SPY_return": 0.003,
                "data_source_timestamp": "2026-06-02",
            }
        ]
    ).to_csv(fresh_dir / "phase15q_fresh_spy_ohlcv.csv", index=False)


def _config(tmp_path: Path):
    required_cols = [
        "date",
        "SPY_close",
        "SPY_return",
        "target_offensive_weight",
        "current_mode",
        "current_exposure",
        "previous_mode",
        "previous_exposure",
        "switch_triggered",
        "data_source",
        "data_source_timestamp",
        "target_weight_source",
        "target_weight_source_valid_flag",
        "pinned_research_endpoint",
        "is_out_of_sample_extension",
        "benchmark_update_flag",
        "stream_row_validity_flag",
        "blocking_warnings",
    ]

    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase15o_post_endpoint_candidate_stream_extension": {"enabled": False},
        "phase15p_extended_candidate_stream_audit": {"enabled": False},
        "phase15q_post_endpoint_data_source_creation": {
            "enabled": True,
            "execution_role": "Manual or fresh post-endpoint data source creation only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "audit_current_date": "2026-06-02",
            "output_file": str(tmp_path / "reports" / "phase15q_post_endpoint_candidate_stream.csv"),
            "handoff_file_for_phase15o": str(tmp_path / "data" / "fresh" / "phase15o_manual_candidate_stream.csv"),
            "source_reports": {
                "phase15p_conclusion": str(tmp_path / "phase15p_extended_stream_conclusion.csv"),
                "phase15p_gate_report": str(tmp_path / "phase15p_extended_stream_gate_report.csv"),
                "phase15p_decision_report": str(tmp_path / "phase15p_extended_stream_decision_report.csv"),
                "pinned_endpoint_signal": str(tmp_path / "phase15k_pinned_endpoint_signal_file.csv"),
                "selected_switch_definition": str(tmp_path / "phase15i_column_semantics_selected_switch_definition.csv"),
            },
            "candidate_source_priority": {
                "rule_generated_candidate_stream": str(tmp_path / "data" / "fresh" / "phase15q_rule_generated_candidate_stream.csv"),
                "verified_manual_candidate_stream": str(tmp_path / "data" / "fresh" / "phase15q_verified_manual_candidate_stream.csv"),
                "existing_phase15o_manual_stream": str(tmp_path / "data" / "fresh" / "phase15o_manual_candidate_stream.csv"),
                "raw_spy_ohlcv_only": str(tmp_path / "data" / "fresh" / "phase15q_fresh_spy_ohlcv.csv"),
            },
            "accepted_target_weight_sources": [
                "phase6b_rule_engine",
                "phase6b_loose_relief_rule_replay",
                "project_rule_replay",
                "verified_project_generated",
            ],
            "rejected_target_weight_sources": ["manual_fill", "guessed", "carry_forward_only", "unknown", ""],
            "benchmark_policy": {
                "acceptable_close_columns": ["SPY_close", "adj_close"],
                "acceptable_return_columns": ["SPY_return", "benchmark_return"],
            },
            "required_phase15q_output_columns": required_cols,
            "allow_post_endpoint_source_creation": True,
            "allow_fresh_data_pull_execution": False,
            "allow_canonical_report_mutation": False,
            "allow_current_signal_generation": False,
            "allow_phase15o_rerun": False,
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
            "phase15r_boundary": {
                "allowed_next_step": "Real post-endpoint candidate stream validation and 15O/15P rerun preparation only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15r_real_post_endpoint_stream_validation": {
            "enabled": True,
            "audit_role": "Real post-endpoint candidate stream validation and 15O/15P rerun preparation only",
            "implementation_classification": "B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "expected_runtime_flags": {
                "phase15o_post_endpoint_candidate_stream_extension": False,
                "phase15p_extended_candidate_stream_audit": False,
                "phase15q_post_endpoint_data_source_creation": True,
                "phase15r_real_post_endpoint_stream_validation": True,
                "relative_momentum_allocator": True,
            },
            "phase15q_reports": {
                "conclusion": str(tmp_path / "reports" / "phase15q_data_source_conclusion.csv"),
                "gate_report": str(tmp_path / "reports" / "phase15q_data_source_gate_report.csv"),
                "candidate_stream": str(tmp_path / "reports" / "phase15q_post_endpoint_candidate_stream.csv"),
                "creation_summary": str(tmp_path / "reports" / "phase15q_data_source_creation_summary.csv"),
                "required_column_check": str(tmp_path / "reports" / "phase15q_data_source_required_column_check.csv"),
            },
            "handoff_file_for_phase15o": str(tmp_path / "data" / "fresh" / "phase15o_manual_candidate_stream.csv"),
            "required_phase15q_output_columns": required_cols,
            "validation_policy": {
                "min_post_endpoint_rows": 1,
                "require_all_rows_after_pinned_endpoint": True,
                "require_benchmark_update_pass": True,
                "require_target_weight_source_valid": True,
                "require_target_offensive_weight_present": True,
                "require_target_exposure_range_0_to_1": True,
                "require_out_of_sample_label": True,
                "require_handoff_file_written_if_valid": True,
                "require_no_canonical_mutation": True,
            },
            "decision_policy": {
                "decision_if_valid": "phase15o_15p_rerun_allowed_next",
                "decision_if_invalid": "blocked_real_post_endpoint_source_invalid",
            },
            "phase15o_rerun_boundary": {
                "allowed_next_step_if_passed": "Rerun Phase 15O and Phase 15P using validated handoff stream",
                "allowed_next_step_if_blocked": "Repair or provide real post-endpoint source only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
            "allow_phase15o_15p_rerun_if_passed": True,
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


def test_phase15q_to_15r_validates_rule_generated_fresh_source(tmp_path):
    _write_source_reports(tmp_path)
    _write_valid_rule_generated_source(tmp_path)
    config = _config(tmp_path)

    reports_dir = tmp_path / "reports"

    out_q = save_phase15q_post_endpoint_data_source_creation(
        config=config,
        reports_dir=reports_dir,
    )
    out_r = save_phase15r_real_post_endpoint_stream_validation(
        config=config,
        reports_dir=reports_dir,
    )

    assert bool(out_q["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_r["conclusion"].iloc[0]["all_gates_passed"])

    q_summary = out_q["creation_summary"].iloc[0]
    assert int(q_summary["post_endpoint_rows"]) == 2
    assert bool(q_summary["candidate_stream_valid"])

    r_decision = out_r["decision_report"].iloc[0]
    assert r_decision["decision"] == "phase15o_15p_rerun_allowed_next"


def test_phase15q_to_15r_consumes_wxyz_verified_project_generated_handoff(tmp_path):
    _write_source_reports(tmp_path)
    _write_valid_wxyz_rule_generated_source(tmp_path)
    config = _config(tmp_path)

    reports_dir = tmp_path / "reports"

    out_q = save_phase15q_post_endpoint_data_source_creation(
        config=config,
        reports_dir=reports_dir,
    )
    out_r = save_phase15r_real_post_endpoint_stream_validation(
        config=config,
        reports_dir=reports_dir,
    )

    stream = out_q["post_endpoint_candidate_stream"]
    assert stream["target_weight_source"].eq("verified_project_generated").all()
    assert stream["target_weight_source_valid_flag"].eq("pass").all()
    assert bool(out_q["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_r["conclusion"].iloc[0]["all_gates_passed"])
    r_decision = out_r["decision_report"].iloc[0]
    assert bool(r_decision["phase15o_15p_rerun_allowed_next"])
    assert not bool(r_decision["phase15m_15n_rerun_allowed_next"])
    assert not bool(r_decision["paper_trading_ready"])


def test_phase15q_to_15r_blocks_raw_spy_without_rule_target(tmp_path):
    _write_source_reports(tmp_path)
    _write_invalid_raw_spy_only_source(tmp_path)
    config = _config(tmp_path)

    reports_dir = tmp_path / "reports"

    out_q = save_phase15q_post_endpoint_data_source_creation(
        config=config,
        reports_dir=reports_dir,
    )
    out_r = save_phase15r_real_post_endpoint_stream_validation(
        config=config,
        reports_dir=reports_dir,
    )

    assert bool(out_q["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_r["conclusion"].iloc[0]["all_gates_passed"])

    q_summary = out_q["creation_summary"].iloc[0]
    assert int(q_summary["post_endpoint_rows"]) == 1
    assert not bool(q_summary["candidate_stream_valid"])

    r_decision = out_r["decision_report"].iloc[0]
    assert r_decision["decision"] == "blocked_real_post_endpoint_source_invalid"
    assert not bool(r_decision["phase15o_15p_rerun_allowed_next"])
    assert not bool(r_decision["paper_dry_run_preregistration_allowed_next"])
    assert not bool(r_decision["paper_trading_ready"])
