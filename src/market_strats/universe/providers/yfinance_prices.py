"""Bounded yfinance daily price and corporate-action adapter."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.universe.hashing import sha256_json


@dataclass(frozen=True)
class PriceFetchResult:
    provider_ticker: str
    retrieved_at_utc: str
    request_parameters: dict[str, object]
    snapshot_sha256: str | None
    status: str
    rows: tuple[dict[str, object], ...]
    actions: tuple[dict[str, object], ...]
    package_version: str


def _default_ticker_factory(ticker: str) -> Any:
    import yfinance as yf

    return yf.Ticker(ticker)


def _value(record: dict[str, Any], key: str) -> Any:
    value = record.get(key)
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


class YFinancePriceAdapter:
    def __init__(
        self,
        *,
        raw_root: Path,
        maximum_attempts: int = 2,
        retry_delay_seconds: float = 1,
        ticker_factory: Callable[[str], Any] = _default_ticker_factory,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if maximum_attempts < 1:
            raise ValueError("maximum_attempts must be positive")
        self.raw_root = raw_root
        self.maximum_attempts = maximum_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.ticker_factory = ticker_factory
        self.sleeper = sleeper

    def fetch(
        self,
        *,
        provider_ticker: str,
        start: date,
        end: date,
    ) -> PriceFetchResult:
        request_parameters = {
            "provider_ticker": provider_ticker,
            "interval": "1d",
            "start": start.isoformat(),
            "end_inclusive": end.isoformat(),
            "auto_adjust": False,
            "actions": True,
        }
        request_key = sha256_json(request_parameters)
        cache_path = self.raw_root / f"request_{request_key}.json"
        if cache_path.is_file():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("request_parameters") == request_parameters:
                return PriceFetchResult(
                    provider_ticker=provider_ticker,
                    retrieved_at_utc=str(cached["retrieved_at_utc"]),
                    request_parameters=request_parameters,
                    snapshot_sha256=str(cached["snapshot_sha256"]),
                    status=str(cached["status"]),
                    rows=tuple(cached.get("rows", ())),
                    actions=tuple(cached.get("actions", ())),
                    package_version=str(cached.get("package_version", "unknown")),
                )
        error_status = "temporary_provider_failure"
        history: pd.DataFrame | None = None
        for attempt in range(1, self.maximum_attempts + 1):
            try:
                history = self.ticker_factory(provider_ticker).history(
                    start=start.isoformat(),
                    end=(end + timedelta(days=1)).isoformat(),
                    interval="1d",
                    auto_adjust=False,
                    actions=True,
                )
                if history is None or history.empty:
                    error_status = "possibly_delisted_no_history"
                else:
                    break
            except Exception:
                error_status = "temporary_provider_failure"
            if attempt < self.maximum_attempts:
                self.sleeper(self.retry_delay_seconds)
        retrieved = datetime.now(UTC).isoformat()
        try:
            package_version = version("yfinance")
        except Exception:
            package_version = "unknown"
        if history is None or history.empty:
            return PriceFetchResult(
                provider_ticker=provider_ticker,
                retrieved_at_utc=retrieved,
                request_parameters=request_parameters,
                snapshot_sha256=None,
                status=error_status,
                rows=(),
                actions=(),
                package_version=package_version,
            )

        normalized: list[dict[str, object]] = []
        actions: list[dict[str, object]] = []
        for index, raw in history.reset_index().iterrows():
            del index
            record = raw.to_dict()
            session = record.get("Date") or record.get("Datetime")
            if hasattr(session, "date"):
                session = session.date()
            row = {
                "provider_ticker": provider_ticker,
                "session_date": session,
                "raw_open": _value(record, "Open"),
                "raw_high": _value(record, "High"),
                "raw_low": _value(record, "Low"),
                "raw_close": _value(record, "Close"),
                "adjusted_close": _value(record, "Adj Close"),
                "volume": _value(record, "Volume"),
            }
            normalized.append(row)
            for column, action_type in (("Dividends", "dividend"), ("Stock Splits", "stock_split")):
                action_value = _value(record, column)
                if action_value not in (None, 0, 0.0):
                    actions.append(
                        {
                            "provider_ticker": provider_ticker,
                            "effective_date": session,
                            "action_type": action_type,
                            "value": action_value,
                        }
                    )
        snapshot = {
            "request_parameters": request_parameters,
            "retrieved_at_utc": retrieved,
            "rows": normalized,
            "actions": actions,
        }
        digest = sha256_json(snapshot)
        self.raw_root.mkdir(parents=True, exist_ok=True)
        path = self.raw_root / f"{provider_ticker.replace('.', '_')}_{digest[:16]}.json"
        path.write_text(json.dumps(snapshot, default=str, sort_keys=True), encoding="utf-8")
        cache_payload = {
            **snapshot,
            "snapshot_sha256": digest,
            "status": "available",
            "package_version": package_version,
        }
        cache_path.write_text(
            json.dumps(cache_payload, default=str, sort_keys=True),
            encoding="utf-8",
        )
        return PriceFetchResult(
            provider_ticker=provider_ticker,
            retrieved_at_utc=retrieved,
            request_parameters=request_parameters,
            snapshot_sha256=digest,
            status="available",
            rows=tuple(normalized),
            actions=tuple(actions),
            package_version=package_version,
        )
