from pathlib import Path

import pandas as pd

import market_strats.analysis.post_endpoint_candidate_stream as extension
from market_strats.analysis.post_endpoint_candidate_stream import (
    save_phase15o_post_endpoint_candidate_stream_extension,
    save_phase15p_extended_candidate_stream_audit,
)


def _write_source_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 15N",
                "verdict": "Completed — fresh signal audit and paper dry-run eligibility decision passed",
                "all_gates_passed": True,
                "decision": "blocked_fresh_signal_audit_failed",
            }
        ]
    ).to_csv(tmp_path / "phase15n_fresh_signal_audit_conclusion.csv", index=False)

    pd.DataFrame([{"gate": "dummy", "passed": True, "result": "Passed"}]).to_csv(
        tmp_path / "phase15n_fresh_signal_audit_gate_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "decision": "blocked_fresh_signal_audit_failed",
                "paper_dry_run_preregistration_allowed_next": False,
            }
        ]
    ).to_csv(tmp_path / "phase15n_fresh_signal_audit_decision_report.csv", index=False)

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


def _mock_final_candidate():
    return pd.DataFrame(
        {
            "date": ["2026-05-29", "2026-06-01", "2026-06-02"],
            "SPY_close": [600.0, 601.0, 603.0],
            "SPY_return": [0.001, -0.002, 0.003],
            "target_offensive_weight": [1.0, 1.0, 1.0],
        }
    )


def _write_candidate_stream(path: Path, date: str, exposure: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": date,
                "SPY_close": 600.0,
                "SPY_return": 0.001,
                "target_offensive_weight": exposure,
                "data_source_timestamp": date,
                "pinned_research_endpoint": "2026-05-01",
                "is_out_of_sample_extension": True,
                "benchmark_update_flag": "pass",
                "stream_row_validity_flag": "pass",
                "blocking_warnings": "",
            }
        ]
    ).to_csv(path, index=False)


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
        "pinned_research_endpoint",
        "is_out_of_sample_extension",
        "benchmark_update_flag",
        "stream_row_validity_flag",
        "blocking_warnings",
    ]

    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase15m_fresh_current_signal_generation": {"enabled": False},
        "phase15n_fresh_signal_audit_paper_dry_run_eligibility": {"enabled": False},
        "phase15o_post_endpoint_candidate_stream_extension": {
            "enabled": True,
            "execution_role": "Post-endpoint candidate stream data extension implementation only",
            "implementation_classification": "A/B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "audit_current_date": "2026-06-02",
            "output_file": str(tmp_path / "phase15o_post_endpoint_candidate_stream.csv"),
            "source_reports": {
                "phase15n_conclusion": str(tmp_path / "phase15n_fresh_signal_audit_conclusion.csv"),
                "phase15n_gate_report": str(tmp_path / "phase15n_fresh_signal_audit_gate_report.csv"),
                "phase15n_decision_report": str(tmp_path / "phase15n_fresh_signal_audit_decision_report.csv"),
                "pinned_endpoint_signal": str(tmp_path / "phase15k_pinned_endpoint_signal_file.csv"),
                "switch_log": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"),
                "selected_switch_definition": str(tmp_path / "phase15i_column_semantics_selected_switch_definition.csv"),
            },
            "candidate_stream_sources": {
                "preferred_manual_candidate_stream_file": str(tmp_path / "missing_manual.csv"),
                "preferred_existing_fresh_candidate_stream_file": str(tmp_path / "missing_existing.csv"),
                "allow_in_memory_final_candidate_frame_if_post_endpoint_rows_exist": True,
            },
            "selected_exposure_fallback_priority": ["target_offensive_weight"],
            "benchmark_policy": {
                "acceptable_close_columns": ["SPY_close", "adj_close"],
                "acceptable_return_columns": ["SPY_return", "benchmark_return"],
            },
            "required_extended_candidate_stream_columns": required_cols,
            "allow_post_endpoint_candidate_stream_write": True,
            "allow_fresh_data_pull_execution": False,
            "allow_canonical_report_mutation": False,
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
            "phase15p_boundary": {
                "allowed_next_step": "Extended candidate stream audit and fresh signal rerun eligibility only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase15p_extended_candidate_stream_audit": {
            "enabled": True,
            "audit_role": "Extended candidate stream audit and fresh signal rerun eligibility only",
            "implementation_classification": "B",
            "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "pinned_research_endpoint": "2026-05-01",
            "expected_runtime_flags": {
                "phase15m_fresh_current_signal_generation": False,
                "phase15n_fresh_signal_audit_paper_dry_run_eligibility": False,
                "phase15o_post_endpoint_candidate_stream_extension": True,
                "phase15p_extended_candidate_stream_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase15o_reports": {
                "conclusion": str(tmp_path / "phase15o_candidate_stream_conclusion.csv"),
                "gate_report": str(tmp_path / "phase15o_candidate_stream_gate_report.csv"),
                "candidate_stream": str(tmp_path / "phase15o_post_endpoint_candidate_stream.csv"),
                "extension_summary": str(tmp_path / "phase15o_candidate_stream_extension_summary.csv"),
                "required_column_check": str(tmp_path / "phase15o_candidate_stream_required_column_check.csv"),
            },
            "required_extended_candidate_stream_columns": required_cols,
            "audit_thresholds": {
                "min_post_endpoint_rows": 1,
                "require_all_rows_after_pinned_endpoint": True,
                "require_benchmark_update_pass": True,
                "require_target_exposure_present": True,
                "require_exposure_range_0_to_1": True,
                "require_out_of_sample_label": True,
            },
            "decision_policy": {
                "decision_if_stream_valid": "fresh_signal_rerun_allowed_next",
                "decision_if_stream_invalid": "blocked_extended_candidate_stream_invalid",
            },
            "phase15m_rerun_boundary": {
                "allowed_next_step_if_passed": "Rerun Phase 15M and Phase 15N with post-endpoint candidate stream",
                "allowed_next_step_if_blocked": "Post-endpoint candidate stream repair only",
                "forbidden_next_step": "paper dry-run, broker/API integration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
            "allow_phase15m_rerun_if_passed": True,
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


def test_phase15o_to_15p_builds_and_audits_extended_candidate_stream(tmp_path, monkeypatch):
    _write_source_reports(tmp_path)
    config = _config(tmp_path)

    monkeypatch.setattr(
        extension,
        "_find_final_candidate_frame",
        lambda relative_momentum_outputs, ticker_outputs, config: _mock_final_candidate(),
    )

    out_o = save_phase15o_post_endpoint_candidate_stream_extension(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs={},
        ticker_outputs={},
    )
    out_p = save_phase15p_extended_candidate_stream_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_o["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_p["conclusion"].iloc[0]["all_gates_passed"])

    summary = out_o["extension_summary"].iloc[0]
    assert int(summary["post_endpoint_rows"]) == 3
    assert bool(summary["candidate_stream_valid"])

    decision = out_p["decision_report"].iloc[0]
    assert decision["decision"] == "fresh_signal_rerun_allowed_next"
    assert bool(decision["fresh_signal_rerun_allowed_next"])
    assert not bool(decision["paper_dry_run_preregistration_allowed_next"])
    assert not bool(decision["paper_trading_ready"])


def test_phase15o_prefers_rule_generated_handoff_when_wxyz_enabled(tmp_path):
    _write_source_reports(tmp_path)
    config = _config(tmp_path)
    manual_path = tmp_path / "manual.csv"
    rule_path = tmp_path / "rule.csv"
    _write_candidate_stream(manual_path, "2026-05-13", 1.0)
    _write_candidate_stream(rule_path, "2026-06-02", 0.0)

    config["phase15wxyz_fresh_extension_pipeline"] = {"enabled": True}
    config["phase15o_post_endpoint_candidate_stream_extension"]["candidate_stream_sources"][
        "preferred_manual_candidate_stream_file"
    ] = str(manual_path)
    config["phase15o_post_endpoint_candidate_stream_extension"]["candidate_stream_sources"][
        "preferred_rule_generated_candidate_stream_file"
    ] = str(rule_path)

    out_o = save_phase15o_post_endpoint_candidate_stream_extension(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    summary = out_o["extension_summary"].iloc[0]
    stream = out_o["post_endpoint_candidate_stream"]
    assert summary["data_source"] == str(rule_path)
    assert stream.iloc[-1]["date"] == "2026-06-02"
    assert stream.iloc[-1]["current_exposure"] == 0.0


def test_phase15p_passes_audit_mechanically_but_blocks_empty_stream(tmp_path, monkeypatch):
    _write_source_reports(tmp_path)
    config = _config(tmp_path)

    monkeypatch.setattr(
        extension,
        "_find_final_candidate_frame",
        lambda relative_momentum_outputs, ticker_outputs, config: pd.DataFrame(
            {
                "date": ["2026-04-30", "2026-05-01"],
                "SPY_close": [600.0, 601.0],
                "SPY_return": [0.001, 0.002],
                "target_offensive_weight": [1.0, 1.0],
            }
        ),
    )

    out_o = save_phase15o_post_endpoint_candidate_stream_extension(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs={},
        ticker_outputs={},
    )
    out_p = save_phase15p_extended_candidate_stream_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_o["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_p["conclusion"].iloc[0]["all_gates_passed"])

    extension_summary = out_o["extension_summary"].iloc[0]
    assert int(extension_summary["post_endpoint_rows"]) == 0
    assert not bool(extension_summary["candidate_stream_valid"])

    decision = out_p["decision_report"].iloc[0]
    assert decision["decision"] == "blocked_extended_candidate_stream_invalid"
    assert not bool(decision["fresh_signal_rerun_allowed_next"])
    assert not bool(decision["paper_dry_run_preregistration_allowed_next"])
    assert not bool(decision["paper_trading_ready"])
