"""Deterministic raw snapshot writing and manifest helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from market_strats.intelligence.contracts import RawSnapshotManifest
from market_strats.intelligence.data.source import SourceInstrumentData

PARSER_VERSION = "mi1_market_data_parser_v1"


def _json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")


def snapshot_id_for(source_data: SourceInstrumentData, content_sha256: str) -> str:
    basis = (
        f"{source_data.source_id}|{source_data.dataset_name}|"
        f"{source_data.instrument.instrument_id}|{content_sha256}"
    )
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return f"{source_data.source_id}_{source_data.instrument.symbol}_{digest[:24]}".lower()


def write_raw_snapshot(
    *,
    source_data: SourceInstrumentData,
    raw_root: Path,
    retrieved_at_utc: datetime,
    publication_permission: str,
    availability_evidence_level: str,
) -> RawSnapshotManifest:
    raw_root.mkdir(parents=True, exist_ok=True)
    content = canonical_json_bytes(source_data.raw_payload)
    content_sha256 = hashlib.sha256(content).hexdigest()
    snapshot_id = snapshot_id_for(source_data, content_sha256)
    raw_path = raw_root / f"{snapshot_id}.json"
    raw_path.write_bytes(content)

    return RawSnapshotManifest(
        snapshot_id=snapshot_id,
        source_name=source_data.source_name,
        dataset_name=source_data.dataset_name,
        request_parameters=source_data.request_parameters,
        retrieved_at_utc=retrieved_at_utc,
        content_sha256=content_sha256,
        parser_version=PARSER_VERSION,
        raw_path=str(raw_path),
        publication_permission=publication_permission,
        availability_evidence_level=availability_evidence_level,
    )
