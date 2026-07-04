from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest
import yaml

from market_strats.global_multi_asset.gma6b_data_bundle import (
    BLOCKED,
    PENDING,
    REQUIRED_TICKERS,
    UNIVERSE_BLOCKED,
    evaluate_ticker,
    expected_session_dates,
    run_gma6b_data_bundle,
    validate_required_tickers,
)

CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1.yaml")
UNIVERSE_CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma6a_expanded_etf_universe_v1.yaml")
MODULE_PATH = Path("src/market_strats/global_multi_asset/gma6b_data_bundle.py")


@dataclass
class FakeSnapshot:
    provider_symbol: str
    raw_frame: pd.DataFrame
    normalised_file_path: Path
    raw_file_path: Path


class FakeProvider:
    def __init__(
        self,
        root: Path,
        *,
        missing_ticker: str | None = None,
        missing_adjusted: str | None = None,
        short_start: str | None = None,
        substitute: dict[str, str] | None = None,
    ):
        self.root = root
        self.calls: list[str] = []
        self.missing_ticker = missing_ticker
        self.missing_adjusted = missing_adjusted
        self.short_start = short_start
        self.substitute = substitute or {}

    def fetch(self, provider_symbol: str, *, start: str, end: str) -> FakeSnapshot:
        self.calls.append(provider_symbol)
        actual_symbol = self.substitute.get(provider_symbol, provider_symbol)
        raw_dir = self.root / "raw" / provider_symbol
        norm_dir = self.root / "normalised" / provider_symbol
        raw_dir.mkdir(parents=True, exist_ok=True)
        norm_dir.mkdir(parents=True, exist_ok=True)
        dates = pd.to_datetime(["2007-05-30", "2007-05-31", "2007-06-01", "2026-05-01"])
        if provider_symbol == self.missing_ticker:
            dates = dates.delete(1)
        if provider_symbol == self.short_start:
            dates = dates[1:]
        raw = pd.DataFrame(
            {
                "Date": dates,
                "Open": [10.0 + idx for idx in range(len(dates))],
                "High": [11.0 + idx for idx in range(len(dates))],
                "Low": [9.0 + idx for idx in range(len(dates))],
                "Close": [10.5 + idx for idx in range(len(dates))],
                "Adj Close": [10.4 + idx for idx in range(len(dates))],
                "Volume": [1000 + idx for idx in range(len(dates))],
                "Dividends": [0.0 for _ in range(len(dates))],
                "Stock Splits": [0.0 for _ in range(len(dates))],
            }
        )
        if provider_symbol == self.missing_adjusted:
            raw["Adj Close"] = pd.NA
        normalised = pd.DataFrame(
            {
                "date": dates.date,
                "open": raw["Open"],
                "high": raw["High"],
                "low": raw["Low"],
                "close": raw["Close"],
                "adj_close": raw["Adj Close"],
                "volume": raw["Volume"],
            }
        )
        raw_path = raw_dir / f"{provider_symbol}.csv"
        norm_path = norm_dir / f"{provider_symbol}_normalised.csv"
        raw.to_csv(raw_path, index=False)
        normalised.to_csv(norm_path, index=False)
        return FakeSnapshot(actual_symbol, raw, norm_path, raw_path)


def _tmp_config(tmp_path: Path) -> Path:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["contract"]["output_root"] = str(tmp_path / "bundle")
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "gma6b.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def test_exactly_29_required_tickers_are_requested_in_order(tmp_path: Path):
    provider = FakeProvider(tmp_path)
    result = run_gma6b_data_bundle(
        config_path=_tmp_config(tmp_path),
        universe_config_path=UNIVERSE_CONFIG_PATH,
        provider=provider,
        downloaded_at_utc="2026-06-23T00:00:00+00:00",
    )
    assert provider.calls == REQUIRED_TICKERS
    assert len(result.audit_rows) == 29


def test_missing_coverage_fails_closed(tmp_path: Path):
    provider = FakeProvider(tmp_path, missing_ticker="TIP")
    result = run_gma6b_data_bundle(
        config_path=_tmp_config(tmp_path),
        universe_config_path=UNIVERSE_CONFIG_PATH,
        provider=provider,
        downloaded_at_utc="2026-06-23T00:00:00+00:00",
    )
    tip = next(row for row in result.audit_rows if row["ticker"] == "TIP")
    assert tip["eligibility_verdict"] == BLOCKED
    assert "missing_expected_sessions" in tip["blocked_reason"]


def test_missing_adjusted_prices_fail_closed(tmp_path: Path):
    provider = FakeProvider(tmp_path, missing_adjusted="VNQ")
    result = run_gma6b_data_bundle(
        config_path=_tmp_config(tmp_path),
        universe_config_path=UNIVERSE_CONFIG_PATH,
        provider=provider,
        downloaded_at_utc="2026-06-23T00:00:00+00:00",
    )
    row = next(item for item in result.audit_rows if item["ticker"] == "VNQ")
    assert row["adjusted_price_available"] == "false"
    assert row["eligibility_verdict"] == BLOCKED


def test_ticker_substitution_fails_closed(tmp_path: Path):
    snapshot = FakeProvider(tmp_path, substitute={"VNQ": "VNQ.A"}).fetch(
        "VNQ", start="2007-05-30", end="2026-05-02"
    )
    spy = FakeProvider(tmp_path).fetch("SPY", start="2007-05-30", end="2026-05-02")
    expected = expected_session_dates(
        {"SPY": spy}, pd.Timestamp("2007-05-30").date(), pd.Timestamp("2026-05-01").date()
    )
    row = evaluate_ticker(
        snapshot,
        expected,
        pd.Timestamp("2007-05-30").date(),
        pd.Timestamp("2026-05-01").date(),
        expected_ticker="VNQ",
    )
    assert row["ticker_identity_status"] == "ticker_substitution_detected"
    assert row["eligibility_verdict"] == BLOCKED


def test_start_date_shortening_fails_closed(tmp_path: Path):
    provider = FakeProvider(tmp_path, short_start="EWG")
    result = run_gma6b_data_bundle(
        config_path=_tmp_config(tmp_path),
        universe_config_path=UNIVERSE_CONFIG_PATH,
        provider=provider,
        downloaded_at_utc="2026-06-23T00:00:00+00:00",
    )
    row = next(item for item in result.audit_rows if item["ticker"] == "EWG")
    assert "start_date_shortened" in row["blocked_reason"]
    assert row["eligibility_verdict"] == BLOCKED


def test_uso_and_dba_cannot_be_eligible_without_structure_handling(tmp_path: Path):
    result = run_gma6b_data_bundle(
        config_path=_tmp_config(tmp_path),
        universe_config_path=UNIVERSE_CONFIG_PATH,
        provider=FakeProvider(tmp_path),
        downloaded_at_utc="2026-06-23T00:00:00+00:00",
    )
    for ticker in ["USO", "DBA"]:
        row = next(item for item in result.audit_rows if item["ticker"] == ticker)
        assert row["eligibility_verdict"] == PENDING
        assert row["commodity_pool_structure_review_status"] == PENDING
    assert result.universe_verdict == UNIVERSE_BLOCKED


def test_raw_and_normalised_hashes_are_recorded(tmp_path: Path):
    result = run_gma6b_data_bundle(
        config_path=_tmp_config(tmp_path),
        universe_config_path=UNIVERSE_CONFIG_PATH,
        provider=FakeProvider(tmp_path),
        downloaded_at_utc="2026-06-23T00:00:00+00:00",
    )
    assert all(row["raw_provider_file_hash"] for row in result.audit_rows)
    assert all(row["normalised_series_file_hash"] for row in result.audit_rows)
    assert (result.output_root / "gma6b_raw_file_hashes_v1.csv").exists()
    assert (result.output_root / "gma6b_normalised_file_hashes_v1.csv").exists()


def test_no_strategy_replay_allocation_or_model_imports():
    source = MODULE_PATH.read_text(encoding="utf-8")
    blocked = [
        "gma4_replay_adapter",
        "strategy_library",
        "sklearn",
        "allocation_engine",
        "portfolio_replay",
    ]
    assert not any(term in source for term in blocked)


def test_bundle_manifest_generation_is_deterministic(tmp_path: Path):
    result_one = run_gma6b_data_bundle(
        config_path=_tmp_config(tmp_path / "one"),
        universe_config_path=UNIVERSE_CONFIG_PATH,
        provider=FakeProvider(tmp_path / "one"),
        downloaded_at_utc="2026-06-23T00:00:00+00:00",
    )
    result_two = run_gma6b_data_bundle(
        config_path=_tmp_config(tmp_path / "two"),
        universe_config_path=UNIVERSE_CONFIG_PATH,
        provider=FakeProvider(tmp_path / "two"),
        downloaded_at_utc="2026-06-23T00:00:00+00:00",
    )
    assert (
        result_one.manifest["deterministic_manifest_hash"]
        == result_two.manifest["deterministic_manifest_hash"]
    )


def test_validate_required_tickers_rejects_wrong_order():
    bad = REQUIRED_TICKERS.copy()
    bad[0], bad[1] = bad[1], bad[0]
    with pytest.raises(ValueError, match="frozen GMA-6A universe order"):
        validate_required_tickers(bad)
