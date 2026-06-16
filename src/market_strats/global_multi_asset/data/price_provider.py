from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.global_multi_asset.data.manifests import sha256_file, write_manifest
from market_strats.global_multi_asset.data.validation import normalise_price_frame
from market_strats.global_multi_asset.identifiers import PHASE_ID, TRACK_ID


@dataclass(frozen=True)
class ProviderSnapshot:
    provider: str
    provider_symbol: str
    request_start: str
    request_end: str
    retrieved_at_utc: str
    raw_frame: pd.DataFrame
    normalised_frame: pd.DataFrame
    raw_file_path: Path
    normalised_file_path: Path
    manifest_path: Path
    warnings: list[str]


def safe_symbol(symbol: str) -> str:
    return symbol.replace("^", "").replace("/", "_").replace("-", "_").upper()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _write_snapshot_files(
    *,
    raw_frame: pd.DataFrame,
    provider: str,
    provider_symbol: str,
    request_start: str,
    request_end: str,
    retrieved_at_utc: str,
    raw_root: Path,
    processed_root: Path,
    manifest_root: Path,
    auto_adjust: bool,
    library_name: str,
    library_version: str,
    warnings: list[str],
) -> ProviderSnapshot:
    stamp = _timestamp()
    symbol = safe_symbol(provider_symbol)
    raw_dir = raw_root / provider / symbol
    processed_dir = processed_root / provider / symbol
    manifest_dir = manifest_root / provider / symbol
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{symbol}_{stamp}.csv"
    normalised_path = processed_dir / f"{symbol}_{stamp}_normalised.csv"
    manifest_path = manifest_dir / f"{symbol}_{stamp}_manifest.json"
    if raw_path.exists() or normalised_path.exists() or manifest_path.exists():
        raise FileExistsError(f"Immutable snapshot path collision for {provider_symbol}")

    raw_frame.to_csv(raw_path, index=False)
    normalised = normalise_price_frame(raw_frame)
    normalised.to_csv(normalised_path, index=False)
    first_observation = normalised["date"].min()
    last_observation = normalised["date"].max()
    manifest: dict[str, Any] = {
        "track_id": TRACK_ID,
        "phase_id": PHASE_ID,
        "provider": provider,
        "provider_symbol": provider_symbol,
        "request_start": request_start,
        "request_end": request_end,
        "retrieved_at_utc": retrieved_at_utc,
        "library_name": library_name,
        "library_version": library_version,
        "auto_adjust": auto_adjust,
        "raw_file_path": str(raw_path),
        "raw_file_sha256": sha256_file(raw_path),
        "normalised_file_path": str(normalised_path),
        "normalised_file_sha256": sha256_file(normalised_path),
        "row_count": int(len(normalised)),
        "first_observation_date": first_observation.date().isoformat() if pd.notna(first_observation) else "",
        "last_observation_date": last_observation.date().isoformat() if pd.notna(last_observation) else "",
        "columns": list(normalised.columns),
        "warnings": warnings,
    }
    write_manifest(manifest, manifest_path)
    return ProviderSnapshot(
        provider=provider,
        provider_symbol=provider_symbol,
        request_start=request_start,
        request_end=request_end,
        retrieved_at_utc=retrieved_at_utc,
        raw_frame=raw_frame,
        normalised_frame=normalised,
        raw_file_path=raw_path,
        normalised_file_path=normalised_path,
        manifest_path=manifest_path,
        warnings=warnings,
    )


class OfflineFixtureProvider:
    def __init__(
        self,
        *,
        fixture_dir: Path,
        raw_root: Path,
        processed_root: Path,
        manifest_root: Path,
    ) -> None:
        self.fixture_dir = fixture_dir
        self.raw_root = raw_root
        self.processed_root = processed_root
        self.manifest_root = manifest_root

    def fetch(self, provider_symbol: str, *, start: str, end: str) -> ProviderSnapshot:
        candidates = [
            self.fixture_dir / f"{provider_symbol}.csv",
            self.fixture_dir / f"{safe_symbol(provider_symbol)}.csv",
        ]
        fixture_path = next((path for path in candidates if path.exists()), None)
        if fixture_path is None:
            raise FileNotFoundError(f"Missing offline fixture for {provider_symbol}")
        raw = pd.read_csv(fixture_path)
        retrieved_at_utc = "2026-06-15T00:00:00+00:00"
        return _write_snapshot_files(
            raw_frame=raw,
            provider="offline_fixture",
            provider_symbol=provider_symbol,
            request_start=start,
            request_end=end,
            retrieved_at_utc=retrieved_at_utc,
            raw_root=self.raw_root,
            processed_root=self.processed_root,
            manifest_root=self.manifest_root,
            auto_adjust=False,
            library_name="pandas_fixture",
            library_version=pd.__version__,
            warnings=[],
        )


class YFinanceProvider:
    def __init__(
        self,
        *,
        cache_root: Path,
        raw_root: Path,
        processed_root: Path,
        manifest_root: Path,
        timeout_seconds: int,
    ) -> None:
        self.cache_root = cache_root
        self.raw_root = raw_root
        self.processed_root = processed_root
        self.manifest_root = manifest_root
        self.timeout_seconds = timeout_seconds

    def fetch(self, provider_symbol: str, *, start: str, end: str) -> ProviderSnapshot:
        import yfinance as yf

        self.cache_root.mkdir(parents=True, exist_ok=True)
        if hasattr(yf, "set_tz_cache_location"):
            yf.set_tz_cache_location(str(self.cache_root))
        raw = yf.download(
            provider_symbol,
            start=start,
            end=end or None,
            auto_adjust=False,
            actions=True,
            progress=False,
            timeout=self.timeout_seconds,
        )
        if raw.empty:
            raise ValueError(f"No data returned for {provider_symbol}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [column[0] for column in raw.columns]
        raw = raw.reset_index()
        return _write_snapshot_files(
            raw_frame=raw,
            provider="yahoo_yfinance",
            provider_symbol=provider_symbol,
            request_start=start,
            request_end=end,
            retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
            raw_root=self.raw_root,
            processed_root=self.processed_root,
            manifest_root=self.manifest_root,
            auto_adjust=False,
            library_name="yfinance",
            library_version=getattr(yf, "__version__", "unknown"),
            warnings=[],
        )
