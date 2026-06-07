import pandas as pd

from market_strats.analysis.fresh_extension_pipeline import (
    build_phase15w_fresh_extension_config,
    build_phase15y_post_endpoint_stream,
    save_phase15wxyz_reports,
)


REQUIRED_EXPORT_COLUMNS = [
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


def test_phase15w_fresh_config_removes_research_endpoint_without_mutating_original():
    config = {
        "end_date": "2026-05-01",
        "research_period": {"end_date": "2026-05-01"},
    }
    phase_config = {
        "pinned_research_endpoint": "2026-05-01",
        "fresh_extension_end_date": None,
    }

    fresh_config, report = build_phase15w_fresh_extension_config(
        config=config,
        phase_config=phase_config,
    )

    assert config["end_date"] == "2026-05-01"
    assert config["research_period"]["end_date"] == "2026-05-01"
    assert fresh_config["end_date"] is None
    assert fresh_config["research_period"]["end_date"] is None
    assert bool(report.iloc[0]["fresh_config_is_copy"])


def test_phase15y_exports_post_endpoint_target_weights():
    final_candidate = pd.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-29", "2026-06-02"],
            "adj_close": [10000.0, 10100.0, 10200.0],  # candidate equity, not SPY price
            "signal_price": [620.0, 625.0, 630.0],  # actual SPY/proxy price
            "strategy_return": [0.0, 0.01, 0.0099],
            "target_offensive_weight": [1.0, 1.0, 0.0],
        }
    )
    phase_config = {
        "pinned_research_endpoint": "2026-05-01",
        "target_weight_source": "verified_project_generated",
        "required_export_columns": REQUIRED_EXPORT_COLUMNS,
    }

    stream, summary = build_phase15y_post_endpoint_stream(
        final_candidate=final_candidate,
        phase_config=phase_config,
    )

    assert len(stream) == 2
    assert list(stream["date"]) == ["2026-05-29", "2026-06-02"]
    assert list(stream["SPY_close"]) == [625.0, 630.0]
    assert list(stream["target_offensive_weight"]) == [1.0, 0.0]
    assert stream["target_weight_source"].eq("verified_project_generated").all()
    assert bool(summary.iloc[0]["rule_generated_stream_valid"])


def test_phase15y_blocks_when_no_post_endpoint_rows():
    final_candidate = pd.DataFrame(
        {
            "date": ["2026-04-30", "2026-05-01"],
            "adj_close": [10000.0, 10100.0],
            "strategy_return": [0.0, 0.01],
            "target_offensive_weight": [1.0, 1.0],
        }
    )
    phase_config = {
        "pinned_research_endpoint": "2026-05-01",
        "target_weight_source": "verified_project_generated",
        "required_export_columns": REQUIRED_EXPORT_COLUMNS,
    }

    stream, summary = build_phase15y_post_endpoint_stream(
        final_candidate=final_candidate,
        phase_config=phase_config,
    )

    assert stream.empty
    assert int(summary.iloc[0]["post_endpoint_rows"]) == 0
    assert not bool(summary.iloc[0]["rule_generated_stream_valid"])
    assert summary.iloc[0]["failure_reason"] == "no_post_endpoint_rows_in_fresh_final_candidate"


def test_phase15y_uses_signal_price_not_overlay_equity_as_spy_close():
    final_candidate = pd.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-04", "2026-05-05"],
            "adj_close": [70000.0, 71516.0, 72089.0],  # overlay equity, not SPY
            "signal_price": [620.0, 621.0, 625.0],  # actual SPY/proxy price
            "strategy_return": [0.0, 0.01, 0.008],
            "target_offensive_weight": [1.0, 1.0, 1.0],
        }
    )
    phase_config = {
        "pinned_research_endpoint": "2026-05-01",
        "target_weight_source": "verified_project_generated",
        "required_export_columns": REQUIRED_EXPORT_COLUMNS,
    }

    stream, summary = build_phase15y_post_endpoint_stream(
        final_candidate=final_candidate,
        phase_config=phase_config,
    )

    assert list(stream["SPY_close"]) == [621.0, 625.0]
    assert stream["SPY_close"].max() < 1000.0
    assert bool(summary.iloc[0]["rule_generated_stream_valid"])


def test_phase15wxyz_writes_rule_generated_handoff_without_mutating_config(tmp_path):
    config = {
        "research_period": {"end_date": "2026-05-01"},
        "phase15wxyz_fresh_extension_pipeline": {
            "enabled": True,
            "pinned_research_endpoint": "2026-05-01",
            "target_weight_source": "verified_project_generated",
            "output_file": str(tmp_path / "reports" / "phase15y_stream.csv"),
            "handoff_file_for_phase15q": str(
                tmp_path / "data" / "fresh" / "phase15q_rule_generated_candidate_stream.csv"
            ),
            "required_export_columns": REQUIRED_EXPORT_COLUMNS,
            "decision_policy": {
                "decision_if_export_valid": "phase15q_15r_rerun_allowed_next",
                "decision_if_export_blocked": "blocked_fresh_extension_pipeline_no_valid_post_endpoint_rows",
            },
        },
    }
    final_candidate = pd.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-29", "2026-06-02"],
            "signal_price": [620.0, 625.0, 630.0],
            "strategy_return": [0.0, 0.01, 0.0099],
            "target_offensive_weight": [1.0, 1.0, 0.0],
        }
    )

    outputs = save_phase15wxyz_reports(
        config=config,
        reports_dir=tmp_path / "reports",
        fresh_config_report=pd.DataFrame(
            [{"fresh_config_is_copy": True, "canonical_report_mutation": False}]
        ),
        fresh_pipeline_report=pd.DataFrame(
            [{"fresh_final_candidate_rows": 3, "canonical_report_mutation": False}]
        ),
        final_candidate=final_candidate,
    )

    handoff = tmp_path / "data" / "fresh" / "phase15q_rule_generated_candidate_stream.csv"
    handoff_frame = pd.read_csv(handoff)

    assert config["research_period"]["end_date"] == "2026-05-01"
    assert bool(outputs["conclusion"].iloc[0]["handoff_file_written"])
    assert len(handoff_frame) == 2
    assert list(handoff_frame["date"]) == ["2026-05-29", "2026-06-02"]
    assert handoff_frame["target_weight_source"].eq("verified_project_generated").all()
    assert handoff_frame["is_out_of_sample_extension"].map(bool).all()
