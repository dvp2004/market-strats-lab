from __future__ import annotations

import json
import urllib.error
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from market_strats.intelligence.mi6.bls_release_qualification import (
    AVAILABILITY_EVIDENCE_LEVEL,
    CALENDAR_URL,
    CPI_TOC_URL,
    EMPSIT_TOC_URL,
    EVENT_COLUMNS,
    MANIFEST_COLUMNS,
    USER_AGENT,
    BlsHttpRequestError,
    build_release_events,
    crawl_bls_sources,
    parse_et_timestamps,
    parse_release_event,
    qualify_source,
    run_mi6_bls_release_qualification,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeFetcher:
    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def fetch(self, url: str, user_agent: str) -> bytes:
        self.calls.append(url)
        assert user_agent == USER_AGENT
        return self.payloads[url].encode("utf-8")


class FakeHttpErrorFetcher:
    def __init__(self, payloads: dict[str, str], failures: dict[str, int]) -> None:
        self.payloads = payloads
        self.failures = failures
        self.calls: list[str] = []
        self.user_agents: list[str] = []

    def fetch(self, url: str, user_agent: str) -> bytes:
        self.calls.append(url)
        self.user_agents.append(user_agent)
        if url in self.failures:
            raise urllib.error.HTTPError(url, self.failures[url], "blocked", None, None)
        return self.payloads[url].encode("utf-8")


def _tmp(name: str) -> Path:
    path = ROOT / ".pytest_tmp" / f"mi6_{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _config(path: Path, minimum: int = 2, maximum_depth: int = 3) -> Path:
    path.write_text(
        f"""
source_id: bls_cpi_employment_release_qualification
calendar_url: {CALENDAR_URL}
release_types:
  - cpi
  - employment_situation
minimum_historical_event_count: {minimum}
maximum_crawl_depth: {maximum_depth}
""",
        encoding="utf-8",
    )
    return path


def _calendar() -> str:
    return """
    <main>
      <table>
        <tr>
          <td>Consumer Price Index</td>
          <td>January 15, 2025 8:30 a.m. (ET)</td>
          <td><a href="/news.release/cpi.nr0.htm">HTML</a></td>
        </tr>
        <tr>
          <td>Employment Situation</td>
          <td>February 7, 2025 8:30 a.m. (ET)</td>
          <td><a href="/news.release/empsit.nr0.htm">HTML</a></td>
        </tr>
      </table>
      <a href="https://example.com/outside.htm">external</a>
    </main>
    """


def _toc(*links: str) -> str:
    return "<main>" + "\n".join(links) + "</main>"


def _release(
    title: str,
    timestamp: str = "January 15, 2025 8:30 a.m. (ET)",
    *,
    include_time: bool = True,
) -> str:
    date_line = f"<p>{timestamp}</p>" if include_time else "<p>January 15, 2025</p>"
    return f"""
    <html>
      <body>
        <main>
          <h1>{title}</h1>
          {date_line}
          <p>Official release text.</p>
        </main>
      </body>
    </html>
    """


def _payloads() -> dict[str, str]:
    return {
        CALENDAR_URL: _calendar(),
        CPI_TOC_URL: _toc('<a href="/news.release/cpi.nr0.htm">Current CPI</a>'),
        EMPSIT_TOC_URL: _toc(
            '<a href="/news.release/empsit.nr0.htm">Current Employment Situation</a>'
        ),
        "https://www.bls.gov/news.release/cpi.nr0.htm": _release("Consumer Price Index"),
        "https://www.bls.gov/news.release/empsit.nr0.htm": _release(
            "Employment Situation",
            "February 7, 2025 8:30 a.m. (ET)",
        ),
    }


def test_root_page_http_403_returns_valid_not_qualified_result() -> None:
    root = _tmp("root_403")
    fetcher = FakeHttpErrorFetcher({}, {CALENDAR_URL: 403})
    result = run_mi6_bls_release_qualification(
        mi6_data_root=root / "data" / "private" / "mi6",
        report_root=root / "reports" / "mi6",
        config_path=_config(root / "event_source_mi6.yaml"),
        fetcher=fetcher,
    )
    assert fetcher.calls == [CALENDAR_URL]
    assert fetcher.user_agents == [USER_AGENT]
    assert result.source_access_status == "blocked_http_403"
    assert result.qualified_for_later_forecast_research is False
    assert result.usable_timestamped_event_count == 0
    assert result.release_type_counts == {"cpi": 0, "employment_situation": 0}
    assert result.qualification_reasons == [
        "official_source_access_blocked_http_403",
        "no_timestamped_release_corpus_was_retrieved",
        "no_attempt_was_made_to_bypass_or_disguise_the_declared_research_client",
    ]
    assert result.source_access_diagnostics == {
        "http_status_code": 403,
        "endpoint_path": "/schedule/news_release/",
        "request_stage": "approved_root_fetch",
        "source_access_status": "blocked_http_403",
    }
    manifest = pd.read_parquet(result.output_paths["bls_raw_snapshot_manifest"])
    events = pd.read_parquet(result.output_paths["bls_release_event"])
    assert list(manifest.columns) == MANIFEST_COLUMNS
    assert list(events.columns) == EVENT_COLUMNS
    assert manifest.empty
    assert events.empty
    report = json.loads(Path(result.output_paths["report_json"]).read_text(encoding="utf-8"))
    assert report["source_id"] == "bls_cpi_employment_release_qualification"
    assert report["source_id"] == report["source_provenance"]["source_id"]
    assert report["source_access_status"] == "blocked_http_403"
    assert list(report)[:3] == [
        "source_id",
        "source_provenance",
        "source_access_status",
    ]
    assert set(report["source_access_diagnostics"]) == {
        "http_status_code",
        "endpoint_path",
        "request_stage",
        "source_access_status",
    }
    assert report["source_access_diagnostics"]["endpoint_path"] == "/schedule/news_release/"
    assert "https://" not in json.dumps(report["source_access_diagnostics"])


def test_discovered_page_http_403_returns_controlled_not_qualified_result() -> None:
    root = _tmp("discovered_403")
    cpi_url = "https://www.bls.gov/news.release/cpi.nr0.htm"
    payloads = {
        CALENDAR_URL: """
        <main><table><tr><td>Consumer Price Index</td>
        <td>January 15, 2025 8:30 a.m. (ET)</td>
        <td><a href="/news.release/cpi.nr0.htm">HTML</a></td></tr></table></main>
        """,
        CPI_TOC_URL: "<main></main>",
        EMPSIT_TOC_URL: "<main></main>",
    }
    fetcher = FakeHttpErrorFetcher(payloads, {cpi_url: 403})
    result = run_mi6_bls_release_qualification(
        mi6_data_root=root / "data" / "private" / "mi6",
        report_root=root / "reports" / "mi6",
        config_path=_config(root / "event_source_mi6.yaml"),
        fetcher=fetcher,
    )
    assert fetcher.calls == [CALENDAR_URL, CPI_TOC_URL, EMPSIT_TOC_URL, cpi_url]
    assert fetcher.user_agents == [USER_AGENT, USER_AGENT, USER_AGENT, USER_AGENT]
    assert result.source_access_status == "blocked_http_403"
    assert result.qualified_for_later_forecast_research is False
    assert result.usable_timestamped_event_count == 0
    assert result.release_type_counts == {"cpi": 0, "employment_situation": 0}
    assert result.source_access_diagnostics == {
        "http_status_code": 403,
        "endpoint_path": "/news.release/cpi.nr0.htm",
        "request_stage": "discovered_same_origin_fetch",
        "source_access_status": "blocked_http_403",
    }
    events = pd.read_parquet(result.output_paths["bls_release_event"])
    assert list(events.columns) == EVENT_COLUMNS
    assert events.empty
    assert Path(result.output_paths["report_markdown"]).exists()
    assert Path(result.output_paths["report_json"]).exists()


def test_normal_non_blocked_json_has_configured_source_id_matching_markdown() -> None:
    root = _tmp("json_source_id")
    result = run_mi6_bls_release_qualification(
        mi6_data_root=root / "data" / "private" / "mi6",
        report_root=root / "reports" / "mi6",
        config_path=_config(root / "event_source_mi6.yaml"),
        fetcher=FakeFetcher(_payloads()),
    )
    report = json.loads(Path(result.output_paths["report_json"]).read_text(encoding="utf-8"))
    markdown = Path(result.output_paths["report_markdown"]).read_text(encoding="utf-8")
    assert report["source_id"] == "bls_cpi_employment_release_qualification"
    assert report["source_id"] == report["source_provenance"]["source_id"]
    assert f"Source: {report['source_id']}" in markdown
    assert list(report)[:3] == [
        "source_id",
        "source_provenance",
        "source_access_status",
    ]


def test_non_403_http_failure_raises_typed_safe_exception() -> None:
    root = _tmp("http_500")
    fetcher = FakeHttpErrorFetcher({}, {CALENDAR_URL: 500})
    with pytest.raises(BlsHttpRequestError) as exc:
        run_mi6_bls_release_qualification(
            mi6_data_root=root / "data" / "private" / "mi6",
            report_root=root / "reports" / "mi6",
            config_path=_config(root / "event_source_mi6.yaml"),
            fetcher=fetcher,
        )
    message = str(exc.value)
    assert "http_status_code=500" in message
    assert "endpoint_path=/schedule/news_release/" in message
    assert "request_stage=approved_root_fetch" in message
    assert "https://" not in message
    assert "blocked" not in message


def test_same_origin_only_crawling_and_no_guessed_urls() -> None:
    root = _tmp("crawl")
    fetcher = FakeFetcher(_payloads())
    crawl = crawl_bls_sources(
        config={
            "calendar_url": CALENDAR_URL,
            "maximum_crawl_depth": 3,
        },
        fetcher=fetcher,
        raw_root=root / "data" / "private" / "mi6" / "raw",
        manifest_root=root / "data" / "private" / "mi6" / "manifests",
    )
    assert "https://example.com/outside.htm" not in fetcher.calls
    assert set(fetcher.calls) == set(_payloads())
    assert crawl.skipped_external_url_count == 1
    assert crawl.duplicate_url_count > 0


def test_crawl_depth_limit_and_archive_navigation_depth_four_exception() -> None:
    root = _tmp("depth")
    archive1 = "https://www.bls.gov/schedule/news_release/2025_sched.htm"
    archive2 = "https://www.bls.gov/schedule/news_release/2024_sched.htm"
    archive3 = "https://www.bls.gov/schedule/news_release/2023_sched.htm"
    archive4 = "https://www.bls.gov/schedule/news_release/2022_sched.htm"
    too_deep = "https://www.bls.gov/schedule/news_release/2021_sched.htm"
    cpi = "https://www.bls.gov/news.release/cpi.deep.htm"
    payloads = {
        CALENDAR_URL: f'<a href="{archive1}">archive</a>',
        CPI_TOC_URL: "<main></main>",
        EMPSIT_TOC_URL: "<main></main>",
        archive1: f'<a href="{archive2}">archive</a>',
        archive2: f'<a href="{archive3}">archive</a>',
        archive3: f'<a href="{archive4}">archive</a>',
        archive4: f'<a href="{too_deep}">archive</a><a href="{cpi}">CPI</a>',
        cpi: _release("Consumer Price Index"),
    }
    fetcher = FakeFetcher(payloads)
    crawl = crawl_bls_sources(
        config={
            "calendar_url": CALENDAR_URL,
            "maximum_crawl_depth": 3,
        },
        fetcher=fetcher,
        raw_root=root / "data" / "private" / "mi6" / "raw",
        manifest_root=root / "data" / "private" / "mi6" / "manifests",
    )
    assert archive4 in fetcher.calls
    assert too_deep not in fetcher.calls
    assert cpi not in fetcher.calls
    assert crawl.max_depth_observed == 4


def test_cpi_and_employment_identification_and_timestamp_conversion() -> None:
    cpi = parse_release_event(
        response=type(
            "Response",
            (),
            {
                "source_url": "https://www.bls.gov/news.release/cpi.nr0.htm",
                "content": _release("Consumer Price Index").encode(),
                "retrieved_at_utc": datetime(2025, 1, 15, tzinfo=UTC),
            },
        )(),
        scheduled_evidence_by_url={},
    )
    empsit = parse_release_event(
        response=type(
            "Response",
            (),
            {
                "source_url": "https://www.bls.gov/news.release/empsit.nr0.htm",
                "content": _release(
                    "Employment Situation", "February 7, 2025 8:30 a.m. (ET)"
                ).encode(),
                "retrieved_at_utc": datetime(2025, 2, 7, tzinfo=UTC),
            },
        )(),
        scheduled_evidence_by_url={},
    )
    assert cpi is not None and cpi["release_type"] == "cpi"
    assert empsit is not None and empsit["release_type"] == "employment_situation"
    assert cpi["document_embargo_timestamp_et"] == "2025-01-15T08:30:00-05:00"
    assert cpi["availability_evidence_level"] == AVAILABILITY_EVIDENCE_LEVEL
    parsed = parse_et_timestamps("January 15, 2025 8:30 a.m. (ET)", CALENDAR_URL, "schedule")
    assert parsed[0].timestamp_et.tzinfo.key == "America/New_York"


def test_release_without_explicit_time_is_rejected() -> None:
    row = parse_release_event(
        response=type(
            "Response",
            (),
            {
                "source_url": "https://www.bls.gov/news.release/cpi.nr0.htm",
                "content": _release("Consumer Price Index", include_time=False).encode(),
                "retrieved_at_utc": datetime(2025, 1, 15, tzinfo=UTC),
            },
        )(),
        scheduled_evidence_by_url={},
    )
    assert row is not None
    assert row["usable"] is False
    assert row["availability_evidence_level"] == "unverified"
    assert row["exclusion_reason"] == "missing_document_embargo_timestamp"


def test_scheduled_and_document_timestamp_conflict_fails_event() -> None:
    scheduled = parse_et_timestamps(
        "January 15, 2025 8:30 a.m. (ET)",
        CALENDAR_URL,
        "schedule",
    )
    row = parse_release_event(
        response=type(
            "Response",
            (),
            {
                "source_url": "https://www.bls.gov/news.release/cpi.nr0.htm",
                "content": _release(
                    "Consumer Price Index", "January 15, 2025 9:30 a.m. (ET)"
                ).encode(),
                "retrieved_at_utc": datetime(2025, 1, 15, tzinfo=UTC),
            },
        )(),
        scheduled_evidence_by_url={"https://www.bls.gov/news.release/cpi.nr0.htm": scheduled},
    )
    assert row is not None
    assert row["timestamp_conflict"] is True
    assert row["usable"] is False
    assert "scheduled_document_timestamp_conflict" in row["exclusion_reason"]


def test_run_writes_outputs_and_uses_provider_verified_only_for_usable_events() -> None:
    root = _tmp("run")
    result = run_mi6_bls_release_qualification(
        mi6_data_root=root / "data" / "private" / "mi6",
        report_root=root / "reports" / "mi6",
        config_path=_config(root / "event_source_mi6.yaml"),
        fetcher=FakeFetcher(_payloads()),
    )
    assert result.usable_timestamped_event_count == 2
    assert result.release_type_counts == {"cpi": 1, "employment_situation": 1}
    for path in result.output_paths.values():
        assert Path(path).exists()
    events = pd.read_parquet(result.output_paths["bls_release_event"])
    usable = events[events["usable"]]
    assert set(usable["availability_evidence_level"]) == {AVAILABILITY_EVIDENCE_LEVEL}
    assert "document_embargo_timestamp_text" in events.columns
    assert "scheduled_timestamp_et" in events.columns


def test_qualification_at_and_below_80_event_threshold() -> None:
    rows = []
    for index in range(80):
        release_type = "cpi" if index < 40 else "employment_situation"
        rows.append(
            {
                "release_type": release_type,
                "usable": True,
                "availability_evidence_level": AVAILABILITY_EVIDENCE_LEVEL,
                "timestamp_conflict": False,
            }
        )
    config = {
        "minimum_historical_event_count": 80,
        "release_types": ["cpi", "employment_situation"],
    }
    qualified, reasons = qualify_source(pd.DataFrame(rows), config)
    assert qualified is True
    assert reasons == ["qualified"]
    below = pd.DataFrame(rows[:-1])
    qualified, reasons = qualify_source(below, config)
    assert qualified is False
    assert "usable_timestamped_event_count_below_minimum:79<80" in reasons


def test_generated_mi6_outputs_are_ignored_by_git() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/data/private/mi6/*" in gitignore
    assert "!/data/private/mi6/.gitkeep" in gitignore
    assert "/reports/mi6/*" in gitignore
    assert "!/reports/mi6/.gitkeep" in gitignore


def test_no_model_return_study_llm_portfolio_candidate_broker_or_credentials() -> None:
    source_text = (
        (ROOT / "src" / "market_strats" / "intelligence" / "mi6" / "bls_release_qualification.py")
        .read_text(encoding="utf-8")
        .lower()
    )
    prohibited = [
        "randomforest",
        "ridge",
        "walk_forward",
        "asset_return",
        "candidate_packet",
        "target_weight",
        "submit_order",
        "broker",
        "llm",
        "fred_api_key",
        ".env",
        "gma",
    ]
    for token in prohibited:
        assert token not in source_text


def test_build_release_events_deduplicates_exact_canonical_urls() -> None:
    root = _tmp("dedupe")
    fetcher = FakeFetcher(_payloads())
    crawl = crawl_bls_sources(
        config={
            "calendar_url": CALENDAR_URL,
            "maximum_crawl_depth": 3,
        },
        fetcher=fetcher,
        raw_root=root / "data" / "private" / "mi6" / "raw",
        manifest_root=root / "data" / "private" / "mi6" / "manifests",
    )
    events = build_release_events(crawl, root / "data" / "private" / "mi6" / "manifests")
    assert events["canonical_url"].is_unique
