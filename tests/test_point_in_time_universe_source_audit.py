from pathlib import Path

import pandas as pd

from market_strats.analysis.point_in_time_universe_source_audit import (
    build_membership_event_schema,
    build_source_registry,
    build_source_scorecard,
    save_phase23b_point_in_time_universe_source_audit,
    validate_membership_event_frame,
)


def _config(tmp_path: Path) -> dict:
    return {
        "phase23b_point_in_time_universe_source_audit": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "phase23b"),
            "dashboard_status_path": str(
                tmp_path
                / "reports"
                / "paper_trading"
                / "dashboard"
                / "phase23b_status.csv"
            ),
        }
    }


def _valid_events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "universe_id": "SP500_POINT_IN_TIME",
                "event_id": "spx-2020-001",
                "event_type": "ADD",
                "announcement_timestamp_utc": "2020-12-11T22:15:00Z",
                "effective_date": "2020-12-21",
                "permanent_security_id": "SEC-0001",
                "ticker": "AAA",
                "company_name": "Example Corp",
                "source_provider": "licensed_vendor",
                "source_reference": "sample-row-1",
                "source_retrieved_at_utc": "2026-06-13T00:00:00Z",
                "license_class": "licensed",
                "is_canonical": True,
            }
        ]
    )


def test_source_registry_identifies_official_candidates_for_both_universes():
    registry = build_source_registry()
    candidates = registry.loc[
        registry["source_class"].eq("official_licensed_canonical_candidate")
    ]
    assert {
        "SP500_POINT_IN_TIME",
        "NASDAQ100_POINT_IN_TIME",
    }.issubset(set(candidates["universe"]))
    assert candidates["official_provider"].all()
    assert candidates["license_or_subscription_required"].all()


def test_public_sources_are_not_misclassified_as_canonical_history():
    scorecard = build_source_scorecard(build_source_registry())
    public = scorecard.loc[scorecard["public_free_source"].astype(bool)]
    assert not bool(public["canonical_ready_now"].any())
    assert not bool(scorecard["canonical_ready_now"].any())


def test_event_schema_separates_announcement_and_effective_time():
    schema = build_membership_event_schema()
    columns = set(schema["column"])
    assert {
        "announcement_timestamp_utc",
        "effective_date",
        "permanent_security_id",
        "source_retrieved_at_utc",
        "license_class",
        "is_canonical",
    }.issubset(columns)


def test_membership_event_validator_accepts_valid_licensed_events():
    report = validate_membership_event_frame(_valid_events())
    assert report["passed"].all()
    assert bool(report["all_gates_passed"].iloc[0])


def test_membership_event_validator_rejects_lookahead_ordering():
    events = _valid_events()
    events.loc[0, "announcement_timestamp_utc"] = "2020-12-22T00:00:00Z"
    report = validate_membership_event_frame(events)
    row = report.loc[
        report["gate"].eq("announcement_not_after_effective_date")
    ].iloc[0]
    assert not bool(row["passed"])
    assert not bool(report["all_gates_passed"].iloc[0])


def test_phase23b_writes_audit_reports_and_blocks_model_training(tmp_path):
    outputs = save_phase23b_point_in_time_universe_source_audit(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )

    summary = outputs["summary"].iloc[0]
    assert bool(summary["phase_execution_gates_passed"])
    assert not bool(summary["universe_data_ready"])
    assert summary["phase23b_decision"] == (
        "phase23b_source_path_identified_acquisition_pending"
    )
    assert not bool(summary["model_training_allowed"])
    assert not bool(summary["backtest_allowed"])
    assert not bool(summary["promotion_allowed"])
    assert not bool(summary["live_trading_allowed"])
    assert not bool(summary["real_money_allowed"])
    assert not bool(summary["broker_api_integration_allowed"])

    output_dir = tmp_path / "reports" / "phase23b"
    required_files = [
        "phase23b_summary.csv",
        "phase23b_source_registry.csv",
        "phase23b_source_scorecard.csv",
        "phase23b_membership_event_schema.csv",
        "phase23b_membership_interval_schema.csv",
        "phase23b_reconstruction_rules.csv",
        "phase23b_validation_plan.csv",
        "phase23b_acquisition_plan.csv",
        "phase23b_gate_report.csv",
        "phase23b_membership_event_import_template.csv",
        "phase23b_point_in_time_universe_source_audit.md",
    ]
    for filename in required_files:
        assert (output_dir / filename).exists()


def test_run_backtest_exposes_phase23b_only_cli():
    source = Path("src/market_strats/run_backtest.py").read_text(encoding="utf-8")
    assert "--phase23b-only" in source
    assert "_run_phase23b_point_in_time_universe_source_audit(" in source
    assert "save_phase23b_point_in_time_universe_source_audit" in source
