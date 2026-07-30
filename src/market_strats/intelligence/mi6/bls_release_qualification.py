"""MI-6 BLS CPI and Employment Situation source qualification."""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

SOURCE_NAME = "U.S. Bureau of Labor Statistics release HTML"
BLS_ORIGIN = "https://www.bls.gov"
CALENDAR_URL = "https://www.bls.gov/schedule/news_release/"
CPI_TOC_URL = "https://www.bls.gov/news.release/cpi.toc.htm"
EMPSIT_TOC_URL = "https://www.bls.gov/news.release/empsit.toc.htm"
APPROVED_ROOT_URLS = (CALENDAR_URL, CPI_TOC_URL, EMPSIT_TOC_URL)
USER_AGENT = "MarketIntelligenceLab/0.1 research-only contact=local-user"
AVAILABILITY_EVIDENCE_LEVEL = "provider_timestamp_verified"
AVAILABILITY_RULE_ID = "bls_embargo_timestamp_v1"
PARSER_VERSION = "mi6_bls_release_qualification_v1"
RAW_PUBLICATION_PERMISSION = "raw_local_only_not_redistributable"
SOURCE_ACCESS_OK = "ok"
SOURCE_ACCESS_BLOCKED_HTTP_403 = "blocked_http_403"
BLOCKED_HTTP_403_REASONS = [
    "official_source_access_blocked_http_403",
    "no_timestamped_release_corpus_was_retrieved",
    "no_attempt_was_made_to_bypass_or_disguise_the_declared_research_client",
]
KNOWN_LIMITATIONS = [
    "MI-6 qualifies BLS release timestamp evidence only.",
    "It does not establish forecast skill, economic value, portfolio value, or "
    "candidate-signal eligibility.",
    "Daily EOD ETF data cannot measure the immediate 8:30 a.m. reaction precisely.",
    "A later MI-7 forecast test must use explicitly defined next-session or multi-session "
    "outcomes and must not claim intraday event-capture ability.",
]
MANIFEST_COLUMNS = [
    "snapshot_id",
    "source_name",
    "source_url",
    "request_parameters",
    "retrieved_at_utc",
    "content_sha256",
    "parser_version",
    "raw_path",
    "publication_permission",
    "availability_evidence_level",
]
EVENT_COLUMNS = [
    "canonical_url",
    "document_id",
    "release_type",
    "scheduled_timestamp_et",
    "scheduled_timestamp_text",
    "scheduled_timestamp_source_url",
    "document_embargo_timestamp_et",
    "document_embargo_timestamp_text",
    "document_embargo_timestamp_source_url",
    "timestamp_evidence_source",
    "availability_evidence_level",
    "availability_rule_id",
    "timestamp_conflict",
    "usable",
    "exclusion_reason",
    "retrieved_at_utc",
    "snapshot_id",
]

MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|November|December"
)
DATE_PATTERN_TEXT = rf"(?:{MONTH_PATTERN})\s+\d{{1,2}},\s+\d{{4}}"
TIME_PATTERN_TEXT = r"\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.|am|pm|AM|PM)"
ET_PATTERN_TEXT = r"(?:\(?\s*ET\s*\)?|Eastern\s+Time)"
DATE_PATTERN = re.compile(rf"\b{DATE_PATTERN_TEXT}\b")
TIMESTAMP_DATE_FIRST = re.compile(
    rf"(?P<date>{DATE_PATTERN_TEXT}).{{0,160}}?"
    rf"(?P<time>{TIME_PATTERN_TEXT})\s*(?P<tz>{ET_PATTERN_TEXT})",
    re.IGNORECASE | re.DOTALL,
)
TIMESTAMP_TIME_FIRST = re.compile(
    rf"(?P<time>{TIME_PATTERN_TEXT})\s*(?P<tz>{ET_PATTERN_TEXT}).{{0,160}}?"
    rf"(?P<date>{DATE_PATTERN_TEXT})",
    re.IGNORECASE | re.DOTALL,
)


class Fetcher(Protocol):
    def fetch(self, url: str, user_agent: str) -> bytes:
        """Fetch one URL and return response bytes."""


class UrlLibFetcher:
    def fetch(self, url: str, user_agent: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()


def endpoint_path(url: str) -> str:
    return urllib.parse.urlparse(url).path or "/"


def request_stage_for(url: str, depth: int) -> str:
    if depth == 0 and url in APPROVED_ROOT_URLS:
        return "approved_root_fetch"
    return "discovered_same_origin_fetch"


@dataclass(frozen=True)
class SourceAccessDiagnostic:
    http_status_code: int
    endpoint_path: str
    request_stage: str
    source_access_status: str


class BlsHttpRequestError(RuntimeError):
    def __init__(self, diagnostic: SourceAccessDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(
            "BLS HTTP request failed "
            f"http_status_code={diagnostic.http_status_code} "
            f"endpoint_path={diagnostic.endpoint_path} "
            f"request_stage={diagnostic.request_stage} "
            f"source_access_status={diagnostic.source_access_status}"
        )


@dataclass(frozen=True)
class RawResponse:
    source_url: str
    content: bytes
    retrieved_at_utc: datetime
    crawl_depth: int
    snapshot_id: str = ""


@dataclass(frozen=True)
class LinkRecord:
    href: str
    text: str


@dataclass(frozen=True)
class HtmlRow:
    text: str
    links: tuple[LinkRecord, ...]


@dataclass(frozen=True)
class TimestampEvidence:
    original_text: str
    timestamp_et: datetime
    evidence_source: str
    source_url: str

    @property
    def timestamp_iso(self) -> str:
        return self.timestamp_et.isoformat()


@dataclass(frozen=True)
class CrawlResult:
    responses: list[RawResponse]
    scheduled_evidence_by_url: dict[str, list[TimestampEvidence]]
    discovered_url_count: int
    skipped_external_url_count: int
    duplicate_url_count: int
    max_depth_observed: int
    source_access_status: str = SOURCE_ACCESS_OK
    source_access_diagnostic: SourceAccessDiagnostic | None = None


@dataclass(frozen=True)
class Mi6RunResult:
    source_id: str
    source_access_status: str
    source_access_diagnostics: dict[str, Any]
    release_type_counts: dict[str, int]
    usable_timestamped_event_count: int
    earliest_usable_timestamp: str | None
    latest_usable_timestamp: str | None
    qualified_for_later_forecast_research: bool
    qualification_reasons: list[str]
    output_paths: dict[str, str]


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return value


def normalize_space(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def normalize_visible(value: str) -> str:
    return normalize_space(html.unescape(value)).casefold()


def content_hash(payload: bytes) -> str:
    return hashlib.sha256(payload.replace(b"\r\n", b"\n")).hexdigest()


def canonical_bls_url(base_url: str, href: str) -> str | None:
    resolved = urllib.parse.urljoin(base_url, href)
    parsed = urllib.parse.urlparse(resolved)
    if parsed.scheme != "https" or parsed.netloc.lower() != "www.bls.gov":
        return None
    return urllib.parse.urlunparse(parsed._replace(fragment=""))


def is_archive_navigation_url(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    return (
        path.startswith("/schedule/news_release/")
        or "/archives/" in path
        or path.endswith(".toc.htm")
    )


def is_relevant_bls_link(url: str, link_text: str = "") -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "www.bls.gov":
        return False
    path = parsed.path.lower()
    text = normalize_visible(link_text)
    haystack = f"{path} {text}"
    relevant_terms = [
        "cpi",
        "consumer price index",
        "empsit",
        "employment situation",
        "news.release",
        "schedule/news_release",
        "archive",
        "archives",
        "prior year",
        "release calendar",
    ]
    if path.endswith(".pdf"):
        return False
    return any(term in haystack for term in relevant_terms)


def document_id_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    stem = Path(parsed.path).stem
    return stem or hashlib.sha256(url.encode()).hexdigest()[:12]


def parse_et_timestamps(
    text: str, source_url: str, evidence_source: str
) -> list[TimestampEvidence]:
    normalized = normalize_space(text)
    results: list[TimestampEvidence] = []
    seen: set[tuple[str, str]] = set()
    for pattern in [TIMESTAMP_DATE_FIRST, TIMESTAMP_TIME_FIRST]:
        for match in pattern.finditer(normalized):
            date_text = normalize_space(match.group("date"))
            time_text = normalize_space(match.group("time")).lower()
            key = (date_text, time_text)
            if key in seen:
                continue
            seen.add(key)
            parsed = pd.to_datetime(f"{date_text} {time_text}", errors="coerce")
            if pd.isna(parsed):
                continue
            timestamp = (
                pd.Timestamp(parsed).to_pydatetime().replace(tzinfo=ZoneInfo("America/New_York"))
            )
            original_text = normalize_space(match.group(0))
            results.append(
                TimestampEvidence(
                    original_text=original_text,
                    timestamp_et=timestamp,
                    evidence_source=evidence_source,
                    source_url=source_url,
                )
            )
    return results


class BlsHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[LinkRecord] = []
        self.rows: list[HtmlRow] = []
        self.visible_parts: list[str] = []
        self.main_parts: list[str] = []
        self._skip_depth = 0
        self._main_depth = 0
        self._anchor_href: str | None = None
        self._anchor_text: list[str] = []
        self._row_depth = 0
        self._row_text: list[str] = []
        self._row_links: list[LinkRecord] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        attr_text = " ".join([tag, *attr.keys(), *attr.values()]).lower()
        if tag in {"script", "style", "nav", "footer"}:
            self._skip_depth += 1
        if tag in {"main", "article"} or "main" in attr_text or "content" in attr_text:
            self._main_depth += 1
        if tag == "a":
            self._anchor_href = attr.get("href")
            self._anchor_text = []
        if tag == "tr":
            self._row_depth += 1
            if self._row_depth == 1:
                self._row_text = []
                self._row_links = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"main", "article"} and self._main_depth:
            self._main_depth -= 1
        if tag == "a" and self._anchor_href:
            text = normalize_space(" ".join(self._anchor_text))
            record = LinkRecord(href=self._anchor_href, text=text)
            self.links.append(record)
            if self._row_depth:
                self._row_links.append(record)
            self._anchor_href = None
            self._anchor_text = []
        if tag == "tr" and self._row_depth:
            if self._row_depth == 1:
                self.rows.append(
                    HtmlRow(
                        text=normalize_space(" ".join(self._row_text)),
                        links=tuple(self._row_links),
                    )
                )
            self._row_depth -= 1

    def handle_data(self, data: str) -> None:
        text = normalize_space(data)
        if not text:
            return
        if self._anchor_href is not None:
            self._anchor_text.append(text)
        if self._row_depth:
            self._row_text.append(text)
        if self._skip_depth == 0:
            self.visible_parts.append(text)
            if self._main_depth > 0:
                self.main_parts.append(text)

    @property
    def visible_text(self) -> str:
        return normalize_space(" ".join(self.visible_parts))

    @property
    def main_text(self) -> str:
        text = normalize_space(" ".join(self.main_parts))
        return text or self.visible_text


def parse_html(content: bytes) -> BlsHtmlParser:
    parser = BlsHtmlParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    return parser


def release_type_from_text(text: str) -> str | None:
    normalized = normalize_visible(text)
    if "employment situation" in normalized:
        return "employment_situation"
    if "consumer price index" in normalized or re.search(r"\bcpi\b", normalized):
        return "cpi"
    return None


def extract_schedule_evidence(
    parser: BlsHtmlParser,
    page_url: str,
) -> dict[str, list[TimestampEvidence]]:
    evidence: dict[str, list[TimestampEvidence]] = {}
    for row in parser.rows:
        if release_type_from_text(row.text) is None:
            continue
        timestamps = parse_et_timestamps(row.text, page_url, "schedule")
        if not timestamps:
            continue
        for link in row.links:
            url = canonical_bls_url(page_url, link.href)
            if url is None or not is_relevant_bls_link(url, link.text):
                continue
            evidence.setdefault(url, []).extend(timestamps)
    return evidence


def should_fetch_child(
    parent_url: str,
    child_url: str,
    next_depth: int,
    configured_maximum_depth: int,
) -> bool:
    if next_depth <= configured_maximum_depth:
        return True
    if next_depth == configured_maximum_depth + 1:
        return is_archive_navigation_url(parent_url) or is_archive_navigation_url(child_url)
    return False


def crawl_bls_sources(
    *,
    config: dict[str, Any],
    fetcher: Fetcher,
    raw_root: Path,
    manifest_root: Path,
) -> CrawlResult:
    roots = [str(config["calendar_url"]), CPI_TOC_URL, EMPSIT_TOC_URL]
    maximum_depth = int(config["maximum_crawl_depth"])
    queue: deque[tuple[str, int]] = deque((url, 0) for url in roots)
    queued: set[str] = set(roots)
    fetched: set[str] = set()
    responses: list[RawResponse] = []
    schedule_evidence: dict[str, list[TimestampEvidence]] = {}
    skipped_external = 0
    duplicate_count = 0
    max_depth_observed = 0

    while queue:
        url, depth = queue.popleft()
        if url in fetched:
            duplicate_count += 1
            continue
        fetched.add(url)
        max_depth_observed = max(max_depth_observed, depth)
        try:
            content = fetcher.fetch(url, USER_AGENT)
        except urllib.error.HTTPError as error:
            diagnostic = SourceAccessDiagnostic(
                http_status_code=int(error.code),
                endpoint_path=endpoint_path(url),
                request_stage=request_stage_for(url, depth),
                source_access_status=(
                    SOURCE_ACCESS_BLOCKED_HTTP_403
                    if int(error.code) == 403
                    else "failed_http_error"
                ),
            )
            if int(error.code) == 403:
                write_raw_snapshots(responses, raw_root, manifest_root)
                return CrawlResult(
                    responses=responses,
                    scheduled_evidence_by_url=schedule_evidence,
                    discovered_url_count=len(queued),
                    skipped_external_url_count=skipped_external,
                    duplicate_url_count=duplicate_count,
                    max_depth_observed=max_depth_observed,
                    source_access_status=SOURCE_ACCESS_BLOCKED_HTTP_403,
                    source_access_diagnostic=diagnostic,
                )
            raise BlsHttpRequestError(diagnostic) from error
        response = RawResponse(
            source_url=url,
            content=content,
            retrieved_at_utc=datetime.now(UTC),
            crawl_depth=depth,
        )
        responses.append(response)
        write_raw_snapshots([response], raw_root, manifest_root)
        parser = parse_html(content)
        for evidence_url, values in extract_schedule_evidence(parser, url).items():
            schedule_evidence.setdefault(evidence_url, []).extend(values)
        for link in parser.links:
            child = canonical_bls_url(url, link.href)
            if child is None:
                skipped_external += 1
                continue
            if not is_relevant_bls_link(child, link.text):
                continue
            next_depth = depth + 1
            if not should_fetch_child(url, child, next_depth, maximum_depth):
                continue
            if child in queued:
                duplicate_count += 1
                continue
            queued.add(child)
            queue.append((child, next_depth))

    write_raw_snapshots(responses, raw_root, manifest_root)
    return CrawlResult(
        responses=responses,
        scheduled_evidence_by_url=schedule_evidence,
        discovered_url_count=len(queued),
        skipped_external_url_count=skipped_external,
        duplicate_url_count=duplicate_count,
        max_depth_observed=max_depth_observed,
    )


def write_raw_snapshots(
    responses: list[RawResponse],
    raw_root: Path,
    manifest_root: Path,
) -> pd.DataFrame:
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for response in responses:
        digest = content_hash(response.content)
        basis = f"{response.source_url}|{digest}".encode()
        snapshot_id = "mi6_bls_" + hashlib.sha256(basis).hexdigest()[:24]
        raw_path = raw_root / f"{snapshot_id}.html"
        raw_path.write_bytes(response.content)
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "source_name": SOURCE_NAME,
                "source_url": response.source_url,
                "request_parameters": {"crawl_depth": response.crawl_depth},
                "retrieved_at_utc": response.retrieved_at_utc,
                "content_sha256": digest,
                "parser_version": PARSER_VERSION,
                "raw_path": str(raw_path),
                "publication_permission": RAW_PUBLICATION_PERMISSION,
                "availability_evidence_level": "unverified",
            }
        )
    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    manifest.to_parquet(manifest_root / "bls_raw_snapshot_manifest.parquet", index=False)
    return manifest


def schedule_evidence_for_url(
    url: str,
    scheduled_evidence_by_url: dict[str, list[TimestampEvidence]],
) -> tuple[TimestampEvidence | None, bool]:
    values = scheduled_evidence_by_url.get(url, [])
    if not values:
        return None, False
    unique = {value.timestamp_iso: value for value in values}
    if len(unique) > 1:
        return None, True
    return next(iter(unique.values())), False


def parse_release_event(
    response: RawResponse,
    scheduled_evidence_by_url: dict[str, list[TimestampEvidence]],
) -> dict[str, Any] | None:
    parser = parse_html(response.content)
    text = parser.main_text
    release_type = release_type_from_text(text)
    document_timestamps = parse_et_timestamps(text, response.source_url, "release_document")
    path = urllib.parse.urlparse(response.source_url).path.lower()
    likely_release_path = "/news.release/" in path and (
        "cpi" in path or "empsit" in path or "archives" in path
    )
    if release_type is None and not document_timestamps and not likely_release_path:
        return None

    scheduled, schedule_conflict = schedule_evidence_for_url(
        response.source_url, scheduled_evidence_by_url
    )
    unique_document_timestamps = {item.timestamp_iso: item for item in document_timestamps}
    document_conflict = len(unique_document_timestamps) > 1
    document = (
        next(iter(unique_document_timestamps.values()))
        if len(unique_document_timestamps) == 1
        else None
    )
    timestamp_conflict = False
    if scheduled is not None and document is not None:
        timestamp_conflict = scheduled.timestamp_iso != document.timestamp_iso
    conflict = schedule_conflict or document_conflict or timestamp_conflict
    exclusion_reasons: list[str] = []
    if release_type is None:
        exclusion_reasons.append("release_type_not_identified")
    if document is None:
        if document_conflict:
            exclusion_reasons.append("conflicting_document_embargo_timestamps")
        else:
            exclusion_reasons.append("missing_document_embargo_timestamp")
    if schedule_conflict:
        exclusion_reasons.append("conflicting_scheduled_timestamps")
    if timestamp_conflict:
        exclusion_reasons.append("scheduled_document_timestamp_conflict")
    if conflict and "timestamp_conflict" not in exclusion_reasons:
        exclusion_reasons.append("timestamp_conflict")
    usable = not exclusion_reasons
    return {
        "canonical_url": response.source_url,
        "document_id": document_id_from_url(response.source_url),
        "release_type": release_type,
        "scheduled_timestamp_et": None if scheduled is None else scheduled.timestamp_iso,
        "scheduled_timestamp_text": None if scheduled is None else scheduled.original_text,
        "scheduled_timestamp_source_url": None if scheduled is None else scheduled.source_url,
        "document_embargo_timestamp_et": None if document is None else document.timestamp_iso,
        "document_embargo_timestamp_text": None if document is None else document.original_text,
        "document_embargo_timestamp_source_url": (
            None if document is None else document.source_url
        ),
        "timestamp_evidence_source": None if document is None else document.evidence_source,
        "availability_evidence_level": AVAILABILITY_EVIDENCE_LEVEL if usable else "unverified",
        "availability_rule_id": AVAILABILITY_RULE_ID if usable else "",
        "timestamp_conflict": bool(conflict),
        "usable": bool(usable),
        "exclusion_reason": ";".join(exclusion_reasons),
        "retrieved_at_utc": response.retrieved_at_utc,
        "snapshot_id": "",
    }


def attach_snapshot_ids(events: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    snapshot_by_url = (
        manifest.drop_duplicates("source_url").set_index("source_url")["snapshot_id"].to_dict()
    )
    events = events.copy()
    events["snapshot_id"] = events["canonical_url"].map(snapshot_by_url).fillna("")
    return events


def build_release_events(crawl: CrawlResult, manifest_root: Path) -> pd.DataFrame:
    rows = []
    for response in crawl.responses:
        row = parse_release_event(response, crawl.scheduled_evidence_by_url)
        if row is not None:
            rows.append(row)
    events = pd.DataFrame(rows, columns=EVENT_COLUMNS)
    manifest = pd.read_parquet(manifest_root / "bls_raw_snapshot_manifest.parquet")
    events = attach_snapshot_ids(events, manifest)
    if not events.empty:
        events = events.drop_duplicates("canonical_url").sort_values("canonical_url")
    return events.reset_index(drop=True)


def empty_release_events() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def qualify_source(events: pd.DataFrame, config: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    minimum = int(config["minimum_historical_event_count"])
    usable = events[events["usable"]] if not events.empty else events
    usable_count = int(len(usable))
    if usable_count < minimum:
        reasons.append(f"usable_timestamped_event_count_below_minimum:{usable_count}<{minimum}")
    for release_type in config["release_types"]:
        type_count = int(len(usable[usable["release_type"] == release_type]))
        if type_count < 24:
            reasons.append(f"{release_type}_usable_event_count_below_24:{type_count}<24")
    if not usable.empty:
        bad_evidence = usable[usable["availability_evidence_level"] != AVAILABILITY_EVIDENCE_LEVEL]
        if not bad_evidence.empty:
            reasons.append("usable_events_without_provider_timestamp_verified_evidence")
    conflict_count = int(events["timestamp_conflict"].sum()) if not events.empty else 0
    if conflict_count:
        reasons.append(f"timestamp_conflict_count:{conflict_count}")
    if not reasons:
        reasons.append("qualified")
    return reasons == ["qualified"], reasons


def build_report(
    *,
    config: dict[str, Any],
    crawl: CrawlResult,
    events: pd.DataFrame,
    report_root: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    report_root.mkdir(parents=True, exist_ok=True)
    usable = events[events["usable"]] if not events.empty else events
    access_blocked = crawl.source_access_status == SOURCE_ACCESS_BLOCKED_HTTP_403
    if access_blocked:
        qualified = False
        reasons = list(BLOCKED_HTTP_403_REASONS)
    else:
        qualified, reasons = qualify_source(events, config)
    release_type_counts = (
        usable["release_type"].value_counts().sort_index().astype(int).to_dict()
        if not usable.empty
        else {}
    )
    if access_blocked:
        release_type_counts = {str(release_type): 0 for release_type in config["release_types"]}
    evidence_counts = (
        events["availability_evidence_level"].value_counts().sort_index().astype(int).to_dict()
        if not events.empty
        else {}
    )
    earliest = None if usable.empty else str(usable["document_embargo_timestamp_et"].min())
    latest = None if usable.empty else str(usable["document_embargo_timestamp_et"].max())
    conflict_count = int(events["timestamp_conflict"].sum()) if not events.empty else 0
    duplicate_url_count = int(crawl.duplicate_url_count)
    source_access_diagnostic = (
        {}
        if crawl.source_access_diagnostic is None
        else {
            "http_status_code": crawl.source_access_diagnostic.http_status_code,
            "endpoint_path": crawl.source_access_diagnostic.endpoint_path,
            "request_stage": crawl.source_access_diagnostic.request_stage,
            "source_access_status": crawl.source_access_diagnostic.source_access_status,
        }
    )
    report = {
        "source_id": str(config["source_id"]),
        "source_provenance": {
            "source_id": config["source_id"],
            "calendar_url": config["calendar_url"],
            "approved_release_roots": [CPI_TOC_URL, EMPSIT_TOC_URL],
            "source_name": SOURCE_NAME,
            "user_agent": USER_AGENT,
        },
        "source_access_status": crawl.source_access_status,
        "source_access_diagnostics": source_access_diagnostic,
        "crawl_coverage": {
            "fetched_page_count": len(crawl.responses),
            "discovered_url_count": crawl.discovered_url_count,
            "skipped_external_url_count": crawl.skipped_external_url_count,
            "duplicate_url_count": duplicate_url_count,
            "max_depth_observed": crawl.max_depth_observed,
            "configured_maximum_crawl_depth": int(config["maximum_crawl_depth"]),
            "archive_navigation_maximum_crawl_depth": int(config["maximum_crawl_depth"]) + 1,
        },
        "release_type_counts": release_type_counts,
        "usable_timestamped_event_count": int(len(usable)),
        "timestamp_evidence_counts": evidence_counts,
        "earliest_usable_timestamp": earliest,
        "latest_usable_timestamp": latest,
        "duplicate_conflict_counts": {
            "duplicate_url_count": duplicate_url_count,
            "timestamp_conflict_count": conflict_count,
        },
        "qualified_for_later_forecast_research": qualified,
        "qualification_reasons": reasons,
        "known_limitations": KNOWN_LIMITATIONS,
    }
    json_path = report_root / "bls_release_source_qualification.json"
    md_path = report_root / "bls_release_source_qualification.md"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [
        "# MI-6 BLS Release Source Qualification",
        "",
        f"Source: {config['source_id']}",
        f"Source access status: {crawl.source_access_status}",
        f"Fetched pages: {len(crawl.responses)}",
        f"Usable timestamped events: {len(usable)}",
        f"Earliest usable timestamp: {earliest}",
        f"Latest usable timestamp: {latest}",
        f"Qualified for later forecast research: {qualified}",
        "Qualification reasons:",
        *[f"- {reason}" for reason in reasons],
    ]
    if source_access_diagnostic:
        lines.extend(
            [
                "",
                "Source access diagnostics:",
                f"- http_status_code: {source_access_diagnostic['http_status_code']}",
                f"- endpoint_path: {source_access_diagnostic['endpoint_path']}",
                f"- request_stage: {source_access_diagnostic['request_stage']}",
                f"- source_access_status: {source_access_diagnostic['source_access_status']}",
            ]
        )
    lines.extend(
        [
            "",
            "Known limitations:",
            *[f"- {item}" for item in KNOWN_LIMITATIONS],
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path, report


def run_mi6_bls_release_qualification(
    *,
    mi6_data_root: Path,
    report_root: Path,
    config_path: Path = Path("configs/intelligence/event_source_mi6.yaml"),
    fetcher: Fetcher | None = None,
) -> Mi6RunResult:
    config = read_yaml(config_path)
    raw_root = mi6_data_root / "raw"
    manifest_root = mi6_data_root / "manifests"
    normalized_root = mi6_data_root / "normalized"
    normalized_root.mkdir(parents=True, exist_ok=True)
    source = fetcher or UrlLibFetcher()
    crawl = crawl_bls_sources(
        config=config,
        fetcher=source,
        raw_root=raw_root,
        manifest_root=manifest_root,
    )
    events = (
        empty_release_events()
        if crawl.source_access_status == SOURCE_ACCESS_BLOCKED_HTTP_403
        else build_release_events(crawl, manifest_root)
    )
    event_path = normalized_root / "bls_release_event.parquet"
    events.to_parquet(event_path, index=False)
    md_path, json_path, report = build_report(
        config=config,
        crawl=crawl,
        events=events,
        report_root=report_root,
    )
    output_paths = {
        "raw_root": str(raw_root),
        "bls_raw_snapshot_manifest": str(manifest_root / "bls_raw_snapshot_manifest.parquet"),
        "bls_release_event": str(event_path),
        "report_markdown": str(md_path),
        "report_json": str(json_path),
    }
    return Mi6RunResult(
        source_id=str(config["source_id"]),
        source_access_status=str(report["source_access_status"]),
        source_access_diagnostics=dict(report["source_access_diagnostics"]),
        release_type_counts={
            str(key): int(value) for key, value in report["release_type_counts"].items()
        },
        usable_timestamped_event_count=int(report["usable_timestamped_event_count"]),
        earliest_usable_timestamp=report["earliest_usable_timestamp"],
        latest_usable_timestamp=report["latest_usable_timestamp"],
        qualified_for_later_forecast_research=bool(report["qualified_for_later_forecast_research"]),
        qualification_reasons=list(report["qualification_reasons"]),
        output_paths=output_paths,
    )
