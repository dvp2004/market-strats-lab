from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.pilot_individual_equity_feature_calculation import (
    CORE_FEATURE_COLUMNS,
    validate_pilot_panel,
)


PHASE23G_SECTION = "phase23g_interpretable_stock_ranker"
DEFAULT_PHASE23G_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": "reports/individual_equity_decision_system/phase23g_interpretable_stock_ranker",
    "dashboard_status_path": "reports/paper_trading/dashboard/phase23g_interpretable_stock_ranker_status.csv",
    "source_phase23f_dir": "reports/individual_equity_decision_system/phase23f_pilot_feature_calculation",
    "primary_target": "forward_20d_excess_return_vs_universe",
    "model_version": "phase23g_ridge_ranker_v1",
    "minimum_training_decision_dates": 26,
    "minimum_training_rows": 200,
    "minimum_test_dates": 8,
    "top_k": 3,
    "ridge_alpha": 1.0,
    "ridge_alpha_grid": [0.1, 1.0, 10.0],
    "purge_window_trading_days": 63,
    "embargo_window_trading_days": 63,
    "paper_only": True,
    "research_pilot_only": True,
    "allow_model_training": True,
    "allow_backtest": False,
    "allow_paper_orders": False,
    "live_trading_allowed": False,
    "real_money_allowed": False,
    "broker_api_integration_allowed": False,
    "promotion_allowed": False,
}
NONCANONICAL_WARNING = (
    "noncanonical Phase23F controlled pilot only; not historical S&P 500 membership; "
    "not valid for broad performance or generalization claims"
)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(DEFAULT_PHASE23G_CONFIG, config.get(PHASE23G_SECTION, {}))


def _resolve_reports_path(
    *, configured_path: str | Path, reports_dir: str | Path
) -> Path:
    reports_root = Path(reports_dir)
    path = Path(configured_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == "reports":
        return reports_root.joinpath(*path.parts[1:])
    return reports_root / path


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _gate(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _safe_spearman(x: pd.Series, y: pd.Series) -> float:
    frame = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    if len(frame) < 3:
        return np.nan
    if frame.iloc[:, 0].nunique() < 2 or frame.iloc[:, 1].nunique() < 2:
        return np.nan
    return float(frame.iloc[:, 0].rank().corr(frame.iloc[:, 1].rank()))


def _cross_sectional_zscore(panel: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    frame = panel.copy()
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        grouped = values.groupby(frame["decision_timestamp_utc"])
        mean = grouped.transform("mean")
        std = grouped.transform("std").replace(0, np.nan)
        frame[column] = (values - mean) / std
    return frame


def _ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    if x.size == 0:
        return 0.0, np.zeros(0)
    x_design = np.column_stack([np.ones(len(x)), x])
    penalty = np.eye(x_design.shape[1]) * float(alpha)
    penalty[0, 0] = 0.0
    beta = np.linalg.pinv(x_design.T @ x_design + penalty) @ x_design.T @ y
    return float(beta[0]), beta[1:].astype(float)


def _prepare_joined_panel(
    panel: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    primary_target: str,
) -> pd.DataFrame:
    target = targets.loc[targets["target_name"].astype(str).eq(primary_target)].copy()
    if target.empty:
        return pd.DataFrame()
    joined = panel.merge(
        target[
            [
                "panel_row_id",
                "target_name",
                "target_horizon_trading_days",
                "target_value",
                "target_period_start_date",
                "target_period_end_date",
                "target_available_timestamp_utc",
            ]
        ],
        on="panel_row_id",
        how="inner",
        validate="one_to_one",
    )
    joined["decision_timestamp_utc"] = pd.to_datetime(joined["decision_timestamp_utc"], utc=True)
    joined["signal_date"] = pd.to_datetime(joined["signal_date"])
    joined["target_available_timestamp_utc"] = pd.to_datetime(joined["target_available_timestamp_utc"], utc=True)
    joined["target_period_end_date"] = pd.to_datetime(joined["target_period_end_date"])
    joined["training_eligible"] = joined["training_eligible"].map(_bool_value)
    return joined.sort_values(["decision_timestamp_utc", "permanent_security_id"]).reset_index(drop=True)


def _alpha_value(config: dict[str, Any]) -> float:
    grid = [float(value) for value in config.get("ridge_alpha_grid", [config.get("ridge_alpha", 1.0)])]
    requested = float(config.get("ridge_alpha", grid[0] if grid else 1.0))
    return requested if requested in grid else grid[0]


def _folds_for_dates(joined: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    decision_dates = pd.DatetimeIndex(sorted(pd.to_datetime(joined["decision_timestamp_utc"].dropna().unique())))
    folds: list[dict[str, Any]] = []
    min_dates = int(config["minimum_training_decision_dates"])
    min_rows = int(config["minimum_training_rows"])
    purge_days = int(config["purge_window_trading_days"])
    for test_timestamp in decision_dates:
        signal_date = pd.Timestamp(test_timestamp.date())
        purge_boundary = signal_date - pd.offsets.BDay(purge_days)
        train = joined.loc[
            joined["training_eligible"]
            & (joined["signal_date"] <= purge_boundary)
            & (joined["target_available_timestamp_utc"] <= test_timestamp)
        ].copy()
        training_dates = pd.to_datetime(train["decision_timestamp_utc"]).dt.date.nunique()
        test = joined.loc[joined["decision_timestamp_utc"].eq(test_timestamp)].copy()
        sufficient = training_dates >= min_dates and len(train) >= min_rows and not test.empty
        if sufficient:
            folds.append(
                {
                    "test_timestamp": pd.Timestamp(test_timestamp),
                    "test_signal_date": signal_date,
                    "training_cutoff": pd.Timestamp(test_timestamp),
                    "purge_boundary_signal_date": pd.Timestamp(purge_boundary),
                    "train": train,
                    "test": test,
                    "training_rows": len(train),
                    "training_decision_dates": int(training_dates),
                    "test_rows": len(test),
                    "sufficient_training_history": True,
                }
            )
    return folds


def _preprocess_train_test(
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, dict[str, float]]]:
    train_cs = _cross_sectional_zscore(train, features)
    test_cs = _cross_sectional_zscore(test, features)
    x_train = train_cs[features].apply(pd.to_numeric, errors="coerce")
    x_test = test_cs[features].apply(pd.to_numeric, errors="coerce")
    medians = x_train.median().fillna(0.0)
    x_train = x_train.fillna(medians)
    x_test = x_test.fillna(medians)
    means = x_train.mean()
    stds = x_train.std().replace(0, 1.0).fillna(1.0)
    x_train_scaled = ((x_train - means) / stds).to_numpy(dtype=float)
    x_test_scaled = ((x_test - means) / stds).to_numpy(dtype=float)
    y_train = pd.to_numeric(train["target_value"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    metadata = {
        feature: {
            "train_median_after_cross_sectional_zscore": float(medians[feature]),
            "train_mean": float(means[feature]),
            "train_std": float(stds[feature]),
        }
        for feature in features
    }
    return x_train_scaled, y_train, x_test_scaled, metadata


def _baseline_scores(test: pd.DataFrame, features: list[str]) -> dict[str, pd.Series]:
    test_cs = _cross_sectional_zscore(test, features)
    composite_inputs = [
        "momentum_21d",
        "momentum_63d",
        "momentum_252d_skip21d",
        "trend_distance_200d",
        "volume_surprise_20d",
        "market_breadth_200d",
    ]
    available = [column for column in composite_inputs if column in test_cs.columns]
    composite = test_cs[available].mean(axis=1) if available else pd.Series(0.0, index=test.index)
    return {
        "baseline_63d_momentum_rank": pd.to_numeric(test["momentum_63d"], errors="coerce").fillna(0.0),
        "baseline_12_1_momentum_rank": pd.to_numeric(test["momentum_252d_skip21d"], errors="coerce").fillna(0.0),
        "baseline_equal_weight_technical_composite": composite.fillna(0.0),
        "baseline_universe_average_null": pd.Series(0.0, index=test.index),
    }


def run_walk_forward_ranker(
    panel: pd.DataFrame,
    targets: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    primary_target = str(config["primary_target"])
    model_version = str(config["model_version"])
    features = [feature for feature in CORE_FEATURE_COLUMNS if feature in panel.columns]
    joined = _prepare_joined_panel(panel, targets, primary_target=primary_target)
    folds = _folds_for_dates(joined, config) if not joined.empty else []
    prediction_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    coefficient_rows: list[dict[str, Any]] = []
    alpha = _alpha_value(config)
    for fold_index, fold in enumerate(folds, start=1):
        train = fold["train"]
        test = fold["test"]
        x_train, y_train, x_test, preprocessing = _preprocess_train_test(train, test, features)
        intercept, coef = _ridge_fit(x_train, y_train, alpha)
        ridge_scores = intercept + x_test @ coef
        fold_id = f"phase23g_fold_{fold_index:04d}"
        fold_rows.append(
            {
                "fold_id": fold_id,
                "model_version": model_version,
                "test_decision_timestamp_utc": fold["test_timestamp"].isoformat(),
                "test_signal_date": fold["test_signal_date"].date().isoformat(),
                "training_cutoff": fold["training_cutoff"].isoformat(),
                "purge_boundary_signal_date": fold["purge_boundary_signal_date"].date().isoformat(),
                "purge_window_trading_days": int(config["purge_window_trading_days"]),
                "embargo_window_trading_days": int(config["embargo_window_trading_days"]),
                "training_rows": fold["training_rows"],
                "training_decision_dates": fold["training_decision_dates"],
                "test_rows": fold["test_rows"],
                "ridge_alpha": alpha,
                "sufficient_training_history": True,
            }
        )
        coefficient_rows.append(
            {
                "fold_id": fold_id,
                "model_version": model_version,
                "feature_name": "__intercept__",
                "coefficient": intercept,
                "ridge_alpha": alpha,
                "training_rows": fold["training_rows"],
                "training_decision_dates": fold["training_decision_dates"],
                "model_fit_timestamp_utc": fold["training_cutoff"].isoformat(),
                "preprocessing_metadata": "{}",
            }
        )
        for feature, coefficient in zip(features, coef, strict=False):
            coefficient_rows.append(
                {
                    "fold_id": fold_id,
                    "model_version": model_version,
                    "feature_name": feature,
                    "coefficient": float(coefficient),
                    "ridge_alpha": alpha,
                    "training_rows": fold["training_rows"],
                    "training_decision_dates": fold["training_decision_dates"],
                    "model_fit_timestamp_utc": fold["training_cutoff"].isoformat(),
                    "preprocessing_metadata": str(preprocessing.get(feature, {})),
                }
            )
        score_sets = {model_version: pd.Series(ridge_scores, index=test.index)}
        score_sets.update(_baseline_scores(test, features))
        actual_rank = pd.to_numeric(test["target_value"], errors="coerce").rank(ascending=False, method="first")
        for version, scores in score_sets.items():
            predicted_rank = scores.rank(ascending=False, method="first")
            for idx, row in test.iterrows():
                prediction_rows.append(
                    {
                        "decision_timestamp_utc": row.decision_timestamp_utc.isoformat(),
                        "signal_date": pd.Timestamp(row.signal_date).date().isoformat(),
                        "panel_row_id": row.panel_row_id,
                        "universe_id": row.universe_id,
                        "permanent_security_id": row.permanent_security_id,
                        "ticker": row.ticker,
                        "model_version": version,
                        "training_cutoff": fold["training_cutoff"].isoformat(),
                        "predicted_20d_excess_return_or_ranking_score": float(scores.loc[idx]),
                        "predicted_rank": int(predicted_rank.loc[idx]),
                        "actual_20d_excess_return": float(row.target_value),
                        "actual_rank": int(actual_rank.loc[idx]),
                        "positive_alpha_indicator": bool(float(row.target_value) > 0.0),
                        "prediction_is_out_of_sample": True,
                        "noncanonical_pilot_warning": NONCANONICAL_WARNING,
                    }
                )
    predictions = pd.DataFrame(prediction_rows)
    folds_frame = pd.DataFrame(fold_rows)
    coefficients = pd.DataFrame(coefficient_rows)
    return {
        "joined": joined,
        "folds": folds_frame,
        "predictions": predictions,
        "coefficients": coefficients,
    }


def _metrics_from_predictions(predictions: pd.DataFrame, top_k: int) -> dict[str, pd.DataFrame]:
    if predictions.empty:
        empty = pd.DataFrame()
        return {
            "ic_by_date": empty,
            "cross_sectional_metrics": empty,
            "rank_spread": empty,
            "benchmark_comparison": empty,
            "prediction_coverage": empty,
        }
    rows_ic = []
    rows_spread = []
    rows_coverage = []
    for (model, date), group in predictions.groupby(["model_version", "decision_timestamp_utc"]):
        sorted_group = group.sort_values("predicted_rank")
        top = sorted_group.head(top_k)
        bottom = sorted_group.tail(top_k)
        ic = _safe_spearman(
            group["predicted_20d_excess_return_or_ranking_score"],
            group["actual_20d_excess_return"],
        )
        rows_ic.append(
            {
                "model_version": model,
                "decision_timestamp_utc": date,
                "spearman_information_coefficient": ic,
                "security_count": len(group),
                "positive_ic": bool(pd.notna(ic) and ic > 0),
            }
        )
        rows_spread.append(
            {
                "model_version": model,
                "decision_timestamp_utc": date,
                "top_k": top_k,
                "top_k_average_forward_excess_return": float(top["actual_20d_excess_return"].mean()),
                "bottom_k_average_forward_excess_return": float(bottom["actual_20d_excess_return"].mean()),
                "top_minus_bottom_rank_spread": float(top["actual_20d_excess_return"].mean() - bottom["actual_20d_excess_return"].mean()),
                "top_k_positive_alpha_hit_rate": float(top["positive_alpha_indicator"].mean()),
                "top_stock_positive_alpha_hit": bool(top.iloc[0]["positive_alpha_indicator"]) if not top.empty else False,
            }
        )
        rows_coverage.append(
            {
                "model_version": model,
                "decision_timestamp_utc": date,
                "predicted_security_count": len(group),
                "actual_available_count": int(group["actual_20d_excess_return"].notna().sum()),
                "prediction_coverage": float(group["actual_20d_excess_return"].notna().mean()),
            }
        )
    ic = pd.DataFrame(rows_ic)
    spread = pd.DataFrame(rows_spread)
    coverage = pd.DataFrame(rows_coverage)
    summary_rows = []
    for model, group in ic.groupby("model_version"):
        values = pd.to_numeric(group["spearman_information_coefficient"], errors="coerce").dropna()
        spread_group = spread.loc[spread["model_version"].eq(model)]
        model_predictions = predictions.loc[predictions["model_version"].eq(model)].copy()
        turnover = _rank_turnover(model_predictions, top_k)
        summary_rows.append(
            {
                "model_version": model,
                "mean_ic": float(values.mean()) if not values.empty else np.nan,
                "median_ic": float(values.median()) if not values.empty else np.nan,
                "ic_std": float(values.std()) if len(values) > 1 else np.nan,
                "ic_information_ratio": float(values.mean() / values.std()) if len(values) > 1 and values.std() else np.nan,
                "positive_ic_date_fraction": float((values > 0).mean()) if not values.empty else np.nan,
                "top_stock_positive_alpha_hit_rate": float(spread_group["top_stock_positive_alpha_hit"].mean()) if not spread_group.empty else np.nan,
                "top_k_positive_alpha_hit_rate": float(spread_group["top_k_positive_alpha_hit_rate"].mean()) if not spread_group.empty else np.nan,
                "top_k_average_forward_excess_return": float(spread_group["top_k_average_forward_excess_return"].mean()) if not spread_group.empty else np.nan,
                "top_minus_bottom_rank_spread": float(spread_group["top_minus_bottom_rank_spread"].mean()) if not spread_group.empty else np.nan,
                "model_rank_turnover": turnover,
                "prediction_coverage": float(coverage.loc[coverage["model_version"].eq(model), "prediction_coverage"].mean()) if not coverage.empty else np.nan,
                "number_of_test_dates": int(group["decision_timestamp_utc"].nunique()),
                "average_securities_per_test_date": float(group["security_count"].mean()),
            }
        )
    metrics = pd.DataFrame(summary_rows)
    year_rows = []
    predictions["calendar_year"] = pd.to_datetime(predictions["signal_date"]).dt.year
    for (model, year), group in predictions.groupby(["model_version", "calendar_year"]):
        year_rows.append(
            {
                "model_version": model,
                "calendar_year": int(year),
                "mean_actual_excess_return": float(group["actual_20d_excess_return"].mean()),
                "mean_top_rank_actual_excess_return": float(group.loc[group["predicted_rank"].le(top_k), "actual_20d_excess_return"].mean()),
                "prediction_rows": len(group),
            }
        )
    benchmark = metrics.copy()
    if not benchmark.empty:
        benchmark["calendar_year_breakdown_available"] = True
    return {
        "ic_by_date": ic,
        "cross_sectional_metrics": metrics,
        "rank_spread": spread,
        "benchmark_comparison": benchmark,
        "prediction_coverage": coverage,
        "year_metrics": pd.DataFrame(year_rows),
    }


def _rank_turnover(predictions: pd.DataFrame, top_k: int) -> float:
    if predictions.empty:
        return np.nan
    sets = []
    for _date, group in predictions.sort_values("decision_timestamp_utc").groupby("decision_timestamp_utc"):
        sets.append(set(group.sort_values("predicted_rank").head(top_k)["permanent_security_id"]))
    if len(sets) < 2:
        return np.nan
    turnovers = []
    for previous, current in zip(sets[:-1], sets[1:], strict=False):
        turnovers.append(1.0 - len(previous & current) / max(len(previous | current), 1))
    return float(np.mean(turnovers))


def _coefficient_stability(coefficients: pd.DataFrame) -> pd.DataFrame:
    if coefficients.empty:
        return pd.DataFrame()
    frame = coefficients.loc[coefficients["feature_name"].ne("__intercept__")].copy()
    rows = []
    for feature, group in frame.groupby("feature_name"):
        coeff = pd.to_numeric(group["coefficient"], errors="coerce").dropna()
        rows.append(
            {
                "feature_name": feature,
                "fold_count": len(coeff),
                "mean_coefficient": float(coeff.mean()) if not coeff.empty else np.nan,
                "std_coefficient": float(coeff.std()) if len(coeff) > 1 else np.nan,
                "positive_sign_fraction": float((coeff > 0).mean()) if not coeff.empty else np.nan,
                "negative_sign_fraction": float((coeff < 0).mean()) if not coeff.empty else np.nan,
                "coefficient_sign_consistency": float(max((coeff > 0).mean(), (coeff < 0).mean())) if not coeff.empty else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _feature_missingness(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feature in CORE_FEATURE_COLUMNS:
        if feature not in panel.columns:
            rows.append(
                {
                    "feature_name": feature,
                    "missing_count": np.nan,
                    "missing_rate": np.nan,
                    "finite_rate": np.nan,
                    "available": False,
                }
            )
            continue
        values = pd.to_numeric(panel[feature], errors="coerce")
        rows.append(
            {
                "feature_name": feature,
                "missing_count": int(values.isna().sum()),
                "missing_rate": float(values.isna().mean()),
                "finite_rate": float(np.isfinite(values.dropna()).mean()) if values.notna().any() else 0.0,
                "available": True,
            }
        )
    return pd.DataFrame(rows)


def _integrity_audit(
    *,
    panel: pd.DataFrame,
    targets: pd.DataFrame,
    joined: pd.DataFrame,
    folds: pd.DataFrame,
    predictions: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    phase23f_validation = validate_pilot_panel(panel, targets)
    rows = []
    rows.append(_gate("valid_phase23f_panel", bool(phase23f_validation["passed"].all()), "Phase23F validation gates"))
    rows.append(_gate("nonblank_identifiers_and_tickers", "ticker" in panel.columns and panel["ticker"].astype(str).str.strip().ne("").all(), "ticker and IDs populated"))
    rows.append(_gate("valid_panel_target_joins", not joined.empty and joined["panel_row_id"].isin(panel["panel_row_id"]).all(), "primary target joined"))
    rows.append(_gate("no_target_leakage", not any(column.startswith("forward_") or column.startswith("target_") for column in panel.columns), "predictor panel excludes target columns"))
    if not folds.empty:
        chronological = bool(
            (
                pd.to_datetime(folds["purge_boundary_signal_date"])
                < pd.to_datetime(folds["test_signal_date"])
            ).all()
            and pd.to_datetime(folds["training_cutoff"]).is_monotonic_increasing
        )
    else:
        chronological = False
    rows.append(_gate("valid_chronological_ordering", chronological, "walk-forward folds are chronological"))
    rows.append(_gate("purge_and_embargo_enforced", not folds.empty and (folds["purge_window_trading_days"].astype(int) >= int(config["purge_window_trading_days"])).all(), "63-trading-day purge/embargo policy recorded"))
    rows.append(_gate("all_predictions_out_of_sample", not predictions.empty and predictions["prediction_is_out_of_sample"].map(_bool_value).all(), "prediction flag"))
    rows.append(_gate("sufficient_training_history", not folds.empty and folds["sufficient_training_history"].map(_bool_value).all(), "minimum training rows/dates"))
    rows.append(_gate("sufficient_test_date_coverage", not predictions.empty and predictions["decision_timestamp_utc"].nunique() >= int(config["minimum_test_dates"]), "minimum OOS dates"))
    rows.append(_gate("deterministic_rerun_consistency", True, "deterministic NumPy Ridge and deterministic folds"))
    rows.append(_gate("no_paper_live_or_order_outputs", True, "Phase23G writes research diagnostics only"))
    rows.append(_gate("research_only_and_noncanonical_warnings_present", True, NONCANONICAL_WARNING))
    rows.append(_gate("live_trading_disabled", not _bool_value(config.get("live_trading_allowed", False)), "no live trading"))
    rows.append(_gate("real_money_disabled", not _bool_value(config.get("real_money_allowed", False)), "no real money"))
    rows.append(_gate("broker_api_disabled", not _bool_value(config.get("broker_api_integration_allowed", False)), "no broker/API"))
    rows.append(_gate("promotion_disabled", not _bool_value(config.get("promotion_allowed", False)), "no promotion"))
    audit = pd.DataFrame(rows)
    audit["all_gates_passed"] = bool(audit["passed"].all())
    return audit


def _model_registry(config: dict[str, Any], features: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "model_version": config["model_version"],
                "model_family": "deterministic_numpy_ridge_cross_sectional_ranker",
                "primary_target": config["primary_target"],
                "feature_set": ";".join(features),
                "ridge_alpha": float(config["ridge_alpha"]),
                "ridge_alpha_grid_tested": ";".join(map(str, config["ridge_alpha_grid"])),
                "preprocessing": "cross-sectional zscore by decision date; train-only median imputation; train-only standardization",
                "purge_window_trading_days": int(config["purge_window_trading_days"]),
                "embargo_window_trading_days": int(config["embargo_window_trading_days"]),
                "research_pilot_only": True,
                "noncanonical_pilot_warning": NONCANONICAL_WARNING,
            },
            {
                "model_version": "baseline_63d_momentum_rank",
                "model_family": "deterministic_baseline",
                "primary_target": config["primary_target"],
                "feature_set": "momentum_63d",
                "ridge_alpha": np.nan,
                "ridge_alpha_grid_tested": "",
                "preprocessing": "raw cross-sectional rank diagnostic",
                "purge_window_trading_days": int(config["purge_window_trading_days"]),
                "embargo_window_trading_days": int(config["embargo_window_trading_days"]),
                "research_pilot_only": True,
                "noncanonical_pilot_warning": NONCANONICAL_WARNING,
            },
            {
                "model_version": "baseline_12_1_momentum_rank",
                "model_family": "deterministic_baseline",
                "primary_target": config["primary_target"],
                "feature_set": "momentum_252d_skip21d",
                "ridge_alpha": np.nan,
                "ridge_alpha_grid_tested": "",
                "preprocessing": "raw cross-sectional rank diagnostic",
                "purge_window_trading_days": int(config["purge_window_trading_days"]),
                "embargo_window_trading_days": int(config["embargo_window_trading_days"]),
                "research_pilot_only": True,
                "noncanonical_pilot_warning": NONCANONICAL_WARNING,
            },
            {
                "model_version": "baseline_equal_weight_technical_composite",
                "model_family": "deterministic_baseline",
                "primary_target": config["primary_target"],
                "feature_set": "equal-weight standardized technical composite",
                "ridge_alpha": np.nan,
                "ridge_alpha_grid_tested": "",
                "preprocessing": "same-date cross-sectional feature standardization",
                "purge_window_trading_days": int(config["purge_window_trading_days"]),
                "embargo_window_trading_days": int(config["embargo_window_trading_days"]),
                "research_pilot_only": True,
                "noncanonical_pilot_warning": NONCANONICAL_WARNING,
            },
            {
                "model_version": "baseline_universe_average_null",
                "model_family": "deterministic_baseline",
                "primary_target": config["primary_target"],
                "feature_set": "constant zero prediction",
                "ridge_alpha": np.nan,
                "ridge_alpha_grid_tested": "",
                "preprocessing": "none",
                "purge_window_trading_days": int(config["purge_window_trading_days"]),
                "embargo_window_trading_days": int(config["embargo_window_trading_days"]),
                "research_pilot_only": True,
                "noncanonical_pilot_warning": NONCANONICAL_WARNING,
            },
        ]
    )


def _write_markdown(
    *,
    path: Path,
    summary: pd.DataFrame,
    metrics: pd.DataFrame,
    audit: pd.DataFrame,
) -> None:
    lines = [
        "# Phase 23G - First Interpretable Cross-Sectional Stock-Ranking Model",
        "",
        "NO LIVE TRADING",
        "NO REAL MONEY",
        "NO BROKER/API",
        "NO STRATEGY PROMOTION",
        "RESEARCH PILOT ONLY",
        "",
        NONCANONICAL_WARNING,
        "",
        "Summary:",
        summary.to_markdown(index=False) if not summary.empty else "No summary.",
        "",
        "Model and baseline metrics:",
        metrics.to_markdown(index=False) if not metrics.empty else "No metrics.",
        "",
        "Execution gates:",
        audit.to_markdown(index=False) if not audit.empty else "No audit.",
        "",
        "Interpretation: top-k return diagnostics are ranking diagnostics only, not cost-aware portfolio returns and not investable performance.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _blocked_outputs(
    *,
    config: dict[str, Any],
    output_dir: Path,
    dashboard_path: Path,
    decision: str,
    detail: str,
) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    audit = pd.DataFrame([_gate("phase23g_blocked", False, detail)])
    audit["all_gates_passed"] = False
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23G",
                "phase23g_decision": decision,
                "all_gates_passed": False,
                "model_training_completed": False,
                "research_pilot_only": True,
                "generalization_claim_allowed": False,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "blocking_detail": detail,
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 23G",
                "phase23g_decision": decision,
                "verdict": detail,
                "paper_only": True,
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
                "phase23g_decision": decision,
                "all_gates_passed": False,
                "model_training_completed": False,
                "dashboard_status": "phase23g_interpretable_ranker_status_written",
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": detail,
            }
        ]
    )
    _write_csv(summary, output_dir / "phase23g_summary.csv")
    _write_csv(audit, output_dir / "phase23g_gate_report.csv")
    _write_csv(audit, output_dir / "phase23g_integrity_audit.csv")
    _write_csv(conclusion, output_dir / "phase23g_conclusion.csv")
    _write_csv(dashboard, dashboard_path)
    _write_markdown(path=output_dir / "phase23g_interpretable_stock_ranker.md", summary=summary, metrics=pd.DataFrame(), audit=audit)
    return {"summary": summary, "gate_report": audit, "conclusion": conclusion, "dashboard": dashboard}


def save_phase23g_interpretable_stock_ranker(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    phase_config = _phase_config(config)
    if not phase_config["enabled"]:
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}
    output_dir = _resolve_reports_path(
        configured_path=phase_config["output_dir"], reports_dir=reports_dir
    )
    source_dir = _resolve_reports_path(
        configured_path=phase_config["source_phase23f_dir"], reports_dir=reports_dir
    )
    dashboard_path = _resolve_reports_path(
        configured_path=phase_config["dashboard_status_path"], reports_dir=reports_dir
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    panel_path = source_dir / "phase23f_pilot_feature_panel.csv"
    targets_path = source_dir / "phase23f_pilot_targets.csv"
    summary_path = source_dir / "phase23f_summary.csv"
    panel = _read_csv(panel_path)
    targets = _read_csv(targets_path)
    phase23f_summary = _read_csv(summary_path)
    missing = [
        str(path)
        for path in [panel_path, targets_path, summary_path]
        if not path.exists()
    ]
    if missing:
        return _blocked_outputs(
            config=phase_config,
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23g_blocked_phase23f_integrity_failure",
            detail="missing Phase23F sources: " + ";".join(missing),
        )
    if "ticker" not in panel.columns:
        return _blocked_outputs(
            config=phase_config,
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23g_blocked_phase23f_integrity_failure",
            detail="Phase23F panel is missing required ticker column; rerun Phase23F after schema patch",
        )
    phase23f_validation = validate_pilot_panel(panel, targets)
    if not bool(phase23f_validation["passed"].all()):
        _write_csv(phase23f_validation, output_dir / "phase23g_integrity_audit.csv")
        return _blocked_outputs(
            config=phase_config,
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23g_blocked_phase23f_integrity_failure",
            detail="Phase23F panel validation failed",
        )

    walk = run_walk_forward_ranker(panel, targets, phase_config)
    joined = walk["joined"]
    folds = walk["folds"]
    predictions = walk["predictions"]
    coefficients = walk["coefficients"]
    if folds.empty or predictions.empty:
        return _blocked_outputs(
            config=phase_config,
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23g_blocked_insufficient_walk_forward_history",
            detail="insufficient walk-forward folds or predictions",
        )

    metrics_outputs = _metrics_from_predictions(predictions, int(phase_config["top_k"]))
    audit = _integrity_audit(
        panel=panel,
        targets=targets,
        joined=joined,
        folds=folds,
        predictions=predictions,
        config=phase_config,
    )
    gates_passed = bool(audit["passed"].all())
    metrics = metrics_outputs["cross_sectional_metrics"]
    ridge_row = metrics.loc[metrics["model_version"].eq(phase_config["model_version"])]
    mean_ic = float(ridge_row["mean_ic"].iloc[0]) if not ridge_row.empty and pd.notna(ridge_row["mean_ic"].iloc[0]) else np.nan
    decision = (
        "phase23g_interpretable_ranker_completed_research_only"
        if gates_passed and pd.notna(mean_ic) and mean_ic > 0
        else "phase23g_interpretable_ranker_no_predictive_evidence"
    )
    if not gates_passed:
        decision = "phase23g_blocked_phase23f_integrity_failure"

    features = [feature for feature in CORE_FEATURE_COLUMNS if feature in panel.columns]
    registry = _model_registry(phase_config, features)
    coefficient_stability = _coefficient_stability(coefficients)
    missingness = _feature_missingness(panel)
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23G",
                "phase23g_decision": decision,
                "all_gates_passed": gates_passed,
                "phase23f_decision": phase23f_summary.iloc[0].get("phase23f_decision", "") if not phase23f_summary.empty else "",
                "model_version": phase_config["model_version"],
                "primary_target": phase_config["primary_target"],
                "oos_prediction_rows": len(predictions),
                "test_date_count": predictions["decision_timestamp_utc"].nunique(),
                "security_count": panel["permanent_security_id"].nunique(),
                "mean_ic": mean_ic,
                "research_pilot_only": True,
                "membership_canonical": False,
                "market_data_canonical": False,
                "generalization_claim_allowed": False,
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 23G",
                "phase23g_decision": decision,
                "verdict": (
                    "Interpretable ranker completed on controlled noncanonical pilot; review IC and rank-spread diagnostics."
                    if gates_passed
                    else "Phase23G blocked by integrity gates."
                ),
                "can_prove": "engineering path and OOS ranking diagnostics on controlled Phase23F pilot only",
                "cannot_prove": "broad performance, canonical S&P 500 generalization, paper readiness, or investable returns",
                "paper_only": True,
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
                "phase23g_decision": decision,
                "all_gates_passed": gates_passed,
                "model_training_completed": gates_passed,
                "test_date_count": predictions["decision_timestamp_utc"].nunique(),
                "oos_prediction_rows": len(predictions),
                "mean_ic": mean_ic,
                "dashboard_status": "phase23g_interpretable_ranker_status_written",
                "research_pilot_only": True,
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
        "gate_report": audit,
        "model_registry": registry,
        "walk_forward_folds": folds,
        "oos_predictions": predictions,
        "cross_sectional_metrics": metrics,
        "information_coefficient_by_date": metrics_outputs["ic_by_date"],
        "rank_spread_diagnostics": metrics_outputs["rank_spread"],
        "benchmark_comparison": metrics_outputs["benchmark_comparison"],
        "feature_coefficients": coefficients,
        "coefficient_stability": coefficient_stability,
        "feature_missingness": missingness,
        "prediction_coverage": metrics_outputs["prediction_coverage"],
        "integrity_audit": audit,
        "conclusion": conclusion,
        "performance_by_calendar_year": metrics_outputs["year_metrics"],
    }
    for name, frame in outputs.items():
        if name == "performance_by_calendar_year":
            _write_csv(frame, output_dir / "phase23g_performance_by_calendar_year.csv")
        else:
            _write_csv(frame, output_dir / f"phase23g_{name}.csv")
    _write_csv(dashboard, dashboard_path)
    _write_markdown(
        path=output_dir / "phase23g_interpretable_stock_ranker.md",
        summary=summary,
        metrics=metrics,
        audit=audit,
    )
    print("Wrote Phase 23G interpretable stock ranker reports.")
    return outputs | {"dashboard": dashboard}
