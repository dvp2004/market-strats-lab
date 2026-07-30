"""Source protocol and source-neutral raw records for MI-1 EOD data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from market_strats.intelligence.contracts import InstrumentRegistryEntry


@dataclass(frozen=True)
class SourceInstrumentData:
    source_id: str
    source_name: str
    dataset_name: str
    instrument: InstrumentRegistryEntry
    request_parameters: dict[str, Any]
    raw_payload: dict[str, Any]
    bars: list[dict[str, Any]]
    dividends: list[dict[str, Any]]
    splits: list[dict[str, Any]]


class EodMarketDataSource(Protocol):
    """Interface for credential-free or credentialed future EOD sources."""

    source_id: str
    source_name: str

    def fetch_eod(
        self,
        instruments: list[InstrumentRegistryEntry],
        start: date,
        end: date | None,
    ) -> list[SourceInstrumentData]:
        """Fetch raw daily EOD data. The optional end date is inclusive."""
