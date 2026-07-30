"""Stable security identity and effective-dated ticker resolution."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from market_strats.universe.contracts import (
    IdentityResolutionError,
    SecurityIdentity,
    TickerIdentityInterval,
)
from market_strats.universe.hashing import sha256_json


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def build_security_id(
    *,
    namespace: str,
    stable_identifier: str,
    share_class: str | None = None,
) -> str:
    if not namespace.strip() or not stable_identifier.strip():
        raise IdentityResolutionError(
            "Security identity requires a namespace and stable identifier"
        )
    digest = sha256_json(
        {
            "namespace": namespace.strip().lower(),
            "stable_identifier": stable_identifier.strip().lower(),
            "share_class": (share_class or "").strip().lower(),
        }
    )
    return f"sec_{digest[:24]}"


def provisional_seed_security_id(ticker: str, first_observed: date) -> str:
    return build_security_id(
        namespace="hanshof_sp500_seed_unresolved",
        stable_identifier=f"{normalize_ticker(ticker)}|{first_observed.isoformat()}",
    )


class IdentityMap:
    """Resolve tickers only through explicitly registered effective-dated intervals."""

    def __init__(self) -> None:
        self.identities: dict[str, SecurityIdentity] = {}
        self._ticker_intervals: dict[str, list[TickerIdentityInterval]] = defaultdict(list)

    @property
    def ticker_intervals(self) -> list[TickerIdentityInterval]:
        return sorted(
            (item for rows in self._ticker_intervals.values() for item in rows),
            key=lambda row: (row.ticker, row.valid_from, row.security_id),
        )

    def add_identity(self, identity: SecurityIdentity) -> None:
        existing = self.identities.get(identity.security_id)
        if existing is not None and existing != identity:
            raise IdentityResolutionError(f"Conflicting security identity: {identity.security_id}")
        self.identities[identity.security_id] = identity

    def add_ticker_interval(self, interval: TickerIdentityInterval) -> None:
        if interval.security_id not in self.identities:
            raise IdentityResolutionError("Ticker interval references an unknown security_id")
        if interval.valid_through is not None and interval.valid_through < interval.valid_from:
            raise IdentityResolutionError("Ticker interval ends before it starts")
        ticker = normalize_ticker(interval.ticker)
        normalized = TickerIdentityInterval(
            security_id=interval.security_id,
            ticker=ticker,
            exchange=interval.exchange,
            valid_from=interval.valid_from,
            valid_through=interval.valid_through,
            source_id=interval.source_id,
        )
        for existing in self._ticker_intervals[ticker]:
            overlap = (
                existing.valid_through is None or existing.valid_through >= normalized.valid_from
            ) and (
                normalized.valid_through is None or normalized.valid_through >= existing.valid_from
            )
            if overlap and existing.security_id != normalized.security_id:
                raise IdentityResolutionError(
                    f"Ticker reuse intervals overlap for ticker {ticker}; identity is ambiguous"
                )
        self._ticker_intervals[ticker].append(normalized)

    def resolve(self, ticker: str, on_date: date) -> str:
        normalized = normalize_ticker(ticker)
        matches = [
            row
            for row in self._ticker_intervals.get(normalized, [])
            if row.valid_from <= on_date
            and (row.valid_through is None or on_date <= row.valid_through)
        ]
        if len(matches) != 1:
            raise IdentityResolutionError(
                f"Ticker {normalized} has {len(matches)} identity matches on {on_date}"
            )
        return matches[0].security_id
