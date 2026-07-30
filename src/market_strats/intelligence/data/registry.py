"""Instrument registry loading for the fixed MI-1 ETF universe."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from market_strats.intelligence.contracts import InstrumentRegistryEntry

DEFAULT_ELIGIBLE_FROM = date(1900, 1, 1)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_instrument_registry(path: Path) -> list[InstrumentRegistryEntry]:
    config = load_yaml(path)
    assets = config.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Universe config must contain an assets list")

    registry_version = int(config["registry_version"])
    instruments: list[InstrumentRegistryEntry] = []
    seen_symbols: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise ValueError("Each universe asset must be a mapping")
        symbol = str(asset["symbol"]).upper()
        if symbol in seen_symbols:
            raise ValueError(f"Duplicate universe symbol: {symbol}")
        seen_symbols.add(symbol)
        instruments.append(
            InstrumentRegistryEntry(
                instrument_id=f"mi1_etf_{symbol.lower()}",
                symbol=symbol,
                asset_class="ETF",
                currency="USD",
                exchange_calendar="XNYS",
                source_symbol=symbol,
                eligible_from=DEFAULT_ELIGIBLE_FROM,
                active=True,
                registry_version=registry_version,
                role=str(asset.get("role", "")),
            )
        )

    if len(instruments) != 22:
        raise ValueError(f"MI-1 universe must contain exactly 22 ETFs, found {len(instruments)}")
    return instruments
