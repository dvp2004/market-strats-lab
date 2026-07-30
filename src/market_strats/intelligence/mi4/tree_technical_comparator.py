"""MI-4 fixed tree technical-model comparator."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn import __version__ as SKLEARN_VERSION
from sklearn.ensemble import RandomForestRegressor

from market_strats.intelligence.mi2.technical_baseline import (
    FEATURE_COLUMNS,
    load_registry_rules,
    rank_correlation,
    walk_forward_boundaries,
)

TREE_MODEL_NAME = "fixed_random_forest_technical_v1"
COMPARATOR_MODELS = [
    "zero_forward_excess_return",
    "persistence_last_observed_return",
    "ridge_technical_only_alpha_1_0",
    TREE_MODEL_NAME,
]
RF_CONSTANTS: dict[str, Any] = {
    "n_estimators": 64,
    "max_depth": 3,
    "min_samples_leaf": 40,
    "max_features": 3,
    "bootstrap": True,
    "max_samples": 0.70,
    "random_state": 20260620,
    "n_jobs": 1,
    "criterion": "squared_error",
}
ALLOWED_ASSET_FAMILIES = {
    "equity_broad_market",
    "equity_sector",
    "equity_international",
    "government_bonds",
    "credit_bonds",
    "broad_bonds",
    "real_assets",
    "cash_proxy",
}


@dataclass(frozen=True)
class Mi4RunResult:
    mi2_input_provenance: dict[str, Any]
    research_start_date: str
    validation_start_date: str
    validation_end_date: str
    holdout_start_date: str
    holdout_end_date: str
    fixed_random_forest_constants: dict[str, Any]
    comparison_row_set_sha256: str
    prediction_counts: dict[str, int]
    output_paths: dict[str, str]
    scoreboard_summary: list[dict[str, Any]]


@dataclass(frozen=True)
class TreePredictionResult:
    predictions: pd.DataFrame
    bounds: dict[str, Any]
    training_window_count_by_segment: dict[str, int]


def sklearn_preflight_version() -> str:
    return SKLEARN_VERSION


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return value


def instrument_id_for_symbol(symbol: str) -> str:
    return f"mi1_etf_{symbol.lower()}"


def load_asset_family_map(path: Path) -> dict[str, str]:
    config = read_yaml(path)
    assets = config.get("assets", [])
    mapping: dict[str, str] = {}
    for item in assets:
        symbol = str(item["symbol"])
        family = str(item.get("asset_family", ""))
        if family not in ALLOWED_ASSET_FAMILIES:
            raise ValueError(f"Unsupported or missing asset_family for {symbol}: {family}")
        mapping[instrument_id_for_symbol(symbol)] = family
    if len(mapping) != 22:
        raise ValueError("MI-4 asset-family diagnostics require the fixed 22-ETF universe")
    return mapping


def load_mi2_inputs(mi2_data_root: Path) -> dict[str, pd.DataFrame]:
    required = {
        "feature_panel": mi2_data_root / "feature_panel.parquet",
        "target_panel": mi2_data_root / "target_panel.parquet",
        "walk_forward_predictions": mi2_data_root / "walk_forward_predictions.parquet",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required MI-2 inputs: " + ", ".join(missing))
    frames = {name: pd.read_parquet(path) for name, path in required.items()}
    for frame in frames.values():
        if "session_date" in frame.columns:
            frame["session_date"] = pd.to_datetime(frame["session_date"]).dt.normalize()
    return frames


def canonical_row_keys(frame: pd.DataFrame) -> list[str]:
    keys = (
        frame[["instrument_id", "session_date"]]
        .drop_duplicates()
        .assign(session_date=lambda item: item["session_date"].dt.date.astype(str))
        .sort_values(["instrument_id", "session_date"])
    )
    return (keys["instrument_id"].astype(str) + "|" + keys["session_date"].astype(str)).tolist()


def comparison_row_set_hash(keys: list[str]) -> str:
    return hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()


def prepare_mi4_samples(feature_panel: pd.DataFrame, target_panel: pd.DataFrame) -> pd.DataFrame:
    required_feature_columns = {
        "instrument_id",
        "session_date",
        "decision_timestamp_utc",
        "availability_evidence_level",
        "feature_available",
        *FEATURE_COLUMNS,
    }
    required_target_columns = {
        "instrument_id",
        "session_date",
        "target_value",
        "target_available",
    }
    missing_features = required_feature_columns - set(feature_panel.columns)
    missing_targets = required_target_columns - set(target_panel.columns)
    if missing_features or missing_targets:
        raise ValueError(
            "MI-2 inputs are outside contract: "
            f"missing_features={sorted(missing_features)} "
            f"missing_targets={sorted(missing_targets)}"
        )
    eligible_features = feature_panel[feature_panel["feature_available"]].copy()
    if (eligible_features["availability_evidence_level"] == "unverified").any():
        raise ValueError("Unverified MI-2 feature row is marked eligible")
    if eligible_features[FEATURE_COLUMNS].isna().any(axis=None):
        raise ValueError("MI-2 feature_available rows contain incomplete technical features")
    samples = feature_panel.merge(target_panel, on=["instrument_id", "session_date"], how="inner")
    samples = samples[samples["feature_available"] & samples["target_available"]].copy()
    if samples.empty:
        raise ValueError("No MI-4 eligible technical forecast rows available")
    if samples[FEATURE_COLUMNS].isna().any(axis=None):
        raise ValueError("MI-4 refuses missing technical features; no imputation is allowed")
    if samples["target_value"].isna().any():
        raise ValueError("MI-4 eligible rows contain missing targets")
    return samples.sort_values(["session_date", "instrument_id"]).reset_index(drop=True)


def fixed_random_forest() -> RandomForestRegressor:
    return RandomForestRegressor(**RF_CONSTANTS)


def fit_tree_predict(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    model = fixed_random_forest()
    model.fit(train[FEATURE_COLUMNS], train["target_value"])
    return model.predict(test[FEATURE_COLUMNS])


def build_tree_predictions(
    samples: pd.DataFrame,
    registry: dict[str, Any],
) -> TreePredictionResult:
    sessions = list(pd.Index(samples["session_date"].unique()).sort_values())
    bounds = walk_forward_boundaries(sessions, registry)
    predictions: list[pd.DataFrame] = []
    training_counts = {"walk_forward_validation": 0, "untouched_holdout": 0}

    def predict_block(
        train_sessions: list[pd.Timestamp],
        test_sessions: list[pd.Timestamp],
        segment: str,
        window_id: str,
    ) -> None:
        train = samples[samples["session_date"].isin(train_sessions)].copy()
        test = samples[samples["session_date"].isin(test_sessions)].copy()
        if train.empty or test.empty:
            return
        train_max = train["session_date"].max()
        test_min = test["session_date"].min()
        if train_max >= test_min:
            raise ValueError("Split-window leakage: training rows overlap test rows")
        prediction = fit_tree_predict(train, test)
        out = test[["instrument_id", "session_date", "target_value"]].copy()
        out["evaluation_segment"] = segment
        out[TREE_MODEL_NAME] = prediction
        out["training_window_id"] = window_id
        out["training_start_session"] = min(train_sessions)
        out["training_end_session"] = max(train_sessions)
        out["test_start_session"] = min(test_sessions)
        out["test_end_session"] = max(test_sessions)
        predictions.append(out)
        training_counts[segment] += 1

    validation_sessions = bounds["validation_sessions"]
    for index, block in enumerate(bounds["blocks"]):
        predict_block(
            validation_sessions[: block["train_end_index"]],
            block["test_sessions"],
            "walk_forward_validation",
            f"validation_{index:03d}",
        )
    holdout_train_end = max(0, bounds["holdout_start_index"] - bounds["purge_sessions"])
    predict_block(
        sessions[:holdout_train_end],
        bounds["holdout_sessions"],
        "untouched_holdout",
        "holdout_000",
    )
    if not predictions:
        raise ValueError("MI-4 walk-forward process produced no out-of-sample predictions")
    return TreePredictionResult(
        predictions=pd.concat(predictions, ignore_index=True),
        bounds=bounds,
        training_window_count_by_segment=training_counts,
    )


def normalize_mi2_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    required = {
        "instrument_id",
        "session_date",
        "target_value",
        "evaluation_segment",
        "zero_prediction",
        "persistence_prediction",
        "prediction",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"MI-2 walk_forward_predictions is outside contract: {sorted(missing)}")
    frame = predictions.copy()
    frame["session_date"] = pd.to_datetime(frame["session_date"]).dt.normalize()
    return frame.rename(
        columns={
            "zero_prediction": "zero_forward_excess_return",
            "persistence_prediction": "persistence_last_observed_return",
            "prediction": "ridge_technical_only_alpha_1_0",
        }
    )[
        [
            "instrument_id",
            "session_date",
            "target_value",
            "evaluation_segment",
            "zero_forward_excess_return",
            "persistence_last_observed_return",
            "ridge_technical_only_alpha_1_0",
        ]
    ].copy()


def assert_row_set_equality(mi2_predictions: pd.DataFrame, tree_predictions: pd.DataFrame) -> None:
    for segment in ["walk_forward_validation", "untouched_holdout"]:
        mi2_keys = canonical_row_keys(
            mi2_predictions[mi2_predictions["evaluation_segment"] == segment]
        )
        tree_keys = canonical_row_keys(
            tree_predictions[tree_predictions["evaluation_segment"] == segment]
        )
        if mi2_keys != tree_keys:
            raise ValueError(
                "MI-4 row-set equality failure for "
                f"{segment}: mi2_rows={len(mi2_keys)} tree_rows={len(tree_keys)}"
            )


def merge_comparison_predictions(
    mi2_predictions: pd.DataFrame,
    tree_predictions: pd.DataFrame,
    asset_family_by_instrument: dict[str, str],
) -> pd.DataFrame:
    assert_row_set_equality(mi2_predictions, tree_predictions)
    merged = mi2_predictions.merge(
        tree_predictions[
            [
                "instrument_id",
                "session_date",
                "target_value",
                "evaluation_segment",
                TREE_MODEL_NAME,
                "training_window_id",
                "training_start_session",
                "training_end_session",
                "test_start_session",
                "test_end_session",
            ]
        ],
        on=["instrument_id", "session_date", "target_value", "evaluation_segment"],
        how="inner",
    )
    if len(merged) != len(tree_predictions):
        raise ValueError("MI-4 comparison merge changed the prediction row set")
    merged["asset_family"] = merged["instrument_id"].map(asset_family_by_instrument)
    if merged["asset_family"].isna().any():
        missing = sorted(merged.loc[merged["asset_family"].isna(), "instrument_id"].unique())
        raise ValueError(f"Missing explicit asset_family metadata for instruments: {missing}")
    return merged.sort_values(["evaluation_segment", "session_date", "instrument_id"]).reset_index(
        drop=True
    )


def prediction_count_by(frame: pd.DataFrame, column: str) -> dict[str, int]:
    return {
        str(key): int(value) for key, value in frame[column].value_counts().sort_index().items()
    }


def build_tree_scoreboard(
    predictions: pd.DataFrame,
    training_window_count_by_segment: dict[str, int],
    *,
    row_set_violation: bool = False,
) -> pd.DataFrame:
    row_set_sha = comparison_row_set_hash(canonical_row_keys(predictions))
    count_by_instrument = prediction_count_by(predictions, "instrument_id")
    count_by_asset_family = prediction_count_by(predictions, "asset_family")
    rows: list[dict[str, Any]] = []
    for segment, group in predictions.groupby("evaluation_segment"):
        for model_name in COMPARATOR_MODELS:
            valid = group[["target_value", model_name]].dropna()
            rows.append(
                {
                    "model_name": model_name,
                    "segment": segment,
                    "mae": float((valid["target_value"] - valid[model_name]).abs().mean()),
                    "rank_correlation": rank_correlation(
                        valid["target_value"],
                        valid[model_name],
                    ),
                    "observation_count": int(len(valid)),
                    "training_window_count": int(training_window_count_by_segment[segment]),
                    "prediction_count": int(len(valid)),
                    "promotion_status": "not_promoted",
                    "promotion_reason": "baseline comparator; no promotion claim",
                    "comparison_row_set_sha256": row_set_sha,
                    "prediction_count_by_instrument": count_by_instrument,
                    "prediction_count_by_asset_family": count_by_asset_family,
                }
            )
    scoreboard = pd.DataFrame(rows)
    reasons = []
    for segment in ["walk_forward_validation", "untouched_holdout"]:
        seg = scoreboard[scoreboard["segment"] == segment].set_index("model_name")
        tree = seg.loc[TREE_MODEL_NAME]
        zero = seg.loc["zero_forward_excess_return"]
        ridge = seg.loc["ridge_technical_only_alpha_1_0"]
        if not (tree["mae"] < zero["mae"] and tree["mae"] < ridge["mae"]):
            reasons.append(f"{segment}: tree MAE did not beat zero and Ridge")
        if not (tree["rank_correlation"] > 0):
            reasons.append(f"{segment}: tree rank correlation was not positive")
        if segment == "untouched_holdout" and not (
            tree["rank_correlation"] >= ridge["rank_correlation"]
        ):
            reasons.append("untouched_holdout: tree rank correlation was below Ridge")
    if row_set_violation:
        reasons.append("row-set, availability, split-window, or leakage violation")
    mask = scoreboard["model_name"] == TREE_MODEL_NAME
    if reasons:
        scoreboard.loc[mask, "promotion_status"] = "not_promoted"
        scoreboard.loc[mask, "promotion_reason"] = "; ".join(reasons)
    else:
        scoreboard.loc[mask, "promotion_status"] = "promoted"
        scoreboard.loc[mask, "promotion_reason"] = (
            "fixed tree comparator met all MI-4 forecast promotion criteria"
        )
    return scoreboard


def write_tree_scoreboard_reports(
    scoreboard: pd.DataFrame,
    report_root: Path,
) -> tuple[Path, Path]:
    report_root.mkdir(parents=True, exist_ok=True)
    json_path = report_root / "tree_technical_forecast_scoreboard.json"
    md_path = report_root / "tree_technical_forecast_scoreboard.md"
    json_path.write_text(
        json.dumps(scoreboard.replace({np.nan: None}).to_dict(orient="records"), indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# MI-4 Tree Technical Forecast Scoreboard",
        "",
        "Evaluation layer: forecast evaluation only.",
        "",
        "| model | segment | mae | rank_correlation | obs | windows | promotion |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in scoreboard.itertuples(index=False):
        lines.append(
            f"| {row.model_name} | {row.segment} | {row.mae:.6f} | "
            f"{row.rank_correlation:.6f} | {row.observation_count} | "
            f"{row.training_window_count} | {row.promotion_status} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def run_mi4_tree_technical_comparator(
    *,
    mi2_data_root: Path,
    mi4_data_root: Path,
    report_root: Path,
    registry_path: Path = Path("configs/intelligence/mi2_research_registry.yaml"),
    universe_config_path: Path = Path("configs/intelligence/universe_mi1.yaml"),
) -> Mi4RunResult:
    registry = load_registry_rules(registry_path)
    asset_family_by_instrument = load_asset_family_map(universe_config_path)
    inputs = load_mi2_inputs(mi2_data_root)
    samples = prepare_mi4_samples(inputs["feature_panel"], inputs["target_panel"])
    tree_result = build_tree_predictions(samples, registry)
    mi2_predictions = normalize_mi2_predictions(inputs["walk_forward_predictions"])
    predictions = merge_comparison_predictions(
        mi2_predictions,
        tree_result.predictions,
        asset_family_by_instrument,
    )
    scoreboard = build_tree_scoreboard(
        predictions,
        tree_result.training_window_count_by_segment,
    )

    mi4_data_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    prediction_path = mi4_data_root / "tree_walk_forward_predictions.parquet"
    scoreboard_path = mi4_data_root / "tree_forecast_scoreboard.parquet"
    predictions.to_parquet(prediction_path, index=False)
    scoreboard.to_parquet(scoreboard_path, index=False)
    md_path, json_path = write_tree_scoreboard_reports(scoreboard, report_root)

    bounds = tree_result.bounds
    validation_sessions = bounds["validation_sessions"]
    holdout_sessions = bounds["holdout_sessions"]
    row_set_sha = str(scoreboard["comparison_row_set_sha256"].iloc[0])
    output_paths = {
        "tree_walk_forward_predictions": str(prediction_path),
        "tree_forecast_scoreboard": str(scoreboard_path),
        "scoreboard_markdown": str(md_path),
        "scoreboard_json": str(json_path),
    }
    return Mi4RunResult(
        mi2_input_provenance={
            "source": "local MI-2 parquet outputs",
            "feature_panel": str(mi2_data_root / "feature_panel.parquet"),
            "target_panel": str(mi2_data_root / "target_panel.parquet"),
            "walk_forward_predictions": str(mi2_data_root / "walk_forward_predictions.parquet"),
            "sklearn_version": sklearn_preflight_version(),
        },
        research_start_date=samples["session_date"].min().date().isoformat(),
        validation_start_date=validation_sessions[0].date().isoformat(),
        validation_end_date=validation_sessions[-1].date().isoformat(),
        holdout_start_date=holdout_sessions[0].date().isoformat(),
        holdout_end_date=holdout_sessions[-1].date().isoformat(),
        fixed_random_forest_constants=dict(RF_CONSTANTS),
        comparison_row_set_sha256=row_set_sha,
        prediction_counts={
            "total": int(len(predictions)),
            **{
                str(segment): int(count)
                for segment, count in predictions["evaluation_segment"]
                .value_counts()
                .sort_index()
                .items()
            },
        },
        output_paths=output_paths,
        scoreboard_summary=scoreboard[
            [
                "model_name",
                "segment",
                "mae",
                "rank_correlation",
                "promotion_status",
            ]
        ].to_dict(orient="records"),
    )
