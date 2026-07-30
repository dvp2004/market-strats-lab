"""Compliant, cached SEC EDGAR identity acquisition."""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from market_strats.universe.contracts import UniverseContractError
from market_strats.universe.hashing import sha256_bytes, sha256_json

SEC_USER_AGENT_ENV = "SEC_USER_AGENT"
SEC_PARSER_VERSION = "sec_identity_v2"
SEC_MAPPING_URLS = (
    "https://www.sec.gov/files/company_tickers_exchange.json",
    "https://www.sec.gov/files/company_tickers.json",
)
SEC_BULK_SUBMISSIONS_URL = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"


class SecAccessError(UniverseContractError):
    """Sanitized SEC transport failure."""

    def __init__(self, status_code: int, category: str, retry_after: str | None = None) -> None:
        self.status_code = status_code
        self.category = category
        self.retry_after = retry_after
        super().__init__(f"SEC request failed: {category} (HTTP {status_code})")


@dataclass(frozen=True)
class SecHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes


@dataclass(frozen=True)
class SecTickerMapping:
    cik: str
    name: str
    ticker: str
    exchange: str


@dataclass(frozen=True)
class SecSnapshot:
    source_url: str
    retrieved_at_utc: str
    response_status: int
    etag: str | None
    last_modified: str | None
    content_sha256: str
    sec_user_agent_present: bool
    parser_version: str
    cache_hit: bool
    raw_path: Path


def validate_sec_user_agent(value: str | None) -> str:
    candidate = (value or "").strip()
    email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", candidate)
    organization = candidate[: email.start()].strip(" ();,:") if email else ""
    if not email or len(organization) < 2:
        raise UniverseContractError(
            "SEC_USER_AGENT must contain an application or organization name and contact email"
        )
    return candidate


def sec_user_agent_from_environment() -> str:
    return validate_sec_user_agent(os.environ.get(SEC_USER_AGENT_ENV))


def _default_get(url: str, headers: dict[str, str], timeout: int) -> SecHttpResponse:
    response = requests.get(url, headers=headers, timeout=timeout)
    return SecHttpResponse(response.status_code, response.headers, response.content)


def _normalized_name(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", value.lower()).split())


def resolve_cik_candidates(
    *,
    issuer_name: str,
    ticker: str,
    exchange: str | None,
    mappings: list[SecTickerMapping],
    former_names: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[str, str | None]:
    """Resolve with name/ticker/exchange evidence; never accept ticker alone."""

    target_name = _normalized_name(issuer_name)
    target_ticker = ticker.upper().replace(".", "-")
    candidates: list[SecTickerMapping] = []
    for row in mappings:
        names = {_normalized_name(row.name)}
        names.update(_normalized_name(item) for item in (former_names or {}).get(row.cik, ()))
        ticker_match = row.ticker.upper().replace(".", "-") == target_ticker
        name_match = target_name in names
        exchange_match = (
            not exchange or not row.exchange or row.exchange.upper() == exchange.upper()
        )
        if name_match and exchange_match and (ticker_match or target_name in names):
            candidates.append(row)
    ciks = sorted({row.cik for row in candidates})
    if len(ciks) == 1:
        return "resolved_sec_cik", ciks[0]
    if len(ciks) > 1:
        return "ambiguous_multiple_candidates", None
    return "unresolved_no_candidate", None


class SecEdgarAdapter:
    def __init__(
        self,
        *,
        user_agent: str | None,
        raw_root: Path,
        timeout_seconds: int = 30,
        maximum_requests_per_second: float = 5,
        maximum_attempts: int = 3,
        get_response: Callable[[str, dict[str, str], int], SecHttpResponse] = _default_get,
        get_bytes: Callable[[str, dict[str, str], int], bytes] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.user_agent = validate_sec_user_agent(user_agent)
        if maximum_requests_per_second <= 0 or maximum_requests_per_second > 5:
            raise UniverseContractError("SEC request rate must be in (0, 5] requests per second")
        if maximum_attempts < 1:
            raise UniverseContractError("SEC maximum_attempts must be positive")
        self.raw_root = raw_root
        self.timeout_seconds = timeout_seconds
        self.minimum_interval = 1 / maximum_requests_per_second
        self.maximum_attempts = maximum_attempts
        if get_bytes is not None:
            self.get_response = lambda url, headers, timeout: SecHttpResponse(
                200, {}, get_bytes(url, headers, timeout)
            )
        else:
            self.get_response = get_response
        self.sleeper = sleeper
        self._last_request_at: float | None = None

    @classmethod
    def from_environment(cls, *, raw_root: Path, **kwargs: Any) -> SecEdgarAdapter:
        return cls(user_agent=sec_user_agent_from_environment(), raw_root=raw_root, **kwargs)

    def _cache_paths(self, url: str, filename: str) -> tuple[Path, Path]:
        key = sha256_json({"url": url, "parser": SEC_PARSER_VERSION})[:16]
        return self.raw_root / f"{key}_{filename}", self.raw_root / f"{key}_{filename}.meta.json"

    def _snapshot(
        self,
        *,
        url: str,
        raw_path: Path,
        meta: Mapping[str, Any],
        content: bytes,
        cache_hit: bool,
    ) -> SecSnapshot:
        return SecSnapshot(
            source_url=url,
            retrieved_at_utc=str(meta["retrieved_at_utc"]),
            response_status=int(meta["response_status"]),
            etag=meta.get("etag"),
            last_modified=meta.get("last_modified"),
            content_sha256=sha256_bytes(content),
            sec_user_agent_present=True,
            parser_version=SEC_PARSER_VERSION,
            cache_hit=cache_hit,
            raw_path=raw_path,
        )

    def _fetch(self, url: str, filename: str) -> tuple[bytes, SecSnapshot]:
        self.raw_root.mkdir(parents=True, exist_ok=True)
        raw_path, meta_path = self._cache_paths(url, filename)
        if raw_path.is_file() and meta_path.is_file():
            content = raw_path.read_bytes()
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("content_sha256") == sha256_bytes(content):
                return content, self._snapshot(
                    url=url, raw_path=raw_path, meta=meta, content=content, cache_hit=True
                )

        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }
        for attempt in range(self.maximum_attempts):
            if self._last_request_at is not None:
                wait = max(0.0, self.minimum_interval - (time.monotonic() - self._last_request_at))
                if wait:
                    self.sleeper(wait)
            response = self.get_response(url, headers, self.timeout_seconds)
            self._last_request_at = time.monotonic()
            retry_after = response.headers.get("Retry-After")
            if response.status_code == 403:
                raise SecAccessError(403, "access_forbidden")
            if response.status_code == 429:
                if attempt + 1 == self.maximum_attempts:
                    raise SecAccessError(429, "rate_limited", retry_after)
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                self.sleeper(delay)
                continue
            if response.status_code >= 500 and attempt + 1 < self.maximum_attempts:
                self.sleeper(2**attempt)
                continue
            if response.status_code != 200:
                raise SecAccessError(response.status_code, "unexpected_http_status")
            retrieved = datetime.now(UTC).isoformat()
            meta = {
                "request_url": url,
                "retrieved_at_utc": retrieved,
                "response_status": response.status_code,
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "content_sha256": sha256_bytes(response.content),
                "sec_user_agent_present": True,
                "parser_version": SEC_PARSER_VERSION,
            }
            raw_path.write_bytes(response.content)
            meta_path.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
            return response.content, self._snapshot(
                url=url,
                raw_path=raw_path,
                meta=meta,
                content=response.content,
                cache_hit=False,
            )
        raise UniverseContractError("SEC bounded retry policy exhausted")

    def fetch_company_ticker_mappings(self) -> tuple[list[SecTickerMapping], SecSnapshot]:
        content, snapshot = self._fetch(SEC_MAPPING_URLS[0], "company_tickers_exchange.json")
        payload = json.loads(content)
        fields, data = payload.get("fields"), payload.get("data")
        if fields != ["cik", "name", "ticker", "exchange"] or not isinstance(data, list):
            raise UniverseContractError("SEC company ticker mapping schema changed unexpectedly")
        rows = [
            SecTickerMapping(
                str(item[0]).zfill(10), str(item[1]), str(item[2]).upper(), str(item[3])
            )
            for item in data
            if isinstance(item, list) and len(item) == 4
        ]
        return rows, snapshot

    def fetch_company_ticker_fallback(self) -> tuple[list[SecTickerMapping], SecSnapshot]:
        content, snapshot = self._fetch(SEC_MAPPING_URLS[1], "company_tickers.json")
        payload = json.loads(content)
        rows = [
            SecTickerMapping(
                str(item["cik_str"]).zfill(10),
                str(item["title"]),
                str(item["ticker"]).upper(),
                str(item.get("exchange", "")),
            )
            for item in payload.values()
        ]
        return rows, snapshot

    def fetch_bulk_submissions(self) -> tuple[bytes, SecSnapshot]:
        return self._fetch(SEC_BULK_SUBMISSIONS_URL, "submissions.zip")

    def fetch_submission_history(self, cik: str) -> tuple[list[dict[str, object]], SecSnapshot]:
        normalized = str(cik).zfill(10)
        url = f"https://www.sec.gov/Archives/edgar/data/{int(normalized)}/submissions.json"
        content, snapshot = self._fetch(url, f"submissions_CIK{normalized}.json")
        payload = json.loads(content)
        recent = payload.get("filings", {}).get("recent", {})
        accessions = recent.get("accessionNumber", [])
        accepted = recent.get("acceptanceDateTime", [])
        forms = recent.get("form", [])
        rows = [
            {
                "cik": normalized,
                "accession_number": accession,
                "form": forms[index] if index < len(forms) else None,
                "acceptance_timestamp": accepted[index] if index < len(accepted) else None,
            }
            for index, accession in enumerate(accessions)
        ]
        return rows, snapshot
