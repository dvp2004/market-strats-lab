from pathlib import Path

import pandas as pd

import market_strats.analysis.phase6b_rule_replay_export as replay
from market_strats.analysis.phase6b_rule_replay_export import (
    save_phase15s_phase6b_rule_replay_source_discovery,
    save_phase15t_rule_generated_candidate_stream_export,
)


def _write_source_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 15R",
                "verdict": "Completed — real post-endpoint stream validation passed",
                "all_gates_passed": True,
                "decision": "blocked_real_post_endpoint_source_invalid",
            }
        ]
    ).to_csv(tmp_path / "phase15r_real_source_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase15r_real_source_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "blocked_real_post_endpoint_source_invalid",
                "phase15o_15p_rerun_allowed_next": False,
            }
        ]
    ).to_csv(tmp_path / "phase15r_real_source_decision_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "selected": True,
                "selected_column": "target_offensive_weight",
                "transform": "direct",
                "candidate_switch_count": 36,
            }
        ]
    ).to_csv(tmp_path / "phase15i_column_semantics_selected_switch_definition.csv", index=False)

    pd.DataFrame(
        [
            {
                "endpoint_date": "2026-05-01",
                "endpoint_mode": "offensive_spy",
                "endpoint_exposure": 1.0,
            }
        ]
    ).to_csv(tmp_path / "phase15k_pinned_endpoint_signal_file.csv", index=False)


def _write_codebase(tmp_path: Path):
    src = tmp_path / "src" / "market_strats"
    src.mkdir(parents=True, exist_ok=True)

    (src / "phase6b_logic.py").write_text(
        """
def phase6b_loose_relief_rule_replay():
    target_offensive_weight = 1.0
    loose_relief = True
    deep_drawdown_guard = False
    return target_offensive_weight
""",
        encoding="utf-8",
    )


def _mock_final_candidate_with_post_endpoint():
    return pd.DataFrame(
        {
            "date": ["2026-04-30", "2026-05-01", "2026-05-29", "2026-06-02"],
            "target_offensive_weight": [1.0, 1.0, 1.0, 1.0],
            "SPY_close": [590.0, 595.0, 600.0, 603.0],
            "SPY_return": [0.001, 0.002, 0.003, 0.004],
        }
    )


def _mock_final_candidate_without_post_endpoint():
    return pd.DataFrame(
        {
            "date": ["2026-04-30", "2026-05-01"],
            "target_offensive_weight": [1.0, 1.0],
            "SPY_close": [590.0, 595.0],
            "SPY_return": [0.001, 0.002],
        }
    )


def _config(tmp_path: Path):
    required_cols = [
        "date",
        "SPY_close",
        "SPY_return",
        "target_offensive_weight",
        "target_weight_source",
        "data_source_timestamp",
        "pinned_research_endpoint",
        "is_out_of_sample_extension",
        "benchmark_update_flag",
        "stream_row_validity_flag",
        "blocking_warnings",
    ]

    return {
        "phase15q_post_endpoint_data_source_creation": {"enabled": False},
        "phase15r_real_post_endpoint_stream_validation": {"enabled": False},
        "phase15s_phase6b_rule_replay_source_discovery": {
            "enabled": True,
            "discovery_role": "Phase 6B/6C rule replay source discovery only",
            "implementation_classification": "B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "audit_current_date": "2026-06-02",
            "source_reports": {
                "phase15r_conclusion": str(tmp_path / "phase15r_real_source_conclusion.csv"),
                "phase15r_gate_report": str(tmp_path / "phase15r_real_source_gate_report.csv"),
                "phase15r_decision_report": str(tmp_path / "phase15r_real_source_decision_report.csv"),
                "selected_switch_definition": str(tmp_path / "phase15i_column_semantics_selected_switch_definition.csv"),
            },
            "source_scan_paths": [str(tmp_path / "src" / "market_strats")],
            "discovery_patterns": {
                "target_column": ["target_offensive_weight", "target_defensive_weight"],
                "candidate_logic": ["loose_relief", "deep_drawdown_guard", "phase6b"],
                "export_logic": ["phase6b_loose_relief_execution_realistic_overlay", "_find_final_candidate_frame"],
            },
            "replay_path_decision_policy": {
                "decision_if_replay_path_discovered": "rule_replay_path_discovered_export_attempt_allowed_next",
                "decision_if_not_discovered": "blocked_rule_replay_path_not_discovered",
            },
            "allow_source_discovery": True,
            "allow_candidate_stream_export": False,
            "allow_current_signal_generation": False,
            "allow_phase15q_15r_rerun": False,
            "allow_phase15o_15p_rerun": False,
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
            "phase15t_boundary": {
                "allowed_next_step": "Post-endpoint rule-generated candidate stream export only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15t_rule_generated_candidate_stream_export": {
            "enabled": True,
            "execution_role": "Post-endpoint rule-generated candidate stream export only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "audit_current_date": "2026-06-02",
            "output_file": str(tmp_path / "reports" / "phase15t_rule_generated_candidate_stream.csv"),
            "handoff_file_for_phase15q": str(tmp_path / "data" / "fresh" / "phase15q_rule_generated_candidate_stream.csv"),
            "source_reports": {
                "phase15s_conclusion": str(tmp_path / "reports" / "phase15s_rule_replay_discovery_conclusion.csv"),
                "phase15s_gate_report": str(tmp_path / "reports" / "phase15s_rule_replay_discovery_gate_report.csv"),
                "phase15s_decision_report": str(tmp_path / "reports" / "phase15s_rule_replay_discovery_decision_report.csv"),
                "phase15s_target_column_discovery": str(tmp_path / "reports" / "phase15s_rule_replay_discovery_target_column_discovery.csv"),
                "pinned_endpoint_signal": str(tmp_path / "phase15k_pinned_endpoint_signal_file.csv"),
            },
            "accepted_target_weight_source": "verified_project_generated",
            "benchmark_policy": {
                "acceptable_close_columns": ["SPY_close", "adj_close"],
                "acceptable_return_columns": ["SPY_return", "benchmark_return"],
            },
            "required_export_columns": required_cols,
            "decision_policy": {
                "decision_if_export_valid": "phase15q_15r_rerun_allowed_next",
                "decision_if_export_blocked": "blocked_rule_generated_stream_unavailable_or_invalid",
            },
            "allow_rule_generated_stream_export": True,
            "allow_current_signal_generation": False,
            "allow_phase15q_15r_rerun": False,
            "allow_phase15o_15p_rerun": False,
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
            "phase15q_rerun_boundary": {
                "allowed_next_step_if_passed": "Rerun Phase 15Q and Phase 15R using rule-generated candidate stream",
                "allowed_next_step_if_blocked": "Expose or repair Phase 6B/6C rule replay path only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "relative_momentum_allocator": {"enabled": True},
    }


def test_phase15s_to_15t_exports_rule_generated_stream_when_post_endpoint_rows_exist(
    tmp_path,
    monkeypatch,
):
    _write_source_reports(tmp_path)
    _write_codebase(tmp_path)
    config = _config(tmp_path)

    monkeypatch.setattr(
        replay,
        "_find_final_candidate_frame",
        lambda relative_momentum_outputs, ticker_outputs, config: _mock_final_candidate_with_post_endpoint(),
    )

    reports_dir = tmp_path / "reports"

    out_s = save_phase15s_phase6b_rule_replay_source_discovery(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )
    out_t = save_phase15t_rule_generated_candidate_stream_export(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert bool(out_s["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_t["conclusion"].iloc[0]["all_gates_passed"])

    export_summary = out_t["export_summary"].iloc[0]
    assert int(export_summary["post_endpoint_rows"]) == 2
    assert bool(export_summary["rule_generated_stream_valid"])

    decision = out_t["decision_report"].iloc[0]
    assert decision["decision"] == "phase15q_15r_rerun_allowed_next"
    assert bool(decision["phase15q_15r_rerun_allowed_next"])
    assert not bool(decision["paper_trading_ready"])


def test_phase15s_to_15t_blocks_when_rule_output_has_no_post_endpoint_rows(
    tmp_path,
    monkeypatch,
):
    _write_source_reports(tmp_path)
    _write_codebase(tmp_path)
    config = _config(tmp_path)

    monkeypatch.setattr(
        replay,
        "_find_final_candidate_frame",
        lambda relative_momentum_outputs, ticker_outputs, config: _mock_final_candidate_without_post_endpoint(),
    )

    reports_dir = tmp_path / "reports"

    out_s = save_phase15s_phase6b_rule_replay_source_discovery(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )
    out_t = save_phase15t_rule_generated_candidate_stream_export(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert bool(out_s["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_t["conclusion"].iloc[0]["all_gates_passed"])

    export_summary = out_t["export_summary"].iloc[0]
    assert int(export_summary["post_endpoint_rows"]) == 0
    assert not bool(export_summary["rule_generated_stream_valid"])

    decision = out_t["decision_report"].iloc[0]
    assert decision["decision"] == "blocked_rule_generated_stream_unavailable_or_invalid"
    assert not bool(decision["phase15q_15r_rerun_allowed_next"])
    assert not bool(decision["paper_dry_run_preregistration_allowed_next"])
    assert not bool(decision["paper_trading_ready"])