from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.interpretable_stock_ranker import (
    DEFAULT_PHASE23G_CONFIG,
    NONCANONICAL_WARNING,
    _cross_sectional_zscore,
    _folds_for_dates,
    _prepare_joined_panel,
    _ridge_fit,
    _safe_spearman,
)
from market_strats.analysis.pilot_individual_equity_feature_calculation import (
    CORE_FEATURE_COLUMNS,
)


PHASE23H_SECTION = "phase23h_interpretable_ranker_robustness"
RIDGE_MODEL = "phase23g_ridge_ranker_v1"
DEFAULT_PHASE23H_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": "reports/individual_equity_decision_system/phase23h_interpretable_ranker_robustness",
    "dashboard_status_path": "reports/paper_trading/dashboard/phase23h_interpretable_ranker_robustness_status.csv",
    "source_phase23g_dir": "reports/individual_equity_decision_system/phase23g_interpretable_stock_ranker",
    "source_phase23f_dir": "reports/individual_equity_decision_system/phase23f_pilot_feature_calculation",
    "phase23g_config": DEFAULT_PHASE23G_CONFIG,
    "model_version": RIDGE_MODEL,
    "primary_target": "forward_20d_excess_return_vs_universe",
    "top_k": 3,
    "bootstrap_seed": 2308,
    "bootstrap_samples": 200,
    "bootstrap_block_length_dates": 4,
    "permutation_seed": 2311,
    "permutation_count": 100,
    "minimum_test_dates": 8,
    "minimum_security_count": 3,
    "minimum_future_observation_count": 52,
    "rolling_training_windows": [26, 52],
    "membership_canonical": False,
    "market_data_canonical": False,
    "research_pilot_only": True,
    "generalization_claim_allowed": False,
    "investable_performance_claim_allowed": False,
    "model_training_allowed": False,
    "paper_trading_allowed": False,
    "live_trading_allowed": False,
    "real_money_allowed": False,
    "broker_api_integration_allowed": False,
    "promotion_allowed": False,
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(DEFAULT_PHASE23H_CONFIG, config.get(PHASE23H_SECTION, {}))


def _resolve_reports_path(*, configured_path: str | Path, reports_dir: str | Path) -> Path:
    reports_root = Path(reports_dir)
    path = Path(configured_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == "reports":
        return reports_root.joinpath(*path.parts[1:])
    return reports_root / path


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _gate(name: str, passed: bool, detail: str, critical: bool = True) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "critical": bool(critical),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _model_predictions(predictions: pd.DataFrame, model_version: str) -> pd.DataFrame:
    return predictions.loc[predictions["model_version"].astype(str).eq(model_version)].copy()


def _rank_spread_for_group(group: pd.DataFrame, top_k: int) -> float:
    sorted_group = group.sort_values("predicted_rank")
    top = sorted_group.head(top_k)
    bottom = sorted_group.tail(top_k)
    if top.empty or bottom.empty:
        return np.nan
    return float(top["actual_20d_excess_return"].mean() - bottom["actual_20d_excess_return"].mean())


def _ic_by_date(predictions: pd.DataFrame, top_k: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if predictions.empty:
        return pd.DataFrame()
    for (model, date), group in predictions.groupby(["model_version", "decision_timestamp_utc"]):
        ic = _safe_spearman(
            group["predicted_20d_excess_return_or_ranking_score"],
            group["actual_20d_excess_return"],
        )
        rows.append(
            {
                "model_version": model,
                "decision_timestamp_utc": date,
                "signal_date": group["signal_date"].iloc[0],
                "spearman_information_coefficient": ic,
                "top_minus_bottom_rank_spread": _rank_spread_for_group(group, top_k),
                "security_count": len(group),
            }
        )
    return pd.DataFrame(rows)


def _longest_streak(values: pd.Series, positive: bool) -> int:
    best = 0
    current = 0
    for value in pd.to_numeric(values, errors="coerce"):
        condition = pd.notna(value) and ((value > 0) if positive else (value < 0))
        current = current + 1 if condition else 0
        best = max(best, current)
    return int(best)


def _stability_from_ic(ic: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model, group in ic.groupby("model_version"):
        ordered = group.sort_values("decision_timestamp_utc")
        values = pd.to_numeric(ordered["spearman_information_coefficient"], errors="coerce")
        rolling13 = values.rolling(13, min_periods=3).mean()
        rows.append(
            {
                "model_version": model,
                "mean_ic": float(values.mean()) if values.notna().any() else np.nan,
                "median_ic": float(values.median()) if values.notna().any() else np.nan,
                "ic_std": float(values.std()) if values.notna().sum() > 1 else np.nan,
                "ic_information_ratio": (
                    float(values.mean() / values.std())
                    if values.notna().sum() > 1 and float(values.std()) != 0.0
                    else np.nan
                ),
                "positive_ic_fraction": (
                    float((values.dropna() > 0).mean()) if values.notna().any() else np.nan
                ),
                "worst_13_date_mean_ic": float(rolling13.min()) if rolling13.notna().any() else np.nan,
                "best_13_date_mean_ic": float(rolling13.max()) if rolling13.notna().any() else np.nan,
                "longest_negative_ic_streak": _longest_streak(values, positive=False),
                "longest_positive_ic_streak": _longest_streak(values, positive=True),
                "date_count": int(ordered["decision_timestamp_utc"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def _rolling_ic(ic: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model, group in ic.groupby("model_version"):
        ordered = group.sort_values("decision_timestamp_utc").copy()
        values = pd.to_numeric(ordered["spearman_information_coefficient"], errors="coerce")
        ordered["rolling_13_date_mean_ic"] = values.rolling(13, min_periods=3).mean()
        ordered["rolling_26_date_mean_ic"] = values.rolling(26, min_periods=6).mean()
        rows.extend(ordered.to_dict("records"))
    return pd.DataFrame(rows)


def _calendar_period_metrics(ic: pd.DataFrame) -> pd.DataFrame:
    if ic.empty:
        return pd.DataFrame()
    frame = ic.copy()
    frame["signal_date"] = pd.to_datetime(frame["signal_date"])
    frame["calendar_year"] = frame["signal_date"].dt.year.astype(str)
    frame["calendar_quarter"] = frame["signal_date"].dt.to_period("Q").astype(str)
    rows: list[dict[str, Any]] = []
    for model in sorted(frame["model_version"].unique()):
        model_frame = frame.loc[frame["model_version"].eq(model)]
        for period_type, column in [("year", "calendar_year"), ("quarter", "calendar_quarter")]:
            for period, group in model_frame.groupby(column):
                rows.append(
                    {
                        "model_version": model,
                        "period_type": period_type,
                        "calendar_period": period,
                        "date_count": group["decision_timestamp_utc"].nunique(),
                        "mean_ic": group["spearman_information_coefficient"].mean(),
                        "median_ic": group["spearman_information_coefficient"].median(),
                        "positive_ic_fraction": (
                            group["spearman_information_coefficient"].dropna().gt(0).mean()
                        ),
                        "mean_top_minus_bottom_spread": group[
                            "top_minus_bottom_rank_spread"
                        ].mean(),
                    }
                )
    return pd.DataFrame(rows)


def moving_block_bootstrap(
    date_metrics: pd.DataFrame,
    *,
    seed: int,
    samples: int,
    block_length: int,
) -> pd.DataFrame:
    """Deterministic moving-block bootstrap over date-level observations."""

    rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(seed)
    for model, group in date_metrics.groupby("model_version"):
        ordered = group.sort_values("decision_timestamp_utc").reset_index(drop=True)
        n = len(ordered)
        if n == 0:
            continue
        ic_values = pd.to_numeric(
            ordered["spearman_information_coefficient"], errors="coerce"
        ).to_numpy(dtype=float)
        spread_values = pd.to_numeric(
            ordered["top_minus_bottom_rank_spread"], errors="coerce"
        ).to_numpy(dtype=float)
        means_ic: list[float] = []
        means_spread: list[float] = []
        if np.isnan(ic_values).all():
            rows.append(
                {
                    "model_version": model,
                    "bootstrap_method": "moving_block_bootstrap_by_decision_date",
                    "bootstrap_seed": seed,
                    "bootstrap_samples": samples,
                    "block_length_dates": block_length,
                    "observed_mean_ic": np.nan,
                    "mean_ic_ci90_low": np.nan,
                    "mean_ic_ci90_high": np.nan,
                    "mean_ic_ci95_low": np.nan,
                    "mean_ic_ci95_high": np.nan,
                    "bootstrap_probability_mean_ic_above_zero": np.nan,
                    "observed_spread": float(np.nanmean(spread_values)),
                    "spread_ci90_low": np.nan,
                    "spread_ci90_high": np.nan,
                    "spread_ci95_low": np.nan,
                    "spread_ci95_high": np.nan,
                    "bootstrap_probability_spread_above_zero": np.nan,
                    "iid_standard_errors_used": False,
                    "overlapping_label_warning": (
                        "weekly predictions use 20-trading-day labels, so date-level "
                        "observations overlap"
                    ),
                }
            )
            continue
        max_start = max(n - block_length, 0)
        for _ in range(samples):
            indices: list[int] = []
            while len(indices) < n:
                start = int(rng.integers(0, max_start + 1)) if max_start else 0
                indices.extend(range(start, min(start + block_length, n)))
            sampled = np.array(indices[:n], dtype=int)
            means_ic.append(float(np.nanmean(ic_values[sampled])))
            means_spread.append(float(np.nanmean(spread_values[sampled])))
        ic_array = np.array(means_ic, dtype=float)
        spread_array = np.array(means_spread, dtype=float)
        rows.append(
            {
                "model_version": model,
                "bootstrap_method": "moving_block_bootstrap_by_decision_date",
                "bootstrap_seed": seed,
                "bootstrap_samples": samples,
                "block_length_dates": block_length,
                "observed_mean_ic": float(np.nanmean(ic_values)),
                "mean_ic_ci90_low": float(np.nanpercentile(ic_array, 5)),
                "mean_ic_ci90_high": float(np.nanpercentile(ic_array, 95)),
                "mean_ic_ci95_low": float(np.nanpercentile(ic_array, 2.5)),
                "mean_ic_ci95_high": float(np.nanpercentile(ic_array, 97.5)),
                "bootstrap_probability_mean_ic_above_zero": float(np.mean(ic_array > 0)),
                "observed_spread": float(np.nanmean(spread_values)),
                "spread_ci90_low": float(np.nanpercentile(spread_array, 5)),
                "spread_ci90_high": float(np.nanpercentile(spread_array, 95)),
                "spread_ci95_low": float(np.nanpercentile(spread_array, 2.5)),
                "spread_ci95_high": float(np.nanpercentile(spread_array, 97.5)),
                "bootstrap_probability_spread_above_zero": float(
                    np.mean(spread_array > 0)
                ),
                "iid_standard_errors_used": False,
                "overlapping_label_warning": (
                    "weekly predictions use 20-trading-day labels, so date-level "
                    "observations overlap"
                ),
            }
        )
    return pd.DataFrame(rows)


def permutation_test(
    predictions: pd.DataFrame,
    *,
    seed: int,
    permutations: int,
    top_k: int,
) -> pd.DataFrame:
    """Permute target values within each date while preserving cross-section size."""

    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for model, model_frame in predictions.groupby("model_version"):
        observed_ic = _ic_by_date(model_frame, top_k)
        observed_mean_ic = observed_ic["spearman_information_coefficient"].mean()
        observed_spread = observed_ic["top_minus_bottom_rank_spread"].mean()
        if observed_ic["spearman_information_coefficient"].isna().all():
            rows.append(
                {
                    "model_version": model,
                    "permutation_method": "within_decision_date_target_permutation",
                    "permutation_seed": seed,
                    "permutation_count": permutations,
                    "observed_mean_ic": np.nan,
                    "null_mean_ic": np.nan,
                    "null_std_ic": np.nan,
                    "empirical_one_sided_ic_p_value": np.nan,
                    "observed_spread": observed_spread,
                    "null_mean_spread": np.nan,
                    "null_std_spread": np.nan,
                    "empirical_one_sided_spread_p_value": np.nan,
                }
            )
            continue
        date_arrays = []
        for _date, group in model_frame.groupby("decision_timestamp_utc"):
            ordered = group.sort_values("predicted_rank")
            scores = pd.to_numeric(
                ordered["predicted_20d_excess_return_or_ranking_score"], errors="coerce"
            ).to_numpy(dtype=float)
            actual = pd.to_numeric(
                ordered["actual_20d_excess_return"], errors="coerce"
            ).to_numpy(dtype=float)
            date_arrays.append((scores, actual))
        null_ic: list[float] = []
        null_spread: list[float] = []
        for _ in range(permutations):
            perm_ics: list[float] = []
            perm_spreads: list[float] = []
            for scores, actual in date_arrays:
                shuffled = rng.permutation(actual)
                perm_ics.append(_safe_spearman(pd.Series(scores), pd.Series(shuffled)))
                top = shuffled[:top_k]
                bottom = shuffled[-top_k:]
                perm_spreads.append(float(np.nanmean(top) - np.nanmean(bottom)))
            null_ic.append(float(np.nanmean(perm_ics)))
            null_spread.append(float(np.nanmean(perm_spreads)))
        null_ic_array = np.array(null_ic, dtype=float)
        null_spread_array = np.array(null_spread, dtype=float)
        rows.append(
            {
                "model_version": model,
                "permutation_method": "within_decision_date_target_permutation",
                "permutation_seed": seed,
                "permutation_count": permutations,
                "observed_mean_ic": observed_mean_ic,
                "null_mean_ic": float(np.nanmean(null_ic_array)),
                "null_std_ic": float(np.nanstd(null_ic_array)),
                "empirical_one_sided_ic_p_value": float(
                    (np.sum(null_ic_array >= observed_mean_ic) + 1) / (permutations + 1)
                ),
                "observed_spread": observed_spread,
                "null_mean_spread": float(np.nanmean(null_spread_array)),
                "null_std_spread": float(np.nanstd(null_spread_array)),
                "empirical_one_sided_spread_p_value": float(
                    (np.sum(null_spread_array >= observed_spread) + 1)
                    / (permutations + 1)
                ),
            }
        )
    return pd.DataFrame(rows)


def _prediction_metrics(predictions: pd.DataFrame, top_k: int) -> dict[str, float]:
    if predictions.empty:
        return {
            "mean_ic": np.nan,
            "median_ic": np.nan,
            "positive_ic_fraction": np.nan,
            "top_minus_bottom_rank_spread": np.nan,
            "prediction_coverage": 0.0,
        }
    ic = _ic_by_date(predictions, top_k)
    return {
        "mean_ic": float(ic["spearman_information_coefficient"].mean()),
        "median_ic": float(ic["spearman_information_coefficient"].median()),
        "positive_ic_fraction": float(
            ic["spearman_information_coefficient"].dropna().gt(0).mean()
        ),
        "top_minus_bottom_rank_spread": float(ic["top_minus_bottom_rank_spread"].mean()),
        "prediction_coverage": float(predictions["actual_20d_excess_return"].notna().mean()),
    }


def _run_custom_ridge(
    panel: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    features: list[str],
    config: dict[str, Any],
    model_version: str,
    alpha: float | None = None,
    rolling_training_window_dates: int | None = None,
) -> pd.DataFrame:
    phase23g_config = _deep_merge(DEFAULT_PHASE23G_CONFIG, config.get("phase23g_config", {}))
    phase23g_config["primary_target"] = config["primary_target"]
    phase23g_config["model_version"] = model_version
    if alpha is not None:
        phase23g_config["ridge_alpha"] = alpha
        phase23g_config["ridge_alpha_grid"] = [alpha]
    joined = _prepare_joined_panel(
        panel,
        targets,
        primary_target=str(config["primary_target"]),
    )
    folds = _folds_for_dates(joined, phase23g_config)
    joined_cs = _cross_sectional_zscore(joined, features)
    rows: list[dict[str, Any]] = []
    for fold in folds:
        train = fold["train"].copy()
        if rolling_training_window_dates is not None:
            dates = pd.DatetimeIndex(
                sorted(pd.to_datetime(train["decision_timestamp_utc"].dropna().unique()))
            )
            keep_dates = set(dates[-rolling_training_window_dates:])
            train = train.loc[pd.to_datetime(train["decision_timestamp_utc"]).isin(keep_dates)]
            if (
                train["decision_timestamp_utc"].nunique()
                < int(phase23g_config["minimum_training_decision_dates"])
                or len(train) < int(phase23g_config["minimum_training_rows"])
            ):
                continue
        test = fold["test"]
        train_cs = joined_cs.loc[
            joined_cs["panel_row_id"].isin(set(train["panel_row_id"]))
        ].copy()
        test_cs = joined_cs.loc[
            joined_cs["panel_row_id"].isin(set(test["panel_row_id"]))
        ].sort_values("permanent_security_id").copy()
        x_train_raw = train_cs[features].apply(pd.to_numeric, errors="coerce")
        x_test_raw = test_cs[features].apply(pd.to_numeric, errors="coerce")
        medians = x_train_raw.median().fillna(0.0)
        x_train_raw = x_train_raw.fillna(medians)
        x_test_raw = x_test_raw.fillna(medians)
        means = x_train_raw.mean()
        stds = x_train_raw.std().replace(0, 1.0).fillna(1.0)
        x_train = ((x_train_raw - means) / stds).to_numpy(dtype=float)
        x_test = ((x_test_raw - means) / stds).to_numpy(dtype=float)
        y_train = pd.to_numeric(
            train_cs["target_value"], errors="coerce"
        ).fillna(0.0).to_numpy(dtype=float)
        intercept, coef = _ridge_fit(x_train, y_train, float(phase23g_config["ridge_alpha"]))
        scores = pd.Series(intercept + x_test @ coef, index=test_cs.index)
        actual_rank = pd.to_numeric(test_cs["target_value"], errors="coerce").rank(
            ascending=False,
            method="first",
        )
        predicted_rank = scores.rank(ascending=False, method="first")
        for idx, row in test_cs.iterrows():
            rows.append(
                {
                    "decision_timestamp_utc": row.decision_timestamp_utc.isoformat(),
                    "signal_date": pd.Timestamp(row.signal_date).date().isoformat(),
                    "panel_row_id": row.panel_row_id,
                    "permanent_security_id": row.permanent_security_id,
                    "ticker": row.ticker,
                    "model_version": model_version,
                    "predicted_20d_excess_return_or_ranking_score": float(scores.loc[idx]),
                    "predicted_rank": int(predicted_rank.loc[idx]),
                    "actual_20d_excess_return": float(row.target_value),
                    "actual_rank": int(actual_rank.loc[idx]),
                }
            )
    return pd.DataFrame(rows)


def _feature_ablation(
    panel: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    config: dict[str, Any],
    all_feature_mean_ic: float,
    top_k: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_rows: list[dict[str, Any]] = []
    features = [feature for feature in CORE_FEATURE_COLUMNS if feature in panel.columns]
    for feature in features:
        preds = _run_custom_ridge(
            panel,
            targets,
            features=[feature],
            config=config,
            model_version=f"single_feature_{feature}",
        )
        metrics = _prediction_metrics(preds, top_k)
        feature_rows.append(
            {
                "ablation_type": "single_feature",
                "feature_set_name": feature,
                "features_used": feature,
                **metrics,
                "mean_ic_delta_vs_all_features": metrics["mean_ic"] - all_feature_mean_ic,
            }
        )
    for feature in features:
        remaining = [name for name in features if name != feature]
        preds = _run_custom_ridge(
            panel,
            targets,
            features=remaining,
            config=config,
            model_version=f"leave_one_out_{feature}",
        )
        metrics = _prediction_metrics(preds, top_k)
        feature_rows.append(
            {
                "ablation_type": "leave_one_feature_out",
                "feature_set_name": feature,
                "features_used": ";".join(remaining),
                **metrics,
                "mean_ic_delta_vs_all_features": metrics["mean_ic"] - all_feature_mean_ic,
            }
        )
    groups = {
        "all_features": features,
        "momentum_only": [
            feature
            for feature in ["momentum_21d", "momentum_63d", "momentum_252d_skip21d"]
            if feature in features
        ],
        "trend_only": [feature for feature in ["trend_distance_200d"] if feature in features],
        "volatility_liquidity_only": [
            feature
            for feature in [
                "realized_volatility_21d",
                "volume_surprise_20d",
                "average_dollar_volume_20d",
                "beta_252d",
            ]
            if feature in features
        ],
        "market_context_only": [
            feature
            for feature in ["market_breadth_200d", "cross_sectional_dispersion_21d"]
            if feature in features
        ],
    }
    group_rows: list[dict[str, Any]] = []
    for name, group_features in groups.items():
        if not group_features:
            continue
        preds = _run_custom_ridge(
            panel,
            targets,
            features=group_features,
            config=config,
            model_version=f"group_{name}",
        )
        metrics = _prediction_metrics(preds, top_k)
        group_rows.append(
            {
                "feature_group": name,
                "features_used": ";".join(group_features),
                **metrics,
                "mean_ic_delta_vs_all_features": metrics["mean_ic"] - all_feature_mean_ic,
            }
        )
    return pd.DataFrame(feature_rows), pd.DataFrame(group_rows)


def _sensitivity(
    panel: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    config: dict[str, Any],
    top_k: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = [feature for feature in CORE_FEATURE_COLUMNS if feature in panel.columns]
    phase23g_config = _deep_merge(DEFAULT_PHASE23G_CONFIG, config.get("phase23g_config", {}))
    alphas = [float(value) for value in phase23g_config.get("ridge_alpha_grid", [1.0])]
    regularization_rows: list[dict[str, Any]] = []
    for alpha in alphas:
        preds = _run_custom_ridge(
            panel,
            targets,
            features=features,
            config=config,
            model_version=f"ridge_alpha_{alpha:g}",
            alpha=alpha,
        )
        regularization_rows.append({"ridge_alpha": alpha, **_prediction_metrics(preds, top_k)})
    window_rows: list[dict[str, Any]] = []
    for window in [None, *list(config.get("rolling_training_windows", []))]:
        preds = _run_custom_ridge(
            panel,
            targets,
            features=features,
            config=config,
            model_version=("expanding_window" if window is None else f"rolling_{window}d"),
            rolling_training_window_dates=window,
        )
        window_rows.append(
            {
                "training_window_type": "expanding" if window is None else "rolling",
                "rolling_training_window_dates": window if window is not None else "",
                **_prediction_metrics(preds, top_k),
            }
        )
    return pd.DataFrame(regularization_rows), pd.DataFrame(window_rows)


def _rank_from_score(frame: pd.DataFrame, score_column: str, model_version: str) -> pd.DataFrame:
    diagnostic = frame.copy()
    diagnostic["model_version"] = model_version
    diagnostic["predicted_20d_excess_return_or_ranking_score"] = pd.to_numeric(
        diagnostic[score_column], errors="coerce"
    ).fillna(0.0)
    diagnostic["predicted_rank"] = diagnostic.groupby("decision_timestamp_utc")[
        "predicted_20d_excess_return_or_ranking_score"
    ].rank(ascending=False, method="first")
    return diagnostic


def _feature_ablation_from_oos_panel(
    predictions_panel: pd.DataFrame,
    *,
    all_feature_mean_ic: float,
    top_k: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Runtime-bounded ablation using OOS rows and same-date feature scores."""

    ridge = _model_predictions(predictions_panel, RIDGE_MODEL)
    features = [feature for feature in CORE_FEATURE_COLUMNS if feature in ridge.columns]
    zframe = _cross_sectional_zscore(ridge, features)
    feature_rows: list[dict[str, Any]] = []
    for feature in features:
        preds = _rank_from_score(zframe, feature, f"single_feature_{feature}")
        metrics = _prediction_metrics(preds, top_k)
        feature_rows.append(
            {
                "ablation_type": "single_feature_no_refit_oos_diagnostic",
                "feature_set_name": feature,
                "features_used": feature,
                "refit_performed": False,
                **metrics,
                "mean_ic_delta_vs_all_features": metrics["mean_ic"] - all_feature_mean_ic,
            }
        )
    for feature in features:
        remaining = [name for name in features if name != feature]
        temp = zframe.copy()
        temp["leave_one_feature_score"] = temp[remaining].mean(axis=1)
        preds = _rank_from_score(
            temp,
            "leave_one_feature_score",
            f"leave_one_out_{feature}",
        )
        metrics = _prediction_metrics(preds, top_k)
        feature_rows.append(
            {
                "ablation_type": "leave_one_feature_out_no_refit_oos_diagnostic",
                "feature_set_name": feature,
                "features_used": ";".join(remaining),
                "refit_performed": False,
                **metrics,
                "mean_ic_delta_vs_all_features": metrics["mean_ic"] - all_feature_mean_ic,
            }
        )
    groups = {
        "all_features": features,
        "momentum_only": [
            feature
            for feature in ["momentum_21d", "momentum_63d", "momentum_252d_skip21d"]
            if feature in features
        ],
        "trend_only": [feature for feature in ["trend_distance_200d"] if feature in features],
        "volatility_liquidity_only": [
            feature
            for feature in [
                "realized_volatility_21d",
                "volume_surprise_20d",
                "average_dollar_volume_20d",
                "beta_252d",
            ]
            if feature in features
        ],
        "market_context_only": [
            feature
            for feature in ["market_breadth_200d", "cross_sectional_dispersion_21d"]
            if feature in features
        ],
    }
    group_rows: list[dict[str, Any]] = []
    for name, group_features in groups.items():
        if not group_features:
            continue
        temp = zframe.copy()
        temp["feature_group_score"] = temp[group_features].mean(axis=1)
        preds = _rank_from_score(temp, "feature_group_score", f"group_{name}")
        metrics = _prediction_metrics(preds, top_k)
        group_rows.append(
            {
                "feature_group": name,
                "features_used": ";".join(group_features),
                "refit_performed": False,
                **metrics,
                "mean_ic_delta_vs_all_features": metrics["mean_ic"] - all_feature_mean_ic,
            }
        )
    return pd.DataFrame(feature_rows), pd.DataFrame(group_rows)


def _runtime_bounded_sensitivity(
    *,
    phase23g_metrics: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    phase23g_config = _deep_merge(DEFAULT_PHASE23G_CONFIG, config.get("phase23g_config", {}))
    ridge = phase23g_metrics.loc[phase23g_metrics["model_version"].eq(RIDGE_MODEL)]
    base_metrics = ridge.iloc[0].to_dict() if not ridge.empty else {}
    regularization_rows = []
    for alpha in phase23g_config.get("ridge_alpha_grid", [phase23g_config.get("ridge_alpha", 1.0)]):
        alpha = float(alpha)
        is_observed = alpha == float(phase23g_config.get("ridge_alpha", 1.0))
        regularization_rows.append(
            {
                "ridge_alpha": alpha,
                "sensitivity_type": "observed_phase23g" if is_observed else "pre_registered_not_refit_in_phase23h",
                "mean_ic": base_metrics.get("mean_ic") if is_observed else np.nan,
                "median_ic": base_metrics.get("median_ic") if is_observed else np.nan,
                "positive_ic_fraction": base_metrics.get("positive_ic_date_fraction") if is_observed else np.nan,
                "top_minus_bottom_rank_spread": base_metrics.get("top_minus_bottom_rank_spread") if is_observed else np.nan,
                "not_run_reason": "" if is_observed else "runtime-bounded Phase23H; not hyperparameter optimization",
            }
        )
    training_rows = [
        {
            "training_window_type": "expanding",
            "rolling_training_window_dates": "",
            "sensitivity_type": "observed_phase23g",
            "mean_ic": base_metrics.get("mean_ic"),
            "median_ic": base_metrics.get("median_ic"),
            "positive_ic_fraction": base_metrics.get("positive_ic_date_fraction"),
            "top_minus_bottom_rank_spread": base_metrics.get("top_minus_bottom_rank_spread"),
            "not_run_reason": "",
        }
    ]
    for window in config.get("rolling_training_windows", []):
        training_rows.append(
            {
                "training_window_type": "rolling",
                "rolling_training_window_dates": int(window),
                "sensitivity_type": "pre_registered_not_refit_in_phase23h",
                "mean_ic": np.nan,
                "median_ic": np.nan,
                "positive_ic_fraction": np.nan,
                "top_minus_bottom_rank_spread": np.nan,
                "not_run_reason": "runtime-bounded Phase23H; not production hyperparameter optimization",
            }
        )
    return pd.DataFrame(regularization_rows), pd.DataFrame(training_rows)


def _prediction_panel(predictions: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "panel_row_id",
        "sector_asof",
        "industry_asof",
        *[feature for feature in CORE_FEATURE_COLUMNS if feature in panel.columns],
    ]
    return predictions.merge(panel[columns], on="panel_row_id", how="left")


def _security_attribution(predictions: pd.DataFrame, top_k: int) -> pd.DataFrame:
    ridge = _model_predictions(predictions, RIDGE_MODEL)
    rows: list[dict[str, Any]] = []
    for security, group in ridge.groupby("permanent_security_id"):
        top_mask = group["predicted_rank"].le(top_k)
        bottom_mask = group["predicted_rank"].ge(group.groupby("decision_timestamp_utc")["predicted_rank"].transform("max") - top_k + 1)
        false_positive = top_mask & group["actual_20d_excess_return"].le(0)
        error = (
            pd.to_numeric(group["predicted_20d_excess_return_or_ranking_score"], errors="coerce")
            - pd.to_numeric(group["actual_20d_excess_return"], errors="coerce")
        )
        rows.append(
            {
                "permanent_security_id": security,
                "ticker": group["ticker"].iloc[0],
                "prediction_rows": len(group),
                "security_time_series_ic": _safe_spearman(
                    group["predicted_20d_excess_return_or_ranking_score"],
                    group["actual_20d_excess_return"],
                ),
                "average_predicted_rank": float(group["predicted_rank"].mean()),
                "average_actual_20d_excess_return": float(group["actual_20d_excess_return"].mean()),
                "top_k_frequency": float(top_mask.mean()),
                "bottom_k_frequency": float(bottom_mask.mean()),
                "top_k_hit_rate": (
                    float(group.loc[top_mask, "actual_20d_excess_return"].gt(0).mean())
                    if top_mask.any()
                    else np.nan
                ),
                "false_positive_rate": float(false_positive.mean()),
                "mean_absolute_prediction_error": float(error.abs().mean()),
            }
        )
    return pd.DataFrame(rows)


def _leave_one_security_out(predictions: pd.DataFrame, top_k: int) -> pd.DataFrame:
    ridge = _model_predictions(predictions, RIDGE_MODEL)
    full = _prediction_metrics(ridge, top_k)
    rows: list[dict[str, Any]] = []
    for security, group in ridge.groupby("permanent_security_id"):
        kept = ridge.loc[~ridge["permanent_security_id"].eq(security)].copy()
        metrics = _prediction_metrics(kept, top_k)
        rows.append(
            {
                "removed_permanent_security_id": security,
                "removed_ticker": group["ticker"].iloc[0],
                "removal_method": "evaluation_only_no_refit",
                **metrics,
                "mean_ic_change_vs_full": metrics["mean_ic"] - full["mean_ic"],
                "spread_change_vs_full": (
                    metrics["top_minus_bottom_rank_spread"]
                    - full["top_minus_bottom_rank_spread"]
                ),
            }
        )
    return pd.DataFrame(rows)


def _sector_diagnostics(predictions_panel: pd.DataFrame, top_k: int) -> pd.DataFrame:
    ridge = _model_predictions(predictions_panel, RIDGE_MODEL)
    rows: list[dict[str, Any]] = []
    for sector, group in ridge.groupby("sector_asof", dropna=False):
        top_mask = group["predicted_rank"].le(top_k)
        false_positive = top_mask & group["actual_20d_excess_return"].le(0)
        rows.append(
            {
                "sector_asof": sector,
                "prediction_rows": len(group),
                "top_k_selection_count": int(top_mask.sum()),
                "top_k_selection_frequency": float(top_mask.mean()),
                "average_forward_excess_return": float(group["actual_20d_excess_return"].mean()),
                "mean_prediction_rank": float(group["predicted_rank"].mean()),
                "false_positive_rate": float(false_positive.mean()),
                "within_sector_ic": (
                    _safe_spearman(
                        group["predicted_20d_excess_return_or_ranking_score"],
                        group["actual_20d_excess_return"],
                    )
                    if group["decision_timestamp_utc"].nunique() >= 3 and len(group) >= 10
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def _sector_neutral_comparison(predictions_panel: pd.DataFrame, top_k: int) -> pd.DataFrame:
    ridge = _model_predictions(predictions_panel, RIDGE_MODEL)
    neutral = ridge.copy()
    score = pd.to_numeric(
        neutral["predicted_20d_excess_return_or_ranking_score"], errors="coerce"
    )
    neutral["sector_neutral_score"] = score - score.groupby(
        [neutral["decision_timestamp_utc"], neutral["sector_asof"]]
    ).transform("mean")
    neutral["predicted_20d_excess_return_or_ranking_score"] = neutral["sector_neutral_score"]
    neutral["predicted_rank"] = neutral.groupby("decision_timestamp_utc")[
        "sector_neutral_score"
    ].rank(ascending=False, method="first")
    original = _prediction_metrics(ridge, top_k)
    neutral_metrics = _prediction_metrics(neutral, top_k)
    return pd.DataFrame(
        [
            {
                "diagnostic": "unconstrained_ranker",
                **original,
            },
            {
                "diagnostic": "sector_neutral_demeaned_prediction_scores",
                **neutral_metrics,
            },
        ]
    )


def _regime_diagnostics(predictions_panel: pd.DataFrame, top_k: int) -> pd.DataFrame:
    ridge = _model_predictions(predictions_panel, RIDGE_MODEL)
    if ridge.empty:
        return pd.DataFrame()
    date_context = (
        ridge.groupby("decision_timestamp_utc")
        .agg(
            market_breadth_200d=("market_breadth_200d", "mean"),
            realized_volatility_21d=("realized_volatility_21d", "mean"),
            cross_sectional_dispersion_21d=("cross_sectional_dispersion_21d", "mean"),
            trend_distance_200d=("trend_distance_200d", "mean"),
        )
        .reset_index()
    )
    thresholds = {
        "realized_volatility_21d": date_context["realized_volatility_21d"].median(),
        "cross_sectional_dispersion_21d": date_context[
            "cross_sectional_dispersion_21d"
        ].median(),
        "market_breadth_200d": date_context["market_breadth_200d"].median(),
    }
    context = ridge.merge(date_context, on="decision_timestamp_utc", suffixes=("", "_date"))
    buckets = {
        "spy_or_market_trend_positive": context["trend_distance_200d_date"].ge(0),
        "spy_or_market_trend_negative": context["trend_distance_200d_date"].lt(0),
        "high_realized_volatility": context["realized_volatility_21d_date"].ge(
            thresholds["realized_volatility_21d"]
        ),
        "low_realized_volatility": context["realized_volatility_21d_date"].lt(
            thresholds["realized_volatility_21d"]
        ),
        "strong_market_breadth": context["market_breadth_200d_date"].ge(
            thresholds["market_breadth_200d"]
        ),
        "weak_market_breadth": context["market_breadth_200d_date"].lt(
            thresholds["market_breadth_200d"]
        ),
        "high_cross_sectional_dispersion": context["cross_sectional_dispersion_21d_date"].ge(
            thresholds["cross_sectional_dispersion_21d"]
        ),
        "low_cross_sectional_dispersion": context["cross_sectional_dispersion_21d_date"].lt(
            thresholds["cross_sectional_dispersion_21d"]
        ),
    }
    rows: list[dict[str, Any]] = []
    for bucket, mask in buckets.items():
        group = context.loc[mask].copy()
        metrics = _prediction_metrics(group, top_k)
        rows.append(
            {
                "regime_bucket": bucket,
                "row_count": len(group),
                "date_count": group["decision_timestamp_utc"].nunique(),
                "tiny_bucket_warning": bool(group["decision_timestamp_utc"].nunique() < 8),
                **metrics,
            }
        )
    context["calendar_year"] = pd.to_datetime(context["signal_date"]).dt.year.astype(str)
    for year, group in context.groupby("calendar_year"):
        rows.append(
            {
                "regime_bucket": f"calendar_year_{year}",
                "row_count": len(group),
                "date_count": group["decision_timestamp_utc"].nunique(),
                "tiny_bucket_warning": bool(group["decision_timestamp_utc"].nunique() < 8),
                **_prediction_metrics(group, top_k),
            }
        )
    return pd.DataFrame(rows)


def _target_horizon_decay(
    predictions: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    top_k: int,
) -> pd.DataFrame:
    ridge = _model_predictions(predictions, RIDGE_MODEL)
    horizons = [1, 5, 20, 63]
    rows: list[dict[str, Any]] = []
    target_subset = targets.loc[
        targets["target_name"].isin(
            [f"forward_{horizon}d_excess_return_vs_universe" for horizon in horizons]
        )
    ].copy()
    for horizon in horizons:
        target_name = f"forward_{horizon}d_excess_return_vs_universe"
        merged = ridge.merge(
            target_subset.loc[
                target_subset["target_name"].eq(target_name),
                ["panel_row_id", "target_value"],
            ],
            on="panel_row_id",
            how="inner",
        )
        if merged.empty:
            rows.append(
                {
                    "target_horizon_trading_days": horizon,
                    "target_name": target_name,
                    "row_count": 0,
                    "mean_ic": np.nan,
                    "top_minus_bottom_rank_spread": np.nan,
                    "diagnostic_refit": False,
                    "signal_behavior": "unavailable",
                }
            )
            continue
        merged["actual_20d_excess_return"] = merged["target_value"]
        metrics = _prediction_metrics(merged, top_k)
        rows.append(
            {
                "target_horizon_trading_days": horizon,
                "target_name": target_name,
                "row_count": len(merged),
                **metrics,
                "diagnostic_refit": False,
                "signal_behavior": (
                    "positive_association"
                    if metrics["mean_ic"] > 0
                    else "negative_or_no_association"
                ),
            }
        )
    return pd.DataFrame(rows)


def _topk_diagnostics(
    predictions_panel: pd.DataFrame,
    *,
    top_values: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ridge = _model_predictions(predictions_panel, RIDGE_MODEL)
    rows: list[dict[str, Any]] = []
    false_rows: list[pd.DataFrame] = []
    max_rank = ridge.groupby("decision_timestamp_utc")["predicted_rank"].transform("max")
    for k in top_values:
        top_mask = ridge["predicted_rank"].le(k)
        bottom_mask = ridge["predicted_rank"].ge(max_rank - k + 1)
        for side, mask in [("top", top_mask), ("bottom", bottom_mask)]:
            group = ridge.loc[mask].copy()
            false_positive = group["actual_20d_excess_return"].le(0) if side == "top" else pd.Series(False, index=group.index)
            rows.append(
                {
                    "selection_bucket": f"{side}_{k}",
                    "row_count": len(group),
                    "date_count": group["decision_timestamp_utc"].nunique(),
                    "average_forward_excess_return": group[
                        "actual_20d_excess_return"
                    ].mean(),
                    "positive_alpha_hit_rate": group[
                        "actual_20d_excess_return"
                    ].gt(0).mean(),
                    "false_positive_count": int(false_positive.sum()),
                    "false_positive_rate": (
                        float(false_positive.mean()) if len(false_positive) else np.nan
                    ),
                }
            )
        false_cases = ridge.loc[top_mask & ridge["actual_20d_excess_return"].le(0)].copy()
        false_cases["top_k_definition"] = f"top_{k}"
        false_rows.append(false_cases)
    false_positive_cases = (
        pd.concat(false_rows, ignore_index=True) if false_rows else pd.DataFrame()
    )
    if not false_positive_cases.empty:
        keep_columns = [
            "decision_timestamp_utc",
            "signal_date",
            "permanent_security_id",
            "ticker",
            "sector_asof",
            "top_k_definition",
            "predicted_rank",
            "predicted_20d_excess_return_or_ranking_score",
            "actual_20d_excess_return",
            *[feature for feature in CORE_FEATURE_COLUMNS if feature in false_positive_cases.columns],
        ]
        false_positive_cases = false_positive_cases[keep_columns]
    return pd.DataFrame(rows), false_positive_cases


def _rank_turnover(predictions: pd.DataFrame, top_k: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model, model_frame in predictions.groupby("model_version"):
        ordered_dates = sorted(model_frame["decision_timestamp_utc"].unique())
        previous: pd.DataFrame | None = None
        top_sets: list[set[str]] = []
        for date in ordered_dates:
            current = model_frame.loc[model_frame["decision_timestamp_utc"].eq(date)].copy()
            current_top = set(
                current.sort_values("predicted_rank").head(top_k)["permanent_security_id"]
            )
            top_sets.append(current_top)
            if previous is None:
                previous = current
                continue
            merged = previous[["permanent_security_id", "predicted_rank", "predicted_20d_excess_return_or_ranking_score"]].merge(
                current[["permanent_security_id", "predicted_rank", "predicted_20d_excess_return_or_ranking_score"]],
                on="permanent_security_id",
                suffixes=("_previous", "_current"),
            )
            previous_top = set(
                previous.sort_values("predicted_rank").head(top_k)[
                    "permanent_security_id"
                ]
            )
            union = previous_top | current_top
            rows.append(
                {
                    "model_version": model,
                    "decision_timestamp_utc": date,
                    "spearman_rank_autocorrelation": _safe_spearman(
                        merged["predicted_rank_previous"],
                        merged["predicted_rank_current"],
                    ),
                    "top_k_entry_count": len(current_top - previous_top),
                    "top_k_exit_count": len(previous_top - current_top),
                    "top_k_membership_turnover": 1.0
                    - len(previous_top & current_top) / max(len(union), 1),
                    "full_rank_turnover": float(
                        (
                            merged["predicted_rank_current"]
                            - merged["predicted_rank_previous"]
                        ).abs().mean()
                    ),
                    "prediction_score_stability": _safe_spearman(
                        merged["predicted_20d_excess_return_or_ranking_score_previous"],
                        merged["predicted_20d_excess_return_or_ranking_score_current"],
                    ),
                }
            )
            previous = current
        security_persistence: dict[str, list[int]] = {}
        current_runs: dict[str, int] = {}
        for top_set in top_sets:
            for security in list(current_runs):
                if security not in top_set:
                    security_persistence.setdefault(security, []).append(current_runs.pop(security))
            for security in top_set:
                current_runs[security] = current_runs.get(security, 0) + 1
        for security, run in current_runs.items():
            security_persistence.setdefault(security, []).append(run)
        persistence_values = [run for runs in security_persistence.values() for run in runs]
        average_persistence = float(np.mean(persistence_values)) if persistence_values else np.nan
        for row in rows:
            if row["model_version"] == model:
                row["average_top_k_holding_persistence_dates"] = average_persistence
    return pd.DataFrame(rows)


def prediction_grain_audit(predictions: pd.DataFrame) -> pd.DataFrame:
    stock_dates = predictions[["decision_timestamp_utc", "permanent_security_id"]].drop_duplicates()
    model_count = predictions["model_version"].nunique() if "model_version" in predictions else 0
    date_count = predictions["decision_timestamp_utc"].nunique() if "decision_timestamp_utc" in predictions else 0
    security_count = predictions["permanent_security_id"].nunique() if "permanent_security_id" in predictions else 0
    total_rows = len(predictions)
    expected_rows = len(stock_dates) * model_count
    unique_key = not bool(
        predictions.duplicated(
            ["model_version", "decision_timestamp_utc", "permanent_security_id"]
        ).any()
    )
    return pd.DataFrame(
        [
            {
                "prediction_row_explanation": (
                    f"{date_count} dates x {security_count} securities x "
                    f"{model_count} models/baselines"
                ),
                "prediction_model_count": model_count,
                "test_dates": date_count,
                "securities": security_count,
                "unique_stock_date_observations": len(stock_dates),
                "total_model_prediction_rows": total_rows,
                "expected_model_prediction_rows": expected_rows,
                "row_count_matches_expected": total_rows == expected_rows,
                "model_date_security_unique": unique_key,
                "model_id_column": "model_version",
                "ridge_model_present": RIDGE_MODEL in set(predictions["model_version"]),
            }
        ]
    )


def _reconstruct_metrics(predictions: pd.DataFrame, top_k: int) -> pd.DataFrame:
    ic = _ic_by_date(predictions, top_k)
    rows: list[dict[str, Any]] = []
    for model, group in ic.groupby("model_version"):
        model_predictions = predictions.loc[predictions["model_version"].eq(model)]
        values = pd.to_numeric(group["spearman_information_coefficient"], errors="coerce")
        rows.append(
            {
                "model_version": model,
                "reconstructed_mean_ic": values.mean(),
                "reconstructed_median_ic": values.median(),
                "reconstructed_positive_ic_date_fraction": values.dropna().gt(0).mean(),
                "reconstructed_top_minus_bottom_rank_spread": group[
                    "top_minus_bottom_rank_spread"
                ].mean(),
                "reconstructed_prediction_coverage": model_predictions[
                    "actual_20d_excess_return"
                ].notna().mean(),
            }
        )
    return pd.DataFrame(rows)


def _phase23g_reconciliation(
    predictions: pd.DataFrame,
    phase23g_summary: pd.DataFrame,
    phase23g_metrics: pd.DataFrame,
    *,
    top_k: int,
    tolerance: float = 1e-10,
) -> pd.DataFrame:
    reconstructed = _reconstruct_metrics(predictions, top_k)
    rows: list[dict[str, Any]] = []
    metrics = phase23g_metrics.copy()
    for row in reconstructed.itertuples(index=False):
        model = row.model_version
        metric_row = metrics.loc[metrics["model_version"].eq(model)]
        if metric_row.empty:
            rows.append(
                {
                    "model_version": model,
                    "metric": "phase23g_metric_row_present",
                    "reconstructed_value": np.nan,
                    "phase23g_value": np.nan,
                    "absolute_difference": np.nan,
                    "within_tolerance": False,
                }
            )
            continue
        comparisons = {
            "mean_ic": row.reconstructed_mean_ic,
            "median_ic": row.reconstructed_median_ic,
            "positive_ic_date_fraction": row.reconstructed_positive_ic_date_fraction,
            "top_minus_bottom_rank_spread": row.reconstructed_top_minus_bottom_rank_spread,
            "prediction_coverage": row.reconstructed_prediction_coverage,
        }
        for metric, reconstructed_value in comparisons.items():
            phase_value = pd.to_numeric(metric_row[metric], errors="coerce").iloc[0]
            diff = abs(float(reconstructed_value) - float(phase_value)) if pd.notna(reconstructed_value) and pd.notna(phase_value) else 0.0
            rows.append(
                {
                    "model_version": model,
                    "metric": metric,
                    "reconstructed_value": reconstructed_value,
                    "phase23g_value": phase_value,
                    "absolute_difference": diff,
                    "within_tolerance": bool(diff <= tolerance),
                }
            )
    if not phase23g_summary.empty:
        summary_row = phase23g_summary.iloc[0]
        ridge = reconstructed.loc[reconstructed["model_version"].eq(RIDGE_MODEL)]
        if not ridge.empty:
            reconstructed_mean = ridge["reconstructed_mean_ic"].iloc[0]
            phase_value = pd.to_numeric(pd.Series([summary_row.get("mean_ic")]), errors="coerce").iloc[0]
            diff = abs(float(reconstructed_mean) - float(phase_value))
            rows.append(
                {
                    "model_version": RIDGE_MODEL,
                    "metric": "summary_mean_ic",
                    "reconstructed_value": reconstructed_mean,
                    "phase23g_value": phase_value,
                    "absolute_difference": diff,
                    "within_tolerance": bool(diff <= tolerance),
                }
            )
    return pd.DataFrame(rows)


def _integrity_gates(
    *,
    predictions: pd.DataFrame,
    panel: pd.DataFrame,
    targets: pd.DataFrame,
    folds: pd.DataFrame,
    grain: pd.DataFrame,
    reconciliation: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows.append(_gate("phase23g_predictions_present", not predictions.empty, f"rows={len(predictions)}"))
    rows.append(_gate("phase23f_panel_present", not panel.empty, f"rows={len(panel)}"))
    rows.append(_gate("phase23f_targets_present", not targets.empty, f"rows={len(targets)}"))
    rows.append(
        _gate(
            "prediction_grain_matches_model_date_security",
            bool(
                not grain.empty
                and grain.iloc[0]["row_count_matches_expected"]
                and grain.iloc[0]["model_date_security_unique"]
            ),
            "model_version x decision_timestamp_utc x permanent_security_id",
        )
    )
    rows.append(
        _gate(
            "model_identity_nonblank",
            bool(
                "model_version" in predictions.columns
                and predictions["model_version"].astype(str).str.strip().ne("").all()
            ),
            "Ridge, momentum baselines, technical composite, and null baseline",
        )
    )
    rows.append(
        _gate(
            "all_predictions_out_of_sample",
            bool(
                "prediction_is_out_of_sample" in predictions.columns
                and predictions["prediction_is_out_of_sample"].map(_bool_value).all()
            ),
            "prediction_is_out_of_sample=True",
        )
    )
    rows.append(
        _gate(
            "training_cutoff_not_after_prediction_timestamp",
            bool(
                (
                    pd.to_datetime(predictions["training_cutoff"], utc=True)
                    <= pd.to_datetime(predictions["decision_timestamp_utc"], utc=True)
                ).all()
            ),
            "Phase23G fits at the decision timestamp using purged prior labels only",
        )
    )
    rows.append(
        _gate(
            "purge_and_embargo_policy_recorded",
            bool(
                not folds.empty
                and folds["purge_window_trading_days"].astype(int).ge(
                    int(config["phase23g_config"]["purge_window_trading_days"])
                ).all()
                and folds["embargo_window_trading_days"].astype(int).ge(
                    int(config["phase23g_config"]["embargo_window_trading_days"])
                ).all()
                and (
                    pd.to_datetime(folds["purge_boundary_signal_date"])
                    < pd.to_datetime(folds["test_signal_date"])
                ).all()
            ),
            "63-trading-day purge and embargo policy recorded by Phase23G folds",
        )
    )
    target_columns = [
        column for column in panel.columns if column.startswith("forward_") or column.startswith("target_")
    ]
    rows.append(
        _gate(
            "no_target_derived_predictor_columns",
            not target_columns,
            "target-derived predictor columns=" + ";".join(target_columns),
        )
    )
    rows.append(
        _gate(
            "phase23g_metrics_reconstruct",
            bool(not reconciliation.empty and reconciliation["within_tolerance"].all()),
            "headline metrics recalculated from OOS predictions",
        )
    )
    rows.append(
        _gate(
            "overlapping_label_warning_recorded",
            True,
            "weekly decisions with 20-trading-day labels overlap; no IID inference used",
            critical=False,
        )
    )
    rows.append(_gate("live_trading_disabled", not _bool_value(config["live_trading_allowed"]), "no live trading"))
    rows.append(_gate("real_money_disabled", not _bool_value(config["real_money_allowed"]), "no real money"))
    rows.append(_gate("broker_api_disabled", not _bool_value(config["broker_api_integration_allowed"]), "no broker/API"))
    rows.append(_gate("promotion_disabled", not _bool_value(config["promotion_allowed"]), "no promotion"))
    report = pd.DataFrame(rows)
    report["all_critical_gates_passed"] = bool(report.loc[report["critical"], "passed"].all())
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def _failure_mode_register(
    *,
    summary: dict[str, Any],
    bootstrap: pd.DataFrame,
    permutation: pd.DataFrame,
    leave_one_out: pd.DataFrame,
) -> pd.DataFrame:
    rows = [
        {
            "failure_mode": "noncanonical_survivorship_biased_pilot_universe",
            "severity": "high",
            "evidence": NONCANONICAL_WARNING,
            "mitigation": "build canonical point-in-time universe before generalization claims",
        },
        {
            "failure_mode": "overlapping_20d_labels_weekly_cadence",
            "severity": "medium",
            "evidence": "20-trading-day labels overlap across weekly decision dates",
            "mitigation": "use date-level and block-bootstrap inference",
        },
        {
            "failure_mode": "technical_only_feature_set",
            "severity": "medium",
            "evidence": "fundamental, sentiment, analyst, and macro features are absent",
            "mitigation": "add only timestamp-audited feature families in later phases",
        },
    ]
    if not bootstrap.empty:
        ridge_boot = bootstrap.loc[bootstrap["model_version"].eq(RIDGE_MODEL)]
        if not ridge_boot.empty and ridge_boot["mean_ic_ci95_low"].iloc[0] <= 0:
            rows.append(
                {
                    "failure_mode": "ic_uncertainty_interval_crosses_zero",
                    "severity": "medium",
                    "evidence": "overlap-aware 95% IC interval includes zero",
                    "mitigation": "require prospective post-endpoint validation",
                }
            )
    if not permutation.empty:
        ridge_perm = permutation.loc[permutation["model_version"].eq(RIDGE_MODEL)]
        if not ridge_perm.empty and ridge_perm["empirical_one_sided_ic_p_value"].iloc[0] > 0.1:
            rows.append(
                {
                    "failure_mode": "weak_permutation_evidence",
                    "severity": "medium",
                    "evidence": "permutation p-value is not compelling on pilot data",
                    "mitigation": "do not promote; use as research diagnostic only",
                }
            )
    if not leave_one_out.empty:
        max_delta = leave_one_out["mean_ic_change_vs_full"].abs().max()
        if pd.notna(max_delta) and max_delta > 0.05:
            rows.append(
                {
                    "failure_mode": "single_security_sensitivity",
                    "severity": "medium",
                    "evidence": f"max leave-one-security IC change={max_delta:.4f}",
                    "mitigation": "expand canonical universe and monitor concentration",
                }
            )
    rows.append(
        {
            "failure_mode": "investable_performance_not_tested",
            "severity": "high",
            "evidence": str(summary),
            "mitigation": "separate cost-aware portfolio simulation must be preregistered later",
        }
    )
    return pd.DataFrame(rows)


def _prospective_holdout_protocol(config: dict[str, Any]) -> pd.DataFrame:
    frozen = {
        "model_version": config["model_version"],
        "primary_target": config["primary_target"],
        "feature_set": CORE_FEATURE_COLUMNS,
        "phase23g_config": config.get("phase23g_config", {}),
    }
    model_hash = sha256(repr(frozen).encode("utf-8")).hexdigest()
    rows = [
        ("canonical_research_endpoint", "2026-05-01"),
        ("post_endpoint_extension_label", "post_2026_05_01_prospective_extension"),
        ("frozen_model_hash", model_hash),
        ("frozen_model_version", str(config["model_version"])),
        ("frozen_primary_target", str(config["primary_target"])),
        ("minimum_future_observation_count", str(config["minimum_future_observation_count"])),
        ("future_metrics", "mean_ic;median_ic;positive_ic_fraction;rank_spread;top_k_hit_rate"),
        ("forbidden_changes", "features;alpha;preprocessing;ranking_rules"),
        ("promotion_policy", "no promotion based solely on pilot extension"),
        ("data_download_policy", "no new data download in Phase23H"),
    ]
    return pd.DataFrame(
        [
            {
                "protocol_item": item,
                "protocol_value": value,
                "protocol_status": "written",
                "research_pilot_only": True,
                "promotion_allowed": False,
            }
            for item, value in rows
        ]
    )


def _write_markdown(
    *,
    path: Path,
    summary: pd.DataFrame,
    gates: pd.DataFrame,
    stability: pd.DataFrame,
    failure_modes: pd.DataFrame,
) -> None:
    lines = [
        "# Phase 23H - Interpretable Ranker Robustness, Stability and Failure-Mode Analysis",
        "",
        "NO LIVE TRADING",
        "NO REAL MONEY",
        "NO BROKER/API",
        "NO STRATEGY PROMOTION",
        "RESEARCH PILOT ONLY",
        "",
        NONCANONICAL_WARNING,
        "",
        "This report treats Phase23G outputs as ranking diagnostics, not investable portfolio performance.",
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False) if not summary.empty else "No summary.",
        "",
        "## Gates",
        "",
        gates.to_markdown(index=False) if not gates.empty else "No gate report.",
        "",
        "## IC Stability",
        "",
        stability.to_markdown(index=False) if not stability.empty else "No stability metrics.",
        "",
        "## Failure Modes",
        "",
        failure_modes.to_markdown(index=False) if not failure_modes.empty else "No failure modes.",
        "",
        "Prospective holdout protocol is written separately and starts after the canonical 2026-05-01 research endpoint.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _blocked_outputs(
    *,
    output_dir: Path,
    dashboard_path: Path,
    decision: str,
    detail: str,
) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    gates = pd.DataFrame([_gate("phase23h_blocked", False, detail)])
    gates["all_critical_gates_passed"] = False
    gates["all_gates_passed"] = False
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23H",
                "decision": decision,
                "execution_gates_passed": False,
                "phase23g_integrity_passed": False,
                "blocking_detail": detail,
                "research_pilot_only": True,
                "paper_trading_allowed": False,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 23H",
                "decision": decision,
                "verdict": detail,
                "research_pilot_only": True,
                "promotion_allowed": False,
            }
        ]
    )
    dashboard = pd.DataFrame(
        [
            {
                "phase23h_decision": decision,
                "phase23g_integrity_passed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
                "notes": detail,
            }
        ]
    )
    _write_csv(summary, output_dir / "phase23h_summary.csv")
    _write_csv(gates, output_dir / "phase23h_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase23h_conclusion.csv")
    _write_csv(dashboard, dashboard_path)
    _write_markdown(
        path=output_dir / "phase23h_interpretable_ranker_robustness.md",
        summary=summary,
        gates=gates,
        stability=pd.DataFrame(),
        failure_modes=pd.DataFrame(),
    )
    return {"summary": summary, "gate_report": gates, "conclusion": conclusion, "dashboard": dashboard}


def save_phase23h_interpretable_ranker_robustness(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    phase_config = _phase_config(config)
    if not phase_config["enabled"]:
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}
    output_dir = _resolve_reports_path(
        configured_path=phase_config["output_dir"], reports_dir=reports_dir
    )
    phase23g_dir = _resolve_reports_path(
        configured_path=phase_config["source_phase23g_dir"], reports_dir=reports_dir
    )
    phase23f_dir = _resolve_reports_path(
        configured_path=phase_config["source_phase23f_dir"], reports_dir=reports_dir
    )
    dashboard_path = _resolve_reports_path(
        configured_path=phase_config["dashboard_status_path"], reports_dir=reports_dir
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)

    required = {
        "predictions": phase23g_dir / "phase23g_oos_predictions.csv",
        "phase23g_summary": phase23g_dir / "phase23g_summary.csv",
        "phase23g_metrics": phase23g_dir / "phase23g_cross_sectional_metrics.csv",
        "folds": phase23g_dir / "phase23g_walk_forward_folds.csv",
        "coefficients": phase23g_dir / "phase23g_feature_coefficients.csv",
        "coefficient_stability": phase23g_dir / "phase23g_coefficient_stability.csv",
        "panel": phase23f_dir / "phase23f_pilot_feature_panel.csv",
        "targets": phase23f_dir / "phase23f_pilot_targets.csv",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        return _blocked_outputs(
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23h_blocked_phase23g_integrity_failure",
            detail="missing required sources: " + ";".join(missing),
        )

    predictions = _read_csv(required["predictions"])
    phase23g_summary = _read_csv(required["phase23g_summary"])
    phase23g_metrics = _read_csv(required["phase23g_metrics"])
    folds = _read_csv(required["folds"])
    coefficient_stability = _read_csv(required["coefficient_stability"])
    panel = _read_csv(required["panel"])
    targets = _read_csv(required["targets"])
    top_k = int(phase_config["top_k"])

    grain = prediction_grain_audit(predictions)
    reconciliation = _phase23g_reconciliation(
        predictions,
        phase23g_summary,
        phase23g_metrics,
        top_k=top_k,
    )
    gates = _integrity_gates(
        predictions=predictions,
        panel=panel,
        targets=targets,
        folds=folds,
        grain=grain,
        reconciliation=reconciliation,
        config=phase_config,
    )
    phase23g_integrity_passed = bool(gates.loc[gates["critical"], "passed"].all())
    if not phase23g_integrity_passed:
        _write_csv(grain, output_dir / "phase23h_prediction_grain_audit.csv")
        _write_csv(reconciliation, output_dir / "phase23h_phase23g_reconciliation.csv")
        _write_csv(gates, output_dir / "phase23h_gate_report.csv")
        return _blocked_outputs(
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23h_blocked_phase23g_integrity_failure",
            detail="critical Phase23G integrity gate failed",
        )

    stock_dates = int(grain.iloc[0]["unique_stock_date_observations"])
    if stock_dates < int(phase_config["minimum_test_dates"]) * int(
        phase_config["minimum_security_count"]
    ):
        return _blocked_outputs(
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23h_blocked_insufficient_observations",
            detail="insufficient stock-date observations for robustness analysis",
        )

    ic = _ic_by_date(predictions, top_k)
    stability = _stability_from_ic(ic)
    rolling = _rolling_ic(ic)
    calendar = _calendar_period_metrics(ic)
    bootstrap = moving_block_bootstrap(
        ic,
        seed=int(phase_config["bootstrap_seed"]),
        samples=int(phase_config["bootstrap_samples"]),
        block_length=int(phase_config["bootstrap_block_length_dates"]),
    )
    permutation = permutation_test(
        predictions,
        seed=int(phase_config["permutation_seed"]),
        permutations=int(phase_config["permutation_count"]),
        top_k=top_k,
    )
    ridge_stability = stability.loc[stability["model_version"].eq(RIDGE_MODEL)]
    all_feature_mean_ic = (
        float(ridge_stability["mean_ic"].iloc[0]) if not ridge_stability.empty else np.nan
    )
    predictions_panel = _prediction_panel(predictions, panel)
    feature_ablation, group_ablation = _feature_ablation_from_oos_panel(
        predictions_panel,
        all_feature_mean_ic=all_feature_mean_ic,
        top_k=top_k,
    )
    regularization, training_window = _runtime_bounded_sensitivity(
        phase23g_metrics=phase23g_metrics,
        config=phase_config,
    )
    security = _security_attribution(predictions, top_k)
    leave_one = _leave_one_security_out(predictions, top_k)
    sector = _sector_diagnostics(predictions_panel, top_k)
    sector_neutral = _sector_neutral_comparison(predictions_panel, top_k)
    regime = _regime_diagnostics(predictions_panel, top_k)
    horizon_decay = _target_horizon_decay(predictions, targets, top_k=top_k)
    topk, false_cases = _topk_diagnostics(predictions_panel, top_values=[1, 3, 5])
    rank_turnover = _rank_turnover(predictions, top_k)
    protocol = _prospective_holdout_protocol(phase_config)

    ridge_boot = bootstrap.loc[bootstrap["model_version"].eq(RIDGE_MODEL)].iloc[0]
    ridge_perm = permutation.loc[permutation["model_version"].eq(RIDGE_MODEL)].iloc[0]
    ridge_sector = sector_neutral.loc[
        sector_neutral["diagnostic"].eq("sector_neutral_demeaned_prediction_scores")
    ].iloc[0]
    ridge_turnover = rank_turnover.loc[rank_turnover["model_version"].eq(RIDGE_MODEL)]
    strongest_feature = (
        feature_ablation.loc[
            feature_ablation["ablation_type"].astype(str).str.contains("single_feature")
        ].sort_values("mean_ic", ascending=False)["feature_set_name"].iloc[0]
        if not feature_ablation.empty
        else ""
    )
    weakest_feature = (
        feature_ablation.loc[
            feature_ablation["ablation_type"].astype(str).str.contains("single_feature")
        ].sort_values("mean_ic", ascending=True)["feature_set_name"].iloc[0]
        if not feature_ablation.empty
        else ""
    )
    most_influential = (
        leave_one.sort_values("mean_ic_change_vs_full", key=lambda s: s.abs(), ascending=False)[
            "removed_ticker"
        ].iloc[0]
        if not leave_one.empty
        else ""
    )
    max_leave_one_change = (
        float(leave_one["mean_ic_change_vs_full"].abs().max())
        if not leave_one.empty
        else np.nan
    )
    best_period = (
        calendar.loc[calendar["model_version"].eq(RIDGE_MODEL)]
        .sort_values("mean_ic", ascending=False)["calendar_period"]
        .iloc[0]
        if not calendar.empty
        else ""
    )
    worst_period = (
        calendar.loc[calendar["model_version"].eq(RIDGE_MODEL)]
        .sort_values("mean_ic", ascending=True)["calendar_period"]
        .iloc[0]
        if not calendar.empty
        else ""
    )
    rank_turnover_mean = (
        float(ridge_turnover["top_k_membership_turnover"].mean())
        if not ridge_turnover.empty
        else np.nan
    )
    stable_signal = (
        float(ridge_boot["mean_ic_ci95_low"]) > 0
        and float(ridge_perm["empirical_one_sided_ic_p_value"]) <= 0.1
    )
    if stable_signal:
        decision = "phase23h_robustness_completed_signal_stable_research_only"
    elif float(ridge_stability["mean_ic"].iloc[0]) > 0:
        decision = "phase23h_robustness_completed_signal_fragile_research_only"
    else:
        decision = "phase23h_robustness_completed_no_reliable_signal"

    summary_dict = {
        "phase": "Phase 23H",
        "decision": decision,
        "execution_gates_passed": True,
        "phase23g_integrity_passed": phase23g_integrity_passed,
        "prediction_model_count": int(grain.iloc[0]["prediction_model_count"]),
        "unique_stock_date_observations": stock_dates,
        "total_model_prediction_rows": int(grain.iloc[0]["total_model_prediction_rows"]),
        "test_dates": int(grain.iloc[0]["test_dates"]),
        "securities": int(grain.iloc[0]["securities"]),
        "observed_mean_ic": float(ridge_stability["mean_ic"].iloc[0]),
        "overlap_aware_95_ic_low": float(ridge_boot["mean_ic_ci95_low"]),
        "overlap_aware_95_ic_high": float(ridge_boot["mean_ic_ci95_high"]),
        "bootstrap_probability_mean_ic_above_zero": float(
            ridge_boot["bootstrap_probability_mean_ic_above_zero"]
        ),
        "permutation_ic_p_value": float(ridge_perm["empirical_one_sided_ic_p_value"]),
        "observed_rank_spread": float(ridge_boot["observed_spread"]),
        "overlap_aware_spread_95_low": float(ridge_boot["spread_ci95_low"]),
        "overlap_aware_spread_95_high": float(ridge_boot["spread_ci95_high"]),
        "best_calendar_period": best_period,
        "worst_calendar_period": worst_period,
        "strongest_feature": strongest_feature,
        "weakest_feature": weakest_feature,
        "most_influential_security": most_influential,
        "maximum_leave_one_security_out_ic_change": max_leave_one_change,
        "sector_neutral_ic": float(ridge_sector["mean_ic"]),
        "rank_turnover": rank_turnover_mean,
        "prospective_holdout_protocol_written": True,
        "membership_canonical": False,
        "market_data_canonical": False,
        "research_pilot_only": True,
        "generalization_claim_allowed": False,
        "investable_performance_claim_allowed": False,
        "model_training_allowed": False,
        "paper_trading_allowed": False,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
        "promotion_allowed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    failure_modes = _failure_mode_register(
        summary=summary_dict,
        bootstrap=bootstrap,
        permutation=permutation,
        leave_one_out=leave_one,
    )
    summary = pd.DataFrame([summary_dict])
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 23H",
                "decision": decision,
                "verdict": (
                    "Phase23G ranking diagnostics were robust enough for further research "
                    "review, but remain noncanonical and non-investable."
                    if decision != "phase23h_robustness_completed_no_reliable_signal"
                    else "Phase23G did not show reliable enough pilot evidence."
                ),
                "can_prove": "robustness diagnostics on controlled noncanonical pilot predictions",
                "cannot_prove": "investable performance, canonical generalization, paper readiness, or promotion",
                "paper_trading_allowed": False,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    dashboard = pd.DataFrame(
        [
            {
                "phase23h_decision": decision,
                "phase23g_integrity_passed": phase23g_integrity_passed,
                "observed_mean_ic": summary_dict["observed_mean_ic"],
                "overlap_aware_95_ic_low": summary_dict["overlap_aware_95_ic_low"],
                "overlap_aware_95_ic_high": summary_dict["overlap_aware_95_ic_high"],
                "permutation_ic_p_value": summary_dict["permutation_ic_p_value"],
                "rank_turnover": rank_turnover_mean,
                "research_pilot_only": True,
                "paper_trading_allowed": False,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": NONCANONICAL_WARNING,
            }
        ]
    )

    outputs = {
        "summary": summary,
        "gate_report": gates,
        "phase23g_reconciliation": reconciliation,
        "prediction_grain_audit": grain,
        "ic_stability": stability,
        "rolling_ic": rolling,
        "calendar_period_metrics": calendar,
        "overlap_aware_bootstrap": bootstrap,
        "permutation_test": permutation,
        "feature_ablation": feature_ablation,
        "feature_group_ablation": group_ablation,
        "regularization_sensitivity": regularization,
        "training_window_sensitivity": training_window,
        "security_attribution": security,
        "leave_one_security_out": leave_one,
        "sector_diagnostics": sector,
        "sector_neutral_comparison": sector_neutral,
        "regime_diagnostics": regime,
        "target_horizon_decay": horizon_decay,
        "topk_diagnostics": topk,
        "false_positive_cases": false_cases,
        "rank_turnover": rank_turnover,
        "coefficient_stability": coefficient_stability,
        "failure_mode_register": failure_modes,
        "prospective_holdout_protocol": protocol,
        "conclusion": conclusion,
    }
    for name, frame in outputs.items():
        _write_csv(frame, output_dir / f"phase23h_{name}.csv")
    _write_csv(dashboard, dashboard_path)
    _write_markdown(
        path=output_dir / "phase23h_interpretable_ranker_robustness.md",
        summary=summary,
        gates=gates,
        stability=stability,
        failure_modes=failure_modes,
    )
    print("Wrote Phase 23H interpretable ranker robustness reports.")
    return outputs | {"dashboard": dashboard}
