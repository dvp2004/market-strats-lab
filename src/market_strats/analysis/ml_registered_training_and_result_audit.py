from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, label_binarize


DEFAULT_PHASE13U_CONFIG: dict[str, Any] = {
    "enabled": False,
    "execution_role": (
        "Registered baseline ML training execution and train/validation "
        "evaluation only"
    ),
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13T",
    "proposed_next_phase": "Phase 13V",
    "allow_model_training": True,
    "allow_train_only_preprocessing_fit": True,
    "allow_train_validation_evaluation": True,
    "allow_validation_prediction_generation": True,
    "allow_holdout_prediction_generation": False,
    "allow_model_selection": False,
    "allow_feature_importance": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "dataset_policy": {},
    "training_policy": {},
    "model_registry": [],
    "metric_policy": {},
    "phase13v_boundary": {},
    "gates": {
        "require_phase13t_passed": True,
        "require_source_reports_present": True,
        "require_dataset_loaded": True,
        "require_dataset_label": True,
        "require_feature_matrix_created": True,
        "require_train_validation_rows": True,
        "require_registered_models_trained": True,
        "min_trained_models": 5,
        "require_train_validation_metrics": True,
        "require_validation_predictions_only": True,
        "require_confusion_matrices": True,
        "require_calibration_reports": True,
        "require_class_support_reports": True,
        "require_baseline_comparison_report": True,
        "require_no_holdout_predictions": True,
        "require_no_feature_importance": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "require_phase13v_boundary_quality_audit_only": True,
        "required_execution_role": (
            "Registered baseline ML training execution and train/validation "
            "evaluation only"
        ),
    },
}


DEFAULT_PHASE13V_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "ML training result quality and leakage audit only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13U",
    "proposed_next_phase": "Phase 13W",
    "allow_holdout_prediction_generation": False,
    "allow_model_selection": False,
    "allow_feature_importance": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "phase13u_reports": {},
    "quality_thresholds": {},
    "phase13w_boundary": {},
    "gates": {
        "require_phase13u_reports_present": True,
        "require_phase13u_conclusion_passed": True,
        "require_phase13u_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_training_outputs_quality": True,
        "require_metrics_quality": True,
        "require_validation_predictions_only": True,
        "require_forbidden_outputs_absent": True,
        "require_no_holdout_predictions": True,
        "require_no_feature_importance": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "require_phase13w_boundary_interpretation_only": True,
        "required_audit_role": "ML training result quality and leakage audit only",
    },
}


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


def _get_phase13u_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13U_CONFIG,
        config.get("phase13u_registered_baseline_ml_training", {}),
    )


def _get_phase13v_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13V_CONFIG,
        config.get("phase13v_ml_training_result_quality_audit", {}),
    )


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()

    if clean in {"true", "1", "yes", "y"}:
        return True

    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False

    return bool(value)


def _read_csv_if_exists(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _safe_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def build_phase13u_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("source_reports", {}).items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "report_key": str(report_key),
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": int(len(frame)),
            }
        )

    out = pd.DataFrame(rows)

    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})

    return out


def build_phase13u_phase13t_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13t_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13t_gate_report", ""))

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_report_passed = (
        not gate_report.empty
        and "passed" in gate_report.columns
        and bool(gate_report["passed"].map(_bool_value).all())
    )

    out = pd.DataFrame(
        [
            {
                "check": "Phase 13T conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13T gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _feature_columns(dataset: pd.DataFrame, phase_config: dict[str, Any]) -> tuple[list[str], list[str]]:
    policy = phase_config.get("dataset_policy", {})
    prefixes = policy.get("feature_prefixes", {})
    numeric_prefixes = tuple(str(item) for item in _as_list(prefixes.get("numeric")))
    categorical_prefixes = tuple(
        str(item) for item in _as_list(prefixes.get("categorical"))
    )
    forbidden_fragments = [
        str(item).lower() for item in _as_list(policy.get("forbidden_feature_fragments"))
    ]

    numeric_cols = [
        str(col)
        for col in dataset.columns
        if str(col).startswith(numeric_prefixes)
        and not any(fragment in str(col).lower() for fragment in forbidden_fragments)
    ]
    categorical_cols = [
        str(col)
        for col in dataset.columns
        if str(col).startswith(categorical_prefixes)
        and not any(fragment in str(col).lower() for fragment in forbidden_fragments)
    ]

    return numeric_cols, categorical_cols


def build_phase13u_dataset_profile(
    *,
    dataset: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame(
            [
                {
                    "rows": 0,
                    "dataset_label": "",
                    "numeric_feature_columns": 0,
                    "categorical_feature_columns": 0,
                    "target_column": "",
                    "train_rows": 0,
                    "validation_rows": 0,
                    "holdout_rows": 0,
                }
            ]
        )

    policy = phase_config.get("dataset_policy", {})
    target = str(policy.get("primary_target_id", "future_63d_spy_return_state"))
    numeric_cols, categorical_cols = _feature_columns(dataset, phase_config)

    split_counts = (
        dataset["split_label"].astype(str).value_counts().to_dict()
        if "split_label" in dataset.columns
        else {}
    )

    return pd.DataFrame(
        [
            {
                "rows": int(len(dataset)),
                "dataset_label": str(dataset["dataset_label"].iloc[0])
                if "dataset_label" in dataset.columns
                else "",
                "numeric_feature_columns": int(len(numeric_cols)),
                "categorical_feature_columns": int(len(categorical_cols)),
                "target_column": target,
                "train_rows": int(split_counts.get(policy.get("train_split_label", "train"), 0)),
                "validation_rows": int(
                    split_counts.get(policy.get("validation_split_label", "validation"), 0)
                ),
                "holdout_rows": int(
                    split_counts.get(policy.get("holdout_split_label", "holdout"), 0)
                ),
            }
        ]
    )


def _model_rows(
    *,
    dataset: pd.DataFrame,
    split_label: str,
    target_col: str,
    target_available_col: str,
    unavailable_class: str,
) -> pd.DataFrame:
    frame = dataset[dataset["split_label"].astype(str).eq(split_label)].copy()
    frame = frame[frame[target_available_col].map(_bool_value)]
    frame = frame[~frame[target_col].astype(str).eq(unavailable_class)]
    return frame.reset_index(drop=True)


def build_phase13u_feature_matrix_profile(
    *,
    dataset: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    policy = phase_config.get("dataset_policy", {})
    target_col = str(policy.get("primary_target_id", "future_63d_spy_return_state"))
    target_available_col = str(policy.get("target_available_column", "target_available"))
    unavailable_class = str(policy.get("unavailable_target_class", "unavailable"))
    train_label = str(policy.get("train_split_label", "train"))
    validation_label = str(policy.get("validation_split_label", "validation"))

    numeric_cols, categorical_cols = _feature_columns(dataset, phase_config)
    train = _model_rows(
        dataset=dataset,
        split_label=train_label,
        target_col=target_col,
        target_available_col=target_available_col,
        unavailable_class=unavailable_class,
    )
    validation = _model_rows(
        dataset=dataset,
        split_label=validation_label,
        target_col=target_col,
        target_available_col=target_available_col,
        unavailable_class=unavailable_class,
    )

    return pd.DataFrame(
        [
            {
                "numeric_feature_columns": int(len(numeric_cols)),
                "categorical_feature_columns": int(len(categorical_cols)),
                "total_feature_columns": int(len(numeric_cols) + len(categorical_cols)),
                "train_model_rows": int(len(train)),
                "validation_model_rows": int(len(validation)),
                "train_target_classes": "; ".join(
                    sorted(train[target_col].dropna().astype(str).unique())
                ),
                "validation_target_classes": "; ".join(
                    sorted(validation[target_col].dropna().astype(str).unique())
                ),
                "holdout_rows_used": 0,
                "holdout_predictions_generated": False,
            }
        ]
    )


def _make_model(model_config: dict[str, Any], random_state: int) -> Any:
    model_type = str(model_config.get("model_type", ""))

    if model_type == "dummy_most_frequent":
        return DummyClassifier(strategy="most_frequent")

    if model_type == "dummy_stratified":
        return DummyClassifier(strategy="stratified", random_state=random_state)

    if model_type == "logistic_regression":
        return LogisticRegression(
            max_iter=int(model_config.get("max_iter", 1000)),
            class_weight="balanced",
            random_state=random_state,
        )

    if model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=int(model_config.get("n_estimators", 300)),
            max_depth=int(model_config.get("max_depth", 4)),
            min_samples_leaf=int(model_config.get("min_samples_leaf", 20)),
            class_weight="balanced",
            random_state=random_state,
            n_jobs=-1,
        )

    if model_type == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_iter=int(model_config.get("max_iter", 150)),
            learning_rate=float(model_config.get("learning_rate", 0.05)),
            max_leaf_nodes=int(model_config.get("max_leaf_nodes", 15)),
            random_state=random_state,
        )

    raise ValueError(f"Unsupported registered model_type: {model_type}")


def _make_preprocessor(numeric_cols: list[str], categorical_cols: list[str]) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", _safe_one_hot_encoder()),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, numeric_cols),
            ("categorical", categorical_pipeline, categorical_cols),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )


def _classification_metrics(
    *,
    model_id: str,
    split_label: str,
    y_true: pd.Series,
    y_pred: np.ndarray,
    labels: list[str],
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "split_label": split_label,
        "rows": int(len(y_true)),
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_precision": precision_score(
            y_true,
            y_pred,
            labels=labels,
            average="macro",
            zero_division=0,
        ),
        "macro_recall": recall_score(
            y_true,
            y_pred,
            labels=labels,
            average="macro",
            zero_division=0,
        ),
        "macro_f1": f1_score(
            y_true,
            y_pred,
            labels=labels,
            average="macro",
            zero_division=0,
        ),
        "weighted_f1": f1_score(
            y_true,
            y_pred,
            labels=labels,
            average="weighted",
            zero_division=0,
        ),
        "model_selected": False,
        "trading_signal_created": False,
    }


def _aligned_proba(
    *,
    model: Pipeline,
    x_frame: pd.DataFrame,
    labels: list[str],
) -> np.ndarray | None:
    if not hasattr(model, "predict_proba"):
        return None

    probabilities = model.predict_proba(x_frame)
    model_classes = [str(item) for item in model.classes_]
    aligned = np.zeros((len(x_frame), len(labels)))

    for idx, label in enumerate(labels):
        if label in model_classes:
            aligned[:, idx] = probabilities[:, model_classes.index(label)]

    row_sums = aligned.sum(axis=1)
    non_zero = row_sums > 0
    aligned[non_zero] = aligned[non_zero] / row_sums[non_zero, None]
    return aligned


def _calibration_rows(
    *,
    model_id: str,
    split_label: str,
    y_true: pd.Series,
    probabilities: np.ndarray | None,
    labels: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if probabilities is None or len(y_true) == 0:
        return rows

    y_true_str = y_true.astype(str).to_numpy()
    y_binary = label_binarize(y_true_str, classes=labels)

    try:
        logloss_value = log_loss(y_true_str, probabilities, labels=labels)
    except ValueError:
        logloss_value = np.nan

    brier_values = []
    for class_idx, label in enumerate(labels):
        if y_binary.shape[1] <= class_idx:
            continue

        y_class = y_binary[:, class_idx]
        proba_class = probabilities[:, class_idx]

        try:
            brier = brier_score_loss(y_class, proba_class)
            prob_true, prob_pred = calibration_curve(
                y_class,
                proba_class,
                n_bins=5,
                strategy="uniform",
            )
            calibration_bins = len(prob_true)
        except ValueError:
            brier = np.nan
            calibration_bins = 0

        brier_values.append(brier)
        rows.append(
            {
                "model_id": model_id,
                "split_label": split_label,
                "class_label": label,
                "log_loss": logloss_value,
                "brier_score_ovr": brier,
                "calibration_bins": calibration_bins,
            }
        )

    return rows


def _confusion_rows(
    *,
    model_id: str,
    split_label: str,
    y_true: pd.Series,
    y_pred: np.ndarray,
    labels: list[str],
) -> list[dict[str, Any]]:
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    rows: list[dict[str, Any]] = []

    for true_idx, true_label in enumerate(labels):
        for pred_idx, pred_label in enumerate(labels):
            rows.append(
                {
                    "model_id": model_id,
                    "split_label": split_label,
                    "true_label": true_label,
                    "predicted_label": pred_label,
                    "count": int(matrix[true_idx, pred_idx]),
                }
            )

    return rows


def _class_support_rows(
    *,
    model_id: str,
    split_label: str,
    y_true: pd.Series,
    labels: list[str],
) -> list[dict[str, Any]]:
    counts = y_true.astype(str).value_counts().to_dict()
    total = len(y_true)

    return [
        {
            "model_id": model_id,
            "split_label": split_label,
            "class_label": label,
            "support": int(counts.get(label, 0)),
            "support_ratio": float(counts.get(label, 0) / total) if total else 0.0,
        }
        for label in labels
    ]


def _build_validation_prediction_rows(
    *,
    model_id: str,
    validation: pd.DataFrame,
    target_col: str,
    y_pred: np.ndarray,
    probabilities: np.ndarray | None,
    labels: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for idx, prediction in enumerate(y_pred):
        row = {
            "model_id": model_id,
            "split_label": "validation",
            "decision_date": validation.iloc[idx].get("decision_date", ""),
            "actual_class": validation.iloc[idx][target_col],
            "predicted_class": prediction,
            "holdout_prediction": False,
            "signal_created": False,
        }

        if probabilities is not None:
            for class_idx, label in enumerate(labels):
                row[f"probability_{label}"] = probabilities[idx, class_idx]

        rows.append(row)

    return rows


def run_phase13u_registered_training(
    *,
    dataset: pd.DataFrame,
    phase_config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    policy = phase_config.get("dataset_policy", {})
    training_policy = phase_config.get("training_policy", {})
    labels = [str(item) for item in _as_list(policy.get("allowed_target_classes"))]
    random_state = int(training_policy.get("random_state", 42))
    target_col = str(policy.get("primary_target_id", "future_63d_spy_return_state"))
    target_available_col = str(policy.get("target_available_column", "target_available"))
    unavailable_class = str(policy.get("unavailable_target_class", "unavailable"))

    train = _model_rows(
        dataset=dataset,
        split_label=str(policy.get("train_split_label", "train")),
        target_col=target_col,
        target_available_col=target_available_col,
        unavailable_class=unavailable_class,
    )
    validation = _model_rows(
        dataset=dataset,
        split_label=str(policy.get("validation_split_label", "validation")),
        target_col=target_col,
        target_available_col=target_available_col,
        unavailable_class=unavailable_class,
    )

    numeric_cols, categorical_cols = _feature_columns(dataset, phase_config)
    feature_cols = numeric_cols + categorical_cols

    x_train = train[feature_cols]
    y_train = train[target_col].astype(str)
    x_validation = validation[feature_cols]
    y_validation = validation[target_col].astype(str)

    execution_rows: list[dict[str, Any]] = []
    preprocessing_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []

    for model_config in _as_list(phase_config.get("model_registry")):
        if not _bool_value(model_config.get("enabled", False)):
            continue

        model_id = str(model_config["model_id"])
        model_type = str(model_config["model_type"])
        model = _make_model(model_config, random_state)
        preprocessor = _make_preprocessor(numeric_cols, categorical_cols)

        pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("model", model),
            ]
        )
        pipeline.fit(x_train, y_train)

        train_pred = pipeline.predict(x_train)
        validation_pred = pipeline.predict(x_validation)
        validation_proba = _aligned_proba(
            model=pipeline,
            x_frame=x_validation,
            labels=labels,
        )

        execution_rows.append(
            {
                "model_id": model_id,
                "model_type": model_type,
                "trained": True,
                "train_rows": int(len(train)),
                "validation_rows": int(len(validation)),
                "holdout_rows_used": 0,
                "holdout_predictions_generated": False,
                "model_selected": False,
                "feature_importance_calculated": False,
                "signal_created": False,
            }
        )
        preprocessing_rows.append(
            {
                "model_id": model_id,
                "fit_scope": "train_only",
                "numeric_feature_columns": int(len(numeric_cols)),
                "categorical_feature_columns": int(len(categorical_cols)),
                "transform_validation_with_train_fitted_pipeline": True,
                "holdout_transformed": False,
            }
        )

        metric_rows.append(
            _classification_metrics(
                model_id=model_id,
                split_label="train",
                y_true=y_train,
                y_pred=train_pred,
                labels=labels,
            )
        )
        metric_rows.append(
            _classification_metrics(
                model_id=model_id,
                split_label="validation",
                y_true=y_validation,
                y_pred=validation_pred,
                labels=labels,
            )
        )
        confusion_rows.extend(
            _confusion_rows(
                model_id=model_id,
                split_label="train",
                y_true=y_train,
                y_pred=train_pred,
                labels=labels,
            )
        )
        confusion_rows.extend(
            _confusion_rows(
                model_id=model_id,
                split_label="validation",
                y_true=y_validation,
                y_pred=validation_pred,
                labels=labels,
            )
        )
        calibration_rows.extend(
            _calibration_rows(
                model_id=model_id,
                split_label="validation",
                y_true=y_validation,
                probabilities=validation_proba,
                labels=labels,
            )
        )
        support_rows.extend(
            _class_support_rows(
                model_id=model_id,
                split_label="train",
                y_true=y_train,
                labels=labels,
            )
        )
        support_rows.extend(
            _class_support_rows(
                model_id=model_id,
                split_label="validation",
                y_true=y_validation,
                labels=labels,
            )
        )
        prediction_rows.extend(
            _build_validation_prediction_rows(
                model_id=model_id,
                validation=validation,
                target_col=target_col,
                y_pred=validation_pred,
                probabilities=validation_proba,
                labels=labels,
            )
        )

    return {
        "model_registry_execution_report": pd.DataFrame(execution_rows),
        "preprocessing_pipeline_report": pd.DataFrame(preprocessing_rows),
        "train_validation_metric_report": pd.DataFrame(metric_rows),
        "confusion_matrix_report": pd.DataFrame(confusion_rows),
        "calibration_report": pd.DataFrame(calibration_rows),
        "class_support_report": pd.DataFrame(support_rows),
        "validation_predictions": pd.DataFrame(prediction_rows),
    }


def build_phase13u_baseline_comparison_report(
    metric_report: pd.DataFrame,
) -> pd.DataFrame:
    if metric_report.empty:
        return pd.DataFrame()

    validation = metric_report[metric_report["split_label"].astype(str).eq("validation")]
    majority = validation[
        validation["model_id"].astype(str).eq("baseline_majority_class")
    ]

    if majority.empty:
        majority_balanced_accuracy = np.nan
        majority_macro_f1 = np.nan
    else:
        majority_balanced_accuracy = float(majority.iloc[0]["balanced_accuracy"])
        majority_macro_f1 = float(majority.iloc[0]["macro_f1"])

    rows: list[dict[str, Any]] = []

    for _, row in validation.iterrows():
        rows.append(
            {
                "model_id": row["model_id"],
                "validation_balanced_accuracy": row["balanced_accuracy"],
                "validation_macro_f1": row["macro_f1"],
                "majority_baseline_balanced_accuracy": majority_balanced_accuracy,
                "majority_baseline_macro_f1": majority_macro_f1,
                "delta_balanced_accuracy_vs_majority": float(row["balanced_accuracy"])
                - majority_balanced_accuracy,
                "delta_macro_f1_vs_majority": float(row["macro_f1"]) - majority_macro_f1,
                "diagnostic_only": True,
                "model_selected": False,
            }
        )

    return pd.DataFrame(rows)


def build_phase13u_forbidden_output_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("holdout_predictions_generated", "allow_holdout_prediction_generation"),
        ("model_selection", "allow_model_selection"),
        ("feature_importance", "allow_feature_importance"),
        ("signal_creation", "allow_signal_creation"),
        ("strategy_backtest", "allow_strategy_backtest"),
        ("paper_trading_deployment", "allow_paper_trading_deployment"),
        ("candidate_promotion", "allow_candidate_promotion"),
        ("final_candidate_change", "allow_final_candidate_change"),
    ]

    rows = [
        {
            "forbidden_item": label,
            "allowed_flag_value": _bool_value(phase_config.get(key, True)),
            "passed": not _bool_value(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13u_phase13v_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase13v_boundary", {})

    checks = [
        (
            "phase13v_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "quality" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13v_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "holdout prediction" in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation" in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13v_may_audit_training_results",
            _bool_value(boundary.get("phase13v_may_audit_training_results", False)),
            _bool_value(boundary.get("phase13v_may_audit_training_results", False)),
        ),
        (
            "phase13v_may_generate_holdout_predictions",
            _bool_value(boundary.get("phase13v_may_generate_holdout_predictions", True)),
            not _bool_value(
                boundary.get("phase13v_may_generate_holdout_predictions", True)
            ),
        ),
        (
            "phase13v_may_calculate_feature_importance",
            _bool_value(boundary.get("phase13v_may_calculate_feature_importance", True)),
            not _bool_value(
                boundary.get("phase13v_may_calculate_feature_importance", True)
            ),
        ),
        (
            "phase13v_may_create_signal",
            _bool_value(boundary.get("phase13v_may_create_signal", True)),
            not _bool_value(boundary.get("phase13v_may_create_signal", True)),
        ),
        (
            "phase13v_may_run_backtest",
            _bool_value(boundary.get("phase13v_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13v_may_run_backtest", True)),
        ),
        (
            "phase13v_may_promote_candidate",
            _bool_value(boundary.get("phase13v_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13v_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [
            {"boundary_item": item, "value": value, "passed": passed}
            for item, value, passed in checks
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No holdout prediction generation", "allow_holdout_prediction_generation"),
        ("No model selection", "allow_model_selection"),
        ("No feature importance", "allow_feature_importance"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No paper trading deployment", "allow_paper_trading_deployment"),
        ("No candidate promotion", "allow_candidate_promotion"),
        ("No final candidate change", "allow_final_candidate_change"),
    ]

    rows = []
    for label, key in checks:
        value = _bool_value(phase_config.get(key, True))
        rows.append({"scope_item": label, "value": value, "passed": not value})

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13u_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13t_result_check: pd.DataFrame,
    dataset_profile: pd.DataFrame,
    feature_matrix_profile: pd.DataFrame,
    training_outputs: dict[str, pd.DataFrame],
    baseline_comparison_report: pd.DataFrame,
    forbidden_output_check: pd.DataFrame,
    phase13v_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    model_execution = training_outputs["model_registry_execution_report"]
    metrics = training_outputs["train_validation_metric_report"]
    validation_predictions = training_outputs["validation_predictions"]

    return pd.DataFrame(
        [
            {
                "execution_role": str(phase_config.get("execution_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase13t_result_passed": bool(phase13t_result_check["passed"].all())
                if not phase13t_result_check.empty
                else False,
                "dataset_rows": int(dataset_profile.iloc[0]["rows"])
                if not dataset_profile.empty
                else 0,
                "dataset_label": str(dataset_profile.iloc[0]["dataset_label"])
                if not dataset_profile.empty
                else "",
                "feature_matrix_rows": int(feature_matrix_profile.iloc[0]["train_model_rows"])
                + int(feature_matrix_profile.iloc[0]["validation_model_rows"])
                if not feature_matrix_profile.empty
                else 0,
                "train_model_rows": int(feature_matrix_profile.iloc[0]["train_model_rows"])
                if not feature_matrix_profile.empty
                else 0,
                "validation_model_rows": int(
                    feature_matrix_profile.iloc[0]["validation_model_rows"]
                )
                if not feature_matrix_profile.empty
                else 0,
                "trained_model_count": int(model_execution["trained"].map(_bool_value).sum())
                if not model_execution.empty
                else 0,
                "metric_rows": int(len(metrics)),
                "validation_prediction_rows": int(len(validation_predictions)),
                "validation_predictions_only": bool(
                    validation_predictions["split_label"].astype(str).eq("validation").all()
                )
                if not validation_predictions.empty
                else False,
                "confusion_matrix_rows": int(
                    len(training_outputs["confusion_matrix_report"])
                ),
                "calibration_rows": int(len(training_outputs["calibration_report"])),
                "class_support_rows": int(len(training_outputs["class_support_report"])),
                "baseline_comparison_rows": int(len(baseline_comparison_report)),
                "forbidden_output_check_passed": bool(
                    forbidden_output_check["passed"].all()
                )
                if not forbidden_output_check.empty
                else False,
                "phase13v_boundary_passed": bool(
                    phase13v_boundary_check["passed"].all()
                )
                if not phase13v_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "holdout_predictions_generated": False,
                "feature_importance_calculated": False,
                "model_selected": False,
                "signal_created": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13u_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [_gate_row("Phase 13U summary exists", False, "No summary.")]
        )

    row = summary.iloc[0]
    required_label = str(
        phase_config.get("dataset_policy", {}).get(
            "dataset_label_required",
            "multi_factor_technical_macro_dataset_v1",
        )
    )
    required_role = str(
        gates.get(
            "required_execution_role",
            "Registered baseline ML training execution and train/validation "
            "evaluation only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13T passed",
            bool(row["phase13t_result_passed"]),
            f"phase13t_result_passed={bool(row['phase13t_result_passed'])}",
        ),
        _gate_row(
            "Source reports are present",
            bool(row["source_reports_present"]),
            f"source_reports_present={bool(row['source_reports_present'])}",
        ),
        _gate_row(
            "Dataset loaded",
            int(row["dataset_rows"]) > 0,
            f"dataset_rows={int(row['dataset_rows'])}",
        ),
        _gate_row(
            "Dataset label is correct",
            str(row["dataset_label"]) == required_label,
            f"dataset_label={row['dataset_label']}",
        ),
        _gate_row(
            "Feature matrix has train/validation rows",
            int(row["train_model_rows"]) > 0 and int(row["validation_model_rows"]) > 0,
            f"train_rows={int(row['train_model_rows'])}; "
            f"validation_rows={int(row['validation_model_rows'])}",
        ),
        _gate_row(
            "Registered models were trained",
            int(row["trained_model_count"]) >= int(gates.get("min_trained_models", 5)),
            f"trained_model_count={int(row['trained_model_count'])}",
        ),
        _gate_row(
            "Train/validation metrics exist",
            int(row["metric_rows"]) >= int(row["trained_model_count"]) * 2,
            f"metric_rows={int(row['metric_rows'])}",
        ),
        _gate_row(
            "Validation predictions only",
            bool(row["validation_predictions_only"])
            and not bool(row["holdout_predictions_generated"]),
            f"validation_prediction_rows={int(row['validation_prediction_rows'])}",
        ),
        _gate_row(
            "Confusion matrices exist",
            int(row["confusion_matrix_rows"]) > 0,
            f"confusion_matrix_rows={int(row['confusion_matrix_rows'])}",
        ),
        _gate_row(
            "Calibration reports exist",
            int(row["calibration_rows"]) > 0,
            f"calibration_rows={int(row['calibration_rows'])}",
        ),
        _gate_row(
            "Class support reports exist",
            int(row["class_support_rows"]) > 0,
            f"class_support_rows={int(row['class_support_rows'])}",
        ),
        _gate_row(
            "Baseline comparison report exists",
            int(row["baseline_comparison_rows"]) > 0,
            f"baseline_comparison_rows={int(row['baseline_comparison_rows'])}",
        ),
        _gate_row(
            "No forbidden outputs were created",
            bool(row["forbidden_output_check_passed"]),
            f"forbidden_output_check_passed="
            f"{bool(row['forbidden_output_check_passed'])}",
        ),
        _gate_row(
            "Phase 13V boundary is quality-audit-only",
            bool(row["phase13v_boundary_passed"]),
            f"phase13v_boundary_passed={bool(row['phase13v_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks signal/backtest/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Execution role is correct",
            str(row["execution_role"]) == required_role,
            f"execution_role={row['execution_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13u_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — registered baseline ML train/validation execution passed"
        if all_passed
        else "Failed registered baseline ML train/validation execution"
    )
    interpretation = (
        "Phase 13U trained only registered baseline ML models with train-only "
        "preprocessing and train/validation evaluation. It generated validation "
        "predictions and classification diagnostics only. It did not generate "
        "holdout predictions, calculate feature importance, create signals, run "
        "backtests, deploy paper trading, promote a candidate, or change the final "
        "candidate."
        if all_passed
        else "Phase 13U found a model-training, metric, prediction, boundary, or "
        "scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13U",
                "diagnostic": "Registered baseline ML train/validation execution",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def _write_markdown(
    *,
    title: str,
    sections: dict[str, pd.DataFrame],
    output_path: Path,
) -> None:
    lines = [f"# {title}", ""]

    for heading, frame in sections.items():
        lines.extend([f"## {heading}", frame.to_markdown(index=False), ""])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13u_registered_baseline_ml_training(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13u_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13u_source_report_check(phase_config)
    phase13t_result_check = build_phase13u_phase13t_result_check(phase_config)

    source_reports = phase_config.get("source_reports", {})
    dataset = _read_csv_if_exists(source_reports.get("dataset", ""))

    dataset_profile = build_phase13u_dataset_profile(
        dataset=dataset,
        phase_config=phase_config,
    )
    feature_matrix_profile = build_phase13u_feature_matrix_profile(
        dataset=dataset,
        phase_config=phase_config,
    )
    training_outputs = run_phase13u_registered_training(
        dataset=dataset,
        phase_config=phase_config,
    )
    baseline_comparison_report = build_phase13u_baseline_comparison_report(
        training_outputs["train_validation_metric_report"]
    )
    forbidden_output_check = build_phase13u_forbidden_output_check(phase_config)
    phase13v_boundary_check = build_phase13u_phase13v_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13u_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13t_result_check=phase13t_result_check,
        dataset_profile=dataset_profile,
        feature_matrix_profile=feature_matrix_profile,
        training_outputs=training_outputs,
        baseline_comparison_report=baseline_comparison_report,
        forbidden_output_check=forbidden_output_check,
        phase13v_boundary_check=phase13v_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13u_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13u_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13t_result_check": phase13t_result_check,
        "dataset_profile": dataset_profile,
        "feature_matrix_profile": feature_matrix_profile,
        "model_registry_execution_report": training_outputs[
            "model_registry_execution_report"
        ],
        "preprocessing_pipeline_report": training_outputs[
            "preprocessing_pipeline_report"
        ],
        "train_validation_metric_report": training_outputs[
            "train_validation_metric_report"
        ],
        "confusion_matrix_report": training_outputs["confusion_matrix_report"],
        "calibration_report": training_outputs["calibration_report"],
        "class_support_report": training_outputs["class_support_report"],
        "baseline_comparison_report": baseline_comparison_report,
        "validation_predictions": training_outputs["validation_predictions"],
        "forbidden_output_check": forbidden_output_check,
        "phase13v_boundary_check": phase13v_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13u_ml_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13U — Registered Baseline ML Training Execution",
        sections={
            "Dataset Profile": dataset_profile,
            "Feature Matrix Profile": feature_matrix_profile,
            "Model Registry Execution Report": outputs[
                "model_registry_execution_report"
            ],
            "Train Validation Metric Report": outputs[
                "train_validation_metric_report"
            ],
            "Baseline Comparison Report": baseline_comparison_report,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13u_registered_baseline_ml_training.md",
    )

    print("Wrote Phase 13U registered baseline ML training reports.")
    return outputs


def build_phase13v_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("phase13u_reports", {}).items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "report_key": str(report_key),
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": int(len(frame)),
            }
        )

    out = pd.DataFrame(rows)

    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})

    return out


def build_phase13v_phase13u_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase13u_reports", {})
    conclusion = _read_csv_if_exists(reports.get("conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("gate_report", ""))

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_report_passed = (
        not gate_report.empty
        and "passed" in gate_report.columns
        and bool(gate_report["passed"].map(_bool_value).all())
    )

    out = pd.DataFrame(
        [
            {
                "check": "Phase 13U conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13U gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13v_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for key, expected in expected_flags.items():
        actual = runtime_config.get(key, {}).get("enabled")
        passed = actual is expected
        rows.append(
            {
                "config_key": str(key),
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase13v_training_output_quality_check(
    *,
    model_execution: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    trained_models = (
        int(model_execution["trained"].map(_bool_value).sum())
        if not model_execution.empty and "trained" in model_execution.columns
        else 0
    )
    holdout_rows_used = (
        int(pd.to_numeric(model_execution["holdout_rows_used"], errors="coerce").sum())
        if not model_execution.empty and "holdout_rows_used" in model_execution.columns
        else 0
    )

    rows = [
        {
            "check": "Minimum registered models trained",
            "passed": trained_models >= int(thresholds.get("min_trained_models", 5)),
            "detail": f"trained_models={trained_models}",
        },
        {
            "check": "No holdout rows used",
            "passed": holdout_rows_used == 0,
            "detail": f"holdout_rows_used={holdout_rows_used}",
        },
        {
            "check": "No model selected",
            "passed": not model_execution.get("model_selected", pd.Series([False])).map(
                _bool_value
            ).any(),
            "detail": "model_selected=False",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13v_metrics_quality_check(
    *,
    metric_report: pd.DataFrame,
    confusion_report: pd.DataFrame,
    class_support_report: pd.DataFrame,
    baseline_comparison_report: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    rows = [
        {
            "check": "Metric rows sufficient",
            "passed": len(metric_report) >= int(thresholds.get("min_metric_rows", 10)),
            "detail": f"metric_rows={len(metric_report)}",
        },
        {
            "check": "Confusion matrix rows sufficient",
            "passed": len(confusion_report)
            >= int(thresholds.get("min_confusion_matrix_rows", 45)),
            "detail": f"confusion_matrix_rows={len(confusion_report)}",
        },
        {
            "check": "Class support rows sufficient",
            "passed": len(class_support_report)
            >= int(thresholds.get("min_class_support_rows", 6)),
            "detail": f"class_support_rows={len(class_support_report)}",
        },
        {
            "check": "Baseline comparison exists",
            "passed": not baseline_comparison_report.empty,
            "detail": f"baseline_comparison_rows={len(baseline_comparison_report)}",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13v_prediction_boundary_check(
    validation_predictions: pd.DataFrame,
) -> pd.DataFrame:
    split_values = (
        set(validation_predictions["split_label"].dropna().astype(str))
        if not validation_predictions.empty and "split_label" in validation_predictions.columns
        else set()
    )
    holdout_flags = (
        validation_predictions["holdout_prediction"].map(_bool_value).any()
        if not validation_predictions.empty
        and "holdout_prediction" in validation_predictions.columns
        else False
    )

    rows = [
        {
            "check": "Validation predictions exist",
            "passed": not validation_predictions.empty,
            "detail": f"rows={len(validation_predictions)}",
        },
        {
            "check": "Predictions are validation-only",
            "passed": split_values == {"validation"},
            "detail": f"split_values={'; '.join(sorted(split_values))}",
        },
        {
            "check": "No holdout prediction flag",
            "passed": not holdout_flags,
            "detail": f"holdout_prediction_flag={holdout_flags}",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13v_forbidden_output_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    thresholds = phase_config.get("quality_thresholds", {})
    rows: list[dict[str, Any]] = []

    for path in _as_list(thresholds.get("forbidden_output_paths")):
        report_path = Path(str(path))
        rows.append(
            {
                "path": str(report_path),
                "present": report_path.exists(),
                "passed": not report_path.exists(),
                "result": "Passed" if not report_path.exists() else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase13v_phase13w_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase13w_boundary", {})

    checks = [
        (
            "phase13w_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "interpretation" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13w_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "holdout prediction" in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation" in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13w_may_interpret_validation_results",
            _bool_value(boundary.get("phase13w_may_interpret_validation_results", False)),
            _bool_value(boundary.get("phase13w_may_interpret_validation_results", False)),
        ),
        (
            "phase13w_may_generate_holdout_predictions",
            _bool_value(boundary.get("phase13w_may_generate_holdout_predictions", True)),
            not _bool_value(
                boundary.get("phase13w_may_generate_holdout_predictions", True)
            ),
        ),
        (
            "phase13w_may_create_signal",
            _bool_value(boundary.get("phase13w_may_create_signal", True)),
            not _bool_value(boundary.get("phase13w_may_create_signal", True)),
        ),
        (
            "phase13w_may_run_backtest",
            _bool_value(boundary.get("phase13w_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13w_may_run_backtest", True)),
        ),
        (
            "phase13w_may_promote_candidate",
            _bool_value(boundary.get("phase13w_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13w_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [
            {"boundary_item": item, "value": value, "passed": passed}
            for item, value, passed in checks
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13v_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No holdout prediction generation", "allow_holdout_prediction_generation"),
        ("No model selection", "allow_model_selection"),
        ("No feature importance", "allow_feature_importance"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No paper trading deployment", "allow_paper_trading_deployment"),
        ("No candidate promotion", "allow_candidate_promotion"),
        ("No final candidate change", "allow_final_candidate_change"),
    ]

    rows = []
    for label, key in checks:
        value = _bool_value(phase_config.get(key, True))
        rows.append({"scope_item": label, "value": value, "passed": not value})

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13v_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13u_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    training_output_quality_check: pd.DataFrame,
    metrics_quality_check: pd.DataFrame,
    prediction_boundary_check: pd.DataFrame,
    forbidden_output_check: pd.DataFrame,
    phase13w_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13u_reports_present": bool(
                    report_inventory_check["present"].all()
                )
                if not report_inventory_check.empty
                else False,
                "phase13u_result_passed": bool(phase13u_result_check["passed"].all())
                if not phase13u_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "training_outputs_quality_passed": bool(
                    training_output_quality_check["passed"].all()
                )
                if not training_output_quality_check.empty
                else False,
                "metrics_quality_passed": bool(metrics_quality_check["passed"].all())
                if not metrics_quality_check.empty
                else False,
                "prediction_boundary_passed": bool(
                    prediction_boundary_check["passed"].all()
                )
                if not prediction_boundary_check.empty
                else False,
                "forbidden_outputs_absent": bool(forbidden_output_check["passed"].all())
                if not forbidden_output_check.empty
                else False,
                "phase13w_boundary_passed": bool(
                    phase13w_boundary_check["passed"].all()
                )
                if not phase13w_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "holdout_predictions_generated": False,
                "feature_importance_calculated": False,
                "model_selected": False,
                "signal_created": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13v_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(
            [_gate_row("Phase 13V summary exists", False, "No summary.")]
        )

    row = summary.iloc[0]
    required_role = str(
        phase_config.get("gates", {}).get(
            "required_audit_role",
            "ML training result quality and leakage audit only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13U reports are present",
            bool(row["phase13u_reports_present"]),
            f"phase13u_reports_present={bool(row['phase13u_reports_present'])}",
        ),
        _gate_row(
            "Phase 13U conclusion and gates passed",
            bool(row["phase13u_result_passed"]),
            f"phase13u_result_passed={bool(row['phase13u_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Training outputs quality passed",
            bool(row["training_outputs_quality_passed"]),
            f"training_outputs_quality_passed="
            f"{bool(row['training_outputs_quality_passed'])}",
        ),
        _gate_row(
            "Metrics quality passed",
            bool(row["metrics_quality_passed"]),
            f"metrics_quality_passed={bool(row['metrics_quality_passed'])}",
        ),
        _gate_row(
            "Prediction boundary passed",
            bool(row["prediction_boundary_passed"]),
            f"prediction_boundary_passed={bool(row['prediction_boundary_passed'])}",
        ),
        _gate_row(
            "Forbidden outputs are absent",
            bool(row["forbidden_outputs_absent"]),
            f"forbidden_outputs_absent={bool(row['forbidden_outputs_absent'])}",
        ),
        _gate_row(
            "Phase 13W boundary is interpretation-only",
            bool(row["phase13w_boundary_passed"]),
            f"phase13w_boundary_passed={bool(row['phase13w_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks signal/backtest/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Audit role is correct",
            str(row["audit_role"]) == required_role,
            f"audit_role={row['audit_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13v_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — ML training result quality/leakage audit passed"
        if all_passed
        else "Failed ML training result quality/leakage audit"
    )
    interpretation = (
        "Phase 13V audited registered train/validation ML outputs, metrics, "
        "validation-only predictions, forbidden-output absence, and leakage "
        "boundaries. It did not generate holdout predictions, calculate feature "
        "importance, create signals, run backtests, deploy paper trading, promote a "
        "candidate, or change the final candidate."
        if all_passed
        else "Phase 13V found a training-output, metric, prediction, forbidden-output, "
        "boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13V",
                "diagnostic": "ML training result quality/leakage audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def save_phase13v_ml_training_result_quality_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13v_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = phase_config.get("phase13u_reports", {})
    thresholds = phase_config.get("quality_thresholds", {})

    report_inventory_check = build_phase13v_report_inventory_check(phase_config)
    phase13u_result_check = build_phase13v_phase13u_result_check(phase_config)
    config_flag_check = build_phase13v_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )

    model_execution = _read_csv_if_exists(
        reports.get("model_registry_execution_report", "")
    )
    metrics = _read_csv_if_exists(reports.get("train_validation_metric_report", ""))
    confusion = _read_csv_if_exists(reports.get("confusion_matrix_report", ""))
    class_support = _read_csv_if_exists(reports.get("class_support_report", ""))
    baseline_comparison = _read_csv_if_exists(
        reports.get("baseline_comparison_report", "")
    )
    validation_predictions = _read_csv_if_exists(
        reports.get("validation_predictions", "")
    )

    training_output_quality_check = build_phase13v_training_output_quality_check(
        model_execution=model_execution,
        thresholds=thresholds,
    )
    metrics_quality_check = build_phase13v_metrics_quality_check(
        metric_report=metrics,
        confusion_report=confusion,
        class_support_report=class_support,
        baseline_comparison_report=baseline_comparison,
        thresholds=thresholds,
    )
    prediction_boundary_check = build_phase13v_prediction_boundary_check(
        validation_predictions
    )
    forbidden_output_check = build_phase13v_forbidden_output_check(phase_config)
    phase13w_boundary_check = build_phase13v_phase13w_boundary_check(phase_config)
    scope_boundary_check = build_phase13v_scope_boundary_check(phase_config)

    summary = build_phase13v_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13u_result_check=phase13u_result_check,
        config_flag_check=config_flag_check,
        training_output_quality_check=training_output_quality_check,
        metrics_quality_check=metrics_quality_check,
        prediction_boundary_check=prediction_boundary_check,
        forbidden_output_check=forbidden_output_check,
        phase13w_boundary_check=phase13w_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13v_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13v_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13u_result_check": phase13u_result_check,
        "config_flag_check": config_flag_check,
        "training_output_quality_check": training_output_quality_check,
        "metrics_quality_check": metrics_quality_check,
        "prediction_boundary_check": prediction_boundary_check,
        "forbidden_output_check": forbidden_output_check,
        "phase13w_boundary_check": phase13w_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13v_quality_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13V — ML Training Result Quality / Leakage Audit",
        sections={
            "Training Output Quality Check": training_output_quality_check,
            "Metrics Quality Check": metrics_quality_check,
            "Prediction Boundary Check": prediction_boundary_check,
            "Forbidden Output Check": forbidden_output_check,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13v_ml_training_result_quality_audit.md",
    )

    print("Wrote Phase 13V ML training result quality audit reports.")
    return outputs