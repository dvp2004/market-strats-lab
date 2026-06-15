from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.frozen_cost_aware_portfolio import (
    DEFAULT_PHASE23I_CONFIG,
    build_phase23i_model_freeze,
    save_phase23i_prospective_shadow_runner,
)
from market_strats.analysis.pilot_individual_equity_feature_calculation import (
    DEFAULT_PHASE23F_CONFIG,
    build_calculated_feature_registry,
    build_pilot_panel_and_targets,
)
from market_strats.analysis.post_endpoint_individual_equity_extension import (
    DEFAULT_PHASE23J_CONFIG,
    merge_historical_and_extension,
    next_us_equity_trading_day,
    save_phase23j_post_endpoint_individual_equity_extension,
    validate_extension_against_history,
)


def test_phase23j_overlap_default_is_twenty_one_rows() -> None:
    assert DEFAULT_PHASE23J_CONFIG["minimum_overlap_rows"] == 21


def _price_frame(dates: pd.DatetimeIndex, base: float, drift: float) -> pd.DataFrame:
    index = np.arange(len(dates), dtype=float)
    close = base * np.exp(drift * index + 0.015 * np.sin(index / 13.0))
    open_ = close * (1.0 - 0.001)
    return pd.DataFrame(
        {
            "date": dates,
            "open": open_,
            "high": close * 1.004,
            "low": open_ * 0.996,
            "close": close,
            "adj_close": close,
            "volume": 1_000_000 + index * 100,
            "dividends": 0.0,
            "stock_splits": 0.0,
        }
    )


def _prepare_sources(tmp_path: Path) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    data_dir = tmp_path / "data" / "individual_equity_pilot"
    phase23f_dir = tmp_path / "reports" / "phase23f"
    phase23i_dir = tmp_path / "reports" / "phase23i"
    data_dir.mkdir(parents=True)
    phase23f_dir.mkdir(parents=True)
    phase23i_dir.mkdir(parents=True)

    dates = pd.bdate_range("2023-01-02", "2026-05-01")
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    sectors = ["Tech", "Health", "Finance", "Energy"]
    frames: dict[str, pd.DataFrame] = {}
    manifest_rows = []
    for idx, (ticker, sector) in enumerate(zip(tickers, sectors, strict=True)):
        frame = _price_frame(dates, 50 + idx * 15, 0.0005 + idx * 0.00008)
        frame.to_csv(data_dir / f"{ticker}.csv", index=False)
        security_id = f"SEC_{ticker}"
        frames[security_id] = frame
        manifest_rows.append(
            {
                "universe_id": "PILOT",
                "permanent_security_id": security_id,
                "permanent_company_id": f"CO_{ticker}",
                "ticker": ticker,
                "sector": sector,
                "industry": "Test",
                "membership_start_date": "2023-01-03",
                "membership_end_date": "",
                "membership_known_timestamp_utc": "2023-01-03T00:00:00Z",
                "price_file": f"{ticker}.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
            }
        )
    benchmark = _price_frame(dates, 100, 0.00045)
    benchmark.to_csv(data_dir / "benchmark_SPY.csv", index=False)
    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(data_dir / "pilot_membership_manifest.csv", index=False)

    phase23f_config = {
        **DEFAULT_PHASE23F_CONFIG,
        "pilot_start_date": "2024-01-02",
        "pilot_end_date": "2026-05-01",
        "minimum_securities": 3,
        "minimum_price_rows": 320,
        "minimum_average_dollar_volume": 0,
    }
    panel, targets, _inventory = build_pilot_panel_and_targets(
        manifest=manifest,
        price_frames=frames,
        benchmark=benchmark,
        phase_config=phase23f_config,
    )
    panel.to_csv(phase23f_dir / "phase23f_pilot_feature_panel.csv", index=False)
    targets.to_csv(phase23f_dir / "phase23f_pilot_targets.csv", index=False)
    features = build_calculated_feature_registry()
    features.to_csv(phase23f_dir / "phase23f_calculated_feature_registry.csv", index=False)

    model_registry = pd.DataFrame(
        [
            {
                "model_version": "phase23g_ridge_ranker_v1",
                "primary_target": "forward_20d_excess_return_vs_universe",
                "feature_set": ";".join(features["feature_name"].tolist()),
                "ridge_alpha": 1.0,
                "preprocessing": "cross-sectional zscore",
                "purge_window_trading_days": 63,
                "embargo_window_trading_days": 63,
            }
        ]
    )
    freeze, hashes = build_phase23i_model_freeze(
        config={**DEFAULT_PHASE23I_CONFIG, "canonical_research_endpoint": "2026-05-01"},
        model_registry=model_registry,
        feature_registry=features,
        git_commit="test",
        generated_at_utc="2026-05-02T00:00:00+00:00",
    )
    freeze.to_csv(phase23i_dir / "phase23i_model_freeze.csv", index=False)
    hashes.to_csv(phase23i_dir / "phase23i_model_freeze_hashes.csv", index=False)

    all_frames = {"SPY": benchmark}
    for ticker in tickers:
        all_frames[ticker] = pd.read_csv(data_dir / f"{ticker}.csv")
    return all_frames, manifest


def _extension_downloads(history: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    post_dates = pd.bdate_range("2026-05-04", "2026-06-15")
    downloads: dict[str, pd.DataFrame] = {}
    for index, (ticker, frame) in enumerate(history.items()):
        historical = frame.copy()
        historical["date"] = pd.to_datetime(historical["date"])
        overlap = historical.loc[historical["date"].ge("2026-03-25")].copy()
        last_close = float(historical.iloc[-1]["close"])
        post = _price_frame(post_dates, last_close * 1.002, 0.0006 + index * 0.00003)
        downloads[ticker] = pd.concat([overlap, post], ignore_index=True)
    return downloads


def _config(tmp_path: Path) -> dict:
    return {
        "phase23j_post_endpoint_individual_equity_extension": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "phase23j"),
            "dashboard_status_path": str(
                tmp_path / "reports" / "dashboard" / "phase23j.csv"
            ),
            "historical_input_dir": str(
                tmp_path / "data" / "individual_equity_pilot"
            ),
            "extension_input_dir": str(
                tmp_path / "data" / "individual_equity_post_endpoint"
            ),
            "combined_input_dir": str(
                tmp_path / "data" / "individual_equity_post_endpoint" / "combined"
            ),
            "source_phase23f_dir": str(tmp_path / "reports" / "phase23f"),
            "source_phase23g_dir": str(tmp_path / "reports" / "phase23g"),
            "source_phase23i_dir": str(tmp_path / "reports" / "phase23i"),
            "canonical_research_endpoint": "2026-05-01",
            "overlap_start_date": "2026-03-25",
            "minimum_overlap_rows": 21,
            "as_of_date": "2026-06-15",
            "minimum_post_endpoint_rows": 5,
            "minimum_security_count": 3,
            "retry_attempts": 1,
            "retry_delay_seconds": 0,
            "inter_symbol_delay_seconds": 0,
            "allow_network_download": True,
            "starting_cash": 10000,
        },
        "phase23i_frozen_cost_aware_portfolio": {
            "max_single_stock_weight": 0.20,
            "max_top5_sector_security_count": 2,
            "max_sector_weight": 0.40,
        },
        "phase23i_prospective_shadow_runner": {
            "starting_cash": 10000,
        },
    }


def test_extension_validation_and_merge_preserve_endpoint_history() -> None:
    history = _price_frame(pd.bdate_range("2026-04-01", "2026-05-01"), 100, 0.001)
    extension = pd.concat(
        [
            history.loc[pd.to_datetime(history["date"]).ge("2026-04-20")],
            _price_frame(pd.bdate_range("2026-05-04", "2026-05-15"), 103, 0.001),
        ],
        ignore_index=True,
    )
    validation = validate_extension_against_history(
        historical=history,
        extension=extension,
        endpoint=pd.Timestamp("2026-05-01"),
        minimum_overlap_rows=5,
        minimum_post_endpoint_rows=5,
        price_relative_tolerance=1e-8,
        volume_absolute_tolerance=0,
    )
    assert validation["passed"].all()
    merged = merge_historical_and_extension(
        historical=history,
        extension=extension,
        endpoint=pd.Timestamp("2026-05-01"),
    )
    assert merged["date"].min() == pd.Timestamp("2026-04-01")
    assert merged["date"].max() == pd.Timestamp("2026-05-15")
    original_endpoint = history.loc[pd.to_datetime(history["date"]).eq("2026-05-01"), "close"].iloc[0]
    merged_endpoint = merged.loc[pd.to_datetime(merged["date"]).eq("2026-05-01"), "close"].iloc[0]
    assert original_endpoint == merged_endpoint


def test_phase23j_generates_prospective_ranking_and_target(tmp_path: Path) -> None:
    history, _manifest = _prepare_sources(tmp_path)
    downloads = _extension_downloads(history)

    def download(ticker: str, _start: str, _end: str) -> pd.DataFrame:
        return downloads[ticker].copy()

    outputs = save_phase23j_post_endpoint_individual_equity_extension(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        download_fn=download,
    )
    summary = outputs["summary"].iloc[0]
    assert summary["phase23j_decision"] == (
        "phase23j_post_endpoint_shadow_activation_ready_manual_research_only"
    )
    assert bool(summary["prospective_ranking_generated"])
    assert bool(summary["shadow_activation_ready"])
    assert len(outputs["current_ranking"]) == 4
    assert not outputs["current_target_portfolio"].empty
    assert outputs["current_target_portfolio"]["reference_price"].gt(0).all()
    assert "expected_execution_date" in outputs["current_target_portfolio"].columns
    assert "observed_execution_date" in outputs["current_target_portfolio"].columns
    assert not (tmp_path / "reports" / "reports").exists()


def test_phase23j_expected_execution_date_uses_holiday_calendar() -> None:
    assert next_us_equity_trading_day(pd.Timestamp("2026-06-12")) == pd.Timestamp("2026-06-15")
    assert next_us_equity_trading_day(pd.Timestamp("2026-06-18")) == pd.Timestamp("2026-06-22")


def test_phase23j_blocks_on_overlap_mismatch(tmp_path: Path) -> None:
    history, _manifest = _prepare_sources(tmp_path)
    downloads = _extension_downloads(history)
    downloads["AAA"].loc[0, "close"] *= 1.5

    def download(ticker: str, _start: str, _end: str) -> pd.DataFrame:
        return downloads[ticker].copy()

    outputs = save_phase23j_post_endpoint_individual_equity_extension(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        download_fn=download,
    )
    assert outputs["summary"].iloc[0]["phase23j_decision"] == (
        "phase23j_post_endpoint_extension_incomplete"
    )
    assert not bool(outputs["summary"].iloc[0]["shadow_activation_ready"])


def test_phase23i_shadow_consumes_phase23j_outputs(tmp_path: Path) -> None:
    history, _manifest = _prepare_sources(tmp_path)
    downloads = _extension_downloads(history)

    def download(ticker: str, _start: str, _end: str) -> pd.DataFrame:
        return downloads[ticker].copy()

    config = _config(tmp_path)
    save_phase23j_post_endpoint_individual_equity_extension(
        config=config,
        reports_dir=tmp_path / "reports",
        download_fn=download,
    )
    config["phase23i_prospective_shadow_runner"] = {
        "enabled": True,
        "output_dir": str(tmp_path / "reports" / "shadow"),
        "dashboard_status_path": str(tmp_path / "reports" / "dashboard" / "shadow.csv"),
        "source_phase23i_dir": str(tmp_path / "reports" / "phase23i"),
        "source_phase23g_dir": str(tmp_path / "reports" / "phase23g"),
        "source_phase23j_dir": str(tmp_path / "reports" / "phase23j"),
        "pilot_input_dir": str(tmp_path / "data" / "individual_equity_pilot"),
        "archive_dir": str(tmp_path / "reports" / "shadow" / "archive"),
        "canonical_research_endpoint": "2026-05-01",
        "starting_cash": 10000,
    }
    outputs = save_phase23i_prospective_shadow_runner(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    assert bool(outputs["summary"].iloc[0]["shadow_readiness_passed"])
    assert not outputs["current_manual_session_template"].empty
    assert outputs["current_manual_session_template"]["reference_price"].gt(0).all()
    assert outputs["current_manual_session_template"]["proposed_quantity"].gt(0).all()
    assert outputs["positions"].iloc[0]["position_status"] == "initial_shadow_cash_only"


def test_entered_shadow_session_updates_positions_cash_and_archive(tmp_path: Path) -> None:
    history, _manifest = _prepare_sources(tmp_path)
    downloads = _extension_downloads(history)

    def download(ticker: str, _start: str, _end: str) -> pd.DataFrame:
        return downloads[ticker].copy()

    config = _config(tmp_path)
    save_phase23j_post_endpoint_individual_equity_extension(
        config=config,
        reports_dir=tmp_path / "reports",
        download_fn=download,
    )
    shadow_dir = tmp_path / "reports" / "shadow"
    config["phase23i_prospective_shadow_runner"] = {
        "enabled": True,
        "output_dir": str(shadow_dir),
        "dashboard_status_path": str(tmp_path / "reports" / "dashboard" / "shadow.csv"),
        "source_phase23i_dir": str(tmp_path / "reports" / "phase23i"),
        "source_phase23g_dir": str(tmp_path / "reports" / "phase23g"),
        "source_phase23j_dir": str(tmp_path / "reports" / "phase23j"),
        "pilot_input_dir": str(tmp_path / "data" / "individual_equity_pilot"),
        "archive_dir": str(shadow_dir / "archive"),
        "canonical_research_endpoint": "2026-05-01",
        "starting_cash": 10000,
        "simulated_cost_bps": 10,
    }
    first = save_phase23i_prospective_shadow_runner(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    template = first["current_manual_session_template"].copy()
    template["manual_decision"] = "enter_simulated_shadow_trade"
    template["session_state"] = "entered"
    template["simulated_fill_price"] = template["reference_price"]
    template["simulated_fill_quantity"] = template["proposed_quantity"]
    template["override_reason"] = "explicit_test_simulated_fill"
    template["notes"] = "research-only test fill"
    template.to_csv(shadow_dir / "shadow_manual_session_filled.csv", index=False)

    second = save_phase23i_prospective_shadow_runner(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    positions = second["positions"]
    assert positions.loc[positions["ticker"].ne("CASH"), "shares"].gt(0).all()
    assert positions.loc[positions["ticker"].eq("CASH"), "cash_balance"].iloc[0] < 10000
    assert second["valuation_history"].iloc[0]["portfolio_value"] > 0
    assert not (shadow_dir / "shadow_manual_session_filled.csv").exists()
    assert list((shadow_dir / "archive").glob("shadow_manual_session_filled_*.csv"))


def test_phase23j_proposal_waits_for_next_open_price(tmp_path: Path) -> None:
    history, _manifest = _prepare_sources(tmp_path)
    downloads = _extension_downloads(history)
    for ticker, frame in list(downloads.items()):
        working = frame.copy()
        working["date"] = pd.to_datetime(working["date"])
        downloads[ticker] = working.loc[working["date"].le("2026-06-12")].copy()

    def download(ticker: str, _start: str, _end: str) -> pd.DataFrame:
        return downloads[ticker].copy()

    config = _config(tmp_path)
    config["phase23j_post_endpoint_individual_equity_extension"]["as_of_date"] = (
        "2026-06-12"
    )
    outputs = save_phase23j_post_endpoint_individual_equity_extension(
        config=config,
        reports_dir=tmp_path / "reports",
        download_fn=download,
    )
    summary = outputs["summary"].iloc[0]
    assert summary["phase23j_decision"] == (
        "phase23j_post_endpoint_shadow_proposal_ready_execution_pending"
    )
    assert bool(summary["manual_shadow_proposal_ready"])
    assert not bool(summary["simulated_fill_ready"])
    assert not bool(summary["shadow_activation_ready"])
    assert not outputs["current_target_portfolio"]["paper_order_allowed"].any()
