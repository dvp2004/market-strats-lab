"""Revision-pinned MediaWiki S&P 500 reconciliation adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode

import requests

from market_strats.universe.contracts import UniverseContractError
from market_strats.universe.hashing import sha256_bytes


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "table" and self._table is None:
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None


@dataclass(frozen=True)
class WikimediaSnapshot:
    page_title: str
    page_id: int
    revision_id: int
    revision_timestamp: str
    revision_sha1: str
    retrieval_timestamp: str
    content_hash: str
    licence_attribution: str
    current_constituents: tuple[dict[str, str], ...]
    historical_changes: tuple[dict[str, str], ...]
    raw_paths: tuple[Path, ...]


def _default_get(url: str, headers: dict[str, str], timeout: int) -> bytes:
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.content


def _tables_from_html(html: str) -> list[list[list[str]]]:
    parser = _TableParser()
    parser.feed(html)
    return parser.tables


def _rows_as_dicts(table: list[list[str]]) -> list[dict[str, str]]:
    if len(table) < 2:
        return []
    headers = [header.strip().lower() for header in table[0]]
    rows = []
    for values in table[1:]:
        padded = values + [""] * max(0, len(headers) - len(values))
        rows.append(dict(zip(headers, padded, strict=False)))
    return rows


def fetch_pinned_wikimedia_snapshot(
    *,
    api_url: str,
    page_title: str,
    expected_page_id: int,
    revision_id: int,
    expected_revision_sha1: str,
    raw_root: Path,
    user_agent: str,
    timeout_seconds: int,
    get_bytes: Callable[[str, dict[str, str], int], bytes] = _default_get,
) -> WikimediaSnapshot:
    if not user_agent.strip():
        raise UniverseContractError("Wikimedia adapter requires a descriptive User-Agent")
    raw_root.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": user_agent}
    query_parameters = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "prop": "revisions",
        "revids": revision_id,
        "rvprop": "ids|timestamp|sha1",
    }
    parse_parameters = {
        "action": "parse",
        "format": "json",
        "formatversion": 2,
        "oldid": revision_id,
        "prop": "text",
    }
    query_url = f"{api_url}?{urlencode(query_parameters)}"
    parse_url = f"{api_url}?{urlencode(parse_parameters)}"
    metadata_bytes = get_bytes(query_url, headers, timeout_seconds)
    parse_bytes = get_bytes(parse_url, headers, timeout_seconds)
    metadata = json.loads(metadata_bytes)
    parsed = json.loads(parse_bytes)
    page = metadata["query"]["pages"][0]
    revision = page["revisions"][0]
    if int(page["pageid"]) != expected_page_id or int(revision["revid"]) != revision_id:
        raise UniverseContractError("Wikimedia page or revision identity mismatch")
    if str(revision["sha1"]).lower() != expected_revision_sha1.lower():
        raise UniverseContractError("Wikimedia revision SHA-1 mismatch")
    html = parsed["parse"]["text"]
    tables = _tables_from_html(html)
    if len(tables) < 2:
        raise UniverseContractError("Pinned Wikimedia revision lacks required tables")
    table_rows = [_rows_as_dicts(table) for table in tables]
    current = next(
        (rows for rows in table_rows if rows and "symbol" in rows[0] and "security" in rows[0]),
        None,
    )
    changes = next(
        (
            rows
            for rows in table_rows
            if rows
            and any("date" in key for key in rows[0])
            and any("added" in key for key in rows[0])
        ),
        None,
    )
    if current is None or changes is None:
        raise UniverseContractError("Pinned Wikimedia tables do not match expected semantics")
    metadata_path = raw_root / f"revision_{revision_id}_metadata.json"
    content_path = raw_root / f"revision_{revision_id}_parse.json"
    metadata_path.write_bytes(metadata_bytes)
    content_path.write_bytes(parse_bytes)
    retrieved = datetime.now(UTC).isoformat()
    return WikimediaSnapshot(
        page_title=page_title,
        page_id=int(page["pageid"]),
        revision_id=revision_id,
        revision_timestamp=str(revision["timestamp"]),
        revision_sha1=str(revision["sha1"]),
        retrieval_timestamp=retrieved,
        content_hash=sha256_bytes(parse_bytes),
        licence_attribution="CC BY-SA 4.0; English Wikipedia contributors",
        current_constituents=tuple(current),
        historical_changes=tuple(changes),
        raw_paths=(metadata_path, content_path),
    )
