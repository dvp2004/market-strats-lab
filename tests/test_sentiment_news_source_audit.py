from pathlib import Path

import pandas as pd

from market_strats.analysis.sentiment_news_source_audit import (
    build_coverage_policy,
    build_entity_linking_policy,
    build_news_event_schema,
    build_revision_deduplication_policy,
    build_sentiment_observation_schema,
    build_source_registry,
    build_source_scorecard,
    build_timestamp_availability_policy,
    save_phase23d_sentiment_news_source_audit,
    validate_news_event_frame,
    validate_sentiment_observation_frame,
)


def _config(tmp_path: Path) -> dict:
    return {
        "phase23d_sentiment_news_source_audit": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "phase23d"),
            "dashboard_status_path": str(
                tmp_path / "reports" / "paper_trading" / "dashboard" / "phase23d.csv"
            ),
        }
    }


def _valid_events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "event-1",
                "source_provider": "SEC EDGAR",
                "source_type": "SEC_FILING_TEXT",
                "source_event_id": "0000320193-25-000079",
                "root_event_id": "event-1",
                "published_timestamp_utc": "2025-08-01T16:30:00Z",
                "first_seen_timestamp_utc": "2025-08-01T16:30:05Z",
                "knowledge_timestamp_utc": "2025-08-01T16:35:05Z",
                "revision_timestamp_utc": "2025-08-01T16:30:00Z",
                "event_version": 1,
                "update_type": "INITIAL",
                "permanent_security_id": "US0378331005",
                "permanent_company_id": "CIK0000320193",
                "ticker": "AAPL",
                "headline": "Quarterly report",
                "body_hash": "sha256:example",
                "language": "en",
                "event_category": "earnings",
                "entity_link_method": "CIK",
                "source_reference": "https://www.sec.gov/Archives/example",
                "source_retrieved_at_utc": "2026-06-13T00:00:00Z",
                "source_revision": "sha256:source",
                "license_class": "public_official",
                "is_canonical": True,
            }
        ]
    )


def _valid_sentiment() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "event-1",
                "event_version": 1,
                "permanent_security_id": "US0378331005",
                "model_id": "baseline_finance_tone",
                "model_version": "v1",
                "calculated_timestamp_utc": "2025-08-01T16:36:00Z",
                "feature_available_timestamp_utc": "2025-08-01T16:36:00Z",
                "sentiment_score": 0.25,
                "confidence_score": 0.8,
                "entity_relevance_score": 1.0,
                "novelty_score": 0.6,
                "uncertainty_score": 0.2,
                "event_category": "earnings",
                "source_revision": "sha256:source",
                "feature_revision": "sha256:feature",
                "is_training_eligible": True,
            }
        ]
    )


def test_source_registry_spans_regulatory_news_transcripts_analysts_macro_and_social():
    registry = build_source_registry()
    assert {
        "SEC_FILING_TEXT_AND_EXHIBITS",
        "LICENSED_MACHINE_READABLE_NEWS",
        "LICENSED_EARNINGS_CALL_TRANSCRIPTS",
        "LICENSED_ANALYST_ACTIONS",
        "GDELT_2_GKG_EVENTS",
        "OFFICIAL_MACRO_RELEASES",
        "REDDIT_OFFICIAL_API",
        "X_OFFICIAL_API",
    }.issubset(set(registry["source_id"]))


def test_no_source_is_falsely_marked_canonical_data_ready():
    scorecard = build_source_scorecard(build_source_registry())
    assert scorecard["source_contract_ready"].any()
    assert not bool(scorecard["canonical_data_ready_now"].any())


def test_schemas_require_point_in_time_lineage_and_model_versioning():
    event_columns = set(build_news_event_schema()["column"])
    sentiment_columns = set(build_sentiment_observation_schema()["column"])
    assert {
        "published_timestamp_utc",
        "first_seen_timestamp_utc",
        "knowledge_timestamp_utc",
        "event_version",
        "body_hash",
        "permanent_security_id",
    }.issubset(event_columns)
    assert {
        "model_id",
        "model_version",
        "calculated_timestamp_utc",
        "feature_available_timestamp_utc",
        "source_revision",
    }.issubset(sentiment_columns)


def test_timestamp_revision_and_entity_policies_block_lookahead_shortcuts():
    timestamp_text = " ".join(
        build_timestamp_availability_policy(
            {"conservative_processing_delay_minutes": 5}
        )["requirement"].astype(str)
    ).lower()
    revision_text = " ".join(
        build_revision_deduplication_policy()["requirement"].astype(str)
    ).lower()
    entity_text = " ".join(build_entity_linking_policy()["requirement"].astype(str)).lower()
    assert "first_seen" in timestamp_text
    assert "retraction" in revision_text
    assert "point-in-time" in entity_text
    assert "future" in entity_text


def test_coverage_policy_is_fail_closed_and_social_is_optional():
    policy = build_coverage_policy(
        {
            "required_start_date": "2006-04-28",
            "required_end_date": "2026-05-01",
            "gdelt2_start_date": "2015-02-19",
            "audit_as_of_date": "2026-06-13",
        }
    )
    assert not bool(policy["canonical_ready_now"].any())
    social = policy.loc[policy["coverage_segment"].eq("social_sentiment_history")].iloc[0]
    assert "optional" in social["training_policy"]
    news = policy.loc[policy["coverage_segment"].eq("canonical_company_news_backfile")].iloc[0]
    assert news["start_date"] == "2006-04-28"


def test_news_event_validator_accepts_valid_event():
    report = validate_news_event_frame(_valid_events())
    assert report["passed"].all()
    assert bool(report["all_gates_passed"].iloc[0])


def test_news_event_validator_rejects_knowledge_before_first_seen_delay():
    events = _valid_events()
    events.loc[0, "knowledge_timestamp_utc"] = "2025-08-01T16:31:00Z"
    report = validate_news_event_frame(events)
    delay = report.loc[report["gate"].eq("knowledge_respects_processing_delay")].iloc[0]
    assert not bool(delay["passed"])
    assert not bool(report["all_gates_passed"].iloc[0])


def test_news_event_validator_rejects_canonical_event_without_approved_license():
    events = _valid_events()
    events.loc[0, "license_class"] = "experimental"
    report = validate_news_event_frame(events)
    row = report.loc[
        report["gate"].eq("canonical_rows_have_provenance_and_identity")
    ].iloc[0]
    assert not bool(row["passed"])


def test_sentiment_validator_accepts_bounded_point_in_time_score():
    report = validate_sentiment_observation_frame(
        _valid_sentiment(), source_events=_valid_events()
    )
    assert report["passed"].all()


def test_sentiment_validator_rejects_out_of_bounds_and_pre_source_feature():
    sentiment = _valid_sentiment()
    sentiment.loc[0, "sentiment_score"] = 1.5
    sentiment.loc[0, "feature_available_timestamp_utc"] = "2025-08-01T16:34:00Z"
    report = validate_sentiment_observation_frame(
        sentiment, source_events=_valid_events()
    )
    assert not bool(report.loc[report["gate"].eq("scores_bounded"), "passed"].iloc[0])
    assert not bool(
        report.loc[
            report["gate"].eq("feature_not_before_source_knowledge"), "passed"
        ].iloc[0]
    )


def test_phase23d_writes_reports_without_reports_reports_and_blocks_training(tmp_path):
    config = {
        "phase23d_sentiment_news_source_audit": {
            "enabled": True,
            "output_dir": (
                "reports/individual_equity_decision_system/"
                "phase23d_sentiment_news_source_audit"
            ),
            "dashboard_status_path": (
                "reports/paper_trading/dashboard/"
                "phase23d_sentiment_news_source_audit_status.csv"
            ),
        }
    }
    outputs = save_phase23d_sentiment_news_source_audit(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    summary = outputs["summary"].iloc[0]
    assert bool(summary["phase_execution_gates_passed"])
    assert bool(summary["sentiment_news_source_contract_ready"])
    assert not bool(summary["sentiment_news_data_ready"])
    assert bool(summary["licensed_company_news_backfile_required"])
    assert bool(summary["social_sentiment_optional_ablation_only"])
    assert not bool(summary["model_training_allowed"])
    assert not bool(summary["backtest_allowed"])
    assert not bool(summary["promotion_allowed"])
    assert not bool(summary["live_trading_allowed"])
    assert not bool(summary["real_money_allowed"])
    assert not bool(summary["broker_api_integration_allowed"])

    output_dir = (
        tmp_path
        / "reports"
        / "individual_equity_decision_system"
        / "phase23d_sentiment_news_source_audit"
    )
    required = [
        "phase23d_summary.csv",
        "phase23d_source_registry.csv",
        "phase23d_source_scorecard.csv",
        "phase23d_news_event_schema.csv",
        "phase23d_sentiment_observation_schema.csv",
        "phase23d_timestamp_availability_policy.csv",
        "phase23d_revision_deduplication_policy.csv",
        "phase23d_entity_linking_policy.csv",
        "phase23d_coverage_policy.csv",
        "phase23d_feature_registry.csv",
        "phase23d_validation_plan.csv",
        "phase23d_acquisition_plan.csv",
        "phase23d_gate_report.csv",
        "phase23d_news_event_import_template.csv",
        "phase23d_sentiment_observation_import_template.csv",
        "phase23d_sentiment_news_source_audit.md",
    ]
    for filename in required:
        assert (output_dir / filename).exists()
    assert not (tmp_path / "reports" / "reports").exists()
    assert (
        tmp_path
        / "reports"
        / "paper_trading"
        / "dashboard"
        / "phase23d_sentiment_news_source_audit_status.csv"
    ).exists()


def test_phase23d_respects_absolute_test_output_paths(tmp_path):
    outputs = save_phase23d_sentiment_news_source_audit(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )
    assert not outputs["summary"].empty
    assert (tmp_path / "reports" / "phase23d" / "phase23d_summary.csv").exists()


def test_run_backtest_exposes_phase23d_only_cli():
    source = Path("src/market_strats/run_backtest.py").read_text(encoding="utf-8")
    assert "--phase23d-only" in source
    assert "_run_phase23d_sentiment_news_source_audit(" in source
    assert "save_phase23d_sentiment_news_source_audit" in source
