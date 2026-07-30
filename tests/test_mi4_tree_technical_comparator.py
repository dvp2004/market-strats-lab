from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from market_strats.intelligence.mi2.technical_baseline import (
    FEATURE_COLUMNS,
    walk_forward_boundaries,
)
from market_strats.intelligence.mi4.tree_technical_comparator import (
    RF_CONSTANTS,
    TREE_MODEL_NAME,
    assert_row_set_equality,
    build_tree_predictions,
    build_tree_scoreboard,
    canonical_row_keys,
    comparison_row_set_hash,
    fixed_random_forest,
    load_asset_family_map,
    prepare_mi4_samples,
    run_mi4_tree_technical_comparator,
    sklearn_preflight_version,
)

ROOT = Path(__file__).resolve().parents[1]


def _tmp(name: str) -> Path:
    path = ROOT / ".pytest_tmp" / f"mi4_{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _sessions(count: int = 220) -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-02", periods=count)


def _registry() -> dict:
    return {
        "walk_forward_and_holdout": {
            "initial_training_fraction": 0.50,
            "test_block_sessions": 20,
            "expanding_window": True,
            "purge_sessions": 20,
            "embargo_sessions": 20,
            "untouched_holdout_fraction": 0.20,
            "holdout_tuning_allowed": False,
        }
    }


def _feature_target_panels(count: int = 220) -> tuple[pd.DataFrame, pd.DataFrame]:
    instruments = ["mi1_etf_spy", "mi1_etf_qqq", "mi1_etf_bil"]
    feature_rows = []
    target_rows = []
    for instrument_index, instrument_id in enumerate(instruments):
        for session_index, session in enumerate(_sessions(count)):
            feature_row = {
                "instrument_id": instrument_id,
                "session_date": session,
                "decision_timestamp_utc": session,
                "availability_evidence_level": "contractual_assumption",
                "feature_available": True,
                "feature_block_reason": "",
                "ticker": instrument_id.upper(),
                "asset_family": "must_not_be_used",
            }
            for feature_index, column in enumerate(FEATURE_COLUMNS):
                feature_row[column] = (
                    0.01 * feature_index
                    + 0.001 * session_index
                    + 0.05 * instrument_index
                    + np.sin(session_index / 17) * 0.001
                )
            feature_rows.append(feature_row)
            raw_signal = feature_row["raw_return_21"] - feature_row["realized_volatility_20"]
            target_rows.append(
                {
                    "instrument_id": instrument_id,
                    "session_date": session,
                    "target_value": raw_signal + 0.01 * instrument_index,
                    "target_available": True,
                    "target_name": "20_trading_session_forward_total_return_excess_vs_BIL",
                }
            )
    return pd.DataFrame(feature_rows), pd.DataFrame(target_rows)


def _mi2_predictions_for_samples(samples: pd.DataFrame, registry: dict) -> pd.DataFrame:
    bounds = walk_forward_boundaries(
        list(pd.Index(samples["session_date"].unique()).sort_values()),
        registry,
    )
    rows = []
    for segment, sessions in {
        "walk_forward_validation": [
            session for block in bounds["blocks"] for session in block["test_sessions"]
        ],
        "untouched_holdout": bounds["holdout_sessions"],
    }.items():
        segment_rows = samples[samples["session_date"].isin(sessions)].copy()
        segment_rows["evaluation_segment"] = segment
        segment_rows["zero_prediction"] = 0.0
        segment_rows["persistence_prediction"] = segment_rows["raw_return_21"]
        segment_rows["prediction"] = segment_rows["target_value"] * 0.9
        segment_rows["model_name"] = "ridge_fixed_alpha_1_0"
        rows.append(
            segment_rows[
                [
                    "instrument_id",
                    "session_date",
                    "target_value",
                    "evaluation_segment",
                    "zero_prediction",
                    "persistence_prediction",
                    "prediction",
                    "model_name",
                ]
            ]
        )
    return pd.concat(rows, ignore_index=True)


def test_sklearn_preflight_version_is_pinned_runtime_version() -> None:
    assert sklearn_preflight_version() == "1.9.0"


def test_fixed_random_forest_constants_are_exact() -> None:
    model = fixed_random_forest()
    assert model.n_estimators == 64
    assert model.max_depth == 3
    assert model.min_samples_leaf == 40
    assert model.max_features == 3
    assert model.bootstrap is True
    assert model.max_samples == 0.70
    assert model.random_state == 20260620
    assert model.n_jobs == 1
    assert model.criterion == "squared_error"
    assert RF_CONSTANTS["max_features"] == 3


def test_deterministic_repeated_predictions_and_no_split_leakage() -> None:
    features, targets = _feature_target_panels()
    samples = prepare_mi4_samples(features, targets)
    first = build_tree_predictions(samples, _registry()).predictions
    second = build_tree_predictions(samples, _registry()).predictions
    pd.testing.assert_series_equal(first[TREE_MODEL_NAME], second[TREE_MODEL_NAME])
    for row in first.drop_duplicates("training_window_id").itertuples(index=False):
        assert row.training_end_session < row.test_start_session
        train_position = list(_sessions()).index(row.training_end_session)
        test_position = list(_sessions()).index(row.test_start_session)
        if row.evaluation_segment == "walk_forward_validation":
            assert (
                test_position - train_position
                > _registry()["walk_forward_and_holdout"]["purge_sessions"]
            )


def test_only_fixed_technical_features_are_used_without_identifier_or_family_leakage() -> None:
    features, targets = _feature_target_panels()
    samples = prepare_mi4_samples(features, targets)
    assert set(FEATURE_COLUMNS).issubset(samples.columns)
    for blocked in ["instrument_id", "session_date", "ticker", "asset_family"]:
        assert blocked not in FEATURE_COLUMNS
    changed = samples.copy()
    changed["ticker"] = "DIFFERENT"
    changed["asset_family"] = "DIFFERENT"
    first = build_tree_predictions(samples, _registry()).predictions[TREE_MODEL_NAME]
    second = build_tree_predictions(changed, _registry()).predictions[TREE_MODEL_NAME]
    pd.testing.assert_series_equal(first, second)


def test_missing_feature_available_values_fail_without_imputation() -> None:
    features, targets = _feature_target_panels()
    features.loc[0, FEATURE_COLUMNS[0]] = np.nan
    with pytest.raises(ValueError, match="incomplete technical features"):
        prepare_mi4_samples(features, targets)


def test_canonical_row_set_hash_is_reproducible() -> None:
    frame = pd.DataFrame(
        {
            "instrument_id": ["b", "a", "a"],
            "session_date": pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-02"]),
        }
    )
    keys = canonical_row_keys(frame)
    assert keys == ["a|2020-01-02", "a|2020-01-03", "b|2020-01-02"]
    assert comparison_row_set_hash(keys) == comparison_row_set_hash(list(keys))


def test_row_set_equality_between_ridge_and_tree_is_required() -> None:
    features, targets = _feature_target_panels()
    samples = prepare_mi4_samples(features, targets)
    tree = build_tree_predictions(samples, _registry()).predictions
    mi2 = _mi2_predictions_for_samples(samples, _registry())
    assert_row_set_equality(mi2, tree)
    with pytest.raises(ValueError, match="row-set equality failure"):
        assert_row_set_equality(mi2.iloc[:-1], tree)


def test_diagnostic_counts_by_instrument_and_asset_family() -> None:
    features, targets = _feature_target_panels()
    samples = prepare_mi4_samples(features, targets)
    tree = build_tree_predictions(samples, _registry())
    predictions = tree.predictions.copy()
    predictions["zero_forward_excess_return"] = 0.0
    predictions["persistence_last_observed_return"] = predictions["target_value"] * 0.1
    predictions["ridge_technical_only_alpha_1_0"] = predictions["target_value"] * 0.8
    predictions["asset_family"] = predictions["instrument_id"].map(
        load_asset_family_map(ROOT / "configs" / "intelligence" / "universe_mi1.yaml")
    )
    scoreboard = build_tree_scoreboard(predictions, tree.training_window_count_by_segment)
    row = scoreboard.iloc[0]
    assert json.loads(json.dumps(row["prediction_count_by_instrument"]))["mi1_etf_spy"] > 0
    assert json.loads(json.dumps(row["prediction_count_by_asset_family"]))["cash_proxy"] > 0


def test_promotion_rejected_when_validation_and_holdout_are_inconsistent() -> None:
    rows = []
    for segment in ["walk_forward_validation", "untouched_holdout"]:
        for index in range(20):
            target = float(index)
            tree = target if segment == "walk_forward_validation" else -target
            rows.append(
                {
                    "instrument_id": "mi1_etf_spy",
                    "session_date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=index),
                    "target_value": target,
                    "evaluation_segment": segment,
                    "zero_forward_excess_return": 0.0,
                    "persistence_last_observed_return": target * 0.5,
                    "ridge_technical_only_alpha_1_0": target * 0.8,
                    TREE_MODEL_NAME: tree,
                    "asset_family": "equity_broad_market",
                }
            )
    scoreboard = build_tree_scoreboard(
        pd.DataFrame(rows),
        {"walk_forward_validation": 1, "untouched_holdout": 1},
    )
    tree_rows = scoreboard[scoreboard["model_name"] == TREE_MODEL_NAME]
    assert set(tree_rows["promotion_status"]) == {"not_promoted"}
    assert "untouched_holdout" in " ".join(tree_rows["promotion_reason"])


def test_run_mi4_writes_only_local_ignored_outputs_and_preserves_boundaries() -> None:
    features, targets = _feature_target_panels()
    samples = prepare_mi4_samples(features, targets)
    mi2 = _mi2_predictions_for_samples(samples, _registry())
    mi2_root = _tmp("mi2")
    mi4_root = _tmp("mi4")
    report_root = _tmp("reports")
    features.to_parquet(mi2_root / "feature_panel.parquet", index=False)
    targets.to_parquet(mi2_root / "target_panel.parquet", index=False)
    mi2.to_parquet(mi2_root / "walk_forward_predictions.parquet", index=False)
    result = run_mi4_tree_technical_comparator(
        mi2_data_root=mi2_root,
        mi4_data_root=mi4_root,
        report_root=report_root,
        registry_path=ROOT / "configs" / "intelligence" / "mi2_research_registry.yaml",
        universe_config_path=ROOT / "configs" / "intelligence" / "universe_mi1.yaml",
    )
    assert result.fixed_random_forest_constants["random_state"] == 20260620
    assert result.comparison_row_set_sha256
    for path in result.output_paths.values():
        assert Path(path).exists()
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/data/private/mi4/*" in gitignore
    assert "/reports/mi4/*" in gitignore


def test_no_portfolio_candidate_packet_broker_macro_llm_or_network_addition() -> None:
    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT
            / "src"
            / "market_strats"
            / "intelligence"
            / "mi4"
            / "tree_technical_comparator.py",
            ROOT / "src" / "market_strats" / "intelligence" / "cli.py",
        ]
    ).lower()
    for prohibited in [
        "candidate_packet",
        "submit_order",
        "target_weight",
        "broker",
        "llm",
        "urlopen",
        "fred",
        "macro_feature",
    ]:
        assert prohibited not in source_text
