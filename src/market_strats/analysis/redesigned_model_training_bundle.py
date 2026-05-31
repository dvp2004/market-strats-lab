from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


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


def _gate_row(gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return config.get(key, {}) or {}


def _source_report_check(paths: dict[str, str]) -> pd.DataFrame:
    rows = []

    for report_key, path in paths.items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "report_key": report_key,
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": len(frame),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def _phase_result_check(
    conclusion_path: str,
    gate_path: str,
    phase_name: str,
) -> pd.DataFrame:
    conclusion = _read_csv_if_exists(conclusion_path)
    gate = _read_csv_if_exists(gate_path)

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_passed = (
        not gate.empty
        and "passed" in gate.columns
        and bool(gate["passed"].map(_bool_value).all())
    )

    out = pd.DataFrame(
        [
            {
                "check": f"{phase_name} conclusion passed",
                "passed": conclusion_passed,
                "detail": "conclusion",
            },
            {
                "check": f"{phase_name} gate report passed",
                "passed": gate_passed,
                "detail": "gate_report",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_holdout_prediction_generation",
        "allow_model_selection",
        "allow_feature_importance",
        "allow_signal_creation",
        "allow_strategy_backtest",
        "allow_paper_trading_deployment",
        "allow_candidate_promotion",
        "allow_final_candidate_change",
    ]

    rows = []
    for key in keys:
        value = _bool_value(section.get(key, False))
        rows.append({"scope_item": key, "value": value, "passed": not value})

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _safe_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def _policy_frame_to_dict(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {}

    key_col = "policy_key"
    value_col = "policy_value"

    if key_col not in frame.columns or value_col not in frame.columns:
        return {}

    return {
        str(row[key_col]): row[value_col]
        for _, row in frame.iterrows()
    }


def _float_gate(gates: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(gates.get(key, default))
    except (TypeError, ValueError):
        return default


def _bool_gate(gates: dict[str, Any], key: str, default: bool) -> bool:
    if key not in gates:
        return default
    return _bool_value(gates[key])


def _list_from_policy_value(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    return [str(item) for item in _as_list(value)]


def _combine_dataset_and_target(
    dataset: pd.DataFrame,
    assignment: pd.DataFrame,
    target_id: str,
) -> pd.DataFrame:
    combined = dataset.copy()

    if target_id not in assignment.columns:
        combined["redesigned_target"] = "unavailable"
        return combined

    if len(assignment) == len(combined):
        combined["redesigned_target"] = assignment[target_id].astype(str).to_numpy()
        return combined

    if {"decision_date", "split_label"}.issubset(assignment.columns).issubset(combined.columns):
        lookup = assignment[["decision_date", "split_label", target_id]].copy()
        merged = combined.merge(
            lookup,
            on=["decision_date", "split_label"],
            how="left",
            validate="one_to_one",
        )
        merged["redesigned_target"] = merged[target_id].fillna("unavailable").astype(str)
        return merged.drop(columns=[target_id])

    combined["redesigned_target"] = "unavailable"
    return combined


def _feature_columns(
    dataset: pd.DataFrame,
    feature_policy: dict[str, Any],
) -> tuple[list[str], list[str]]:
    numeric_prefixes = tuple(_list_from_policy_value(
        feature_policy.get("numeric_feature_prefixes", [])
    ))
    categorical_prefixes = tuple(_list_from_policy_value(
        feature_policy.get("categorical_feature_prefixes", [])
    ))
    forbidden_fragments = [
        fragment.lower()
        for fragment in _list_from_policy_value(
            feature_policy.get("forbidden_feature_fragments", [])
        )
    ]

    numeric = [
        col for col in dataset.columns
        if str(col).startswith(numeric_prefixes)
        and not any(fragment in str(col).lower() for fragment in forbidden_fragments)
    ]
    categorical = [
        col for col in dataset.columns
        if str(col).startswith(categorical_prefixes)
        and not any(fragment in str(col).lower() for fragment in forbidden_fragments)
    ]

    return numeric, categorical


def _make_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    numeric_pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", _safe_one_hot_encoder()),
        ]
    )

    return ColumnTransformer(
        [
            ("numeric", numeric_pipe, numeric),
            ("categorical", categorical_pipe, categorical),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )


def _make_model(row: pd.Series) -> Any:
    family = str(row.get("family", ""))

    if family == "dummy":
        return DummyClassifier(
            strategy=str(row.get("strategy", "most_frequent")),
            random_state=42,
        )

    if family == "logistic_regression":
        return LogisticRegression(
            C=float(row.get("C", 0.5)),
            max_iter=int(float(row.get("max_iter", 1000))),
            class_weight=row.get("class_weight", "balanced"),
            random_state=42,
        )

    if family == "random_forest":
        return RandomForestClassifier(
            n_estimators=int(float(row.get("n_estimators", 300))),
            max_depth=int(float(row.get("max_depth", 4))),
            min_samples_leaf=int(float(row.get("min_samples_leaf", 25))),
            class_weight=row.get("class_weight", "balanced"),
            random_state=int(float(row.get("random_state", 42))),
            n_jobs=-1,
        )

    if family == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_iter=int(float(row.get("max_iter", 120))),
            learning_rate=float(row.get("learning_rate", 0.04)),
            max_leaf_nodes=int(float(row.get("max_leaf_nodes", 9))),
            l2_regularization=float(row.get("l2_regularization", 1.0)),
            random_state=int(float(row.get("random_state", 42))),
        )

    raise ValueError(f"Unsupported model family: {family}")


def _split_rows(
    combined: pd.DataFrame,
    split_label: str,
    labels: list[str],
) -> pd.DataFrame:
    frame = combined[combined["split_label"].astype(str).eq(split_label)].copy()
    frame = frame[frame["redesigned_target"].astype(str).isin(labels)]
    return frame.reset_index(drop=True)


def _metric_row(
    model_id: str,
    family: str,
    split: str,
    y_true: pd.Series,
    y_pred: np.ndarray,
    labels: list[str],
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "family": family,
        "split_label": split,
        "rows": len(y_true),
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0),
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
        "model_selected": False,
        "signal_created": False,
        "backtest_run": False,
    }


def _confusion_rows(
    model_id: str,
    split: str,
    y_true: pd.Series,
    y_pred: np.ndarray,
    labels: list[str],
) -> list[dict[str, Any]]:
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    rows = []

    for actual_idx, actual in enumerate(labels):
        for predicted_idx, predicted in enumerate(labels):
            rows.append(
                {
                    "model_id": model_id,
                    "split_label": split,
                    "actual_class": actual,
                    "predicted_class": predicted,
                    "count": int(matrix[actual_idx, predicted_idx]),
                }
            )

    return rows


def _class_recall_rows(
    model_id: str,
    split: str,
    y_true: pd.Series,
    y_pred: np.ndarray,
    labels: list[str],
) -> list[dict[str, Any]]:
    pred_series = pd.Series(y_pred).astype(str).reset_index(drop=True)
    true_series = y_true.astype(str).reset_index(drop=True)
    rows = []

    for label in labels:
        actual_mask = true_series.eq(label)
        predicted_mask = pred_series.eq(label)

        support = int(actual_mask.sum())
        predicted_count = int(predicted_mask.sum())
        true_positive = int((actual_mask & predicted_mask).sum())

        recall = true_positive / support if support else 0.0
        precision = true_positive / predicted_count if predicted_count else 0.0

        rows.append(
            {
                "model_id": model_id,
                "split_label": split,
                "class_label": label,
                "support": support,
                "predicted_count": predicted_count,
                "true_positive": true_positive,
                "precision": precision,
                "recall": recall,
                "fragile_recall_warning": bool(label == "fragile" and recall < 0.20),
            }
        )

    return rows


def _calibration_rows(
    model_id: str,
    split: str,
    y_true: pd.Series,
    y_pred: np.ndarray,
    probabilities: np.ndarray | None,
) -> list[dict[str, Any]]:
    if probabilities is None or len(probabilities) == 0:
        return []

    confidence = probabilities.max(axis=1)
    correct = pd.Series(y_pred).astype(str).reset_index(drop=True).eq(
        y_true.astype(str).reset_index(drop=True)
    )

    bins = pd.cut(
        confidence,
        bins=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        include_lowest=True,
    )

    rows = []
    frame = pd.DataFrame({"bin": bins, "confidence": confidence, "correct": correct})

    for bin_label, group in frame.groupby("bin", observed=False):
        rows.append(
            {
                "model_id": model_id,
                "split_label": split,
                "confidence_bin": str(bin_label),
                "rows": len(group),
                "mean_confidence": float(group["confidence"].mean()) if len(group) else 0.0,
                "accuracy": float(group["correct"].mean()) if len(group) else 0.0,
                "absolute_calibration_gap": abs(
                    float(group["confidence"].mean()) - float(group["correct"].mean())
                ) if len(group) else 0.0,
            }
        )

    return rows


def _prediction_rows(
    model_id: str,
    validation: pd.DataFrame,
    y_true: pd.Series,
    y_pred: np.ndarray,
    labels: list[str],
    probabilities: np.ndarray | None,
) -> list[dict[str, Any]]:
    rows = []

    for idx, predicted in enumerate(y_pred):
        base = {
            "model_id": model_id,
            "split_label": "validation",
            "decision_date": validation.iloc[idx].get("decision_date", ""),
            "actual_class": y_true.iloc[idx],
            "predicted_class": predicted,
            "holdout_prediction": False,
            "model_selected": False,
            "signal_created": False,
        }

        if probabilities is not None:
            for label_idx, label in enumerate(labels):
                base[f"predicted_probability__{label}"] = float(
                    probabilities[idx, label_idx]
                )

        rows.append(base)

    return rows


def _predict_proba_aligned(
    model: Pipeline,
    features: pd.DataFrame,
    labels: list[str],
) -> np.ndarray | None:
    if not hasattr(model, "predict_proba"):
        return None

    probabilities = model.predict_proba(features)
    classes = [str(item) for item in model.classes_]
    aligned = np.zeros((len(features), len(labels)))

    for label_idx, label in enumerate(labels):
        if label in classes:
            aligned[:, label_idx] = probabilities[:, classes.index(label)]

    return aligned


def _overfit_report(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for model_id, group in metrics.groupby("model_id"):
        train = group[group["split_label"].astype(str).eq("train")]
        validation = group[group["split_label"].astype(str).eq("validation")]

        if train.empty or validation.empty:
            continue

        train_row = train.iloc[0]
        validation_row = validation.iloc[0]

        rows.append(
            {
                "model_id": model_id,
                "family": validation_row["family"],
                "train_balanced_accuracy": train_row["balanced_accuracy"],
                "validation_balanced_accuracy": validation_row["balanced_accuracy"],
                "balanced_accuracy_gap": (
                    train_row["balanced_accuracy"] - validation_row["balanced_accuracy"]
                ),
                "train_macro_f1": train_row["macro_f1"],
                "validation_macro_f1": validation_row["macro_f1"],
                "macro_f1_gap": train_row["macro_f1"] - validation_row["macro_f1"],
            }
        )

    return pd.DataFrame(rows)


def _baseline_comparison(metrics: pd.DataFrame) -> pd.DataFrame:
    validation = metrics[metrics["split_label"].astype(str).eq("validation")].copy()

    majority = validation[validation["model_id"].astype(str).eq("baseline_majority_class")]
    stratified = validation[
        validation["model_id"].astype(str).eq("baseline_stratified_dummy")
    ]

    majority_bal = float(majority.iloc[0]["balanced_accuracy"]) if not majority.empty else 0.0
    majority_f1 = float(majority.iloc[0]["macro_f1"]) if not majority.empty else 0.0
    strat_bal = float(stratified.iloc[0]["balanced_accuracy"]) if not stratified.empty else 0.0
    strat_f1 = float(stratified.iloc[0]["macro_f1"]) if not stratified.empty else 0.0

    rows = []

    for _, row in validation.iterrows():
        rows.append(
            {
                "model_id": row["model_id"],
                "family": row["family"],
                "validation_balanced_accuracy": row["balanced_accuracy"],
                "validation_macro_f1": row["macro_f1"],
                "majority_balanced_accuracy": majority_bal,
                "majority_macro_f1": majority_f1,
                "stratified_balanced_accuracy": strat_bal,
                "stratified_macro_f1": strat_f1,
                "delta_balanced_accuracy_vs_majority": (
                    row["balanced_accuracy"] - majority_bal
                ),
                "delta_macro_f1_vs_majority": row["macro_f1"] - majority_f1,
                "delta_balanced_accuracy_vs_stratified": (
                    row["balanced_accuracy"] - strat_bal
                ),
                "delta_macro_f1_vs_stratified": row["macro_f1"] - strat_f1,
            }
        )

    return pd.DataFrame(rows)


def _success_report(
    metrics: pd.DataFrame,
    baseline: pd.DataFrame,
    class_recall: pd.DataFrame,
    overfit: pd.DataFrame,
    gates: dict[str, Any],
) -> pd.DataFrame:
    validation = metrics[metrics["split_label"].astype(str).eq("validation")].copy()
    rows = []

    for _, row in validation.iterrows():
        model_id = str(row["model_id"])
        family = str(row["family"])
        is_real_model = family != "dummy"

        comparison = baseline[baseline["model_id"].astype(str).eq(model_id)]
        recall_row = class_recall[
            class_recall["model_id"].astype(str).eq(model_id)
            & class_recall["split_label"].astype(str).eq("validation")
            & class_recall["class_label"].astype(str).eq("fragile")
        ]
        overfit_row = overfit[overfit["model_id"].astype(str).eq(model_id)]

        delta_bal_majority = (
            float(comparison.iloc[0]["delta_balanced_accuracy_vs_majority"])
            if not comparison.empty
            else 0.0
        )
        delta_f1_majority = (
            float(comparison.iloc[0]["delta_macro_f1_vs_majority"])
            if not comparison.empty
            else 0.0
        )
        delta_bal_stratified = (
            float(comparison.iloc[0]["delta_balanced_accuracy_vs_stratified"])
            if not comparison.empty
            else 0.0
        )
        fragile_recall = (
            float(recall_row.iloc[0]["recall"])
            if not recall_row.empty
            else 0.0
        )
        balanced_gap = (
            float(overfit_row.iloc[0]["balanced_accuracy_gap"])
            if not overfit_row.empty
            else 0.0
        )
        macro_f1_gap = (
            float(overfit_row.iloc[0]["macro_f1_gap"])
            if not overfit_row.empty
            else 0.0
        )

        passes_majority_bal = delta_bal_majority >= _float_gate(
            gates,
            "min_validation_balanced_accuracy_delta_vs_majority",
            0.05,
        )
        passes_majority_f1 = delta_f1_majority >= _float_gate(
            gates,
            "min_validation_macro_f1_delta_vs_majority",
            0.05,
        )
        passes_fragile = fragile_recall >= _float_gate(
            gates,
            "min_validation_fragile_recall",
            0.20,
        )
        passes_bal_overfit = balanced_gap <= _float_gate(
            gates,
            "max_balanced_accuracy_overfit_gap",
            0.30,
        )
        passes_f1_overfit = macro_f1_gap <= _float_gate(
            gates,
            "max_macro_f1_overfit_gap",
            0.30,
        )
        passes_stratified = (
            delta_bal_stratified > 0.0
            if _bool_gate(
                gates,
                "require_real_model_beats_stratified_on_balanced_accuracy",
                True,
            )
            else True
        )

        passes_all = bool(
            is_real_model
            and passes_majority_bal
            and passes_majority_f1
            and passes_fragile
            and passes_bal_overfit
            and passes_f1_overfit
            and passes_stratified
        )

        rows.append(
            {
                "model_id": model_id,
                "family": family,
                "is_real_model": is_real_model,
                "validation_balanced_accuracy": row["balanced_accuracy"],
                "validation_macro_f1": row["macro_f1"],
                "validation_fragile_recall": fragile_recall,
                "delta_balanced_accuracy_vs_majority": delta_bal_majority,
                "delta_macro_f1_vs_majority": delta_f1_majority,
                "delta_balanced_accuracy_vs_stratified": delta_bal_stratified,
                "balanced_accuracy_gap": balanced_gap,
                "macro_f1_gap": macro_f1_gap,
                "passes_majority_balanced_accuracy_gate": passes_majority_bal,
                "passes_majority_macro_f1_gate": passes_majority_f1,
                "passes_fragile_recall_gate": passes_fragile,
                "passes_balanced_accuracy_overfit_gate": passes_bal_overfit,
                "passes_macro_f1_overfit_gate": passes_f1_overfit,
                "passes_stratified_baseline_gate": passes_stratified,
                "passes_all_validation_gates": passes_all,
                "holdout_preregistration_permission": False,
                "model_selected": False,
                "signal_permission": False,
                "backtest_permission": False,
                "candidate_promotion": False,
            }
        )

    return pd.DataFrame(rows)


def _phase13_boundaries(section: dict[str, Any]) -> pd.DataFrame:
    rows = []

    for key in ["phase13ap_boundary", "phase13aq_boundary"]:
        boundary = section.get(key, {})
        allowed = str(
            boundary.get("allowed_next_step", boundary.get("allowed_future_step", ""))
        ).lower()
        forbidden = str(
            boundary.get("forbidden_next_step", boundary.get("forbidden_future_step", ""))
        ).lower()

        rows.append(
            {
                "boundary": key,
                "allowed": allowed,
                "forbidden": forbidden,
                "passed": bool(
                    ("audit" in allowed or "decision" in allowed)
                    and "holdout prediction" in forbidden
                    and "feature importance" in forbidden
                    and "strategy backtest" in forbidden
                ),
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def save_phase13ao_registered_redesigned_model_training(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13ao_registered_redesigned_model_training")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    phase13an_check = _phase_result_check(
        source_reports["phase13an_conclusion"],
        source_reports["phase13an_gate_report"],
        "Phase 13AN",
    )

    model_run_spec = _read_csv_if_exists(source_reports["model_run_spec"])
    feature_policy_frame = _read_csv_if_exists(source_reports["feature_policy"])
    model_families = _read_csv_if_exists(source_reports["registered_model_families"])
    success_gates_frame = _read_csv_if_exists(source_reports["validation_success_gates"])
    candidate = _read_csv_if_exists(source_reports["candidate_target_decision_report"])
    assignment = _read_csv_if_exists(source_reports["target_assignment_panel"])
    dataset = _read_csv_if_exists(source_reports["dataset"])

    target_id = ""
    if not candidate.empty:
        target_id = str(candidate.iloc[0].get("candidate_target_variant", ""))

    if not target_id and not model_run_spec.empty:
        target_id = str(
            model_run_spec.iloc[0].get(
                "primary_target_variant_fallback",
                "return_drawdown_63d_composite",
            )
        )

    labels = [
        str(item)
        for item in section.get("model_training_policy", {}).get(
            "allowed_target_classes",
            ["supportive", "neutral", "fragile"],
        )
    ]

    combined = _combine_dataset_and_target(dataset, assignment, target_id)
    feature_policy = _policy_frame_to_dict(feature_policy_frame)
    numeric_features, categorical_features = _feature_columns(combined, feature_policy)

    train = _split_rows(combined, "train", labels)
    validation = _split_rows(combined, "validation", labels)

    x_train = train[numeric_features + categorical_features]
    y_train = train["redesigned_target"].astype(str)
    x_validation = validation[numeric_features + categorical_features]
    y_validation = validation["redesigned_target"].astype(str)

    preprocessor = _make_preprocessor(numeric_features, categorical_features)

    execution_rows = []
    metric_rows = []
    confusion_rows = []
    class_rows = []
    calibration_rows = []
    prediction_rows = []

    for _, model_row in model_families.iterrows():
        model_id = str(model_row["model_id"])
        family = str(model_row["family"])

        estimator = _make_model(model_row)
        pipeline = Pipeline(
            [
                ("preprocessor", preprocessor),
                ("model", estimator),
            ]
        )

        pipeline.fit(x_train, y_train)

        train_pred = pipeline.predict(x_train)
        validation_pred = pipeline.predict(x_validation)

        train_proba = _predict_proba_aligned(pipeline, x_train, labels)
        validation_proba = _predict_proba_aligned(pipeline, x_validation, labels)

        metric_rows.append(
            _metric_row(model_id, family, "train", y_train, train_pred, labels)
        )
        metric_rows.append(
            _metric_row(
                model_id,
                family,
                "validation",
                y_validation,
                validation_pred,
                labels,
            )
        )

        confusion_rows.extend(
            _confusion_rows(model_id, "train", y_train, train_pred, labels)
        )
        confusion_rows.extend(
            _confusion_rows(
                model_id,
                "validation",
                y_validation,
                validation_pred,
                labels,
            )
        )

        class_rows.extend(
            _class_recall_rows(model_id, "train", y_train, train_pred, labels)
        )
        class_rows.extend(
            _class_recall_rows(
                model_id,
                "validation",
                y_validation,
                validation_pred,
                labels,
            )
        )

        calibration_rows.extend(
            _calibration_rows(model_id, "train", y_train, train_pred, train_proba)
        )
        calibration_rows.extend(
            _calibration_rows(
                model_id,
                "validation",
                y_validation,
                validation_pred,
                validation_proba,
            )
        )

        prediction_rows.extend(
            _prediction_rows(
                model_id,
                validation,
                y_validation,
                validation_pred,
                labels,
                validation_proba,
            )
        )

        execution_rows.append(
            {
                "model_id": model_id,
                "family": family,
                "trained": True,
                "train_rows": len(train),
                "validation_rows": len(validation),
                "holdout_rows_used": 0,
                "validation_predictions_generated": True,
                "holdout_predictions_generated": False,
                "feature_importance_calculated": False,
                "model_selected": False,
                "signal_created": False,
                "backtest_run": False,
                "candidate_promotion": False,
            }
        )

    metrics = pd.DataFrame(metric_rows)
    baseline = _baseline_comparison(metrics)
    confusion = pd.DataFrame(confusion_rows)
    class_recall = pd.DataFrame(class_rows)
    calibration = pd.DataFrame(calibration_rows)
    overfit = _overfit_report(metrics)
    success_gates = _policy_frame_to_dict(success_gates_frame)
    success = _success_report(metrics, baseline, class_recall, overfit, success_gates)
    predictions = pd.DataFrame(prediction_rows)
    execution = pd.DataFrame(execution_rows)
    boundary = _phase13_boundaries(section)
    scope = _scope_check(section)

    validation_predictions_only = (
        not predictions.empty
        and set(predictions["split_label"].astype(str)) == {"validation"}
        and not predictions["holdout_prediction"].map(_bool_value).any()
    )

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "target_variant": target_id,
                "phase13an_passed": bool(phase13an_check["passed"].all()),
                "models_trained": int(execution["trained"].map(_bool_value).sum())
                if not execution.empty
                else 0,
                "train_rows": len(train),
                "validation_rows": len(validation),
                "numeric_feature_columns": len(numeric_features),
                "categorical_feature_columns": len(categorical_features),
                "metric_rows": len(metrics),
                "baseline_comparison_rows": len(baseline),
                "class_recall_rows": len(class_recall),
                "overfit_rows": len(overfit),
                "success_rows": len(success),
                "validation_prediction_rows": len(predictions),
                "validation_predictions_only": validation_predictions_only,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "holdout_predictions": False,
                "feature_importance": False,
                "model_selection": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AN passed",
                bool(summary.iloc[0]["phase13an_passed"]),
                "phase13an",
            ),
            _gate_row(
                "Registered models trained",
                int(summary.iloc[0]["models_trained"]) >= 5,
                f"models={summary.iloc[0]['models_trained']}",
            ),
            _gate_row(
                "Train/validation metrics exist",
                len(metrics) >= 10,
                f"rows={len(metrics)}",
            ),
            _gate_row(
                "Validation predictions only",
                validation_predictions_only,
                "validation only",
            ),
            _gate_row(
                "Baseline comparison report exists",
                len(baseline) >= 5,
                f"rows={len(baseline)}",
            ),
            _gate_row(
                "Class recall report exists",
                len(class_recall) >= 30,
                f"rows={len(class_recall)}",
            ),
            _gate_row(
                "Overfit report exists",
                len(overfit) >= 5,
                f"rows={len(overfit)}",
            ),
            _gate_row(
                "Success report exists",
                len(success) >= 5,
                f"rows={len(success)}",
            ),
            _gate_row(
                "No holdout predictions",
                bool(not summary.iloc[0]["holdout_predictions"]),
                "holdout blocked",
            ),
            _gate_row(
                "No feature importance",
                bool(not summary.iloc[0]["feature_importance"]),
                "feature importance blocked",
            ),
            _gate_row(
                "No model selection",
                bool(not summary.iloc[0]["model_selection"]),
                "model selection blocked",
            ),
            _gate_row(
                "No signal/backtest/promotion",
                bool(
                    not summary.iloc[0]["signal_creation"]
                    and not summary.iloc[0]["strategy_backtest"]
                    and not summary.iloc[0]["candidate_promotion"]
                ),
                "scope",
            ),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role")
                == "Registered redesigned model training on train/validation only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AO",
                "diagnostic": "Registered redesigned model training execution",
                "verdict": (
                    "Completed — registered redesigned model training passed"
                    if bool(gate_report["passed"].all())
                    else "Failed registered redesigned model training"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase13an_result_check": phase13an_check,
        "model_execution_report": execution,
        "metric_report": metrics,
        "baseline_comparison_report": baseline,
        "confusion_matrix_report": confusion,
        "class_recall_report": class_recall,
        "calibration_report": calibration,
        "overfit_report": overfit,
        "success_report": success,
        "validation_predictions": predictions,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13ao_model_training_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AO redesigned model training reports.")
    return outputs


def _forbidden_output_check(paths: list[str]) -> pd.DataFrame:
    rows = []

    for path in paths:
        report_path = Path(path)
        rows.append(
            {
                "path": str(report_path),
                "present": report_path.exists(),
                "passed": not report_path.exists(),
                "result": "Passed" if not report_path.exists() else "Failed",
            }
        )

    return pd.DataFrame(rows)


def _phase13aq_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    boundary = section.get("phase13aq_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": "phase13aq_boundary_is_decision_only",
            "passed": "decision" in allowed,
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": "phase13aq_boundary_blocks_forbidden_actions",
            "passed": bool(
                "holdout prediction" in forbidden
                and "feature importance" in forbidden
                and "strategy backtest" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def save_phase13ap_redesigned_model_training_result_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13ap_redesigned_model_training_result_audit")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = []
    for key, expected in section.get("expected_runtime_flags", {}).items():
        actual = config.get(key, {}).get("enabled")
        flags.append(
            {
                "config_key": key,
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": actual is expected,
            }
        )

    config_check = pd.DataFrame(flags)
    config_check["result"] = config_check["passed"].map(
        {True: "Passed", False: "Failed"}
    )

    reports = section.get("phase13ao_reports", {})
    inventory = _source_report_check(reports)
    phase13ao_check = _phase_result_check(
        reports["conclusion"],
        reports["gate_report"],
        "Phase 13AO",
    )

    predictions = _read_csv_if_exists(reports["validation_predictions"])
    success = _read_csv_if_exists(reports["success_report"])
    baseline = _read_csv_if_exists(reports["baseline_comparison_report"])
    class_recall = _read_csv_if_exists(reports["class_recall_report"])

    validation_predictions_only = (
        not predictions.empty
        and set(predictions["split_label"].astype(str)) == {"validation"}
        and not predictions["holdout_prediction"].map(_bool_value).any()
    )

    forbidden = _forbidden_output_check(section.get("forbidden_output_paths", []))
    boundary = _phase13aq_boundary_check(section)
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "phase13ao_passed": bool(phase13ao_check["passed"].all()),
                "config_flags_clean": bool(config_check["passed"].all()),
                "result_reports_present": bool(inventory["present"].all())
                if not inventory.empty
                else False,
                "validation_predictions_only": validation_predictions_only,
                "success_report_rows": len(success),
                "baseline_comparison_rows": len(baseline),
                "class_recall_rows": len(class_recall),
                "forbidden_outputs_absent": bool(forbidden["passed"].all())
                if not forbidden.empty
                else True,
                "phase13aq_boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "holdout_predictions": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AO passed",
                bool(summary.iloc[0]["phase13ao_passed"]),
                "phase13ao",
            ),
            _gate_row(
                "Config flags clean",
                bool(summary.iloc[0]["config_flags_clean"]),
                "runtime flags",
            ),
            _gate_row(
                "Result reports present",
                bool(summary.iloc[0]["result_reports_present"]),
                "inventory",
            ),
            _gate_row(
                "Validation predictions only",
                validation_predictions_only,
                "validation only",
            ),
            _gate_row(
                "Success report present",
                len(success) > 0,
                f"rows={len(success)}",
            ),
            _gate_row(
                "Baseline comparison present",
                len(baseline) > 0,
                f"rows={len(baseline)}",
            ),
            _gate_row(
                "Class recall present",
                len(class_recall) > 0,
                f"rows={len(class_recall)}",
            ),
            _gate_row(
                "Forbidden outputs absent",
                bool(summary.iloc[0]["forbidden_outputs_absent"]),
                "forbidden outputs",
            ),
            _gate_row(
                "Phase 13AQ boundary is decision-only",
                bool(boundary["passed"].all()),
                "phase13aq",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Redesigned model training result and leakage audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AP",
                "diagnostic": "Redesigned model training result and leakage audit",
                "verdict": (
                    "Completed — redesigned model training result audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed redesigned model training result audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "config_flag_check": config_check,
        "report_inventory_check": inventory,
        "phase13ao_result_check": phase13ao_check,
        "prediction_boundary_check": pd.DataFrame(
            [
                {
                    "check": "validation_predictions_only",
                    "passed": validation_predictions_only,
                    "result": "Passed" if validation_predictions_only else "Failed",
                }
            ]
        ),
        "forbidden_output_check": forbidden,
        "phase13aq_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13ap_model_audit_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AP redesigned model training audit reports.")
    return outputs


def _phase13ar_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    boundary = section.get("phase13ar_boundary", {})
    allowed_pass = str(boundary.get("allowed_next_step_if_passed", "")).lower()
    allowed_fail = str(boundary.get("allowed_next_step_if_failed", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": "passed_boundary_is_holdout_preregistration_only",
            "passed": "holdout" in allowed_pass and "pre-registration" in allowed_pass,
            "detail": boundary.get("allowed_next_step_if_passed", ""),
        },
        {
            "check": "failed_boundary_is_kill_pause_or_redesign_only",
            "passed": (
                "kill" in allowed_fail
                or "pause" in allowed_fail
                or "redesign" in allowed_fail
            ),
            "detail": boundary.get("allowed_next_step_if_failed", ""),
        },
        {
            "check": "boundary_blocks_forbidden_actions",
            "passed": bool(
                "holdout prediction" in forbidden
                and "feature importance" in forbidden
                and "strategy backtest" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _validation_ranking(success: pd.DataFrame) -> pd.DataFrame:
    if success.empty:
        return pd.DataFrame()

    ranking = success.copy()
    ranking = ranking[ranking["is_real_model"].map(_bool_value)].copy()

    if ranking.empty:
        return pd.DataFrame()

    ranking["validation_balanced_accuracy"] = pd.to_numeric(
        ranking["validation_balanced_accuracy"],
        errors="coerce",
    )
    ranking["validation_macro_f1"] = pd.to_numeric(
        ranking["validation_macro_f1"],
        errors="coerce",
    )

    ranking = ranking.sort_values(
        ["passes_all_validation_gates", "validation_balanced_accuracy", "validation_macro_f1"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranking["diagnostic_rank"] = ranking.index + 1
    ranking["model_selected"] = False
    ranking["holdout_predictions_generated"] = False
    return ranking


def save_phase13aq_validation_to_holdout_decision(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13aq_validation_to_holdout_decision")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    source_check = _source_report_check(source_reports)
    phase13ap_check = _phase_result_check(
        source_reports["phase13ap_conclusion"],
        source_reports["phase13ap_gate_report"],
        "Phase 13AP",
    )

    success = _read_csv_if_exists(source_reports["success_report"])
    ranking = _validation_ranking(success)

    passing = ranking[
        ranking["passes_all_validation_gates"].map(_bool_value)
    ].copy() if not ranking.empty else pd.DataFrame()

    holdout_justified = not passing.empty
    leading_model = str(passing.iloc[0]["model_id"]) if holdout_justified else (
        str(ranking.iloc[0]["model_id"]) if not ranking.empty else ""
    )

    if holdout_justified:
        decision = section.get("decision_policy", {}).get(
            "if_any_real_model_passes_all_validation_gates",
            "justify_holdout_preregistration",
        )
        decision_reason = (
            "At least one real model passed all pre-registered validation gates."
        )
    else:
        decision = section.get("decision_policy", {}).get(
            "if_no_real_model_passes_all_validation_gates",
            "do_not_proceed_to_holdout",
        )
        decision_reason = (
            "No real model passed all pre-registered validation gates; "
            "holdout remains blocked."
        )

    decision_report = pd.DataFrame(
        [
            {
                "decision": decision,
                "decision_reason": decision_reason,
                "diagnostic_leading_model": leading_model,
                "holdout_preregistration_justified": holdout_justified,
                "holdout_predictions_generated": False,
                "model_selected": False,
                "feature_importance_permission": False,
                "signal_permission": False,
                "backtest_permission": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    boundary = _phase13ar_boundary_check(section)
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "decision_role": section.get("decision_role", ""),
                "phase13ap_passed": bool(phase13ap_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all())
                if not source_check.empty
                else False,
                "real_model_rows": len(ranking),
                "passing_real_model_rows": len(passing),
                "decision": decision,
                "holdout_preregistration_justified": holdout_justified,
                "diagnostic_leading_model": leading_model,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "holdout_predictions": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AP passed",
                bool(summary.iloc[0]["phase13ap_passed"]),
                "phase13ap",
            ),
            _gate_row(
                "Success report present",
                len(success) > 0,
                f"rows={len(success)}",
            ),
            _gate_row(
                "Decision report exists",
                len(decision_report) == 1,
                decision,
            ),
            _gate_row(
                "No holdout predictions",
                bool(not summary.iloc[0]["holdout_predictions"]),
                "holdout blocked",
            ),
            _gate_row(
                "No model selection",
                bool(not summary.iloc[0]["model_selection"]),
                "model selection blocked",
            ),
            _gate_row(
                "No feature importance",
                bool(not summary.iloc[0]["feature_importance"]),
                "feature importance blocked",
            ),
            _gate_row(
                "No signal/backtest/promotion",
                bool(
                    not summary.iloc[0]["signal_creation"]
                    and not summary.iloc[0]["strategy_backtest"]
                    and not summary.iloc[0]["candidate_promotion"]
                ),
                "scope",
            ),
            _gate_row(
                "Phase 13AR boundary is conditional preregistration only",
                bool(boundary["passed"].all()),
                "phase13ar",
            ),
            _gate_row(
                "Decision role is correct",
                section.get("decision_role") == "Validation-to-holdout decision only",
                section.get("decision_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AQ",
                "diagnostic": "Validation-to-holdout decision",
                "verdict": (
                    "Completed — validation-to-holdout decision passed"
                    if bool(gate_report["passed"].all())
                    else "Failed validation-to-holdout decision"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "holdout_preregistration_justified": holdout_justified,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13ap_result_check": phase13ap_check,
        "validation_ranking_report": ranking,
        "decision_report": decision_report,
        "phase13ar_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13aq_holdout_decision_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AQ validation-to-holdout decision reports.")
    return outputs