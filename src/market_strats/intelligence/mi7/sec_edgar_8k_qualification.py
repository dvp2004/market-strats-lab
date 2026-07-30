"""MI-7 SEC EDGAR Form 8-K acceptance-time source qualification."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

SOURCE_NAME = "SEC EDGAR submissions JSON"
SEC_SUBMISSIONS_BASE_URL = "https://data.sec.gov/submissions/"
USER_AGENT_ENV_VAR = "MI_LAB_SEC_USER_AGENT"
PARSER_VERSION = "mi7_sec_edgar_8k_acceptance_qualification_v1"
RAW_PUBLICATION_PERMISSION = "raw_local_only_not_redistributable"
SOURCE_ACCESS_AVAILABLE = "available"
SOURCE_ACCESS_BLOCKED_HTTP_403 = "blocked_http_403"
SOURCE_ACCESS_RATE_LIMITED_HTTP_429 = "rate_limited_http_429"
CONTENT_AVAILABILITY_EVIDENCE_LEVEL = "contractual_assumption"
AVAILABILITY_RULE_ID = "sec_edgar_acceptance_next_eligible_session_close_v1"
TIMESTAMP_EVIDENCE_SOURCE = "sec_edgar_acceptance_timestamp"
ACCEPTANCE_TIMEZONE = "America/New_York"
RETAINED_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$"
)
KNOWN_LIMITATIONS = [
    "No filing text was retrieved or analyzed.",
    "Acceptance timestamps do not prove when filing content became available on sec.gov.",
    "The source is not approved for same-session or intraday event studies.",
    "MI-7 does not establish forecast skill, economic value, portfolio value, or "
    "candidate-signal eligibility.",
    "Without an individual-equity price panel or approved issuer-to-ETF exposure mapping, MI-7 "
    "ends as a reusable data capability only.",
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
    "issuer_id",
    "issuer_cik",
    "accession_number",
    "form_type",
    "filing_date",
    "acceptance_timestamp_raw",
    "acceptance_timestamp",
    "acceptance_timestamp_timezone",
    "timestamp_evidence_source",
    "content_availability_evidence_level",
    "availability_rule_id",
    "source_url",
    "retrieved_at_utc",
    "snapshot_id",
]
EXCLUSION_ACCOUNTING_FIELDS = [
    "records_seen",
    "records_with_exact_8k_form",
    "records_after_history_start_date",
    "records_missing_accession_number",
    "records_missing_acceptance_timestamp",
    "records_unrecognized_acceptance_timestamp_format",
    "records_missing_timestamp_timezone",
    "records_filing_date_inconsistent",
    "records_deduplicated",
    "records_retained_as_eligible_8k",
]
CONTROLLED_ACCESS_REASONS = {
    SOURCE_ACCESS_BLOCKED_HTTP_403: [
        "official_source_access_blocked_http_403",
        "no_sec_8k_acceptance_corpus_was_retrieved",
        "no_attempt_was_made_to_bypass_or_disguise_the_declared_research_client",
    ],
    SOURCE_ACCESS_RATE_LIMITED_HTTP_429: [
        "official_source_rate_limited_http_429",
        "no_sec_8k_acceptance_corpus_was_retrieved",
        "no_attempt_was_made_to_bypass_or_disguise_the_declared_research_client",
    ],
}


class Fetcher(Protocol):
    def fetch(self, url: str, user_agent: str) -> bytes:
        """Fetch one URL and return response bytes."""


class UrlLibFetcher:
    def fetch(self, url: str, user_agent: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()


class Mi7ConfigurationError(ValueError):
    """Raised before network access when MI-7 configuration is invalid."""


@dataclass(frozen=True)
class SourceAccessDiagnostic:
    http_status_code: int
    endpoint_path: str
    request_stage: str
    source_access_status: str


class SecHttpRequestError(RuntimeError):
    def __init__(self, diagnostic: SourceAccessDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(
            "SEC submissions request failed "
            f"http_status_code={diagnostic.http_status_code} "
            f"endpoint_path={diagnostic.endpoint_path} "
            f"request_stage={diagnostic.request_stage} "
            f"source_access_status={diagnostic.source_access_status}"
        )


class AcceptanceTimestampConflictError(ValueError):
    def __init__(self, conflicts: list[dict[str, Any]]) -> None:
        self.conflicts = conflicts
        samples = [f"{item['issuer_id']}:{item['accession_number']}" for item in conflicts[:10]]
        super().__init__(
            "Conflicting SEC acceptance timestamps for issuer/accession pairs "
            f"conflict_count={len(conflicts)} sample_pairs={samples}"
        )


class AcceptanceTimestampNormalizationError(ValueError):
    def __init__(self, affected_event_ids: list[str], total_count: int) -> None:
        self.affected_event_ids = affected_event_ids
        self.total_count = total_count
        super().__init__(
            "Retained SEC acceptance timestamps failed canonical timezone normalization "
            f"failure_count={total_count} affected_event_ids={affected_event_ids[:10]}"
        )


@dataclass(frozen=True)
class RawResponse:
    source_url: str
    content: bytes
    retrieved_at_utc: datetime
    issuer_id: str
    issuer_cik: str
    request_stage: str


@dataclass(frozen=True)
class CrawlResult:
    responses: list[RawResponse]
    fetched_issuer_ids: set[str]
    source_access_status: str = SOURCE_ACCESS_AVAILABLE
    source_access_diagnostic: SourceAccessDiagnostic | None = None


@dataclass(frozen=True)
class Mi7RunResult:
    source_id: str
    source_access_status: str
    source_access_diagnostics: dict[str, Any]
    configured_issuer_count: int
    eligible_8k_event_count: int
    earliest_acceptance_timestamp: str | None
    latest_acceptance_timestamp: str | None
    qualified_for_later_next_session_event_research: bool
    qualification_reasons: list[str]
    output_paths: dict[str, str]


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return value


def load_sec_user_agent(env: dict[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    value = source.get(USER_AGENT_ENV_VAR, "").strip()
    if not value:
        raise Mi7ConfigurationError(
            f"{USER_AGENT_ENV_VAR} must be set before MI-7 SEC EDGAR access"
        )
    return value


def normalize_cik(value: str) -> str:
    digits = "".join(char for char in str(value) if char.isdigit())
    return digits.zfill(10)


def canonical_issuer_url(base_url: str, cik: str) -> str:
    if base_url != SEC_SUBMISSIONS_BASE_URL:
        raise ValueError("MI-7 SEC submission_base_url must be the official SEC submissions API")
    return urllib.parse.urljoin(base_url, f"CIK{normalize_cik(cik)}.json")


def resolve_supplemental_url(base_url: str, relative_name: str) -> str | None:
    parsed_name = urllib.parse.urlparse(str(relative_name))
    if parsed_name.scheme or parsed_name.netloc or str(relative_name).startswith("/"):
        return None
    resolved = urllib.parse.urljoin(base_url, str(relative_name))
    parsed = urllib.parse.urlparse(resolved)
    base = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != base.netloc.lower():
        return None
    if not parsed.path.startswith(base.path):
        return None
    return urllib.parse.urlunparse(parsed._replace(fragment=""))


def endpoint_path(url: str) -> str:
    return urllib.parse.urlparse(url).path or "/"


def source_access_status_for_http(code: int) -> str:
    if code == 403:
        return SOURCE_ACCESS_BLOCKED_HTTP_403
    if code == 429:
        return SOURCE_ACCESS_RATE_LIMITED_HTTP_429
    return "failed_http_error"


class RequestPacer:
    def __init__(
        self,
        *,
        max_requests_per_second: float,
        time_fn: Any = time.monotonic,
        sleep_fn: Any = time.sleep,
    ) -> None:
        self.minimum_interval = 1.0 / max_requests_per_second
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn
        self.last_request_at: float | None = None

    def wait(self) -> None:
        now = float(self.time_fn())
        if self.last_request_at is not None:
            elapsed = now - self.last_request_at
            if elapsed < self.minimum_interval:
                self.sleep_fn(self.minimum_interval - elapsed)
                now = float(self.time_fn())
        self.last_request_at = now


def fetch_json(
    *,
    url: str,
    issuer_id: str,
    issuer_cik: str,
    request_stage: str,
    user_agent: str,
    fetcher: Fetcher,
    pacer: RequestPacer,
) -> RawResponse:
    pacer.wait()
    try:
        content = fetcher.fetch(url, user_agent)
    except urllib.error.HTTPError as error:
        status = source_access_status_for_http(int(error.code))
        diagnostic = SourceAccessDiagnostic(
            http_status_code=int(error.code),
            endpoint_path=endpoint_path(url),
            request_stage=request_stage,
            source_access_status=status,
        )
        raise SecHttpRequestError(diagnostic) from error
    return RawResponse(
        source_url=url,
        content=content,
        retrieved_at_utc=datetime.now(UTC),
        issuer_id=issuer_id,
        issuer_cik=issuer_cik,
        request_stage=request_stage,
    )


def content_hash(payload: bytes) -> str:
    return hashlib.sha256(payload.replace(b"\r\n", b"\n")).hexdigest()


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
        snapshot_id = "mi7_sec_" + hashlib.sha256(basis).hexdigest()[:24]
        raw_path = raw_root / f"{snapshot_id}.json"
        raw_path.write_bytes(response.content)
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "source_name": SOURCE_NAME,
                "source_url": response.source_url,
                "request_parameters": {
                    "issuer_id": response.issuer_id,
                    "issuer_cik": response.issuer_cik,
                    "request_stage": response.request_stage,
                },
                "retrieved_at_utc": response.retrieved_at_utc,
                "content_sha256": digest,
                "parser_version": PARSER_VERSION,
                "raw_path": str(raw_path),
                "publication_permission": RAW_PUBLICATION_PERMISSION,
                "availability_evidence_level": "provider_timestamp_verified_metadata_only",
            }
        )
    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    manifest.to_parquet(manifest_root / "sec_edgar_raw_snapshot_manifest.parquet", index=False)
    return manifest


def crawl_sec_submissions(
    *,
    config: dict[str, Any],
    user_agent: str,
    fetcher: Fetcher,
    raw_root: Path,
    manifest_root: Path,
    time_fn: Any = time.monotonic,
    sleep_fn: Any = time.sleep,
) -> CrawlResult:
    responses: list[RawResponse] = []
    fetched_issuers: set[str] = set()
    pacer = RequestPacer(
        max_requests_per_second=float(config["max_requests_per_second"]),
        time_fn=time_fn,
        sleep_fn=sleep_fn,
    )
    for issuer in config["issuers"]:
        issuer_id = str(issuer["issuer_id"])
        issuer_cik = normalize_cik(str(issuer["cik"]))
        root_url = canonical_issuer_url(str(config["submission_base_url"]), issuer_cik)
        try:
            root_response = fetch_json(
                url=root_url,
                issuer_id=issuer_id,
                issuer_cik=issuer_cik,
                request_stage="canonical_submissions_fetch",
                user_agent=user_agent,
                fetcher=fetcher,
                pacer=pacer,
            )
        except SecHttpRequestError as error:
            if error.diagnostic.http_status_code in {403, 429}:
                write_raw_snapshots(responses, raw_root, manifest_root)
                return CrawlResult(
                    responses=responses,
                    fetched_issuer_ids=fetched_issuers,
                    source_access_status=error.diagnostic.source_access_status,
                    source_access_diagnostic=error.diagnostic,
                )
            raise
        responses.append(root_response)
        fetched_issuers.add(issuer_id)
        write_raw_snapshots([root_response], raw_root, manifest_root)
        payload = json.loads(root_response.content.decode("utf-8"))
        for file_record in payload.get("filings", {}).get("files", []) or []:
            supplemental_name = file_record.get("name")
            if not supplemental_name:
                continue
            supplemental_url = resolve_supplemental_url(
                str(config["submission_base_url"]), str(supplemental_name)
            )
            if supplemental_url is None:
                continue
            try:
                supplemental_response = fetch_json(
                    url=supplemental_url,
                    issuer_id=issuer_id,
                    issuer_cik=issuer_cik,
                    request_stage="explicit_supplemental_submissions_fetch",
                    user_agent=user_agent,
                    fetcher=fetcher,
                    pacer=pacer,
                )
            except SecHttpRequestError as error:
                if error.diagnostic.http_status_code in {403, 429}:
                    write_raw_snapshots(responses, raw_root, manifest_root)
                    return CrawlResult(
                        responses=responses,
                        fetched_issuer_ids=fetched_issuers,
                        source_access_status=error.diagnostic.source_access_status,
                        source_access_diagnostic=error.diagnostic,
                    )
                raise
            responses.append(supplemental_response)
            write_raw_snapshots([supplemental_response], raw_root, manifest_root)
    write_raw_snapshots(responses, raw_root, manifest_root)
    return CrawlResult(responses=responses, fetched_issuer_ids=fetched_issuers)


def parse_acceptance_timestamp_with_reason(value: Any) -> tuple[datetime | None, str]:
    text = str(value or "")
    if not text:
        return None, "records_missing_acceptance_timestamp"
    if len(text) != 14 or not text.isdigit():
        if text.endswith("Z") and "T" in text:
            iso_text = text[:-1] + "+00:00"
        else:
            iso_text = text
        if "T" in iso_text and (
            iso_text.endswith("+00:00")
            or iso_text.endswith("-00:00")
            or "+" in iso_text[10:]
            or "-" in iso_text[10:]
        ):
            try:
                parsed = datetime.fromisoformat(iso_text)
            except ValueError:
                return None, "records_unrecognized_acceptance_timestamp_format"
            if parsed.tzinfo is None:
                return None, "records_missing_timestamp_timezone"
            return parsed.astimezone(ZoneInfo(ACCEPTANCE_TIMEZONE)), ""
        if "T" in text:
            return None, "records_missing_timestamp_timezone"
        return None, "records_unrecognized_acceptance_timestamp_format"
    try:
        parsed = datetime.strptime(text, "%Y%m%d%H%M%S")
    except ValueError:
        return None, "records_unrecognized_acceptance_timestamp_format"
    return parsed.replace(tzinfo=ZoneInfo(ACCEPTANCE_TIMEZONE)), ""


def parse_acceptance_timestamp(value: Any) -> datetime | None:
    timestamp, _reason = parse_acceptance_timestamp_with_reason(value)
    return timestamp


def normalize_acceptance_timestamps_ny(events: pd.DataFrame) -> pd.Series:
    malformed = events[
        ~events["acceptance_timestamp"]
        .astype(str)
        .map(lambda value: bool(RETAINED_TIMESTAMP_PATTERN.match(value)))
    ]
    if not malformed.empty:
        affected = [
            f"{row.issuer_id}:{row.accession_number}"
            for row in malformed.head(10).itertuples(index=False)
        ]
        raise AcceptanceTimestampNormalizationError(affected, len(malformed))
    try:
        timestamps_utc = pd.to_datetime(
            events["acceptance_timestamp"],
            utc=True,
            errors="raise",
        )
        return timestamps_utc.dt.tz_convert(ACCEPTANCE_TIMEZONE)
    except Exception as error:
        affected = [
            f"{row.issuer_id}:{row.accession_number}"
            for row in events.itertuples(index=False)
            if pd.isna(getattr(row, "acceptance_timestamp", None))
        ][:10]
        if not affected:
            affected = [
                f"{row.issuer_id}:{row.accession_number}"
                for row in events.head(10).itertuples(index=False)
            ]
        raise AcceptanceTimestampNormalizationError(affected, len(events)) from error


def records_from_array_mapping(values_by_field: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(values_by_field, dict):
        return []
    max_len = max(
        (len(value) for value in values_by_field.values() if isinstance(value, list)),
        default=0,
    )
    rows = []
    for index in range(max_len):
        row = {}
        for key, values in values_by_field.items():
            if isinstance(values, list) and index < len(values):
                row[key] = values[index]
        rows.append(row)
    return rows


def recent_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recent = payload.get("filings", {}).get("recent", {})
    if isinstance(recent, dict) and recent:
        return records_from_array_mapping(recent)
    if isinstance(payload.get("accessionNumber"), list):
        return records_from_array_mapping(payload)
    return []


def timestamp_consistent_with_filing_date(timestamp: datetime, filing_date: date) -> bool:
    return timestamp.date() == filing_date


def parse_response_events(
    response: RawResponse,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    payload = json.loads(response.content.decode("utf-8"))
    configured_cik = normalize_cik(response.issuer_cik)
    payload_cik = normalize_cik(str(payload.get("cik", configured_cik)))
    counters = {field: 0 for field in EXCLUSION_ACCOUNTING_FIELDS}
    counters["records_cik_mismatch"] = 0
    rows: list[dict[str, Any]] = []
    history_start = date.fromisoformat(str(config["history_start_date"]))
    for record in recent_records(payload):
        counters["records_seen"] += 1
        if payload_cik != configured_cik:
            counters["records_cik_mismatch"] += 1
            continue
        form_type = str(record.get("form", ""))
        if form_type != "8-K":
            continue
        counters["records_with_exact_8k_form"] += 1
        filing_date_text = str(record.get("filingDate", ""))
        try:
            filing_date = date.fromisoformat(filing_date_text)
        except ValueError:
            continue
        if filing_date < history_start:
            continue
        counters["records_after_history_start_date"] += 1
        accession_number = str(record.get("accessionNumber", "")).strip()
        if not accession_number:
            counters["records_missing_accession_number"] += 1
            continue
        raw_timestamp = record.get("acceptanceDateTime")
        timestamp, timestamp_exclusion = parse_acceptance_timestamp_with_reason(raw_timestamp)
        if timestamp is None:
            counters[timestamp_exclusion] += 1
            continue
        if not timestamp_consistent_with_filing_date(timestamp, filing_date):
            counters["records_filing_date_inconsistent"] += 1
            continue
        counters["records_retained_as_eligible_8k"] += 1
        rows.append(
            {
                "issuer_id": response.issuer_id,
                "issuer_cik": configured_cik,
                "accession_number": accession_number,
                "form_type": form_type,
                "filing_date": filing_date,
                "acceptance_timestamp_raw": str(raw_timestamp),
                "acceptance_timestamp": timestamp.isoformat(),
                "acceptance_timestamp_timezone": ACCEPTANCE_TIMEZONE,
                "timestamp_evidence_source": TIMESTAMP_EVIDENCE_SOURCE,
                "content_availability_evidence_level": CONTENT_AVAILABILITY_EVIDENCE_LEVEL,
                "availability_rule_id": AVAILABILITY_RULE_ID,
                "source_url": response.source_url,
                "retrieved_at_utc": response.retrieved_at_utc,
                "snapshot_id": "",
            }
        )
    return rows, counters


def empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def build_acceptance_events(
    crawl: CrawlResult,
    config: dict[str, Any],
    manifest_root: Path,
) -> tuple[pd.DataFrame, dict[str, int], int, int]:
    rows: list[dict[str, Any]] = []
    exclusions: dict[str, int] = {}
    for response in crawl.responses:
        response_rows, counters = parse_response_events(response, config)
        rows.extend(response_rows)
        for key, value in counters.items():
            exclusions[key] = exclusions.get(key, 0) + int(value)
    events = pd.DataFrame(rows, columns=EVENT_COLUMNS)
    duplicate_count = 0
    conflict_rows: list[dict[str, Any]] = []
    if not events.empty:
        grouped = events.groupby(["issuer_id", "accession_number"], dropna=False)
        keep_indexes = []
        for (_issuer_id, _accession), group in grouped:
            unique_timestamps = set(group["acceptance_timestamp"])
            if len(unique_timestamps) > 1:
                conflict_rows.append(
                    {
                        "issuer_id": group.iloc[0]["issuer_id"],
                        "accession_number": group.iloc[0]["accession_number"],
                    }
                )
            duplicate_count += max(0, len(group) - 1)
            keep_indexes.append(group.index[0])
        if conflict_rows:
            raise AcceptanceTimestampConflictError(conflict_rows)
        events = events.loc[sorted(keep_indexes)].copy()
        exclusions["records_deduplicated"] = int(duplicate_count)
        manifest = pd.read_parquet(manifest_root / "sec_edgar_raw_snapshot_manifest.parquet")
        snapshot_by_url = (
            manifest.drop_duplicates("source_url").set_index("source_url")["snapshot_id"].to_dict()
        )
        events["snapshot_id"] = events["source_url"].map(snapshot_by_url).fillna("")
        timestamps_ny = normalize_acceptance_timestamps_ny(events)
        events = (
            events.assign(_acceptance_timestamp_sort=timestamps_ny)
            .sort_values(["_acceptance_timestamp_sort", "issuer_id", "accession_number"])
            .drop(columns=["_acceptance_timestamp_sort"])
        )
    for field in EXCLUSION_ACCOUNTING_FIELDS:
        exclusions.setdefault(field, 0)
    exclusions["records_retained_as_eligible_8k"] = int(len(events))
    return events.reset_index(drop=True), exclusions, duplicate_count, len(conflict_rows)


def qualification_summary(
    events: pd.DataFrame,
    config: dict[str, Any],
    source_access_status: str,
    conflict_count: int,
) -> tuple[bool, list[str]]:
    if source_access_status in CONTROLLED_ACCESS_REASONS:
        return False, list(CONTROLLED_ACCESS_REASONS[source_access_status])
    reasons: list[str] = []
    if source_access_status != SOURCE_ACCESS_AVAILABLE:
        reasons.append(f"source_access_status_not_available:{source_access_status}")
    total = int(len(events))
    minimum_total = int(config["minimum_total_accepted_8k_events"])
    if total < minimum_total:
        reasons.append(f"eligible_8k_event_count_below_minimum:{total}<{minimum_total}")
    event_counts = (
        events["issuer_id"].value_counts().sort_index().to_dict() if not events.empty else {}
    )
    qualifying_issuers = [
        issuer_id
        for issuer_id, count in event_counts.items()
        if int(count) >= int(config["minimum_events_per_qualifying_issuer"])
    ]
    if len(qualifying_issuers) < int(config["minimum_qualifying_issuers"]):
        reasons.append(
            "qualifying_issuer_count_below_minimum:"
            f"{len(qualifying_issuers)}<{int(config['minimum_qualifying_issuers'])}"
        )
    if not events.empty:
        timestamps_ny = normalize_acceptance_timestamps_ny(events)
        years = timestamps_ny.dt.year
        coverage_years = int(years.max() - years.min() + 1)
    else:
        coverage_years = 0
    if coverage_years < int(config["minimum_calendar_years_of_coverage"]):
        reasons.append(
            "calendar_year_coverage_below_minimum:"
            f"{coverage_years}<{int(config['minimum_calendar_years_of_coverage'])}"
        )
    if not events.empty:
        missing = events[events["acceptance_timestamp"].isna()]
        if not missing.empty:
            reasons.append("retained_events_with_unparseable_acceptance_timestamp")
    if conflict_count:
        reasons.append(f"timestamp_conflict_count:{conflict_count}")
    if not reasons:
        reasons.append("qualified")
    return reasons == ["qualified"], reasons


def diagnostic_dict(diagnostic: SourceAccessDiagnostic | None) -> dict[str, Any]:
    if diagnostic is None:
        return {}
    return {
        "http_status_code": diagnostic.http_status_code,
        "endpoint_path": diagnostic.endpoint_path,
        "request_stage": diagnostic.request_stage,
        "source_access_status": diagnostic.source_access_status,
    }


def build_report(
    *,
    config: dict[str, Any],
    crawl: CrawlResult,
    events: pd.DataFrame,
    exclusions: dict[str, int],
    duplicate_count: int,
    conflict_count: int,
    report_root: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    report_root.mkdir(parents=True, exist_ok=True)
    qualified, reasons = qualification_summary(
        events, config, crawl.source_access_status, conflict_count
    )
    event_counts = (
        {
            str(key): int(value)
            for key, value in events["issuer_id"].value_counts().sort_index().items()
        }
        if not events.empty
        else {}
    )
    evidence_counts = (
        {
            str(key): int(value)
            for key, value in (
                events["timestamp_evidence_source"].value_counts().sort_index().items()
            )
        }
        if not events.empty
        else {}
    )
    if events.empty:
        earliest = None
        latest = None
    else:
        timestamps_ny = normalize_acceptance_timestamps_ny(events)
        earliest = timestamps_ny.min().isoformat()
        latest = timestamps_ny.max().isoformat()
    exclusion_counts = {
        field: int(exclusions.get(field, 0)) for field in EXCLUSION_ACCOUNTING_FIELDS
    }
    for key, value in sorted(exclusions.items()):
        if key not in exclusion_counts:
            exclusion_counts[str(key)] = int(value)
    report = {
        "source_id": str(config["source_id"]),
        "source_access_status": crawl.source_access_status,
        "source_access_diagnostics": diagnostic_dict(crawl.source_access_diagnostic),
        "configured_issuer_count": len(config["issuers"]),
        "fetched_issuer_count": len(crawl.fetched_issuer_ids),
        "eligible_8k_event_count": int(len(events)),
        "event_count_by_issuer": event_counts,
        "earliest_acceptance_timestamp": earliest,
        "latest_acceptance_timestamp": latest,
        "timestamp_evidence_counts": evidence_counts,
        "duplicate_and_conflict_counts": {
            "duplicate_issuer_accession_count": int(duplicate_count),
            "timestamp_conflict_count": int(conflict_count),
        },
        "exclusion_counts": exclusion_counts,
        "qualified_for_later_next_session_event_research": qualified,
        "qualification_reasons": reasons,
        "known_limitations": KNOWN_LIMITATIONS,
    }
    json_path = report_root / "sec_edgar_8k_acceptance_qualification.json"
    md_path = report_root / "sec_edgar_8k_acceptance_qualification.md"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [
        "# MI-7 SEC EDGAR 8-K Acceptance Source Qualification",
        "",
        f"Source: {config['source_id']}",
        f"Source access status: {crawl.source_access_status}",
        f"Configured issuers: {len(config['issuers'])}",
        f"Fetched issuers: {len(crawl.fetched_issuer_ids)}",
        f"Eligible 8-K events: {len(events)}",
        f"eligible_8k_event_count: {len(events)}",
        f"Earliest acceptance timestamp: {earliest}",
        f"Latest acceptance timestamp: {latest}",
        f"Qualified for later next-session event research: {qualified}",
        "Qualification reasons:",
        *[f"- {reason}" for reason in reasons],
        "",
        "Exclusion accounting:",
        *[f"- {field}: {exclusion_counts[field]}" for field in EXCLUSION_ACCOUNTING_FIELDS],
        "",
        "Known limitations:",
        *[f"- {item}" for item in KNOWN_LIMITATIONS],
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path, report


def run_mi7_sec_edgar_8k_acceptance_qualification(
    *,
    mi7_data_root: Path,
    report_root: Path,
    config_path: Path = Path("configs/intelligence/sec_issuer_panel_mi7.yaml"),
    fetcher: Fetcher | None = None,
    env: dict[str, str] | None = None,
    time_fn: Any = time.monotonic,
    sleep_fn: Any = time.sleep,
) -> Mi7RunResult:
    config = read_yaml(config_path)
    user_agent = load_sec_user_agent(env)
    raw_root = mi7_data_root / "raw"
    manifest_root = mi7_data_root / "manifests"
    normalized_root = mi7_data_root / "normalized"
    normalized_root.mkdir(parents=True, exist_ok=True)
    source = fetcher or UrlLibFetcher()
    crawl = crawl_sec_submissions(
        config=config,
        user_agent=user_agent,
        fetcher=source,
        raw_root=raw_root,
        manifest_root=manifest_root,
        time_fn=time_fn,
        sleep_fn=sleep_fn,
    )
    if crawl.source_access_status in CONTROLLED_ACCESS_REASONS:
        events = empty_events()
        exclusions: dict[str, int] = {}
        duplicate_count = 0
        conflict_count = 0
    else:
        events, exclusions, duplicate_count, conflict_count = build_acceptance_events(
            crawl, config, manifest_root
        )
    event_path = normalized_root / "sec_edgar_8k_acceptance_event.parquet"
    events.to_parquet(event_path, index=False)
    md_path, json_path, report = build_report(
        config=config,
        crawl=crawl,
        events=events,
        exclusions=exclusions,
        duplicate_count=duplicate_count,
        conflict_count=conflict_count,
        report_root=report_root,
    )
    output_paths = {
        "raw_root": str(raw_root),
        "sec_edgar_raw_snapshot_manifest": str(
            manifest_root / "sec_edgar_raw_snapshot_manifest.parquet"
        ),
        "sec_edgar_8k_acceptance_event": str(event_path),
        "report_markdown": str(md_path),
        "report_json": str(json_path),
    }
    return Mi7RunResult(
        source_id=str(report["source_id"]),
        source_access_status=str(report["source_access_status"]),
        source_access_diagnostics=dict(report["source_access_diagnostics"]),
        configured_issuer_count=int(report["configured_issuer_count"]),
        eligible_8k_event_count=int(report["eligible_8k_event_count"]),
        earliest_acceptance_timestamp=report["earliest_acceptance_timestamp"],
        latest_acceptance_timestamp=report["latest_acceptance_timestamp"],
        qualified_for_later_next_session_event_research=bool(
            report["qualified_for_later_next_session_event_research"]
        ),
        qualification_reasons=list(report["qualification_reasons"]),
        output_paths=output_paths,
    )
