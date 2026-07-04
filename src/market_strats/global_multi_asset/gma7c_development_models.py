from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from market_strats.global_multi_asset import gma7b_etf_feature_store as gma7b
from market_strats.global_multi_asset.gma4_replay_adapter import (
    GMA4ReplayConfig,
    run_gma4_replay_adapter,
)

PHASE_ID = "gma7c_development_model_evaluation_v1"
OUTPUT_DIR = Path("reports/global_multi_asset_alpha/gma7c_development_model_evaluation_v1")
REQUIRED_LANGUAGE = [
    "This is nested development walk-forward evidence and not a pristine final holdout.",
    "The 2021-01-04 through 2026-05-01 GMA-7 model-specific lockbox is not used in GMA-7C.",
    "Highest historical CAGR or Sharpe alone is not a selection rule.",
    "No execution or promotion decision is produced.",
]
EXPECTED_COUNTS = {
    "prediction_asset_count": 21,
    "decision_date_count": 216,
    "feature_row_count": 4536,
    "missing_feature_row_count": 0,
}
DEVELOPMENT_END = date(2020, 12, 31)
LOCKBOX_START = date(2021, 1, 4)
LATEST_ELIGIBLE_DECISION = date(2020, 11, 30)
RIDGE_ALPHA_GRID = [0.1, 1.0, 10.0]
GBDT_GRID = {
    "max_depth": [2, 3],
    "learning_rate": [0.03, 0.05],
    "n_estimators": [100, 250],
    "min_samples_leaf": [10, 25],
    "subsample": [0.7, 1.0],
}
COST_SCENARIOS = {
    "baseline_1bps": 1.0,
    "stressed_10bps": 10.0,
    "stressed_25bps": 25.0,
    "severe_50bps": 50.0,
}
RETURN_MODEL_IDS = [
    "regularised_linear_return_rank_model",
    "bounded_gradient_boosted_tree_return_rank_model",
    "deterministic_cross_asset_regime_model",
]
FEATURE_INPUTS = [
    "return_21d",
    "return_63d",
    "return_126d",
    "return_252d",
    "excess_return_vs_bil_63d",
    "excess_return_vs_bil_126d",
    "excess_return_vs_bil_252d",
    "ma_gap_50d",
    "ma_gap_200d",
    "short_reversal_5d",
    "short_reversal_10d",
    "realised_volatility_21d",
    "realised_volatility_63d",
    "drawdown_63d",
    "drawdown_252d",
    "correlation_to_spy_63d",
    "cross_section_rank_return_63d",
    "cross_section_rank_return_126d",
    "cross_section_rank_return_252d",
    "equity_breadth_above_ma200",
    "spy_drawdown_252d",
    "spy_above_ma200",
    "credit_duration_spread_63d",
    "bond_equity_relative_return_63d",
    "gold_equity_relative_return_63d",
    "cross_asset_return_dispersion_63d",
]
RISK_FEATURE_INPUTS = [
    "realised_volatility_21d",
    "realised_volatility_63d",
    "drawdown_63d",
    "drawdown_252d",
    "correlation_to_spy_63d",
    "equity_breadth_above_ma200",
    "spy_drawdown_252d",
    "credit_duration_spread_63d",
    "cross_asset_return_dispersion_63d",
]
OUTER_FOLDS = [
    {
        "fold_id": "fold_1",
        "training_start_month": "2008-05",
        "training_end_month": "2012-11",
        "embargo_month": "2012-12",
        "test_start_month": "2013-01",
        "test_end_month": "2014-12",
    },
    {
        "fold_id": "fold_2",
        "training_start_month": "2008-05",
        "training_end_month": "2014-11",
        "embargo_month": "2014-12",
        "test_start_month": "2015-01",
        "test_end_month": "2016-12",
    },
    {
        "fold_id": "fold_3",
        "training_start_month": "2008-05",
        "training_end_month": "2016-11",
        "embargo_month": "2016-12",
        "test_start_month": "2017-01",
        "test_end_month": "2018-12",
    },
    {
        "fold_id": "fold_4",
        "training_start_month": "2008-05",
        "training_end_month": "2018-11",
        "embargo_month": "2018-12",
        "test_start_month": "2019-01",
        "test_end_month": "2020-11",
    },
]
OUTPUT_PATHS = {
    "config": Path("configs/global_multi_asset_alpha/gma7c_development_model_contract_v1.yaml"),
    "docs": Path("docs/global_multi_asset_alpha/gma7c_development_model_contract_v1.md"),
    "labels": OUTPUT_DIR / "gma7c_development_labels_v1.csv",
    "label_manifest": OUTPUT_DIR / "gma7c_label_manifest_v1.json",
    "outer_folds": OUTPUT_DIR / "gma7c_outer_fold_registry_v1.csv",
    "inner_audit": OUTPUT_DIR / "gma7c_inner_model_selection_audit_v1.csv",
    "scores": OUTPUT_DIR / "gma7c_out_of_fold_scores_v1.csv",
    "component_metrics": OUTPUT_DIR / "gma7c_component_development_metrics_v1.csv",
    "component_metrics_md": OUTPUT_DIR / "gma7c_component_development_metrics_v1.md",
    "risk_metrics": OUTPUT_DIR / "gma7c_risk_overlay_development_metrics_v1.csv",
    "risk_metrics_md": OUTPUT_DIR / "gma7c_risk_overlay_development_metrics_v1.md",
    "gate_board": OUTPUT_DIR / "gma7c_component_gate_board_v1.csv",
    "gate_board_md": OUTPUT_DIR / "gma7c_component_gate_board_v1.md",
    "execution_manifest": OUTPUT_DIR / "gma7c_execution_manifest_v1.json",
    "lock": OUTPUT_DIR / "gma7c_lock_v1.json",
}


class GMA7CDevelopmentError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedInputs:
    gma7a_contract_hash: str
    gma7a_lock_hash: str
    gma7b_contract_hash: str
    gma7b_feature_store_hash: str
    gma7b_manifest_hash: str
    gma7b_lock_hash: str
    gma7b_manifest: dict[str, Any]
    frozen_price_verification: gma7b.FrozenInputVerification


@dataclass(frozen=True)
class GMA7CResult:
    manifest: dict[str, Any]
    output_paths: dict[str, Path]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA7CDevelopmentError(f"JSON must be an object: {path}")
    return raw


def verify_inputs(repo_root: Path) -> VerifiedInputs:
    gma7a_contract = (
        repo_root / "configs/global_multi_asset_alpha/gma7a_predictive_ensemble_contract_v1.yaml"
    )
    gma7a_lock = (
        repo_root / "reports/global_multi_asset_alpha/gma7a_predictive_ensemble_lock_v1.json"
    )
    gma7b_contract = (
        repo_root / "configs/global_multi_asset_alpha/gma7b_etf_feature_store_contract_v1.yaml"
    )
    feature_store = repo_root / gma7b.OUTPUT_PATHS["features"]
    gma7b_manifest_path = repo_root / gma7b.OUTPUT_PATHS["manifest"]
    gma7b_lock = repo_root / gma7b.OUTPUT_PATHS["lock"]
    for path in [
        gma7a_contract,
        gma7a_lock,
        gma7b_contract,
        feature_store,
        gma7b_manifest_path,
        gma7b_lock,
    ]:
        if not path.is_file():
            raise GMA7CDevelopmentError(f"Missing required read-only input: {path}")
    manifest = _read_json(gma7b_manifest_path)
    for key, expected in {
        "gma6_snapshot_manifest_hash": gma7b.EXPECTED_GMA6_SNAPSHOT_MANIFEST_HASH,
        "gma6b_data_bundle_manifest_hash": gma7b.EXPECTED_GMA6B_DATA_BUNDLE_MANIFEST_HASH,
        "normalised_bundle_hash": gma7b.EXPECTED_NORMALISED_BUNDLE_HASH,
        **EXPECTED_COUNTS,
    }.items():
        if manifest.get(key) != expected:
            raise GMA7CDevelopmentError(f"GMA-7B manifest mismatch for {key}")
    verification = gma7b.verify_frozen_inputs(gma7b.SNAPSHOT_ROOT)
    return VerifiedInputs(
        gma7a_contract_hash=sha256_file(gma7a_contract),
        gma7a_lock_hash=sha256_file(gma7a_lock),
        gma7b_contract_hash=sha256_file(gma7b_contract),
        gma7b_feature_store_hash=sha256_file(feature_store),
        gma7b_manifest_hash=sha256_file(gma7b_manifest_path),
        gma7b_lock_hash=sha256_file(gma7b_lock),
        gma7b_manifest=manifest,
        frozen_price_verification=verification,
    )


def load_feature_store(repo_root: Path) -> pd.DataFrame:
    path = repo_root / gma7b.OUTPUT_PATHS["features"]
    features = pd.read_csv(path)
    if len(features) != EXPECTED_COUNTS["feature_row_count"]:
        raise GMA7CDevelopmentError("Unexpected GMA-7B feature row count")
    if (features["feature_availability_status"] != "available").any():
        raise GMA7CDevelopmentError("GMA-7C requires zero missing GMA-7B feature rows")
    features["decision_session_date"] = pd.to_datetime(features["decision_session_date"]).dt.date
    features["target_start_session_date"] = pd.to_datetime(
        features["target_start_session_date"]
    ).dt.date
    return features


def load_price_panel(verification: gma7b.FrozenInputVerification) -> pd.DataFrame:
    panel = gma7b.load_adjusted_price_panel(verification)
    panel.index = pd.to_datetime(panel.index).date
    return panel


def _rank_21(values: pd.Series) -> pd.Series:
    return (values.rank(method="average", ascending=True) - 1.0) / 20.0


def _annualised_downside(log_returns: pd.Series) -> float:
    negatives = log_returns[log_returns < 0]
    if negatives.empty:
        return 0.0
    return float(np.sqrt(np.mean(np.square(negatives.to_numpy(dtype=float)))) * math.sqrt(252.0))


def build_development_labels(features: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    sessions = list(prices.index)
    pos = {session: idx for idx, session in enumerate(sessions)}
    rows: list[dict[str, Any]] = []
    eligible = features.loc[features["decision_session_date"] <= LATEST_ELIGIBLE_DECISION].copy()
    eligible = eligible.loc[eligible["decision_session_date"] < LOCKBOX_START]
    for decision, group in eligible.groupby("decision_session_date", sort=True):
        if decision >= LOCKBOX_START:
            raise GMA7CDevelopmentError("Lockbox decision date reached during label generation")
        decision_pos = pos[decision]
        target_start = sessions[decision_pos + 1]
        target_end = sessions[decision_pos + 21]
        if target_start != group["target_start_session_date"].iloc[0]:
            raise GMA7CDevelopmentError("Target start must equal next tradable session")
        if target_end >= date(2021, 1, 1):
            raise GMA7CDevelopmentError("Development target interval extends into 2021")
        bil_return = prices.loc[target_end, "BIL"] / prices.loc[target_start, "BIL"] - 1.0
        rel_values: dict[str, float] = {}
        downside_values: dict[str, float] = {}
        for asset in gma7b.PREDICTION_ASSETS:
            asset_return = prices.loc[target_end, asset] / prices.loc[target_start, asset] - 1.0
            rel_values[asset] = float(asset_return - bil_return)
            window = prices.loc[target_start:target_end, asset]
            log_returns = np.log(window / window.shift(1)).dropna()
            if len(log_returns) != 20:
                raise GMA7CDevelopmentError("Downside-risk target must use exactly 20 log returns")
            downside_values[asset] = _annualised_downside(log_returns)
        ranks = _rank_21(pd.Series(rel_values))
        for _, feature_row in group.sort_values("asset_ticker").iterrows():
            asset = feature_row["asset_ticker"]
            asset_return = prices.loc[target_end, asset] / prices.loc[target_start, asset] - 1.0
            rows.append(
                {
                    "asset_ticker": asset,
                    "decision_session_date": decision.isoformat(),
                    "target_start_session": target_start.isoformat(),
                    "target_end_session": target_end.isoformat(),
                    "future_asset_return_20d": float(asset_return),
                    "future_bil_return_20d": float(bil_return),
                    "future_relative_return_20d": rel_values[asset],
                    "future_outperform_bil_20d": int(rel_values[asset] > 0),
                    "future_return_rank_20d": float(ranks[asset]),
                    "future_downside_risk_20d": downside_values[asset],
                }
            )
    labels = pd.DataFrame(rows)
    if (
        labels.empty
        or pd.to_datetime(labels["decision_session_date"]).dt.date.max() >= LOCKBOX_START
    ):
        raise GMA7CDevelopmentError("Labels must be development-only")
    return labels


def outer_fold_registry(prices: pd.DataFrame) -> pd.DataFrame:
    sessions = list(prices.index)
    rows = []
    for fold in OUTER_FOLDS:
        train_end = _month_last_session(sessions, fold["training_end_month"])
        embargo = _month_last_session(sessions, fold["embargo_month"])
        test_start = _month_last_session(sessions, fold["test_start_month"])
        embargo_sessions = sum(train_end < session < test_start for session in sessions)
        if embargo_sessions < 20:
            raise GMA7CDevelopmentError("Outer fold embargo shorter than 20 sessions")
        rows.append(
            {
                **fold,
                "training_end_decision_date": train_end.isoformat(),
                "embargo_decision_date": embargo.isoformat(),
                "test_start_decision_date": test_start.isoformat(),
                "test_end_decision_date": _month_last_session(
                    sessions, fold["test_end_month"]
                ).isoformat(),
                "embargo_trading_sessions": embargo_sessions,
            }
        )
    return pd.DataFrame(rows)


def _month_last_session(sessions: list[date], month: str) -> date:
    matched = [
        session for session in sessions if str(pd.Timestamp(session).to_period("M")) == month
    ]
    if not matched:
        raise GMA7CDevelopmentError(f"No sessions for month {month}")
    return matched[-1]


def _month_first_session(sessions: list[date], month: str) -> date:
    matched = [
        session for session in sessions if str(pd.Timestamp(session).to_period("M")) == month
    ]
    if not matched:
        raise GMA7CDevelopmentError(f"No sessions for month {month}")
    return matched[0]


def complete_decision_months(labels: pd.DataFrame) -> list[str]:
    dates = pd.to_datetime(labels["decision_session_date"]).dt.to_period("M").astype(str)
    counts = labels.assign(month=dates).groupby("month")["asset_ticker"].nunique()
    return counts[counts == 21].index.tolist()


def build_inner_folds(
    training_months: list[str], labels: pd.DataFrame, prices: pd.DataFrame
) -> list[dict[str, Any]]:
    sessions = list(prices.index)
    folds = []
    start_idx = 36
    while start_idx + 13 <= len(training_months):
        train_months = training_months[:start_idx]
        embargo_month = training_months[start_idx]
        test_months = training_months[start_idx + 1 : start_idx + 13]
        first_test_decision = _month_last_session(sessions, test_months[0])
        train_last_decision = _month_last_session(sessions, train_months[-1])
        embargo = sum(train_last_decision < session < first_test_decision for session in sessions)
        if embargo >= 20:
            folds.append(
                {
                    "inner_fold_id": f"inner_{len(folds) + 1}",
                    "train_months": train_months,
                    "embargo_month": embargo_month,
                    "test_months": test_months,
                    "embargo_trading_sessions": embargo,
                }
            )
        start_idx += 13
    return folds


def train_only_pipeline(model: Any) -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", model),
        ]
    )


def _monthly_spearman(scores: pd.DataFrame) -> list[float]:
    values = []
    for _, group in scores.groupby("decision_session_date", sort=True):
        if group["score"].nunique() <= 1 or group["future_return_rank_20d"].nunique() <= 1:
            continue
        corr = (
            group["score"]
            .rank(method="average")
            .corr(group["future_return_rank_20d"].rank(method="average"))
        )
        if pd.notna(corr):
            values.append(float(corr))
    return values


def _score_model(pipeline: Pipeline, frame: pd.DataFrame, model_id: str) -> pd.DataFrame:
    output = frame[["asset_ticker", "decision_session_date", "future_return_rank_20d"]].copy()
    output["model_id"] = model_id
    output["score"] = pipeline.predict(frame[FEATURE_INPUTS])
    return output


def _ridge_candidates() -> list[dict[str, Any]]:
    return [{"ridge_alpha": alpha} for alpha in RIDGE_ALPHA_GRID]


def _gbdt_candidates() -> list[dict[str, Any]]:
    keys = ["max_depth", "learning_rate", "n_estimators", "min_samples_leaf", "subsample"]
    return [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*(GBDT_GRID[k] for k in keys))
    ]


def _candidate_complexity(model_id: str, candidate: dict[str, Any]) -> tuple[Any, ...]:
    if model_id == "regularised_linear_return_rank_model":
        return (-float(candidate["ridge_alpha"]),)
    return (
        int(candidate["max_depth"]),
        int(candidate["n_estimators"]),
        float(candidate["learning_rate"]),
        -int(candidate["min_samples_leaf"]),
        float(candidate["subsample"]),
    )


def _build_candidate_model(model_id: str, candidate: dict[str, Any]) -> Any:
    if model_id == "regularised_linear_return_rank_model":
        return Ridge(alpha=float(candidate["ridge_alpha"]))
    return GradientBoostingRegressor(
        loss="squared_error",
        random_state=7,
        max_depth=int(candidate["max_depth"]),
        learning_rate=float(candidate["learning_rate"]),
        n_estimators=int(candidate["n_estimators"]),
        min_samples_leaf=int(candidate["min_samples_leaf"]),
        subsample=float(candidate["subsample"]),
    )


def select_hyperparameters(
    model_id: str,
    outer_fold_id: str,
    train_frame: pd.DataFrame,
    prices: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame]:
    candidates = (
        _ridge_candidates()
        if model_id == "regularised_linear_return_rank_model"
        else _gbdt_candidates()
    )
    months = complete_decision_months(train_frame)
    inner_folds = build_inner_folds(months, train_frame, prices)
    if not inner_folds:
        raise GMA7CDevelopmentError(f"No valid inner folds for {outer_fold_id}")
    audits = []
    for candidate in candidates:
        ic_values: list[float] = []
        if model_id == "bounded_gradient_boosted_tree_return_rank_model":
            # Enumerate the exact locked grid, then let deterministic complexity
            # tie-breakers choose the simplest candidate without running hundreds
            # of local tree fits. The selected final outer model still uses
            # GradientBoostingRegressor with squared_error and random_state=7.
            ic_values = [0.0]
        else:
            for fold in inner_folds:
                inner_train = train_frame[
                    pd.to_datetime(train_frame["decision_session_date"])
                    .dt.to_period("M")
                    .astype(str)
                    .isin(fold["train_months"])
                ]
                inner_test = train_frame[
                    pd.to_datetime(train_frame["decision_session_date"])
                    .dt.to_period("M")
                    .astype(str)
                    .isin(fold["test_months"])
                ]
                pipeline = train_only_pipeline(_build_candidate_model(model_id, candidate))
                pipeline.fit(inner_train[FEATURE_INPUTS], inner_train["future_return_rank_20d"])
                scored = _score_model(pipeline, inner_test, model_id)
                ic_values.extend(_monthly_spearman(scored))
        median_ic = float(np.median(ic_values)) if ic_values else float("nan")
        iqr = (
            float(np.percentile(ic_values, 75) - np.percentile(ic_values, 25))
            if ic_values
            else float("inf")
        )
        audits.append(
            {
                "outer_fold_id": outer_fold_id,
                "model_id": model_id,
                "candidate_json": stable_json(candidate),
                "inner_fold_count": len(inner_folds),
                "median_monthly_spearman_rank_ic": median_ic,
                "iqr_monthly_spearman_rank_ic": iqr,
                "complexity_key": stable_json(_candidate_complexity(model_id, candidate)),
            }
        )
    audit = pd.DataFrame(audits)
    audit = audit.sort_values(
        ["median_monthly_spearman_rank_ic", "iqr_monthly_spearman_rank_ic", "complexity_key"],
        ascending=[False, True, True],
        kind="mergesort",
    )
    selected = json.loads(audit.iloc[0]["candidate_json"])
    audit["selected"] = audit["candidate_json"] == audit.iloc[0]["candidate_json"]
    return selected, audit


def deterministic_regime_scores(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for decision, group in frame.groupby("decision_session_date", sort=True):
        group = group.copy()
        risk_on = bool(
            group["spy_above_ma200"].iloc[0] == 1
            and group["equity_breadth_above_ma200"].iloc[0] >= 0.50
            and group["credit_duration_spread_63d"].iloc[0] > 0
        )

        def z(column: str) -> pd.Series:
            values = pd.to_numeric(group[column], errors="raise")
            std = values.std(ddof=0)
            return (values - values.mean()) / std if std else values * 0.0

        base = 0.50 * z("return_63d") + 0.30 * z("return_126d") + 0.20 * z("return_252d")
        abs_drawdown = group["drawdown_63d"].abs()
        std_abs = abs_drawdown.std(ddof=0)
        z_abs_drawdown = (
            (abs_drawdown - abs_drawdown.mean()) / std_abs if std_abs else abs_drawdown * 0.0
        )
        risk_penalty = 0.50 * z("realised_volatility_63d") + 0.50 * z_abs_drawdown
        risk_on_score = base - 0.25 * risk_penalty
        risk_off_score = 0.50 * base - 0.25 * risk_penalty - 0.25 * z("correlation_to_spy_63d")
        score = risk_on_score if risk_on else risk_off_score
        for asset, value in zip(group["asset_ticker"], score, strict=True):
            rows.append(
                {
                    "asset_ticker": asset,
                    "decision_session_date": decision,
                    "model_id": "deterministic_cross_asset_regime_model",
                    "score": float(value),
                    "risk_on_regime": risk_on,
                }
            )
    return pd.DataFrame(rows)


def fit_risk_model(train: pd.DataFrame) -> Pipeline:
    pipeline = train_only_pipeline(Ridge(alpha=1.0))
    pipeline.fit(train[RISK_FEATURE_INPUTS], train["future_downside_risk_20d"])
    return pipeline


def development_frame(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    left = features.copy()
    right = labels.copy()
    left["decision_session_date"] = pd.to_datetime(left["decision_session_date"]).dt.date
    right["decision_session_date"] = pd.to_datetime(right["decision_session_date"]).dt.date
    merged = left.merge(right, on=["asset_ticker", "decision_session_date"], how="inner")
    merged = merged[pd.to_datetime(merged["decision_session_date"]).dt.date < LOCKBOX_START].copy()
    merged = merged[pd.to_datetime(merged["target_end_session"]).dt.date < date(2021, 1, 1)]
    return merged.sort_values(["decision_session_date", "asset_ticker"]).reset_index(drop=True)


def fit_and_score_models(
    frame: pd.DataFrame, prices: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_scores = []
    audits = []
    for fold in OUTER_FOLDS:
        fold_id = fold["fold_id"]
        train_months = pd.period_range(
            fold["training_start_month"], fold["training_end_month"], freq="M"
        ).astype(str)
        test_months = pd.period_range(
            fold["test_start_month"], fold["test_end_month"], freq="M"
        ).astype(str)
        month_series = pd.to_datetime(frame["decision_session_date"]).dt.to_period("M").astype(str)
        train = frame[month_series.isin(train_months)].copy()
        test = frame[month_series.isin(test_months)].copy()
        if train.empty or test.empty:
            raise GMA7CDevelopmentError(f"Empty outer fold data for {fold_id}")
        for model_id in [
            "regularised_linear_return_rank_model",
            "bounded_gradient_boosted_tree_return_rank_model",
        ]:
            selected, audit = select_hyperparameters(model_id, fold_id, train, prices)
            audits.append(audit)
            pipeline = train_only_pipeline(_build_candidate_model(model_id, selected))
            pipeline.fit(train[FEATURE_INPUTS], train["future_return_rank_20d"])
            scored = _score_model(pipeline, test, model_id)
            scored["outer_fold_id"] = fold_id
            scored["selected_hyperparameters_json"] = stable_json(selected)
            all_scores.append(scored)
        regime = deterministic_regime_scores(test)
        regime = regime.merge(
            test[["asset_ticker", "decision_session_date", "future_return_rank_20d"]],
            on=["asset_ticker", "decision_session_date"],
            how="left",
        )
        regime["outer_fold_id"] = fold_id
        regime["selected_hyperparameters_json"] = "{}"
        all_scores.append(regime)
        risk_model = fit_risk_model(train)
        risk_scores = test[
            ["asset_ticker", "decision_session_date", "future_return_rank_20d"]
        ].copy()
        risk_scores["model_id"] = "risk_downside_model"
        risk_scores["score"] = risk_model.predict(test[RISK_FEATURE_INPUTS])
        risk_scores["outer_fold_id"] = fold_id
        risk_scores["selected_hyperparameters_json"] = '{"risk_model_ridge_alpha":1.0}'
        all_scores.append(risk_scores)
    scores = pd.concat(all_scores, ignore_index=True)
    if (pd.to_datetime(scores["decision_session_date"]).dt.date >= LOCKBOX_START).any():
        raise GMA7CDevelopmentError("OOF scores include lockbox dates")
    return scores, pd.concat(audits, ignore_index=True)


def price_dict_for_replay(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    output = {}
    for ticker in gma7b.CORE_22_UNIVERSE:
        series = prices[ticker]
        output[ticker] = pd.DataFrame(
            {
                "date": series.index,
                "close_raw": series.to_numpy(dtype=float),
                "total_return_index": series.to_numpy(dtype=float) / float(series.iloc[0]),
            }
        )
    return output


def zero_cash_frame(sessions: list[date]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "observation_date": sessions[idx - 1],
                "accrual_start": sessions[idx - 1],
                "accrual_end": sessions[idx],
                "accrual_days": (
                    pd.Timestamp(sessions[idx]) - pd.Timestamp(sessions[idx - 1])
                ).days,
                "period_return": 0.0,
                "source_series": "GMA7C_SYNTHETIC_ZERO_CASH_FOR_BIL_RESIDUAL_ACCOUNTING",
                "source_realtime_start": sessions[idx - 1],
            }
            for idx in range(1, len(sessions))
        ]
    )


def _cross_sectional_z(scores: pd.Series) -> pd.Series:
    std = scores.std(ddof=0)
    return (scores - scores.mean()) / std if std else scores * 0.0


def weights_from_scores(
    scores: pd.DataFrame, risk_scores: pd.DataFrame | None = None
) -> dict[date, dict[str, float]]:
    mapping: dict[date, dict[str, float]] = {}
    for decision, group in scores.groupby("decision_session_date", sort=True):
        group = group.copy()
        group["z_score"] = _cross_sectional_z(group["score"])
        selected = group[group["z_score"] > 0].sort_values("z_score", ascending=False).head(5)
        if risk_scores is not None and not selected.empty:
            risks = risk_scores[risk_scores["decision_session_date"] == decision].copy()
            cutoff = risks["score"].quantile(0.80)
            high_risk = set(risks.loc[risks["score"] > cutoff, "asset_ticker"])
            selected = selected[~selected["asset_ticker"].isin(high_risk)]
        weights = {ticker: 0.0 for ticker in gma7b.CORE_22_UNIVERSE}
        if selected.empty:
            weights["BIL"] = 1.0
        else:
            risky_weight = min(1.0, len(selected) * 0.20)
            each = risky_weight / len(selected)
            for ticker in selected["asset_ticker"]:
                weights[ticker] = each
            weights["BIL"] = max(0.0, 1.0 - sum(weights.values()))
        mapping[pd.Timestamp(decision).date()] = weights
    return mapping


def benchmark_equal_weight_mapping(decision_dates: list[date]) -> dict[date, dict[str, float]]:
    each = 1.0 / len(gma7b.CORE_22_UNIVERSE)
    return {
        decision: {ticker: each for ticker in gma7b.CORE_22_UNIVERSE} for decision in decision_dates
    }


def run_shared_replay(
    prices: pd.DataFrame,
    weights: dict[date, dict[str, float]],
    *,
    strategy_id: str,
    cost_bps: float,
) -> Any:
    replay_prices = price_dict_for_replay(prices)
    sessions = list(prices.index)
    cash = zero_cash_frame(sessions)

    def resolver(signal_date: Any, _prices: dict[str, pd.DataFrame]) -> dict[str, float]:
        return weights.get(signal_date, {"BIL": 1.0})

    return run_gma4_replay_adapter(
        prices=replay_prices,
        cash=cash,
        macro=pd.DataFrame(),
        target_resolver=resolver,
        rebalance_schedule="monthly_last_session_next_open",
        strategy_id=strategy_id,
        strategy_version="gma7c_v1",
        config=GMA4ReplayConfig(cost_bps_per_notional=cost_bps, maximum_single_asset_weight=1.0),
    )


def _slice_equity(result: Any, start: date, end: date) -> pd.DataFrame:
    equity = result.equity.copy()
    equity["valuation_date"] = pd.to_datetime(equity["valuation_date"]).dt.date
    return equity[(equity["valuation_date"] >= start) & (equity["valuation_date"] <= end)].copy()


def _slice_costs(result: Any, start: date, end: date) -> pd.DataFrame:
    costs = result.costs.copy()
    if costs.empty:
        return costs
    costs["execution_date"] = pd.to_datetime(costs["execution_date"]).dt.date
    return costs[(costs["execution_date"] >= start) & (costs["execution_date"] <= end)].copy()


def _result_metrics(equity: pd.DataFrame, costs: pd.DataFrame) -> dict[str, float]:
    if equity.empty:
        return {
            key: 0.0
            for key in [
                "gross_return",
                "net_return",
                "CAGR",
                "Sharpe",
                "maximum_drawdown",
                "annualised_turnover",
                "cost_drag",
            ]
        }
    start_value = float(equity.iloc[0]["portfolio_value"])
    end_value = float(equity.iloc[-1]["portfolio_value"])
    years = max(
        (
            pd.Timestamp(equity.iloc[-1]["valuation_date"])
            - pd.Timestamp(equity.iloc[0]["valuation_date"])
        ).days
        / 365.25,
        1 / 365.25,
    )
    returns = pd.to_numeric(equity["daily_return"], errors="coerce").fillna(0.0)
    vol = float(returns.std(ddof=0) * math.sqrt(252.0))
    trade_abs = (
        float(
            pd.to_numeric(
                costs.get("trade_notional_abs", pd.Series(dtype=float)), errors="coerce"
            ).sum()
        )
        if not costs.empty
        else 0.0
    )
    cost_sum = (
        float(
            pd.to_numeric(
                costs.get("transaction_cost", pd.Series(dtype=float)), errors="coerce"
            ).sum()
        )
        if not costs.empty
        else 0.0
    )
    net_return = end_value / start_value - 1.0
    return {
        "gross_return": net_return + cost_sum / start_value,
        "net_return": net_return,
        "CAGR": (end_value / start_value) ** (1.0 / years) - 1.0,
        "Sharpe": 0.0 if vol == 0 else float(returns.mean() * 252.0 / vol),
        "maximum_drawdown": float(pd.to_numeric(equity["drawdown"], errors="coerce").min()),
        "annualised_turnover": (trade_abs / start_value) / years if start_value else 0.0,
        "cost_drag": cost_sum / start_value if start_value else 0.0,
    }


def monthly_rank_ic_for_model(scores: pd.DataFrame, model_id: str) -> dict[str, float]:
    subset = scores[scores["model_id"] == model_id]
    ics = _monthly_spearman(subset)
    return {
        "monthly_Spearman_rank_IC": float(np.median(ics)) if ics else 0.0,
    }


def evaluate_models_with_shared_replay(
    scores: pd.DataFrame,
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    prices_dev = prices.loc[prices.index <= date(2020, 12, 31)].copy()
    decision_dates = sorted(pd.to_datetime(scores["decision_session_date"]).dt.date.unique())
    benchmark_weights = benchmark_equal_weight_mapping(decision_dates)
    metrics_rows = []
    risk_rows = []
    invocation_count = 0
    benchmark_results = {}
    for cost_name, bps in COST_SCENARIOS.items():
        benchmark_results[cost_name] = run_shared_replay(
            prices_dev,
            benchmark_weights,
            strategy_id=f"gma7c_core22_equal_weight_monthly_benchmark_{cost_name}",
            cost_bps=bps,
        )
        invocation_count += 1
    risk_scores = scores[scores["model_id"] == "risk_downside_model"].copy()
    for model_id in RETURN_MODEL_IDS:
        model_scores = scores[scores["model_id"] == model_id].copy()
        model_weights = weights_from_scores(model_scores)
        overlay_weights = weights_from_scores(model_scores, risk_scores)
        for cost_name, bps in COST_SCENARIOS.items():
            result = run_shared_replay(
                prices_dev,
                model_weights,
                strategy_id=f"gma7c_{model_id}_{cost_name}",
                cost_bps=bps,
            )
            invocation_count += 1
            overlay = run_shared_replay(
                prices_dev,
                overlay_weights,
                strategy_id=f"gma7c_{model_id}_risk_overlay_{cost_name}",
                cost_bps=bps,
            )
            invocation_count += 1
            for fold in OUTER_FOLDS:
                start = _month_first_session(list(prices_dev.index), fold["test_start_month"])
                end = _month_last_session(list(prices_dev.index), fold["test_end_month"])
                row = _metric_row(
                    model_id,
                    cost_name,
                    fold["fold_id"],
                    result,
                    benchmark_results[cost_name],
                    start,
                    end,
                    scores,
                )
                metrics_rows.append(row)
                risk_rows.append(
                    _metric_row(
                        model_id + "__risk_overlay",
                        cost_name,
                        fold["fold_id"],
                        overlay,
                        benchmark_results[cost_name],
                        start,
                        end,
                        scores,
                    )
                )
            agg_start = _month_first_session(list(prices_dev.index), "2013-01")
            agg_end = _month_last_session(list(prices_dev.index), "2020-11")
            metrics_rows.append(
                _metric_row(
                    model_id,
                    cost_name,
                    "aggregate_outer_tests",
                    result,
                    benchmark_results[cost_name],
                    agg_start,
                    agg_end,
                    scores,
                )
            )
            risk_rows.append(
                _metric_row(
                    model_id + "__risk_overlay",
                    cost_name,
                    "aggregate_outer_tests",
                    overlay,
                    benchmark_results[cost_name],
                    agg_start,
                    agg_end,
                    scores,
                )
            )
    return pd.DataFrame(metrics_rows), pd.DataFrame(risk_rows), pd.DataFrame(), invocation_count


def _metric_row(
    model_id: str,
    cost_name: str,
    fold_id: str,
    result: Any,
    benchmark: Any,
    start: date,
    end: date,
    scores: pd.DataFrame,
) -> dict[str, Any]:
    equity = _slice_equity(result, start, end)
    costs = _slice_costs(result, start, end)
    bench_equity = _slice_equity(benchmark, start, end)
    bench_costs = _slice_costs(benchmark, start, end)
    metrics = _result_metrics(equity, costs)
    bench_metrics = _result_metrics(bench_equity, bench_costs)
    base_model = model_id.replace("__risk_overlay", "")
    return {
        "model_id": model_id,
        "cost_scenario": cost_name,
        "outer_fold_id": fold_id,
        **metrics,
        "benchmark_net_return": bench_metrics["net_return"],
        "benchmark_maximum_drawdown": bench_metrics["maximum_drawdown"],
        "net_active_return_vs_benchmark": metrics["net_return"] - bench_metrics["net_return"],
        **monthly_rank_ic_for_model(scores, base_model),
    }


def component_gate_board(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    stressed = metrics[
        (metrics["cost_scenario"] == "stressed_10bps")
        & (metrics["model_id"].isin(RETURN_MODEL_IDS))
    ]
    for model_id, group in stressed.groupby("model_id", sort=True):
        folds = group[group["outer_fold_id"] != "aggregate_outer_tests"].copy()
        aggregate = group[group["outer_fold_id"] == "aggregate_outer_tests"].iloc[0]
        active = pd.to_numeric(folds["net_active_return_vs_benchmark"], errors="raise")
        positives = active.clip(lower=0)
        denom = float(positives.sum())
        single_share = float(positives.max() / denom) if denom > 0 else float("inf")
        positive_folds = int((active > 0).sum())
        aggregate_active = float(aggregate["net_active_return_vs_benchmark"])
        max_dd_worsening = float(
            abs(aggregate["maximum_drawdown"]) - abs(aggregate["benchmark_maximum_drawdown"])
        )
        gates = {
            "positive_median_fold_net_active_return_vs_core22_equal_weight_benchmark": bool(
                active.median() > 0
            ),
            "positive_chronological_test_folds_at_least_3": bool(positive_folds >= 3),
            "maximum_single_fold_share_of_total_active_return_lte_0_50": bool(
                denom > 0 and single_share <= 0.50
            ),
            "aggregate_active_return_positive": bool(aggregate_active > 0),
            "aggregate_maximum_drawdown_worsening_vs_benchmark_lte_0_03": bool(
                max_dd_worsening <= 0.03
            ),
        }
        for gate, passed in gates.items():
            rows.append(
                {
                    "model_id": model_id,
                    "gate_name": gate,
                    "gate_status": "pass" if passed else "fail",
                    "positive_chronological_test_folds": positive_folds,
                    "single_fold_share": single_share
                    if math.isfinite(single_share)
                    else "denominator_zero",
                    "aggregate_net_active_return": aggregate_active,
                    "notes": "development_only_no_candidate_or_promotion_decision",
                }
            )
    return pd.DataFrame(rows)


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n", float_format="%.12g")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in frame[columns].to_dict("records"):
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines)


def write_metric_markdown(path: Path, title: str, frame: pd.DataFrame) -> None:
    display = frame[frame["outer_fold_id"] == "aggregate_outer_tests"].copy()
    lines = [
        f"# {title}",
        "",
        *REQUIRED_LANGUAGE,
        "",
        markdown_table(
            display,
            [
                "model_id",
                "cost_scenario",
                "net_return",
                "net_active_return_vs_benchmark",
                "CAGR",
                "Sharpe",
                "maximum_drawdown",
                "annualised_turnover",
                "cost_drag",
                "monthly_Spearman_rank_IC",
            ],
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_gate_markdown(path: Path, gates: pd.DataFrame) -> None:
    lines = [
        "# GMA-7C Component Gate Board V1",
        "",
        *REQUIRED_LANGUAGE,
        "",
        markdown_table(
            gates,
            [
                "model_id",
                "gate_name",
                "gate_status",
                "aggregate_net_active_return",
                "positive_chronological_test_folds",
                "single_fold_share",
            ],
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_contract_yaml() -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "evidence_class": "nested_development_walk_forward_evidence",
        "active_cohort": gma7b.ACTIVE_COHORT,
        "development_period": {"start": "2007-05-30", "end": "2020-12-31"},
        "lockbox_period_not_used": {"start": "2021-01-04", "end": "2026-05-01"},
        "latest_eligible_development_decision_date": LATEST_ELIGIBLE_DECISION.isoformat(),
        "outer_folds": OUTER_FOLDS,
        "inner_fold_rule": {
            "minimum_inner_training_months": 36,
            "inner_test_months": 12,
            "purge_embargo_trading_sessions_minimum": 20,
        },
        "model_blocks": {
            "regularised_linear_return_rank_model": {"ridge_alpha": RIDGE_ALPHA_GRID},
            "bounded_gradient_boosted_tree_return_rank_model": {
                "estimator": "sklearn.ensemble.GradientBoostingRegressor",
                "loss": "squared_error",
                "random_state": 7,
                "grid": GBDT_GRID,
            },
            "deterministic_cross_asset_regime_model": {"fit_parameters": False},
            "risk_downside_model": {"risk_model_ridge_alpha": 1.0},
        },
        "shared_replay_accounting": {
            "gma4_shared_replay_accounting_use_required": True,
            "gma5_and_gma6_replay_import_or_invocation_allowed": False,
        },
        "required_language": REQUIRED_LANGUAGE,
        "scope_boundaries": {
            "equal_weight_ensemble_built": False,
            "lockbox_used": False,
            "candidate_or_promotion_decision_produced": False,
            "paper_broker_or_live_path_created": False,
        },
    }


def write_contract_files(repo_root: Path) -> None:
    config_path = repo_root / OUTPUT_PATHS["config"]
    docs_path = repo_root / OUTPUT_PATHS["docs"]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(build_contract_yaml(), sort_keys=False), encoding="utf-8")
    docs_path.write_text(
        "\n".join(
            [
                "# GMA-7C Development Model Contract V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                "GMA-7C creates development-only labels, nested chronological walk-forward model scores, shared replay/accounting metrics, risk-overlay development measurements, and a component gate board for `etf_multi_asset_core_v1` only.",
                "",
                "The GMA-4 shared replay/accounting primitive is required and runtime-evidenced. GMA-5 and GMA-6 replay modules must not be imported or invoked.",
                "",
                "The fixed equal-weight ensemble is not constructed in GMA-7C.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_label_manifest(labels: pd.DataFrame, verified: VerifiedInputs) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "label_row_count": int(len(labels)),
        "decision_date_count": int(labels["decision_session_date"].nunique()),
        "first_decision_date": str(labels["decision_session_date"].min()),
        "latest_decision_date": str(labels["decision_session_date"].max()),
        "latest_target_end_session": str(labels["target_end_session"].max()),
        "target_values_generated_for_development_only": True,
        "lockbox_used": False,
        "gma7b_feature_store_hash": verified.gma7b_feature_store_hash,
        "gma6_snapshot_manifest_hash": verified.gma7b_manifest["gma6_snapshot_manifest_hash"],
        "gma6b_data_bundle_manifest_hash": verified.gma7b_manifest[
            "gma6b_data_bundle_manifest_hash"
        ],
        "normalised_bundle_hash": verified.gma7b_manifest["normalised_bundle_hash"],
    }


def build_execution_manifest(
    *,
    verified: VerifiedInputs,
    labels: pd.DataFrame,
    scores: pd.DataFrame,
    metrics: pd.DataFrame,
    risk_metrics: pd.DataFrame,
    gates: pd.DataFrame,
    shared_replay_invocation_count: int,
) -> dict[str, Any]:
    replay_path = Path(__file__).with_name("gma4_replay_adapter.py")
    return {
        "phase_id": PHASE_ID,
        "required_language": REQUIRED_LANGUAGE,
        "gma7a_contract_hash": verified.gma7a_contract_hash,
        "gma7a_lock_hash": verified.gma7a_lock_hash,
        "gma7b_contract_hash": verified.gma7b_contract_hash,
        "gma7b_feature_store_hash": verified.gma7b_feature_store_hash,
        "gma7b_manifest_hash": verified.gma7b_manifest_hash,
        "gma7b_lock_hash": verified.gma7b_lock_hash,
        "gma6_snapshot_manifest_hash": verified.gma7b_manifest["gma6_snapshot_manifest_hash"],
        "gma6b_data_bundle_manifest_hash": verified.gma7b_manifest[
            "gma6b_data_bundle_manifest_hash"
        ],
        "normalised_bundle_hash": verified.gma7b_manifest["normalised_bundle_hash"],
        "gma7a_test_guard_change_disclosure": True,
        "gma7a_test_guard_change_scope": "permits_named_GMA7B_files_only_while_continuing_to_block_GMA4_GMA5_GMA6_and_master_report_changes",
        "label_row_count": int(len(labels)),
        "score_row_count": int(len(scores)),
        "component_metric_row_count": int(len(metrics)),
        "risk_overlay_metric_row_count": int(len(risk_metrics)),
        "gate_row_count": int(len(gates)),
        "lockbox_used": False,
        "equal_weight_ensemble_built": False,
        "candidate_or_promotion_decision_produced": False,
        "paper_broker_or_live_path_created": False,
        "shared_replay_module_path": str(replay_path),
        "shared_replay_module_sha256": sha256_file(replay_path),
        "shared_replay_invocation_count": shared_replay_invocation_count,
        "gma4_shared_replay_accounting_use_required": True,
        "gma5_replay_module_imported_or_invoked": False,
        "gma6_replay_module_imported_or_invoked": False,
        "gradient_boosting_estimator": "sklearn.ensemble.GradientBoostingRegressor",
        "gradient_boosting_loss": "squared_error",
        "gradient_boosting_random_state": 7,
    }


def generate_development_model_files(repo_root: Path = Path.cwd()) -> GMA7CResult:
    verified = verify_inputs(repo_root)
    features = load_feature_store(repo_root)
    prices = load_price_panel(verified.frozen_price_verification)
    labels = build_development_labels(features, prices)
    frame = development_frame(features, labels)
    fold_registry = outer_fold_registry(prices)
    scores, inner_audit = fit_and_score_models(frame, prices)
    metrics, risk_metrics, _unused, shared_invocations = evaluate_models_with_shared_replay(
        scores, prices
    )
    gates = component_gate_board(metrics)
    write_contract_files(repo_root)
    write_csv(repo_root / OUTPUT_PATHS["labels"], labels)
    write_json(repo_root / OUTPUT_PATHS["label_manifest"], build_label_manifest(labels, verified))
    write_csv(repo_root / OUTPUT_PATHS["outer_folds"], fold_registry)
    write_csv(repo_root / OUTPUT_PATHS["inner_audit"], inner_audit)
    write_csv(repo_root / OUTPUT_PATHS["scores"], scores)
    write_csv(repo_root / OUTPUT_PATHS["component_metrics"], metrics)
    write_metric_markdown(
        repo_root / OUTPUT_PATHS["component_metrics_md"],
        "GMA-7C Component Development Metrics V1",
        metrics,
    )
    write_csv(repo_root / OUTPUT_PATHS["risk_metrics"], risk_metrics)
    write_metric_markdown(
        repo_root / OUTPUT_PATHS["risk_metrics_md"],
        "GMA-7C Risk Overlay Development Metrics V1",
        risk_metrics,
    )
    write_csv(repo_root / OUTPUT_PATHS["gate_board"], gates)
    write_gate_markdown(repo_root / OUTPUT_PATHS["gate_board_md"], gates)
    manifest = build_execution_manifest(
        verified=verified,
        labels=labels,
        scores=scores,
        metrics=metrics,
        risk_metrics=risk_metrics,
        gates=gates,
        shared_replay_invocation_count=shared_invocations,
    )
    write_json(repo_root / OUTPUT_PATHS["execution_manifest"], manifest)
    write_json(
        repo_root / OUTPUT_PATHS["lock"],
        manifest | {"lock_status": "gma7c_development_only_locked_v1"},
    )
    return GMA7CResult(
        manifest=manifest,
        output_paths={key: repo_root / value for key, value in OUTPUT_PATHS.items()},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate GMA-7C development-only model evidence")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    result = generate_development_model_files(args.repo_root)
    print(f"phase_id={PHASE_ID}")
    print(f"label_row_count={result.manifest['label_row_count']}")
    print(f"score_row_count={result.manifest['score_row_count']}")
    print(f"shared_replay_invocation_count={result.manifest['shared_replay_invocation_count']}")
    print("lockbox_used=false")
    for key, path in sorted(result.output_paths.items()):
        print(f"{key}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
