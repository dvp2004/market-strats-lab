"""GMA-6B expanded ETF data eligibility and frozen bundle creation."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
import yaml

from market_strats.global_multi_asset.data.manifests import sha256_file, sha256_structured
from market_strats.global_multi_asset.data.price_provider import YFinanceProvider
from market_strats.global_multi_asset.data.validation import corporate_action_frame
from market_strats.global_multi_asset.gma6a_universe_contract import (
    FIXED_GMA6A_ADDITIONS,
    FROZEN_CORE_V1_UNIVERSE,
    load_gma6a_universe_contract,
    validate_gma6a_universe_contract,
)

PHASE_ID = "gma6b_expanded_etf_data_bundle_v1"
CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1.yaml")
UNIVERSE_CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma6a_expanded_etf_universe_v1.yaml")
OUTPUT_ROOT = Path("reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1")
ELIGIBILITY_CSV = Path(
    "reports/global_multi_asset_alpha/gma6b_expanded_etf_data_eligibility_v1.csv"
)
ELIGIBILITY_MD = Path("reports/global_multi_asset_alpha/gma6b_expanded_etf_data_eligibility_v1.md")
REQUESTED_START_DATE = "2007-05-30"
REQUESTED_END_DATE = "2026-05-01"
REQUIRED_TICKERS = [*FROZEN_CORE_V1_UNIVERSE, *FIXED_GMA6A_ADDITIONS]
COMMODITY_POOL_TICKERS = {"USO", "DBA"}
ELIGIBLE = "eligible_for_later_research_execution"
BLOCKED = "blocked_data_contract_failure"
PENDING = "structure_review_pending"
UNIVERSE_ELIGIBLE = "eligible_for_later_gma6_research_execution"
UNIVERSE_BLOCKED = "blocked_data_contract_failure"

AUDIT_FIELDS = [
    "ticker",
    "raw_provider_file_hash",
    "normalised_series_file_hash",
    "first_observed_date",
    "last_observed_date",
    "session_count",
    "missing_session_count",
    "adjusted_price_available",
    "raw_close_available",
    "corporate_action_handling_status",
    "ticker_identity_status",
    "commodity_pool_structure_review_status",
    "roll_or_carry_handling_status",
    "etp_structure_review_status",
    "later_strategy_execution_eligibility",
    "eligibility_verdict",
    "blocked_reason",
]


class PriceProvider(Protocol):
    def fetch(self, provider_symbol: str, *, start: str, end: str) -> Any: ...


@dataclass(frozen=True)
class BundleResult:
    output_root: Path
    audit_rows: list[dict[str, str]]
    universe_verdict: str
    provider_request: dict[str, Any]
    manifest: dict[str, Any]


def load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a mapping")
    return raw


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def inclusive_provider_end(end_date: str) -> str:
    return (parse_date(end_date) + timedelta(days=1)).isoformat()


def read_normalised(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.date
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def frame_dates(frame: pd.DataFrame, start: date, end: date) -> set[date]:
    dates = set(pd.to_datetime(frame["date"], errors="raise").dt.date)
    return {value for value in dates if start <= value <= end}


def value_available(frame: pd.DataFrame, column: str, expected_dates: set[date]) -> bool:
    if column not in frame.columns:
        return False
    by_date = frame.set_index("date")
    if not expected_dates <= set(by_date.index):
        return False
    values = pd.to_numeric(by_date.loc[sorted(expected_dates), column], errors="coerce")
    return bool(values.notna().all() and values.gt(0).all())


def corporate_action_status(raw_frame: pd.DataFrame) -> str:
    actions = corporate_action_frame(raw_frame)
    if {"dividends", "splits"}.issubset(actions.columns):
        return "source_actions_captured"
    return "source_actions_missing"


def expected_session_dates(snapshots: dict[str, Any], start: date, end: date) -> set[date]:
    if "SPY" not in snapshots:
        raise ValueError("SPY snapshot is required to define expected observed sessions")
    spy = read_normalised(Path(snapshots["SPY"].normalised_file_path))
    dates = frame_dates(spy, start, end)
    if start not in dates or end not in dates:
        raise ValueError("SPY expected-session reference does not cover the frozen window")
    return dates


def provider_environment_detail() -> str:
    try:
        import yfinance as yf

        return f"yfinance {getattr(yf, '__version__', 'unknown')}"
    except Exception:
        return "yfinance unavailable until provider invocation"


def make_default_provider(output_root: Path, timeout_seconds: int) -> YFinanceProvider:
    return YFinanceProvider(
        cache_root=output_root / "provider_cache",
        raw_root=output_root / "raw",
        processed_root=output_root / "normalised",
        manifest_root=output_root / "provider_manifests",
        timeout_seconds=timeout_seconds,
    )


def validate_required_tickers(tickers: list[str]) -> None:
    if tickers != REQUIRED_TICKERS:
        raise ValueError("GMA-6B required tickers must match the frozen GMA-6A universe order")
    if len(set(tickers)) != 29:
        raise ValueError("GMA-6B universe must contain exactly 29 unique tickers")


def evaluate_ticker(
    snapshot: Any,
    expected_dates: set[date],
    start: date,
    end: date,
    expected_ticker: str | None = None,
) -> dict[str, str]:
    ticker = expected_ticker or str(snapshot.provider_symbol)
    normalised = read_normalised(Path(snapshot.normalised_file_path))
    observed_dates = frame_dates(normalised, start, end)
    missing_dates = expected_dates - observed_dates
    first_observed = min(observed_dates).isoformat() if observed_dates else ""
    last_observed = max(observed_dates).isoformat() if observed_dates else ""
    adjusted_available = value_available(normalised, "adj_close", expected_dates)
    raw_close_available = value_available(normalised, "close", expected_dates)
    identity_status = (
        "requested_ticker_preserved"
        if str(snapshot.provider_symbol) == ticker
        else "ticker_substitution_detected"
    )
    action_status = corporate_action_status(snapshot.raw_frame)
    reasons: list[str] = []
    if first_observed != start.isoformat():
        reasons.append("start_date_shortened")
    if last_observed != end.isoformat():
        reasons.append("end_date_not_covered")
    if missing_dates:
        reasons.append("missing_expected_sessions")
    if not adjusted_available:
        reasons.append("missing_adjusted_prices")
    if not raw_close_available:
        reasons.append("missing_raw_close")
    if identity_status != "requested_ticker_preserved":
        reasons.append("ticker_substitution_detected")
    commodity_status = ""
    roll_status = ""
    etp_status = "documented_for_later_execution"
    later_eligibility = ELIGIBLE
    verdict = ELIGIBLE
    if ticker in COMMODITY_POOL_TICKERS:
        commodity_status = PENDING
        roll_status = PENDING
        etp_status = ""
        later_eligibility = PENDING
        verdict = PENDING
        reasons.append("commodity_pool_roll_or_carry_review_pending")
    if reasons and verdict != PENDING:
        verdict = BLOCKED
        later_eligibility = BLOCKED
    return {
        "ticker": ticker,
        "raw_provider_file_hash": sha256_file(Path(snapshot.raw_file_path)),
        "normalised_series_file_hash": sha256_file(Path(snapshot.normalised_file_path)),
        "first_observed_date": first_observed,
        "last_observed_date": last_observed,
        "session_count": str(len(observed_dates)),
        "missing_session_count": str(len(missing_dates)),
        "adjusted_price_available": str(adjusted_available).lower(),
        "raw_close_available": str(raw_close_available).lower(),
        "corporate_action_handling_status": action_status,
        "ticker_identity_status": identity_status,
        "commodity_pool_structure_review_status": commodity_status,
        "roll_or_carry_handling_status": roll_status,
        "etp_structure_review_status": etp_status,
        "later_strategy_execution_eligibility": later_eligibility,
        "eligibility_verdict": verdict,
        "blocked_reason": ";".join(sorted(set(reasons))),
    }


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_audit_markdown(path: Path, rows: list[dict[str, str]], universe_verdict: str) -> None:
    body = [
        "# GMA-6B Expanded ETF Data Eligibility v1",
        "",
        "This is observed development evidence and not a pristine final holdout.",
        "No strategy, portfolio replay, model fit, allocation, execution, or promotion decision is produced.",
        "A data-eligible universe does not imply that it improves return, diversification, or risk-adjusted performance.",
        "",
        f"Universe verdict: `{universe_verdict}`",
        "",
        markdown_table(
            ["ticker", "verdict", "first", "last", "missing", "reason"],
            [
                [
                    row["ticker"],
                    row["eligibility_verdict"],
                    row["first_observed_date"],
                    row["last_observed_date"],
                    row["missing_session_count"],
                    row["blocked_reason"],
                ]
                for row in rows
            ],
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body), encoding="utf-8")


def write_hash_csvs(output_root: Path, rows: list[dict[str, str]]) -> None:
    write_csv(
        output_root / "gma6b_raw_file_hashes_v1.csv",
        [
            {"ticker": row["ticker"], "raw_provider_file_hash": row["raw_provider_file_hash"]}
            for row in rows
        ],
        ["ticker", "raw_provider_file_hash"],
    )
    write_csv(
        output_root / "gma6b_normalised_file_hashes_v1.csv",
        [
            {
                "ticker": row["ticker"],
                "normalised_series_file_hash": row["normalised_series_file_hash"],
            }
            for row in rows
        ],
        ["ticker", "normalised_series_file_hash"],
    )


def run_gma6b_data_bundle(
    *,
    config_path: Path = CONFIG_PATH,
    universe_config_path: Path = UNIVERSE_CONFIG_PATH,
    provider: PriceProvider | None = None,
    downloaded_at_utc: str | None = None,
) -> BundleResult:
    config = load_yaml(config_path)
    contract = load_gma6a_universe_contract(universe_config_path)
    validate_gma6a_universe_contract(contract)
    tickers = [row["ticker"] for row in contract.instruments]
    validate_required_tickers(tickers)
    start = str(config["contract"]["requested_start_date"])
    end = str(config["contract"]["requested_end_date"])
    start_date = parse_date(start)
    end_date = parse_date(end)
    output_root = Path(config["contract"].get("output_root", str(OUTPUT_ROOT)))
    output_root.mkdir(parents=True, exist_ok=True)
    downloaded_at = downloaded_at_utc or datetime.now(timezone.utc).isoformat()
    universe_hash = sha256_file(universe_config_path)
    provider_record = {
        "provider_name": config["provider"]["provider_name"],
        "provider_module_path": config["provider"]["provider_module_path"],
        "provider_version_or_environment_detail": provider_environment_detail(),
        "downloaded_at_utc": downloaded_at,
        "requested_start_date": start,
        "requested_end_date": end,
        "provider_fetch_end_exclusive": inclusive_provider_end(end),
        "universe_contract_hash": universe_hash,
    }
    write_json(output_root / "gma6b_provider_request_record_v1.json", provider_record)
    active_provider = provider or make_default_provider(
        output_root, int(config["provider"].get("timeout_seconds", 60))
    )
    snapshots: dict[str, Any] = {}
    for ticker in tickers:
        snapshots[ticker] = active_provider.fetch(
            ticker, start=start, end=inclusive_provider_end(end)
        )
    expected_dates = expected_session_dates(snapshots, start_date, end_date)
    audit_rows = [
        evaluate_ticker(
            snapshots[ticker],
            expected_dates,
            start_date,
            end_date,
            expected_ticker=ticker,
        )
        for ticker in tickers
    ]
    universe_verdict = (
        UNIVERSE_ELIGIBLE
        if all(row["eligibility_verdict"] == ELIGIBLE for row in audit_rows)
        else UNIVERSE_BLOCKED
    )
    write_csv(output_root / "gma6b_ticker_eligibility_audit_v1.csv", audit_rows, AUDIT_FIELDS)
    write_audit_markdown(
        output_root / "gma6b_ticker_eligibility_audit_v1.md", audit_rows, universe_verdict
    )
    write_csv(ELIGIBILITY_CSV, audit_rows, AUDIT_FIELDS)
    write_audit_markdown(ELIGIBILITY_MD, audit_rows, universe_verdict)
    write_hash_csvs(output_root, audit_rows)
    verdict_payload = {
        "phase_id": PHASE_ID,
        "universe_verdict": universe_verdict,
        "ticker_verdict_counts": {
            str(key): int(value)
            for key, value in pd.Series([row["eligibility_verdict"] for row in audit_rows])
            .value_counts()
            .sort_index()
            .items()
        },
        "blocked_or_pending_tickers": [
            row["ticker"] for row in audit_rows if row["eligibility_verdict"] != ELIGIBLE
        ],
    }
    write_json(output_root / "gma6b_universe_data_contract_verdict_v1.json", verdict_payload)
    manifest = {
        "phase_id": PHASE_ID,
        "provider_request_record_hash": sha256_file(
            output_root / "gma6b_provider_request_record_v1.json"
        ),
        "ticker_eligibility_audit_hash": sha256_file(
            output_root / "gma6b_ticker_eligibility_audit_v1.csv"
        ),
        "raw_file_hashes_hash": sha256_file(output_root / "gma6b_raw_file_hashes_v1.csv"),
        "normalised_file_hashes_hash": sha256_file(
            output_root / "gma6b_normalised_file_hashes_v1.csv"
        ),
        "universe_data_contract_verdict_hash": sha256_file(
            output_root / "gma6b_universe_data_contract_verdict_v1.json"
        ),
        "requested_tickers": tickers,
        "requested_start_date": start,
        "requested_end_date": end,
        "universe_contract_hash": universe_hash,
        "deterministic_manifest_hash": sha256_structured(
            {"tickers": tickers, "start": start, "end": end, "universe_hash": universe_hash}
        ),
    }
    write_json(output_root / "gma6b_data_bundle_manifest_v1.json", manifest)
    return BundleResult(output_root, audit_rows, universe_verdict, provider_record, manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the GMA-6B data eligibility bundle.")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--universe-config", default=str(UNIVERSE_CONFIG_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_gma6b_data_bundle(
        config_path=Path(args.config), universe_config_path=Path(args.universe_config)
    )


if __name__ == "__main__":
    main()
