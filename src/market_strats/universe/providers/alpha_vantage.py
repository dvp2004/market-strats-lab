"""Optional free Alpha Vantage LISTING_STATUS lifecycle evidence."""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode

import requests

from market_strats.universe.contracts import UniverseContractError
from market_strats.universe.hashing import sha256_bytes, sha256_json

ALPHA_VANTAGE_KEY_ENV = "ALPHA_VANTAGE_API_KEY"
FREE_ENDPOINT = "LISTING_STATUS"


@dataclass(frozen=True)
class ListingStatusSnapshot:
    query_date: date
    content_sha256: str
    retrieved_at_utc: str
    cache_hit: bool
    rows: tuple[dict[str, str], ...]


def _default_get(url: str, timeout: int) -> bytes:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


class AlphaVantageListingStatusAdapter:
    def __init__(
        self,
        *,
        api_key: str | None,
        raw_root: Path,
        endpoint: str = FREE_ENDPOINT,
        timeout_seconds: int = 30,
        get_bytes: Callable[[str, int], bytes] = _default_get,
    ) -> None:
        if endpoint != FREE_ENDPOINT:
            raise UniverseContractError("Only the free LISTING_STATUS endpoint is permitted")
        if not (api_key or "").strip():
            raise UniverseContractError("ALPHA_VANTAGE_API_KEY is required for optional use")
        self._api_key = str(api_key)
        self.raw_root = raw_root
        self.timeout_seconds = timeout_seconds
        self.get_bytes = get_bytes

    @classmethod
    def from_environment(
        cls, *, raw_root: Path, **kwargs: object
    ) -> AlphaVantageListingStatusAdapter:
        return cls(api_key=os.environ.get(ALPHA_VANTAGE_KEY_ENV), raw_root=raw_root, **kwargs)

    def fetch(self, query_date: date) -> ListingStatusSnapshot:
        self.raw_root.mkdir(parents=True, exist_ok=True)
        cache_key = sha256_json({"function": FREE_ENDPOINT, "date": query_date.isoformat()})[:16]
        raw_path = self.raw_root / f"listing_status_{cache_key}.csv"
        meta_path = self.raw_root / f"listing_status_{cache_key}.meta.json"
        cache_hit = raw_path.is_file() and meta_path.is_file()
        if cache_hit:
            content = raw_path.read_bytes()
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            retrieved = str(meta["retrieved_at_utc"])
        else:
            query = urlencode(
                {
                    "function": FREE_ENDPOINT,
                    "date": query_date.isoformat(),
                    "state": "active",
                    "apikey": self._api_key,
                }
            )
            content = self.get_bytes(
                f"https://www.alphavantage.co/query?{query}", self.timeout_seconds
            )
            text = content.decode("utf-8", errors="replace")
            if "rate limit" in text.lower() or "thank you for using alpha vantage" in text.lower():
                raise UniverseContractError("Alpha Vantage free rate limit returned")
            retrieved = datetime.now(UTC).isoformat()
            raw_path.write_bytes(content)
            meta_path.write_text(
                json.dumps(
                    {
                        "retrieved_at_utc": retrieved,
                        "content_sha256": sha256_bytes(content),
                        "api_key_present": True,
                        "endpoint": FREE_ENDPOINT,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        rows = tuple(dict(row) for row in csv.DictReader(io.StringIO(content.decode("utf-8"))))
        return ListingStatusSnapshot(
            query_date=query_date,
            content_sha256=sha256_bytes(content),
            retrieved_at_utc=retrieved,
            cache_hit=cache_hit,
            rows=rows,
        )
