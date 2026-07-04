from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from market_strats.global_multi_asset import gma7b_etf_feature_store as gma7b


def _prices_for(ticker_index: int, periods: int) -> list[float]:
    return [50.0 + ticker_index * 3.0 + i * (0.05 + ticker_index * 0.002) for i in range(periods)]


def _write_gma7a_inputs(repo_root: Path, symbols: list[str] | None = None) -> None:
    symbols = symbols or gma7b.CORE_22_UNIVERSE
    config = {
        "phase_id": "gma7a_predictive_ensemble_contract_v1",
        "universe": {"cohort_id": gma7b.ACTIVE_COHORT, "symbols": symbols},
    }
    config_path = (
        repo_root / "configs/global_multi_asset_alpha/gma7a_predictive_ensemble_contract_v1.yaml"
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    lock = {
        "active_cohorts": [gma7b.ACTIVE_COHORT],
        "core22_universe_hash": gma7b.core22_universe_hash(symbols),
    }
    lock_path = (
        repo_root / "reports/global_multi_asset_alpha/gma7a_predictive_ensemble_lock_v1.json"
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, sort_keys=True), encoding="utf-8")


def _write_snapshot(
    root: Path,
    *,
    symbols: list[str] | None = None,
    periods: int = 330,
) -> tuple[Path, gma7b.FrozenHashExpectations, pd.DatetimeIndex]:
    symbols = symbols or gma7b.CORE_22_UNIVERSE
    snapshot = root / "snapshot"
    bundle = snapshot / "reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1"
    dates = pd.bdate_range("2019-01-02", periods=periods)
    hash_rows = []
    for ticker_index, ticker in enumerate(symbols):
        ticker_dir = bundle / "normalised/yahoo_yfinance" / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        path = ticker_dir / f"{ticker}_synthetic_normalised.csv"
        values = _prices_for(ticker_index, periods)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["date", "open", "high", "low", "close", "adj_close", "volume"],
                lineterminator="\n",
            )
            writer.writeheader()
            for idx, session in enumerate(dates):
                price = values[idx]
                writer.writerow(
                    {
                        "date": session.date().isoformat(),
                        "open": price,
                        "high": price,
                        "low": price,
                        "close": price,
                        "adj_close": price,
                        "volume": 1000,
                    }
                )
        hash_rows.append({"ticker": ticker, "normalised_series_file_hash": gma7b.sha256_file(path)})
    inventory = bundle / "gma6b_normalised_file_hashes_v1.csv"
    with inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ticker", "normalised_series_file_hash"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(hash_rows)
    normalised_hash = gma7b.sha256_file(inventory)
    manifest_path = bundle / "gma6b_data_bundle_manifest_v1.json"
    manifest_path.write_text(
        json.dumps(
            {
                "normalised_file_hashes_hash": normalised_hash,
                "requested_start_date": dates[0].date().isoformat(),
                "requested_end_date": dates[-1].date().isoformat(),
                "requested_tickers": symbols,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot_manifest = snapshot / "gma6_v1_evidence_snapshot_manifest_v1.csv"
    snapshot_manifest.write_text("relative_path,sha256\nsynthetic,synthetic\n", encoding="utf-8")
    expectations = gma7b.FrozenHashExpectations(
        gma6_snapshot_manifest_sha256=gma7b.sha256_file(snapshot_manifest),
        gma6b_data_bundle_manifest_hash=gma7b.sha256_file(manifest_path),
        normalised_bundle_hash=normalised_hash,
    )
    return snapshot, expectations, dates


def _generate(tmp_path: Path, periods: int = 330) -> tuple[pd.DataFrame, dict[str, object]]:
    _write_gma7a_inputs(tmp_path)
    snapshot, expectations, _ = _write_snapshot(tmp_path, periods=periods)
    result = gma7b.generate_feature_store_files(
        tmp_path,
        snapshot_root=snapshot,
        expectations=expectations,
    )
    features = pd.read_csv(result.output_paths["features"])
    return features, result.manifest


def test_only_gma7a_core22_universe_is_accepted(tmp_path: Path):
    bad = gma7b.CORE_22_UNIVERSE + ["VNQ"]
    _write_gma7a_inputs(tmp_path, bad)
    with pytest.raises(gma7b.GMA7BFeatureStoreError):
        gma7b.load_and_validate_gma7a_contract(tmp_path)


def test_ticker_order_is_exact(tmp_path: Path):
    bad = list(gma7b.CORE_22_UNIVERSE)
    bad[0], bad[1] = bad[1], bad[0]
    _write_gma7a_inputs(tmp_path, bad)
    with pytest.raises(gma7b.GMA7BFeatureStoreError, match="ticker order"):
        gma7b.load_and_validate_gma7a_contract(tmp_path)


def test_bil_is_context_reference_not_prediction_row(tmp_path: Path):
    features, manifest = _generate(tmp_path)
    assert "BIL" not in set(features["asset_ticker"])
    assert set(features["asset_ticker"]) == set(gma7b.PREDICTION_ASSETS)
    assert manifest["prediction_asset_count"] == 21


def test_features_use_decision_or_prior_sessions_only(tmp_path: Path):
    features, _ = _generate(tmp_path)
    snapshot = tmp_path / "snapshot"
    verification = gma7b.verify_frozen_inputs(
        snapshot,
        gma7b.FrozenHashExpectations(
            gma6_snapshot_manifest_sha256=gma7b.sha256_file(
                snapshot / "gma6_v1_evidence_snapshot_manifest_v1.csv"
            ),
            gma6b_data_bundle_manifest_hash=gma7b.sha256_file(
                snapshot
                / "reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1/gma6b_data_bundle_manifest_v1.json"
            ),
            normalised_bundle_hash=gma7b.sha256_file(
                snapshot
                / "reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1/gma6b_normalised_file_hashes_v1.csv"
            ),
        ),
    )
    prices = gma7b.load_adjusted_price_panel(verification)
    row = features[features["asset_ticker"] == "SPY"].iloc[0]
    session = pd.Timestamp(row["decision_session_date"])
    position = prices.index.get_loc(session)
    expected = prices.loc[session, "SPY"] / prices.iloc[position - 21]["SPY"] - 1.0
    assert row["return_21d"] == pytest.approx(expected)


def test_next_tradable_session_is_execution_and_target_start_metadata(tmp_path: Path):
    features, _ = _generate(tmp_path)
    decision_dates = sorted(features["decision_session_date"].unique())
    row = features[features["decision_session_date"] == decision_dates[0]].iloc[0]
    assert row["earliest_execution_session_date"] == row["target_start_session_date"]
    assert pd.Timestamp(row["earliest_execution_session_date"]) > pd.Timestamp(
        row["decision_session_date"]
    )


def test_no_future_return_target_or_model_output_columns_are_emitted(tmp_path: Path):
    features, _ = _generate(tmp_path)
    forbidden = [
        column
        for column in features.columns
        if any(fragment in column.lower() for fragment in gma7b.FORBIDDEN_COLUMN_FRAGMENTS)
        and column != "is_prediction_asset"
    ]
    assert forbidden == []
    assert "forward_label_window_available" in features.columns


def test_252_session_availability_is_required_before_rows_emit(tmp_path: Path):
    _write_gma7a_inputs(tmp_path)
    snapshot, expectations, _ = _write_snapshot(tmp_path, periods=240)
    with pytest.raises(gma7b.GMA7BFeatureStoreError, match="No feature rows"):
        gma7b.generate_feature_store_files(
            tmp_path, snapshot_root=snapshot, expectations=expectations
        )


def test_exact_feature_dictionary_is_enforced():
    rows = gma7b.feature_dictionary_rows()
    assert [row["feature_name"] for row in rows] == gma7b.FEATURE_COLUMNS
    assert "forward_label_window_available" not in [row["feature_name"] for row in rows]


def test_cross_sectional_ranks_use_21_prediction_assets(tmp_path: Path):
    features, _ = _generate(tmp_path)
    date = sorted(features["decision_session_date"].unique())[0]
    one_date = features[features["decision_session_date"] == date]
    assert len(one_date) == 21
    assert one_date["cross_section_rank_return_63d"].max() == pytest.approx(1.0)
    assert one_date["cross_section_rank_return_63d"].min() == pytest.approx(0.0)


def test_repeated_context_features_match_across_prediction_assets(tmp_path: Path):
    features, _ = _generate(tmp_path)
    date = sorted(features["decision_session_date"].unique())[0]
    one_date = features[features["decision_session_date"] == date]
    for column in gma7b.CONTEXT_FEATURE_COLUMNS:
        assert one_date[column].nunique() == 1


def test_frozen_snapshot_hash_mismatch_fails_closed(tmp_path: Path):
    _write_gma7a_inputs(tmp_path)
    snapshot, expectations, _ = _write_snapshot(tmp_path)
    bad = gma7b.FrozenHashExpectations(
        gma6_snapshot_manifest_sha256="0" * 64,
        gma6b_data_bundle_manifest_hash=expectations.gma6b_data_bundle_manifest_hash,
        normalised_bundle_hash=expectations.normalised_bundle_hash,
    )
    with pytest.raises(gma7b.GMA7BFeatureStoreError, match="snapshot manifest hash"):
        gma7b.verify_frozen_inputs(snapshot, bad)


def test_no_data_provider_model_strategy_replay_allocation_or_live_imports():
    source = Path(gma7b.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = [
        "yfinance",
        "price_provider",
        "gma4_tournament",
        "gma4_replay_adapter",
        "strategy",
        "replay",
        "allocation",
        "paper",
        "broker",
        "live",
    ]
    assert not any(any(fragment in module for fragment in forbidden) for module in imported)


def test_generation_is_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    features_a, manifest_a = _generate(first)
    features_b, manifest_b = _generate(second)
    assert features_a.to_csv(index=False) == features_b.to_csv(index=False)
    assert manifest_a == manifest_b
