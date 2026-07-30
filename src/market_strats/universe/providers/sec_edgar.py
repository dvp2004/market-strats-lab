"""Official SEC EDGAR identity and filing-availability adapter."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from market_strats.universe.contracts import UniverseContractError
from market_strats.universe.hashing import sha256_bytes


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
    content_sha256: str
    raw_path: Path


def _default_get(url: str, headers: dict[str, str], timeout: int) -> bytes:
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.content


class SecEdgarAdapter:
    def __init__(
        self,
        *,
        user_agent: str,
        raw_root: Path,
        timeout_seconds: int = 30,
        minimum_request_interval_seconds: float = 0.11,
        get_bytes: Callable[[str, dict[str, str], int], bytes] = _default_get,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not user_agent.strip() or "@" not in user_agent:
            raise UniverseContractError(
                "SEC User-Agent must identify the research software and a contact address"
            )
        self.user_agent = user_agent
        self.raw_root = raw_root
        self.timeout_seconds = timeout_seconds
        self.minimum_request_interval_seconds = minimum_request_interval_seconds
        self.get_bytes = get_bytes
        self.sleeper = sleeper
        self._last_request_at: float | None = None

    def _fetch(self, url: str, filename: str) -> tuple[dict[str, object], SecSnapshot]:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            wait = max(0.0, self.minimum_request_interval_seconds - elapsed)
            if wait:
                self.sleeper(wait)
        payload = self.get_bytes(
            url,
            {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
            self.timeout_seconds,
        )
        self._last_request_at = time.monotonic()
        parsed = json.loads(payload)
        self.raw_root.mkdir(parents=True, exist_ok=True)
        raw_path = self.raw_root / filename
        raw_path.write_bytes(payload)
        return parsed, SecSnapshot(
            source_url=url,
            retrieved_at_utc=datetime.now(UTC).isoformat(),
            content_sha256=sha256_bytes(payload),
            raw_path=raw_path,
        )

    def fetch_company_ticker_mappings(
        self,
    ) -> tuple[list[SecTickerMapping], SecSnapshot]:
        url = "https://www.sec.gov/files/company_tickers_exchange.json"
        payload, snapshot = self._fetch(url, "company_tickers_exchange.json")
        fields = payload.get("fields")
        data = payload.get("data")
        if fields != ["cik", "name", "ticker", "exchange"] or not isinstance(data, list):
            raise UniverseContractError("SEC company ticker mapping schema changed unexpectedly")
        rows = [
            SecTickerMapping(
                cik=str(item[0]).zfill(10),
                name=str(item[1]),
                ticker=str(item[2]).upper(),
                exchange=str(item[3]),
            )
            for item in data
            if isinstance(item, list) and len(item) == 4
        ]
        return rows, snapshot

    def fetch_submission_history(
        self,
        cik: str,
    ) -> tuple[list[dict[str, object]], SecSnapshot]:
        normalized = str(cik).zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{normalized}.json"
        payload, snapshot = self._fetch(url, f"submissions_CIK{normalized}.json")
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
