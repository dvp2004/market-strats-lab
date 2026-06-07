from pathlib import Path

import pandas as pd

from market_strats.analysis.reusable_rule_replay_engine_bundle import (
    save_phase15u_reusable_phase6b_rule_replay_engine,
    save_phase15v_post_endpoint_rule_based_candidate_stream,
)
from market_strats.strategies.phase6b_loose_relief_replay import (
    replay_phase6b_loose_relief_target_weights,
)


def _write_phase15t_reports(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "phase": "Phase 15T",
                "all_gates_passed": True,
                "decision": "blocked_rule_generated_stream_unavailable_or_invalid",
            }
        ]
    ).to_csv(reports / "phase15t_rule_export_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        reports / "phase15t_rule_export_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "blocked_rule_generated_stream_unavailable_or_invalid",
                "phase15q_15r_rerun_allowed_next": False,
            }
        ]
    ).to_csv(reports / "phase15t_rule_export_decision_report.csv", index=False)


def _write_valid_rule_input(tmp_path: Path):
    fresh = tmp_path / "data" / "fresh"
    fresh.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "date": "2026-05-29",
                "SPY_close": 600.0,
                "SPY_return": 0.001,
                "final_phase6b_signal": "offensive_spy",
                "data_source_timestamp": "2026-05-29",
            },
            {
                "date": "2026-06-02",
                "SPY_close": 603.0,
                "SPY_return": 0.003,
                "final_phase6b_signal": "offensive_spy",
                "data_source_timestamp": "2026-06-02",
            },
        ]
    ).to_csv(fresh / "phase15u_rule_input_panel.csv", index=False)


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
        "phase15u_reusable_phase6b_rule_replay_engine": {
            "enabled": True,
            "execution_role": "Reusable Phase 6B/6C rule replay engine extraction only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "audit_current_date": "2026-06-02",
            "source_reports": {
                "phase15t_conclusion": str(tmp_path / "reports" / "phase15t_rule_export_conclusion.csv"),
                "phase15t_gate_report": str(tmp_path / "reports" / "phase15t_rule_export_gate_report.csv"),
                "phase15t_decision_report": str(tmp_path / "reports" / "phase15t_rule_export_decision_report.csv"),
            },
            "replay_engine_contract": {
                "module_path": "src/market_strats/strategies/phase6b_loose_relief_replay.py",
                "function_name": "replay_phase6b_loose_relief_target_weights",
                "target_weight_source": "phase6b_loose_relief_rule_replay",
                "rejected_inputs": ["manual_fill", "carry_forward_only", "guessed", "unknown"],
            },
            "required_engine_output_columns": required_cols,
            "allow_replay_engine_extraction": True,
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
            "phase15v_boundary": {
                "allowed_next_step": "Post-endpoint rule-based candidate stream generation only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15v_post_endpoint_rule_based_candidate_stream": {
            "enabled": True,
            "execution_role": "Post-endpoint rule-based candidate stream generation only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "audit_current_date": "2026-06-02",
            "rule_input_sources": {
                "preferred_rule_input_panel": str(tmp_path / "data" / "fresh" / "phase15u_rule_input_panel.csv"),
                "fallback_rule_input_panel": str(tmp_path / "reports" / "phase15u_rule_input_panel.csv"),
            },
            "output_file": str(tmp_path / "reports" / "phase15v_rule_based_candidate_stream.csv"),
            "handoff_file_for_phase15q": str(tmp_path / "data" / "fresh" / "phase15q_rule_generated_candidate_stream.csv"),
            "required_rule_input_columns_any_signal": [
                "final_phase6b_signal",
                "confirmed_signal",
                "guarded_signal",
                "final_signal",
                "target_signal",
                "current_mode",
            ],
            "required_export_columns": required_cols,
            "decision_policy": {
                "decision_if_export_valid": "phase15q_15r_rerun_allowed_next",
                "decision_if_export_blocked": "blocked_rule_input_missing_or_invalid",
            },
            "allow_rule_based_stream_export": True,
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
                "allowed_next_step_if_blocked": "Provide or generate valid post-endpoint Phase 6B/6C rule-input panel only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
    }


def test_replay_engine_maps_rule_signal_to_target_weight():
    rule_input = pd.DataFrame(
        [
            {"date": "2026-06-01", "SPY_close": 600.0, "SPY_return": 0.01, "final_phase6b_signal": "offensive_spy"},
            {"date": "2026-06-02", "SPY_close": 590.0, "SPY_return": -0.02, "final_phase6b_signal": "defensive_or_cash"},
        ]
    )

    result = replay_phase6b_loose_relief_target_weights(
        rule_input=rule_input,
        pinned_research_endpoint="2026-05-01",
        audit_current_date="2026-06-02",
    )

    assert list(result.stream["target_offensive_weight"]) == [1.0, 0.0]
    assert result.stream["target_weight_source"].eq("phase6b_loose_relief_rule_replay").all()
    assert bool(result.summary.iloc[0]["rule_replay_stream_valid"])


def test_phase15u_15v_exports_handoff_when_rule_input_exists(tmp_path):
    _write_phase15t_reports(tmp_path)
    _write_valid_rule_input(tmp_path)
    config = _config(tmp_path)

    out_u = save_phase15u_reusable_phase6b_rule_replay_engine(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    out_v = save_phase15v_post_endpoint_rule_based_candidate_stream(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    assert bool(out_u["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_v["conclusion"].iloc[0]["all_gates_passed"])

    summary = out_v["replay_summary"].iloc[0]
    assert int(summary["post_endpoint_rows"]) == 2
    assert bool(summary["rule_replay_stream_valid"])

    decision = out_v["decision_report"].iloc[0]
    assert decision["decision"] == "phase15q_15r_rerun_allowed_next"
    assert bool(decision["phase15q_15r_rerun_allowed_next"])
    assert not bool(decision["paper_trading_ready"])

    handoff = tmp_path / "data" / "fresh" / "phase15q_rule_generated_candidate_stream.csv"
    assert handoff.exists()


def test_phase15v_blocks_when_rule_input_missing(tmp_path):
    _write_phase15t_reports(tmp_path)
    config = _config(tmp_path)

    out_u = save_phase15u_reusable_phase6b_rule_replay_engine(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    out_v = save_phase15v_post_endpoint_rule_based_candidate_stream(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    assert bool(out_u["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_v["conclusion"].iloc[0]["all_gates_passed"])

    decision = out_v["decision_report"].iloc[0]
    assert decision["decision"] == "blocked_rule_input_missing_or_invalid"
    assert not bool(decision["phase15q_15r_rerun_allowed_next"])
    assert not bool(decision["paper_trading_ready"])