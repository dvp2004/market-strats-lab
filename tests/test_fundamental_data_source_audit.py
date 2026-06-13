from pathlib import Path

import pandas as pd

from market_strats.analysis.fundamental_data_source_audit import (
    build_filing_availability_policy,
    build_fundamental_fact_schema,
    build_pre_xbrl_coverage_policy,
    build_restatement_policy,
    build_source_registry,
    build_source_scorecard,
    save_phase23c_fundamental_data_source_audit,
    validate_fundamental_fact_frame,
)


def _config(tmp_path: Path) -> dict:
    return {
        "phase23c_fundamental_data_source_audit": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "phase23c"),
            "dashboard_status_path": str(
                tmp_path
                / "reports"
                / "paper_trading"
                / "dashboard"
                / "phase23c_status.csv"
            ),
        }
    }


def _valid_facts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cik": "0000320193",
                "accession_number": "0000320193-25-000079",
                "form": "10-Q",
                "filing_date": "2025-08-01",
                "accepted_timestamp_utc": "2025-08-01T16:30:00Z",
                "knowledge_timestamp_utc": "2025-08-01T16:35:00Z",
                "report_period_end": "2025-06-28",
                "start_date": "2025-03-30",
                "end_date": "2025-06-28",
                "taxonomy": "us-gaap",
                "concept": "Revenues",
                "canonical_concept": "revenue",
                "unit": "USD",
                "value": 94_000_000_000.0,
                "context_id": "D2025Q3",
                "dimensions_json": "{}",
                "source_provider": "SEC EDGAR",
                "source_reference": "https://www.sec.gov/Archives/example",
                "source_retrieved_at_utc": "2026-06-13T00:00:00Z",
                "source_revision": "sha256:example",
                "is_amendment": False,
                "license_class": "public_official",
                "is_canonical": True,
            }
        ]
    )


def test_source_registry_contains_three_official_sec_contract_sources():
    registry = build_source_registry()
    official = registry.loc[
        registry["source_class"].str.contains("canonical_candidate", na=False)
    ]
    assert {
        "SEC_SUBMISSIONS_API",
        "SEC_XBRL_COMPANYFACTS",
        "SEC_INLINE_XBRL_FILING_ARCHIVE",
    }.issubset(set(official["source_id"]))
    assert official["official_provider"].all()
    assert official["public_free_source"].all()


def test_current_snapshot_source_is_never_canonical_ready():
    scorecard = build_source_scorecard(build_source_registry())
    current = scorecard.loc[
        scorecard["source_id"].eq("CURRENT_WEBSITE_FUNDAMENTALS")
    ].iloc[0]
    assert not bool(current["source_contract_ready"])
    assert not bool(current["canonical_data_ready_now"])
    assert not bool(scorecard["canonical_data_ready_now"].any())


def test_fact_schema_requires_accession_and_knowledge_timestamp():
    schema = build_fundamental_fact_schema()
    columns = set(schema["column"])
    assert {
        "accession_number",
        "accepted_timestamp_utc",
        "knowledge_timestamp_utc",
        "taxonomy",
        "concept",
        "unit",
        "source_revision",
        "is_amendment",
    }.issubset(columns)


def test_availability_and_restatement_policies_block_lookahead_shortcuts():
    availability = build_filing_availability_policy(
        {"conservative_processing_delay_minutes": 5}
    )
    restatement = build_restatement_policy()
    availability_text = " ".join(availability["requirement"].astype(str)).lower()
    restatement_text = " ".join(restatement["requirement"].astype(str)).lower()
    assert "period end" in availability_text
    assert "accepted" in availability_text
    assert "historical training" in restatement_text
    assert "amendment" in restatement_text



def test_pre_xbrl_coverage_gap_is_explicit_and_fail_closed():
    policy = build_pre_xbrl_coverage_policy(
        {
            "required_start_date": "2006-04-28",
            "standardized_xbrl_start_date": "2009-01-01",
            "required_end_date": "2026-05-01",
        }
    )
    assert {"pre_standardized_xbrl", "standardized_xbrl_era"}.issubset(
        set(policy["coverage_segment"])
    )
    assert not bool(policy["canonical_ready_now"].any())
    pre = policy.loc[
        policy["coverage_segment"].eq("pre_standardized_xbrl")
    ].iloc[0]
    assert pre["start_date"] == "2006-04-28"
    assert "exclude" in pre["training_policy"]

def test_fundamental_fact_validator_accepts_valid_point_in_time_fact():
    report = validate_fundamental_fact_frame(_valid_facts())
    assert report["passed"].all()
    assert bool(report["all_gates_passed"].iloc[0])


def test_fundamental_fact_validator_rejects_knowledge_before_acceptance():
    facts = _valid_facts()
    facts.loc[0, "knowledge_timestamp_utc"] = "2025-08-01T16:20:00Z"
    report = validate_fundamental_fact_frame(facts)
    row = report.loc[
        report["gate"].eq("knowledge_not_before_accepted_timestamp")
    ].iloc[0]
    assert not bool(row["passed"])
    assert not bool(report["all_gates_passed"].iloc[0])


def test_fundamental_fact_validator_rejects_amendment_flag_mismatch():
    facts = _valid_facts()
    facts.loc[0, "form"] = "10-Q/A"
    facts.loc[0, "is_amendment"] = False
    report = validate_fundamental_fact_frame(facts)
    row = report.loc[report["gate"].eq("amendment_flag_matches_form")].iloc[0]
    assert not bool(row["passed"])


def test_phase23c_writes_reports_without_reports_reports_and_blocks_training(tmp_path):
    config = {
        "phase23c_fundamental_data_source_audit": {
            "enabled": True,
            "output_dir": (
                "reports/individual_equity_decision_system/"
                "phase23c_fundamental_data_source_audit"
            ),
            "dashboard_status_path": (
                "reports/paper_trading/dashboard/"
                "phase23c_fundamental_data_source_audit_status.csv"
            ),
        }
    }
    outputs = save_phase23c_fundamental_data_source_audit(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    summary = outputs["summary"].iloc[0]
    assert bool(summary["phase_execution_gates_passed"])
    assert bool(summary["fundamental_source_contract_ready"])
    assert not bool(summary["fundamental_data_ready"])
    assert bool(summary["pre_xbrl_gap_requires_parser_or_vendor"])
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
        / "phase23c_fundamental_data_source_audit"
    )
    required_files = [
        "phase23c_summary.csv",
        "phase23c_source_registry.csv",
        "phase23c_source_scorecard.csv",
        "phase23c_filing_event_schema.csv",
        "phase23c_fundamental_fact_schema.csv",
        "phase23c_filing_availability_policy.csv",
        "phase23c_restatement_policy.csv",
        "phase23c_pre_xbrl_coverage_policy.csv",
        "phase23c_feature_concept_registry.csv",
        "phase23c_context_selection_rules.csv",
        "phase23c_validation_plan.csv",
        "phase23c_acquisition_plan.csv",
        "phase23c_gate_report.csv",
        "phase23c_filing_event_import_template.csv",
        "phase23c_fundamental_fact_import_template.csv",
        "phase23c_fundamental_data_source_audit.md",
    ]
    for filename in required_files:
        assert (output_dir / filename).exists()
    assert not (tmp_path / "reports" / "reports").exists()

    dashboard = (
        tmp_path
        / "reports"
        / "paper_trading"
        / "dashboard"
        / "phase23c_fundamental_data_source_audit_status.csv"
    )
    assert dashboard.exists()


def test_phase23c_respects_absolute_test_output_paths(tmp_path):
    outputs = save_phase23c_fundamental_data_source_audit(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )
    assert not outputs["summary"].empty
    assert (tmp_path / "reports" / "phase23c" / "phase23c_summary.csv").exists()


def test_run_backtest_exposes_phase23c_only_cli():
    source = Path("src/market_strats/run_backtest.py").read_text(encoding="utf-8")
    assert "--phase23c-only" in source
    assert "_run_phase23c_fundamental_data_source_audit(" in source
    assert "save_phase23c_fundamental_data_source_audit" in source
