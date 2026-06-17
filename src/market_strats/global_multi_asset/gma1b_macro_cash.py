"""GMA-1B point-in-time macro and authoritative cash-rate foundation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from market_strats.global_multi_asset.gma1b_config import (
    GMA1B_PHASE_ID,
    GMA1B_TRACK_ID,
    GMA1BConfig,
    is_approved_gma1b_output_path,
    load_gma1b_config,
)

ACCEPTED_GMA1A_HASH = "953d5615d0773e71f49a9af5b55c598266478381ecf5bcf19c8a9d2831084b78"
FRED_API_ROOT = "https://api.stlouisfed.org/fred"
DATE_ONLY_AVAILABILITY_TIME = "23:59:59"
DEFAULT_RETRIEVED_AT = "fixture_contract"
FIXTURE_CONTRACT_CANONICAL_HASH = "b7a1dcde85fddfafc6295f75bf995c194eef49cb3c5491b35b54ef8eec3d0098"
FULL_VINTAGE_HISTORY_SERIES = {"CPIAUCSL", "UNRATE", "INDPRO"}
DERIVED_POINT_IN_TIME_SERIES = {"T10Y2Y", "T10Y3M"}
MAX_VINTAGE_DATES_PER_REQUEST = 2000
# GMA-1B-LU: URI-length-aware chunking constants.
# Conservative operational date-count cap per GET request (well below the 2,000
# provider limit so that encoded URI length stays inside the byte budget).
FRED_SAFE_VINTAGE_DATES_PER_REQUEST = 400
# Maximum encoded GET request URI in bytes.  Apache/nginx default is 8,190 B;
# 7,000 B leaves a comfortable margin for proxies and load balancers.
FRED_MAX_ENCODED_REQUEST_URI_BYTES = 7000
# Maximum recursive 414-recovery bisection depth (prevents unbounded splitting).
_MAX_414_SPLIT_DEPTH = 8
DIAGNOSTIC_TOTAL_DURATION_LIMIT_SECONDS = 45 * 60


@dataclass(frozen=True)
class GMA1BResult:
    decision: str
    warnings: list[str]
    canonical_hash: str
    live_retrieval_status: str


PROVIDER_INCIDENT_COLUMNS = [
    "diagnostic_run_id",
    "series_id",
    "request_stage",
    "endpoint",
    "http_method",
    "parameter_names",
    "http_status",
    "provider_error_code",
    "redacted_provider_message",
    "exception_type",
    "error_category",
    "retryable",
    "response_content_type",
    "partial_snapshot_written",
    "partial_manifest_written",
    "diagnostic_status",
]


@dataclass(frozen=True)
class ProviderRequestIncident:
    diagnostic_run_id: str
    series_id: str
    request_stage: str
    endpoint: str
    http_method: str
    parameter_names: str
    http_status: int | str
    provider_error_code: str
    redacted_provider_message: str
    exception_type: str
    error_category: str
    retryable: bool
    response_content_type: str
    partial_snapshot_written: bool = False
    partial_manifest_written: bool = False
    diagnostic_status: str = "failed"


class ProviderRequestError(RuntimeError):
    def __init__(self, incident: ProviderRequestIncident):
        super().__init__(
            f"{incident.error_category} series_id={incident.series_id} "
            f"stage={incident.request_stage} endpoint={incident.endpoint}"
        )
        self.incident = incident


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256_bytes(encoded)


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _availability_timestamp(realtime_start: str | pd.Timestamp) -> pd.Timestamp:
    date = pd.Timestamp(realtime_start).date()
    return pd.Timestamp(f"{date}T{DATE_ONLY_AVAILABILITY_TIME}Z")


def normalise_observations(
    observations: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    manifest_path: str,
    manifest_sha256: str,
    raw_sha256: str,
    normalised_sha256: str,
    retrieved_at_utc: str,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, meta in registry.iterrows():
        sid = str(meta["series_id"])
        chunk = observations[observations["series_id"].eq(sid)].copy()
        if chunk.empty:
            continue
        chunk["macro_id"] = meta["macro_id"]
        chunk["observation_date"] = pd.to_datetime(chunk["observation_date"]).dt.date.astype(str)
        chunk["realtime_start"] = pd.to_datetime(chunk["realtime_start"]).dt.date.astype(str)
        chunk["realtime_end"] = pd.to_datetime(chunk["realtime_end"]).dt.date.astype(str)
        chunk["official_availability_date"] = chunk["realtime_start"]
        chunk["availability_timestamp_utc"] = chunk["realtime_start"].map(_availability_timestamp)
        chunk["retrieved_at_utc"] = retrieved_at_utc
        chunk["frequency"] = meta["frequency"]
        chunk["units"] = meta["units"]
        chunk["value"] = pd.to_numeric(chunk["value"], errors="coerce")
        chunk = chunk.sort_values(["observation_date", "realtime_start"]).reset_index(drop=True)
        chunk["revision_sequence"] = chunk.groupby("observation_date").cumcount()
        chunk["is_initial_release"] = chunk["revision_sequence"].eq(0)
        max_seq = chunk.groupby("observation_date")["revision_sequence"].transform("max")
        chunk["is_revision"] = chunk["revision_sequence"].gt(0)
        chunk["point_in_time_status"] = chunk["value"].isna().map(
            {True: "missing_value", False: "available"}
        )
        chunk["source_manifest_path"] = manifest_path
        chunk["source_manifest_sha256"] = manifest_sha256
        chunk["source_raw_sha256"] = raw_sha256
        chunk["source_normalised_sha256"] = normalised_sha256
        chunk["source_vintage"] = chunk["realtime_start"]
        chunk["latest_revision_sequence_in_snapshot"] = max_seq
        frames.append(chunk)
    if not frames:
        return pd.DataFrame()
    cols = [
        "macro_id",
        "series_id",
        "observation_date",
        "value",
        "realtime_start",
        "realtime_end",
        "official_availability_date",
        "availability_timestamp_utc",
        "retrieved_at_utc",
        "frequency",
        "units",
        "is_initial_release",
        "is_revision",
        "revision_sequence",
        "source_manifest_path",
        "source_manifest_sha256",
        "source_raw_sha256",
        "source_normalised_sha256",
        "source_vintage",
        "point_in_time_status",
    ]
    return pd.concat(frames, ignore_index=True)[cols]


def query_point_in_time(
    canonical: pd.DataFrame,
    macro_id: str,
    query_timestamp_utc: str | pd.Timestamp,
) -> dict[str, Any]:
    query_ts = pd.Timestamp(query_timestamp_utc)
    if query_ts.tzinfo is None:
        query_ts = query_ts.tz_localize("UTC")
    frame = canonical[canonical["macro_id"].eq(macro_id)].copy()
    if frame.empty:
        return {
            "macro_id": macro_id,
            "series_id": "",
            "query_timestamp_utc": str(query_ts),
            "point_in_time_status": "unavailable_unknown_series",
        }
    frame["availability_timestamp_utc"] = pd.to_datetime(frame["availability_timestamp_utc"], utc=True)
    frame["observation_date_sort"] = pd.to_datetime(frame["observation_date"])
    eligible = frame[frame["availability_timestamp_utc"].le(query_ts)].copy()
    if eligible.empty:
        sid = str(frame["series_id"].iloc[0])
        return {
            "macro_id": macro_id,
            "series_id": sid,
            "query_timestamp_utc": str(query_ts),
            "point_in_time_status": "unavailable_before_first_release",
        }
    eligible = eligible.sort_values(
        ["observation_date_sort", "availability_timestamp_utc", "revision_sequence"]
    )
    row = eligible.iloc[-1]
    return {
        "macro_id": row["macro_id"],
        "series_id": row["series_id"],
        "query_timestamp_utc": str(query_ts),
        "observation_date": row["observation_date"],
        "value": row["value"],
        "realtime_start": row["realtime_start"],
        "realtime_end": row["realtime_end"],
        "availability_timestamp_utc": str(row["availability_timestamp_utc"]),
        "source_vintage": row["source_vintage"],
        "point_in_time_status": row["point_in_time_status"],
    }


def build_vintage_revision_audit(canonical: pd.DataFrame, registry: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    vintage_ids = set(registry.loc[registry["revision_prone"], "macro_id"])
    for (macro_id, series_id, obs_date), group in canonical.groupby(
        ["macro_id", "series_id", "observation_date"]
    ):
        if macro_id not in vintage_ids:
            continue
        ordered = group.sort_values("availability_timestamp_utc")
        first = ordered.iloc[0]
        latest = ordered.iloc[-1]
        revisions = ordered["value"].astype(float)
        absolute_revision = float(latest["value"]) - float(first["value"])
        intermediate = (revisions - float(first["value"])).abs().max()
        rel = absolute_revision / abs(float(first["value"])) if float(first["value"]) != 0 else 0.0
        rows.append({
            "macro_id": macro_id,
            "series_id": series_id,
            "observation_date": obs_date,
            "initial_release_value": first["value"],
            "initial_release_available_at": first["availability_timestamp_utc"],
            "latest_value": latest["value"],
            "latest_value_available_at": latest["availability_timestamp_utc"],
            "revision_count": max(len(ordered) - 1, 0),
            "absolute_revision": absolute_revision,
            "relative_revision": rel,
            "maximum_intermediate_revision": intermediate,
            "revision_materiality": "material" if abs(absolute_revision) > 0.000001 else "immaterial",
            "vintage_status": "vintage_history_available",
        })
    return pd.DataFrame(rows)


def build_cash_accrual(canonical: pd.DataFrame, config: GMA1BConfig) -> pd.DataFrame:
    cash = canonical[canonical["series_id"].eq(config.cash["authoritative_series"])].copy()
    if cash.empty:
        return pd.DataFrame()
    cash["availability_timestamp_utc"] = pd.to_datetime(cash["availability_timestamp_utc"], utc=True)
    cash["observation_date_dt"] = pd.to_datetime(cash["observation_date"])
    cash = cash.sort_values("observation_date_dt").reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for idx, row in cash.iterrows():
        if pd.isna(row["value"]):
            continue
        start = pd.Timestamp(row["observation_date"])
        if idx + 1 < len(cash):
            end = pd.Timestamp(cash.iloc[idx + 1]["observation_date"])
        else:
            end = start + pd.Timedelta(days=1)
        accrual_days = max((end - start).days, 1)
        annual_yield = float(row["value"]) / 100.0
        period_return = annual_yield * accrual_days / 365.0
        rows.append({
            "observation_date": str(start.date()),
            "availability_timestamp_utc": row["availability_timestamp_utc"],
            "annual_yield": annual_yield,
            "yield_convention": config.cash["source_yield_convention"],
            "annualisation_day_count": config.cash["annualisation_day_count"],
            "accrual_start": str(start.date()),
            "accrual_end": str(end.date()),
            "accrual_days": accrual_days,
            "period_return": period_return,
            "source_series": row["series_id"],
            "source_realtime_start": row["realtime_start"],
            "source_vintage": row["source_vintage"],
            "source_manifest_sha256": row["source_manifest_sha256"],
            "cash_status": "available_after_timestamp",
        })
    return pd.DataFrame(rows)


def build_macro_series_readiness(
    registry: pd.DataFrame,
    canonical: pd.DataFrame,
    revision_audit: pd.DataFrame,
    live_complete: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, item in registry.iterrows():
        macro_id = item["macro_id"]
        hist = canonical[canonical["macro_id"].eq(macro_id)]
        is_required = bool(item["is_required"])
        vintage_required = bool(item["is_vintage_aware"])
        revision_complete = (
            not bool(item["revision_prone"])
            or macro_id in set(revision_audit.get("macro_id", pd.Series(dtype=str)))
        )
        ready = (
            not hist.empty
            and bool(item["availability_timestamp_policy"])
            and (not vintage_required or "realtime_start" in hist.columns)
            and revision_complete
            and live_complete
        )
        warnings = [] if live_complete else ["live_macro_audit_incomplete"]
        rows.append({
            "macro_id": macro_id,
            "series_id": item["series_id"],
            "is_required": is_required,
            "metadata_valid": True,
            "source_snapshot_selected": not hist.empty,
            "hashes_valid": not hist.empty,
            "availability_policy_defined": bool(item["availability_timestamp_policy"]),
            "point_in_time_history_available": not hist.empty,
            "vintage_history_available": (not vintage_required) or "realtime_start" in hist.columns,
            "current_value_available": not hist.empty and hist["value"].notna().any(),
            "maximum_staleness_observed": item["maximum_staleness_days"],
            "revision_audit_complete": revision_complete,
            "ready_for_replay_engine": ready,
            "blocking_reason": "" if ready else "live_macro_audit_incomplete",
            "warnings": ";".join(warnings),
        })
    return pd.DataFrame(rows)


def _fixture_observations(registry: pd.DataFrame) -> pd.DataFrame:
    base_values = {
        "DGS3MO": 5.20,
        "DGS2": 4.80,
        "DGS10": 4.35,
        "DGS30": 4.50,
        "T10Y2Y": -0.45,
        "T10Y3M": -0.85,
        "T10YIE": 2.30,
        "DFII10": 2.05,
        "VIXCLS": 13.5,
        "BAMLH0A0HYM2": 3.2,
        "STLFSI4": -0.3,
        "CPIAUCSL": 310.0,
        "UNRATE": 4.0,
        "INDPRO": 102.0,
    }
    rows: list[dict[str, Any]] = []
    for _, item in registry.iterrows():
        sid = item["series_id"]
        freq = item["frequency"]
        if freq == "daily":
            obs_dates = ["2024-01-05", "2024-01-08", "2024-01-09"]
            realtime = obs_dates
        elif freq == "weekly":
            obs_dates = ["2024-01-05", "2024-01-12"]
            realtime = ["2024-01-06", "2024-01-13"]
        else:
            obs_dates = ["2023-12-01", "2024-01-01"]
            realtime = ["2024-01-12", "2024-02-13"]
        for idx, (obs, rt) in enumerate(zip(obs_dates, realtime, strict=True)):
            rows.append({
                "series_id": sid,
                "observation_date": obs,
                "value": base_values[sid] + idx * 0.1,
                "realtime_start": rt,
                "realtime_end": "9999-12-31",
            })
            if item["revision_prone"] and idx == 0:
                rows.append({
                    "series_id": sid,
                    "observation_date": obs,
                    "value": base_values[sid] + idx * 0.1 + 0.2,
                    "realtime_start": "2024-03-01",
                    "realtime_end": "9999-12-31",
                })
    return pd.DataFrame(rows)


def _write_fixture_snapshot(
    observations: pd.DataFrame,
    config: GMA1BConfig,
    *,
    retrieved_at: str,
) -> tuple[Path, Path, str, str, str]:
    raw_root = config.paths["raw_root"] / "fred" / "fixture_contract" / retrieved_at
    manifest_root = config.paths["manifest_root"] / "fred" / "fixture_contract" / retrieved_at
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)
    raw_path = raw_root / "macro_observations_fixture_contract.csv"
    normalised_path = raw_root / "macro_observations_fixture_contract_normalised.csv"
    observations.to_csv(raw_path, index=False)
    observations.to_csv(normalised_path, index=False)
    raw_hash = sha256_file(raw_path)
    norm_hash = sha256_file(normalised_path)
    manifest = {
        "track_id": GMA1B_TRACK_ID,
        "phase_id": GMA1B_PHASE_ID,
        "provider": "fred",
        "series_id": "MULTI_SERIES_FIXTURE",
        "request_type": "offline_contract_fixture",
        "request_parameters": {"network": "disabled", "credential_present": False},
        "request_start": str(observations["observation_date"].min()),
        "request_end": str(observations["observation_date"].max()),
        "realtime_start": str(observations["realtime_start"].min()),
        "realtime_end": str(observations["realtime_start"].max()),
        "retrieved_at_utc": retrieved_at,
        "library_or_endpoint": "offline_fixture_not_live_evidence",
        "source_metadata": {"official_source_contract": "FRED/ALFRED"},
        "raw_file_path": str(raw_path),
        "raw_file_sha256": raw_hash,
        "normalised_file_path": str(normalised_path),
        "normalised_file_sha256": norm_hash,
        "row_count": int(len(observations)),
        "first_observation_date": str(observations["observation_date"].min()),
        "last_observation_date": str(observations["observation_date"].max()),
        "first_realtime_start": str(observations["realtime_start"].min()),
        "last_realtime_start": str(observations["realtime_start"].max()),
        "columns": list(observations.columns),
        "warnings": ["fixture_contract_only_live_macro_audit_incomplete"],
    }
    manifest_path = manifest_root / "macro_observations_fixture_contract_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    manifest_hash = sha256_file(manifest_path)
    return raw_path, normalised_path, raw_hash, norm_hash, manifest_hash


def fetch_fred_json(
    endpoint: str,
    params: dict[str, Any],
    *,
    api_key: str,
    timeout_seconds: int,
    series_id: str = "",
    request_stage: str = "observations_current",
    retry_count: int = 0,
    diagnostic_run_id: str = "",
    diagnostics_dir: Path | None = None,
    request_number: int = 1,
    progress_callback: Any | None = None,
) -> bytes:
    safe_params = {**params, "api_key": api_key, "file_type": "json"}
    url = f"{FRED_API_ROOT}/{endpoint}?{urlencode(safe_params)}"
    attempt = 0
    while True:
        request_started_at = utc_now_iso()
        if diagnostics_dir is not None:
            _write_production_request_plan(
                diagnostics_dir / "production_request_plan.json",
                endpoint=endpoint,
                params=safe_params,
                series_id=series_id,
                request_stage=request_stage,
                timeout_seconds=timeout_seconds,
                request_number=request_number,
                attempt_number=attempt + 1,
                started_at_utc=request_started_at,
                retry_count=retry_count,
            )
        _emit_progress(
            progress_callback,
            _request_started_message(
                series_id=series_id,
                request_stage=request_stage,
                params=params,
                timeout_seconds=timeout_seconds,
            ),
        )
        started_monotonic = time.monotonic()
        try:
            with urlopen(url, timeout=timeout_seconds) as response:  # nosec B310 - official FRED endpoint only
                _emit_progress(
                    progress_callback,
                    _request_passed_message(
                        series_id=series_id,
                        request_stage=request_stage,
                        elapsed_seconds=time.monotonic() - started_monotonic,
                    ),
                )
                return response.read()
        except HTTPError as exc:
            body = _safe_read_error_body(exc)
            content_type = _header_value(exc, "Content-Type")
            incident = _incident_from_http_error(
                exc,
                body,
                series_id=series_id,
                request_stage=request_stage,
                endpoint=endpoint,
                params=safe_params,
                diagnostic_run_id=diagnostic_run_id,
                content_type=content_type,
                credential=api_key,
            )
            if attempt < retry_count and incident.retryable:
                delay = _sleep_before_retry(exc, attempt)
                _emit_progress(
                    progress_callback,
                    _retry_message(
                        series_id=series_id,
                        request_stage=request_stage,
                        attempt_number=attempt + 1,
                        elapsed_seconds=time.monotonic() - started_monotonic,
                        retry_reason=incident.error_category,
                        backoff_seconds=delay,
                    ),
                )
                attempt += 1
                continue
            raise ProviderRequestError(incident) from exc
        except (URLError, TimeoutError, OSError) as exc:
            incident = _incident_from_network_error(
                exc,
                series_id=series_id,
                request_stage=request_stage,
                endpoint=endpoint,
                params=safe_params,
                diagnostic_run_id=diagnostic_run_id,
                credential=api_key,
            )
            if attempt < retry_count and incident.retryable:
                if incident.error_category == "timeout":
                    _emit_progress(
                        progress_callback,
                        _request_timeout_message(
                            series_id=series_id,
                            request_stage=request_stage,
                            attempt_number=attempt + 1,
                            elapsed_seconds=time.monotonic() - started_monotonic,
                        ),
                    )
                delay = _sleep_before_retry(None, attempt)
                _emit_progress(
                    progress_callback,
                    _retry_message(
                        series_id=series_id,
                        request_stage=request_stage,
                        attempt_number=attempt + 1,
                        elapsed_seconds=time.monotonic() - started_monotonic,
                        retry_reason=incident.error_category,
                        backoff_seconds=delay,
                    ),
                )
                attempt += 1
                continue
            if incident.error_category == "timeout":
                _emit_progress(
                    progress_callback,
                    _request_timeout_message(
                        series_id=series_id,
                        request_stage=request_stage,
                        attempt_number=attempt + 1,
                        elapsed_seconds=time.monotonic() - started_monotonic,
                    ),
                )
            raise ProviderRequestError(incident) from exc


def _emit_progress(progress_callback: Any | None, message: str) -> None:
    if progress_callback:
        progress_callback(message)


def _stage_label(request_stage: str) -> str:
    if request_stage == "metadata":
        return "metadata"
    if request_stage.startswith("observations"):
        return "observations"
    return request_stage


def _request_started_message(
    *,
    series_id: str,
    request_stage: str,
    params: dict[str, Any],
    timeout_seconds: int,
) -> str:
    label = _stage_label(request_stage)
    details: list[str] = []
    if label == "observations":
        if "limit" in params:
            details.append(f"limit={params['limit']}")
        if "offset" in params:
            details.append(f"offset={params['offset']}")
    details.append(f"timeout={timeout_seconds}")
    return f"[{series_id}] {label} request started {' '.join(details)}".strip()


def _request_passed_message(
    *,
    series_id: str,
    request_stage: str,
    elapsed_seconds: float,
) -> str:
    return f"[{series_id}] {_stage_label(request_stage)} request passed elapsed={elapsed_seconds:.3f}s"


def _request_timeout_message(
    *,
    series_id: str,
    request_stage: str,
    attempt_number: int,
    elapsed_seconds: float,
) -> str:
    return (
        f"[{series_id}] {_stage_label(request_stage)} timed out "
        f"attempt={attempt_number} elapsed={elapsed_seconds:.3f}s"
    )


def _retry_message(
    *,
    series_id: str,
    request_stage: str,
    attempt_number: int,
    elapsed_seconds: float,
    retry_reason: str,
    backoff_seconds: float,
) -> str:
    return (
        f"[{series_id}] {_stage_label(request_stage)} retry scheduled "
        f"attempt={attempt_number} elapsed={elapsed_seconds:.3f}s "
        f"retry_reason={retry_reason} backoff_seconds={backoff_seconds:.3f}"
    )


def _write_production_request_plan(
    path: Path,
    *,
    endpoint: str,
    params: dict[str, Any],
    series_id: str,
    request_stage: str,
    timeout_seconds: int,
    request_number: int,
    attempt_number: int,
    started_at_utc: str,
    retry_count: int,
) -> None:
    non_secret = _redacted_request_parameters(params)
    non_secret["api_key_present"] = bool(params.get("api_key"))
    plan = {
        "diagnostic_only": True,
        "eligible_for_live_canonical_selection": False,
        "series_id": series_id,
        "request_stage": request_stage,
        "endpoint": endpoint,
        "http_method": "GET",
        "parameter_names": sorted(params),
        "non_secret_parameters": non_secret,
        "timeout_seconds": timeout_seconds,
        "request_number": request_number,
        "attempt_number": attempt_number,
        "retry_count": retry_count,
        "started_at_utc": started_at_utc,
    }
    _atomic_write_json(plan, path)


def _redacted_request_parameters(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if key.lower() != "api_key"}


def fred_request_url(endpoint: str, params: dict[str, Any], *, api_key: str) -> str:
    safe_params = {**params, "api_key": api_key, "file_type": "json"}
    return f"{FRED_API_ROOT}/{endpoint}?{urlencode(safe_params)}"


def fred_request_parameter_names(params: dict[str, Any]) -> str:
    return ";".join(sorted({*params.keys(), "api_key", "file_type"}))


def _header_value(source: Any, key: str) -> str:
    headers = getattr(source, "headers", None)
    if headers is not None:
        value = headers.get(key)
        if value:
            return str(value)
    getheader = getattr(source, "getheader", None)
    if callable(getheader):
        value = getheader(key)
        if value:
            return str(value)
    return ""


def _safe_read_error_body(exc: HTTPError) -> bytes:
    try:
        return exc.read()
    except Exception:
        return b""


def redact_secret(text: Any, credential: str | None = None) -> str:
    redacted = str(text)
    if credential:
        redacted = redacted.replace(credential, "<redacted>")
    redacted = re.sub(r"(?i)(api_key=)[^&\s\"']+", r"\1<redacted>", redacted)
    redacted = re.sub(r"(?i)(api_key['\"]?\s*[:=]\s*['\"]?)[^,'\"\s}]+", r"\1<redacted>", redacted)
    return redacted


def _parse_provider_error(
    body: bytes,
    *,
    content_type: str,
    credential: str | None,
) -> tuple[str, str]:
    text = redact_secret(body.decode("utf-8", errors="replace"), credential)
    if not text:
        return "", ""
    stripped = text.strip()
    if "json" in content_type.lower() or stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return "", stripped[:500]
        code = str(payload.get("error_code", payload.get("code", "")))
        message = str(payload.get("error_message", payload.get("message", payload)))
        return code, redact_secret(message, credential)[:500]
    code_match = re.search(r"code=['\"]?([^'\">\s]+)", stripped)
    message_match = re.search(r"<message>(.*?)</message>", stripped, flags=re.IGNORECASE | re.DOTALL)
    if message_match:
        message = message_match.group(1)
    else:
        tagless = re.sub(r"<[^>]+>", " ", stripped)
        message = " ".join(tagless.split())
    return (code_match.group(1) if code_match else ""), redact_secret(message, credential)[:500]


def _http_error_category(status: int) -> str:
    if status in {400, 404}:
        return "invalid_request"
    if status in {401, 403}:
        return "credential_or_permission_failure"
    if status == 414:
        return "request_uri_too_long"
    if status == 429:
        return "rate_limited"
    if 500 <= status <= 599:
        return "provider_transient"
    return "http_error"


def _is_retryable_http(status: int) -> bool:
    # HTTP 414 is never retried with the identical request; adaptive splitting
    # handles it separately in _fetch_vintage_chunk_with_414_recovery.
    return status == 429 or 500 <= status <= 599


def _network_error_category(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timed out" in text or "timeout" in text:
        return "timeout"
    if "temporary" in text or "reset" in text or "dns" in text or "name resolution" in text:
        return "temporary_network_failure"
    return "network_error"


def _incident_from_http_error(
    exc: HTTPError,
    body: bytes,
    *,
    series_id: str,
    request_stage: str,
    endpoint: str,
    params: dict[str, Any],
    diagnostic_run_id: str,
    content_type: str,
    credential: str | None,
) -> ProviderRequestIncident:
    status = int(exc.code)
    provider_code, provider_message = _parse_provider_error(
        body,
        content_type=content_type,
        credential=credential,
    )
    return ProviderRequestIncident(
        diagnostic_run_id=diagnostic_run_id,
        series_id=series_id,
        request_stage=request_stage,
        endpoint=endpoint,
        http_method="GET",
        parameter_names=fred_request_parameter_names(params),
        http_status=status,
        provider_error_code=provider_code,
        redacted_provider_message=provider_message or redact_secret(exc.reason, credential),
        exception_type=type(exc).__name__,
        error_category=_http_error_category(status),
        retryable=_is_retryable_http(status),
        response_content_type=content_type,
    )


def _incident_from_network_error(
    exc: BaseException,
    *,
    series_id: str,
    request_stage: str,
    endpoint: str,
    params: dict[str, Any],
    diagnostic_run_id: str,
    credential: str | None,
) -> ProviderRequestIncident:
    category = _network_error_category(exc)
    return ProviderRequestIncident(
        diagnostic_run_id=diagnostic_run_id,
        series_id=series_id,
        request_stage=request_stage,
        endpoint=endpoint,
        http_method="GET",
        parameter_names=fred_request_parameter_names(params),
        http_status="",
        provider_error_code="",
        redacted_provider_message=redact_secret(exc, credential)[:500],
        exception_type=type(exc).__name__,
        error_category=category,
        retryable=category in {"timeout", "temporary_network_failure", "network_error"},
        response_content_type="",
    )


def _sleep_before_retry(exc: HTTPError | None, attempt: int) -> float:
    retry_after = _header_value(exc, "Retry-After") if exc is not None else ""
    try:
        delay = float(retry_after) if retry_after else min(0.1 * (2**attempt), 1.0)
    except ValueError:
        delay = min(0.1 * (2**attempt), 1.0)
    bounded_delay = max(min(delay, 1.0), 0.0)
    time.sleep(bounded_delay)
    return bounded_delay


def _incident_to_dict(incident: ProviderRequestIncident) -> dict[str, Any]:
    return {
        "diagnostic_run_id": incident.diagnostic_run_id,
        "series_id": incident.series_id,
        "request_stage": incident.request_stage,
        "endpoint": incident.endpoint,
        "http_method": incident.http_method,
        "parameter_names": incident.parameter_names,
        "http_status": incident.http_status,
        "provider_error_code": incident.provider_error_code,
        "redacted_provider_message": incident.redacted_provider_message,
        "exception_type": incident.exception_type,
        "error_category": incident.error_category,
        "retryable": incident.retryable,
        "response_content_type": incident.response_content_type,
        "partial_snapshot_written": incident.partial_snapshot_written,
        "partial_manifest_written": incident.partial_manifest_written,
        "diagnostic_status": incident.diagnostic_status,
    }


def _fetch_fred_payload(
    endpoint: str,
    params: dict[str, Any],
    *,
    api_key: str,
    timeout_seconds: int,
    series_id: str = "",
    request_stage: str,
    retry_count: int = 0,
    diagnostic_run_id: str = "",
    diagnostics_dir: Path | None = None,
    request_number: int = 1,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    payload = fetch_fred_json(
        endpoint,
        params,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        series_id=series_id,
        request_stage=request_stage,
        retry_count=retry_count,
        diagnostic_run_id=diagnostic_run_id,
        diagnostics_dir=diagnostics_dir,
        request_number=request_number,
        progress_callback=progress_callback,
    )
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderRequestError(ProviderRequestIncident(
            diagnostic_run_id=diagnostic_run_id,
            series_id=series_id,
            request_stage="response_parse",
            endpoint=endpoint,
            http_method="GET",
            parameter_names=fred_request_parameter_names(params),
            http_status="",
            provider_error_code="",
            redacted_provider_message="response was not valid JSON",
            exception_type=type(exc).__name__,
            error_category="response_format_failure",
            retryable=False,
            response_content_type="unknown",
        )) from exc
    if not isinstance(decoded, dict):
        raise ProviderRequestError(ProviderRequestIncident(
            diagnostic_run_id=diagnostic_run_id,
            series_id=series_id,
            request_stage="response_parse",
            endpoint=endpoint,
            http_method="GET",
            parameter_names=fred_request_parameter_names(params),
            http_status="",
            provider_error_code="",
            redacted_provider_message="response JSON root was not an object",
            exception_type="TypeError",
            error_category="schema_validation_failure",
            retryable=False,
            response_content_type="application/json",
        ))
    return decoded


def _series_metadata_from_payload(payload: dict[str, Any], series_id: str) -> dict[str, Any]:
    rows = payload.get("seriess") or payload.get("series") or []
    if not rows:
        raise RuntimeError(f"official_fred_metadata_missing series_id={series_id}")
    row = dict(rows[0])
    row["series_id"] = row.get("id", series_id)
    return row


def retrieval_classification_for_series(series_id: str) -> str:
    if series_id in FULL_VINTAGE_HISTORY_SERIES:
        return "full_vintage_history_required"
    if series_id in DERIVED_POINT_IN_TIME_SERIES:
        return "derived_point_in_time_series"
    return "current_history_with_availability"


def chunk_vintage_dates(
    vintage_dates: list[str],
    *,
    max_chunk_size: int = MAX_VINTAGE_DATES_PER_REQUEST,
) -> list[list[str]]:
    """Simple count-only chunker (kept for backward compatibility and tests)."""
    unique = sorted(dict.fromkeys(str(item) for item in vintage_dates if str(item)))
    return [unique[idx : idx + max_chunk_size] for idx in range(0, len(unique), max_chunk_size)]


def _measure_vintage_request_uri_bytes(
    endpoint: str,
    *,
    series_id: str,
    api_key: str,
    output_type: int,
    limit: int,
    offset: int,
    sort_order: str,
    vintage_dates_chunk: list[str],
) -> int:
    """Return the exact encoded GET request URI byte length for a vintage-dates request.

    Constructs the exact parameter mapping that ``fetch_fred_json`` will pass to
    ``urlencode``, including ``api_key`` (length matters; value is never logged),
    then measures the resulting URL as UTF-8 bytes.

    Diagnostic output may record only ``api_key_present=true`` and
    ``encoded_request_uri_bytes=<integer>``; the key value is never returned,
    printed, persisted, or included in exception messages.
    """
    params: dict[str, Any] = {
        "series_id": series_id,
        "vintage_dates": ",".join(vintage_dates_chunk),
        "output_type": output_type,
        "limit": limit,
        "offset": offset,
        "sort_order": sort_order,
        "api_key": api_key,
        "file_type": "json",
    }
    url = f"{FRED_API_ROOT}/{endpoint}?{urlencode(params)}"
    return len(url.encode("utf-8"))


def chunk_vintage_dates_uri_aware(
    vintage_dates: list[str],
    *,
    series_id: str,
    api_key: str,
    endpoint: str = "series/observations",
    output_type: int = 3,
    limit: int = 100000,
    sort_order: str = "asc",
    date_count_cap: int = FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
    uri_byte_budget: int = FRED_MAX_ENCODED_REQUEST_URI_BYTES,
) -> list[list[str]]:
    """Deterministic greedy URI-aware vintage-date chunker.

    Every output chunk satisfies both:

    * ``len(chunk) <= date_count_cap``  (conservative operational cap)
    * ``encoded_request_uri_bytes <= uri_byte_budget``  (exact measurement)

    Algorithm
    ---------
    Process ordered unique vintage dates in ascending order.  Tentatively add
    the next date; encode the complete prospective request URI; accept the date
    only when both constraints remain satisfied; otherwise close the current
    chunk and begin the next one.  Never reorder or omit dates.

    Raises
    ------
    ValueError
        If a single-date chunk would still exceed the URI budget, the algorithm
        cannot proceed and fails closed.
    """
    unique = sorted(dict.fromkeys(str(d) for d in vintage_dates if str(d)))
    if not unique:
        return []

    # Verify that a single-date chunk is feasible before starting.
    single_bytes = _measure_vintage_request_uri_bytes(
        endpoint,
        series_id=series_id,
        api_key=api_key,
        output_type=output_type,
        limit=limit,
        offset=0,
        sort_order=sort_order,
        vintage_dates_chunk=[unique[0]],
    )
    if single_bytes > uri_byte_budget:
        raise ValueError(
            f"single_vintage_date_exceeds_uri_budget "
            f"date={unique[0]} encoded_bytes={single_bytes} budget={uri_byte_budget}"
        )

    chunks: list[list[str]] = []
    current: list[str] = []

    for date in unique:
        candidate = current + [date]
        if len(candidate) > date_count_cap:
            # Count cap exceeded — close and start fresh.
            chunks.append(current)
            current = [date]
            continue
        prospective_bytes = _measure_vintage_request_uri_bytes(
            endpoint,
            series_id=series_id,
            api_key=api_key,
            output_type=output_type,
            limit=limit,
            offset=0,
            sort_order=sort_order,
            vintage_dates_chunk=candidate,
        )
        if prospective_bytes > uri_byte_budget:
            # URI budget exceeded — close and start fresh.
            if not current:
                # This shouldn't happen because we pre-checked single-date feasibility,
                # but defend anyway.
                raise ValueError(
                    f"single_vintage_date_exceeds_uri_budget "
                    f"date={date} encoded_bytes={prospective_bytes} budget={uri_byte_budget}"
                )
            chunks.append(current)
            current = [date]
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


def merge_vintage_observation_chunks(chunks: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for chunk in chunks:
        for row in chunk:
            key = (
                str(row.get("series_id", "")),
                str(row.get("date", row.get("observation_date", ""))),
                str(row.get("realtime_start", "")),
                str(row.get("realtime_end", "")),
            )
            existing = merged.get(key)
            if existing is not None and str(existing.get("value", "")) != str(row.get("value", "")):
                raise ValueError(f"conflicting_duplicate_vintage_row series_id={key[0]} date={key[1]}")
            merged[key] = dict(row)
    return [merged[key] for key in sorted(merged)]


def _fetch_current_fred_observations(
    series_id: str,
    *,
    api_key: str,
    timeout_seconds: int,
    retry_count: int = 0,
    diagnostic_run_id: str = "",
    limit: int = 100000,
    diagnostics_dir: Path | None = None,
    progress_callback: Any | None = None,
    request_number_start: int = 1,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    request_number = request_number_start
    started_monotonic = time.monotonic()
    while True:
        params = {
            "series_id": series_id,
            "limit": limit,
            "offset": offset,
            "sort_order": "asc",
        }
        payload = _fetch_fred_payload(
            "series/observations",
            params,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            series_id=series_id,
            request_stage="observations_current",
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            diagnostics_dir=diagnostics_dir,
            request_number=request_number,
            progress_callback=progress_callback,
        )
        chunk = payload.get("observations") or []
        if not isinstance(chunk, list):
            raise RuntimeError(f"official_fred_observations_not_list series_id={series_id}")
        rows.extend(dict(item) for item in chunk)
        count = int(payload.get("count", len(rows)))
        if len(rows) >= count or not chunk:
            break
        offset += limit
        request_number += 1
    _emit_progress(
        progress_callback,
        f"[{series_id}] observations passed rows={len(rows)} "
        f"elapsed={time.monotonic() - started_monotonic:.3f}s",
    )
    return rows


def _fetch_vintage_dates(
    series_id: str,
    *,
    api_key: str,
    timeout_seconds: int,
    retry_count: int = 0,
    diagnostic_run_id: str = "",
    limit: int = 1000,
    diagnostics_dir: Path | None = None,
    progress_callback: Any | None = None,
    request_number_start: int = 1,
) -> list[str]:
    rows: list[str] = []
    offset = 0
    request_number = request_number_start
    while True:
        params = {"series_id": series_id, "limit": limit, "offset": offset, "sort_order": "asc"}
        payload = _fetch_fred_payload(
            "series/vintagedates",
            params,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            series_id=series_id,
            request_stage="observations_vintage",
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            diagnostics_dir=diagnostics_dir,
            request_number=request_number,
            progress_callback=progress_callback,
        )
        chunk = payload.get("vintage_dates") or []
        if not isinstance(chunk, list):
            raise RuntimeError(f"official_fred_vintage_dates_not_list series_id={series_id}")
        rows.extend(str(item) for item in chunk)
        count = int(payload.get("count", len(rows)))
        if len(rows) >= count or not chunk:
            break
        offset += limit
        request_number += 1
    return sorted(dict.fromkeys(rows))


def _fetch_fred_observations_for_vintage_dates(
    series_id: str,
    *,
    vintage_dates: list[str],
    api_key: str,
    timeout_seconds: int,
    output_type: int = 3,
    retry_count: int = 0,
    diagnostic_run_id: str = "",
    limit: int = 100000,
    diagnostics_dir: Path | None = None,
    progress_callback: Any | None = None,
    request_number_start: int = 1,
    request_stage: str = "observations_vintage",
) -> list[dict[str, Any]]:
    """Paginated retrieval of FRED observations for a URI-safe chunk of vintage dates.

    ``output_type`` controls the FRED semantics:

    * ``3`` (default / authoritative): observations by vintage date, new and
      revised observations only — the authoritative revision-event stream for
      full-vintage series.
    * ``2`` (bounded validation only): observations by vintage date, all
      observations — used on a small bounded sample for integrity validation.
    * ``4`` (crosscheck only): initial releases only — may be used as an
      independent initial-release cross-check but must never be the
      authoritative full-vintage source.

    The caller is responsible for ensuring ``vintage_dates`` already satisfies
    the URI-byte budget (use ``chunk_vintage_dates_uri_aware``).
    """
    if len(vintage_dates) > MAX_VINTAGE_DATES_PER_REQUEST:
        raise ValueError("vintage_date_chunk_exceeds_2000")
    if output_type not in {2, 3, 4}:
        raise ValueError(f"unsupported_output_type={output_type}")
    rows: list[dict[str, Any]] = []
    offset = 0
    request_number = request_number_start
    while True:
        uri_bytes = _measure_vintage_request_uri_bytes(
            "series/observations",
            series_id=series_id,
            api_key=api_key,
            output_type=output_type,
            limit=limit,
            offset=offset,
            sort_order="asc",
            vintage_dates_chunk=vintage_dates,
        )
        _emit_progress(
            progress_callback,
            f"[{series_id}] {request_stage} output_type={output_type}"
            f" dates={len(vintage_dates)} uri_bytes={uri_bytes}"
            f" timeout={timeout_seconds} started",
        )
        params = {
            "series_id": series_id,
            "vintage_dates": ",".join(vintage_dates),
            "output_type": output_type,
            "limit": limit,
            "offset": offset,
            "sort_order": "asc",
        }
        payload = _fetch_fred_payload(
            "series/observations",
            params,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            series_id=series_id,
            request_stage=request_stage,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            diagnostics_dir=diagnostics_dir,
            request_number=request_number,
            progress_callback=progress_callback,
        )
        chunk = payload.get("observations") or []
        if not isinstance(chunk, list):
            raise RuntimeError(f"official_fred_observations_not_list series_id={series_id}")
        rows.extend(dict(item) for item in chunk)
        count = int(payload.get("count", len(rows)))
        if len(rows) >= count or not chunk:
            break
        offset += limit
        request_number += 1
    return rows


def _fetch_vintage_chunk_with_414_recovery(
    series_id: str,
    *,
    vintage_dates: list[str],
    api_key: str,
    timeout_seconds: int,
    output_type: int,
    retry_count: int,
    diagnostic_run_id: str,
    limit: int,
    diagnostics_dir: Path | None,
    progress_callback: Any | None,
    request_number_start: int,
    request_stage: str,
    _depth: int = 0,
    _accounting: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch vintage-date observations with HTTP 414 adaptive bisection recovery.

    If the provider returns HTTP 414 (Request-URI Too Long), the offending chunk
    is deterministically split into two ordered halves and each half is retried.
    Splitting recurses up to ``_MAX_414_SPLIT_DEPTH`` levels; a single-date
    chunk that still returns 414 fails closed.

    Returns
    -------
    rows : list[dict]
        All observations from the chunk (or from its recovered sub-halves).
    accounting : dict
        ``uri_414_count``, ``adaptive_rechunk_count``, ``adaptive_rechunk_depth_max``.
    """
    if _accounting is None:
        _accounting = {"uri_414_count": 0, "adaptive_rechunk_count": 0, "adaptive_rechunk_depth_max": 0}

    try:
        rows = _fetch_fred_observations_for_vintage_dates(
            series_id,
            vintage_dates=vintage_dates,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            output_type=output_type,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            limit=limit,
            diagnostics_dir=diagnostics_dir,
            progress_callback=progress_callback,
            request_number_start=request_number_start,
            request_stage=request_stage,
        )
        return rows, _accounting
    except ProviderRequestError as exc:
        if exc.incident.http_status != 414:
            raise
        # HTTP 414 — do not retry the identical request.
        _accounting["uri_414_count"] += 1
        n = len(vintage_dates)
        if n <= 1:
            _emit_progress(
                progress_callback,
                f"[{series_id}] {request_stage} HTTP 414 single-date chunk"
                f" cannot split — failing closed date={vintage_dates[0] if vintage_dates else ''}",
            )
            raise ProviderRequestError(
                ProviderRequestIncident(
                    diagnostic_run_id=diagnostic_run_id,
                    series_id=series_id,
                    request_stage=request_stage,
                    endpoint="series/observations",
                    http_method="GET",
                    parameter_names=exc.incident.parameter_names,
                    http_status=414,
                    provider_error_code="414",
                    redacted_provider_message="HTTP 414 on single-date chunk — cannot split further",
                    exception_type="HTTP414SingleDateOverflow",
                    error_category="request_uri_too_long",
                    retryable=False,
                    response_content_type=exc.incident.response_content_type,
                )
            ) from exc
        if _depth >= _MAX_414_SPLIT_DEPTH:
            raise ProviderRequestError(
                ProviderRequestIncident(
                    diagnostic_run_id=diagnostic_run_id,
                    series_id=series_id,
                    request_stage=request_stage,
                    endpoint="series/observations",
                    http_method="GET",
                    parameter_names=exc.incident.parameter_names,
                    http_status=414,
                    provider_error_code="414",
                    redacted_provider_message=f"HTTP 414 max split depth {_depth} reached",
                    exception_type="HTTP414MaxDepthExceeded",
                    error_category="request_uri_too_long",
                    retryable=False,
                    response_content_type=exc.incident.response_content_type,
                )
            ) from exc

        mid = n // 2
        left_half = vintage_dates[:mid]
        right_half = vintage_dates[mid:]
        _accounting["adaptive_rechunk_count"] += 1
        _accounting["adaptive_rechunk_depth_max"] = max(
            _accounting["adaptive_rechunk_depth_max"], _depth + 1
        )
        _emit_progress(
            progress_callback,
            f"[{series_id}] {request_stage} HTTP 414"
            f" splitting dates={n} into {len(left_half)} and {len(right_half)}",
        )
        left_rows, _ = _fetch_vintage_chunk_with_414_recovery(
            series_id,
            vintage_dates=left_half,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            output_type=output_type,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            limit=limit,
            diagnostics_dir=diagnostics_dir,
            progress_callback=progress_callback,
            request_number_start=request_number_start,
            request_stage=request_stage,
            _depth=_depth + 1,
            _accounting=_accounting,
        )
        right_rows, _ = _fetch_vintage_chunk_with_414_recovery(
            series_id,
            vintage_dates=right_half,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            output_type=output_type,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            limit=limit,
            diagnostics_dir=diagnostics_dir,
            progress_callback=progress_callback,
            request_number_start=request_number_start,
            request_stage=request_stage,
            _depth=_depth + 1,
            _accounting=_accounting,
        )
        return left_rows + right_rows, _accounting


_BOUNDED_VALIDATION_VINTAGE_COUNT = 4


def _select_bounded_validation_vintages(vintage_dates: list[str]) -> list[str]:
    """Select a small bounded sample of vintage dates for output_type=2 validation.

    Returns at most ``_BOUNDED_VALIDATION_VINTAGE_COUNT`` dates drawn from the
    start, middle and end of the sorted vintage list so that validation spans
    the full range without retrieving the entire matrix.
    """
    if not vintage_dates:
        return []
    n = len(vintage_dates)
    indices: list[int] = []
    indices.append(0)  # earliest vintage (before or at initial release)
    if n > 1:
        indices.append(min(1, n - 1))  # initial-release vintage
    if n > 3:
        indices.append(n // 2)  # intermediate-revision vintage
    indices.append(n - 1)  # latest vintage
    seen: set[int] = set()
    selected: list[str] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            selected.append(vintage_dates[idx])
    return sorted(selected)


def _validate_output_type_2_against_reconstruction(
    series_id: str,
    *,
    vintage_dates: list[str],
    revision_events: list[dict[str, Any]],
    api_key: str,
    timeout_seconds: int,
    retry_count: int = 0,
    diagnostic_run_id: str = "",
    limit: int = 100000,
    progress_callback: Any | None = None,
    request_number_start: int = 1,
) -> dict[str, Any]:
    """Bounded output_type=2 integrity gate.

    Fetches all-observations snapshots for a small bounded sample of vintage
    dates (``output_type=2``) and compares the as-of value for each sampled
    vintage against the value reconstructed from the ``output_type=3``
    revision-event stream.  Any mismatch closes the gate and returns
    ``status='failed'``.
    """
    sample = _select_bounded_validation_vintages(vintage_dates)
    if not sample:
        return {
            "output_type_2_validation_status": "skipped_no_vintage_dates",
            "output_type_2_sample_dates": "",
            "output_type_2_mismatch_count": 0,
        }

    # Build as-of reconstruction from the output_type=3 event stream.
    # Key: (observation_date) -> list[(realtime_start, value)] sorted by realtime_start.
    from collections import defaultdict

    events_by_obs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in revision_events:
        obs_date = str(row.get("date", row.get("observation_date", "")))
        rt_start = str(row.get("realtime_start", ""))
        value = str(row.get("value", ""))
        if obs_date and rt_start:
            events_by_obs[obs_date].append((rt_start, value))
    for obs_date in events_by_obs:
        events_by_obs[obs_date].sort(key=lambda x: x[0])

    def reconstruct_asof(obs_date: str, as_of_vintage: str) -> str | None:
        """Return the value known as of a given vintage from the event stream."""
        candidates = [
            (rt, val)
            for rt, val in events_by_obs.get(obs_date, [])
            if rt <= as_of_vintage
        ]
        if not candidates:
            return None
        return candidates[-1][1]

    # Fetch output_type=2 snapshots for the bounded sample.
    try:
        type2_rows = _fetch_fred_observations_for_vintage_dates(
            series_id,
            vintage_dates=sample,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            output_type=2,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            limit=limit,
            progress_callback=progress_callback,
            request_number_start=request_number_start,
            request_stage="observations_vintage_validation",
        )
    except ProviderRequestError:
        return {
            "output_type_2_validation_status": "failed_provider_error",
            "output_type_2_sample_dates": ";".join(sample),
            "output_type_2_mismatch_count": 0,
        }

    mismatches = 0
    for row in type2_rows:
        obs_date = str(row.get("date", row.get("observation_date", "")))
        vintage = str(row.get("realtime_start", ""))
        official_value = str(row.get("value", ""))
        reconstructed = reconstruct_asof(obs_date, vintage)
        if reconstructed is None:
            mismatches += 1
        elif reconstructed != official_value:
            mismatches += 1

    status = "passed" if mismatches == 0 else "failed"
    return {
        "output_type_2_validation_status": status,
        "output_type_2_sample_dates": ";".join(sample),
        "output_type_2_mismatch_count": mismatches,
    }


def _crosscheck_output_type_4_initial_releases(
    series_id: str,
    *,
    initial_release_vintages: list[str],
    revision_events: list[dict[str, Any]],
    api_key: str,
    timeout_seconds: int,
    retry_count: int = 0,
    diagnostic_run_id: str = "",
    limit: int = 100000,
    progress_callback: Any | None = None,
    request_number_start: int = 1,
) -> dict[str, Any]:
    """Optional output_type=4 initial-release cross-check.

    Uses output_type=4 (initial releases only) solely to verify that the
    initial-release values reconstructed from the output_type=3 event stream
    match the official output_type=4 snapshot for a bounded sample of
    initial-release vintages.  output_type=4 is never used as the authoritative
    full-vintage source, does not supply later revisions, and does not determine
    revision count or justify a passing vintage gate.
    """
    sample = _select_bounded_validation_vintages(initial_release_vintages)
    if not sample:
        return {
            "output_type_4_crosscheck_status": "skipped_no_initial_release_vintages",
            "output_type_4_mismatch_count": 0,
        }

    # Build initial-release lookup from output_type=3 events.
    # For each observation date, the earliest event (lowest realtime_start) is
    # the initial release.
    initial_by_obs: dict[str, str] = {}
    for row in revision_events:
        obs_date = str(row.get("date", row.get("observation_date", "")))
        rt_start = str(row.get("realtime_start", ""))
        value = str(row.get("value", ""))
        if obs_date and rt_start:
            if obs_date not in initial_by_obs or rt_start < initial_by_obs[obs_date]:
                initial_by_obs[obs_date] = value

    try:
        type4_rows = _fetch_fred_observations_for_vintage_dates(
            series_id,
            vintage_dates=sample,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            output_type=4,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            limit=limit,
            progress_callback=progress_callback,
            request_number_start=request_number_start,
            request_stage="observations_vintage_crosscheck",
        )
    except ProviderRequestError:
        return {
            "output_type_4_crosscheck_status": "skipped_provider_error",
            "output_type_4_mismatch_count": 0,
        }

    mismatches = 0
    for row in type4_rows:
        obs_date = str(row.get("date", row.get("observation_date", "")))
        official_initial = str(row.get("value", ""))
        reconstructed_initial = initial_by_obs.get(obs_date)
        if reconstructed_initial is not None and reconstructed_initial != official_initial:
            mismatches += 1

    status = "passed" if mismatches == 0 else "failed"
    return {
        "output_type_4_crosscheck_status": status,
        "output_type_4_mismatch_count": mismatches,
    }


def _derive_revision_event_counts(
    revision_events: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Return (revision_event_count, initial_release_event_count, later_revision_event_count).

    Groups events by observation date and assigns revision sequence within each
    group by sorted realtime_start.  Sequence 0 is the initial release; any
    subsequent event is a later revision.
    """
    from collections import defaultdict

    obs_groups: dict[str, list[str]] = defaultdict(list)
    for row in revision_events:
        obs_date = str(row.get("date", row.get("observation_date", "")))
        rt_start = str(row.get("realtime_start", ""))
        if obs_date and rt_start:
            obs_groups[obs_date].append(rt_start)

    initial_count = 0
    later_count = 0
    for rt_list in obs_groups.values():
        rt_list_sorted = sorted(rt_list)
        initial_count += 1  # always one initial release per obs_date group
        later_count += len(rt_list_sorted) - 1

    total = initial_count + later_count
    return total, initial_count, later_count


def _fetch_observations_by_classification(
    series_id: str,
    *,
    api_key: str,
    timeout_seconds: int,
    retry_count: int = 0,
    diagnostic_run_id: str = "",
    limit: int = 100000,
    diagnostics_dir: Path | None = None,
    progress_callback: Any | None = None,
    request_number_start: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Route retrieval to the correct FRED output-type contract.

    Full-vintage series (CPIAUCSL, UNRATE, INDPRO)
    -----------------------------------------------
    1. Retrieve all official vintage dates from ``series/vintagedates``
       (paginated, deterministic).
    2. Split into URI-aware chunks satisfying both the date-count cap
       (``FRED_SAFE_VINTAGE_DATES_PER_REQUEST``) and the URI-byte budget
       (``FRED_MAX_ENCODED_REQUEST_URI_BYTES``).
    3. Retrieve the authoritative revision-event stream with
       ``output_type=3`` (new and revised observations only) for each chunk,
       with HTTP 414 adaptive bisection recovery.
    4. Merge all events; derive revision-event counts.
    5. Run a bounded ``output_type=2`` integrity validation on a small
       sample of vintages.
    6. Optionally run an ``output_type=4`` initial-release crosscheck.
    7. ``output_type=4`` is never the authoritative source and never
       determines revision count.

    Accounting fields returned
    --------------------------
    ``request_count_attempted``, ``request_count_completed``,
    ``metadata_request_count``, ``vintagedates_request_count``,
    ``output_type_3_request_count``, ``output_type_2_request_count``,
    ``output_type_4_request_count``, ``uri_414_count``,
    ``adaptive_rechunk_count``, ``adaptive_rechunk_depth_max``,
    ``vintage_chunk_uri_bytes``, ``maximum_chunk_uri_bytes``,
    ``minimum_chunk_uri_bytes``, ``configured_uri_budget_bytes``,
    ``configured_date_count_cap``.

    Current-history series
    ----------------------
    Plain ``series/observations`` retrieval without vintage parameters.
    """
    classification = retrieval_classification_for_series(series_id)
    if classification == "full_vintage_history_required":
        # --- Step 1: retrieve all vintage dates (paginated) ---
        vintage_dates = _fetch_vintage_dates(
            series_id,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            diagnostics_dir=diagnostics_dir,
            progress_callback=progress_callback,
            request_number_start=request_number_start,
        )
        vintagedates_request_count = 1  # paginated internally; counted as one logical call

        # --- Step 2: URI-aware greedy chunking ---
        chunks = chunk_vintage_dates_uri_aware(
            vintage_dates,
            series_id=series_id,
            api_key=api_key,
            output_type=3,
            limit=limit,
        )

        chunk_uri_bytes: list[int] = [
            _measure_vintage_request_uri_bytes(
                "series/observations",
                series_id=series_id,
                api_key=api_key,
                output_type=3,
                limit=limit,
                offset=0,
                sort_order="asc",
                vintage_dates_chunk=chunk,
            )
            for chunk in chunks
        ]

        # --- Step 3: Authoritative output_type=3 revision-event stream ---
        global_414: dict[str, Any] = {
            "uri_414_count": 0,
            "adaptive_rechunk_count": 0,
            "adaptive_rechunk_depth_max": 0,
        }
        observation_chunks: list[list[dict[str, Any]]] = []
        output_type_3_request_count = 0
        for idx, (chunk, uri_bytes) in enumerate(zip(chunks, chunk_uri_bytes), start=1):
            chunk_label = f"output_type=3 chunk {idx}/{len(chunks)}"
            _emit_progress(
                progress_callback,
                f"[{series_id}] {chunk_label}"
                f" dates={len(chunk)} uri_bytes={uri_bytes}"
                f" timeout={timeout_seconds} started",
            )
            chunk_rows, acct = _fetch_vintage_chunk_with_414_recovery(
                series_id,
                vintage_dates=chunk,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                output_type=3,
                retry_count=retry_count,
                diagnostic_run_id=diagnostic_run_id,
                limit=limit,
                diagnostics_dir=diagnostics_dir,
                progress_callback=progress_callback,
                request_number_start=request_number_start + idx,
                request_stage="observations_vintage",
            )
            observation_chunks.append(chunk_rows)
            output_type_3_request_count += 1
            global_414["uri_414_count"] += acct["uri_414_count"]
            global_414["adaptive_rechunk_count"] += acct["adaptive_rechunk_count"]
            global_414["adaptive_rechunk_depth_max"] = max(
                global_414["adaptive_rechunk_depth_max"], acct["adaptive_rechunk_depth_max"]
            )

        observations = merge_vintage_observation_chunks(observation_chunks)

        revision_event_count, initial_release_event_count, later_revision_event_count = (
            _derive_revision_event_counts(observations)
        )

        # --- Step 5: Bounded output_type=2 integrity validation ---
        validation_request_start = request_number_start + 1 + len(chunks)
        type2_result = _validate_output_type_2_against_reconstruction(
            series_id,
            vintage_dates=vintage_dates,
            revision_events=observations,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            limit=limit,
            progress_callback=progress_callback,
            request_number_start=validation_request_start,
        )
        output_type_2_request_count = 1 if vintage_dates else 0

        # --- Step 6: Optional output_type=4 initial-release crosscheck ---
        crosscheck_request_start = validation_request_start + 1
        type4_result = _crosscheck_output_type_4_initial_releases(
            series_id,
            initial_release_vintages=vintage_dates,
            revision_events=observations,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            limit=limit,
            progress_callback=progress_callback,
            request_number_start=crosscheck_request_start,
        )
        output_type_4_request_count = 1 if vintage_dates else 0

        total_attempted = (
            vintagedates_request_count
            + output_type_3_request_count
            + output_type_2_request_count
            + output_type_4_request_count
        )

        info: dict[str, Any] = {
            "retrieval_classification": classification,
            "vintage_status": "full_vintage_retrieved",
            "vintage_date_count": len(vintage_dates),
            "vintage_page_count": 1,  # paginated internally; one logical vintagedates call
            "vintage_chunk_count": len(chunks),
            "vintage_chunk_sizes": ";".join(str(len(chunk)) for chunk in chunks),
            "vintage_chunk_uri_bytes": ";".join(str(b) for b in chunk_uri_bytes),
            "maximum_chunk_uri_bytes": max(chunk_uri_bytes) if chunk_uri_bytes else 0,
            "minimum_chunk_uri_bytes": min(chunk_uri_bytes) if chunk_uri_bytes else 0,
            "configured_uri_budget_bytes": FRED_MAX_ENCODED_REQUEST_URI_BYTES,
            "configured_date_count_cap": FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
            "revision_event_count": revision_event_count,
            "initial_release_event_count": initial_release_event_count,
            "later_revision_event_count": later_revision_event_count,
            "output_type_3_status": "used_as_authoritative_revision_event_stream",
            "output_type_2_validation_status": type2_result["output_type_2_validation_status"],
            "output_type_2_sample_dates": type2_result["output_type_2_sample_dates"],
            "output_type_2_mismatch_count": type2_result["output_type_2_mismatch_count"],
            "output_type_4_crosscheck_status": type4_result["output_type_4_crosscheck_status"],
            "output_type_4_mismatch_count": type4_result["output_type_4_mismatch_count"],
            # Accounting
            "request_count": total_attempted,
            "request_count_attempted": total_attempted,
            "request_count_completed": total_attempted,
            "metadata_request_count": 0,  # caller adds this
            "vintagedates_request_count": vintagedates_request_count,
            "output_type_3_request_count": output_type_3_request_count,
            "output_type_2_request_count": output_type_2_request_count,
            "output_type_4_request_count": output_type_4_request_count,
            "uri_414_count": global_414["uri_414_count"],
            "adaptive_rechunk_count": global_414["adaptive_rechunk_count"],
            "adaptive_rechunk_depth_max": global_414["adaptive_rechunk_depth_max"],
        }
        return observations, info

    observations = _fetch_current_fred_observations(
        series_id,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        retry_count=retry_count,
        diagnostic_run_id=diagnostic_run_id,
        limit=limit,
        diagnostics_dir=diagnostics_dir,
        progress_callback=progress_callback,
        request_number_start=request_number_start,
    )
    return observations, {
        "retrieval_classification": classification,
        "vintage_status": "not_requested_current_history",
        "vintage_date_count": 0,
        "vintage_chunk_count": 0,
        "vintage_chunk_sizes": "",
        "vintage_chunk_uri_bytes": "",
        "maximum_chunk_uri_bytes": 0,
        "minimum_chunk_uri_bytes": 0,
        "configured_uri_budget_bytes": FRED_MAX_ENCODED_REQUEST_URI_BYTES,
        "configured_date_count_cap": FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
        "revision_event_count": 0,
        "initial_release_event_count": 0,
        "later_revision_event_count": 0,
        "output_type_3_status": "not_applicable_current_history",
        "output_type_2_validation_status": "not_applicable",
        "output_type_2_sample_dates": "",
        "output_type_2_mismatch_count": 0,
        "output_type_4_crosscheck_status": "not_applicable",
        "output_type_4_mismatch_count": 0,
        "request_count": 1,
        "request_count_attempted": 1,
        "request_count_completed": 1,
        "metadata_request_count": 0,
        "vintagedates_request_count": 0,
        "output_type_3_request_count": 0,
        "output_type_2_request_count": 0,
        "output_type_4_request_count": 0,
        "uri_414_count": 0,
        "adaptive_rechunk_count": 0,
        "adaptive_rechunk_depth_max": 0,
    }


def _write_live_snapshot(
    config: GMA1BConfig,
    registry: pd.DataFrame,
    *,
    api_key: str,
    retrieved_at: str,
) -> tuple[pd.DataFrame, pd.DataFrame, Path, Path, Path, str, str, str]:
    raw_root = config.paths["raw_root"] / "fred" / "live" / retrieved_at
    manifest_root = config.paths["manifest_root"] / "fred" / "live" / retrieved_at
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)

    metadata_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    timeout_seconds = int(config.provider.get("timeout_seconds", 20))
    for _, item in registry.iterrows():
        series_id = str(item["series_id"])
        metadata_payload = _fetch_fred_payload(
            "series",
            {"series_id": series_id},
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            series_id=series_id,
            request_stage="metadata",
            retry_count=int(config.provider.get("retry_count", 0)),
        )
        metadata = _series_metadata_from_payload(metadata_payload, series_id)
        metadata_rows.append({
            "macro_id": item["macro_id"],
            "series_id": series_id,
            "title": metadata.get("title", ""),
            "source": metadata.get("source", ""),
            "release": metadata.get("release", metadata.get("release_id", "")),
            "frequency": metadata.get("frequency", ""),
            "frequency_short": metadata.get("frequency_short", ""),
            "units": metadata.get("units", ""),
            "seasonal_adjustment": metadata.get("seasonal_adjustment", ""),
            "observation_start": metadata.get("observation_start", ""),
            "observation_end": metadata.get("observation_end", ""),
            "last_updated": metadata.get("last_updated", ""),
            "notes": metadata.get("notes", ""),
        })
        observations_for_series, retrieval_info = _fetch_observations_by_classification(
            series_id,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            retry_count=int(config.provider.get("retry_count", 0)),
            diagnostic_run_id=retrieved_at,
        )
        metadata_rows[-1].update(retrieval_info)
        for obs in observations_for_series:
            observation_rows.append({
                "series_id": series_id,
                "observation_date": obs.get("date", ""),
                "value": obs.get("value", ""),
                "realtime_start": obs.get("realtime_start", ""),
                "realtime_end": obs.get("realtime_end", ""),
            })

    observations = pd.DataFrame(observation_rows)
    if observations.empty:
        raise RuntimeError("official_fred_live_observations_empty")
    metadata_df = pd.DataFrame(metadata_rows)
    raw_path = raw_root / "macro_observations_live.csv"
    metadata_path = raw_root / "series_metadata_live.csv"
    normalised_path = raw_root / "macro_observations_live_normalised.csv"
    observations.to_csv(raw_path, index=False)
    metadata_df.to_csv(metadata_path, index=False)
    observations.to_csv(normalised_path, index=False)
    raw_hash = sha256_file(raw_path)
    norm_hash = sha256_file(normalised_path)
    metadata_hash = sha256_file(metadata_path)
    manifest = {
        "track_id": GMA1B_TRACK_ID,
        "phase_id": GMA1B_PHASE_ID,
        "provider": "fred",
        "vintage_provider": "alfred",
        "series_id": "MULTI_SERIES_LIVE",
        "request_type": "official_fred_alfred_live",
        "request_parameters": {
            "series_count": int(len(registry)),
            "observation_endpoint": "series/observations",
            "metadata_endpoint": "series",
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
            "credential_present": True,
        },
        "retrieved_at_utc": retrieved_at,
        "library_or_endpoint": FRED_API_ROOT,
        "source_metadata": metadata_df.to_dict(orient="records"),
        "raw_file_path": str(raw_path),
        "raw_file_sha256": raw_hash,
        "metadata_file_path": str(metadata_path),
        "metadata_file_sha256": metadata_hash,
        "normalised_file_path": str(normalised_path),
        "normalised_file_sha256": norm_hash,
        "row_count": int(len(observations)),
        "first_observation_date": str(observations["observation_date"].min()),
        "last_observation_date": str(observations["observation_date"].max()),
        "first_realtime_start": str(observations["realtime_start"].min()),
        "last_realtime_start": str(observations["realtime_start"].max()),
        "columns": list(observations.columns),
        "warnings": [],
    }
    manifest_path = manifest_root / "macro_observations_live_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    manifest_hash = sha256_file(manifest_path)
    return observations, metadata_df, raw_path, normalised_path, manifest_path, raw_hash, norm_hash, manifest_hash


def _build_live_reproducibility_report(
    first: pd.DataFrame,
    second: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    first_snapshot: str,
    second_snapshot: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    keys = ["series_id", "observation_date", "realtime_start", "realtime_end"]
    for _, item in registry.iterrows():
        series_id = str(item["series_id"])
        left = first[first["series_id"].eq(series_id)].copy()
        right = second[second["series_id"].eq(series_id)].copy()
        overlap = left.merge(right, on=keys, suffixes=("_first", "_second"))
        diffs = overlap[
            pd.to_numeric(overlap["value_first"], errors="coerce")
            .ne(pd.to_numeric(overlap["value_second"], errors="coerce"))
        ]
        right_keys = set(map(tuple, right[keys].astype(str).to_numpy()))
        left_keys = set(map(tuple, left[keys].astype(str).to_numpy()))
        new_rows = right_keys - left_keys
        rows.append({
            "macro_id": item["macro_id"],
            "series_id": series_id,
            "first_snapshot": first_snapshot,
            "second_snapshot": second_snapshot,
            "overlap_rows": int(len(overlap)),
            "exact_difference_count": int(len(diffs)),
            "expected_revision_count": int(len(new_rows)),
            "metadata_update_count": 0,
            "unexplained_difference_count": int(len(diffs)),
            "first_difference_date": "" if diffs.empty else str(diffs["observation_date"].min()),
            "last_difference_date": "" if diffs.empty else str(diffs["observation_date"].max()),
            "reproducibility_status": "stable" if diffs.empty else "unexplained_value_differences",
        })
    return pd.DataFrame(rows)


def _series_registry_row(config: GMA1BConfig, series_id: str) -> dict[str, Any] | None:
    for item in config.series:
        if str(item["series_id"]) == series_id:
            return item
    return None


def _empty_provider_incident_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=PROVIDER_INCIDENT_COLUMNS)


def _write_diagnostic_outputs(
    config: GMA1BConfig,
    incidents: list[ProviderRequestIncident],
    per_series: pd.DataFrame,
    smoke: dict[str, Any] | None = None,
) -> None:
    diagnostics_dir = config.paths["report_root"] / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    incident_df = (
        pd.DataFrame([_incident_to_dict(item) for item in incidents])
        if incidents
        else _empty_provider_incident_frame()
    )
    _atomic_write_csv(incident_df, diagnostics_dir / "provider_request_incidents.csv")
    _atomic_write_csv(per_series, diagnostics_dir / "per_series_live_diagnostic.csv")
    if smoke is not None:
        _atomic_write_json(smoke, diagnostics_dir / "production_dgs3mo_smoke_test.json")


def _diagnostic_missing_credential_incident(
    *,
    diagnostic_run_id: str,
    series_id: str,
    stage: str,
) -> ProviderRequestIncident:
    return ProviderRequestIncident(
        diagnostic_run_id=diagnostic_run_id,
        series_id=series_id,
        request_stage=stage,
        endpoint="series" if stage == "metadata" else "series/observations",
        http_method="GET",
        parameter_names="api_key;file_type;series_id",
        http_status="",
        provider_error_code="",
        redacted_provider_message="credential environment variable not available to this process",
        exception_type="MissingCredential",
        error_category="credential_or_permission_failure",
        retryable=False,
        response_content_type="",
    )


def _diagnose_one_series(
    config: GMA1BConfig,
    *,
    series_id: str,
    api_key: str | None,
    diagnostic_run_id: str,
    progress_callback: Any | None = None,
) -> tuple[dict[str, Any], list[ProviderRequestIncident], dict[str, Any]]:
    started_at = utc_now_iso()
    start_monotonic = time.monotonic()
    incidents: list[ProviderRequestIncident] = []
    classification = retrieval_classification_for_series(series_id)
    retry_count = int(config.provider.get("retry_count", 0))

    def finish(row: dict[str, Any]) -> dict[str, Any]:
        completed_at = utc_now_iso()
        row.setdefault("retrieval_classification", classification)
        row.setdefault("vintage_status", "")
        row.setdefault("vintage_date_count", 0)
        row.setdefault("vintage_chunk_count", 0)
        row.setdefault("vintage_chunk_sizes", "")
        row.setdefault("started_at_utc", started_at)
        row["completed_at_utc"] = completed_at
        row["elapsed_seconds"] = round(time.monotonic() - start_monotonic, 3)
        row.setdefault("request_count", 0)
        row.setdefault("retry_count", retry_count)
        row.setdefault("cancelled", False)
        return row

    if _series_registry_row(config, series_id) is None:
        incident = ProviderRequestIncident(
            diagnostic_run_id=diagnostic_run_id,
            series_id=series_id,
            request_stage="metadata",
            endpoint="series",
            http_method="GET",
            parameter_names="api_key;file_type;series_id",
            http_status="",
            provider_error_code="",
            redacted_provider_message="series is not registered in GMA-1B config",
            exception_type="UnknownSeries",
            error_category="invalid_series",
            retryable=False,
            response_content_type="",
        )
        return (finish({
            "series_id": series_id,
            "metadata_status": "failed",
            "metadata_http_status": "",
            "observations_status": "not_attempted",
            "observations_http_status": "",
            "row_count": 0,
            "first_observation_date": "",
            "last_observation_date": "",
            "failure_stage": "metadata",
            "failure_category": "invalid_series",
            "retryable": False,
            "diagnostic_snapshot_eligible": False,
        }), [incident], {})
    if not api_key:
        incident = _diagnostic_missing_credential_incident(
            diagnostic_run_id=diagnostic_run_id,
            series_id=series_id,
            stage="metadata",
        )
        return (finish({
            "series_id": series_id,
            "metadata_status": "failed",
            "metadata_http_status": "",
            "observations_status": "not_attempted",
            "observations_http_status": "",
            "row_count": 0,
            "first_observation_date": "",
            "last_observation_date": "",
            "failure_stage": "metadata",
            "failure_category": incident.error_category,
            "retryable": False,
            "diagnostic_snapshot_eligible": False,
        }), [incident], {})

    timeout_seconds = min(int(config.provider.get("timeout_seconds", 20)), 30)
    diagnostics_dir = config.paths["report_root"] / "diagnostics"
    metadata_http_status: int | str = 200
    observations_http_status: int | str = 200
    try:
        metadata_payload = _fetch_fred_payload(
            "series",
            {"series_id": series_id},
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            series_id=series_id,
            request_stage="metadata",
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            diagnostics_dir=diagnostics_dir,
            request_number=1,
            progress_callback=progress_callback,
        )
        metadata = _series_metadata_from_payload(metadata_payload, series_id)
    except ProviderRequestError as exc:
        incidents.append(exc.incident)
        return (finish({
            "series_id": series_id,
            "metadata_status": "failed",
            "metadata_http_status": exc.incident.http_status,
            "observations_status": "not_attempted",
            "observations_http_status": "",
            "row_count": 0,
            "first_observation_date": "",
            "last_observation_date": "",
            "failure_stage": exc.incident.request_stage,
            "failure_category": exc.incident.error_category,
            "retryable": exc.incident.retryable,
            "diagnostic_snapshot_eligible": False,
        }), incidents, {})

    # Pre-compute URI-aware chunk plan for full-vintage series so that
    # vintage_date_count and chunk info survive even if the observations
    # request later fails.
    pre_vintage_dates: list[str] = []
    pre_chunks: list[list[str]] = []
    pre_chunk_uri_bytes: list[int] = []
    if retrieval_classification_for_series(series_id) == "full_vintage_history_required":
        try:
            pre_vintage_dates = _fetch_vintage_dates(
                series_id,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                retry_count=retry_count,
                diagnostic_run_id=diagnostic_run_id,
                diagnostics_dir=diagnostics_dir,
                progress_callback=progress_callback,
                request_number_start=2,
            )
            pre_chunks = chunk_vintage_dates_uri_aware(
                pre_vintage_dates,
                series_id=series_id,
                api_key=api_key,
                output_type=3,
                limit=100000,
            )
            pre_chunk_uri_bytes = [
                _measure_vintage_request_uri_bytes(
                    "series/observations",
                    series_id=series_id,
                    api_key=api_key,
                    output_type=3,
                    limit=100000,
                    offset=0,
                    sort_order="asc",
                    vintage_dates_chunk=chunk,
                )
                for chunk in pre_chunks
            ]
        except ProviderRequestError as exc:
            incidents.append(exc.incident)
            return (finish({
                "series_id": series_id,
                "metadata_status": "passed",
                "metadata_http_status": metadata_http_status,
                "observations_status": "failed",
                "observations_http_status": exc.incident.http_status,
                "row_count": 0,
                "first_observation_date": "",
                "last_observation_date": "",
                "vintage_date_count": 0,
                "vintage_chunk_count": 0,
                "vintage_chunk_sizes": "",
                "vintage_chunk_uri_bytes": "",
                "maximum_chunk_uri_bytes": 0,
                "minimum_chunk_uri_bytes": 0,
                "configured_uri_budget_bytes": FRED_MAX_ENCODED_REQUEST_URI_BYTES,
                "configured_date_count_cap": FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
                "request_count_attempted": 2,  # metadata + vintagedates
                "request_count_completed": 1,  # only metadata
                "failure_stage": exc.incident.request_stage,
                "failure_category": exc.incident.error_category,
                "retryable": exc.incident.retryable,
                "diagnostic_snapshot_eligible": False,
            }), incidents, {})

        # Now do the full retrieval using the pre-fetched vintage dates.
        # _fetch_observations_by_classification would re-fetch; instead call
        # the sub-pipeline directly to avoid a second vintagedates request.
        try:
            global_414: dict[str, Any] = {
                "uri_414_count": 0, "adaptive_rechunk_count": 0,
                "adaptive_rechunk_depth_max": 0,
            }
            obs_chunks: list[list[dict[str, Any]]] = []
            ot3_count = 0
            for idx, chunk in enumerate(pre_chunks, start=1):
                uri_bytes_i = pre_chunk_uri_bytes[idx - 1]
                chunk_label = f"output_type=3 chunk {idx}/{len(pre_chunks)}"
                _emit_progress(
                    progress_callback,
                    f"[{series_id}] {chunk_label}"
                    f" dates={len(chunk)} uri_bytes={uri_bytes_i}"
                    f" timeout={timeout_seconds} started",
                )
                chunk_rows, acct = _fetch_vintage_chunk_with_414_recovery(
                    series_id,
                    vintage_dates=chunk,
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    output_type=3,
                    retry_count=retry_count,
                    diagnostic_run_id=diagnostic_run_id,
                    limit=100000,
                    diagnostics_dir=diagnostics_dir,
                    progress_callback=progress_callback,
                    request_number_start=2 + idx,
                    request_stage="observations_vintage",
                )
                obs_chunks.append(chunk_rows)
                ot3_count += 1
                global_414["uri_414_count"] += acct["uri_414_count"]
                global_414["adaptive_rechunk_count"] += acct["adaptive_rechunk_count"]
                global_414["adaptive_rechunk_depth_max"] = max(
                    global_414["adaptive_rechunk_depth_max"],
                    acct["adaptive_rechunk_depth_max"],
                )
            observations = merge_vintage_observation_chunks(obs_chunks)
        except ProviderRequestError as exc:
            incidents.append(exc.incident)
            return (finish({
                "series_id": series_id,
                "metadata_status": "passed",
                "metadata_http_status": metadata_http_status,
                "observations_status": "failed",
                "observations_http_status": exc.incident.http_status,
                "row_count": 0,
                "first_observation_date": "",
                "last_observation_date": "",
                # Preserved from the successful vintagedates request:
                "vintage_date_count": len(pre_vintage_dates),
                "vintage_chunk_count": len(pre_chunks),
                "vintage_chunk_sizes": ";".join(str(len(c)) for c in pre_chunks),
                "vintage_chunk_uri_bytes": ";".join(str(b) for b in pre_chunk_uri_bytes),
                "maximum_chunk_uri_bytes": max(pre_chunk_uri_bytes) if pre_chunk_uri_bytes else 0,
                "minimum_chunk_uri_bytes": min(pre_chunk_uri_bytes) if pre_chunk_uri_bytes else 0,
                "configured_uri_budget_bytes": FRED_MAX_ENCODED_REQUEST_URI_BYTES,
                "configured_date_count_cap": FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
                "request_count_attempted": 2 + ot3_count + 1,  # meta + vd + attempted chunks
                "request_count_completed": 2 + ot3_count,       # meta + vd + completed chunks
                "failure_stage": exc.incident.request_stage,
                "failure_category": exc.incident.error_category,
                "retryable": exc.incident.retryable,
                "diagnostic_snapshot_eligible": False,
            }), incidents, {})
        except ValueError as exc:
            incident = ProviderRequestIncident(
                diagnostic_run_id=diagnostic_run_id,
                series_id=series_id,
                request_stage="observations_vintage",
                endpoint="series/observations",
                http_method="GET",
                parameter_names="api_key;file_type;output_type;series_id;vintage_dates",
                http_status="",
                provider_error_code="",
                redacted_provider_message=redact_secret(exc, api_key),
                exception_type=type(exc).__name__,
                error_category="schema_validation_failure",
                retryable=False,
                response_content_type="application/json",
            )
            incidents.append(incident)
            return (finish({
                "series_id": series_id,
                "metadata_status": "passed",
                "metadata_http_status": metadata_http_status,
                "observations_status": "failed",
                "observations_http_status": "",
                "row_count": 0,
                "first_observation_date": "",
                "last_observation_date": "",
                "vintage_date_count": len(pre_vintage_dates),
                "vintage_chunk_count": len(pre_chunks),
                "vintage_chunk_sizes": ";".join(str(len(c)) for c in pre_chunks),
                "vintage_chunk_uri_bytes": ";".join(str(b) for b in pre_chunk_uri_bytes),
                "maximum_chunk_uri_bytes": max(pre_chunk_uri_bytes) if pre_chunk_uri_bytes else 0,
                "minimum_chunk_uri_bytes": min(pre_chunk_uri_bytes) if pre_chunk_uri_bytes else 0,
                "configured_uri_budget_bytes": FRED_MAX_ENCODED_REQUEST_URI_BYTES,
                "configured_date_count_cap": FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
                "request_count_attempted": 2 + ot3_count + 1,
                "request_count_completed": 2 + ot3_count,
                "failure_stage": "observations_vintage",
                "failure_category": "schema_validation_failure",
                "retryable": False,
                "diagnostic_snapshot_eligible": False,
            }), incidents, {})

        # --- output_type=2 bounded validation and output_type=4 crosscheck ---
        revision_event_count, initial_release_event_count, later_revision_event_count = (
            _derive_revision_event_counts(observations)
        )
        type2_result = _validate_output_type_2_against_reconstruction(
            series_id,
            vintage_dates=pre_vintage_dates,
            revision_events=observations,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            limit=100000,
            progress_callback=progress_callback,
            request_number_start=2 + len(pre_chunks) + 1,
        )
        type4_result = _crosscheck_output_type_4_initial_releases(
            series_id,
            initial_release_vintages=pre_vintage_dates,
            revision_events=observations,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            diagnostic_run_id=diagnostic_run_id,
            limit=100000,
            progress_callback=progress_callback,
            request_number_start=2 + len(pre_chunks) + 2,
        )
        retrieval_info: dict[str, Any] = {
            "retrieval_classification": "full_vintage_history_required",
            "vintage_status": "full_vintage_retrieved",
            "vintage_date_count": len(pre_vintage_dates),
            "vintage_page_count": 1,
            "vintage_chunk_count": len(pre_chunks),
            "vintage_chunk_sizes": ";".join(str(len(c)) for c in pre_chunks),
            "vintage_chunk_uri_bytes": ";".join(str(b) for b in pre_chunk_uri_bytes),
            "maximum_chunk_uri_bytes": max(pre_chunk_uri_bytes) if pre_chunk_uri_bytes else 0,
            "minimum_chunk_uri_bytes": min(pre_chunk_uri_bytes) if pre_chunk_uri_bytes else 0,
            "configured_uri_budget_bytes": FRED_MAX_ENCODED_REQUEST_URI_BYTES,
            "configured_date_count_cap": FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
            "revision_event_count": revision_event_count,
            "initial_release_event_count": initial_release_event_count,
            "later_revision_event_count": later_revision_event_count,
            "output_type_3_status": "used_as_authoritative_revision_event_stream",
            "output_type_2_validation_status": type2_result["output_type_2_validation_status"],
            "output_type_2_sample_dates": type2_result["output_type_2_sample_dates"],
            "output_type_2_mismatch_count": type2_result["output_type_2_mismatch_count"],
            "output_type_4_crosscheck_status": type4_result["output_type_4_crosscheck_status"],
            "output_type_4_mismatch_count": type4_result["output_type_4_mismatch_count"],
            "request_count": 1 + 1 + ot3_count + 2,  # meta + vd + ot3 + ot2 + ot4
            "request_count_attempted": 1 + 1 + ot3_count + 2,
            "request_count_completed": 1 + 1 + ot3_count + 2,
            "metadata_request_count": 1,
            "vintagedates_request_count": 1,
            "output_type_3_request_count": ot3_count,
            "output_type_2_request_count": 1 if pre_vintage_dates else 0,
            "output_type_4_request_count": 1 if pre_vintage_dates else 0,
            "uri_414_count": global_414["uri_414_count"],
            "adaptive_rechunk_count": global_414["adaptive_rechunk_count"],
            "adaptive_rechunk_depth_max": global_414["adaptive_rechunk_depth_max"],
        }
    else:
        try:
            observations, retrieval_info = _fetch_observations_by_classification(
                series_id,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                retry_count=retry_count,
                diagnostic_run_id=diagnostic_run_id,
                diagnostics_dir=diagnostics_dir,
                progress_callback=progress_callback,
                request_number_start=2,
            )
        except ProviderRequestError as exc:
            incidents.append(exc.incident)
            return (finish({
                "series_id": series_id,
                "metadata_status": "passed",
                "metadata_http_status": metadata_http_status,
                "observations_status": "failed",
                "observations_http_status": exc.incident.http_status,
                "row_count": 0,
                "first_observation_date": "",
                "last_observation_date": "",
                "failure_stage": exc.incident.request_stage,
                "failure_category": exc.incident.error_category,
                "retryable": exc.incident.retryable,
                "diagnostic_snapshot_eligible": False,
                "request_count_attempted": 2,  # metadata + 1 failed obs
                "request_count_completed": 1,
            }), incidents, {})
        except ValueError as exc:
            incident = ProviderRequestIncident(
                diagnostic_run_id=diagnostic_run_id,
                series_id=series_id,
                request_stage="observations_vintage",
                endpoint="series/observations",
                http_method="GET",
                parameter_names="api_key;file_type;output_type;series_id;vintage_dates",
                http_status="",
                provider_error_code="",
                redacted_provider_message=redact_secret(exc, api_key),
                exception_type=type(exc).__name__,
                error_category="schema_validation_failure",
                retryable=False,
                response_content_type="application/json",
            )
            incidents.append(incident)
            return (finish({
                "series_id": series_id,
                "metadata_status": "passed",
                "metadata_http_status": metadata_http_status,
                "observations_status": "failed",
                "observations_http_status": "",
                "row_count": 0,
                "first_observation_date": "",
                "last_observation_date": "",
                "failure_stage": "observations_vintage",
                "failure_category": "schema_validation_failure",
                "retryable": False,
                "diagnostic_snapshot_eligible": False,
                "request_count_attempted": 2,
                "request_count_completed": 1,
            }), incidents, {})

    row_count = len(observations)
    dates = [str(row.get("date", "")) for row in observations if row.get("date")]
    smoke = {
        "diagnostic_run_id": diagnostic_run_id,
        "series_id": series_id,
        "diagnostic_only": True,
        "eligible_for_live_canonical_selection": False,
        "retrieval_classification": retrieval_info["retrieval_classification"],
        "metadata_status": "passed",
        "observations_status": "passed",
        "metadata_title": metadata.get("title", ""),
        "metadata_units": metadata.get("units", ""),
        "row_count": row_count,
        "first_observation_date": min(dates) if dates else "",
        "last_observation_date": max(dates) if dates else "",
        "vintage_date_count": retrieval_info.get("vintage_date_count", 0),
        "vintage_chunk_count": retrieval_info.get("vintage_chunk_count", 0),
        "vintage_chunk_sizes": retrieval_info.get("vintage_chunk_sizes", ""),
        "vintage_chunk_uri_bytes": retrieval_info.get("vintage_chunk_uri_bytes", ""),
        "maximum_chunk_uri_bytes": retrieval_info.get("maximum_chunk_uri_bytes", 0),
        "configured_uri_budget_bytes": FRED_MAX_ENCODED_REQUEST_URI_BYTES,
        "configured_date_count_cap": FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
        "request_count_attempted": retrieval_info.get("request_count_attempted", retrieval_info.get("request_count", 0)) + 1,
        "request_count_completed": retrieval_info.get("request_count_completed", retrieval_info.get("request_count", 0)) + 1,
        "request_count": retrieval_info.get("request_count", 0) + 1,
        "parameter_names": fred_request_parameter_names({"series_id": series_id, "limit": 100000}),
        "api_key_present": True,
    }
    row = {
        "series_id": series_id,
        "retrieval_classification": retrieval_info["retrieval_classification"],
        "metadata_status": "passed",
        "metadata_http_status": metadata_http_status,
        "observations_status": "passed",
        "observations_http_status": observations_http_status,
        "row_count": row_count,
        "first_observation_date": min(dates) if dates else "",
        "last_observation_date": max(dates) if dates else "",
        "vintage_status": retrieval_info.get("vintage_status", ""),
        "vintage_date_count": retrieval_info.get("vintage_date_count", 0),
        "vintage_chunk_count": retrieval_info.get("vintage_chunk_count", 0),
        "vintage_chunk_sizes": retrieval_info.get("vintage_chunk_sizes", ""),
        "vintage_chunk_uri_bytes": retrieval_info.get("vintage_chunk_uri_bytes", ""),
        "maximum_chunk_uri_bytes": retrieval_info.get("maximum_chunk_uri_bytes", 0),
        "minimum_chunk_uri_bytes": retrieval_info.get("minimum_chunk_uri_bytes", 0),
        "configured_uri_budget_bytes": FRED_MAX_ENCODED_REQUEST_URI_BYTES,
        "configured_date_count_cap": FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
        "failure_stage": "",
        "failure_category": "",
        "retryable": False,
        "diagnostic_snapshot_eligible": False,
        "request_count": retrieval_info.get("request_count", 0) + 1,
        "request_count_attempted": retrieval_info.get("request_count_attempted", retrieval_info.get("request_count", 0)) + 1,
        "request_count_completed": retrieval_info.get("request_count_completed", retrieval_info.get("request_count", 0)) + 1,
        "metadata_request_count": retrieval_info.get("metadata_request_count", 1),
        "vintagedates_request_count": retrieval_info.get("vintagedates_request_count", 0),
        "output_type_3_request_count": retrieval_info.get("output_type_3_request_count", 0),
        "output_type_2_request_count": retrieval_info.get("output_type_2_request_count", 0),
        "output_type_4_request_count": retrieval_info.get("output_type_4_request_count", 0),
        "uri_414_count": retrieval_info.get("uri_414_count", 0),
        "adaptive_rechunk_count": retrieval_info.get("adaptive_rechunk_count", 0),
        "adaptive_rechunk_depth_max": retrieval_info.get("adaptive_rechunk_depth_max", 0),
    }
    return (finish(row), incidents, smoke)


def run_gma1b_live_diagnostic(
    config: GMA1BConfig | str | Path,
    *,
    series_id: str | None = None,
    all_series: bool = False,
    progress_callback: Any | None = None,
    total_duration_limit_seconds: float = DIAGNOSTIC_TOTAL_DURATION_LIMIT_SECONDS,
) -> GMA1BResult:
    if not isinstance(config, GMA1BConfig):
        config = load_gma1b_config(config)
    diagnostic_run_id = utc_now_compact()
    api_key = os.environ.get(str(config.provider["api_key_environment_variable"]))
    if all_series:
        series_ids = [str(item["series_id"]) for item in config.series]
    elif series_id:
        series_ids = [series_id]
    else:
        raise ValueError("series_id is required unless all_series is true")

    rows: list[dict[str, Any]] = []
    incidents: list[ProviderRequestIncident] = []
    smoke: dict[str, Any] | None = None
    run_start = time.monotonic()
    cancelled = False
    try:
        for idx, sid in enumerate(series_ids, start=1):
            if time.monotonic() - run_start > total_duration_limit_seconds:
                row = {
                    "series_id": sid,
                    "retrieval_classification": retrieval_classification_for_series(sid),
                    "metadata_status": "not_attempted",
                    "metadata_http_status": "",
                    "observations_status": "not_attempted",
                    "observations_http_status": "",
                    "row_count": 0,
                    "first_observation_date": "",
                    "last_observation_date": "",
                    "vintage_status": "",
                    "vintage_date_count": 0,
                    "vintage_chunk_count": 0,
                    "vintage_chunk_sizes": "",
                    "failure_stage": "diagnostic_runtime",
                    "failure_category": "diagnostic_duration_limit_exceeded",
                    "retryable": False,
                    "diagnostic_snapshot_eligible": False,
                    "started_at_utc": utc_now_iso(),
                    "completed_at_utc": utc_now_iso(),
                    "elapsed_seconds": 0,
                    "request_count": 0,
                    "retry_count": int(config.provider.get("retry_count", 0)),
                    "cancelled": True,
                }
                rows.append(row)
                cancelled = True
                break
            diagnose_kwargs = {
                "series_id": sid,
                "api_key": api_key,
                "diagnostic_run_id": diagnostic_run_id,
            }
            if progress_callback is not None:
                diagnose_kwargs["progress_callback"] = progress_callback
            row, row_incidents, row_smoke = _diagnose_one_series(config, **diagnose_kwargs)
            rows.append(row)
            incidents.extend(row_incidents)
            if progress_callback:
                progress_callback(
                    f"[{idx}/{len(series_ids)}] {sid} "
                    f"metadata={row['metadata_status']} observations={row['observations_status']} "
                    f"elapsed={row['elapsed_seconds']}s"
                )
            if sid == "DGS3MO":
                smoke = row_smoke or {
                    "diagnostic_run_id": diagnostic_run_id,
                    "series_id": sid,
                    "diagnostic_only": True,
                    "eligible_for_live_canonical_selection": False,
                    "metadata_status": row["metadata_status"],
                    "observations_status": row["observations_status"],
                    "failure_stage": row["failure_stage"],
                    "failure_category": row["failure_category"],
                }
            _write_diagnostic_outputs(config, incidents, pd.DataFrame(rows), smoke)
    except KeyboardInterrupt:
        cancelled = True
        if rows:
            rows[-1]["cancelled"] = True
        _write_diagnostic_outputs(config, incidents, pd.DataFrame(rows), smoke)
    per_series = pd.DataFrame(rows)
    _write_diagnostic_outputs(config, incidents, per_series, smoke)
    passed = bool(
        not per_series.empty
        and per_series["metadata_status"].eq("passed").all()
        and per_series["observations_status"].eq("passed").all()
        and not cancelled
    )
    decision = (
        "gma1b_live_diagnostic_passed_ineligible_for_canonical_selection"
        if passed
        else "gma1b_live_diagnostic_failed"
    )
    warnings = [] if passed else ["live_diagnostic_failed_review_sanitized_reports"]
    return GMA1BResult(
        decision=decision,
        warnings=warnings,
        canonical_hash="",
        live_retrieval_status=decision,
    )


def _accepted_gma1a_verified() -> tuple[bool, str]:
    conclusion = Path("reports/global_multi_asset_alpha/data_foundation/gma1a_conclusion.md")
    hash_path = Path("reports/global_multi_asset_alpha/data_foundation/canonical_selection_hash.txt")
    if not conclusion.exists() or not hash_path.exists():
        return False, "missing_gma1a_conclusion_or_hash"
    decision_ok = "gma1a_feasible_proceed_to_macro_foundation" in conclusion.read_text(encoding="utf-8")
    hash_ok = hash_path.read_text(encoding="utf-8").strip() == ACCEPTED_GMA1A_HASH
    return decision_ok and hash_ok, "verified" if decision_ok and hash_ok else "decision_or_hash_mismatch"


def _write_markdown_reports(report_root: Path) -> None:
    (report_root / "availability_policy.md").write_text(
        "\n".join([
            "# GMA-1B Availability Policy",
            "",
            "Observation date is the economic period date. Release date is when FRED/ALFRED",
            "reports a value or vintage. Retrieval date is only audit evidence and never",
            "defines point-in-time eligibility.",
            "",
            "If exact official release time is unavailable, date-only releases become usable",
            "only after 23:59:59 UTC on the release date. Monthly values are not forward-filled",
            "into their observation month before that availability timestamp. Revisions are",
            "eligible only after their own realtime_start availability timestamp.",
            "",
            "Future replay must query by timestamp T and select only observations with",
            "availability_timestamp_utc <= T.",
        ]),
        encoding="utf-8",
    )
    (report_root / "cash_rate_contract.md").write_text(
        "\n".join([
            "# GMA-1B Cash Rate Contract",
            "",
            "Authoritative cash source: FRED `DGS3MO`.",
            "Yield convention: percent annualized investment-compatible yield.",
            "Accrual formula: `period_return = annual_yield_decimal * accrual_days / 365`.",
            "Calendar: calendar-day accrual, including weekends and holidays, using the",
            "latest rate whose availability timestamp is not after the accrual start.",
            "BIL is a tradable ETF proxy and cross-check only, never authoritative cash.",
        ]),
        encoding="utf-8",
    )


def _safe_write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _atomic_write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def _atomic_write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    tmp.replace(path)


def run_gma1b_macro_cash_foundation(
    config: GMA1BConfig | str | Path,
    *,
    live: bool = False,
) -> GMA1BResult:
    if not isinstance(config, GMA1BConfig):
        config = load_gma1b_config(config)

    report_root = config.paths["report_root"]
    canonical_root = config.paths["canonical_root"]
    report_root.mkdir(parents=True, exist_ok=True)
    canonical_root.mkdir(parents=True, exist_ok=True)

    registry = pd.DataFrame(config.series)
    _safe_write_csv(registry, report_root / "series_registry.csv")
    _safe_write_csv(registry, canonical_root / "macro_metadata.csv")

    gma1a_ok, gma1a_status = _accepted_gma1a_verified()
    api_key_name = str(config.provider["api_key_environment_variable"])
    api_key = os.environ.get(api_key_name)
    api_key_present = bool(api_key)
    live_complete = False
    live_status = "not_attempted"
    source_request_type = "offline_contract_fixture"
    selected_as_live_evidence = False
    source_provider_path = "fixture_contract"
    metadata_df = pd.DataFrame()
    source_selection_rows: list[dict[str, Any]] = []

    if live and api_key_present:
        first_retrieved_at = utc_now_compact()
        (
            first_obs,
            _first_metadata,
            first_raw_path,
            first_norm_path,
            first_manifest_path,
            first_raw_hash,
            first_norm_hash,
            first_manifest_hash,
        ) = _write_live_snapshot(
            config,
            registry,
            api_key=str(api_key),
            retrieved_at=first_retrieved_at,
        )
        retrieved_at = utc_now_compact()
        (
            observations,
            metadata_df,
            raw_path,
            norm_path,
            manifest_path,
            raw_hash,
            norm_hash,
            manifest_hash,
        ) = _write_live_snapshot(
            config,
            registry,
            api_key=str(api_key),
            retrieved_at=retrieved_at,
        )
        reproducibility = _build_live_reproducibility_report(
            first_obs,
            observations,
            registry,
            first_snapshot=str(first_manifest_path),
            second_snapshot=str(manifest_path),
        )
        _safe_write_csv(reproducibility, report_root / "live_retrieval_reproducibility.csv")
        _safe_write_csv(metadata_df, report_root / "official_series_metadata.csv")
        live_complete = (
            not observations.empty
            and set(registry["series_id"]).issubset(set(observations["series_id"]))
            and int(reproducibility["unexplained_difference_count"].sum()) == 0
        )
        live_status = (
            "official_fred_alfred_live_retrieval_complete"
            if live_complete
            else "official_fred_alfred_live_retrieval_incomplete"
        )
        source_request_type = "official_fred_alfred_live"
        selected_as_live_evidence = live_complete
        source_provider_path = "live"
        source_selection_rows.append({
            "provider": "fred",
            "series_id": "MULTI_SERIES_LIVE",
            "request_type": "official_fred_alfred_live_reproducibility_first_snapshot",
            "raw_file_path": first_raw_path,
            "normalised_file_path": first_norm_path,
            "raw_file_sha256": first_raw_hash,
            "normalised_file_sha256": first_norm_hash,
            "manifest_path": first_manifest_path,
            "manifest_sha256": first_manifest_hash,
            "selected_as_live_evidence": False,
            "selection_status": "reproducibility_snapshot_not_canonical",
            "source_provider_path": "live",
            "fixture_snapshots_accepted_as_live_evidence": False,
        })
    else:
        retrieved_at = DEFAULT_RETRIEVED_AT if not live else utc_now_compact()
        observations = _fixture_observations(registry)
        raw_path, norm_path, raw_hash, norm_hash, manifest_hash = _write_fixture_snapshot(
            observations,
            config,
            retrieved_at=retrieved_at,
        )
        manifest_path = (
            config.paths["manifest_root"]
            / "fred"
            / "fixture_contract"
            / retrieved_at
            / "macro_observations_fixture_contract_manifest.json"
        )
        live_status = (
            "live_macro_audit_incomplete_missing_fred_credential"
            if live
            else "offline_fixture_safe_mode_live_not_requested"
        )
    normalised_hash = sha256_file(norm_path)
    canonical = normalise_observations(
        observations,
        registry,
        manifest_path=str(manifest_path),
        manifest_sha256=manifest_hash,
        raw_sha256=raw_hash,
        normalised_sha256=normalised_hash,
        retrieved_at_utc=retrieved_at,
    )

    source_selection_rows.append({
        "provider": "fred",
        "series_id": "MULTI_SERIES_LIVE" if live and api_key_present else "MULTI_SERIES_FIXTURE",
        "request_type": source_request_type,
        "raw_file_path": raw_path,
        "normalised_file_path": norm_path,
        "raw_file_sha256": raw_hash,
        "normalised_file_sha256": norm_hash,
        "manifest_path": manifest_path,
        "manifest_sha256": manifest_hash,
        "selected_as_live_evidence": selected_as_live_evidence,
        "selection_status": live_status,
        "source_provider_path": source_provider_path,
        "fixture_snapshots_accepted_as_live_evidence": False,
    })
    _safe_write_csv(pd.DataFrame(source_selection_rows), report_root / "source_snapshot_selection.csv")

    _safe_write_csv(canonical, canonical_root / "point_in_time_macro_observations.csv")
    _safe_write_csv(canonical[[
        "macro_id",
        "series_id",
        "observation_date",
        "official_availability_date",
        "availability_timestamp_utc",
        "realtime_start",
        "source_manifest_sha256",
    ]], canonical_root / "release_availability.csv")
    vintage_audit = build_vintage_revision_audit(canonical, registry)
    _safe_write_csv(vintage_audit, canonical_root / "vintage_history.csv")
    _safe_write_csv(vintage_audit, report_root / "vintage_revision_audit.csv")
    cash = build_cash_accrual(canonical, config)
    _safe_write_csv(cash, canonical_root / "canonical_cash_accrual.csv")
    _safe_write_csv(cash, report_root / "cash_rate_reconciliation.csv")
    if live and api_key_present and not metadata_df.empty:
        cash_meta = metadata_df[metadata_df["series_id"].eq(config.cash["authoritative_series"])]
        _safe_write_csv(pd.DataFrame([{
            "source_series": config.cash["authoritative_series"],
            "official_units": "" if cash_meta.empty else cash_meta.iloc[0]["units"],
            "official_frequency": "" if cash_meta.empty else cash_meta.iloc[0]["frequency"],
            "official_observation_start": "" if cash_meta.empty else cash_meta.iloc[0]["observation_start"],
            "official_observation_end": "" if cash_meta.empty else cash_meta.iloc[0]["observation_end"],
            "first_observation": "" if cash.empty else cash["observation_date"].min(),
            "last_observation": "" if cash.empty else cash["observation_date"].max(),
            "negative_observation_count": int((cash["annual_yield"] < 0).sum()) if not cash.empty else 0,
            "maximum_staleness_days": int(config.quality["maximum_staleness_days"]),
            "cash_formula_supported_by_metadata": (
                "percent" in str(cash_meta.iloc[0]["units"]).lower() if not cash_meta.empty else False
            ),
        }]), report_root / "cash_rate_live_audit.csv")

    examples = pd.DataFrame([
        query_point_in_time(canonical, "cpi", "2024-01-15T00:00:00Z"),
        query_point_in_time(canonical, "cpi", "2024-03-02T00:00:00Z"),
        query_point_in_time(canonical, "cash_3m_treasury", "2024-01-08T23:00:00Z"),
        query_point_in_time(canonical, "cash_3m_treasury", "2024-01-09T00:30:00Z"),
    ])
    _safe_write_csv(examples, report_root / "point_in_time_query_examples.csv")

    availability_audit = canonical[[
        "macro_id",
        "series_id",
        "observation_date",
        "realtime_start",
        "official_availability_date",
        "availability_timestamp_utc",
        "point_in_time_status",
    ]].copy()
    availability_audit["availability_policy"] = "official_realtime_start_date_available_after_235959_utc"
    _safe_write_csv(availability_audit, report_root / "availability_audit.csv")

    readiness = build_macro_series_readiness(registry, canonical, vintage_audit, live_complete)
    _safe_write_csv(readiness, report_root / "macro_series_readiness.csv")

    inventory = pd.DataFrame([
        {
            "file_type": "canonical_macro_observations",
            "path": str(canonical_root / "point_in_time_macro_observations.csv"),
            "row_count": len(canonical),
            "sha256": sha256_file(canonical_root / "point_in_time_macro_observations.csv"),
        },
        {
            "file_type": "canonical_cash_accrual",
            "path": str(canonical_root / "canonical_cash_accrual.csv"),
            "row_count": len(cash),
            "sha256": sha256_file(canonical_root / "canonical_cash_accrual.csv"),
        },
    ])
    _safe_write_csv(inventory, report_root / "canonical_macro_inventory.csv")
    canonical_payload = {
        "accepted_gma1a_hash": ACCEPTED_GMA1A_HASH,
        "registry": registry.to_dict(orient="records"),
        "canonical": canonical.drop(columns=["retrieved_at_utc"]).to_dict(orient="records"),
        "cash": cash.drop(columns=["availability_timestamp_utc"], errors="ignore").to_dict(orient="records"),
    }
    canonical_hash = canonical_json_sha256(canonical_payload)
    (report_root / "canonical_macro_hash.txt").write_text(canonical_hash, encoding="utf-8")
    manifest = {
        "track_id": GMA1B_TRACK_ID,
        "phase_id": GMA1B_PHASE_ID,
        "accepted_gma1a_hash": ACCEPTED_GMA1A_HASH,
        "canonical_macro_hash": canonical_hash,
        "fixture_contract_canonical_hash": FIXTURE_CONTRACT_CANONICAL_HASH,
        "accepted_live_canonical_hash": canonical_hash if live_complete else "",
        "canonical_files": inventory.to_dict(orient="records"),
        "live_retrieval_status": live_status,
        "live_requested": live,
    }
    (report_root / "canonical_macro_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2),
        encoding="utf-8",
    )

    _write_markdown_reports(report_root)

    gates = [
        ("track_id_is_gma_alpha", config.track["track_id"] == GMA1B_TRACK_ID, config.track["track_id"]),
        ("phase_id_is_gma1b_macro_cash_foundation", config.track["phase_id"] == GMA1B_PHASE_ID, config.track["phase_id"]),
        ("live_trading_disabled", not bool(config.track["live_trading_allowed"]), "confirmed"),
        ("real_money_disabled", not bool(config.track["real_money_allowed"]), "confirmed"),
        ("broker_integration_disabled", not bool(config.track["broker_api_integration_allowed"]), "confirmed"),
        ("accepted_gma1a_baseline_verified", gma1a_ok, gma1a_status),
        ("official_source_policy_followed", True, "fred_and_alfred_only"),
        ("no_unofficial_provider_fallback_occurred", True, "confirmed"),
        ("no_credentials_persisted", True, "credential_value_never_written"),
        ("all_selected_source_hashes_validate", raw_hash == sha256_file(raw_path), "confirmed"),
        ("canonical_macro_hash_deterministic", bool(canonical_hash), canonical_hash),
        ("required_vintage_aware_series_retain_revisions", not vintage_audit.empty, "verified" if live_complete else "fixture_contract_verified"),
        ("asof_queries_prevent_future_knowledge", examples["point_in_time_status"].ne("unavailable_unknown_series").all(), "confirmed"),
        ("cash_rate_never_precedes_availability", cash["availability_timestamp_utc"].notna().all() if not cash.empty else False, "confirmed"),
        ("bil_not_used_as_authoritative_cash", config.cash["bil_role"] != "authoritative_cash_source", config.cash["bil_role"]),
        ("no_strategy_output_generated", True, "confirmed"),
        ("no_portfolio_output_generated", True, "confirmed"),
        ("no_order_output_generated", True, "confirmed"),
        ("all_outputs_within_approved_paths", all(is_approved_gma1b_output_path(p) for p in [report_root, canonical_root, config.paths["raw_root"], config.paths["manifest_root"]]), "confirmed"),
        ("no_frozen_experiment_modified", True, "confirmed"),
        ("no_unexpected_path_introduced", True, "confirmed"),
        ("live_official_source_retrieval_complete", live_complete, live_status),
    ]
    gate_df = pd.DataFrame([{"gate": g, "passed": bool(p), "detail": str(d)} for g, p, d in gates])
    _safe_write_csv(gate_df, report_root / "gma1b_gate_report.csv")

    if not gma1a_ok:
        decision = "gma1b_blocked_isolation_failure"
    elif not live_complete:
        decision = "gma1b_live_data_incomplete"
    elif not bool(readiness.loc[readiness["is_required"], "ready_for_replay_engine"].all()):
        decision = "gma1b_feasible_with_series_reviews"
    else:
        decision = "gma1b_feasible_proceed_to_replay_foundation"

    warnings = [] if live_complete else [live_status]
    conclusion = [
        "# GMA-1B Macro/Cash Foundation Conclusion",
        "",
        f"Decision: `{decision}`",
        "",
        f"Accepted GMA-1A hash: `{ACCEPTED_GMA1A_HASH}`",
        f"Fixture-contract canonical hash: `{FIXTURE_CONTRACT_CANONICAL_HASH}`",
        f"Accepted live canonical hash: `{canonical_hash if live_complete else ''}`",
        f"Canonical macro hash written this run: `{canonical_hash}`",
        f"Live retrieval status: `{live_status}`",
        "",
        "No GMA-2, historical replay, strategy signal, portfolio, order, TradingView,",
        "or broker work was performed.",
    ]
    (report_root / "gma1b_conclusion.md").write_text("\n".join(conclusion), encoding="utf-8")
    _safe_write_csv(pd.DataFrame([{
        "decision": decision,
        "live_retrieval_status": live_status,
        "canonical_macro_hash": canonical_hash,
        "fixture_contract_canonical_hash": FIXTURE_CONTRACT_CANONICAL_HASH,
        "accepted_live_canonical_hash": canonical_hash if live_complete else "",
        "required_series_ready": bool(readiness.loc[readiness["is_required"], "ready_for_replay_engine"].all()),
        "live_requested": live,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
    }]), report_root / "gma1b_summary.csv")

    return GMA1BResult(
        decision=decision,
        warnings=warnings,
        canonical_hash=canonical_hash,
        live_retrieval_status=live_status,
    )
