"""Credential-free yfinance daily EOD adapter for MI-1."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from market_strats.intelligence.contracts import InstrumentRegistryEntry
from market_strats.intelligence.data.source import SourceInstrumentData


class YFinanceEodAdapter:
    """Fetch daily ETF OHLCV, adjusted close, dividends, and splits through yfinance."""

    source_id = "yfinance_eod_mi1"
    source_name = "Yahoo Finance daily EOD via yfinance"

    def __init__(self, *, auto_adjust: bool = False, actions: bool = True) -> None:
        if auto_adjust:
            raise ValueError("MI-1 yfinance adapter must use auto_adjust=False")
        self.auto_adjust = auto_adjust
        self.actions = actions

    def fetch_eod(
        self,
        instruments: list[InstrumentRegistryEntry],
        start: date,
        end: date | None,
    ) -> list[SourceInstrumentData]:
        import yfinance as yf

        end_exclusive = None if end is None else end + timedelta(days=1)
        results: list[SourceInstrumentData] = []
        for instrument in instruments:
            ticker = yf.Ticker(instrument.source_symbol)
            history = ticker.history(
                start=start.isoformat(),
                end=None if end_exclusive is None else end_exclusive.isoformat(),
                auto_adjust=self.auto_adjust,
                actions=self.actions,
            )
            records = history.reset_index().to_dict(orient="records")
            bars: list[dict[str, Any]] = []
            dividends: list[dict[str, Any]] = []
            splits: list[dict[str, Any]] = []
            for record in records:
                session_date = record.get("Date") or record.get("Datetime")
                if hasattr(session_date, "date"):
                    session_date = session_date.date()
                row = {
                    "source_symbol": instrument.source_symbol,
                    "session_date": session_date,
                    "open": record.get("Open"),
                    "high": record.get("High"),
                    "low": record.get("Low"),
                    "close": record.get("Close"),
                    "volume": record.get("Volume"),
                    "adj_close": record.get("Adj Close"),
                }
                bars.append(row)
                dividend = record.get("Dividends", 0)
                split = record.get("Stock Splits", 0)
                if dividend not in (None, 0):
                    dividends.append(
                        {
                            "source_symbol": instrument.source_symbol,
                            "session_date": session_date,
                            "value": dividend,
                        }
                    )
                if split not in (None, 0):
                    splits.append(
                        {
                            "source_symbol": instrument.source_symbol,
                            "session_date": session_date,
                            "value": split,
                        }
                    )

            request_parameters = {
                "source_symbol": instrument.source_symbol,
                "start": start.isoformat(),
                "end_inclusive": None if end is None else end.isoformat(),
                "auto_adjust": self.auto_adjust,
                "actions": self.actions,
            }
            raw_payload = {
                "request_parameters": request_parameters,
                "history": records,
                "bars": bars,
                "dividends": dividends,
                "splits": splits,
            }
            results.append(
                SourceInstrumentData(
                    source_id=self.source_id,
                    source_name=self.source_name,
                    dataset_name="daily_eod_ohlcv_actions",
                    instrument=instrument,
                    request_parameters=request_parameters,
                    raw_payload=raw_payload,
                    bars=bars,
                    dividends=dividends,
                    splits=splits,
                )
            )
        return results
