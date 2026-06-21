"""Isolated GMA-4 fixed 22-ETF historical input bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from market_strats.global_multi_asset.data.manifests import sha256_file
from market_strats.global_multi_asset.data.price_provider import ProviderSnapshot, YFinanceProvider
from market_strats.global_multi_asset.data.validation import (
    completed_history,
    corporate_action_frame,
    normalise_price_frame,
)
from market_strats.global_multi_asset.gma1a_market_bundle import build_total_return_series
from market_strats.global_multi_asset.gma4_contract import (
    FIXED_GMA4_UNIVERSE,
    GMA4_CANONICAL_RESEARCH_END_DATE,
)
from market_strats.global_multi_asset.gma4_replay_adapter import validate_gma4_price_inputs

BUNDLE_ID = "gma4_fixed_22_etf_v1"
DATA_BUNDLE_ROOT = Path("data/global_multi_asset_alpha/gma4_fixed_22_etf_v1")
REPORT_BUNDLE_ROOT = Path("reports/global_multi_asset_alpha/gma4_fixed_22_etf_v1")
SOURCE_INVENTORY_PATH = Path(
    "reports/global_multi_asset_alpha/data_foundation/canonical_market_bundle_inventory.csv"
)
GMA3A_TOURNAMENT_CASH_SOURCE_ID = "gma3a_tournament_cash"
GMA3A_TOURNAMENT_CASH_SOURCE_PATH = Path(
    "../Market-strats-lab/data/global_multi_asset_alpha/gma3a_tournament_cash/canonical_cash_accrual.csv"
)
GMA3A_TOURNAMENT_CASH_METHODOLOGY_LABEL = (
    "existing_gma3a_historical_tournament_cash_series_not_new_methodology"
)

MARKET_COLUMNS = [
    "date",
    "instrument_id",
    "open_raw",
    "close_raw",
    "dividend_cash",
    "split_ratio",
    "is_completed_observation",
    "calendar_id",
    "total_return_index",
]
REQUIRED_NUMERIC_COLUMNS = ["open_raw", "close_raw", "total_return_index"]
INVENTORY_COLUMNS = [
    "instrument_id",
    "canonical_file_path",
    "first_available_date",
    "last_available_date",
    "session_count",
    "raw_hash",
    "normalised_hash",
    "source_manifest_hash",
    "bundle_id",
]


class GMA4DataBundleError(RuntimeError):
    """Fail-closed GMA-4 data-bundle error."""


class SnapshotFetcher(Protocol):
    def fetch(self, provider_symbol: str, *, start: str, end: str) -> ProviderSnapshot: ...


@dataclass(frozen=True)
class GMA4DataBundleResult:
    status: str
    bundle_root: Path
    report_root: Path
    inventory: pd.DataFrame
    common_start: date | None
    common_end: date | None
    blockers: list[str]
    cash_metadata: dict[str, Any]


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _resolve_path(raw: Any) -> Path:
    path = Path(str(raw))
    return path if path.is_absolute() else Path.cwd() / path


def _safe_symbol(symbol: str) -> str:
    return symbol.replace("-", "_").upper()


def _source_inventory(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise GMA4DataBundleError(f"source inventory missing: {path}")
    inventory = pd.read_csv(path)
    if "instrument_id" not in inventory:
        raise GMA4DataBundleError("source inventory missing instrument_id")
    duplicated = sorted(
        inventory.loc[inventory["instrument_id"].duplicated(), "instrument_id"].astype(str).unique()
    )
    if duplicated:
        raise GMA4DataBundleError(f"duplicate source inventory rows: {duplicated}")
    return inventory


def _validate_market_frame(
    frame: pd.DataFrame,
    symbol: str,
    endpoint: date,
    *,
    allow_post_endpoint_completed: bool = False,
) -> pd.DataFrame:
    missing = sorted(set(MARKET_COLUMNS) - set(frame.columns))
    if missing:
        raise GMA4DataBundleError(f"{symbol} missing bundle market columns: {missing}")
    result = frame[MARKET_COLUMNS].copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.date
    if result["date"].isna().any():
        raise GMA4DataBundleError(f"{symbol} has invalid dates")
    if result["date"].duplicated().any():
        raise GMA4DataBundleError(f"{symbol} has duplicate dates")
    if result[MARKET_COLUMNS].isna().any().any():
        raise GMA4DataBundleError(f"{symbol} has null required bundle fields")
    for column in REQUIRED_NUMERIC_COLUMNS:
        values = pd.to_numeric(result[column], errors="coerce")
        if values.isna().any() or values.le(0).any():
            raise GMA4DataBundleError(f"{symbol} has invalid {column}")
        result[column] = values
    completed = result["is_completed_observation"].astype(bool)
    if (
        result.loc[completed & (result["date"] > endpoint)].shape[0]
        and not allow_post_endpoint_completed
    ):
        raise GMA4DataBundleError(f"{symbol} has completed observations after {endpoint}")
    result = result.loc[result["date"] <= endpoint].sort_values("date").reset_index(drop=True)
    if endpoint not in set(result["date"]):
        raise GMA4DataBundleError(f"{symbol} missing endpoint date {endpoint}")
    if set(result["instrument_id"].astype(str)) != {symbol}:
        raise GMA4DataBundleError(f"{symbol} file contains another instrument_id")
    return result


def _bundle_frame_from_canonical(source_path: Path, symbol: str, endpoint: date) -> pd.DataFrame:
    if not source_path.exists():
        raise GMA4DataBundleError(f"source canonical file missing for {symbol}: {source_path}")
    source = pd.read_csv(source_path)
    return _validate_market_frame(source, symbol, endpoint, allow_post_endpoint_completed=True)


def _bundle_frame_from_snapshot(
    snapshot: ProviderSnapshot, symbol: str, endpoint: date
) -> pd.DataFrame:
    normalised = normalise_price_frame(snapshot.raw_frame)
    completed = completed_history(normalised, snapshot.retrieved_at_utc)
    actions = corporate_action_frame(snapshot.raw_frame)
    total_return = build_total_return_series(completed, actions)
    frame = pd.DataFrame(
        {
            "date": total_return["date"],
            "instrument_id": symbol,
            "open_raw": total_return["open"],
            "close_raw": total_return["close"],
            "dividend_cash": total_return["dividend_cash"],
            "split_ratio": total_return["split_ratio"],
            "is_completed_observation": True,
            "calendar_id": "us_listed_etf",
            "total_return_index": total_return["total_return_index"],
        }
    )
    return _validate_market_frame(frame, symbol, endpoint)


def _write_market_file(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _copy_cash_for_common_history(
    *,
    source_cash_path: Path,
    output_cash_path: Path,
    common_dates: list[date],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not source_cash_path.exists():
        raise GMA4DataBundleError(f"GMA-3A tournament cash source missing: {source_cash_path}")
    cash = pd.read_csv(source_cash_path, dtype={"period_return": "string"})
    required = {"accrual_start", "accrual_end", "period_return"}
    missing = sorted(required - set(cash.columns))
    if missing:
        raise GMA4DataBundleError(f"GMA-3A tournament cash source missing fields: {missing}")
    cash["accrual_start"] = pd.to_datetime(cash["accrual_start"], errors="coerce").dt.date
    cash["accrual_end"] = pd.to_datetime(cash["accrual_end"], errors="coerce").dt.date
    if cash[["accrual_start", "accrual_end"]].isna().any().any():
        raise GMA4DataBundleError("GMA-3A tournament cash source has invalid accrual dates")
    if cash.duplicated(["accrual_start", "accrual_end"]).any():
        raise GMA4DataBundleError("GMA-3A tournament cash source has duplicate accrual intervals")
    period_return = pd.to_numeric(cash["period_return"], errors="coerce")
    if period_return.isna().any():
        raise GMA4DataBundleError("GMA-3A tournament cash source has non-numeric period_return")

    required_pairs = [
        (common_dates[idx - 1], common_dates[idx]) for idx in range(1, len(common_dates))
    ]
    by_pair = cash.set_index(["accrual_start", "accrual_end"], drop=False)
    missing_pairs = [pair for pair in required_pairs if pair not in by_pair.index]
    if missing_pairs:
        raise GMA4DataBundleError(
            f"missing cash accrual for {len(missing_pairs)} common-session intervals"
        )
    copied = by_pair.loc[required_pairs].reset_index(drop=True).copy()
    copied = copied.drop_duplicates(["accrual_start", "accrual_end"], keep="first")
    output_cash_path.parent.mkdir(parents=True, exist_ok=True)
    copied.to_csv(output_cash_path, index=False)
    metadata = {
        "cash_source_id": GMA3A_TOURNAMENT_CASH_SOURCE_ID,
        "cash_source_path": str(source_cash_path),
        "cash_source_hash": sha256_file(source_cash_path),
        "copied_cash_path": str(output_cash_path),
        "copied_cash_hash": sha256_file(output_cash_path),
        "source_row_count": int(len(cash)),
        "copied_row_count": int(len(copied)),
        "first_accrual_start": str(copied["accrual_start"].min()) if not copied.empty else "",
        "last_accrual_end": str(copied["accrual_end"].max()) if not copied.empty else "",
        "methodology_label": GMA3A_TOURNAMENT_CASH_METHODOLOGY_LABEL,
        "derived_from_existing_gma_historical_tournament_cash_series": True,
        "new_cash_methodology_invented": False,
    }
    return copied, metadata


def validate_gma4_bundle_outputs(
    *,
    inventory_path: Path = REPORT_BUNDLE_ROOT / "gma4_market_bundle_inventory.csv",
    cash_path: Path = DATA_BUNDLE_ROOT / "cash" / "canonical_cash_accrual.csv",
    endpoint: date = GMA4_CANONICAL_RESEARCH_END_DATE,
) -> tuple[pd.DataFrame, list[date]]:
    if not inventory_path.exists():
        raise GMA4DataBundleError(f"GMA-4 inventory missing: {inventory_path}")
    inventory = pd.read_csv(inventory_path)
    missing_cols = sorted(set(INVENTORY_COLUMNS) - set(inventory.columns))
    if missing_cols:
        raise GMA4DataBundleError(f"GMA-4 inventory missing fields: {missing_cols}")
    if inventory["instrument_id"].duplicated().any():
        duplicated = sorted(
            inventory.loc[inventory["instrument_id"].duplicated(), "instrument_id"]
            .astype(str)
            .unique()
        )
        raise GMA4DataBundleError(f"duplicate GMA-4 inventory records: {duplicated}")
    if list(inventory["instrument_id"].astype(str)) != FIXED_GMA4_UNIVERSE:
        raise GMA4DataBundleError("GMA-4 inventory must contain exactly the fixed 22 ETFs in order")

    common: set[date] | None = None
    for row in inventory.to_dict("records"):
        symbol = str(row["instrument_id"])
        path = _resolve_path(row["canonical_file_path"])
        frame = _validate_market_frame(pd.read_csv(path), symbol, endpoint)
        dates = set(frame["date"])
        common = dates if common is None else common & dates
    common_dates = sorted(common or [])
    if endpoint not in common_dates:
        raise GMA4DataBundleError("incomplete 22-ETF common universe at endpoint")
    if len(common_dates) < 2:
        raise GMA4DataBundleError("insufficient common GMA-4 sessions")

    cash = pd.read_csv(cash_path)
    cash["accrual_start"] = pd.to_datetime(cash["accrual_start"], errors="coerce").dt.date
    cash["accrual_end"] = pd.to_datetime(cash["accrual_end"], errors="coerce").dt.date
    if cash.duplicated(["accrual_start", "accrual_end"]).any():
        raise GMA4DataBundleError("GMA-4 cash copy has duplicate accrual intervals")
    period_return = pd.to_numeric(cash["period_return"], errors="coerce")
    if period_return.isna().any():
        raise GMA4DataBundleError("GMA-4 cash copy has non-numeric period_return")
    observed = set(zip(cash["accrual_start"], cash["accrual_end"]))
    missing_cash = [
        (common_dates[idx - 1], common_dates[idx])
        for idx in range(1, len(common_dates))
        if (common_dates[idx - 1], common_dates[idx]) not in observed
    ]
    if missing_cash:
        raise GMA4DataBundleError(
            f"missing cash accrual for {len(missing_cash)} common-session intervals"
        )
    return inventory, common_dates


def load_gma4_bundle_prices_cash(
    *,
    inventory_path: Path = REPORT_BUNDLE_ROOT / "gma4_market_bundle_inventory.csv",
    cash_path: Path = DATA_BUNDLE_ROOT / "cash" / "canonical_cash_accrual.csv",
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    inventory, _common_dates = validate_gma4_bundle_outputs(
        inventory_path=inventory_path, cash_path=cash_path
    )
    prices: dict[str, pd.DataFrame] = {}
    for row in inventory.to_dict("records"):
        symbol = str(row["instrument_id"])
        frame = pd.read_csv(_resolve_path(row["canonical_file_path"]))
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        prices[symbol] = frame.set_index("date").sort_index()
    cash = pd.read_csv(cash_path)
    cash["accrual_start"] = pd.to_datetime(cash["accrual_start"]).dt.date
    cash["accrual_end"] = pd.to_datetime(cash["accrual_end"]).dt.date
    validate_gma4_price_inputs(prices)
    return prices, cash, inventory


def build_gma4_data_bundle(
    *,
    source_inventory_path: Path = SOURCE_INVENTORY_PATH,
    source_cash_path: Path | None = None,
    bundle_root: Path = DATA_BUNDLE_ROOT,
    report_root: Path = REPORT_BUNDLE_ROOT,
    endpoint: date = GMA4_CANONICAL_RESEARCH_END_DATE,
    fetch_missing: bool = True,
    fetcher: SnapshotFetcher | None = None,
) -> GMA4DataBundleResult:
    source_inventory = _source_inventory(source_inventory_path)
    if source_cash_path is None:
        source_cash_path = GMA3A_TOURNAMENT_CASH_SOURCE_PATH
    market_root = bundle_root / "market"
    cash_path = bundle_root / "cash" / "canonical_cash_accrual.csv"
    report_root.mkdir(parents=True, exist_ok=True)
    market_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    source_rows = {str(row["instrument_id"]): row for row in source_inventory.to_dict("records")}
    if fetcher is None and fetch_missing:
        fetcher = YFinanceProvider(
            cache_root=bundle_root / "yfinance_cache",
            raw_root=bundle_root / "raw",
            processed_root=bundle_root / "normalised_source",
            manifest_root=bundle_root / "manifests",
            timeout_seconds=30,
        )

    for symbol in FIXED_GMA4_UNIVERSE:
        try:
            source_row = source_rows.get(symbol)
            if source_row is not None:
                source_path = _resolve_path(source_row["canonical_file_path"])
                frame = _bundle_frame_from_canonical(source_path, symbol, endpoint)
                raw_hash = str(
                    source_row.get("source_raw_sha256")
                    or source_row.get("raw_hash")
                    or source_row.get("canonical_file_sha256")
                    or sha256_file(source_path)
                )
                normalised_hash = str(
                    source_row.get("source_normalised_sha256")
                    or source_row.get("normalised_hash")
                    or source_row.get("canonical_file_sha256")
                    or sha256_file(source_path)
                )
                source_manifest_hash = str(
                    source_row.get("selected_manifest_sha256")
                    or source_row.get("source_manifest_hash")
                    or source_row.get("source_manifest_sha256")
                    or ""
                )
                source_identifier = str(source_path)
            elif fetch_missing and fetcher is not None:
                request_end = (pd.Timestamp(endpoint) + pd.Timedelta(days=1)).date().isoformat()
                snapshot = fetcher.fetch(symbol, start="1990-01-01", end=request_end)
                frame = _bundle_frame_from_snapshot(snapshot, symbol, endpoint)
                raw_hash = sha256_file(snapshot.raw_file_path)
                normalised_hash = sha256_file(snapshot.normalised_file_path)
                source_manifest_hash = sha256_file(snapshot.manifest_path)
                source_identifier = str(snapshot.manifest_path)
            else:
                raise GMA4DataBundleError(f"missing source data for {symbol}")

            out_path = market_root / f"{symbol}.csv"
            _write_market_file(frame, out_path)
            rows.append(
                {
                    "instrument_id": symbol,
                    "canonical_file_path": str(out_path),
                    "first_available_date": str(frame["date"].min()),
                    "last_available_date": str(frame["date"].max()),
                    "session_count": int(len(frame)),
                    "raw_hash": raw_hash,
                    "normalised_hash": normalised_hash,
                    "source_manifest_hash": source_manifest_hash,
                    "bundle_id": BUNDLE_ID,
                    "bundle_file_sha256": sha256_file(out_path),
                    "source_identifier": source_identifier,
                    "data_status": "ready",
                }
            )
        except Exception as exc:
            blockers.append(f"{symbol}: {exc}")

    inventory = pd.DataFrame(rows)
    inventory_path = report_root / "gma4_market_bundle_inventory.csv"
    inventory.to_csv(inventory_path, index=False)
    common_start: date | None = None
    common_end: date | None = None
    status = "ready"
    cash_metadata: dict[str, Any] = {}
    try:
        _, common_dates = validate_gma4_bundle_outputs(
            inventory_path=inventory_path, cash_path=cash_path, endpoint=endpoint
        )
    except Exception:
        if not blockers and len(rows) == len(FIXED_GMA4_UNIVERSE):
            # Cash has not been copied yet; compute common dates from market files first.
            common_sets = []
            for row in rows:
                frame = pd.read_csv(_resolve_path(row["canonical_file_path"]))
                common_sets.append(set(pd.to_datetime(frame["date"]).dt.date))
            common_dates = sorted(set.intersection(*common_sets)) if common_sets else []
        else:
            common_dates = []
    if common_dates:
        common_start = common_dates[0]
        common_end = common_dates[-1]
        try:
            _copied_cash, cash_metadata = _copy_cash_for_common_history(
                source_cash_path=source_cash_path,
                output_cash_path=cash_path,
                common_dates=common_dates,
            )
            validate_gma4_bundle_outputs(
                inventory_path=inventory_path, cash_path=cash_path, endpoint=endpoint
            )
        except Exception as exc:
            blockers.append(str(exc))

    if blockers:
        status = "blocked_data_quality"

    manifest = {
        "bundle_id": BUNDLE_ID,
        "git_commit": _git_commit(),
        "endpoint_date": endpoint.isoformat(),
        "fixed_universe_hash": _sha256_text(_stable_json(FIXED_GMA4_UNIVERSE)),
        "source_inventory_path": str(source_inventory_path),
        "source_cash_path": str(source_cash_path),
        "cash_source": cash_metadata,
        "instruments": inventory.to_dict("records"),
        "data_status": status,
        "historical_research_only": True,
        "not_active_gma_canonical_bundle": True,
        "common_history_start": str(common_start or ""),
        "common_history_end": str(common_end or ""),
        "blockers": blockers,
    }
    (report_root / "gma4_data_bundle_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    lines = [
        "# GMA-4 Fixed 22 ETF Data Bundle",
        "",
        f"Bundle ID: `{BUNDLE_ID}`",
        f"Status: `{status}`",
        f"Endpoint date: `{endpoint.isoformat()}`",
        "Historical research only: `true`",
        "Not active GMA canonical bundle: `true`",
        f"Common history: `{common_start or ''}` through `{common_end or ''}`",
        f"Cash source ID: `{cash_metadata.get('cash_source_id', GMA3A_TOURNAMENT_CASH_SOURCE_ID)}`",
        f"Cash methodology: `{cash_metadata.get('methodology_label', GMA3A_TOURNAMENT_CASH_METHODOLOGY_LABEL)}`",
        "",
        "## Blockers",
        "",
        *(f"- {blocker}" for blocker in blockers),
    ]
    if not blockers:
        lines.append("- none")
    lines.extend(["", "## Instruments", ""])
    for row in inventory.to_dict("records"):
        lines.append(
            f"- {row['instrument_id']}: {row['first_available_date']} through {row['last_available_date']} ({row['session_count']} sessions)"
        )
    (report_root / "gma4_data_bundle_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return GMA4DataBundleResult(
        status,
        bundle_root,
        report_root,
        inventory,
        common_start,
        common_end,
        blockers,
        cash_metadata,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m market_strats.global_multi_asset.gma4_data_bundle"
    )
    parser.add_argument("--source-inventory", type=Path, default=SOURCE_INVENTORY_PATH)
    parser.add_argument("--source-cash", type=Path, default=None)
    parser.add_argument("--bundle-root", type=Path, default=DATA_BUNDLE_ROOT)
    parser.add_argument("--report-root", type=Path, default=REPORT_BUNDLE_ROOT)
    parser.add_argument("--no-fetch-missing", action="store_true")
    args = parser.parse_args(argv)
    result = build_gma4_data_bundle(
        source_inventory_path=args.source_inventory,
        source_cash_path=args.source_cash,
        bundle_root=args.bundle_root,
        report_root=args.report_root,
        fetch_missing=not args.no_fetch_missing,
    )
    print(f"status: {result.status}")
    print(f"bundle_root: {result.bundle_root}")
    print(f"report_root: {result.report_root}")
    print(f"common_history: {result.common_start} through {result.common_end}")
    if result.blockers:
        print("blockers:")
        for blocker in result.blockers:
            print(f"  {blocker}")
    return 0 if result.status == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
