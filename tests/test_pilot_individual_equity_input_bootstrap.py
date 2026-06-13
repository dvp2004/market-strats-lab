from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.pilot_individual_equity_input_bootstrap import (
    DEFAULT_PHASE23F_INPUT_CONFIG,
    build_pilot_security_registry,
    normalize_yfinance_price_frame,
    save_phase23f_pilot_individual_equity_input_bootstrap,
    validate_downloaded_price_frame,
    validate_pilot_security_registry,
)


def _fake_download(ticker: str, start: str, end: str) -> pd.DataFrame:
    del ticker, start, end
    dates = pd.bdate_range("2021-12-01", "2026-05-01")
    base = 100.0 + np.arange(len(dates), dtype=float) * 0.05
    return pd.DataFrame(
        {
            "Open": base,
            "High": base + 1.0,
            "Low": base - 1.0,
            "Close": base + 0.25,
            "Adj Close": base + 0.20,
            "Volume": np.full(len(dates), 2_000_000.0),
            "Dividends": np.zeros(len(dates)),
            "Stock Splits": np.zeros(len(dates)),
        },
        index=dates,
    )


def _config(tmp_path: Path) -> dict:
    return {
        "phase23f_pilot_individual_equity_input_bootstrap": {
            "enabled": True,
            "output_dir": "reports/test_phase23f_inputs",
            "dashboard_status_path": "reports/paper_trading/dashboard/test_phase23f_inputs.csv",
            "input_dir": "data/individual_equity_pilot",
            "membership_manifest_path": "data/individual_equity_pilot/pilot_membership_manifest.csv",
            "minimum_price_rows": 700,
            "minimum_securities": 3,
            "retry_attempts": 1,
            "retry_delay_seconds": 0,
            "inter_symbol_delay_seconds": 0,
            "pilot_securities": DEFAULT_PHASE23F_INPUT_CONFIG["pilot_securities"][:3],
        }
    }


def test_default_registry_is_noncanonical_and_diversified():
    registry = build_pilot_security_registry(DEFAULT_PHASE23F_INPUT_CONFIG)
    report = validate_pilot_security_registry(registry, minimum_securities=12)

    assert report["passed"].all()
    assert len(registry) == 16
    assert registry["sector"].nunique() >= 7
    assert not registry["canonical_membership"].any()
    assert registry["research_pilot_only"].all()


def test_normalize_yfinance_flat_frame():
    normalized = normalize_yfinance_price_frame(_fake_download("AAPL", "", ""))

    assert list(normalized.columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "dividends",
        "stock_splits",
    ]
    assert normalized["date"].is_monotonic_increasing
    assert normalized["adj_close"].notna().all()


def test_normalize_rejects_interior_incomplete_row():
    frame = _fake_download("AAPL", "", "")
    frame.iloc[100, frame.columns.get_loc("Close")] = np.nan

    try:
        normalize_yfinance_price_frame(frame)
    except ValueError as exc:
        assert "incomplete non-trailing" in str(exc)
    else:
        raise AssertionError("Expected incomplete interior row to fail")


def test_price_validation_requires_full_window():
    normalized = normalize_yfinance_price_frame(_fake_download("AAPL", "", ""))
    report = validate_downloaded_price_frame(
        normalized,
        minimum_price_rows=700,
        requested_start_date="2021-12-01",
        requested_end_date_inclusive="2026-05-01",
    )

    assert report["passed"].all()


def test_bootstrap_writes_inputs_manifest_and_no_double_reports(tmp_path: Path):
    reports_dir = tmp_path / "reports"
    outputs = save_phase23f_pilot_individual_equity_input_bootstrap(
        config=_config(tmp_path),
        reports_dir=reports_dir,
        download_fn=_fake_download,
    )

    summary = outputs["summary"].iloc[0]
    manifest_path = tmp_path / "data/individual_equity_pilot/pilot_membership_manifest.csv"
    assert bool(summary["all_required_downloads_ready"])
    assert bool(summary["membership_manifest_written"])
    assert bool(summary["phase23f_feature_calculation_ready"])
    assert manifest_path.exists()
    manifest = pd.read_csv(manifest_path)
    assert len(manifest) == 3
    assert not manifest["canonical_membership"].astype(bool).any()
    assert manifest["research_pilot_only"].astype(bool).all()
    assert not (reports_dir / "reports").exists()


def test_bootstrap_fails_closed_when_one_symbol_download_fails(tmp_path: Path):
    def failing_download(ticker: str, start: str, end: str) -> pd.DataFrame:
        if ticker == "MSFT":
            raise RuntimeError("provider failure")
        return _fake_download(ticker, start, end)

    outputs = save_phase23f_pilot_individual_equity_input_bootstrap(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        download_fn=failing_download,
    )

    summary = outputs["summary"].iloc[0]
    manifest_path = tmp_path / "data/individual_equity_pilot/pilot_membership_manifest.csv"
    assert not bool(summary["all_required_downloads_ready"])
    assert not bool(summary["membership_manifest_written"])
    assert not manifest_path.exists()
    failed = outputs["download_status"].query("status == 'failed'")
    assert set(failed["ticker"]) == {"MSFT"}


def test_bootstrap_reuses_existing_valid_files(tmp_path: Path):
    config = _config(tmp_path)
    reports_dir = tmp_path / "reports"
    save_phase23f_pilot_individual_equity_input_bootstrap(
        config=config,
        reports_dir=reports_dir,
        download_fn=_fake_download,
    )

    def must_not_download(ticker: str, start: str, end: str) -> pd.DataFrame:
        raise AssertionError(f"Unexpected download: {ticker} {start} {end}")

    outputs = save_phase23f_pilot_individual_equity_input_bootstrap(
        config=config,
        reports_dir=reports_dir,
        download_fn=must_not_download,
    )

    assert outputs["download_status"]["reused_existing"].all()
    assert outputs["summary"].iloc[0]["phase23f_feature_calculation_ready"]
