from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from market_strats.global_multi_asset.availability_audit import (
    _snapshot_reproducibility_audit,
    run_gma0_availability_audit,
)
from market_strats.global_multi_asset.cli import main as gma_main
from market_strats.global_multi_asset.config import load_config, validate_config
from market_strats.global_multi_asset.data.manifests import sha256_structured
from market_strats.global_multi_asset.data.price_provider import OfflineFixtureProvider
from market_strats.global_multi_asset.data.validation import (
    liquidity_audit,
    validate_price_frame,
)
from market_strats.global_multi_asset.universe import (
    PROPOSED_INSTRUMENTS,
    default_instrument_registry,
)


def _base_config(tmp_path: Path) -> dict:
    return {
        "track": {
            "track_id": "gma_alpha",
            "phase_id": "gma0_feasibility",
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        },
        "paths": {
            "raw_root": "data/global_multi_asset_alpha/raw",
            "processed_root": "data/global_multi_asset_alpha/processed",
            "manifest_root": "data/global_multi_asset_alpha/manifests",
            "report_root": "reports/global_multi_asset_alpha/feasibility",
            "cache_root": "data/global_multi_asset_alpha/cache/yfinance",
        },
        "provider": {
            "name": "yahoo_yfinance",
            "fetch_enabled": True,
            "immutable_snapshots": True,
            "auto_adjust": False,
            "timeout_seconds": 10,
        },
        "audit": {
            "expected_price_columns": ["date", "open", "high", "low", "close", "adj_close", "volume"],
            "minimum_history_observations": 20,
            "momentum_warmup_months": 12,
            "require_raw_open": True,
            "require_adjusted_close": True,
            "require_volume": True,
            "stale_price_threshold_days": 3,
            "zero_volume_threshold_days": 2,
            "hash_algorithm": "sha256",
        },
        "replay_start": {
            "required_core_instruments": ["SPY", "QQQ"],
            "minimum_warmup_months": 12,
            "provisional_first_signal_rule": "fixture_test",
            "provisional_execution_rule": "next_open",
            "benchmark_exemptions": ["SPY Buy & Hold", "ACWI Buy & Hold", "fixed 60/40 benchmark"],
            "draft_governance_notes": ["draft only"],
        },
        "instruments": {instrument: {} for instrument in PROPOSED_INSTRUMENTS},
    }


def _write_config(tmp_path: Path, config: dict | None = None) -> Path:
    path = tmp_path / "configs" / "global_multi_asset_alpha" / "gma0_feasibility.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config or _base_config(tmp_path), sort_keys=False), encoding="utf-8")
    return path


def _price_frame(start: str = "2020-01-01", periods: int = 330, *, freq: str = "B") -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq=freq)
    rows = []
    for index, date in enumerate(dates):
        close = 100.0 + index * 0.1
        rows.append(
            {
                "Date": date.date().isoformat(),
                "Open": close - 0.1,
                "High": close + 0.2,
                "Low": close - 0.2,
                "Close": close,
                "Adj Close": close,
                "Volume": 1000 + index,
                "Dividends": 0.01 if index == 10 else 0.0,
                "Stock Splits": 0.0,
            }
        )
    return pd.DataFrame(rows)


def _write_fixtures(
    fixture_dir: Path,
    *,
    btc_start: str = "2021-01-01",
    periods: int = 330,
) -> None:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    for instrument in PROPOSED_INSTRUMENTS:
        start = btc_start if instrument == "BTC-USD" else "2020-01-01"
        freq = "D" if instrument == "BTC-USD" else "B"
        _price_frame(start, periods, freq=freq).to_csv(fixture_dir / f"{instrument}.csv", index=False)


def _write_fixture(fixture_dir: Path, instrument: str, frame: pd.DataFrame) -> None:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(fixture_dir / f"{instrument}.csv", index=False)


def _reproducibility_after_two_spy_snapshots(
    tmp_path: Path,
    first: pd.DataFrame,
    second: pd.DataFrame,
) -> pd.Series:
    fixture_dir = tmp_path / "fixtures"
    provider = OfflineFixtureProvider(
        fixture_dir=fixture_dir,
        raw_root=Path("data/global_multi_asset_alpha/raw"),
        processed_root=Path("data/global_multi_asset_alpha/processed"),
        manifest_root=Path("data/global_multi_asset_alpha/manifests"),
    )
    _write_fixture(fixture_dir, "SPY", first)
    provider.fetch("SPY", start="1900-01-01", end="")
    _write_fixture(fixture_dir, "SPY", second)
    provider.fetch("SPY", start="1900-01-01", end="")
    audit = _snapshot_reproducibility_audit(Path("data/global_multi_asset_alpha/manifests"))
    return audit.loc[audit["provider_symbol"].eq("SPY")].iloc[0]


def _validate(raw: pd.DataFrame):
    return validate_price_frame(
        raw=raw,
        instrument_id="SPY",
        retrieved_at_utc="2026-06-15T00:00:00+00:00",
        stale_price_threshold_days=3,
        minimum_history_observations=2,
    )


def test_configuration_safety_flags_and_ids(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["track"]["live_trading_allowed"] = True
    with pytest.raises(ValueError, match="live_trading_allowed"):
        validate_config(config)


def test_unknown_instrument_rejection(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["instruments"]["NOT_REAL"] = {}
    with pytest.raises(ValueError, match="Unknown GMA instruments"):
        validate_config(config)


def test_registry_uniqueness_and_proxy_groups() -> None:
    registry = default_instrument_registry()
    assert len({entry["provider_symbol"] for entry in registry.values()}) == len(registry)
    assert registry["EEM"]["alternative_proxy_group"] == registry["VWO"]["alternative_proxy_group"]
    assert registry["DBC"]["alternative_proxy_group"] == registry["DBA"]["alternative_proxy_group"]
    assert registry["EEM"]["is_primary_implementation"]
    assert not registry["VWO"]["is_primary_implementation"]


def test_path_isolation_rejects_non_gma_paths(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["paths"]["report_root"] = "reports/paper_trading"
    with pytest.raises(ValueError, match="report_root"):
        validate_config(config)


def test_immutable_snapshot_naming_and_manifest_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    _write_fixtures(fixture_dir)
    provider = OfflineFixtureProvider(
        fixture_dir=fixture_dir,
        raw_root=Path("data/global_multi_asset_alpha/raw"),
        processed_root=Path("data/global_multi_asset_alpha/processed"),
        manifest_root=Path("data/global_multi_asset_alpha/manifests"),
    )
    first = provider.fetch("SPY", start="1900-01-01", end="")
    second = provider.fetch("SPY", start="1900-01-01", end="")
    assert first.raw_file_path != second.raw_file_path
    assert first.manifest_path.exists()


def test_deterministic_sha256_for_structured_manifest_values() -> None:
    left = {"b": [2, 1], "a": "x"}
    right = {"a": "x", "b": [2, 1]}
    assert sha256_structured(left) == sha256_structured(right)


def test_duplicate_dates_are_reported() -> None:
    raw = _price_frame(periods=5)
    raw.loc[1, "Date"] = raw.loc[0, "Date"]
    result = _validate(raw)
    assert result.audit["duplicate_dates"]


def test_unsorted_dates_are_reported() -> None:
    raw = _price_frame(periods=5).iloc[[1, 0, 2, 3, 4]].reset_index(drop=True)
    result = _validate(raw)
    assert result.audit["out_of_order_dates"]


def test_missing_interior_ohlcv_is_reported() -> None:
    raw = _price_frame(periods=5)
    raw.loc[2, "Close"] = pd.NA
    result = _validate(raw)
    assert result.audit["missing_interior_data"]


def test_trailing_incomplete_rows_are_reported() -> None:
    raw = _price_frame(periods=5)
    raw.loc[4, "Close"] = pd.NA
    result = _validate(raw)
    assert result.audit["trailing_incomplete_rows"]


def test_non_positive_prices_are_reported() -> None:
    raw = _price_frame(periods=5)
    raw.loc[2, "Close"] = 0
    result = _validate(raw)
    assert result.audit["non_positive_prices"]


def test_negative_volume_is_reported() -> None:
    raw = _price_frame(periods=5)
    raw.loc[2, "Volume"] = -1
    result = _validate(raw)
    assert result.audit["negative_volume"]


def test_zero_volume_and_stale_close_streaks_are_calculated() -> None:
    raw = _price_frame(periods=6)
    raw.loc[1:3, "Volume"] = 0
    raw.loc[1:3, "Close"] = raw.loc[0, "Close"]
    result = _validate(raw)
    liquidity = liquidity_audit(result.completed, "SPY")
    assert liquidity["longest_zero_volume_streak"] == 3
    assert liquidity["longest_stale_close_streak"] >= 3


def test_missing_raw_open_and_adjusted_close_are_reported() -> None:
    raw = _price_frame(periods=5)
    raw = raw.drop(columns=["Open", "Adj Close"])
    result = _validate(raw)
    assert result.audit["unavailable_raw_open"]
    assert result.audit["unavailable_adjusted_close"]


def test_etf_and_bitcoin_calendar_handling_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = _write_config(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    _write_fixtures(fixture_dir, btc_start="2021-01-01")
    config = load_config(config_path)
    result = run_gma0_availability_audit(config=config, offline_fixtures=fixture_dir)
    availability = pd.read_csv(result.outputs["price_availability"])
    assert availability.loc[availability["instrument_id"].eq("SPY"), "expected_calendar"].iloc[0] == "us_listed_etf"
    assert availability.loc[availability["instrument_id"].eq("BTC-USD"), "expected_calendar"].iloc[0] == "bitcoin_utc_daily"


def test_warmup_next_open_and_bitcoin_not_delaying_core_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = _write_config(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    _write_fixtures(fixture_dir, btc_start="2022-01-01", periods=500)
    result = run_gma0_availability_audit(config=load_config(config_path), offline_fixtures=fixture_dir)
    replay = result.replay_start.iloc[0]
    assert replay["earliest_common_core_signal_date"] < replay["earliest_bitcoin_eligible_date"]
    assert not bool(replay["bitcoin_delays_core_start"])
    assert replay["earliest_core_next_open_execution_date"] > replay["earliest_common_core_signal_date"]


def test_benchmark_only_excluded_from_core_common_date(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["replay_start"]["required_core_instruments"] = ["SPY", "ACWI"]
    with pytest.raises(ValueError, match="Benchmark-only"):
        validate_config(config)


def test_missing_required_core_instrument_fails_config(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["replay_start"]["required_core_instruments"] = ["SPY", "MISSING"]
    with pytest.raises(ValueError, match="Unknown required core"):
        validate_config(config)


def test_unexpected_write_path_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = _write_config(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    _write_fixtures(fixture_dir)
    result = run_gma0_availability_audit(config=load_config(config_path), offline_fixtures=fixture_dir)
    gate = pd.read_csv(result.outputs["isolation_gate_report"])
    assert gate.loc[gate["gate"].eq("no_frozen_report_or_data_path_written"), "passed"].iloc[0]


def test_deterministic_report_generation_from_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = _write_config(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    _write_fixtures(fixture_dir)
    result = run_gma0_availability_audit(config=load_config(config_path), offline_fixtures=fixture_dir)
    expected = {
        "reuse_map",
        "instrument_registry",
        "price_availability",
        "corporate_action_availability",
        "liquidity_summary",
        "calendar_registry",
        "macro_series_registry",
        "replay_start_assessment",
        "isolation_gate_report",
        "gma0_conclusion",
        "snapshot_reproducibility_audit",
        "gma0r_adjusted_close_reconciliation",
        "gma0r_adjusted_close_reconciliation_md",
    }
    assert expected.issubset(result.outputs)
    assert result.outputs["price_availability"].exists()


def test_gma0r_exact_adjusted_close_match_is_classified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    row = _reproducibility_after_two_spy_snapshots(tmp_path, _price_frame(periods=30), _price_frame(periods=30))
    assert row["reproducibility_classification"] == "exact_match"
    assert row["adj_close_exact_difference_count"] == 0


def test_gma0r_floating_point_noise_is_non_material(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    first = _price_frame(periods=30)
    second = first.copy()
    second.loc[10, "Adj Close"] = second.loc[10, "Adj Close"] + 1e-13
    row = _reproducibility_after_two_spy_snapshots(tmp_path, first, second)
    assert row["reproducibility_classification"] == "numerical_noise_only"
    assert row["adj_close_difference_count_gt_1e_8"] == 0
    assert not bool(row["completed_history_revision_material"])


def test_gma0r_incomplete_final_row_only_difference_is_not_material(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    first = _price_frame(periods=30)
    second = first.copy()
    second.loc[29, "Adj Close"] = pd.NA
    row = _reproducibility_after_two_spy_snapshots(tmp_path, first, second)
    assert row["reproducibility_classification"] == "incomplete_row_only"
    assert bool(row["differences_confined_to_incomplete_rows"])
    assert row["adj_close_exact_difference_count"] == 0


def test_gma0r_material_completed_history_revision_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    first = _price_frame(periods=30)
    second = first.copy()
    second.loc[10, "Close"] = second.loc[10, "Close"] * 1.05
    row = _reproducibility_after_two_spy_snapshots(tmp_path, first, second)
    assert row["reproducibility_classification"] == "material_completed_history_revision"
    assert row["raw_close_exact_difference_count"] == 1
    assert bool(row["material_completed_history_revision"])


def test_gma0r_adjustment_factor_change_is_classified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    first = _price_frame(periods=30)
    second = first.copy()
    second.loc[10, "Adj Close"] = second.loc[10, "Adj Close"] * 0.99
    row = _reproducibility_after_two_spy_snapshots(tmp_path, first, second)
    assert row["reproducibility_classification"] == "corporate_action_adjustment_update"
    assert row["adjustment_factor_exact_difference_count"] == 1
    assert bool(row["corporate_action_adjustment_update"])


def test_gma0r_changed_dividend_event_is_classified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    first = _price_frame(periods=30)
    second = first.copy()
    second.loc[10, "Dividends"] = 0.42
    row = _reproducibility_after_two_spy_snapshots(tmp_path, first, second)
    assert row["reproducibility_classification"] == "corporate_action_adjustment_update"
    assert row["dividend_event_difference_count"] == 1


def test_gma0r_expanded_non_crypto_and_full_allocator_dates_are_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = _write_config(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    _write_fixtures(fixture_dir, btc_start="2022-01-01", periods=500)
    result = run_gma0_availability_audit(config=load_config(config_path), offline_fixtures=fixture_dir)
    replay = pd.read_csv(result.outputs["replay_start_assessment"]).iloc[0]
    assert replay["earliest_expanded_non_crypto_allocator_date"] < replay["earliest_full_allocator_including_bitcoin_date"]
    assert replay["earliest_full_allocator_including_bitcoin_date"] >= replay["earliest_bitcoin_eligible_date"]
    assert bool(replay["legacy_earliest_expanded_universe_date_deprecated"])


def test_gma0r_benchmark_only_acwi_does_not_receive_momentum_warmup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = _write_config(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    _write_fixtures(fixture_dir, periods=500)
    result = run_gma0_availability_audit(config=load_config(config_path), offline_fixtures=fixture_dir)
    availability = pd.read_csv(result.outputs["price_availability"])
    acwi = availability.loc[availability["instrument_id"].eq("ACWI")].iloc[0]
    replay = pd.read_csv(result.outputs["replay_start_assessment"]).iloc[0]
    assert bool(acwi["benchmark_warmup_exempt"])
    assert pd.isna(acwi["warmup_complete_date"])
    assert bool(replay["acwi_benchmark_warmup_exempt"])
    assert replay["earliest_benchmark_comparison_date"] >= acwi["first_return_eligible_date"]


def test_gma0r_warnings_do_not_imply_reduced_universe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = _write_config(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    _write_fixtures(fixture_dir, periods=500)
    bil = pd.read_csv(fixture_dir / "BIL.csv")
    bil.loc[1, "Date"] = bil.loc[0, "Date"]
    bil.to_csv(fixture_dir / "BIL.csv", index=False)
    result = run_gma0_availability_audit(config=load_config(config_path), offline_fixtures=fixture_dir)
    conclusion = result.outputs["gma0_conclusion"].read_text(encoding="utf-8")
    assert result.warnings
    assert result.decision == "gma0_feasible_proceed_to_data_foundation"
    assert "excluded instruments: `none`" in conclusion
    assert "reason for every reduction: `none; no GMA-0R universe reduction was applied`" in conclusion


def test_cli_offline_fixture_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = _write_config(tmp_path)
    fixture_dir = tmp_path / "fixtures"
    _write_fixtures(fixture_dir)
    exit_code = gma_main(
        [
            "--config",
            str(config_path),
            "audit-availability",
            "--offline-fixtures",
            str(fixture_dir),
        ]
    )
    assert exit_code == 0
