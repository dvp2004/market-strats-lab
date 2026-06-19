"""GMA-3A post-endpoint market-data refresh for operational paper packets."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.global_multi_asset.data.manifests import sha256_file
from market_strats.global_multi_asset.data.price_provider import YFinanceProvider, safe_symbol
from market_strats.global_multi_asset.data.validation import (
    corporate_action_frame,
    PRICE_COLUMNS,
)
from market_strats.global_multi_asset.gma2_replay import _load_prices
from market_strats.global_multi_asset.gma3a_config import GMA3AConfig
from market_strats.global_multi_asset.gma3a_tournament import _load_gma2_for_gma3a


POST_ENDPOINT_START = "2026-05-02"
POST_ENDPOINT_CANONICAL_COLUMNS = [
    "date",
    "instrument_id",
    "open_raw",
    "high_raw",
    "low_raw",
    "close_raw",
    "adj_close_provider",
    "volume",
    "dividend_cash",
    "split_ratio",
    "is_completed_observation",
    "calendar_id",
    "source_manifest_path",
    "source_manifest_sha256",
    "source_raw_sha256",
    "source_normalised_sha256",
    "total_return_factor",
    "total_return_index",
    "total_return_construction_status",
]


@dataclass(frozen=True)
class GMA3APostEndpointRefreshResult:
    decision: str
    output_root: Path
    data_root: Path
    refreshed_symbols: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class _ProcessedSnapshotForMaterialization:
    completed: pd.DataFrame
    raw: pd.DataFrame
    manifest_path: Path
    normalised_path: Path
    raw_path: Path
    latest_completed_date: Any
    completed_row_count: int


def _target_symbols(config: GMA3AConfig) -> list[str]:
    weights = config.raw.get("strategy_universe", {}).get("balanced_benchmark_weights", {}) or {}
    symbols = [str(symbol) for symbol in weights if str(symbol) != "CASH"]
    return sorted(set(symbols))


def _next_provider_end_date() -> str:
    # yfinance end date is exclusive. Request through tomorrow so the provider can
    # return today's row if available; completed_history will exclude active bars.
    return (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()


def _merge_actions(normalised: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    completed = normalised.copy()
    actions = corporate_action_frame(raw)
    if actions.empty:
        completed["dividend_cash"] = 0.0
        completed["split_ratio"] = 0.0
        return completed
    actions = actions.copy()
    actions["date"] = pd.to_datetime(actions["date"], errors="coerce")
    actions = actions.groupby("date", as_index=False).agg(
        {
            "dividends": "sum",
            "splits": lambda x: x.loc[x.fillna(0.0).ne(0.0)].iloc[0]
            if x.fillna(0.0).ne(0.0).any()
            else 0.0,
        }
    )
    completed = completed.merge(actions, on="date", how="left")
    completed["dividend_cash"] = pd.to_numeric(completed["dividends"], errors="coerce").fillna(0.0)
    completed["split_ratio"] = pd.to_numeric(completed["splits"], errors="coerce").fillna(0.0)
    return completed


def _post_endpoint_completed_history(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    working = frame.copy().sort_values("date").reset_index(drop=True)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    required_complete = working[PRICE_COLUMNS].isna().any(axis=1)
    while len(working) and bool(required_complete.iloc[-1]):
        working = working.iloc[:-1].copy()
        required_complete = required_complete.iloc[:-1].copy()
    if bool(required_complete.any()):
        raise ValueError("processed provider snapshot contains incomplete interior rows")
    return working.reset_index(drop=True)


def _resolve_snapshot_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute() or path.exists():
        return path
    return Path.cwd() / path


def _processed_snapshot_from_manifest(manifest_path: Path) -> _ProcessedSnapshotForMaterialization | None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    normalised_path = _resolve_snapshot_path(manifest.get("normalised_file_path", ""))
    raw_path = _resolve_snapshot_path(manifest.get("raw_file_path", ""))
    if not normalised_path.exists() or not raw_path.exists():
        return None
    normalised = pd.read_csv(normalised_path)
    completed = _post_endpoint_completed_history(normalised)
    if completed.empty:
        return None
    raw = pd.read_csv(raw_path)
    latest = pd.to_datetime(completed["date"], errors="coerce").max()
    if pd.isna(latest):
        return None
    return _ProcessedSnapshotForMaterialization(
        completed=completed,
        raw=raw,
        manifest_path=manifest_path,
        normalised_path=normalised_path,
        raw_path=raw_path,
        latest_completed_date=latest.date(),
        completed_row_count=int(len(completed)),
    )


def _best_processed_snapshot_for_materialization(
    *,
    symbol: str,
    provider: str,
    manifest_root: Path,
) -> _ProcessedSnapshotForMaterialization | None:
    manifest_dir = manifest_root / provider / safe_symbol(symbol)
    if not manifest_dir.exists():
        return None
    candidates: list[_ProcessedSnapshotForMaterialization] = []
    for manifest_path in sorted(manifest_dir.glob("*_manifest.json")):
        try:
            candidate = _processed_snapshot_from_manifest(manifest_path)
        except Exception:  # noqa: BLE001
            candidate = None
        if candidate is not None:
            candidates.append(candidate)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            pd.Timestamp(item.latest_completed_date),
            item.completed_row_count,
            item.manifest_path.stat().st_mtime,
        ),
    )[-1]


def _build_post_endpoint_rows(
    *,
    symbol: str,
    canonical: pd.DataFrame,
    completed: pd.DataFrame,
    raw: pd.DataFrame,
    manifest_path: Path,
    normalised_path: Path,
    raw_path: Path,
) -> pd.DataFrame:
    start_date = pd.Timestamp(POST_ENDPOINT_START).date()
    rows = _merge_actions(completed, raw)
    rows["date"] = pd.to_datetime(rows["date"], errors="coerce")
    rows = rows.loc[rows["date"].dt.date >= start_date].sort_values("date").reset_index(drop=True)
    if rows.empty:
        return pd.DataFrame(columns=POST_ENDPOINT_CANONICAL_COLUMNS)

    canonical_sorted = canonical.copy().sort_index()
    anchor_candidates = canonical_sorted.loc[canonical_sorted.index < rows["date"].dt.date.iloc[0]]
    if anchor_candidates.empty:
        raise ValueError(f"{symbol} missing canonical anchor before post-endpoint start")
    anchor = anchor_candidates.iloc[-1]
    prev_close = float(anchor["close_raw"])
    prev_index = float(anchor["total_return_index"])
    if not math.isfinite(prev_close) or prev_close <= 0 or not math.isfinite(prev_index) or prev_index <= 0:
        raise ValueError(f"{symbol} invalid canonical anchor for total-return continuation")

    manifest_hash = sha256_file(manifest_path)
    raw_hash = sha256_file(raw_path)
    normalised_hash = sha256_file(normalised_path)
    output_rows: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        close = float(row["close"])
        dividend = float(row.get("dividend_cash", 0.0))
        factor = (close + dividend) / prev_close
        current_index = prev_index * factor
        output_rows.append(
            {
                "date": pd.Timestamp(row["date"]).date().isoformat(),
                "instrument_id": symbol,
                "open_raw": float(row["open"]),
                "high_raw": float(row["high"]),
                "low_raw": float(row["low"]),
                "close_raw": close,
                "adj_close_provider": float(row["adj_close"]),
                "volume": float(row["volume"]),
                "dividend_cash": dividend,
                "split_ratio": float(row.get("split_ratio", 0.0)),
                "is_completed_observation": True,
                "calendar_id": "us_listed_etf",
                "source_manifest_path": str(manifest_path),
                "source_manifest_sha256": manifest_hash,
                "source_raw_sha256": raw_hash,
                "source_normalised_sha256": normalised_hash,
                "total_return_factor": factor,
                "total_return_index": current_index,
                "total_return_construction_status": "constructed",
            }
        )
        prev_close = close
        prev_index = current_index
    return pd.DataFrame(output_rows, columns=POST_ENDPOINT_CANONICAL_COLUMNS)


def run_gma3a_post_endpoint_refresh(config: GMA3AConfig) -> GMA3APostEndpointRefreshResult:
    out = config.paths["output_root"]
    data_root = config.paths["data_root"]
    out.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)

    raw_root = data_root / "post_endpoint_provider_snapshots" / "raw"
    processed_root = data_root / "post_endpoint_provider_snapshots" / "processed"
    manifest_root = data_root / "post_endpoint_provider_snapshots" / "manifests"
    post_market_root = data_root / "post_endpoint_market"
    post_market_root.mkdir(parents=True, exist_ok=True)

    provider = YFinanceProvider(
        cache_root=data_root / "post_endpoint_provider_snapshots" / "cache",
        raw_root=raw_root,
        processed_root=processed_root,
        manifest_root=manifest_root,
        timeout_seconds=30,
    )
    gma2 = _load_gma2_for_gma3a(config)
    symbols = _target_symbols(config)
    canonical = _load_prices(gma2, set(symbols))
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    refreshed: list[str] = []
    request_end = _next_provider_end_date()

    for symbol in symbols:
        status = "blocked"
        blocking_reason = ""
        latest_completed_date = ""
        row_count = 0
        try:
            snapshot = provider.fetch(symbol, start=POST_ENDPOINT_START, end=request_end)
            materialized = _best_processed_snapshot_for_materialization(
                symbol=symbol,
                provider=snapshot.provider,
                manifest_root=manifest_root,
            )
            completed = materialized.completed if materialized is not None else _post_endpoint_completed_history(snapshot.normalised_frame)
            raw = materialized.raw if materialized is not None else snapshot.raw_frame
            manifest_path = materialized.manifest_path if materialized is not None else snapshot.manifest_path
            normalised_path = materialized.normalised_path if materialized is not None else snapshot.normalised_file_path
            raw_path = materialized.raw_path if materialized is not None else snapshot.raw_file_path
            post_rows = _build_post_endpoint_rows(
                symbol=symbol,
                canonical=canonical[symbol],
                completed=completed,
                raw=raw,
                manifest_path=manifest_path,
                normalised_path=normalised_path,
                raw_path=raw_path,
            )
            if post_rows.empty:
                raise ValueError("provider returned no completed post-endpoint rows")
            post_rows.to_csv(post_market_root / f"{symbol}_post_endpoint.csv", index=False)
            status = "refreshed"
            latest_completed_date = str(post_rows["date"].iloc[-1])
            row_count = int(len(post_rows))
            refreshed.append(symbol)
        except Exception as exc:  # noqa: BLE001
            blocking_reason = str(exc)
            warnings.append(f"{symbol}: {blocking_reason}")
        rows.append(
            {
                "symbol": symbol,
                "refresh_status": status,
                "request_start": POST_ENDPOINT_START,
                "request_end_exclusive": request_end,
                "latest_completed_date": latest_completed_date,
                "completed_row_count": row_count,
                "output_file": str(post_market_root / f"{symbol}_post_endpoint.csv") if status == "refreshed" else "",
                "blocking_reason": blocking_reason,
            }
        )

    report = pd.DataFrame(rows)
    report.to_csv(out / "gma3a_post_endpoint_refresh_status.csv", index=False)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "post_endpoint_start": POST_ENDPOINT_START,
        "request_end_exclusive": request_end,
        "symbols": symbols,
        "refreshed_symbols": refreshed,
        "post_endpoint_market_root": str(post_market_root),
        "status_rows": rows,
    }
    (out / "gma3a_post_endpoint_refresh_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    decision = (
        "gma3a_post_endpoint_refresh_completed"
        if len(refreshed) == len(symbols)
        else "gma3a_post_endpoint_refresh_failed_closed"
    )
    return GMA3APostEndpointRefreshResult(
        decision=decision,
        output_root=out,
        data_root=data_root,
        refreshed_symbols=refreshed,
        warnings=warnings,
    )
