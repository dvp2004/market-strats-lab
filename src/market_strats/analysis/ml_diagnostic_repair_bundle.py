from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from market_strats.analysis.ml_registered_training_and_result_audit import (
    _bool_value,
    _read_csv_if_exists,
    _safe_one_hot_encoder,
)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _gate_row(gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"gate": gate, "passed": bool(passed), "result": "Passed" if passed else "Failed", "detail": detail}


def _config_section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return config.get(key, {}) or {}


def _source_report_check(paths: dict[str, str]) -> pd.DataFrame:
    rows = []
    for key, path in paths.items():
        p = Path(path)
        frame = _read_csv_if_exists(p)
        rows.append({"report_key": key, "path": str(p), "present": p.exists(), "rows": len(frame)})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def _phase_result_check(conclusion_path: str, gate_path: str, phase_name: str) -> pd.DataFrame:
    conclusion = _read_csv_if_exists(conclusion_path)
    gate = _read_csv_if_exists(gate_path)
    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_passed = not gate.empty and "passed" in gate.columns and bool(gate["passed"].map(_bool_value).all())
    out = pd.DataFrame(
        [
            {"check": f"{phase_name} conclusion passed", "passed": conclusion_passed, "detail": "conclusion"},
            {"check": f"{phase_name} gate report passed", "passed": gate_passed, "detail": "gate_report"},
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


def save_phase13y_ml_diagnostic_repair_preregistration(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    section = _config_section(config, "phase13y_ml_diagnostic_repair_preregistration")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_check = _source_report_check(section.get("source_reports", {}))
    phase13x_check = _phase_result_check(
        section["source_reports"]["phase13x_conclusion"],
        section["source_reports"]["phase13x_gate_report"],
        "Phase 13X",
    )
    decision = _read_csv_if_exists(section["source_reports"]["continuation_decision_report"])

    targets = pd.DataFrame(section.get("repair_targets", []))
    hypotheses = pd.DataFrame(section.get("registered_repair_hypotheses", []))
    success_gates = pd.DataFrame([section.get("repair_success_gates", {})])

    continuation_is_repair = (
        not decision.empty
        and str(decision.iloc[0].get("decision", "")) == "continue_only_after_model_diagnostic_repair"
    )

    boundary_rows = [
        {"boundary": "phase13z", "allowed": section.get("phase13z_boundary", {}).get("allowed_next_step", ""), "passed": "readiness" in str(section.get("phase13z_boundary", {}).get("allowed_next_step", "")).lower()},
        {"boundary": "phase13aa", "allowed": section.get("phase13aa_boundary", {}).get("allowed_future_step", ""), "passed": "train/validation" in str(section.get("phase13aa_boundary", {}).get("allowed_future_step", "")).lower()},
    ]
    boundary = pd.DataFrame(boundary_rows)
    boundary["result"] = boundary["passed"].map({True: "Passed", False: "Failed"})
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "spec_role": section.get("spec_role", ""),
                "source_reports_present": bool(source_check["present"].all()) if not source_check.empty else False,
                "phase13x_passed": bool(phase13x_check["passed"].all()),
                "continuation_is_repair": continuation_is_repair,
                "repair_target_rows": len(targets),
                "repair_hypothesis_rows": len(hypotheses),
                "success_gate_rows": len(success_gates),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "repair_execution": False,
                "holdout_predictions": False,
                "model_selection": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate = pd.DataFrame(
        [
            _gate_row("Phase 13X passed", bool(summary.iloc[0]["phase13x_passed"]), "phase13x"),
            _gate_row("Continuation decision requires repair", continuation_is_repair, str(decision.iloc[0].get("decision", "")) if not decision.empty else "missing"),
            _gate_row("Repair targets registered", len(targets) >= 3, f"rows={len(targets)}"),
            _gate_row("Repair hypotheses registered", len(hypotheses) >= 4, f"rows={len(hypotheses)}"),
            _gate_row("Success gates registered", len(success_gates) == 1, f"rows={len(success_gates)}"),
            _gate_row("Boundaries passed", bool(boundary["passed"].all()), "phase13z/phase13aa"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row("Spec role is correct", section.get("spec_role") == "ML diagnostic repair pre-registration spec only", section.get("spec_role", "")),
        ]
    )
    gate["all_gates_passed"] = bool(gate["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13Y",
                "diagnostic": "ML diagnostic repair pre-registration spec",
                "verdict": "Completed — ML diagnostic repair pre-registration spec passed" if bool(gate["passed"].all()) else "Failed ML diagnostic repair pre-registration spec",
                "all_gates_passed": bool(gate["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13x_result_check": phase13x_check,
        "repair_target_registry": targets,
        "hypothesis_registry": hypotheses,
        "success_gate_registry": success_gates,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13y_repair_prereg_{name}.csv", index=False)

    print("Wrote Phase 13Y repair pre-registration reports.")
    return outputs


def save_phase13z_ml_diagnostic_repair_readiness_audit(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    section = _config_section(config, "phase13z_ml_diagnostic_repair_readiness_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = []
    for key, expected in section.get("expected_runtime_flags", {}).items():
        actual = config.get(key, {}).get("enabled")
        flags.append({"config_key": key, "expected": expected, "actual": actual, "passed": actual is expected})
    config_check = pd.DataFrame(flags)
    config_check["result"] = config_check["passed"].map({True: "Passed", False: "Failed"})

    y_reports = section.get("phase13y_reports", {})
    inventory = _source_report_check(y_reports)
    y_check = _phase_result_check(y_reports["conclusion"], y_reports["gate_report"], "Phase 13Y")
    hypotheses = _read_csv_if_exists(y_reports["repair_hypothesis_registry"])
    success = _read_csv_if_exists(y_reports["repair_success_gate_registry"])
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "phase13y_passed": bool(y_check["passed"].all()),
                "config_flags_clean": bool(config_check["passed"].all()),
                "repair_hypothesis_rows": len(hypotheses),
                "success_gate_rows": len(success),
                "scope_passed": bool(scope["passed"].all()),
                "repair_execution": False,
                "holdout_predictions": False,
                "signal_creation": False,
                "strategy_backtest": False,
            }
        ]
    )

    gate = pd.DataFrame(
        [
            _gate_row("Phase 13Y passed", bool(summary.iloc[0]["phase13y_passed"]), "phase13y"),
            _gate_row("Config flags clean", bool(summary.iloc[0]["config_flags_clean"]), "flags"),
            _gate_row("Repair hypotheses present", len(hypotheses) >= 4, f"rows={len(hypotheses)}"),
            _gate_row("Success gates present", len(success) == 1, f"rows={len(success)}"),
            _gate_row("Scope blocks forbidden actions", bool(summary.iloc[0]["scope_passed"]), "scope"),
            _gate_row("Audit role is correct", section.get("audit_role") == "ML diagnostic repair readiness and boundary audit only", section.get("audit_role", "")),
        ]
    )
    gate["all_gates_passed"] = bool(gate["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13Z",
                "diagnostic": "ML diagnostic repair readiness audit",
                "verdict": "Completed — ML diagnostic repair readiness audit passed" if bool(gate["passed"].all()) else "Failed ML diagnostic repair readiness audit",
                "all_gates_passed": bool(gate["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "report_inventory_check": inventory,
        "phase13y_result_check": y_check,
        "config_flag_check": config_check,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13z_repair_readiness_{name}.csv", index=False)

    print("Wrote Phase 13Z repair readiness reports.")
    return outputs


def _feature_columns(dataset: pd.DataFrame, section: dict[str, Any]) -> tuple[list[str], list[str]]:
    policy = section.get("dataset_policy", {})
    prefixes = policy.get("feature_prefixes", {})
    numeric_prefixes = tuple(_as_list(prefixes.get("numeric")))
    categorical_prefixes = tuple(_as_list(prefixes.get("categorical")))
    forbidden = [str(x).lower() for x in _as_list(policy.get("forbidden_feature_fragments"))]

    numeric = [c for c in dataset.columns if str(c).startswith(numeric_prefixes) and not any(f in str(c).lower() for f in forbidden)]
    categorical = [c for c in dataset.columns if str(c).startswith(categorical_prefixes) and not any(f in str(c).lower() for f in forbidden)]
    return numeric, categorical


def _make_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    numeric_pipe = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    categorical_pipe = Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", _safe_one_hot_encoder())])
    return ColumnTransformer(
        [("numeric", numeric_pipe, numeric), ("categorical", categorical_pipe, categorical)],
        remainder="drop",
        sparse_threshold=0.0,
    )


def _make_repair_model(row: pd.Series):
    family = str(row["base_model_family"])
    if family == "random_forest":
        class_weight = None
        if "class_weight" in row and isinstance(row["class_weight"], dict):
            class_weight = row["class_weight"]
        return RandomForestClassifier(
            n_estimators=int(row.get("n_estimators", 300)),
            max_depth=int(row.get("max_depth", 3)),
            min_samples_leaf=int(row.get("min_samples_leaf", 30)),
            class_weight=class_weight or "balanced",
            random_state=42,
            n_jobs=-1,
        )
    if family == "logistic_regression":
        return LogisticRegression(
            C=float(row.get("C", 0.25)),
            max_iter=int(row.get("max_iter", 1000)),
            class_weight="balanced",
            random_state=42,
        )
    if family == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_iter=int(row.get("max_iter", 80)),
            learning_rate=float(row.get("learning_rate", 0.03)),
            max_leaf_nodes=int(row.get("max_leaf_nodes", 7)),
            l2_regularization=float(row.get("l2_regularization", 1.0)),
            random_state=42,
        )
    raise ValueError(f"Unsupported repair model family: {family}")


def _model_rows(dataset: pd.DataFrame, section: dict[str, Any], split: str) -> pd.DataFrame:
    policy = section.get("dataset_policy", {})
    target = policy["primary_target_id"]
    available_col = policy["target_available_column"]
    unavailable = policy["unavailable_target_class"]

    frame = dataset[dataset["split_label"].astype(str).eq(split)].copy()
    frame = frame[frame[available_col].map(_bool_value)]
    frame = frame[~frame[target].astype(str).eq(unavailable)]
    return frame.reset_index(drop=True)


def _metrics(model_id: str, split: str, y_true: pd.Series, y_pred: np.ndarray, labels: list[str]) -> dict[str, Any]:
    return {
        "repair_id": model_id,
        "split_label": split,
        "rows": len(y_true),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0),
        "macro_recall": recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0),
        "model_selected": False,
        "signal_created": False,
    }


def save_phase13aa_registered_ml_diagnostic_repair_execution(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    section = _config_section(config, "phase13aa_registered_ml_diagnostic_repair_execution")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source = section.get("source_reports", {})
    z_check = _phase_result_check(source["phase13z_conclusion"], source["phase13z_gate_report"], "Phase 13Z")
    dataset = _read_csv_if_exists(source["dataset"])
    y_hypotheses = _read_csv_if_exists(
        reports_path / "phase13y_repair_prereg_hypothesis_registry.csv"
    )
    success_gate = _read_csv_if_exists(
        reports_path / "phase13y_repair_prereg_success_gate_registry.csv"
    )

    policy = section.get("dataset_policy", {})
    target = policy["primary_target_id"]
    labels = _as_list(policy["allowed_target_classes"])
    numeric, categorical = _feature_columns(dataset, section)

    train = _model_rows(dataset, section, policy["train_split_label"])
    validation = _model_rows(dataset, section, policy["validation_split_label"])

    x_train = train[numeric + categorical]
    y_train = train[target].astype(str)
    x_val = validation[numeric + categorical]
    y_val = validation[target].astype(str)

    metric_rows = []
    recall_rows = []
    overfit_rows = []
    pred_rows = []
    exec_rows = []

    for _, hyp in y_hypotheses.iterrows():
        if not _bool_value(hyp.get("allowed", True)):
            continue

        repair_id = str(hyp["repair_id"])
        model = Pipeline([("preprocessor", _make_preprocessor(numeric, categorical)), ("model", _make_repair_model(hyp))])
        model.fit(x_train, y_train)

        train_pred = model.predict(x_train)
        val_pred = model.predict(x_val)

        train_m = _metrics(repair_id, "train", y_train, train_pred, labels)
        val_m = _metrics(repair_id, "validation", y_val, val_pred, labels)
        metric_rows.extend([train_m, val_m])

        overfit_rows.append(
            {
                "repair_id": repair_id,
                "train_balanced_accuracy": train_m["balanced_accuracy"],
                "validation_balanced_accuracy": val_m["balanced_accuracy"],
                "balanced_accuracy_gap": train_m["balanced_accuracy"] - val_m["balanced_accuracy"],
                "train_macro_f1": train_m["macro_f1"],
                "validation_macro_f1": val_m["macro_f1"],
                "macro_f1_gap": train_m["macro_f1"] - val_m["macro_f1"],
            }
        )

        for cls in labels:
            cls_mask = y_val.eq(cls)
            support = int(cls_mask.sum())
            correct = int((pd.Series(val_pred).astype(str).eq(cls) & cls_mask.reset_index(drop=True)).sum())
            recall = correct / support if support else 0.0
            recall_rows.append(
                {
                    "repair_id": repair_id,
                    "class_label": cls,
                    "validation_support": support,
                    "validation_recall": recall,
                    "fragile_recall_warning": cls == "fragile" and recall < 0.20,
                }
            )

        for idx, pred in enumerate(val_pred):
            pred_rows.append(
                {
                    "repair_id": repair_id,
                    "split_label": "validation",
                    "decision_date": validation.iloc[idx].get("decision_date", ""),
                    "actual_class": y_val.iloc[idx],
                    "predicted_class": pred,
                    "holdout_prediction": False,
                    "signal_created": False,
                }
            )

        exec_rows.append(
            {
                "repair_id": repair_id,
                "trained": True,
                "train_rows": len(train),
                "validation_rows": len(validation),
                "holdout_rows_used": 0,
                "holdout_predictions_generated": False,
                "model_selected": False,
                "feature_importance_calculated": False,
                "signal_created": False,
            }
        )

    metrics = pd.DataFrame(metric_rows)
    recalls = pd.DataFrame(recall_rows)
    overfit = pd.DataFrame(overfit_rows)
    preds = pd.DataFrame(pred_rows)
    execution = pd.DataFrame(exec_rows)

    if metrics.empty:
        metrics = pd.DataFrame(
            columns=[
                "repair_id",
                "split_label",
                "rows",
                "balanced_accuracy",
                "macro_f1",
                "macro_recall",
                "model_selected",
                "signal_created",
            ]
        )

    if recalls.empty:
        recalls = pd.DataFrame(
            columns=[
                "repair_id",
                "class_label",
                "validation_support",
                "validation_recall",
                "fragile_recall_warning",
            ]
        )

    if overfit.empty:
        overfit = pd.DataFrame(
            columns=[
                "repair_id",
                "train_balanced_accuracy",
                "validation_balanced_accuracy",
                "balanced_accuracy_gap",
                "train_macro_f1",
                "validation_macro_f1",
                "macro_f1_gap",
            ]
        )

    if preds.empty:
        preds = pd.DataFrame(
            columns=[
                "repair_id",
                "split_label",
                "decision_date",
                "actual_class",
                "predicted_class",
                "holdout_prediction",
                "signal_created",
            ]
        )

    if execution.empty:
        execution = pd.DataFrame(
            columns=[
                "repair_id",
                "trained",
                "train_rows",
                "validation_rows",
                "holdout_rows_used",
                "holdout_predictions_generated",
                "model_selected",
                "feature_importance_calculated",
                "signal_created",
            ]
        )

    gate_values = success_gate.iloc[0].to_dict() if not success_gate.empty else {}
    majority_bal = 0.3333333333333333
    majority_f1 = 0.2049518569463548

    success_rows = []
    for _, row in metrics[metrics["split_label"].eq("validation")].iterrows():
        repair_id = row["repair_id"]
        fragile = recalls[(recalls["repair_id"].eq(repair_id)) & (recalls["class_label"].eq("fragile"))]
        overfit_row = overfit[overfit["repair_id"].eq(repair_id)].iloc[0]
        fragile_recall = float(fragile.iloc[0]["validation_recall"]) if not fragile.empty else 0.0
        success_rows.append(
            {
                "repair_id": repair_id,
                "validation_balanced_accuracy": row["balanced_accuracy"],
                "validation_macro_f1": row["macro_f1"],
                "validation_fragile_recall": fragile_recall,
                "delta_balanced_accuracy_vs_majority": row["balanced_accuracy"] - majority_bal,
                "delta_macro_f1_vs_majority": row["macro_f1"] - majority_f1,
                "balanced_accuracy_gap": overfit_row["balanced_accuracy_gap"],
                "macro_f1_gap": overfit_row["macro_f1_gap"],
                "passes_fragile_recall_gate": fragile_recall >= float(gate_values.get("min_validation_fragile_recall", 0.20)),
                "passes_majority_edge_gate": (row["balanced_accuracy"] - majority_bal) >= float(gate_values.get("min_delta_balanced_accuracy_vs_majority", 0.05)),
                "passes_overfit_gate": overfit_row["balanced_accuracy_gap"] <= float(gate_values.get("max_balanced_accuracy_overfit_gap", 0.30)),
                "model_selected": False,
                "signal_permission": False,
                "holdout_permission": False,
            }
        )
    success = pd.DataFrame(success_rows)

    scope = _scope_check(section)
    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "phase13z_passed": bool(z_check["passed"].all()),
                "repair_models_trained": int(execution["trained"].map(_bool_value).sum()) if not execution.empty else 0,
                "metric_rows": len(metrics),
                "class_recall_rows": len(recalls),
                "overfit_rows": len(overfit),
                "validation_prediction_rows": len(preds),
                "validation_predictions_only": bool(preds["split_label"].astype(str).eq("validation").all()) if not preds.empty else False,
                "scope_passed": bool(scope["passed"].all()),
                "holdout_predictions": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate = pd.DataFrame(
        [
            _gate_row("Phase 13Z passed", bool(summary.iloc[0]["phase13z_passed"]), "phase13z"),
            _gate_row("Repair models trained", int(summary.iloc[0]["repair_models_trained"]) >= 4, f"models={summary.iloc[0]['repair_models_trained']}"),
            _gate_row("Metric report exists", len(metrics) >= 8, f"rows={len(metrics)}"),
            _gate_row("Class recall report exists", len(recalls) >= 12, f"rows={len(recalls)}"),
            _gate_row("Overfit report exists", len(overfit) >= 4, f"rows={len(overfit)}"),
            _gate_row("Validation predictions only", bool(summary.iloc[0]["validation_predictions_only"]), "validation only"),
            _gate_row("Scope blocks forbidden actions", bool(summary.iloc[0]["scope_passed"]), "scope"),
            _gate_row("Execution role is correct", section.get("execution_role") == "Registered ML diagnostic repair execution on train/validation only", section.get("execution_role", "")),
        ]
    )
    gate["all_gates_passed"] = bool(gate["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AA",
                "diagnostic": "Registered ML diagnostic repair execution",
                "verdict": "Completed — registered ML diagnostic repair execution passed" if bool(gate["passed"].all()) else "Failed registered ML diagnostic repair execution",
                "all_gates_passed": bool(gate["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase13z_result_check": z_check,
        "model_execution_report": execution,
        "metric_report": metrics,
        "class_recall_report": recalls,
        "overfit_report": overfit,
        "success_report": success,
        "validation_predictions": preds,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13aa_repair_execution_{name}.csv", index=False)

    print("Wrote Phase 13AA repair execution reports.")
    return outputs


def save_phase13ab_ml_diagnostic_repair_result_audit(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    section = _config_section(config, "phase13ab_ml_diagnostic_repair_result_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    paths = section.get("phase13aa_reports", {})

    inventory = _source_report_check(paths)
    aa_check = _phase_result_check(paths["conclusion"], paths["gate_report"], "Phase 13AA")
    preds = _read_csv_if_exists(paths["validation_predictions"])
    success = _read_csv_if_exists(paths["repair_success_report"])
    scope = _scope_check(section)

    prediction_boundary_passed = (
        not preds.empty
        and set(preds["split_label"].dropna().astype(str)) == {"validation"}
        and not preds["holdout_prediction"].map(_bool_value).any()
    )

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "phase13aa_passed": bool(aa_check["passed"].all()),
                "reports_present": bool(inventory["present"].all()) if not inventory.empty else False,
                "success_report_rows": len(success),
                "prediction_boundary_passed": prediction_boundary_passed,
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

    gate = pd.DataFrame(
        [
            _gate_row("Phase 13AA passed", bool(summary.iloc[0]["phase13aa_passed"]), "phase13aa"),
            _gate_row("Result reports present", bool(summary.iloc[0]["reports_present"]), "inventory"),
            _gate_row("Repair success report exists", len(success) > 0, f"rows={len(success)}"),
            _gate_row("Validation predictions only", prediction_boundary_passed, "prediction boundary"),
            _gate_row("Scope blocks forbidden actions", bool(summary.iloc[0]["scope_passed"]), "scope"),
            _gate_row("Audit role is correct", section.get("audit_role") == "ML diagnostic repair result quality and leakage audit only", section.get("audit_role", "")),
        ]
    )
    gate["all_gates_passed"] = bool(gate["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AB",
                "diagnostic": "ML diagnostic repair result quality audit",
                "verdict": "Completed — ML diagnostic repair result quality audit passed" if bool(gate["passed"].all()) else "Failed ML diagnostic repair result quality audit",
                "all_gates_passed": bool(gate["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "report_inventory_check": inventory,
        "phase13aa_result_check": aa_check,
        "prediction_boundary_check": pd.DataFrame([{"check": "validation_predictions_only", "passed": prediction_boundary_passed, "result": "Passed" if prediction_boundary_passed else "Failed"}]),
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13ab_repair_audit_{name}.csv", index=False)

    print("Wrote Phase 13AB repair result audit reports.")
    return outputs