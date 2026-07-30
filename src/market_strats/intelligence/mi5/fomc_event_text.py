"""MI-5 FOMC event/text foundation."""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import yaml

AVAILABILITY_EVIDENCE_LEVEL = "contractual_assumption"
AVAILABILITY_RULE_ID = "fomc_statement_next_eligible_session_close_v1"
SOURCE_NAME = "Federal Reserve FOMC statement HTML archive"
FED_ORIGIN = "https://www.federalreserve.gov"
HORIZONS = {"1_session": 1, "5_sessions": 5, "20_sessions": 20}
KNOWN_LIMITATIONS = [
    "This is a sparse, official-policy-event corpus.",
    "It is not a general news dataset.",
    "It does not establish forecast skill, trading value, or candidate-signal eligibility.",
    "Historical intraday publication timestamps are not provider-timestamp-verified.",
    (
        "FOMC text alone must not be used as a standalone model unless a later phase explicitly "
        "evaluates a suitable corpus under pre-registered rules."
    ),
]


@dataclass(frozen=True)
class RawResponse:
    source_url: str
    content: bytes
    retrieved_at_utc: datetime
    meeting_label: str | None = None
    document_id: str | None = None
    statement_publication_date: date | None = None


@dataclass(frozen=True)
class StatementLink:
    meeting_label: str
    url: str
    document_id: str
    statement_record_id: str = ""
    archive_year: str | None = None


@dataclass(frozen=True)
class ArchiveDiscoveryDiagnostics:
    total_anchor_count: int = 0
    same_origin_anchor_count: int = 0
    html_anchor_count: int = 0
    statement_scoped_html_anchor_count: int = 0
    minutes_scoped_html_anchor_count: int = 0
    statement_record_count: int = 0
    unique_statement_record_url_pair_count: int = 0
    globally_conflicting_statement_url_count: int = 0
    minimum_event_count: int = 0

    def as_error_message(self) -> str:
        return (
            "FOMC statement HTML discovery below minimum_event_count "
            f"total_anchor_count={self.total_anchor_count} "
            f"same_origin_anchor_count={self.same_origin_anchor_count} "
            f"html_anchor_count={self.html_anchor_count} "
            f"statement_scoped_html_anchor_count={self.statement_scoped_html_anchor_count} "
            f"minutes_scoped_html_anchor_count={self.minutes_scoped_html_anchor_count} "
            f"statement_record_count={self.statement_record_count} "
            f"unique_statement_record_url_pair_count="
            f"{self.unique_statement_record_url_pair_count} "
            f"globally_conflicting_statement_url_count="
            f"{self.globally_conflicting_statement_url_count} "
            f"minimum_event_count={self.minimum_event_count}"
        )


class ArchiveDiscoveryError(ValueError):
    def __init__(self, diagnostics: ArchiveDiscoveryDiagnostics) -> None:
        self.diagnostics = diagnostics
        super().__init__(diagnostics.as_error_message())


class ArchiveStatementUrlConflictError(ValueError):
    def __init__(self, conflicts: dict[str, list[str]]) -> None:
        self.conflicts = conflicts
        affected = sorted({record_id for values in conflicts.values() for record_id in values})
        super().__init__(
            "Conflicting statement URL attached to multiple statement records "
            f"conflicting_statement_url_count={len(conflicts)} "
            f"affected_statement_record_ids={affected}"
        )


class NoUsableFomcStatementsError(ValueError):
    def __init__(self, parsed: list[ParsedStatement]) -> None:
        fetched_count = len(parsed)
        usable_count = sum(1 for item in parsed if not item.exclusion_reason)
        excluded_count = fetched_count - usable_count
        publication_counts = Counter(item.publication_date_resolution_status for item in parsed)
        extraction_counts = Counter(item.extraction_status for item in parsed)
        samples = [
            item.link.statement_record_id or item.link.document_id
            for item in parsed
            if item.exclusion_reason
        ][:10]
        self.fetched_statement_document_count = fetched_count
        self.usable_statement_count = usable_count
        self.excluded_statement_count = excluded_count
        self.publication_date_resolution_reason_counts = dict(publication_counts)
        self.visible_body_extraction_reason_counts = dict(extraction_counts)
        self.sample_excluded_statement_record_ids = samples
        super().__init__(
            "No usable FOMC statement events after parsing "
            f"fetched_statement_document_count={fetched_count} "
            f"usable_statement_count={usable_count} "
            f"excluded_statement_count={excluded_count} "
            "publication_date_resolution_reason_counts="
            f"{dict(sorted(publication_counts.items()))} "
            "visible_body_extraction_reason_counts="
            f"{dict(sorted(extraction_counts.items()))} "
            f"sample_excluded_statement_record_ids={samples}"
        )


@dataclass(frozen=True)
class ParsedStatement:
    link: StatementLink
    document_fetch_status: str
    publication_date: date | None
    publication_date_evidence_source: str
    publication_date_resolution_status: str
    body_text: str
    extraction_status: str
    exclusion_reason: str
    content_sha256: str


@dataclass(frozen=True)
class Mi5RunResult:
    mi1_input_provenance: dict[str, Any]
    archive_source_id: str
    discovered_coverage_start: str | None
    discovered_coverage_end: str | None
    statement_count: int
    resolved_publication_date_count: int
    excluded_event_count: int
    availability_evidence_level: str
    lexical_descriptor_row_count: int
    usable_statement_count: int
    standalone_predictive_model_eligible: bool
    event_window_row_count: int
    output_paths: dict[str, str]


@dataclass(frozen=True)
class VisibleTextSegment:
    text: str
    tag: str
    is_heading: bool
    in_main_content: bool


class Fetcher(Protocol):
    def fetch(self, url: str, user_agent: str) -> bytes:
        """Fetch one URL and return response bytes."""


class UrlLibFetcher:
    def fetch(self, url: str, user_agent: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return value


def canonical_bytes(payload: bytes) -> bytes:
    return payload.replace(b"\r\n", b"\n")


def content_hash(payload: bytes) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def same_origin_url(base_url: str, href: str) -> str:
    resolved = urllib.parse.urljoin(base_url, href)
    parsed = urllib.parse.urlparse(resolved)
    if parsed.scheme != "https" or parsed.netloc.lower() != "www.federalreserve.gov":
        raise ValueError(f"Non-Federal-Reserve statement URL rejected: {resolved}")
    return urllib.parse.urlunparse(parsed._replace(fragment=""))


def is_same_origin_url(base_url: str, href: str) -> bool:
    resolved = urllib.parse.urljoin(base_url, href)
    parsed = urllib.parse.urlparse(resolved)
    return parsed.scheme == "https" and parsed.netloc.lower() == "www.federalreserve.gov"


def document_id_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    stem = Path(parsed.path).stem
    if not stem:
        raise ValueError(f"Unable to derive document identifier from {url}")
    return stem


def normalize_visible_for_comparison(value: str) -> str:
    return normalize_space(html.unescape(value)).casefold()


def extract_single_archive_year(value: str) -> str | None:
    years = sorted(set(re.findall(r"\b(?:19|20)\d{2}\b", value)))
    if len(years) == 1:
        return years[0]
    return None


ARCHIVE_BOUNDARY_LABELS = {
    "minutes:",
    "implementation note",
    "press conference",
    "projection materials",
}


class ArchiveStatementParser(HTMLParser):
    def __init__(self, archive_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.archive_url = archive_url
        self.links: list[StatementLink] = []
        self._heading_stack: list[str] = []
        self._current_year: str | None = None
        self._current_meeting_label = ""
        self._heading_buffer: list[str] = []
        self._anchor_href: str | None = None
        self._anchor_text: list[str] = []
        self._statement_scope = False
        self._minutes_scope = False
        self._statement_ordinals_by_year: dict[str, int] = {}
        self._current_statement_record_id = ""
        self._statement_record_ids: set[str] = set()
        self._total_anchor_count = 0
        self._same_origin_anchor_count = 0
        self._html_anchor_count = 0
        self._statement_scoped_html_anchor_count = 0
        self._minutes_scoped_html_anchor_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h2", "h3", "h4", "h5"}:
            self._exit_scopes()
            self._heading_stack.append(tag)
            self._heading_buffer = []
        if tag == "a":
            self._anchor_href = dict(attrs).get("href")
            self._anchor_text = []
            self._total_anchor_count += 1
            if self._anchor_href and is_same_origin_url(self.archive_url, self._anchor_href):
                self._same_origin_anchor_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "h3", "h4", "h5"} and self._heading_stack:
            text = normalize_space(" ".join(self._heading_buffer))
            if text:
                archive_year = extract_single_archive_year(text)
                if archive_year is not None:
                    self._current_year = archive_year
                if tag not in {"h2", "h3"}:
                    self._current_meeting_label = text
            self._heading_stack.pop()
            self._heading_buffer = []
        if tag == "a" and self._anchor_href:
            label = normalize_space(" ".join(self._anchor_text))
            normalized_label = normalize_visible_for_comparison(label)
            if normalized_label == "html":
                self._html_anchor_count += 1
                if self._minutes_scope and is_same_origin_url(self.archive_url, self._anchor_href):
                    self._minutes_scoped_html_anchor_count += 1
                if self._statement_scope and is_same_origin_url(
                    self.archive_url, self._anchor_href
                ):
                    self._statement_scoped_html_anchor_count += 1
                    url = same_origin_url(self.archive_url, self._anchor_href)
                    self.links.append(
                        StatementLink(
                            meeting_label=self._current_meeting_label,
                            url=url,
                            document_id=document_id_from_url(url),
                            statement_record_id=self._current_statement_record_id,
                            archive_year=self._current_year,
                        )
                    )
            self._anchor_href = None
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        text = normalize_space(data)
        if not text:
            return
        if self._heading_stack:
            self._heading_buffer.append(text)
        if self._anchor_href is not None:
            self._anchor_text.append(text)
        normalized = normalize_visible_for_comparison(text)
        if normalized == "statement:":
            self._enter_statement_scope()
            return
        if normalized in ARCHIVE_BOUNDARY_LABELS:
            self._statement_scope = False
            self._minutes_scope = normalized == "minutes:"

    def _exit_scopes(self) -> None:
        self._statement_scope = False
        self._minutes_scope = False

    def _enter_statement_scope(self) -> None:
        archive_year = self._current_year or "unknown_year"
        ordinal = self._statement_ordinals_by_year.get(archive_year, 0) + 1
        self._statement_ordinals_by_year[archive_year] = ordinal
        self._current_statement_record_id = f"{archive_year}:statement:{ordinal}"
        self._statement_record_ids.add(self._current_statement_record_id)
        self._statement_scope = True
        self._minutes_scope = False

    def diagnostics(self, minimum_event_count: int = 0) -> ArchiveDiscoveryDiagnostics:
        links, conflicts = canonicalize_statement_links(self.links)
        return ArchiveDiscoveryDiagnostics(
            total_anchor_count=self._total_anchor_count,
            same_origin_anchor_count=self._same_origin_anchor_count,
            html_anchor_count=self._html_anchor_count,
            statement_scoped_html_anchor_count=self._statement_scoped_html_anchor_count,
            minutes_scoped_html_anchor_count=self._minutes_scoped_html_anchor_count,
            statement_record_count=len(self._statement_record_ids),
            unique_statement_record_url_pair_count=len(links),
            globally_conflicting_statement_url_count=len(conflicts),
            minimum_event_count=minimum_event_count,
        )


def discover_statement_links(archive_html: str, archive_url: str) -> list[StatementLink]:
    links, _diagnostics = discover_statement_links_with_diagnostics(archive_html, archive_url)
    return links


def canonicalize_statement_links(
    candidates: list[StatementLink],
) -> tuple[list[StatementLink], dict[str, list[str]]]:
    seen_pairs: set[tuple[str, str]] = set()
    links: list[StatementLink] = []
    record_ids_by_url: dict[str, set[str]] = {}
    for link in candidates:
        pair = (link.statement_record_id, link.url)
        record_ids_by_url.setdefault(link.url, set()).add(link.statement_record_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        links.append(link)
    conflicts = {
        url: sorted(record_ids)
        for url, record_ids in record_ids_by_url.items()
        if len(record_ids) > 1
    }
    return links, conflicts


def discover_statement_links_with_diagnostics(
    archive_html: str,
    archive_url: str,
    *,
    minimum_event_count: int = 0,
) -> tuple[list[StatementLink], ArchiveDiscoveryDiagnostics]:
    parser = ArchiveStatementParser(archive_url)
    parser.feed(archive_html)
    links, conflicts = canonicalize_statement_links(parser.links)
    diagnostics = parser.diagnostics(minimum_event_count)
    if conflicts:
        raise ArchiveStatementUrlConflictError(conflicts)
    return links, diagnostics


class StatementPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta_dates: list[tuple[str, str]] = []
        self.time_dates: list[str] = []
        self.visible_date_candidates: list[str] = []
        self.visible_segments: list[VisibleTextSegment] = []
        self.body_parts: list[str] = []
        self._skip_depth = 0
        self._body_depth = 0
        self._current_dateish = False
        self._tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta"}:
            self._tag_stack.append(tag)
        attr = {key.lower(): value or "" for key, value in attrs}
        attr_text = " ".join(attr.values()).lower()
        if tag in {"script", "style", "nav", "header", "footer", "a"}:
            self._skip_depth += 1
        if tag in {"main", "article"} or "article" in attr_text or "content" in attr_text:
            self._body_depth += 1
        if tag == "meta":
            name = (attr.get("name") or attr.get("property") or "").lower()
            content = attr.get("content", "")
            if any(key in name for key in ["date", "published", "publication"]):
                self.meta_dates.append((name, content))
        if tag == "time" and attr.get("datetime"):
            self.time_dates.append(attr["datetime"])
        self._current_dateish = any(key in attr_text for key in ["date", "time", "release"])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "header", "footer", "a"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"main", "article"} and self._body_depth:
            self._body_depth -= 1
        self._current_dateish = False
        if tag in self._tag_stack:
            while self._tag_stack:
                popped = self._tag_stack.pop()
                if popped == tag:
                    break

    def handle_data(self, data: str) -> None:
        text = normalize_space(data)
        if not text:
            return
        current_tag = self._tag_stack[-1] if self._tag_stack else ""
        if self._skip_depth == 0:
            self.visible_segments.append(
                VisibleTextSegment(
                    text=text,
                    tag=current_tag,
                    is_heading=current_tag in {"h1", "h2", "h3", "h4", "h5", "h6"},
                    in_main_content=self._body_depth > 0,
                )
            )
        if self._current_dateish or re.search(
            r"(for release|release date|publication date)", text, re.I
        ):
            self.visible_date_candidates.append(text)
        if self._skip_depth == 0:
            self.body_parts.append(text)


def normalize_space(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|November|December"
)
DATE_PATTERN = re.compile(rf"\b({MONTH_PATTERN})\s+\d{{1,2}},\s+\d{{4}}\b")


def parse_date_value(value: str) -> date | None:
    text = normalize_space(value)
    if not text:
        return None
    match = DATE_PATTERN.search(text)
    candidate = match.group(0) if match else text
    parsed = pd.to_datetime(candidate, errors="coerce", utc=False)
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).date()


def _resolve_single_precedence_level(
    sources: list[tuple[str, date]],
) -> tuple[date | None, str, str] | None:
    if not sources:
        return None
    dates = {item[1] for item in sources}
    if len(dates) > 1:
        return (
            None,
            ",".join(source for source, _date in sources),
            "excluded_conflicting_publication_dates",
        )
    return sources[0][1], sources[0][0], "resolved"


def _is_statement_heading(text: str) -> bool:
    return normalize_visible_for_comparison(text) == "federal reserve issues fomc statement"


def _is_rejected_visible_date_context(text: str) -> bool:
    normalized = normalize_visible_for_comparison(text)
    return any(
        phrase in normalized
        for phrase in [
            "last update",
            "implementation note",
            "minutes",
            "transcript",
            "projection materials",
        ]
    )


def _visible_press_release_header_dates(parser: StatementPageParser) -> list[tuple[str, date]]:
    segments = parser.visible_segments
    sources: list[tuple[str, date]] = []
    for index, segment in enumerate(segments):
        if _is_rejected_visible_date_context(segment.text):
            continue
        match = DATE_PATTERN.search(segment.text)
        if match is None:
            continue
        candidate_date = parse_date_value(match.group(0))
        if candidate_date is None:
            continue
        following_heading_index: int | None = None
        following_heading_text = ""
        for heading_index in range(index + 1, len(segments)):
            if segments[heading_index].is_heading:
                following_heading_index = heading_index
                following_heading_text = segments[heading_index].text
                break
        if following_heading_index is None or not _is_statement_heading(following_heading_text):
            continue
        prior_header_segments = segments[: index + 1]
        press_release_seen = any(
            normalize_visible_for_comparison(item.text) == "press release"
            or "press release" in normalize_visible_for_comparison(item.text)
            for item in prior_header_segments
        )
        if not press_release_seen:
            continue
        intervening_heading = any(
            item.is_heading for item in segments[index + 1 : following_heading_index]
        )
        if intervening_heading:
            continue
        sources.append(("visible_press_release_header_date", candidate_date))
    return sources


def resolve_publication_date(html: str) -> tuple[date | None, str, str]:
    parser = StatementPageParser()
    parser.feed(html)
    meta_sources: list[tuple[str, date]] = []
    for name, value in parser.meta_dates:
        parsed = parse_date_value(value)
        if parsed is not None:
            meta_sources.append((f"meta:{name}", parsed))
    resolved = _resolve_single_precedence_level(meta_sources)
    if resolved is not None:
        return resolved
    time_sources: list[tuple[str, date]] = []
    for value in parser.time_dates:
        parsed = parse_date_value(value)
        if parsed is not None:
            time_sources.append(("time:datetime", parsed))
    resolved = _resolve_single_precedence_level(time_sources)
    if resolved is not None:
        return resolved
    visible_sources = _visible_press_release_header_dates(parser)
    resolved = _resolve_single_precedence_level(visible_sources)
    if resolved is not None:
        return resolved
    return None, "", "excluded_missing_publication_date"


def extract_visible_statement_body(html: str) -> tuple[str, str, int]:
    parser = StatementPageParser()
    parser.feed(html)
    text = normalize_space(" ".join(parser.body_parts))
    text = re.sub(r"(?i)\b(federal reserve|monetary policy|open market operations)\b", "", text)
    text = normalize_space(text)
    if not text:
        return "", "excluded_empty_body", 0
    return text, "extracted", len(text)


def parse_statement(link: StatementLink, html: str) -> ParsedStatement:
    publication_date, evidence, status = resolve_publication_date(html)
    body, extraction_status, _chars = extract_visible_statement_body(html)
    exclusion = ""
    if status != "resolved":
        exclusion = status
    elif extraction_status != "extracted":
        exclusion = extraction_status
    return ParsedStatement(
        link=link,
        document_fetch_status="fetched",
        publication_date=publication_date,
        publication_date_evidence_source=evidence,
        publication_date_resolution_status=status,
        body_text=body,
        extraction_status=extraction_status,
        exclusion_reason=exclusion,
        content_sha256=content_hash(html.encode("utf-8")),
    )


def fetch_official_responses(
    config: dict[str, Any],
    fetcher: Fetcher,
    raw_root: Path | None = None,
    manifest_root: Path | None = None,
) -> tuple[list[RawResponse], list[StatementLink]]:
    archive_url = str(config["archive_url"])
    user_agent = str(config["user_agent"])
    retrieved = datetime.now(UTC)
    archive_content = fetcher.fetch(archive_url, user_agent)
    archive_response = RawResponse(
        source_url=archive_url,
        content=archive_content,
        retrieved_at_utc=retrieved,
        document_id="archive",
    )
    if raw_root is not None and manifest_root is not None:
        write_raw_snapshots([archive_response], raw_root, manifest_root)
    archive_html = archive_content.decode("utf-8", errors="replace")
    minimum_event_count = int(config["minimum_event_count"])
    links, diagnostics = discover_statement_links_with_diagnostics(
        archive_html,
        archive_url,
        minimum_event_count=minimum_event_count,
    )
    if len(links) < minimum_event_count:
        raise ArchiveDiscoveryError(diagnostics)
    responses = [archive_response]
    for link in links:
        responses.append(
            RawResponse(
                source_url=link.url,
                content=fetcher.fetch(link.url, user_agent),
                retrieved_at_utc=datetime.now(UTC),
                meeting_label=link.meeting_label,
                document_id=link.document_id,
            )
        )
    return responses, links


def write_raw_snapshots(
    responses: list[RawResponse],
    raw_root: Path,
    manifest_root: Path,
    publication_dates_by_document: dict[str, date] | None = None,
) -> pd.DataFrame:
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)
    rows = []
    publication_dates_by_document = publication_dates_by_document or {}
    for response in responses:
        digest = content_hash(response.content)
        basis = f"{response.source_url}|{digest}".encode()
        snapshot_id = "mi5_fomc_" + hashlib.sha256(basis).hexdigest()[:24]
        raw_path = raw_root / f"{snapshot_id}.html"
        raw_path.write_bytes(response.content)
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "source_name": SOURCE_NAME,
                "source_url": response.source_url,
                "retrieved_at_utc": response.retrieved_at_utc,
                "content_sha256": digest,
                "meeting_label": response.meeting_label,
                "document_id": response.document_id,
                "statement_publication_date": publication_dates_by_document.get(
                    str(response.document_id), response.statement_publication_date
                ),
                "raw_path": str(raw_path),
                "publication_permission": "raw_local_only_not_redistributable",
                "availability_evidence_level": AVAILABILITY_EVIDENCE_LEVEL,
            }
        )
    manifest = pd.DataFrame(rows)
    manifest.to_parquet(manifest_root / "fomc_raw_snapshot_manifest.parquet", index=False)
    return manifest


def validate_duplicate_conflicts(parsed: list[ParsedStatement]) -> None:
    by_doc: dict[str, set[str]] = {}
    by_date: dict[date, set[str]] = {}
    for item in parsed:
        by_doc.setdefault(item.link.document_id, set()).add(item.content_sha256)
        if item.publication_date is not None:
            by_date.setdefault(item.publication_date, set()).add(item.content_sha256)
    doc_conflicts = [key for key, values in by_doc.items() if len(values) > 1]
    date_conflicts = [key.isoformat() for key, values in by_date.items() if len(values) > 1]
    if doc_conflicts:
        raise ValueError(
            f"Duplicate document identifiers have conflicting content: {doc_conflicts}"
        )
    if date_conflicts:
        raise ValueError(
            f"Duplicate publication dates map to conflicting statement content: {date_conflicts}"
        )


def first_equity_session_after(
    value: date, market_sessions: list[pd.Timestamp] | None = None
) -> pd.Timestamp:
    sessions = market_sessions
    if sessions is None:
        calendar = mcal.get_calendar("XNYS")
        schedule = calendar.schedule(
            start_date=value.isoformat(),
            end_date=(pd.Timestamp(value) + pd.Timedelta(days=14)).date().isoformat(),
        )
        sessions = [pd.Timestamp(index).normalize() for index in schedule.index]
    target = pd.Timestamp(value).normalize()
    for session in sessions:
        if session > target:
            return session
    raise ValueError(f"No valid U.S. equity session found strictly after {value}")


def decision_timestamp_for_session(session: pd.Timestamp) -> pd.Timestamp:
    local = datetime.combine(session.date(), time(20, 0), tzinfo=ZoneInfo("America/New_York"))
    return pd.Timestamp(local.astimezone(UTC))


EVENT_COLUMNS = [
    "statement_record_id",
    "document_id",
    "source_url",
    "meeting_label",
    "statement_publication_date",
    "publication_date_evidence_source",
    "publication_date_resolution_status",
    "availability_evidence_level",
    "availability_rule_id",
    "effective_session_date",
    "decision_timestamp_utc",
    "document_fetch_status",
    "extraction_status",
    "statement_character_count",
]


def parse_outcome_records(parsed: list[ParsedStatement]) -> list[dict[str, Any]]:
    return [
        {
            "statement_record_id": item.link.statement_record_id,
            "source_url": item.link.url,
            "document_fetch_status": item.document_fetch_status,
            "visible_body_extraction_status": item.extraction_status,
            "publication_date_resolution_status": item.publication_date_resolution_status,
            "statement_publication_date": item.publication_date,
            "publication_date_evidence_source": item.publication_date_evidence_source,
            "exclusion_reason": item.exclusion_reason,
        }
        for item in parsed
    ]


def normalize_events(parsed: list[ParsedStatement]) -> pd.DataFrame:
    rows = []
    for item in parsed:
        if item.exclusion_reason:
            continue
        assert item.publication_date is not None
        effective = first_equity_session_after(item.publication_date)
        rows.append(
            {
                "statement_record_id": item.link.statement_record_id,
                "document_id": item.link.document_id,
                "source_url": item.link.url,
                "meeting_label": item.link.meeting_label,
                "statement_publication_date": item.publication_date,
                "publication_date_evidence_source": item.publication_date_evidence_source,
                "publication_date_resolution_status": item.publication_date_resolution_status,
                "availability_evidence_level": AVAILABILITY_EVIDENCE_LEVEL,
                "availability_rule_id": AVAILABILITY_RULE_ID,
                "effective_session_date": effective,
                "decision_timestamp_utc": decision_timestamp_for_session(effective),
                "document_fetch_status": item.document_fetch_status,
                "extraction_status": item.extraction_status,
                "statement_character_count": len(item.body_text),
            }
        )
    if not rows:
        raise NoUsableFomcStatementsError(parsed)
    return (
        pd.DataFrame(rows, columns=EVENT_COLUMNS)
        .sort_values("statement_publication_date")
        .reset_index(drop=True)
    )


TOKEN_PATTERN = re.compile(r"\b[a-z][a-z0-9']*\b")


def normalized_text(value: str) -> str:
    return normalize_space(re.sub(r"[^a-z0-9']+", " ", value.lower()))


def token_set(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(normalized_text(value)))


def count_phrase(text: str, phrase: str) -> int:
    pattern = r"(?<![a-z0-9])" + re.escape(normalized_text(phrase)) + r"(?![a-z0-9])"
    return len(re.findall(pattern, normalized_text(text)))


def build_lexical_descriptors(
    parsed: list[ParsedStatement],
    lexicons: dict[str, list[str]],
) -> pd.DataFrame:
    usable = sorted(
        [item for item in parsed if not item.exclusion_reason],
        key=lambda item: item.publication_date or date.min,
    )
    rows = []
    prior_tokens: set[str] | None = None
    for item in usable:
        tokens = TOKEN_PATTERN.findall(normalized_text(item.body_text))
        unique_tokens = set(tokens)
        row: dict[str, Any] = {
            "document_id": item.link.document_id,
            "statement_publication_date": item.publication_date,
            "statement_character_count": len(item.body_text),
            "statement_token_count": len(tokens),
            "statement_sentence_count": len(
                [part for part in re.split(r"[.!?]+", item.body_text) if normalize_space(part)]
            ),
        }
        for category, phrases in lexicons.items():
            row[f"{category}_term_count"] = sum(
                count_phrase(item.body_text, phrase) for phrase in phrases
            )
        if prior_tokens is None:
            row["novel_token_ratio_vs_prior_statement"] = np.nan
        else:
            row["novel_token_ratio_vs_prior_statement"] = (
                len(unique_tokens - prior_tokens) / len(unique_tokens) if unique_tokens else np.nan
            )
        prior_tokens = unique_tokens
        rows.append(row)
    return pd.DataFrame(rows)


def instrument_id_for_symbol(symbol: str) -> str:
    return f"mi1_etf_{symbol.lower()}"


def load_asset_family_map(path: Path) -> dict[str, str]:
    config = read_yaml(path)
    return {
        instrument_id_for_symbol(str(item["symbol"])): str(item["asset_family"])
        for item in config["assets"]
    }


def load_mi1_market_inputs(mi1_data_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    bar_path = mi1_data_root / "normalized" / "market_eod_bar.parquet"
    coverage_path = mi1_data_root / "normalized" / "coverage_audit.parquet"
    missing = [str(path) for path in [bar_path, coverage_path] if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required MI-1 inputs: " + ", ".join(missing))
    bars = pd.read_parquet(bar_path)
    coverage = pd.read_parquet(coverage_path)
    bars["session_date"] = pd.to_datetime(bars["session_date"]).dt.normalize()
    return bars, coverage


def eligible_instruments_from_coverage(coverage: pd.DataFrame) -> list[str]:
    if "start_date_eligible" in coverage.columns:
        coverage = coverage[coverage["start_date_eligible"]]
    return sorted(coverage["instrument_id"].dropna().astype(str).unique())


def build_event_window_returns(
    events: pd.DataFrame,
    bars: pd.DataFrame,
    coverage: pd.DataFrame,
    asset_family_by_instrument: dict[str, str],
) -> pd.DataFrame:
    eligible = set(eligible_instruments_from_coverage(coverage))
    bars = bars[bars["instrument_id"].isin(eligible)].copy()
    prices = bars.pivot(
        index="session_date", columns="instrument_id", values="vendor_adjusted_close"
    )
    sessions = list(prices.index.sort_values())
    bil_id = "mi1_etf_bil"
    if bil_id not in prices.columns:
        raise ValueError("BIL adjusted close is required for MI-5 event-window excess returns")
    rows = []
    for event in events.itertuples(index=False):
        if event.effective_session_date not in prices.index:
            continue
        start_index = sessions.index(event.effective_session_date)
        for horizon, offset in HORIZONS.items():
            end_index = start_index + offset
            if end_index >= len(sessions):
                continue
            end_session = sessions[end_index]
            bil_start = prices.at[event.effective_session_date, bil_id]
            bil_end = prices.at[end_session, bil_id]
            if pd.isna(bil_start) or pd.isna(bil_end):
                continue
            bil_return = bil_end / bil_start - 1.0
            for instrument_id in sorted(eligible):
                if instrument_id not in prices.columns:
                    continue
                start_price = prices.at[event.effective_session_date, instrument_id]
                end_price = prices.at[end_session, instrument_id]
                if pd.isna(start_price) or pd.isna(end_price):
                    continue
                asset_return = end_price / start_price - 1.0
                rows.append(
                    {
                        "document_id": event.document_id,
                        "statement_publication_date": event.statement_publication_date,
                        "effective_session_date": event.effective_session_date,
                        "horizon": horizon,
                        "horizon_end_session_date": end_session,
                        "instrument_id": instrument_id,
                        "asset_family": asset_family_by_instrument.get(instrument_id, "unknown"),
                        "event_year": pd.Timestamp(event.statement_publication_date).year,
                        "asset_total_return_h": float(asset_return),
                        "bil_total_return_h": float(bil_return),
                        "bil_excess_return_h": float(asset_return - bil_return),
                    }
                )
    return pd.DataFrame(rows)


def descriptive_return_summary(returns: pd.DataFrame) -> list[dict[str, Any]]:
    if returns.empty:
        return []
    grouped = returns.groupby(["instrument_id", "asset_family", "event_year", "horizon"])
    rows = []
    for keys, group in grouped:
        instrument_id, asset_family, event_year, horizon = keys
        rows.append(
            {
                "instrument_id": instrument_id,
                "asset_family": asset_family,
                "event_year": int(event_year),
                "horizon": horizon,
                "row_count": int(len(group)),
                "mean_bil_excess_return": float(group["bil_excess_return_h"].mean()),
                "median_bil_excess_return": float(group["bil_excess_return_h"].median()),
            }
        )
    return rows


def excluded_reason_counts(parsed: list[ParsedStatement]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in parsed:
        if item.exclusion_reason:
            counts[item.exclusion_reason] = counts.get(item.exclusion_reason, 0) + 1
    return dict(sorted(counts.items()))


def usable_statement_count(
    events: pd.DataFrame, descriptors: pd.DataFrame, returns: pd.DataFrame
) -> int:
    if events.empty or descriptors.empty or returns.empty:
        return 0
    complete_20 = returns[returns["horizon"] == "20_sessions"]
    bil_docs = set(complete_20.loc[complete_20["instrument_id"] == "mi1_etf_bil", "document_id"])
    non_bil_docs = set(
        complete_20.loc[complete_20["instrument_id"] != "mi1_etf_bil", "document_id"]
    )
    descriptor_docs = set(descriptors["document_id"])
    event_docs = set(events["document_id"])
    return len(event_docs & descriptor_docs & bil_docs & non_bil_docs)


def build_reports(
    *,
    config: dict[str, Any],
    parsed: list[ParsedStatement],
    events: pd.DataFrame,
    descriptors: pd.DataFrame,
    returns: pd.DataFrame,
    report_root: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    report_root.mkdir(parents=True, exist_ok=True)
    usable_count = usable_statement_count(events, descriptors, returns)
    minimum_for_model = int(config["standalone_predictive_model_minimum_usable_statement_count"])
    evidence_counts = (
        events["availability_evidence_level"].value_counts().sort_index().to_dict()
        if not events.empty
        else {}
    )
    report = {
        "source_provenance": {
            "source_id": config["source_id"],
            "archive_url": config["archive_url"],
            "event_type": config["event_type"],
        },
        "discovered_event_coverage": {
            "start": None if events.empty else str(events["statement_publication_date"].min()),
            "end": None if events.empty else str(events["statement_publication_date"].max()),
        },
        "statement_count": len(parsed),
        "resolved_publication_date_count": int(len(events)),
        "excluded_event_count": int(sum(1 for item in parsed if item.exclusion_reason)),
        "excluded_event_reasons": excluded_reason_counts(parsed),
        "availability_evidence_level_counts": evidence_counts,
        "event_timing_rule": AVAILABILITY_RULE_ID,
        "lexical_descriptor_coverage": {"row_count": int(len(descriptors))},
        "usable_statement_count": usable_count,
        "standalone_predictive_model_eligible": usable_count >= minimum_for_model,
        "event_window_row_counts": (
            returns["horizon"].value_counts().sort_index().to_dict() if not returns.empty else {}
        ),
        "descriptive_return_summaries": descriptive_return_summary(returns),
        "known_limitations": KNOWN_LIMITATIONS,
    }
    json_path = report_root / "fomc_event_text_foundation.json"
    md_path = report_root / "fomc_event_text_foundation.md"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [
        "# MI-5 FOMC Event/Text Foundation",
        "",
        f"Source: {config['source_id']}",
        (
            f"Coverage: {report['discovered_event_coverage']['start']} through "
            f"{report['discovered_event_coverage']['end']}"
        ),
        f"Statements: {report['statement_count']}",
        f"Resolved publication dates: {report['resolved_publication_date_count']}",
        f"Excluded events: {report['excluded_event_count']}",
        f"Availability rule: {AVAILABILITY_RULE_ID}",
        f"Lexical descriptor rows: {len(descriptors)}",
        f"Usable statements: {usable_count}",
        f"Standalone predictive model eligible: {usable_count >= minimum_for_model}",
        f"Event-window rows: {len(returns)}",
        "",
        "Known limitations:",
        *[f"- {item}" for item in KNOWN_LIMITATIONS],
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path, report


def parse_statement_responses(
    links: list[StatementLink],
    responses: list[RawResponse],
) -> list[ParsedStatement]:
    response_by_url = {response.source_url: response for response in responses}
    parsed = [
        parse_statement(link, response_by_url[link.url].content.decode("utf-8", errors="replace"))
        for link in links
    ]
    validate_duplicate_conflicts(parsed)
    return parsed


def run_mi5_fomc_event_text_foundation(
    *,
    mi1_data_root: Path,
    mi5_data_root: Path,
    report_root: Path,
    config_path: Path = Path("configs/intelligence/event_source_mi5.yaml"),
    universe_config_path: Path = Path("configs/intelligence/universe_mi1.yaml"),
    fetcher: Fetcher | None = None,
) -> Mi5RunResult:
    config = read_yaml(config_path)
    source = fetcher or UrlLibFetcher()
    raw_root = mi5_data_root / "raw"
    manifest_root = mi5_data_root / "manifests"
    normalized_root = mi5_data_root / "normalized"
    normalized_root.mkdir(parents=True, exist_ok=True)
    responses, links = fetch_official_responses(config, source, raw_root, manifest_root)
    parsed = parse_statement_responses(links, responses)
    write_raw_snapshots(
        responses,
        raw_root,
        manifest_root,
        {
            item.link.document_id: item.publication_date
            for item in parsed
            if item.publication_date is not None
        },
    )
    events = normalize_events(parsed)
    descriptors = build_lexical_descriptors(parsed, config["lexicons"])
    bars, coverage = load_mi1_market_inputs(mi1_data_root)
    asset_families = load_asset_family_map(universe_config_path)
    returns = build_event_window_returns(events, bars, coverage, asset_families)
    events.to_parquet(normalized_root / "fomc_statement_event.parquet", index=False)
    descriptors.to_parquet(mi5_data_root / "fomc_lexical_descriptor.parquet", index=False)
    returns.to_parquet(mi5_data_root / "fomc_event_window_return.parquet", index=False)
    md_path, json_path, report = build_reports(
        config=config,
        parsed=parsed,
        events=events,
        descriptors=descriptors,
        returns=returns,
        report_root=report_root,
    )
    output_paths = {
        "raw_root": str(raw_root),
        "fomc_raw_snapshot_manifest": str(manifest_root / "fomc_raw_snapshot_manifest.parquet"),
        "fomc_statement_event": str(normalized_root / "fomc_statement_event.parquet"),
        "fomc_lexical_descriptor": str(mi5_data_root / "fomc_lexical_descriptor.parquet"),
        "fomc_event_window_return": str(mi5_data_root / "fomc_event_window_return.parquet"),
        "report_markdown": str(md_path),
        "report_json": str(json_path),
    }
    return Mi5RunResult(
        mi1_input_provenance={
            "source": "local MI-1 normalized parquet outputs",
            "market_eod_bar": str(mi1_data_root / "normalized" / "market_eod_bar.parquet"),
            "coverage_audit": str(mi1_data_root / "normalized" / "coverage_audit.parquet"),
        },
        archive_source_id=str(config["source_id"]),
        discovered_coverage_start=report["discovered_event_coverage"]["start"],
        discovered_coverage_end=report["discovered_event_coverage"]["end"],
        statement_count=len(parsed),
        resolved_publication_date_count=int(len(events)),
        excluded_event_count=int(sum(1 for item in parsed if item.exclusion_reason)),
        availability_evidence_level=AVAILABILITY_EVIDENCE_LEVEL,
        lexical_descriptor_row_count=int(len(descriptors)),
        usable_statement_count=int(report["usable_statement_count"]),
        standalone_predictive_model_eligible=bool(report["standalone_predictive_model_eligible"]),
        event_window_row_count=int(len(returns)),
        output_paths=output_paths,
    )
