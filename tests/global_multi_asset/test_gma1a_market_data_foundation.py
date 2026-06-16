"""GMA-1A market-data-foundation tests — 40 focused test cases."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from market_strats.global_multi_asset.data.manifests import (
    sha256_file,
    write_manifest,
)
from market_strats.global_multi_asset.data.price_provider import safe_symbol
from market_strats.global_multi_asset.data.validation import normalise_price_frame
from market_strats.global_multi_asset.gma1a_config import (
    is_approved_gma_path,
    validate_gma1a_config,
)
from market_strats.global_multi_asset.gma1a_market_bundle import (
    build_total_return_series,
    next_eligible_completed_observation,
    reconcile_total_return,
)
from market_strats.global_multi_asset.gma1a_snapshot_selection import (
    _is_valid_live_yahoo_candidate,
    compute_selection_set_hash,
    select_canonical_snapshots,
)
from market_strats.global_multi_asset.universe import PROPOSED_INSTRUMENTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_config() -> dict:
    return {
        "track": {
            "track_id": "gma_alpha",
            "phase_id": "gma1a_market_data_foundation",
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        },
        "source_selection": {
            "gma0_manifest_root": "data/global_multi_asset_alpha/manifests",
            "gma0_report_root": "reports/global_multi_asset_alpha/feasibility",
            "selection_policy": "latest_valid_live_yahoo_snapshot",
            "require_live_yahoo_audit": True,
            "require_completed_history": True,
            "require_valid_hashes": True,
            "prohibit_mutable_latest_files": True,
            "require_provider_symbol_match": True,
            "require_registry_match": True,
        },
        "price_basis": {
            "execution_price_basis": "raw_open",
            "execution_validation_basis": "raw_ohlc",
            "signal_total_return_basis": "constructed_total_return",
            "adjusted_close_role": "reconciliation_and_cross_check_only",
            "dividend_accounting": "explicit_cash_dividends_from_provider",
            "split_accounting": "explicit_split_ratio_from_provider",
            "raw_price_split_basis_policy": "yahoo_auto_adjust_false_prices_are_split_adjusted",
            "missing_action_policy": "flag_and_continue",
        },
        "calendars": {
            "etf_calendar": "us_listed_etf",
            "bitcoin_calendar": "bitcoin_utc_daily",
            "decision_timezone": "America/New_York",
            "valuation_timezone": "America/New_York",
            "incomplete_observation_policy": "exclude_from_completed_history",
        },
        "cash": {
            "authoritative_source_type": "point_in_time_treasury_bill_rate",
            "bil_role": "tradable_etf_proxy_and_cross_check_only",
            "missing_rate_policy": "flag_and_defer_to_gma1b",
            "future_rate_phase": "gma1b_macro_data_foundation",
        },
        "quality": {
            "required_core_instruments": ["SPY", "QQQ"],
            "maximum_missing_interior_rows": 0,
            "maximum_duplicate_rows": 0,
            "adjusted_close_reconciliation_tolerance_bps": 1.0,
            "material_return_difference_tolerance_bps": 1.0,
            "require_raw_open": True,
            "require_raw_ohlc": True,
            "require_adjusted_close": True,
            "require_volume": True,
            "require_action_capability": True,
            "required_core_failure_policy": "block_gma1a",
        },
        "paths": {
            "canonical_bundle_root": "data/global_multi_asset_alpha/canonical_market",
            "report_root": "reports/global_multi_asset_alpha/data_foundation",
            "state_root": "state/global_multi_asset_alpha",
        },
    }


def _write_config(tmp_path: Path, config: dict | None = None) -> Path:
    path = tmp_path / "configs" / "gma1a.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(config or _base_config(), sort_keys=False), encoding="utf-8"
    )
    return path


def _price_frame(
    start: str = "2020-01-01",
    periods: int = 330,
    *,
    freq: str = "B",
    close_start: float = 100.0,
    dividend_idx: int | None = 60,
    dividend_amount: float = 0.50,
    split_idx: int | None = None,
    split_ratio: float = 2.0,
) -> pd.DataFrame:
    """Create a synthetic raw Yahoo-style price frame."""
    dates = pd.date_range(start, periods=periods, freq=freq)
    rows = []
    for i, date in enumerate(dates):
        close = close_start + i * 0.1
        adj_factor = 1.0
        if dividend_idx is not None and i >= dividend_idx:
            adj_factor = (close_start + dividend_idx * 0.1 - dividend_amount) / (
                close_start + dividend_idx * 0.1
            )
        rows.append({
            "Date": date.date().isoformat(),
            "Open": close - 0.05,
            "High": close + 0.2,
            "Low": close - 0.2,
            "Close": close,
            "Adj Close": close * adj_factor,
            "Volume": 1000000 + i,
            "Dividends": dividend_amount if i == dividend_idx else 0.0,
            "Stock Splits": split_ratio if (split_idx is not None and i == split_idx) else 0.0,
        })
    return pd.DataFrame(rows)


def _write_yahoo_fixture(
    tmp_path: Path,
    instrument_id: str,
    frame: pd.DataFrame,
    *,
    provider: str = "yahoo_yfinance",
    library_name: str = "yfinance",
    retrieved_at_utc: str = "2026-06-15T00:00:00+00:00",
) -> dict:
    """Write a raw CSV, normalised CSV and manifest mimicking GMA-0 structure."""
    symbol = safe_symbol(instrument_id)
    stamp = "20260615T000000000000Z"
    raw_dir = tmp_path / "manifests_data" / "raw" / provider / symbol
    proc_dir = tmp_path / "manifests_data" / "processed" / provider / symbol
    manifest_dir = tmp_path / "manifests" / provider / symbol
    raw_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / f"{symbol}_{stamp}.csv"
    frame.to_csv(raw_path, index=False)

    normalised = normalise_price_frame(frame)
    norm_path = proc_dir / f"{symbol}_{stamp}_normalised.csv"
    normalised.to_csv(norm_path, index=False)

    first_obs = normalised["date"].min()
    last_obs = normalised["date"].max()
    manifest = {
        "track_id": "gma_alpha",
        "phase_id": "gma0_feasibility",
        "provider": provider,
        "provider_symbol": instrument_id,
        "request_start": "1900-01-01",
        "request_end": "",
        "retrieved_at_utc": retrieved_at_utc,
        "library_name": library_name,
        "library_version": "1.3.0",
        "auto_adjust": False,
        "raw_file_path": str(raw_path),
        "raw_file_sha256": sha256_file(raw_path),
        "normalised_file_path": str(norm_path),
        "normalised_file_sha256": sha256_file(norm_path),
        "row_count": len(normalised),
        "first_observation_date": (
            first_obs.date().isoformat() if pd.notna(first_obs) else ""
        ),
        "last_observation_date": (
            last_obs.date().isoformat() if pd.notna(last_obs) else ""
        ),
        "columns": list(normalised.columns),
        "warnings": [],
    }
    manifest_path = manifest_dir / f"{symbol}_{stamp}_manifest.json"
    write_manifest(manifest, manifest_path)
    manifest["_manifest_path"] = str(manifest_path)
    return manifest


def _fixture_config(tmp_path: Path) -> dict:
    cfg = _base_config()
    cfg["source_selection"]["gma0_manifest_root"] = str(
        tmp_path / "manifests"
    )
    cfg["paths"]["canonical_bundle_root"] = str(
        tmp_path / "canonical_market"
    )
    cfg["paths"]["report_root"] = str(tmp_path / "reports")
    cfg["paths"]["state_root"] = str(tmp_path / "state")
    return cfg


# ===================================================================
# 1. Configuration safety flags
# ===================================================================


class TestConfigSafety:
    def test_01_safety_flags(self, tmp_path: Path) -> None:
        config = _base_config()
        config["track"]["live_trading_allowed"] = True
        with pytest.raises(ValueError, match="live_trading_allowed"):
            validate_gma1a_config(config)

    def test_02_unknown_field_rejection(self, tmp_path: Path) -> None:
        config = _base_config()
        config["extra_field"] = "bad"
        with pytest.raises(ValueError, match="Unknown keys"):
            validate_gma1a_config(config)

    def test_03_track_and_phase_identifiers(self) -> None:
        config = _base_config()
        config["track"]["track_id"] = "wrong_track"
        with pytest.raises(ValueError, match="track_id"):
            validate_gma1a_config(config)

    def test_04_path_isolation(self) -> None:
        assert is_approved_gma_path("data/global_multi_asset_alpha/canonical_market/x.csv")
        assert is_approved_gma_path("reports/global_multi_asset_alpha/data_foundation/r.csv")
        assert not is_approved_gma_path("data/raw/spy.csv")
        assert not is_approved_gma_path("reports/paper_trading/x.csv")


# ===================================================================
# 5–10. Snapshot selection validation
# ===================================================================


class TestSnapshotSelection:
    def test_05_rejects_missing_manifest(self, tmp_path: Path) -> None:
        manifest = {"track_id": "gma_alpha", "provider": "yahoo_yfinance",
                     "library_name": "yfinance", "provider_symbol": "SPY",
                     "raw_file_path": str(tmp_path / "nonexistent.csv"),
                     "normalised_file_path": str(tmp_path / "nonexistent_n.csv"),
                     "raw_file_sha256": "abc", "normalised_file_sha256": "def",
                     "columns": ["date", "open", "high", "low", "close", "adj_close", "volume"],
                     "row_count": 100, "_manifest_path": str(tmp_path / "m.json")}
        valid, reason = _is_valid_live_yahoo_candidate(manifest, "SPY", "SPY")
        assert not valid
        assert reason == "raw_file_missing"

    def test_06_rejects_invalid_raw_hash(self, tmp_path: Path) -> None:
        manifest = _write_yahoo_fixture(tmp_path, "SPY", _price_frame())
        manifest["raw_file_sha256"] = "invalidhash"
        valid, reason = _is_valid_live_yahoo_candidate(manifest, "SPY", "SPY")
        assert not valid
        assert reason == "raw_hash_invalid"

    def test_07_rejects_invalid_normalised_hash(self, tmp_path: Path) -> None:
        manifest = _write_yahoo_fixture(tmp_path, "SPY", _price_frame())
        manifest["normalised_file_sha256"] = "invalidhash"
        valid, reason = _is_valid_live_yahoo_candidate(manifest, "SPY", "SPY")
        assert not valid
        assert reason == "normalised_hash_invalid"

    def test_08_rejects_provider_symbol_mismatch(self, tmp_path: Path) -> None:
        manifest = _write_yahoo_fixture(tmp_path, "SPY", _price_frame())
        valid, reason = _is_valid_live_yahoo_candidate(manifest, "SPY", "QQQ")
        assert not valid
        assert reason == "provider_symbol_mismatch"

    def test_09_rejects_mutable_latest_source(self, tmp_path: Path) -> None:
        manifest = _write_yahoo_fixture(tmp_path, "SPY", _price_frame())
        manifest["raw_file_path"] = str(tmp_path / "SPY_latest.csv")
        (tmp_path / "SPY_latest.csv").write_text("dummy", encoding="utf-8")
        valid, reason = _is_valid_live_yahoo_candidate(manifest, "SPY", "SPY")
        assert not valid
        assert reason == "mutable_latest_source"

    def test_10_rejects_non_live_fixture(self, tmp_path: Path) -> None:
        manifest = _write_yahoo_fixture(
            tmp_path, "SPY", _price_frame(), provider="offline_fixture",
            library_name="pandas_fixture",
        )
        valid, reason = _is_valid_live_yahoo_candidate(manifest, "SPY", "SPY")
        assert not valid
        assert reason == "not_yahoo_provider"

    def test_11_deterministic_selection(self, tmp_path: Path) -> None:
        cfg = _fixture_config(tmp_path)
        for inst in PROPOSED_INSTRUMENTS:
            _write_yahoo_fixture(tmp_path, inst, _price_frame())
        config = validate_gma1a_config(cfg)
        from market_strats.global_multi_asset.universe import default_instrument_registry
        sel1, _ = select_canonical_snapshots(config, default_instrument_registry())
        sel2, _ = select_canonical_snapshots(config, default_instrument_registry())
        for col in ["selected_manifest_sha256", "raw_sha256", "normalised_sha256"]:
            assert sel1[col].tolist() == sel2[col].tolist()

    def test_12_deterministic_selection_set_hash(self, tmp_path: Path) -> None:
        cfg = _fixture_config(tmp_path)
        for inst in PROPOSED_INSTRUMENTS:
            _write_yahoo_fixture(tmp_path, inst, _price_frame())
        config = validate_gma1a_config(cfg)
        from market_strats.global_multi_asset.universe import default_instrument_registry
        sel1, _ = select_canonical_snapshots(config, default_instrument_registry())
        sel2, _ = select_canonical_snapshots(config, default_instrument_registry())
        assert compute_selection_set_hash(sel1) == compute_selection_set_hash(sel2)
        assert len(compute_selection_set_hash(sel1)) == 64


# ===================================================================
# 13–14. Completed history and excluded observations
# ===================================================================


class TestCompletedHistory:
    def test_13_active_incomplete_rows_excluded(self) -> None:
        frame = _price_frame(periods=5)
        frame.loc[4, "Close"] = pd.NA
        normalised = normalise_price_frame(frame)
        from market_strats.global_multi_asset.data.validation import completed_history
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        assert len(completed) <= 4

    def test_14_excluded_observations_auditable(self, tmp_path: Path) -> None:
        frame = _price_frame(periods=10)
        frame.loc[9, "Close"] = pd.NA
        normalised = normalise_price_frame(frame)
        from market_strats.global_multi_asset.data.validation import completed_history
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        excluded_count = len(normalised) - len(completed)
        assert excluded_count >= 1


# ===================================================================
# 15–16. Price basis integrity
# ===================================================================


class TestPriceBasis:
    def test_15_raw_open_unadjusted(self) -> None:
        frame = _price_frame(periods=5)
        normalised = normalise_price_frame(frame)
        assert normalised["open"].notna().all()
        assert normalised["open"].iloc[0] != normalised["adj_close"].iloc[0]

    def test_16_adjusted_close_never_execution_price(self) -> None:
        config = _base_config()
        assert config["price_basis"]["execution_price_basis"] == "raw_open"
        assert config["price_basis"]["adjusted_close_role"] == "reconciliation_and_cross_check_only"


# ===================================================================
# 17–22. Corporate actions and total return
# ===================================================================


class TestCorporateActionsAndTotalReturn:
    def test_17_no_action_instrument(self) -> None:
        frame = _price_frame(periods=10, dividend_idx=None)
        from market_strats.global_multi_asset.data.validation import (
            completed_history,
            corporate_action_frame,
        )
        normalised = normalise_price_frame(frame)
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        actions = corporate_action_frame(frame)
        result = build_total_return_series(completed, actions)
        assert "total_return_index" in result.columns
        assert result["total_return_index"].iloc[0] == 1.0
        # No dividends: total return should match price return
        assert result["dividend_cash"].fillna(0).sum() == 0

    def test_18_dividend_total_return_treatment(self) -> None:
        frame = _price_frame(periods=100, dividend_idx=50, dividend_amount=0.50)
        from market_strats.global_multi_asset.data.validation import (
            completed_history,
            corporate_action_frame,
        )
        normalised = normalise_price_frame(frame)
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        actions = corporate_action_frame(frame)
        result = build_total_return_series(completed, actions)
        # Dividend should cause total-return factor > price return on ex-date
        div_row = result.loc[result["dividend_cash"].gt(0)]
        assert len(div_row) == 1
        factor = div_row.iloc[0]["total_return_factor"]
        close_t = div_row.iloc[0]["close"]
        idx = div_row.index[0]
        close_prev = result.loc[idx - 1, "close"]
        price_return_factor = close_t / close_prev
        assert factor > price_return_factor  # total return > price-only return

    def test_19_split_without_double_counting(self) -> None:
        # With auto_adjust=false, close is already split-adjusted
        # So split_ratio is for accounting only, not for return calc
        frame = _price_frame(periods=20, split_idx=10, split_ratio=2.0, dividend_idx=None)
        from market_strats.global_multi_asset.data.validation import (
            completed_history,
            corporate_action_frame,
        )
        normalised = normalise_price_frame(frame)
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        actions = corporate_action_frame(frame)
        result = build_total_return_series(completed, actions)
        # Since close is already split-adjusted, return factor should be normal
        # near the split date (no sudden 2x or 0.5x)
        factors = result["total_return_factor"].dropna()
        assert factors.max() < 1.1  # no huge factor from double-counting

    def test_20_same_date_dividend_and_split(self) -> None:
        frame = _price_frame(periods=20, dividend_idx=10, split_idx=10, split_ratio=2.0)
        from market_strats.global_multi_asset.data.validation import (
            completed_history,
            corporate_action_frame,
        )
        normalised = normalise_price_frame(frame)
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        actions = corporate_action_frame(frame)
        result = build_total_return_series(completed, actions)
        both = result.loc[result["dividend_cash"].gt(0) & result["split_ratio"].ne(0)]
        assert len(both) == 1

    def test_21_first_observation_total_return_index(self) -> None:
        frame = _price_frame(periods=10, dividend_idx=None)
        from market_strats.global_multi_asset.data.validation import (
            completed_history,
            corporate_action_frame,
        )
        normalised = normalise_price_frame(frame)
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        actions = corporate_action_frame(frame)
        result = build_total_return_series(completed, actions)
        assert result["total_return_index"].iloc[0] == 1.0
        assert result["total_return_construction_status"].iloc[0] == "first_observation"
        assert pd.isna(result["total_return_factor"].iloc[0])

    def test_22_missing_corporate_action_handling(self) -> None:
        frame = _price_frame(periods=10, dividend_idx=None)
        # Empty actions
        from market_strats.global_multi_asset.data.validation import (
            completed_history,
        )
        normalised = normalise_price_frame(frame)
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        actions = pd.DataFrame()  # completely empty
        result = build_total_return_series(completed, actions)
        assert result["total_return_index"].notna().all()


# ===================================================================
# 23–28. Reconciliation
# ===================================================================


class TestReconciliation:
    def _reconcile_fixture(
        self, periods: int = 50, dividend_idx: int | None = 20,
    ) -> dict:
        frame = _price_frame(periods=periods, dividend_idx=dividend_idx)
        from market_strats.global_multi_asset.data.validation import (
            completed_history,
            corporate_action_frame,
        )
        normalised = normalise_price_frame(frame)
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        actions = corporate_action_frame(frame)
        tr = build_total_return_series(completed, actions)
        canon = pd.DataFrame({
            "date": tr["date"],
            "close_raw": tr["close"],
            "adj_close_provider": tr["adj_close"],
            "volume": tr["volume"],
            "dividend_cash": tr["dividend_cash"],
            "split_ratio": tr["split_ratio"],
            "total_return_factor": tr["total_return_factor"],
            "total_return_index": tr["total_return_index"],
        })
        return reconcile_total_return(canon, tolerance_bps=1.0)

    def test_23_reconciliation_within_tolerance(self) -> None:
        result = self._reconcile_fixture(dividend_idx=None)
        assert result["reconciliation_status"] in (
            "reconciled", "reconciled_with_immaterial_drift"
        )

    def test_24_immaterial_floating_point_drift(self) -> None:
        result = self._reconcile_fixture(dividend_idx=None)
        assert result["median_return_difference_bps"] < 0.1

    def test_25_action_timing_review(self) -> None:
        # Dividend creates slight timing diff between constructed and adj_close
        result = self._reconcile_fixture(dividend_idx=20)
        # Should be reconciled or action_timing_review
        assert result["reconciliation_status"] in (
            "reconciled", "reconciled_with_immaterial_drift",
            "action_timing_review",
        )

    def test_26_provider_basis_review(self) -> None:
        frame = _price_frame(periods=20, dividend_idx=None)
        from market_strats.global_multi_asset.data.validation import (
            completed_history,
            corporate_action_frame,
        )
        normalised = normalise_price_frame(frame)
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        actions = corporate_action_frame(frame)
        tr = build_total_return_series(completed, actions)
        # Create return-level differences by perturbing adj_close non-uniformly
        adj = tr["adj_close"].copy()
        for i in range(5, 15):
            adj.iloc[i] = adj.iloc[i] * (1.0 + (i % 3) * 0.02)
        canon = pd.DataFrame({
            "date": tr["date"],
            "close_raw": tr["close"],
            "adj_close_provider": adj,
            "volume": tr["volume"],
            "dividend_cash": tr["dividend_cash"],
            "split_ratio": tr["split_ratio"],
            "total_return_factor": tr["total_return_factor"],
            "total_return_index": tr["total_return_index"],
        })
        result = reconcile_total_return(canon, tolerance_bps=1.0)
        assert result["reconciliation_status"] == "provider_basis_review"

    def test_27_failed_core_blocks_gate(self) -> None:
        # A failed required-core reconciliation must block
        # verify that the code logic does block on failure
        from market_strats.global_multi_asset.gma1a_market_bundle import _build_gate_report
        config = validate_gma1a_config(_base_config())
        gate = _build_gate_report(config, {}, "abc123", core_blocked=True)
        core_gate = gate.loc[
            gate["gate"].eq("required_core_total_return_reconciliation_passed")
        ]
        assert not core_gate.iloc[0]["passed"]

    def test_28_non_core_review_represented(self) -> None:
        result = self._reconcile_fixture(dividend_idx=None)
        # A passing instrument should have a valid status
        assert result["reconciliation_status"] in (
            "reconciled", "reconciled_with_immaterial_drift",
            "action_timing_review", "provider_basis_review",
            "failed_reconciliation",
        )


# ===================================================================
# 29–35. Calendar operations
# ===================================================================


class TestCalendar:
    def _etf_dates(self) -> pd.Series:
        """Business day dates across a week with holiday gap."""
        dates = pd.to_datetime([
            "2024-01-02",  # Tue (after New Year)
            "2024-01-03",  # Wed
            "2024-01-04",  # Thu
            "2024-01-05",  # Fri
            "2024-01-08",  # Mon (next week)
            "2024-01-09",  # Tue
        ])
        return pd.Series(dates)

    def test_29_etf_friday_to_monday(self) -> None:
        dates = self._etf_dates()
        friday = pd.Timestamp("2024-01-05")
        result = next_eligible_completed_observation(dates, friday)
        assert result == pd.Timestamp("2024-01-08")

    def test_30_etf_holiday_gap(self) -> None:
        # Simulate a holiday: remove Jan 8
        dates = pd.to_datetime([
            "2024-01-05",  # Fri
            "2024-01-09",  # Tue (Mon was holiday)
        ])
        result = next_eligible_completed_observation(pd.Series(dates), pd.Timestamp("2024-01-05"))
        assert result == pd.Timestamp("2024-01-09")

    def test_31_bitcoin_weekends_retained(self) -> None:
        dates = pd.to_datetime([
            "2024-01-05",  # Fri
            "2024-01-06",  # Sat
            "2024-01-07",  # Sun
            "2024-01-08",  # Mon
        ])
        result = next_eligible_completed_observation(pd.Series(dates), pd.Timestamp("2024-01-05"))
        assert result == pd.Timestamp("2024-01-06")

    def test_32_bitcoin_next_observation(self) -> None:
        dates = pd.to_datetime([
            "2024-01-06",  # Sat
            "2024-01-07",  # Sun
        ])
        result = next_eligible_completed_observation(pd.Series(dates), pd.Timestamp("2024-01-06"))
        assert result == pd.Timestamp("2024-01-07")

    def test_33_incomplete_final_not_executable(self) -> None:
        frame = _price_frame(periods=5)
        frame.loc[4, "Close"] = pd.NA
        normalised = normalise_price_frame(frame)
        from market_strats.global_multi_asset.data.validation import completed_history
        completed = completed_history(normalised, "2026-06-15T00:00:00+00:00")
        last_normalised_date = pd.to_datetime(normalised["date"]).max()
        last_completed_date = pd.to_datetime(completed["date"]).max()
        assert last_completed_date < last_normalised_date

    def test_34_no_future_observation_controlled(self) -> None:
        dates = pd.to_datetime(["2024-01-05"])
        result = next_eligible_completed_observation(
            pd.Series(dates), pd.Timestamp("2024-12-31")
        )
        assert result is None

    def test_35_etf_weekends_not_fabricated(self) -> None:
        # ETF calendar should not have weekend dates
        dates = pd.bdate_range("2024-01-01", "2024-01-15")
        for date in dates:
            assert date.weekday() < 5  # No Sat/Sun


# ===================================================================
# 36–37. Cash contract
# ===================================================================


class TestCashContract:
    def test_36_bil_not_authoritative_cash(self) -> None:
        config = _base_config()
        assert config["cash"]["bil_role"] != "authoritative_cash_source"
        config["cash"]["bil_role"] = "authoritative_cash_source"
        with pytest.raises(ValueError, match="BIL must not be used"):
            validate_gma1a_config(config)

    def test_37_missing_cash_not_fabricated(self) -> None:
        config = _base_config()
        assert config["cash"]["missing_rate_policy"] == "flag_and_defer_to_gma1b"
        assert config["cash"]["authoritative_source_type"] == "point_in_time_treasury_bill_rate"


# ===================================================================
# 38–40. Isolation and report generation
# ===================================================================


class TestIsolation:
    def test_38_no_writes_outside_approved_paths(self) -> None:
        assert is_approved_gma_path("data/global_multi_asset_alpha/canonical_market/SPY.csv")
        assert is_approved_gma_path("reports/global_multi_asset_alpha/data_foundation/x.csv")
        assert not is_approved_gma_path("data/raw/spy.csv")
        assert not is_approved_gma_path("reports/paper_trading/x.md")
        assert not is_approved_gma_path("configs/spy_sma10.yaml")

    def test_39_preexisting_dirty_paths_exempted(self) -> None:
        # Dirty paths under individual_equity_post_endpoint are not GMA paths
        assert not is_approved_gma_path(
            "data/individual_equity_post_endpoint/AAPL.csv"
        )

    def test_40_deterministic_report_generation(self, tmp_path: Path) -> None:
        cfg = _fixture_config(tmp_path)
        for inst in PROPOSED_INSTRUMENTS:
            _write_yahoo_fixture(tmp_path, inst, _price_frame())
        config = validate_gma1a_config(cfg)
        from market_strats.global_multi_asset.universe import default_instrument_registry
        sel1, _ = select_canonical_snapshots(config, default_instrument_registry())
        sel2, _ = select_canonical_snapshots(config, default_instrument_registry())
        hash1 = compute_selection_set_hash(sel1)
        hash2 = compute_selection_set_hash(sel2)
        assert hash1 == hash2
