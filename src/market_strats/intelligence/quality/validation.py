"""Pure validation functions for MI-1 normalized market data."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from math import isfinite

from market_strats.intelligence.contracts import DataQualityEvent, MarketEodBar
from market_strats.intelligence.data.availability import SUPPORTED_EVIDENCE_LEVELS


class DataQualityError(RuntimeError):
    """Raised when fail-closed MI-1 data-quality checks find fatal events."""

    def __init__(self, events: list[DataQualityEvent]) -> None:
        self.events = events
        super().__init__("Fatal MI-1 data-quality validation failure")


def _fatal(
    run_id: str,
    event_type: str,
    message: str,
    bar: MarketEodBar | None = None,
) -> DataQualityEvent:
    return DataQualityEvent(
        run_id=run_id,
        severity="fatal",
        event_type=event_type,
        instrument_id=None if bar is None else bar.instrument_id,
        session_date=None if bar is None else bar.session_date,
        message=message,
        source="market_eod_bar_validation",
    )


def validate_market_eod_bars(run_id: str, bars: list[MarketEodBar]) -> list[DataQualityEvent]:
    events: list[DataQualityEvent] = []
    keys = Counter((bar.instrument_id, bar.session_date) for bar in bars)
    for (instrument_id, session_date), count in keys.items():
        if count > 1:
            events.append(
                DataQualityEvent(
                    run_id=run_id,
                    severity="fatal",
                    event_type="duplicate_instrument_session",
                    instrument_id=instrument_id,
                    session_date=session_date,
                    message=f"Found {count} rows for instrument/session",
                    source="market_eod_bar_validation",
                )
            )

    for bar in bars:
        if not bar.instrument_id or not bar.snapshot_id:
            events.append(_fatal(run_id, "missing_required_identifier", "Missing identifier", bar))
        prices = [bar.open_raw, bar.high_raw, bar.low_raw, bar.close_raw]
        if any(not isfinite(price) for price in prices):
            events.append(
                _fatal(
                    run_id,
                    "missing_required_price",
                    "Required raw OHLC price is missing or non-finite "
                    f"(open={bar.open_raw}, high={bar.high_raw}, low={bar.low_raw}, "
                    f"close={bar.close_raw}, volume={bar.volume_raw}, "
                    f"vendor_adjusted_close={bar.vendor_adjusted_close})",
                    bar,
                )
            )
        elif any(price <= 0 for price in prices):
            events.append(
                _fatal(run_id, "non_positive_price", "Raw OHLC prices must be positive", bar)
            )
        if bar.volume_raw < 0:
            events.append(_fatal(run_id, "negative_volume", "Volume must be non-negative", bar))
        if bar.low_raw > min(bar.open_raw, bar.close_raw):
            events.append(
                _fatal(run_id, "invalid_ohlc_low", "low_raw exceeds min(open_raw, close_raw)", bar)
            )
        if bar.high_raw < max(bar.open_raw, bar.close_raw):
            events.append(
                _fatal(
                    run_id, "invalid_ohlc_high", "high_raw is below max(open_raw, close_raw)", bar
                )
            )
        timestamp_fields: list[datetime] = [bar.available_at_utc, bar.retrieved_at_utc]
        if any(
            timestamp.tzinfo is None or timestamp.utcoffset() is None
            for timestamp in timestamp_fields
        ):
            events.append(
                _fatal(run_id, "invalid_timestamp", "Timestamps must be timezone-aware", bar)
            )
        if bar.availability_evidence_level not in SUPPORTED_EVIDENCE_LEVELS:
            events.append(
                _fatal(
                    run_id,
                    "unsupported_evidence_level",
                    f"Unsupported evidence level: {bar.availability_evidence_level}",
                    bar,
                )
            )

    fatal_events = [event for event in events if event.severity == "fatal"]
    if fatal_events:
        raise DataQualityError(events)
    return events
