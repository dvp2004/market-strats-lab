"""Bounded official S&P Global change-announcement reconciliation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from market_strats.universe.hashing import sha256_bytes


@dataclass(frozen=True)
class AnnouncementReconciliation:
    sample_id: str
    announcement_url: str
    publication_date: str
    effective_date: str
    content_sha256: str | None
    expected_tickers: tuple[str, ...]
    matched_tickers: tuple[str, ...]
    status: str
    retrieval_timestamp: str


def _default_get(url: str, headers: dict[str, str], timeout: int) -> bytes:
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.content


def reconcile_bounded_announcements(
    *,
    samples: list[dict[str, object]],
    raw_root: Path,
    user_agent: str,
    timeout_seconds: int,
    get_bytes: Callable[[str, dict[str, str], int], bytes] = _default_get,
) -> list[AnnouncementReconciliation]:
    raw_root.mkdir(parents=True, exist_ok=True)
    rows: list[AnnouncementReconciliation] = []
    for sample in samples:
        expected = tuple(str(item).upper() for item in sample["added_tickers"])
        try:
            payload = get_bytes(
                str(sample["announcement_url"]),
                {"User-Agent": user_agent},
                timeout_seconds,
            )
        except Exception:
            rows.append(
                AnnouncementReconciliation(
                    sample_id=str(sample["sample_id"]),
                    announcement_url=str(sample["announcement_url"]),
                    publication_date=str(sample["publication_date"]),
                    effective_date=str(sample["effective_date"]),
                    content_sha256=None,
                    expected_tickers=expected,
                    matched_tickers=(),
                    status="official_evidence_unavailable",
                    retrieval_timestamp=datetime.now(UTC).isoformat(),
                )
            )
            continue
        text = payload.decode("utf-8", errors="ignore").upper()
        matched = tuple(ticker for ticker in expected if ticker in text)
        path = raw_root / f"{sample['sample_id']}.html"
        path.write_bytes(payload)
        rows.append(
            AnnouncementReconciliation(
                sample_id=str(sample["sample_id"]),
                announcement_url=str(sample["announcement_url"]),
                publication_date=str(sample["publication_date"]),
                effective_date=str(sample["effective_date"]),
                content_sha256=sha256_bytes(payload),
                expected_tickers=expected,
                matched_tickers=matched,
                status="passed" if matched == expected else "factual_metadata_not_reconciled",
                retrieval_timestamp=datetime.now(UTC).isoformat(),
            )
        )
    return rows
