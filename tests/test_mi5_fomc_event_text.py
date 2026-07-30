from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from market_strats.intelligence.mi5.fomc_event_text import (
    AVAILABILITY_EVIDENCE_LEVEL,
    EVENT_COLUMNS,
    ArchiveDiscoveryError,
    ArchiveStatementUrlConflictError,
    NoUsableFomcStatementsError,
    RawResponse,
    StatementLink,
    build_event_window_returns,
    build_lexical_descriptors,
    build_reports,
    discover_statement_links,
    discover_statement_links_with_diagnostics,
    extract_visible_statement_body,
    fetch_official_responses,
    first_equity_session_after,
    normalize_events,
    parse_outcome_records,
    parse_statement,
    resolve_publication_date,
    run_mi5_fomc_event_text_foundation,
    same_origin_url,
    usable_statement_count,
    write_raw_snapshots,
)

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"


class FakeFetcher:
    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def fetch(self, url: str, user_agent: str) -> bytes:
        self.calls.append(url)
        assert user_agent == "MarketIntelligenceLab/0.1 research-only contact=local-user"
        return self.payloads[url].encode("utf-8")


def _tmp(name: str) -> Path:
    path = ROOT / ".pytest_tmp" / f"mi5_{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _statement_html(date_text: str = "January 31, 2024", body: str | None = None) -> str:
    body = body or (
        "Inflation remains elevated. Employment gains are strong. "
        "The Committee will adjust the federal funds rate and balance sheet policy."
    )
    return f"""
    <html>
      <head><meta name="publication_date" content="{date_text}"></head>
      <body>
        <header>Search Navigation PDF Minutes</header>
        <main>
          <p class="release-date">For release at 2:00 p.m. EST {date_text}</p>
          <article><p>{body}</p></article>
        </main>
        <footer>Contact links</footer>
      </body>
    </html>
    """


def _visible_press_release_statement_html(
    date_text: str = "January 29, 2025",
    body: str | None = None,
    title: str = "Federal Reserve issues FOMC statement",
) -> str:
    body = body or (
        "Inflation remains elevated. Employment gains are strong. "
        "The Committee will adjust the federal funds rate and balance sheet policy."
    )
    return f"""
    <html>
      <body>
        <nav>Navigation Last Update January 1, 1999</nav>
        <main>
          <div class="press-release-header">
            <div>Press Release</div>
            <div>{date_text}</div>
          </div>
          <h1>{title}</h1>
          <article><p>{body}</p></article>
        </main>
        <footer>Last Update January 1, 1999</footer>
      </body>
    </html>
    """


def _config(path: Path, minimum_event_count: int = 2, minimum_model_count: int = 80) -> Path:
    path.write_text(
        f"""
source_id: federal_reserve_fomc_statement_html
archive_url: {ARCHIVE_URL}
event_type: fomc_statement
minimum_event_count: {minimum_event_count}
standalone_predictive_model_minimum_usable_statement_count: {minimum_model_count}
user_agent: MarketIntelligenceLab/0.1 research-only contact=local-user
lexicons:
  inflation: [inflation, price stability]
  employment: [employment, labor market]
  growth: [growth, economic activity]
  uncertainty: [uncertainty, risks]
  policy_rate: [federal funds rate, policy rate]
  balance_sheet: [balance sheet]
  restrictive: [restrictive, tightening]
  easing: [easing, accommodative]
""",
        encoding="utf-8",
    )
    return path


def _archive() -> str:
    return """
    <html><body>
      <h4>January 30-31</h4>
      <p>Statement: <a href="/monetarypolicy/files/statement20240131.pdf">PDF</a> |
      <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a></p>
      <p>Minutes: <a href="/monetarypolicy/fomcminutes20240131.htm">HTML</a></p>
      <p>Press Conference: <a href="/monetarypolicy/fomcpresconf20240131.htm">HTML</a></p>
      <h4>March 19-20</h4>
      <p>Statement: <a href="/newsevents/pressreleases/monetary20240320a.htm">HTML</a></p>
      <p>Statement: <a href="https://example.com/bad.htm">HTML</a></p>
    </body></html>
    """


def _bars() -> tuple[pd.DataFrame, pd.DataFrame]:
    sessions = pd.bdate_range("2024-01-02", periods=50)
    rows = []
    instruments = ["mi1_etf_spy", "mi1_etf_bil"]
    for instrument_index, instrument_id in enumerate(instruments):
        for index, session in enumerate(sessions):
            rows.append(
                {
                    "instrument_id": instrument_id,
                    "session_date": session,
                    "vendor_adjusted_close": 100 + index + instrument_index * 10,
                }
            )
    coverage = pd.DataFrame(
        {
            "instrument_id": instruments,
            "start_date_eligible": [True, True],
        }
    )
    return pd.DataFrame(rows), coverage


def test_only_statement_html_links_are_collected_and_external_rejected() -> None:
    links = discover_statement_links(_archive(), ARCHIVE_URL)
    assert [link.document_id for link in links] == ["monetary20240131a", "monetary20240320a"]
    assert all("minutes" not in link.url and "presconf" not in link.url for link in links)
    assert same_origin_url(ARCHIVE_URL, "/newsevents/pressreleases/x.htm").startswith(
        "https://www.federalreserve.gov/"
    )


def test_statement_pdf_separator_then_html_yields_one_link() -> None:
    archive = """
    <h4>May 1</h4>
    <p>Statement: <a href="/statement.pdf">PDF</a> |
    <a href="/newsevents/pressreleases/monetary20240501a.htm">HTML</a></p>
    """
    links = discover_statement_links(archive, ARCHIVE_URL)
    assert [link.document_id for link in links] == ["monetary20240501a"]


def test_nested_statement_label_and_html_whitespace_yield_one_link() -> None:
    archive = """
    <h4>June 12</h4>
    <p><span> Statement: </span>
    <span><a href="/statement.pdf">PDF</a></span> |
    <span><a href="/newsevents/pressreleases/monetary20240612a.htm"> HTML </a></span></p>
    """
    links = discover_statement_links(archive, ARCHIVE_URL)
    assert [link.document_id for link in links] == ["monetary20240612a"]


def test_minutes_html_and_html_outside_statement_scope_are_excluded() -> None:
    archive = """
    <h4>July 31</h4>
    <p>Minutes: <a href="/minutes.pdf">PDF</a> |
    <a href="/monetarypolicy/fomcminutes20240731.htm">HTML</a></p>
    <p><a href="/newsevents/pressreleases/unrelated.htm">HTML</a></p>
    """
    assert discover_statement_links(archive, ARCHIVE_URL) == []


def test_statement_scope_ends_at_each_boundary() -> None:
    boundaries = ["Minutes:", "Implementation Note", "Press Conference", "Projection Materials"]
    for boundary in boundaries:
        archive = f"""
        <h4>September 18</h4>
        <p>Statement: <a href="/statement.pdf">PDF</a></p>
        <p>{boundary} <a href="/newsevents/pressreleases/notstatement.htm">HTML</a></p>
        """
        assert discover_statement_links(archive, ARCHIVE_URL) == []
    heading_archive = """
    <h4>November 7</h4>
    <p>Statement: <a href="/statement.pdf">PDF</a></p>
    <h4>December 18</h4>
    <p><a href="/newsevents/pressreleases/notstatement.htm">HTML</a></p>
    """
    assert discover_statement_links(heading_archive, ARCHIVE_URL) == []


def test_same_archive_year_with_three_statement_scopes_returns_three_records() -> None:
    archive = """
    <h3>Meeting calendars, statements, and minutes (2021-2027)</h3>
    <h4>2024 FOMC Meetings</h4>
    <h4>January 31</h4>
    <p>Statement: <a href="/jan.pdf">PDF</a> |
    <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a></p>
    <h4>March 20</h4>
    <p>Statement: <a href="/mar.pdf">PDF</a> |
    <a href="/newsevents/pressreleases/monetary20240320a.htm">HTML</a></p>
    <h4>May 1</h4>
    <p>Statement: <a href="/may.pdf">PDF</a> |
    <a href="/newsevents/pressreleases/monetary20240501a.htm">HTML</a></p>
    """
    links = discover_statement_links(archive, ARCHIVE_URL)
    assert [link.document_id for link in links] == [
        "monetary20240131a",
        "monetary20240320a",
        "monetary20240501a",
    ]
    assert [link.statement_record_id for link in links] == [
        "2024:statement:1",
        "2024:statement:2",
        "2024:statement:3",
    ]


def test_multiple_same_year_statement_records_never_overwrite_each_other() -> None:
    archive = """
    <h3>2024</h3>
    <p>Statement: <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a></p>
    <p>Statement: <a href="/newsevents/pressreleases/monetary20240320a.htm">HTML</a></p>
    """
    links, diagnostics = discover_statement_links_with_diagnostics(archive, ARCHIVE_URL)
    assert len(links) == 2
    assert diagnostics.statement_record_count == 2
    assert diagnostics.unique_statement_record_url_pair_count == 2


def test_repeated_anchor_within_same_statement_record_deduplicates_to_one_pair() -> None:
    archive = """
    <h3>2024</h3>
    <h4>January 31</h4>
    <p>Statement:
    <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a> |
    <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a></p>
    """
    links, diagnostics = discover_statement_links_with_diagnostics(archive, ARCHIVE_URL)
    assert len(links) == 1
    assert diagnostics.statement_scoped_html_anchor_count == 2
    assert diagnostics.statement_record_count == 1
    assert diagnostics.unique_statement_record_url_pair_count == 1
    assert diagnostics.globally_conflicting_statement_url_count == 0


def test_same_url_attached_to_two_statement_records_fails_before_document_fetch() -> None:
    root = _tmp("statement_url_conflict")
    archive = """
    <h3>2024</h3>
    <h4>January 31</h4>
    <p>Statement: <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a></p>
    <h4>March 20</h4>
    <p>Statement: <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a></p>
    """
    config = {
        "archive_url": ARCHIVE_URL,
        "user_agent": "MarketIntelligenceLab/0.1 research-only contact=local-user",
        "minimum_event_count": 1,
    }
    fetcher = FakeFetcher({ARCHIVE_URL: archive})
    with pytest.raises(ArchiveStatementUrlConflictError) as exc:
        fetch_official_responses(
            config,
            fetcher,
            root / "data" / "private" / "mi5" / "raw",
            root / "data" / "private" / "mi5" / "manifests",
        )
    message = str(exc.value)
    assert "conflicting_statement_url_count=1" in message
    assert "2024:statement:1" in message
    assert "2024:statement:2" in message
    assert fetcher.calls == [ARCHIVE_URL]


def test_discovery_diagnostics_report_counts() -> None:
    archive = """
    <h4>January 31</h4>
    <p>Statement: <a href="/statement.pdf">PDF</a> |
    <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a></p>
    <p>Minutes: <a href="/minutes.pdf">PDF</a> |
    <a href="/monetarypolicy/fomcminutes20240131.htm">HTML</a></p>
    <p><a href="https://example.com/external.htm">HTML</a></p>
    """
    links, diagnostics = discover_statement_links_with_diagnostics(
        archive,
        ARCHIVE_URL,
        minimum_event_count=25,
    )
    assert len(links) == 1
    assert diagnostics.total_anchor_count == 5
    assert diagnostics.same_origin_anchor_count == 4
    assert diagnostics.html_anchor_count == 3
    assert diagnostics.statement_scoped_html_anchor_count == 1
    assert diagnostics.minutes_scoped_html_anchor_count == 1
    assert diagnostics.statement_record_count == 1
    assert diagnostics.unique_statement_record_url_pair_count == 1
    assert diagnostics.globally_conflicting_statement_url_count == 0
    assert diagnostics.minimum_event_count == 25


def test_diagnostics_distinguish_scoped_candidates_from_canonical_pairs() -> None:
    archive = """
    <h3>2024</h3>
    <h4>January 31</h4>
    <p>Statement:
    <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a> |
    <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a></p>
    <h4>March 20</h4>
    <p>Statement: <a href="/newsevents/pressreleases/monetary20240320a.htm">HTML</a></p>
    <p>Minutes: <a href="/monetarypolicy/fomcminutes20240320.htm">HTML</a></p>
    """
    links, diagnostics = discover_statement_links_with_diagnostics(
        archive,
        ARCHIVE_URL,
        minimum_event_count=25,
    )
    assert len(links) == 2
    assert diagnostics.statement_scoped_html_anchor_count == 3
    assert diagnostics.minutes_scoped_html_anchor_count == 1
    assert diagnostics.statement_record_count == 2
    assert diagnostics.unique_statement_record_url_pair_count == 2


def test_archive_snapshot_manifest_written_before_minimum_count_failure() -> None:
    root = _tmp("discovery_failure")
    archive = """
    <h4>January 31</h4>
    <p>Statement: <a href="/statement.pdf">PDF</a> |
    <a href="/newsevents/pressreleases/monetary20240131a.htm">HTML</a></p>
    """
    config = {
        "archive_url": ARCHIVE_URL,
        "user_agent": "MarketIntelligenceLab/0.1 research-only contact=local-user",
        "minimum_event_count": 2,
    }
    with pytest.raises(ArchiveDiscoveryError) as exc:
        fetch_official_responses(
            config,
            FakeFetcher({ARCHIVE_URL: archive}),
            root / "data" / "private" / "mi5" / "raw",
            root / "data" / "private" / "mi5" / "manifests",
        )
    message = str(exc.value)
    assert "total_anchor_count=2" in message
    assert "unique_statement_record_url_pair_count=1" in message
    assert (
        root / "data" / "private" / "mi5" / "manifests" / "fomc_raw_snapshot_manifest.parquet"
    ).exists()
    assert len(list((root / "data" / "private" / "mi5" / "raw").glob("*.html"))) == 1


def test_publication_metadata_resolves_actual_date_and_meeting_label_is_provenance_only() -> None:
    link = StatementLink("January 30-31", FED_URL := f"{ARCHIVE_URL}/../x.htm", "x")
    parsed = parse_statement(link, _statement_html("January 31, 2024"))
    assert FED_URL
    assert parsed.publication_date.isoformat() == "2024-01-31"
    assert parsed.link.meeting_label == "January 30-31"
    assert parsed.publication_date_resolution_status == "resolved"


def test_visible_press_release_header_date_resolves_fomc_statement_date() -> None:
    link = StatementLink(
        "January 28-29",
        "https://www.federalreserve.gov/newsevents/pressreleases/monetary20250129a.htm",
        "monetary20250129a",
    )
    parsed = parse_statement(link, _visible_press_release_statement_html("January 29, 2025"))
    assert parsed.publication_date.isoformat() == "2025-01-29"
    assert parsed.publication_date_evidence_source == "visible_press_release_header_date"
    assert parsed.publication_date_resolution_status == "resolved"
    assert parsed.exclusion_reason == ""


def test_meeting_label_does_not_resolve_publication_date() -> None:
    link = StatementLink(
        "January 28-29",
        "https://www.federalreserve.gov/newsevents/pressreleases/monetary20250129a.htm",
        "monetary20250129a",
    )
    parsed = parse_statement(
        link,
        """
        <main>
          <div>Press Release</div>
          <h1>Federal Reserve issues FOMC statement</h1>
          <article><p>Statement body text.</p></article>
        </main>
        """,
    )
    assert parsed.publication_date is None
    assert parsed.publication_date_resolution_status == "excluded_missing_publication_date"


def test_last_update_and_implementation_note_dates_are_rejected() -> None:
    link = StatementLink(
        "January 28-29",
        "https://www.federalreserve.gov/newsevents/pressreleases/monetary20250129a.htm",
        "monetary20250129a",
    )
    last_update = """
    <main>
      <div>Press Release</div>
      <div>Last Update January 29, 2025</div>
      <h1>Federal Reserve issues FOMC statement</h1>
      <article><p>Statement body text.</p></article>
    </main>
    """
    implementation_note = """
    <main>
      <div>Press Release</div>
      <div>Implementation Note January 29, 2025</div>
      <h1>Federal Reserve issues FOMC statement</h1>
      <article><p>Statement body text.</p></article>
    </main>
    """
    assert parse_statement(link, last_update).publication_date is None
    assert parse_statement(link, implementation_note).publication_date is None


def test_ambiguous_conflicting_or_missing_publication_dates_exclude_event() -> None:
    conflicting = """
    <meta name="publication_date" content="January 31, 2024">
    <meta name="published" content="February 1, 2024">
    <main>Statement body text.</main>
    """
    assert resolve_publication_date(conflicting)[2] == "excluded_conflicting_publication_dates"
    assert resolve_publication_date("<main>January 31, 2024 Statement body.</main>")[2] == (
        "excluded_missing_publication_date"
    )


def test_conflicting_same_precedence_visible_header_dates_exclude_document() -> None:
    html = """
    <main>
      <div>Press Release</div>
      <div>January 29, 2025</div>
      <div>January 30, 2025</div>
      <h1>Federal Reserve issues FOMC statement</h1>
      <article><p>Statement body text.</p></article>
    </main>
    """
    publication_date, evidence, status = resolve_publication_date(html)
    assert publication_date is None
    assert evidence == "visible_press_release_header_date,visible_press_release_header_date"
    assert status == "excluded_conflicting_publication_dates"


def test_no_resolved_dates_raise_typed_summary_exception_not_key_error() -> None:
    parsed = [
        parse_statement(
            StatementLink(
                "January 28-29",
                "https://www.federalreserve.gov/newsevents/pressreleases/one.htm",
                "one",
                statement_record_id="2025:statement:1",
            ),
            """
            <main>
              <h1>Federal Reserve issues FOMC statement</h1>
              <article><p>Statement body text.</p></article>
            </main>
            """,
        )
    ]
    with pytest.raises(NoUsableFomcStatementsError) as exc:
        normalize_events(parsed)
    message = str(exc.value)
    assert "fetched_statement_document_count=1" in message
    assert "usable_statement_count=0" in message
    assert "excluded_statement_count=1" in message
    assert "excluded_missing_publication_date" in message
    assert "2025:statement:1" in message


def test_mixed_usable_and_excluded_documents_normalize_with_expected_schema() -> None:
    parsed = [
        parse_statement(
            StatementLink(
                "January 28-29",
                "https://www.federalreserve.gov/newsevents/pressreleases/one.htm",
                "one",
                statement_record_id="2025:statement:1",
            ),
            _visible_press_release_statement_html("January 29, 2025"),
        ),
        parse_statement(
            StatementLink(
                "March 18-19",
                "https://www.federalreserve.gov/newsevents/pressreleases/two.htm",
                "two",
                statement_record_id="2025:statement:2",
            ),
            """
            <main>
              <h1>Federal Reserve issues FOMC statement</h1>
              <article><p>Statement body text.</p></article>
            </main>
            """,
        ),
    ]
    outcomes = parse_outcome_records(parsed)
    assert len(outcomes) == 2
    assert outcomes[0]["document_fetch_status"] == "fetched"
    assert outcomes[1]["exclusion_reason"] == "excluded_missing_publication_date"
    events = normalize_events(parsed)
    assert list(events.columns) == EVENT_COLUMNS
    assert len(events) == 1
    assert events.loc[0, "statement_record_id"] == "2025:statement:1"
    assert events.loc[0, "publication_date_evidence_source"] == (
        "visible_press_release_header_date"
    )


def test_raw_snapshot_hashing_and_local_only_manifest_paths() -> None:
    root = _tmp("raw")
    manifest = write_raw_snapshots(
        [
            RawResponse(
                source_url=ARCHIVE_URL,
                content=b"<html>archive</html>",
                retrieved_at_utc=datetime(2024, 1, 1, tzinfo=UTC),
                document_id="archive",
            )
        ],
        root / "data" / "private" / "mi5" / "raw",
        root / "data" / "private" / "mi5" / "manifests",
    )
    assert len(manifest.loc[0, "content_sha256"]) == 64
    assert (
        "data\\private\\mi5\\raw" in manifest.loc[0, "raw_path"]
        or "data/private/mi5/raw" in manifest.loc[0, "raw_path"]
    )


def test_conservative_next_eligible_session_availability_and_no_same_day() -> None:
    link = StatementLink("January 30-31", "https://www.federalreserve.gov/x.htm", "x")
    parsed = parse_statement(link, _statement_html("January 31, 2024"))
    events = normalize_events([parsed])
    assert events.loc[0, "effective_session_date"] > pd.Timestamp("2024-01-31")
    assert events.loc[0, "availability_evidence_level"] == AVAILABILITY_EVIDENCE_LEVEL
    assert first_equity_session_after(pd.Timestamp("2024-01-31").date()) == pd.Timestamp(
        "2024-02-01"
    )


def test_visible_body_extraction_excludes_page_chrome() -> None:
    body, status, count = extract_visible_statement_body(_statement_html(body="Policy text only."))
    assert status == "extracted"
    assert count > 0
    assert "Navigation" not in body
    assert "Contact" not in body
    assert "Policy text only" in body


def test_deterministic_lexicon_counts_and_first_statement_novelty_null() -> None:
    parsed = [
        parse_statement(
            StatementLink("one", "https://www.federalreserve.gov/one.htm", "one"),
            _statement_html("January 31, 2024", "Inflation inflation. Federal funds rate."),
        ),
        parse_statement(
            StatementLink("two", "https://www.federalreserve.gov/two.htm", "two"),
            _statement_html("March 20, 2024", "Employment growth uncertainty easing."),
        ),
    ]
    descriptors = build_lexical_descriptors(
        parsed,
        {
            "inflation": ["inflation"],
            "employment": ["employment"],
            "growth": ["growth"],
            "uncertainty": ["uncertainty"],
            "policy_rate": ["federal funds rate"],
            "balance_sheet": ["balance sheet"],
            "restrictive": ["restrictive"],
            "easing": ["easing"],
        },
    )
    assert descriptors.loc[0, "inflation_term_count"] == 2
    assert descriptors.loc[0, "policy_rate_term_count"] == 1
    assert pd.isna(descriptors.loc[0, "novel_token_ratio_vs_prior_statement"])
    assert descriptors.loc[1, "novel_token_ratio_vs_prior_statement"] > 0


def test_event_window_returns_use_t_to_t_plus_h_and_bil_excess() -> None:
    link = StatementLink("January 30-31", "https://www.federalreserve.gov/x.htm", "x")
    event = normalize_events([parse_statement(link, _statement_html("January 31, 2024"))])
    bars, coverage = _bars()
    returns = build_event_window_returns(
        event,
        bars,
        coverage,
        {"mi1_etf_spy": "equity_broad_market", "mi1_etf_bil": "cash_proxy"},
    )
    one = returns[
        (returns["instrument_id"] == "mi1_etf_spy") & (returns["horizon"] == "1_session")
    ].iloc[0]
    prices = bars.pivot(
        index="session_date", columns="instrument_id", values="vendor_adjusted_close"
    )
    t = event.loc[0, "effective_session_date"]
    t1 = pd.bdate_range(t, periods=2)[1]
    expected_asset = prices.at[t1, "mi1_etf_spy"] / prices.at[t, "mi1_etf_spy"] - 1
    expected_bil = prices.at[t1, "mi1_etf_bil"] / prices.at[t, "mi1_etf_bil"] - 1
    assert one["asset_total_return_h"] == pytest.approx(expected_asset)
    assert one["bil_excess_return_h"] == pytest.approx(expected_asset - expected_bil)
    assert one["effective_session_date"] > pd.Timestamp("2024-01-31")


def test_incomplete_horizons_are_excluded() -> None:
    link = StatementLink("late", "https://www.federalreserve.gov/late.htm", "late")
    event = normalize_events([parse_statement(link, _statement_html("February 28, 2024"))])
    bars, coverage = _bars()
    returns = build_event_window_returns(
        event,
        bars,
        coverage,
        {"mi1_etf_spy": "equity_broad_market", "mi1_etf_bil": "cash_proxy"},
    )
    assert returns.empty or "20_sessions" not in set(returns["horizon"])


def test_corpus_suitability_count_and_threshold() -> None:
    link = StatementLink("January 30-31", "https://www.federalreserve.gov/x.htm", "x")
    parsed = [parse_statement(link, _statement_html("January 31, 2024"))]
    events = normalize_events(parsed)
    descriptors = build_lexical_descriptors(
        parsed,
        {
            "inflation": ["inflation"],
            "employment": ["employment"],
            "growth": ["growth"],
            "uncertainty": ["uncertainty"],
            "policy_rate": ["federal funds rate"],
            "balance_sheet": ["balance sheet"],
            "restrictive": ["restrictive"],
            "easing": ["easing"],
        },
    )
    bars, coverage = _bars()
    returns = build_event_window_returns(
        events,
        bars,
        coverage,
        {"mi1_etf_spy": "equity_broad_market", "mi1_etf_bil": "cash_proxy"},
    )
    assert usable_statement_count(events, descriptors, returns) == 1
    _md, _json, report = build_reports(
        config={
            "source_id": "federal_reserve_fomc_statement_html",
            "archive_url": ARCHIVE_URL,
            "event_type": "fomc_statement",
            "standalone_predictive_model_minimum_usable_statement_count": 80,
        },
        parsed=parsed,
        events=events,
        descriptors=descriptors,
        returns=returns,
        report_root=_tmp("report"),
    )
    assert report["usable_statement_count"] == 1
    assert report["standalone_predictive_model_eligible"] is False


def test_run_mi5_with_fake_fetcher_writes_outputs_and_uses_no_network() -> None:
    safe_archive = _archive().replace(
        '<p>Statement: <a href="https://example.com/bad.htm">HTML</a></p>', ""
    )
    urls = {
        ARCHIVE_URL: safe_archive,
        (
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240131a.htm"
        ): _statement_html("January 31, 2024"),
        (
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240320a.htm"
        ): _statement_html("March 20, 2024"),
    }
    root = _tmp("run")
    mi1 = root / "data" / "private" / "mi1"
    normalized = mi1 / "normalized"
    normalized.mkdir(parents=True)
    bars, coverage = _bars()
    bars.to_parquet(normalized / "market_eod_bar.parquet", index=False)
    coverage.to_parquet(normalized / "coverage_audit.parquet", index=False)
    result = run_mi5_fomc_event_text_foundation(
        mi1_data_root=mi1,
        mi5_data_root=root / "data" / "private" / "mi5",
        report_root=root / "reports" / "mi5",
        config_path=_config(root / "event_source_mi5.yaml"),
        universe_config_path=ROOT / "configs" / "intelligence" / "universe_mi1.yaml",
        fetcher=FakeFetcher(urls),
    )
    assert result.statement_count == 2
    assert result.resolved_publication_date_count == 2
    assert result.lexical_descriptor_row_count == 2
    for path in result.output_paths.values():
        assert Path(path).exists()
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/data/private/mi5/*" in gitignore
    assert "/reports/mi5/*" in gitignore


def test_no_forecast_portfolio_candidate_broker_llm_or_network_dependency() -> None:
    source_text = (
        (ROOT / "src" / "market_strats" / "intelligence" / "mi5" / "fomc_event_text.py")
        .read_text(encoding="utf-8")
        .lower()
    )
    for prohibited in ["randomforest", "candidate_packet", "submit_order", "target_weight", "llm"]:
        assert prohibited not in source_text
