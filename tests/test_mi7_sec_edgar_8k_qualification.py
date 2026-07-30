from __future__ import annotations

import json
import urllib.error
import warnings
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from market_strats.intelligence.mi7.sec_edgar_8k_qualification import (
    ACCEPTANCE_TIMEZONE,
    EVENT_COLUMNS,
    EXCLUSION_ACCOUNTING_FIELDS,
    MANIFEST_COLUMNS,
    SEC_SUBMISSIONS_BASE_URL,
    USER_AGENT_ENV_VAR,
    AcceptanceTimestampConflictError,
    AcceptanceTimestampNormalizationError,
    CrawlResult,
    Mi7ConfigurationError,
    SecHttpRequestError,
    build_acceptance_events,
    build_report,
    canonical_issuer_url,
    crawl_sec_submissions,
    normalize_acceptance_timestamps_ny,
    parse_acceptance_timestamp,
    qualification_summary,
    resolve_supplemental_url,
    run_mi7_sec_edgar_8k_acceptance_qualification,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_SOURCE_ID = "sec_edgar_8k_acceptance_qualification"
TEST_USER_AGENT = "ResearchClient UnitTest"


class FakeFetcher:
    def __init__(self, payloads: dict[str, dict]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []
        self.user_agents: list[str] = []

    def fetch(self, url: str, user_agent: str) -> bytes:
        self.calls.append(url)
        self.user_agents.append(user_agent)
        return json.dumps(self.payloads[url]).encode("utf-8")


class FakeHttpErrorFetcher:
    def __init__(self, payloads: dict[str, dict], failures: dict[str, int]) -> None:
        self.payloads = payloads
        self.failures = failures
        self.calls: list[str] = []
        self.user_agents: list[str] = []

    def fetch(self, url: str, user_agent: str) -> bytes:
        self.calls.append(url)
        self.user_agents.append(user_agent)
        if url in self.failures:
            raise urllib.error.HTTPError(url, self.failures[url], "blocked", None, None)
        return json.dumps(self.payloads[url]).encode("utf-8")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _tmp(name: str) -> Path:
    path = ROOT / ".pytest_tmp" / f"mi7_{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _config(path: Path, issuer_count: int = 2, minimum_total: int = 2) -> Path:
    issuers = [
        ("apple", "0000320193"),
        ("microsoft", "0000789019"),
        ("jpmorgan_chase", "0000019617"),
        ("exxon_mobil", "0000034088"),
        ("johnson_and_johnson", "0000200406"),
        ("walmart", "0000104169"),
        ("procter_and_gamble", "0000080424"),
        ("caterpillar", "0000018230"),
    ][:issuer_count]
    issuer_yaml = "\n".join(
        f'  - issuer_id: {issuer_id}\n    cik: "{cik}"' for issuer_id, cik in issuers
    )
    path.write_text(
        f"""
source_id: {CONFIG_SOURCE_ID}
submission_base_url: {SEC_SUBMISSIONS_BASE_URL}
history_start_date: 2016-01-01
form_types:
  - 8-K
minimum_total_accepted_8k_events: {minimum_total}
minimum_qualifying_issuers: 1
minimum_events_per_qualifying_issuer: 1
minimum_calendar_years_of_coverage: 1
max_requests_per_second: 2
issuers:
{issuer_yaml}
""",
        encoding="utf-8",
    )
    return path


def _submissions(
    cik: str,
    *,
    accession: str = "0000320193-24-000001",
    form: str = "8-K",
    filing_date: str = "2024-01-02",
    acceptance: str | None = "20240102170102",
    files: list[dict] | None = None,
) -> dict:
    row = {
        "accessionNumber": [accession],
        "filingDate": [filing_date],
        "form": [form],
    }
    if acceptance is not None:
        row["acceptanceDateTime"] = [acceptance]
    return {
        "cik": int(cik),
        "filings": {
            "recent": row,
            "files": files or [],
        },
    }


def _supplemental(
    *,
    accession: str = "0000320193-24-000002",
    form: str = "8-K",
    filing_date: str = "2024-02-02",
    acceptance: str | None = "2024-02-02T22:01:02Z",
) -> dict:
    row = {
        "accessionNumber": [accession],
        "filingDate": [filing_date],
        "form": [form],
    }
    if acceptance is not None:
        row["acceptanceDateTime"] = [acceptance]
    return row


def _payloads() -> dict[str, dict]:
    apple_url = canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193")
    microsoft_url = canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000789019")
    return {
        apple_url: _submissions(
            "0000320193",
            files=[{"name": "CIK0000320193-submissions-001.json"}],
        ),
        SEC_SUBMISSIONS_BASE_URL + "CIK0000320193-submissions-001.json": _supplemental(
            accession="0000320193-24-000002",
            filing_date="2024-02-02",
            acceptance="2024-02-02T22:01:02Z",
        ),
        microsoft_url: _submissions(
            "0000789019",
            accession="0000789019-24-000001",
            filing_date="2024-01-03",
            acceptance="20240103170102",
        ),
    }


def test_missing_user_agent_fails_before_any_request() -> None:
    fetcher = FakeFetcher({})
    root = _tmp("missing_ua")
    with pytest.raises(Mi7ConfigurationError):
        run_mi7_sec_edgar_8k_acceptance_qualification(
            mi7_data_root=root / "data" / "private" / "mi7",
            report_root=root / "reports" / "mi7",
            config_path=_config(root / "sec_issuer_panel_mi7.yaml"),
            fetcher=fetcher,
            env={},
        )
    assert fetcher.calls == []


def test_user_agent_passes_unchanged_and_only_canonical_urls_are_fetched() -> None:
    root = _tmp("canonical")
    fetcher = FakeFetcher(_payloads())
    result = run_mi7_sec_edgar_8k_acceptance_qualification(
        mi7_data_root=root / "data" / "private" / "mi7",
        report_root=root / "reports" / "mi7",
        config_path=_config(root / "sec_issuer_panel_mi7.yaml"),
        fetcher=fetcher,
        env={USER_AGENT_ENV_VAR: TEST_USER_AGENT},
    )
    assert fetcher.user_agents == [TEST_USER_AGENT, TEST_USER_AGENT, TEST_USER_AGENT]
    assert fetcher.calls == [
        canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193"),
        SEC_SUBMISSIONS_BASE_URL + "CIK0000320193-submissions-001.json",
        canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000789019"),
    ]
    assert result.eligible_8k_event_count == 3
    report = json.loads(Path(result.output_paths["report_json"]).read_text(encoding="utf-8"))
    markdown = Path(result.output_paths["report_markdown"]).read_text(encoding="utf-8")
    assert report["eligible_8k_event_count"] == result.eligible_8k_event_count
    assert "eligible_accepted_8k_event_count" not in report
    assert "eligible_8k_event_count: 3" in markdown
    for field in EXCLUSION_ACCOUNTING_FIELDS:
        assert field in report["exclusion_counts"]


def test_supplemental_history_follows_only_explicit_safe_files() -> None:
    assert (
        resolve_supplemental_url(SEC_SUBMISSIONS_BASE_URL, "CIK0000320193-submissions-001.json")
        == SEC_SUBMISSIONS_BASE_URL + "CIK0000320193-submissions-001.json"
    )
    assert resolve_supplemental_url(SEC_SUBMISSIONS_BASE_URL, "/Archives/guess.json") is None
    assert resolve_supplemental_url(SEC_SUBMISSIONS_BASE_URL, "../Archives/guess.json") is None
    assert resolve_supplemental_url(SEC_SUBMISSIONS_BASE_URL, "https://example.com/x.json") is None


def test_request_pacing_enforces_two_requests_per_second() -> None:
    root = _tmp("pacing")
    clock = FakeClock()
    fetcher = FakeFetcher(_payloads())
    crawl_sec_submissions(
        config={
            "submission_base_url": SEC_SUBMISSIONS_BASE_URL,
            "max_requests_per_second": 2,
            "issuers": [
                {"issuer_id": "apple", "cik": "0000320193"},
                {"issuer_id": "microsoft", "cik": "0000789019"},
            ],
        },
        user_agent=TEST_USER_AGENT,
        fetcher=fetcher,
        raw_root=root / "data" / "private" / "mi7" / "raw",
        manifest_root=root / "data" / "private" / "mi7" / "manifests",
        time_fn=clock.time,
        sleep_fn=clock.sleep,
    )
    assert clock.sleeps == [0.5, 0.5]


def test_exact_8k_filtering_and_timestamp_parsing_excludes_bad_rows() -> None:
    payload = {
        canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193"): {
            "cik": 320193,
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "good",
                        "amended",
                        "missing_time",
                        "malformed",
                        "old",
                    ],
                    "filingDate": [
                        "2024-01-02",
                        "2024-01-03",
                        "2024-01-04",
                        "2024-01-05",
                        "2015-12-31",
                    ],
                    "form": ["8-K", "8-K/A", "8-K", "8-K", "8-K"],
                    "acceptanceDateTime": [
                        "20240102170102",
                        "20240103170102",
                        "",
                        "bad",
                        "20151231170102",
                    ],
                },
                "files": [],
            },
        }
    }
    root = _tmp("filtering")
    crawl = crawl_sec_submissions(
        config={
            "submission_base_url": SEC_SUBMISSIONS_BASE_URL,
            "max_requests_per_second": 2,
            "issuers": [{"issuer_id": "apple", "cik": "0000320193"}],
        },
        user_agent=TEST_USER_AGENT,
        fetcher=FakeFetcher(payload),
        raw_root=root / "data" / "private" / "mi7" / "raw",
        manifest_root=root / "data" / "private" / "mi7" / "manifests",
    )
    events, exclusions, _duplicates, _conflicts = build_acceptance_events(
        crawl,
        {
            "history_start_date": "2016-01-01",
        },
        root / "data" / "private" / "mi7" / "manifests",
    )
    assert len(events) == 1
    assert events.loc[0, "accession_number"] == "good"
    assert events.loc[0, "acceptance_timestamp"] == "2024-01-02T17:01:02-05:00"
    assert events.loc[0, "acceptance_timestamp_raw"] == "20240102170102"
    assert events.loc[0, "acceptance_timestamp_timezone"] == ACCEPTANCE_TIMEZONE
    assert exclusions["records_seen"] == 5
    assert exclusions["records_with_exact_8k_form"] == 4
    assert exclusions["records_after_history_start_date"] == 3
    assert exclusions["records_missing_acceptance_timestamp"] == 1
    assert exclusions["records_unrecognized_acceptance_timestamp_format"] == 1
    assert exclusions["records_retained_as_eligible_8k"] == 1
    assert parse_acceptance_timestamp("20240102170102").isoformat() == ("2024-01-02T17:01:02-05:00")


def test_iso_utc_offset_and_compact_acceptance_timestamps_parse_to_new_york() -> None:
    assert parse_acceptance_timestamp("2024-01-02T22:01:02Z").isoformat() == (
        "2024-01-02T17:01:02-05:00"
    )
    assert parse_acceptance_timestamp("2024-01-02T22:01:02.000Z").isoformat() == (
        "2024-01-02T17:01:02-05:00"
    )
    assert parse_acceptance_timestamp("2024-01-02T17:01:02-05:00").isoformat() == (
        "2024-01-02T17:01:02-05:00"
    )
    assert parse_acceptance_timestamp("2024-01-02T17:01:02.000-05:00").isoformat() == (
        "2024-01-02T17:01:02-05:00"
    )
    assert parse_acceptance_timestamp("20240102170102").isoformat() == ("2024-01-02T17:01:02-05:00")


def _mixed_offset_events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "issuer_id": "apple",
                "issuer_cik": "0000320193",
                "accession_number": "jan",
                "form_type": "8-K",
                "filing_date": "2024-01-02",
                "acceptance_timestamp_raw": "2024-01-02T22:01:02Z",
                "acceptance_timestamp": "2024-01-02T17:01:02-05:00",
                "acceptance_timestamp_timezone": ACCEPTANCE_TIMEZONE,
                "timestamp_evidence_source": "sec_edgar_acceptance_timestamp",
                "content_availability_evidence_level": "contractual_assumption",
                "availability_rule_id": "sec_edgar_acceptance_next_eligible_session_close_v1",
                "source_url": "https://data.sec.gov/submissions/CIK0000320193.json",
                "retrieved_at_utc": "2024-01-02T22:02:00+00:00",
                "snapshot_id": "one",
            },
            {
                "issuer_id": "apple",
                "issuer_cik": "0000320193",
                "accession_number": "jul",
                "form_type": "8-K",
                "filing_date": "2024-07-02",
                "acceptance_timestamp_raw": "2024-07-02T21:01:02Z",
                "acceptance_timestamp": "2024-07-02T17:01:02-04:00",
                "acceptance_timestamp_timezone": ACCEPTANCE_TIMEZONE,
                "timestamp_evidence_source": "sec_edgar_acceptance_timestamp",
                "content_availability_evidence_level": "contractual_assumption",
                "availability_rule_id": "sec_edgar_acceptance_next_eligible_session_close_v1",
                "source_url": "https://data.sec.gov/submissions/CIK0000320193.json",
                "retrieved_at_utc": "2024-07-02T21:02:00+00:00",
                "snapshot_id": "two",
            },
        ],
        columns=EVENT_COLUMNS,
    )


def test_mixed_offset_timestamps_normalize_to_timezone_aware_series() -> None:
    timestamps_ny = normalize_acceptance_timestamps_ny(_mixed_offset_events())
    assert str(timestamps_ny.dtype) == "datetime64[ns, America/New_York]"
    assert list(timestamps_ny.dt.year) == [2024, 2024]
    assert timestamps_ny.iloc[0].isoformat() == "2024-01-02T17:01:02-05:00"
    assert timestamps_ny.iloc[1].isoformat() == "2024-07-02T17:01:02-04:00"


def test_qualification_summary_handles_mixed_offsets_without_futurewarning() -> None:
    events = _mixed_offset_events()
    config = {
        "minimum_total_accepted_8k_events": 2,
        "minimum_qualifying_issuers": 1,
        "minimum_events_per_qualifying_issuer": 2,
        "minimum_calendar_years_of_coverage": 1,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        qualified, reasons = qualification_summary(events, config, "available", 0)
    assert qualified is True
    assert reasons == ["qualified"]
    assert not any("mixed time zones" in str(item.message) for item in caught)


def test_report_generation_orders_earliest_latest_after_utc_normalization() -> None:
    root = _tmp("mixed_offset_report")
    events = _mixed_offset_events().iloc[[1, 0]].reset_index(drop=True)
    _md_path, _json_path, report = build_report(
        config={
            "source_id": CONFIG_SOURCE_ID,
            "issuers": [{"issuer_id": "apple", "cik": "0000320193"}],
            "minimum_total_accepted_8k_events": 2,
            "minimum_qualifying_issuers": 1,
            "minimum_events_per_qualifying_issuer": 2,
            "minimum_calendar_years_of_coverage": 1,
        },
        crawl=CrawlResult(responses=[], fetched_issuer_ids={"apple"}),
        events=events,
        exclusions={field: 0 for field in EXCLUSION_ACCOUNTING_FIELDS},
        duplicate_count=0,
        conflict_count=0,
        report_root=root / "reports" / "mi7",
    )
    assert report["earliest_acceptance_timestamp"] == "2024-01-02T17:01:02-05:00"
    assert report["latest_acceptance_timestamp"] == "2024-07-02T17:01:02-04:00"
    assert report["qualified_for_later_next_session_event_research"] is True


def test_unparseable_retained_event_fails_with_typed_safe_exception() -> None:
    events = _mixed_offset_events()
    events.loc[0, "acceptance_timestamp"] = "not-a-timestamp"
    with pytest.raises(AcceptanceTimestampNormalizationError) as exc:
        normalize_acceptance_timestamps_ny(events)
    assert "apple:jan" in str(exc.value)


def test_timezone_less_iso_timestamp_is_counted_as_missing_timezone() -> None:
    payload = {
        canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193"): _submissions(
            "0000320193",
            acceptance="2024-01-02T17:01:02",
        )
    }
    root = _tmp("missing_tz")
    crawl = crawl_sec_submissions(
        config={
            "submission_base_url": SEC_SUBMISSIONS_BASE_URL,
            "max_requests_per_second": 2,
            "issuers": [{"issuer_id": "apple", "cik": "0000320193"}],
        },
        user_agent=TEST_USER_AGENT,
        fetcher=FakeFetcher(payload),
        raw_root=root / "data" / "private" / "mi7" / "raw",
        manifest_root=root / "data" / "private" / "mi7" / "manifests",
    )
    events, exclusions, _duplicates, _conflicts = build_acceptance_events(
        crawl,
        {"history_start_date": "2016-01-01"},
        root / "data" / "private" / "mi7" / "manifests",
    )
    assert events.empty
    assert exclusions["records_missing_timestamp_timezone"] == 1


def test_filing_date_consistency_after_timezone_conversion() -> None:
    payload = {
        canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193"): _submissions(
            "0000320193",
            filing_date="2024-01-02",
            acceptance="2024-01-03T01:01:02Z",
        )
    }
    root = _tmp("timezone_consistency")
    crawl = crawl_sec_submissions(
        config={
            "submission_base_url": SEC_SUBMISSIONS_BASE_URL,
            "max_requests_per_second": 2,
            "issuers": [{"issuer_id": "apple", "cik": "0000320193"}],
        },
        user_agent=TEST_USER_AGENT,
        fetcher=FakeFetcher(payload),
        raw_root=root / "data" / "private" / "mi7" / "raw",
        manifest_root=root / "data" / "private" / "mi7" / "manifests",
    )
    events, exclusions, _duplicates, _conflicts = build_acceptance_events(
        crawl,
        {"history_start_date": "2016-01-01"},
        root / "data" / "private" / "mi7" / "manifests",
    )
    assert len(events) == 1
    assert events.loc[0, "acceptance_timestamp"] == "2024-01-02T20:01:02-05:00"
    assert exclusions["records_filing_date_inconsistent"] == 0


def test_filing_date_inconsistent_after_timezone_conversion_is_counted() -> None:
    payload = {
        canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193"): _submissions(
            "0000320193",
            filing_date="2024-01-03",
            acceptance="2024-01-03T01:01:02Z",
        )
    }
    root = _tmp("timezone_inconsistent")
    crawl = crawl_sec_submissions(
        config={
            "submission_base_url": SEC_SUBMISSIONS_BASE_URL,
            "max_requests_per_second": 2,
            "issuers": [{"issuer_id": "apple", "cik": "0000320193"}],
        },
        user_agent=TEST_USER_AGENT,
        fetcher=FakeFetcher(payload),
        raw_root=root / "data" / "private" / "mi7" / "raw",
        manifest_root=root / "data" / "private" / "mi7" / "manifests",
    )
    events, exclusions, _duplicates, _conflicts = build_acceptance_events(
        crawl,
        {"history_start_date": "2016-01-01"},
        root / "data" / "private" / "mi7" / "manifests",
    )
    assert events.empty
    assert exclusions["records_filing_date_inconsistent"] == 1


def test_duplicate_event_deduplicates_exact_issuer_accession_pair() -> None:
    root = _tmp("dedupe")
    payload = _payloads()
    payload[canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193")]["filings"]["recent"][
        "accessionNumber"
    ].append("0000320193-24-000001")
    payload[canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193")]["filings"]["recent"][
        "filingDate"
    ].append("2024-01-02")
    payload[canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193")]["filings"]["recent"][
        "form"
    ].append("8-K")
    payload[canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193")]["filings"]["recent"][
        "acceptanceDateTime"
    ].append("20240102170102")
    result = run_mi7_sec_edgar_8k_acceptance_qualification(
        mi7_data_root=root / "data" / "private" / "mi7",
        report_root=root / "reports" / "mi7",
        config_path=_config(root / "sec_issuer_panel_mi7.yaml"),
        fetcher=FakeFetcher(payload),
        env={USER_AGENT_ENV_VAR: TEST_USER_AGENT},
    )
    events = pd.read_parquet(result.output_paths["sec_edgar_8k_acceptance_event"])
    assert len(events) == 3


def test_conflicting_acceptance_timestamp_fails_clearly() -> None:
    root = _tmp("conflict")
    payload = {
        canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193"): {
            "cik": 320193,
            "filings": {
                "recent": {
                    "accessionNumber": ["same", "same"],
                    "filingDate": ["2024-01-02", "2024-01-02"],
                    "form": ["8-K", "8-K"],
                    "acceptanceDateTime": ["20240102170102", "20240102180102"],
                },
                "files": [],
            },
        }
    }
    with pytest.raises(AcceptanceTimestampConflictError):
        run_mi7_sec_edgar_8k_acceptance_qualification(
            mi7_data_root=root / "data" / "private" / "mi7",
            report_root=root / "reports" / "mi7",
            config_path=_config(root / "sec_issuer_panel_mi7.yaml", issuer_count=1),
            fetcher=FakeFetcher(payload),
            env={USER_AGENT_ENV_VAR: TEST_USER_AGENT},
        )


def test_controlled_http_403_and_429_write_empty_outputs_and_not_qualified_reports() -> None:
    for status_code, expected_status in [
        (403, "blocked_http_403"),
        (429, "rate_limited_http_429"),
    ]:
        root = _tmp(f"http_{status_code}")
        url = canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193")
        result = run_mi7_sec_edgar_8k_acceptance_qualification(
            mi7_data_root=root / "data" / "private" / "mi7",
            report_root=root / "reports" / "mi7",
            config_path=_config(root / "sec_issuer_panel_mi7.yaml", issuer_count=1),
            fetcher=FakeHttpErrorFetcher({}, {url: status_code}),
            env={USER_AGENT_ENV_VAR: TEST_USER_AGENT},
        )
        assert result.source_access_status == expected_status
        assert result.qualified_for_later_next_session_event_research is False
        manifest = pd.read_parquet(result.output_paths["sec_edgar_raw_snapshot_manifest"])
        events = pd.read_parquet(result.output_paths["sec_edgar_8k_acceptance_event"])
        assert list(manifest.columns) == MANIFEST_COLUMNS
        assert list(events.columns) == EVENT_COLUMNS
        assert manifest.empty
        assert events.empty
        assert Path(result.output_paths["report_json"]).exists()
        assert Path(result.output_paths["report_markdown"]).exists()
        report = json.loads(Path(result.output_paths["report_json"]).read_text(encoding="utf-8"))
        assert isinstance(report["eligible_8k_event_count"], int)
        assert report["eligible_8k_event_count"] == 0
        assert "eligible_accepted_8k_event_count" not in report
        for field in EXCLUSION_ACCOUNTING_FIELDS:
            assert field in report["exclusion_counts"]


def test_non_controlled_http_failure_raises_typed_safe_exception() -> None:
    root = _tmp("http_500")
    url = canonical_issuer_url(SEC_SUBMISSIONS_BASE_URL, "0000320193")
    with pytest.raises(SecHttpRequestError) as exc:
        run_mi7_sec_edgar_8k_acceptance_qualification(
            mi7_data_root=root / "data" / "private" / "mi7",
            report_root=root / "reports" / "mi7",
            config_path=_config(root / "sec_issuer_panel_mi7.yaml", issuer_count=1),
            fetcher=FakeHttpErrorFetcher({}, {url: 500}),
            env={USER_AGENT_ENV_VAR: TEST_USER_AGENT},
        )
    message = str(exc.value)
    assert "http_status_code=500" in message
    assert "endpoint_path=/submissions/CIK0000320193.json" in message
    assert "https://" not in message


def test_qualification_at_and_below_thresholds() -> None:
    rows = []
    for issuer_index in range(6):
        for event_index in range(12):
            rows.append(
                {
                    "issuer_id": f"issuer_{issuer_index}",
                    "acceptance_timestamp": (f"{2016 + (event_index % 6)}-01-02T17:01:02-05:00"),
                    "timestamp_evidence_source": "sec_edgar_acceptance_timestamp",
                }
            )
    config = {
        "minimum_total_accepted_8k_events": 72,
        "minimum_qualifying_issuers": 6,
        "minimum_events_per_qualifying_issuer": 12,
        "minimum_calendar_years_of_coverage": 6,
    }
    qualified, reasons = qualification_summary(
        pd.DataFrame(rows),
        config,
        "available",
        0,
    )
    assert qualified is True
    assert reasons == ["qualified"]
    qualified, reasons = qualification_summary(pd.DataFrame(rows[:-1]), config, "available", 0)
    assert qualified is False
    assert "eligible_8k_event_count_below_minimum:71<72" in reasons


def test_generated_mi7_outputs_are_ignored_by_git() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/data/private/mi7/*" in gitignore
    assert "!/data/private/mi7/.gitkeep" in gitignore
    assert "/reports/mi7/*" in gitignore
    assert "!/reports/mi7/.gitkeep" in gitignore


def test_no_return_model_text_llm_portfolio_candidate_broker_or_gma_dependency() -> None:
    source_text = (
        (ROOT / "src" / "market_strats" / "intelligence" / "mi7" / "sec_edgar_8k_qualification.py")
        .read_text(encoding="utf-8")
        .lower()
    )
    prohibited = [
        "randomforest",
        "ridge",
        "walk_forward",
        "asset_return",
        "sentiment",
        "target_weight",
        "submit_order",
        "broker",
        "llm",
        "gma",
    ]
    for token in prohibited:
        assert token not in source_text
