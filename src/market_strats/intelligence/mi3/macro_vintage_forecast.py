"""Vintage-aware MI-3 macro forecast comparison."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import yaml

from market_strats.intelligence.mi2.technical_baseline import (
    FEATURE_COLUMNS as TECHNICAL_FEATURE_COLUMNS,
)
from market_strats.intelligence.mi2.technical_baseline import (
    fit_ridge_predict,
    load_registry_rules,
    rank_correlation,
    walk_forward_boundaries,
)

MACRO_AVAILABILITY_EVIDENCE_LEVEL = "contractual_assumption"
MACRO_AVAILABILITY_RULE_ID = "macro_vintage_next_session_cutoff_v1"
RIDGE_ALPHA = 1.0
FRED_BASE_URL = "https://api.stlouisfed.org"
FRED_OBSERVATIONS_ENDPOINT_PATH = "/fred/series/observations"
FRED_VINTAGE_DATES_ENDPOINT_PATH = "/fred/series/vintagedates"
FRED_ENDPOINT_PATH = FRED_OBSERVATIONS_ENDPOINT_PATH

MACRO_FEATURE_COLUMNS = [
    "DFF_level",
    "DFF_change_21",
    "T10Y2Y_level",
    "T10Y2Y_change_21",
    "BAA10YM_level",
    "BAA10YM_change_21",
    "CPIAUCSL_log_change_252",
    "UNRATE_level",
    "UNRATE_change_63",
    "INDPRO_log_change_252",
    "DFF_macro_staleness_sessions",
    "T10Y2Y_macro_staleness_sessions",
    "BAA10YM_macro_staleness_sessions",
    "CPIAUCSL_macro_staleness_sessions",
    "UNRATE_macro_staleness_sessions",
    "INDPRO_macro_staleness_sessions",
]


@dataclass(frozen=True)
class MacroSeries:
    series_id: str
    name: str


@dataclass(frozen=True)
class MacroRawResponse:
    series_id: str
    request_parameters: dict[str, Any]
    payload: dict[str, Any]
    retrieved_at_utc: datetime


@dataclass(frozen=True)
class MacroVintageCapability:
    series_id: str
    vintage_start_date: date
    vintage_end_date: date
    requested_effective_realtime_start: date
    requested_effective_realtime_end: date


@dataclass(frozen=True)
class Mi3RunResult:
    source_provenance: dict[str, Any]
    macro_series_count: int
    macro_availability_evidence_level: str
    macro_eligible_start_date: str
    validation_start_date: str
    validation_end_date: str
    holdout_start_date: str
    holdout_end_date: str
    row_counts: dict[str, int]
    model_count: int
    output_paths: dict[str, str]
    scoreboard_summary: list[dict[str, Any]]
    vintage_capabilities: list[dict[str, str]]


class MacroVintageSource(Protocol):
    source_id: str
    source_name: str

    def fetch_vintage_observations(
        self,
        series: list[MacroSeries],
        observation_start: date,
        observation_end: date,
    ) -> list[MacroRawResponse]:
        """Fetch vintage-aware observations without using current-default responses."""


class FredRequestError(RuntimeError):
    """Safe FRED request failure without API-key or full-URL leakage."""

    def __init__(
        self,
        *,
        status_code: int,
        series_id: str,
        request_parameters: dict[str, Any],
        body: str,
    ) -> None:
        self.status_code = status_code
        self.series_id = series_id
        self.request_parameters = request_parameters
        self.body = sanitize_fred_error_body(body)
        super().__init__(self._message())

    def _message(self) -> str:
        endpoint_path = self.request_parameters.get("endpoint_path", FRED_ENDPOINT_PATH)
        request_type = self.request_parameters.get("request_type", "observations")
        return (
            "FRED request failed "
            f"status_code={self.status_code} "
            f"series_id={self.series_id} "
            f"request_type={request_type} "
            f"endpoint_path={endpoint_path} "
            f"realtime_start={self.request_parameters.get('realtime_start')} "
            f"realtime_end={self.request_parameters.get('realtime_end')} "
            f"observation_start={self.request_parameters.get('observation_start')} "
            f"observation_end={self.request_parameters.get('observation_end')} "
            f"output_type={self.request_parameters.get('output_type')} "
            f"limit={self.request_parameters.get('limit')} "
            f"offset={self.request_parameters.get('offset')} "
            f"fred_error_body={self.body}"
        )


def sanitize_fred_error_body(body: str, limit: int = 500) -> str:
    text = " ".join(str(body).replace("\r", " ").replace("\n", " ").split())
    text = re.sub(r"api_key=([^&\s]+)", "api_key=<redacted>", text, flags=re.IGNORECASE)
    text = re.sub(
        r'("api_key"\s*:\s*")[^"]+(")',
        r"\1<redacted>\2",
        text,
        flags=re.IGNORECASE,
    )
    return text[:limit]


def split_realtime_windows(
    realtime_start: date,
    realtime_end: date,
    *,
    years_per_chunk: int = 3,
) -> list[tuple[date, date]]:
    if realtime_end < realtime_start:
        raise ValueError("realtime_end must be on or after realtime_start")
    chunks: list[tuple[date, date]] = []
    chunk_start = pd.Timestamp(realtime_start)
    final_end = pd.Timestamp(realtime_end)
    while chunk_start <= final_end:
        chunk_end = min(
            chunk_start + pd.DateOffset(years=years_per_chunk) - pd.Timedelta(days=1),
            final_end,
        )
        chunks.append((chunk_start.date(), chunk_end.date()))
        chunk_start = chunk_end + pd.Timedelta(days=1)
    validate_realtime_windows(
        chunks,
        realtime_start,
        realtime_end,
        years_per_chunk=years_per_chunk,
    )
    return chunks


def validate_realtime_windows(
    chunks: list[tuple[date, date]],
    realtime_start: date,
    realtime_end: date,
    *,
    years_per_chunk: int = 3,
) -> None:
    if not chunks:
        raise ValueError("At least one realtime chunk is required")
    if chunks[0][0] != realtime_start:
        raise ValueError("First realtime chunk does not start at requested realtime_start")
    if chunks[-1][1] != realtime_end:
        raise ValueError("Final realtime chunk does not end at requested realtime_end")
    for index, (chunk_start, chunk_end) in enumerate(chunks):
        max_end = (
            pd.Timestamp(chunk_start) + pd.DateOffset(years=years_per_chunk) - pd.Timedelta(days=1)
        ).date()
        if chunk_end > max_end:
            raise ValueError("Realtime chunk exceeds maximum calendar-year span")
        if chunk_end < chunk_start:
            raise ValueError("Realtime chunk end precedes start")
        if index > 0:
            previous_end = chunks[index - 1][1]
            expected_start = (pd.Timestamp(previous_end) + pd.Timedelta(days=1)).date()
            if chunk_start != expected_start:
                raise ValueError("Realtime chunks must be contiguous without gaps or overlaps")


def manifest_value(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value)


def int_or_zero(value: Any) -> int:
    if value is None:
        return 0
    if pd.isna(value):
        return 0
    return int(value)


def response_manifest_key(response: MacroRawResponse) -> tuple[str, str, str, int]:
    params = response.request_parameters
    return (
        response.series_id,
        manifest_value(params.get("realtime_start")),
        manifest_value(params.get("realtime_end")),
        int_or_zero(params.get("offset")),
    )


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return value


def load_macro_series_config(path: Path) -> tuple[dict[str, Any], list[MacroSeries]]:
    config = read_yaml(path)
    series = [MacroSeries(str(item["series_id"]), str(item["name"])) for item in config["series"]]
    expected = ["DFF", "T10Y2Y", "BAA10YM", "CPIAUCSL", "UNRATE", "INDPRO"]
    if [item.series_id for item in series] != expected:
        raise ValueError(
            "MI-3 macro universe must match configs/intelligence/macro_series_mi3.yaml exactly"
        )
    return config["source"], series


class FredVintageAdapter:
    source_id = "fred_alfred_observations_vintage"
    source_name = "FRED/ALFRED observations API"

    def __init__(
        self,
        api_key: str | None = None,
        opener: Any | None = None,
        limit: int = 100000,
        vintage_dates_limit: int = 10000,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("FRED_API_KEY")
        self._opener = opener or urllib.request.urlopen
        self._limit = limit
        self._vintage_dates_limit = vintage_dates_limit
        self.vintage_capabilities: list[MacroVintageCapability] = []

    def _require_key(self) -> str:
        if not self._api_key:
            raise RuntimeError("FRED_API_KEY is required in the active process environment")
        return self._api_key

    def _request_json(
        self,
        *,
        endpoint_path: str,
        series_id: str,
        safe_params: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        query_params = {
            key: value
            for key, value in safe_params.items()
            if key not in {"request_type", "endpoint_path"}
        }
        url = (
            FRED_BASE_URL
            + endpoint_path
            + "?"
            + urllib.parse.urlencode({**query_params, "api_key": api_key})
        )
        try:
            with self._opener(url, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise FredRequestError(
                status_code=error.code,
                series_id=series_id,
                request_parameters=safe_params,
                body=read_error_body(error),
            ) from error

    def _fetch_vintage_date_pages(
        self,
        item: MacroSeries,
        api_key: str,
    ) -> list[MacroRawResponse]:
        responses: list[MacroRawResponse] = []
        offset = 0
        while True:
            safe_params = {
                "request_type": "vintage_dates",
                "endpoint_path": FRED_VINTAGE_DATES_ENDPOINT_PATH,
                "series_id": item.series_id,
                "file_type": "json",
                "limit": self._vintage_dates_limit,
                "offset": offset,
            }
            payload = self._request_json(
                endpoint_path=FRED_VINTAGE_DATES_ENDPOINT_PATH,
                series_id=item.series_id,
                safe_params=safe_params,
                api_key=api_key,
            )
            vintage_dates = payload.get("vintage_dates", [])
            responses.append(
                MacroRawResponse(
                    series_id=item.series_id,
                    request_parameters=safe_params,
                    payload=payload,
                    retrieved_at_utc=datetime.now(UTC),
                )
            )
            count = int(payload.get("count", offset + len(vintage_dates)))
            if not vintage_dates or offset + len(vintage_dates) >= count:
                break
            offset += self._vintage_dates_limit
        return responses

    def _discover_vintage_capabilities(
        self,
        series: list[MacroSeries],
        observation_start: date,
        observation_end: date,
        api_key: str,
    ) -> tuple[list[MacroRawResponse], list[MacroVintageCapability]]:
        responses: list[MacroRawResponse] = []
        capabilities: list[MacroVintageCapability] = []
        unsupported: list[str] = []
        outside_requested_range: list[str] = []
        for item in series:
            pages = self._fetch_vintage_date_pages(item, api_key)
            responses.extend(pages)
            vintage_dates = sorted(
                {
                    pd.Timestamp(value).date()
                    for page in pages
                    for value in page.payload.get("vintage_dates", [])
                    if pd.notna(pd.to_datetime(value, errors="coerce"))
                }
            )
            if not vintage_dates:
                unsupported.append(item.series_id)
                continue
            vintage_start = vintage_dates[0]
            vintage_end = vintage_dates[-1]
            effective_start = max(observation_start, vintage_start)
            effective_end = min(observation_end, vintage_end)
            if effective_end < effective_start:
                outside_requested_range.append(item.series_id)
                continue
            capabilities.append(
                MacroVintageCapability(
                    series_id=item.series_id,
                    vintage_start_date=vintage_start,
                    vintage_end_date=vintage_end,
                    requested_effective_realtime_start=effective_start,
                    requested_effective_realtime_end=effective_end,
                )
            )
        if unsupported:
            raise ValueError(
                "Configured macro series unavailable in ALFRED vintage dates; "
                "no FRED-current fallback is allowed. unsupported_series_ids="
                + ",".join(sorted(unsupported))
            )
        if outside_requested_range:
            raise ValueError(
                "Configured macro series have no ALFRED vintage-date overlap with the requested "
                "historical real-time range; no FRED-current fallback is allowed. "
                "series_ids=" + ",".join(sorted(outside_requested_range))
            )
        return responses, capabilities

    def fetch_vintage_observations(
        self,
        series: list[MacroSeries],
        observation_start: date,
        observation_end: date,
    ) -> list[MacroRawResponse]:
        api_key = self._require_key()
        capability_responses, capabilities = self._discover_vintage_capabilities(
            series,
            observation_start,
            observation_end,
            api_key,
        )
        self.vintage_capabilities = capabilities
        capabilities_by_series = {capability.series_id: capability for capability in capabilities}
        responses: list[MacroRawResponse] = list(capability_responses)
        for item in series:
            capability = capabilities_by_series[item.series_id]
            chunks = split_realtime_windows(
                capability.requested_effective_realtime_start,
                capability.requested_effective_realtime_end,
            )
            for chunk_start, chunk_end in chunks:
                offset = 0
                while True:
                    safe_params = {
                        "request_type": "observations",
                        "endpoint_path": FRED_OBSERVATIONS_ENDPOINT_PATH,
                        "series_id": item.series_id,
                        "file_type": "json",
                        "observation_start": observation_start.isoformat(),
                        "observation_end": observation_end.isoformat(),
                        "realtime_start": chunk_start.isoformat(),
                        "realtime_end": chunk_end.isoformat(),
                        "output_type": 1,
                        "limit": self._limit,
                        "offset": offset,
                        "series_vintage_start_date": capability.vintage_start_date.isoformat(),
                        "series_vintage_end_date": capability.vintage_end_date.isoformat(),
                        "requested_effective_realtime_start": (
                            capability.requested_effective_realtime_start.isoformat()
                        ),
                        "requested_effective_realtime_end": (
                            capability.requested_effective_realtime_end.isoformat()
                        ),
                    }
                    payload = self._request_json(
                        endpoint_path=FRED_OBSERVATIONS_ENDPOINT_PATH,
                        series_id=item.series_id,
                        safe_params=safe_params,
                        api_key=api_key,
                    )
                    batch = payload.get("observations", [])
                    responses.append(
                        MacroRawResponse(
                            series_id=item.series_id,
                            request_parameters=safe_params,
                            payload=payload,
                            retrieved_at_utc=datetime.now(UTC),
                        )
                    )
                    count = int(payload.get("count", offset + len(batch)))
                    if not batch or offset + len(batch) >= count:
                        break
                    offset += int(safe_params["limit"])
        return responses


def read_error_body(error: urllib.error.HTTPError) -> str:
    try:
        content = error.read()
    except Exception:
        return ""
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content)


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def write_macro_raw_snapshots(
    responses: list[MacroRawResponse],
    raw_root: Path,
    manifest_root: Path,
    source_name: str,
) -> pd.DataFrame:
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for response in responses:
        content = canonical_json_bytes(response.payload)
        content_hash = hashlib.sha256(content).hexdigest()
        request_basis = json.dumps(response.request_parameters, sort_keys=True)
        snapshot_basis = f"{response.series_id}|{request_basis}|{content_hash}".encode()
        snapshot_digest = hashlib.sha256(snapshot_basis).hexdigest()[:24]
        snapshot_id = f"mi3_macro_{response.series_id.lower()}_{snapshot_digest}"
        raw_path = raw_root / f"{snapshot_id}.json"
        raw_path.write_bytes(content)
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "source_name": source_name,
                "series_id": response.series_id,
                "request_parameters": json.dumps(response.request_parameters, sort_keys=True),
                "request_type": response.request_parameters.get("request_type"),
                "endpoint_path": response.request_parameters.get("endpoint_path"),
                "realtime_start": response.request_parameters.get("realtime_start"),
                "realtime_end": response.request_parameters.get("realtime_end"),
                "observation_start": response.request_parameters.get("observation_start"),
                "observation_end": response.request_parameters.get("observation_end"),
                "limit": response.request_parameters.get("limit"),
                "offset": response.request_parameters.get("offset"),
                "series_vintage_start_date": response.request_parameters.get(
                    "series_vintage_start_date"
                ),
                "series_vintage_end_date": response.request_parameters.get(
                    "series_vintage_end_date"
                ),
                "requested_effective_realtime_start": response.request_parameters.get(
                    "requested_effective_realtime_start"
                ),
                "requested_effective_realtime_end": response.request_parameters.get(
                    "requested_effective_realtime_end"
                ),
                "retrieved_at_utc": response.retrieved_at_utc,
                "content_sha256": content_hash,
                "raw_path": str(raw_path),
                "publication_permission": "raw_local_only_not_redistributable",
                "availability_evidence_level": MACRO_AVAILABILITY_EVIDENCE_LEVEL,
            }
        )
    manifest = pd.DataFrame(rows)
    manifest.to_parquet(manifest_root / "macro_raw_snapshot_manifest.parquet", index=False)
    return manifest


@lru_cache(maxsize=64)
def equity_sessions_for_years(start_year: int, end_year: int) -> tuple[pd.Timestamp, ...]:
    calendar = mcal.get_calendar("XNYS")
    schedule = calendar.schedule(
        start_date=f"{start_year}-01-01",
        end_date=f"{end_year}-12-31",
    )
    return tuple(pd.Timestamp(index_value).normalize() for index_value in schedule.index)


@lru_cache(maxsize=4096)
def first_equity_session_after_date(value: date) -> pd.Timestamp:
    lookup = pd.Timestamp(value).normalize()
    sessions = equity_sessions_for_years(lookup.year, lookup.year + 1)
    index = bisect_right(sessions, lookup)
    if index >= len(sessions):
        raise ValueError(f"No U.S. equity session found after {value}")
    return sessions[index]


def first_equity_session_after(value: pd.Timestamp) -> pd.Timestamp:
    return first_equity_session_after_date(value.date())


def macro_available_at_utc(realtime_start: pd.Timestamp) -> pd.Timestamp:
    session = first_equity_session_after(realtime_start)
    local = datetime.combine(
        session.date(),
        time(20, 0),
        tzinfo=ZoneInfo("America/New_York"),
    )
    return pd.Timestamp(local.astimezone(UTC))


def parse_provider_date(value: Any, *, realtime_end: bool = False) -> pd.Timestamp:
    if realtime_end and str(value) == "9999-12-31":
        return pd.Timestamp.max.normalize()
    return pd.to_datetime(value, errors="coerce")


def normalize_macro_observations(
    responses: list[MacroRawResponse],
    manifest: pd.DataFrame,
) -> pd.DataFrame:
    responses = [
        response
        for response in responses
        if response.request_parameters.get("request_type", "observations") == "observations"
    ]
    snapshot_by_request = {
        (
            row.series_id,
            manifest_value(row.realtime_start),
            manifest_value(row.realtime_end),
            int_or_zero(row.offset),
        ): row.snapshot_id
        for row in manifest.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for response in responses:
        for observation in response.payload.get("observations", []):
            realtime_start = parse_provider_date(observation.get("realtime_start"))
            realtime_end = parse_provider_date(observation.get("realtime_end"), realtime_end=True)
            observation_date = parse_provider_date(observation.get("date"))
            value = pd.to_numeric(observation.get("value"), errors="coerce")
            valid_vintage = (
                pd.notna(realtime_start)
                and pd.notna(realtime_end)
                and pd.notna(observation_date)
                and pd.notna(value)
                and realtime_end >= realtime_start
            )
            evidence = MACRO_AVAILABILITY_EVIDENCE_LEVEL if valid_vintage else "unverified"
            rows.append(
                {
                    "series_id": response.series_id,
                    "observation_date": observation_date.normalize()
                    if pd.notna(observation_date)
                    else pd.NaT,
                    "realtime_start": realtime_start.normalize()
                    if pd.notna(realtime_start)
                    else pd.NaT,
                    "realtime_end": realtime_end.normalize() if pd.notna(realtime_end) else pd.NaT,
                    "value": float(value) if pd.notna(value) else np.nan,
                    "available_at_utc": macro_available_at_utc(realtime_start)
                    if valid_vintage
                    else pd.NaT,
                    "availability_evidence_level": evidence,
                    "availability_rule_id": MACRO_AVAILABILITY_RULE_ID,
                    "retrieved_at_utc": response.retrieved_at_utc,
                    "snapshot_id": snapshot_by_request[response_manifest_key(response)],
                }
            )
    if not rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(rows).drop_duplicates(
        subset=["series_id", "observation_date", "value", "realtime_start", "realtime_end"],
        keep="first",
    )


def staleness_sessions(
    sessions: list[pd.Timestamp],
    observation_date: pd.Timestamp,
    decision_session: pd.Timestamp,
) -> int:
    if pd.isna(observation_date):
        return -1
    return sum(observation_date < session <= decision_session for session in sessions)


def build_macro_asof_panel(
    decision_sessions: list[pd.Timestamp],
    observations: pd.DataFrame,
) -> pd.DataFrame:
    if (observations["availability_evidence_level"] == "unverified").any():
        observations = observations[
            observations["availability_evidence_level"] != "unverified"
        ].copy()
    sessions = [pd.Timestamp(item).normalize() for item in decision_sessions]
    rows = []
    grouped = {series_id: group.copy() for series_id, group in observations.groupby("series_id")}
    for session in sessions:
        decision_cutoff = pd.Timestamp(
            datetime.combine(session.date(), time(20, 0), tzinfo=ZoneInfo("America/New_York"))
        ).tz_convert("UTC")
        row: dict[str, Any] = {"session_date": session}
        evidence_counts: dict[str, int] = {}
        available_all = True
        for series_id, group in grouped.items():
            eligible = group[
                (group["observation_date"] <= session)
                & (group["realtime_start"] <= session)
                & (group["realtime_end"] >= session)
                & (pd.to_datetime(group["available_at_utc"], utc=True) <= decision_cutoff)
                & (group["availability_evidence_level"] == MACRO_AVAILABILITY_EVIDENCE_LEVEL)
            ]
            if eligible.empty:
                row[f"{series_id}_value"] = np.nan
                row[f"{series_id}_observation_date"] = pd.NaT
                row[f"{series_id}_macro_staleness_sessions"] = np.nan
                available_all = False
                continue
            selected = eligible.sort_values(["observation_date", "realtime_start"]).iloc[-1]
            row[f"{series_id}_value"] = selected["value"]
            row[f"{series_id}_observation_date"] = selected["observation_date"]
            row[f"{series_id}_macro_staleness_sessions"] = staleness_sessions(
                sessions,
                selected["observation_date"],
                session,
            )
            level = selected["availability_evidence_level"]
            evidence_counts[level] = evidence_counts.get(level, 0) + 1
        row["macro_asof_available"] = available_all
        row["availability_evidence_level_counts"] = json.dumps(evidence_counts, sort_keys=True)
        rows.append(row)
    return pd.DataFrame(rows)


def build_macro_feature_panel(asof_panel: pd.DataFrame) -> pd.DataFrame:
    panel = asof_panel.sort_values("session_date").copy()
    panel["DFF_level"] = panel["DFF_value"]
    panel["DFF_change_21"] = panel["DFF_value"] - panel["DFF_value"].shift(21)
    panel["T10Y2Y_level"] = panel["T10Y2Y_value"]
    panel["T10Y2Y_change_21"] = panel["T10Y2Y_value"] - panel["T10Y2Y_value"].shift(21)
    panel["BAA10YM_level"] = panel["BAA10YM_value"]
    panel["BAA10YM_change_21"] = panel["BAA10YM_value"] - panel["BAA10YM_value"].shift(21)
    panel["CPIAUCSL_log_change_252"] = np.log(
        panel["CPIAUCSL_value"] / panel["CPIAUCSL_value"].shift(252)
    )
    panel["UNRATE_level"] = panel["UNRATE_value"]
    panel["UNRATE_change_63"] = panel["UNRATE_value"] - panel["UNRATE_value"].shift(63)
    panel["INDPRO_log_change_252"] = np.log(
        panel["INDPRO_value"] / panel["INDPRO_value"].shift(252)
    )
    for series_id in ["DFF", "T10Y2Y", "BAA10YM", "CPIAUCSL", "UNRATE", "INDPRO"]:
        panel[f"{series_id}_macro_staleness_sessions"] = panel[
            f"{series_id}_macro_staleness_sessions"
        ]
    panel["macro_feature_available"] = panel["macro_asof_available"] & panel[
        MACRO_FEATURE_COLUMNS
    ].notna().all(axis=1)
    panel["macro_feature_block_reason"] = ""
    panel.loc[~panel["macro_asof_available"], "macro_feature_block_reason"] = (
        "missing_vintage_available_macro_value"
    )
    panel.loc[
        panel["macro_asof_available"] & ~panel[MACRO_FEATURE_COLUMNS].notna().all(axis=1),
        "macro_feature_block_reason",
    ] = "insufficient_macro_feature_history"
    return panel[
        [
            "session_date",
            "macro_feature_available",
            "macro_feature_block_reason",
            "availability_evidence_level_counts",
            *MACRO_FEATURE_COLUMNS,
        ]
    ].copy()


def load_mi2_panels(mi2_data_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_path = mi2_data_root / "feature_panel.parquet"
    target_path = mi2_data_root / "target_panel.parquet"
    missing = [str(path) for path in [feature_path, target_path] if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required MI-2 outputs: " + ", ".join(missing))
    features = pd.read_parquet(feature_path)
    targets = pd.read_parquet(target_path)
    features["session_date"] = pd.to_datetime(features["session_date"]).dt.normalize()
    targets["session_date"] = pd.to_datetime(targets["session_date"]).dt.normalize()
    return features, targets


def validate_mi1_availability_for_mi3(mi1_data_root: Path) -> None:
    path = mi1_data_root / "normalized" / "decision_panel_availability_audit.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"Missing required MI-1 availability audit: {path}")
    availability = pd.read_parquet(path)
    required = {"eligible", "availability_evidence_level"}
    missing = required - set(availability.columns)
    if missing:
        raise ValueError(f"MI-1 availability audit is outside contract: {sorted(missing)}")
    if (
        (availability["availability_evidence_level"] == "unverified") & availability["eligible"]
    ).any():
        raise ValueError("Unverified MI-1 row is marked decision-panel eligible")


def build_macro_predictions(
    technical_features: pd.DataFrame,
    targets: pd.DataFrame,
    macro_features: pd.DataFrame,
    registry: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any], pd.Timestamp]:
    samples = technical_features.merge(targets, on=["instrument_id", "session_date"])
    samples = samples.merge(macro_features, on="session_date", how="inner")
    samples = samples[
        samples["feature_available"]
        & samples["target_available"]
        & samples["macro_feature_available"]
    ].copy()
    if samples.empty:
        raise ValueError("No macro-eligible forecast rows available")
    macro_start = samples["session_date"].min()
    sessions = list(pd.Index(samples["session_date"].unique()).sort_values())
    bounds = walk_forward_boundaries(sessions, registry)
    predictions: list[pd.DataFrame] = []

    def predict_block(
        train_sessions: list[pd.Timestamp],
        test_sessions: list[pd.Timestamp],
        segment: str,
    ) -> None:
        train = samples[samples["session_date"].isin(train_sessions)]
        test = samples[samples["session_date"].isin(test_sessions)]
        if train.empty or test.empty:
            return
        technical_prediction = fit_ridge_predict(
            train[TECHNICAL_FEATURE_COLUMNS],
            train["target_value"],
            test[TECHNICAL_FEATURE_COLUMNS],
            alpha=RIDGE_ALPHA,
        )
        combined_prediction = fit_ridge_predict(
            train[TECHNICAL_FEATURE_COLUMNS + MACRO_FEATURE_COLUMNS],
            train["target_value"],
            test[TECHNICAL_FEATURE_COLUMNS + MACRO_FEATURE_COLUMNS],
            alpha=RIDGE_ALPHA,
        )
        out = test[
            [
                "instrument_id",
                "session_date",
                "target_value",
                "raw_return_21",
                "availability_evidence_level_counts",
            ]
        ].copy()
        out["evaluation_segment"] = segment
        out["ridge_technical_only_alpha_1_0"] = technical_prediction
        out["ridge_technical_plus_macro_alpha_1_0"] = combined_prediction
        out["zero_forward_excess_return"] = 0.0
        out["persistence_last_observed_return"] = test["raw_return_21"].to_numpy()
        predictions.append(out)

    validation_sessions = bounds["validation_sessions"]
    for block in bounds["blocks"]:
        predict_block(
            validation_sessions[: block["train_end_index"]],
            block["test_sessions"],
            "walk_forward_validation",
        )
    holdout_train_end = max(0, bounds["holdout_start_index"] - bounds["purge_sessions"])
    predict_block(sessions[:holdout_train_end], bounds["holdout_sessions"], "untouched_holdout")
    if not predictions:
        raise ValueError("Walk-forward process produced no out-of-sample macro predictions")
    return pd.concat(predictions, ignore_index=True), bounds, macro_start


def summarize_evidence_counts(values: pd.Series) -> str:
    totals: dict[str, int] = {}
    for value in values.dropna():
        for key, count in json.loads(value).items():
            totals[key] = totals.get(key, 0) + int(count)
    return json.dumps(totals, sort_keys=True)


def build_macro_scoreboard(
    predictions: pd.DataFrame,
    macro_start: pd.Timestamp,
) -> pd.DataFrame:
    model_columns = [
        "zero_forward_excess_return",
        "persistence_last_observed_return",
        "ridge_technical_only_alpha_1_0",
        "ridge_technical_plus_macro_alpha_1_0",
    ]
    rows: list[dict[str, Any]] = []
    for segment, group in predictions.groupby("evaluation_segment"):
        for model in model_columns:
            valid = group[["target_value", model]].dropna()
            rows.append(
                {
                    "evaluation_layer": "forecast evaluation only",
                    "model_name": model,
                    "segment": segment,
                    "mae": float((valid["target_value"] - valid[model]).abs().mean()),
                    "rank_correlation": rank_correlation(valid["target_value"], valid[model]),
                    "observation_count": int(len(valid)),
                    "macro_eligible_start_date": macro_start.date().isoformat(),
                    "availability_evidence_level_counts": summarize_evidence_counts(
                        group["availability_evidence_level_counts"]
                    ),
                    "promotion_status": "not_promoted",
                    "promotion_reason": "promotion criteria not evaluated yet",
                }
            )
    scoreboard = pd.DataFrame(rows)
    promotion_pass = True
    reasons = []
    for segment in ["walk_forward_validation", "untouched_holdout"]:
        seg = scoreboard[scoreboard["segment"] == segment].set_index("model_name")
        macro = seg.loc["ridge_technical_plus_macro_alpha_1_0"]
        technical = seg.loc["ridge_technical_only_alpha_1_0"]
        zero = seg.loc["zero_forward_excess_return"]
        if not (macro["mae"] < technical["mae"] and macro["mae"] < zero["mae"]):
            promotion_pass = False
            reasons.append(f"{segment}: macro MAE did not beat technical-only and zero")
        if not (macro["rank_correlation"] > 0):
            promotion_pass = False
            reasons.append(f"{segment}: macro rank correlation was not positive")
    status = "promoted" if promotion_pass else "not_promoted"
    reason = "meets fixed MI-3 macro forecast criteria" if promotion_pass else "; ".join(reasons)
    mask = scoreboard["model_name"] == "ridge_technical_plus_macro_alpha_1_0"
    scoreboard.loc[mask, "promotion_status"] = status
    scoreboard.loc[mask, "promotion_reason"] = reason
    scoreboard.loc[~mask, "promotion_reason"] = "baseline comparator; no promotion claim"
    return scoreboard


def write_macro_scoreboard_reports(
    scoreboard: pd.DataFrame,
    report_root: Path,
) -> tuple[Path, Path]:
    report_root.mkdir(parents=True, exist_ok=True)
    json_path = report_root / "macro_forecast_scoreboard.json"
    md_path = report_root / "macro_forecast_scoreboard.md"
    json_path.write_text(
        json.dumps(scoreboard.replace({np.nan: None}).to_dict(orient="records"), indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# MI-3 Macro Forecast Scoreboard",
        "",
        "Evaluation layer: forecast evaluation only.",
        "",
        "| model | segment | mae | rank_correlation | obs | macro_start | promotion |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in scoreboard.itertuples(index=False):
        lines.append(
            f"| {row.model_name} | {row.segment} | {row.mae:.6f} | "
            f"{row.rank_correlation:.6f} | {row.observation_count} | "
            f"{row.macro_eligible_start_date} | {row.promotion_status} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def run_mi3_macro_vintage_forecast(
    *,
    mi1_data_root: Path,
    mi2_data_root: Path,
    mi3_data_root: Path,
    report_root: Path,
    macro_config_path: Path = Path("configs/intelligence/macro_series_mi3.yaml"),
    registry_path: Path = Path("configs/intelligence/mi2_research_registry.yaml"),
    adapter: MacroVintageSource | None = None,
) -> Mi3RunResult:
    source_config, series = load_macro_series_config(macro_config_path)
    validate_mi1_availability_for_mi3(mi1_data_root)
    technical_features, targets = load_mi2_panels(mi2_data_root)
    decision_sessions = list(pd.Index(technical_features["session_date"].unique()).sort_values())
    if not decision_sessions:
        raise ValueError("MI-2 feature panel has no decision sessions")
    observation_start = decision_sessions[0].date()
    observation_end = decision_sessions[-1].date()
    source = adapter or FredVintageAdapter()
    responses = source.fetch_vintage_observations(series, observation_start, observation_end)
    vintage_capabilities = [
        {
            "series_id": capability.series_id,
            "vintage_start_date": capability.vintage_start_date.isoformat(),
            "vintage_end_date": capability.vintage_end_date.isoformat(),
            "requested_effective_realtime_start": (
                capability.requested_effective_realtime_start.isoformat()
            ),
            "requested_effective_realtime_end": (
                capability.requested_effective_realtime_end.isoformat()
            ),
        }
        for capability in getattr(source, "vintage_capabilities", [])
    ]

    raw_root = mi3_data_root / "raw"
    manifest_root = mi3_data_root / "manifests"
    normalized_root = mi3_data_root / "normalized"
    normalized_root.mkdir(parents=True, exist_ok=True)
    manifest = write_macro_raw_snapshots(responses, raw_root, manifest_root, source.source_name)
    observations = normalize_macro_observations(responses, manifest)
    if observations.empty:
        raise ValueError("No macro observations returned by vintage source")
    if (observations["availability_evidence_level"] == "unverified").all():
        raise ValueError("All macro observations lack valid provider vintage periods")
    asof_panel = build_macro_asof_panel(decision_sessions, observations)
    macro_features = build_macro_feature_panel(asof_panel)
    registry = load_registry_rules(registry_path)
    predictions, bounds, macro_start = build_macro_predictions(
        technical_features,
        targets,
        macro_features,
        registry,
    )
    scoreboard = build_macro_scoreboard(predictions, macro_start)

    observations.to_parquet(normalized_root / "macro_vintage_observation.parquet", index=False)
    asof_panel.to_parquet(normalized_root / "macro_asof_panel.parquet", index=False)
    macro_features.to_parquet(mi3_data_root / "macro_feature_panel.parquet", index=False)
    predictions.to_parquet(mi3_data_root / "walk_forward_macro_predictions.parquet", index=False)
    scoreboard.to_parquet(mi3_data_root / "macro_forecast_scoreboard.parquet", index=False)
    md_path, json_path = write_macro_scoreboard_reports(scoreboard, report_root)

    validation_sessions = bounds["validation_sessions"]
    holdout_sessions = bounds["holdout_sessions"]
    output_paths = {
        "raw_root": str(raw_root),
        "macro_raw_snapshot_manifest": str(manifest_root / "macro_raw_snapshot_manifest.parquet"),
        "macro_vintage_observation": str(normalized_root / "macro_vintage_observation.parquet"),
        "macro_asof_panel": str(normalized_root / "macro_asof_panel.parquet"),
        "macro_feature_panel": str(mi3_data_root / "macro_feature_panel.parquet"),
        "walk_forward_macro_predictions": str(
            mi3_data_root / "walk_forward_macro_predictions.parquet"
        ),
        "macro_forecast_scoreboard": str(mi3_data_root / "macro_forecast_scoreboard.parquet"),
        "scoreboard_markdown": str(md_path),
        "scoreboard_json": str(json_path),
    }
    return Mi3RunResult(
        source_provenance={
            "source_id": source_config["source_id"],
            "source_name": source.source_name,
            "raw_handling": source_config["raw_data_handling"],
        },
        macro_series_count=len(series),
        macro_availability_evidence_level=MACRO_AVAILABILITY_EVIDENCE_LEVEL,
        macro_eligible_start_date=macro_start.date().isoformat(),
        validation_start_date=validation_sessions[0].date().isoformat(),
        validation_end_date=validation_sessions[-1].date().isoformat(),
        holdout_start_date=holdout_sessions[0].date().isoformat(),
        holdout_end_date=holdout_sessions[-1].date().isoformat(),
        row_counts={
            "macro_vintage_observation": int(len(observations)),
            "macro_asof_panel": int(len(asof_panel)),
            "macro_feature_panel": int(len(macro_features)),
            "walk_forward_macro_predictions": int(len(predictions)),
            "macro_forecast_scoreboard": int(len(scoreboard)),
        },
        model_count=4,
        output_paths=output_paths,
        scoreboard_summary=scoreboard[
            ["model_name", "segment", "mae", "rank_correlation", "promotion_status"]
        ].to_dict(orient="records"),
        vintage_capabilities=vintage_capabilities,
    )
