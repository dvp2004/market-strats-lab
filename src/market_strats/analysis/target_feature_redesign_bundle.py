from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


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
    rows: list[dict[str, Any]] = []

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
        "allow_model_training",
        "allow_repair_execution",
        "allow_model_selection",
        "allow_holdout_prediction_generation",
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


def _normalise_registry_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)

    for col in frame.columns:
        frame[col] = frame[col].apply(
            lambda value: "; ".join(map(str, value))
            if isinstance(value, list)
            else value
        )

    return frame


def _boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    rows = []

    for key in ["phase13ah_boundary", "phase13ai_boundary"]:
        boundary = section.get(key, {})
        allowed = str(
            boundary.get("allowed_next_step", boundary.get("allowed_future_step", ""))
        )
        forbidden = str(
            boundary.get(
                "forbidden_next_step",
                boundary.get("forbidden_future_step", ""),
            )
        )

        rows.append(
            {
                "boundary": key,
                "allowed": allowed,
                "forbidden": forbidden,
                "passed": bool(
                    (
                        "readiness" in allowed.lower()
                        or "panel execution" in allowed.lower()
                    )
                    and "model training" in forbidden.lower()
                    and "holdout prediction" in forbidden.lower()
                    and "feature importance" in forbidden.lower()
                    and "strategy backtest" in forbidden.lower()
                ),
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def save_phase13ag_target_feature_redesign_preregistration(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13ag_target_feature_redesign_preregistration")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    source_check = _source_report_check(source_reports)
    phase13af_check = _phase_result_check(
        source_reports["phase13af_conclusion"],
        source_reports["phase13af_gate_report"],
        "Phase 13AF",
    )
    architecture_decision = _read_csv_if_exists(
        source_reports["architecture_decision_report"]
    )

    decision_is_redesign = (
        not architecture_decision.empty
        and str(
            architecture_decision.iloc[0].get("architecture_decision", "")
        )
        == "pivot_to_target_feature_redesign_preregistration"
    )

    target_registry = _normalise_registry_rows(
        section.get("target_variant_registry", [])
    )
    target_quality_policy = pd.DataFrame(
        [
            {
                "policy_key": key,
                "policy_value": "; ".join(map(str, value))
                if isinstance(value, list)
                else value,
            }
            for key, value in section.get("target_quality_policy", {}).items()
        ]
    )
    feature_family_registry = _normalise_registry_rows(
        section.get("feature_family_registry", [])
    )
    diagnostic_panel_policy = pd.DataFrame(
        [
            {"policy_key": key, "policy_value": value}
            for key, value in section.get("diagnostic_panel_policy", {}).items()
        ]
    )
    boundary = _boundary_check(section)
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "spec_role": section.get("spec_role", ""),
                "phase_branch": section.get("phase_branch", ""),
                "source_phase": section.get("source_phase", ""),
                "proposed_next_phase": section.get("proposed_next_phase", ""),
                "phase13af_passed": bool(phase13af_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all())
                if not source_check.empty
                else False,
                "architecture_decision_is_redesign": decision_is_redesign,
                "target_variant_rows": len(target_registry),
                "feature_family_rows": len(feature_family_registry),
                "target_quality_policy_rows": len(target_quality_policy),
                "diagnostic_panel_policy_rows": len(diagnostic_panel_policy),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
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
                "Phase 13AF passed",
                bool(summary.iloc[0]["phase13af_passed"]),
                "phase13af",
            ),
            _gate_row(
                "Architecture decision is target-feature redesign",
                decision_is_redesign,
                "architecture_decision",
            ),
            _gate_row(
                "Target variant registry exists",
                len(target_registry) >= 4,
                f"rows={len(target_registry)}",
            ),
            _gate_row(
                "Feature family registry exists",
                len(feature_family_registry) >= 5,
                f"rows={len(feature_family_registry)}",
            ),
            _gate_row(
                "Target quality policy exists",
                len(target_quality_policy) > 0,
                f"rows={len(target_quality_policy)}",
            ),
            _gate_row(
                "Diagnostic panel policy exists",
                len(diagnostic_panel_policy) > 0,
                f"rows={len(diagnostic_panel_policy)}",
            ),
            _gate_row(
                "Boundaries passed",
                bool(boundary["passed"].all()),
                "phase13ah/phase13ai",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Spec role is correct",
                section.get("spec_role")
                == "Target-feature redesign pre-registration spec only",
                section.get("spec_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AG",
                "diagnostic": "Target-feature redesign pre-registration spec",
                "verdict": "Completed — target-feature redesign pre-registration passed"
                if bool(gate_report["passed"].all())
                else "Failed target-feature redesign pre-registration",
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13af_result_check": phase13af_check,
        "target_variant_registry": target_registry,
        "target_quality_policy": target_quality_policy,
        "feature_family_registry": feature_family_registry,
        "diagnostic_panel_policy": diagnostic_panel_policy,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13ag_redesign_prereg_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AG target-feature redesign pre-registration reports.")
    return outputs


def save_phase13ah_target_feature_redesign_readiness_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13ah_target_feature_redesign_readiness_audit")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flag_rows = []
    for key, expected in section.get("expected_runtime_flags", {}).items():
        actual = config.get(key, {}).get("enabled")
        flag_rows.append(
            {
                "config_key": key,
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": actual is expected,
            }
        )

    config_check = pd.DataFrame(flag_rows)
    config_check["result"] = config_check["passed"].map(
        {True: "Passed", False: "Failed"}
    )

    reports = section.get("phase13ag_reports", {})
    inventory = _source_report_check(reports)
    phase13ag_check = _phase_result_check(
        reports["conclusion"],
        reports["gate_report"],
        "Phase 13AG",
    )
    target_variants = _read_csv_if_exists(reports["target_variant_registry"])
    feature_families = _read_csv_if_exists(reports["feature_family_registry"])
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "phase13ag_passed": bool(phase13ag_check["passed"].all()),
                "config_flags_clean": bool(config_check["passed"].all()),
                "phase13ag_reports_present": bool(inventory["present"].all())
                if not inventory.empty
                else False,
                "target_variant_rows": len(target_variants),
                "feature_family_rows": len(feature_families),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
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
                "Phase 13AG passed",
                bool(summary.iloc[0]["phase13ag_passed"]),
                "phase13ag",
            ),
            _gate_row(
                "Config flags clean",
                bool(summary.iloc[0]["config_flags_clean"]),
                "runtime flags",
            ),
            _gate_row(
                "Target variants present",
                len(target_variants) >= 4,
                f"rows={len(target_variants)}",
            ),
            _gate_row(
                "Feature families present",
                len(feature_families) >= 5,
                f"rows={len(feature_families)}",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Target-feature redesign readiness and boundary audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AH",
                "diagnostic": "Target-feature redesign readiness audit",
                "verdict": "Completed — target-feature redesign readiness audit passed"
                if bool(gate_report["passed"].all())
                else "Failed target-feature redesign readiness audit",
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
        "phase13ag_result_check": phase13ag_check,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13ah_redesign_readiness_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AH target-feature redesign readiness reports.")
    return outputs


def _split_required_columns(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    return [str(item) for item in _as_list(value)]


def _label_target_variant(
    dataset: pd.DataFrame,
    row: pd.Series,
) -> tuple[pd.Series, bool, str]:
    rule_type = str(row.get("rule_type", ""))
    required_columns = _split_required_columns(row.get("required_columns", ""))
    missing = [col for col in required_columns if col not in dataset.columns]

    if missing:
        return (
            pd.Series(["unavailable"] * len(dataset), index=dataset.index),
            False,
            "; ".join(missing),
        )

    if rule_type == "existing_state_column":
        source_col = str(row.get("source_column", ""))
        if source_col not in dataset.columns:
            return (
                pd.Series(["unavailable"] * len(dataset), index=dataset.index),
                False,
                source_col,
            )
        return dataset[source_col].fillna("unavailable").astype(str), True, ""

    if rule_type == "return_63d_threshold":
        returns = pd.to_numeric(dataset["future_return_63d"], errors="coerce")
        fragile_max = float(row.get("fragile_return_max", -0.03))
        supportive_min = float(row.get("supportive_return_min", 0.05))

        labels = pd.Series(["neutral"] * len(dataset), index=dataset.index)
        labels.loc[returns <= fragile_max] = "fragile"
        labels.loc[returns >= supportive_min] = "supportive"
        labels.loc[returns.isna()] = "unavailable"
        return labels, True, ""

    if rule_type == "return_drawdown_63d_composite":
        returns = pd.to_numeric(dataset["future_return_63d"], errors="coerce")
        drawdowns = pd.to_numeric(
            dataset["future_window_max_drawdown_63d"],
            errors="coerce",
        )
        fragile_return_max = float(row.get("fragile_return_max", -0.04))
        fragile_drawdown_max = float(row.get("fragile_drawdown_max", -0.10))
        supportive_return_min = float(row.get("supportive_return_min", 0.05))
        supportive_drawdown_min = float(row.get("supportive_drawdown_min", -0.08))

        labels = pd.Series(["neutral"] * len(dataset), index=dataset.index)
        labels.loc[
            (returns <= fragile_return_max) | (drawdowns <= fragile_drawdown_max)
        ] = "fragile"
        labels.loc[
            (returns >= supportive_return_min)
            & (drawdowns >= supportive_drawdown_min)
        ] = "supportive"
        labels.loc[returns.isna() | drawdowns.isna()] = "unavailable"
        return labels, True, ""

    if rule_type == "drawdown_63d_threshold":
        returns = pd.to_numeric(dataset["future_return_63d"], errors="coerce")
        drawdowns = pd.to_numeric(
            dataset["future_window_max_drawdown_63d"],
            errors="coerce",
        )
        fragile_drawdown_max = float(row.get("fragile_drawdown_max", -0.10))
        supportive_return_min = float(row.get("supportive_return_min", 0.04))
        supportive_drawdown_min = float(row.get("supportive_drawdown_min", -0.05))

        labels = pd.Series(["neutral"] * len(dataset), index=dataset.index)
        labels.loc[drawdowns <= fragile_drawdown_max] = "fragile"
        labels.loc[
            (returns >= supportive_return_min)
            & (drawdowns >= supportive_drawdown_min)
        ] = "supportive"
        labels.loc[returns.isna() | drawdowns.isna()] = "unavailable"
        return labels, True, ""

    return (
        pd.Series(["unavailable"] * len(dataset), index=dataset.index),
        False,
        "rule_type_unavailable_or_registry_only",
    )


def _target_variant_feasibility(
    dataset: pd.DataFrame,
    target_registry: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    assignment = pd.DataFrame()

    if "decision_date" in dataset.columns:
        assignment["decision_date"] = dataset["decision_date"]
    if "split_label" in dataset.columns:
        assignment["split_label"] = dataset["split_label"]

    rows = []

    for _, row in target_registry.iterrows():
        variant_id = str(row["target_variant_id"])
        labels, feasible, missing = _label_target_variant(dataset, row)
        assignment[variant_id] = labels

        live = labels[~labels.astype(str).eq("unavailable")]
        live_classes = sorted(live.astype(str).unique())

        rows.append(
            {
                "target_variant_id": variant_id,
                "rule_type": row.get("rule_type", ""),
                "horizon_days": row.get("horizon_days", ""),
                "feasible": feasible,
                "missing_columns": missing,
                "live_rows": int(len(live)),
                "live_classes": "; ".join(live_classes),
                "has_supportive_neutral_fragile": set(live_classes).issuperset(
                    {"supportive", "neutral", "fragile"}
                ),
                "target_variant_selected": False,
                "model_training": False,
            }
        )

    return pd.DataFrame(rows), assignment


def _target_distribution(
    assignment: pd.DataFrame,
    feasible: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    variant_ids = feasible["target_variant_id"].astype(str).tolist()

    for variant_id in variant_ids:
        for split, group in assignment.groupby("split_label"):
            labels = group[variant_id].astype(str)
            split_rows = len(labels)

            for class_label, count in labels.value_counts(dropna=False).items():
                rows.append(
                    {
                        "target_variant_id": variant_id,
                        "split_label": split,
                        "class_label": class_label,
                        "rows": int(count),
                        "split_rows": int(split_rows),
                        "class_ratio": float(count / split_rows)
                        if split_rows
                        else 0.0,
                    }
                )

    return pd.DataFrame(rows)


def _policy_value(policy: pd.DataFrame, key: str, default: Any) -> Any:
    if policy.empty:
        return default

    rows = policy[policy["policy_key"].astype(str).eq(key)]

    if rows.empty:
        return default

    return rows.iloc[0]["policy_value"]


def _class_balance_report(
    distribution: pd.DataFrame,
    target_quality_policy: pd.DataFrame,
) -> pd.DataFrame:
    min_validation = float(
        _policy_value(target_quality_policy, "min_validation_fragile_ratio", 0.12)
    )
    max_validation = float(
        _policy_value(target_quality_policy, "max_validation_fragile_ratio", 0.35)
    )
    min_train = float(
        _policy_value(target_quality_policy, "min_train_fragile_ratio", 0.12)
    )
    max_train = float(
        _policy_value(target_quality_policy, "max_train_fragile_ratio", 0.35)
    )

    rows = []

    for variant_id, group in distribution.groupby("target_variant_id"):
        train_fragile = group[
            group["split_label"].astype(str).eq("train")
            & group["class_label"].astype(str).eq("fragile")
        ]
        validation_fragile = group[
            group["split_label"].astype(str).eq("validation")
            & group["class_label"].astype(str).eq("fragile")
        ]

        train_ratio = (
            float(train_fragile.iloc[0]["class_ratio"])
            if not train_fragile.empty
            else 0.0
        )
        validation_ratio = (
            float(validation_fragile.iloc[0]["class_ratio"])
            if not validation_fragile.empty
            else 0.0
        )

        rows.append(
            {
                "target_variant_id": variant_id,
                "train_fragile_ratio": train_ratio,
                "validation_fragile_ratio": validation_ratio,
                "train_balance_passed": min_train <= train_ratio <= max_train,
                "validation_balance_passed": min_validation
                <= validation_ratio
                <= max_validation,
                "target_variant_selected": False,
            }
        )

    return pd.DataFrame(rows)


def _target_outcome_profile(
    dataset: pd.DataFrame,
    assignment: pd.DataFrame,
    feasible: pd.DataFrame,
) -> pd.DataFrame:
    outcome_cols = [
        col
        for col in ["future_return_63d", "future_window_max_drawdown_63d"]
        if col in dataset.columns
    ]

    rows = []

    if not outcome_cols:
        return pd.DataFrame(
            [
                {
                    "target_variant_id": "unavailable",
                    "class_label": "unavailable",
                    "outcome_column": "missing",
                    "rows": 0,
                }
            ]
        )

    for variant_id in feasible["target_variant_id"].astype(str):
        labels = assignment[variant_id].astype(str)

        for class_label in ["supportive", "neutral", "fragile"]:
            mask = labels.eq(class_label)

            for outcome_col in outcome_cols:
                values = pd.to_numeric(dataset.loc[mask, outcome_col], errors="coerce")
                values = values.dropna()

                rows.append(
                    {
                        "target_variant_id": variant_id,
                        "class_label": class_label,
                        "outcome_column": outcome_col,
                        "rows": int(len(values)),
                        "mean": float(values.mean()) if len(values) else 0.0,
                        "median": float(values.median()) if len(values) else 0.0,
                        "min": float(values.min()) if len(values) else 0.0,
                        "max": float(values.max()) if len(values) else 0.0,
                    }
                )

    return pd.DataFrame(rows)


def _feature_family_availability(
    dataset: pd.DataFrame,
    feature_family_registry: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for _, row in feature_family_registry.iterrows():
        value_prefixes = _split_semicolon(row.get("value_prefixes", ""))
        state_prefixes = _split_semicolon(row.get("state_prefixes", ""))
        missingness_prefixes = _split_semicolon(row.get("missingness_prefixes", ""))

        value_cols = [
            col for col in dataset.columns if str(col).startswith(tuple(value_prefixes))
        ]
        state_cols = [
            col for col in dataset.columns if str(col).startswith(tuple(state_prefixes))
        ]
        missingness_cols = [
            col
            for col in dataset.columns
            if str(col).startswith(tuple(missingness_prefixes))
        ]

        available_cells = 0
        total_cells = 0

        for col in value_cols:
            values = pd.to_numeric(dataset[col], errors="coerce")
            available_cells += int(values.notna().sum())
            total_cells += int(len(values))

        rows.append(
            {
                "family_id": row.get("family_id", ""),
                "status": row.get("status", ""),
                "value_feature_columns": len(value_cols),
                "state_feature_columns": len(state_cols),
                "missingness_feature_columns": len(missingness_cols),
                "value_available_ratio": float(available_cells / total_cells)
                if total_cells
                else 0.0,
                "available_for_current_panel": len(value_cols) > 0,
            }
        )

    return pd.DataFrame(rows)


def _split_semicolon(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    return [str(item) for item in _as_list(value)]


def _feature_target_separation(
    dataset: pd.DataFrame,
    assignment: pd.DataFrame,
    feasible: pd.DataFrame,
    max_rows: int,
) -> pd.DataFrame:
    numeric_features = [
        col
        for col in dataset.columns
        if str(col).startswith("value__technical_")
        or str(col).startswith("value__macro_")
    ]

    rows = []

    for variant_id in feasible[
        feasible["feasible"].map(_bool_value)
    ]["target_variant_id"].astype(str):
        labels = assignment[variant_id].astype(str)

        for feature_col in numeric_features:
            values = pd.to_numeric(dataset[feature_col], errors="coerce")

            for class_label in ["supportive", "neutral", "fragile"]:
                class_values = values[labels.eq(class_label)].dropna()
                non_class_values = values[~labels.eq(class_label)].dropna()

                rows.append(
                    {
                        "target_variant_id": variant_id,
                        "feature_column": feature_col,
                        "class_label": class_label,
                        "class_rows": int(len(class_values)),
                        "class_mean": float(class_values.mean())
                        if len(class_values)
                        else 0.0,
                        "non_class_mean": float(non_class_values.mean())
                        if len(non_class_values)
                        else 0.0,
                        "class_minus_non_class_mean": float(
                            class_values.mean() - non_class_values.mean()
                        )
                        if len(class_values) and len(non_class_values)
                        else 0.0,
                        "descriptive_only": True,
                        "feature_importance": False,
                        "feature_selected": False,
                    }
                )

                if len(rows) >= max_rows:
                    return pd.DataFrame(rows)

    return pd.DataFrame(rows)


def _redesign_screen(
    feasible: pd.DataFrame,
    balance: pd.DataFrame,
    outcome_profile: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for _, row in feasible.iterrows():
        variant_id = str(row["target_variant_id"])
        balance_row = balance[balance["target_variant_id"].astype(str).eq(variant_id)]

        validation_balance_passed = (
            _bool_value(balance_row.iloc[0]["validation_balance_passed"])
            if not balance_row.empty
            else False
        )
        train_balance_passed = (
            _bool_value(balance_row.iloc[0]["train_balance_passed"])
            if not balance_row.empty
            else False
        )

        return_profile = outcome_profile[
            outcome_profile["target_variant_id"].astype(str).eq(variant_id)
            & outcome_profile["outcome_column"].astype(str).eq("future_return_63d")
        ]
        drawdown_profile = outcome_profile[
            outcome_profile["target_variant_id"].astype(str).eq(variant_id)
            & outcome_profile["outcome_column"].astype(str).eq(
                "future_window_max_drawdown_63d"
            )
        ]

        return_map = {
            str(item["class_label"]): float(item["mean"])
            for _, item in return_profile.iterrows()
        }
        drawdown_map = {
            str(item["class_label"]): float(item["mean"])
            for _, item in drawdown_profile.iterrows()
        }

        economic_return_ordering = (
            return_map.get("fragile", 0.0)
            < return_map.get("neutral", 0.0)
            < return_map.get("supportive", 0.0)
        )
        drawdown_ordering = drawdown_map.get("fragile", 0.0) < drawdown_map.get(
            "neutral", 0.0
        )

        feasible_flag = _bool_value(row["feasible"])
        economically_meaningful = economic_return_ordering and drawdown_ordering
        viable_for_future_interpretation = (
            feasible_flag
            and train_balance_passed
            and validation_balance_passed
            and economically_meaningful
        )

        rows.append(
            {
                "target_variant_id": variant_id,
                "feasible": feasible_flag,
                "train_balance_passed": train_balance_passed,
                "validation_balance_passed": validation_balance_passed,
                "economic_return_ordering_passed": economic_return_ordering,
                "fragile_drawdown_worse_than_neutral": drawdown_ordering,
                "viable_for_future_interpretation": viable_for_future_interpretation,
                "target_variant_selected": False,
                "model_training_permission": False,
                "holdout_permission": False,
                "signal_permission": False,
                "backtest_permission": False,
            }
        )

    return pd.DataFrame(rows)


def _ai_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    boundary = section.get("phase13aj_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": "phase13aj_boundary_result_audit_only",
            "passed": "result audit" in allowed,
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": "phase13aj_forbidden_blocks_model_holdout_signal",
            "passed": bool(
                "model training" in forbidden
                and "holdout prediction" in forbidden
                and "feature importance" in forbidden
                and "strategy backtest" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def save_phase13ai_target_feature_diagnostic_panel_execution(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13ai_target_feature_diagnostic_panel_execution")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    phase13ah_check = _phase_result_check(
        source_reports["phase13ah_conclusion"],
        source_reports["phase13ah_gate_report"],
        "Phase 13AH",
    )

    dataset = _read_csv_if_exists(source_reports["dataset"])
    target_registry = _read_csv_if_exists(source_reports["target_variant_registry"])
    target_quality_policy = _read_csv_if_exists(
        source_reports["target_quality_policy"]
    )
    feature_family_registry = _read_csv_if_exists(
        source_reports["feature_family_registry"]
    )

    feasibility, assignment = _target_variant_feasibility(dataset, target_registry)
    distribution = _target_distribution(assignment, feasibility)
    balance = _class_balance_report(distribution, target_quality_policy)
    outcome_profile = _target_outcome_profile(dataset, assignment, feasibility)
    feature_family_availability = _feature_family_availability(
        dataset,
        feature_family_registry,
    )
    max_rows = int(section.get("panel_policy", {}).get("max_feature_target_separation_rows", 10000))
    separation = _feature_target_separation(
        dataset,
        assignment,
        feasibility,
        max_rows,
    )
    redesign_screen = _redesign_screen(feasibility, balance, outcome_profile)
    boundary = _ai_boundary_check(section)
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "phase13ah_passed": bool(phase13ah_check["passed"].all()),
                "dataset_rows": len(dataset),
                "target_variant_rows": len(target_registry),
                "feasible_target_variants": int(
                    feasibility["feasible"].map(_bool_value).sum()
                )
                if not feasibility.empty
                else 0,
                "target_assignment_rows": len(assignment),
                "target_distribution_rows": len(distribution),
                "class_balance_rows": len(balance),
                "target_outcome_profile_rows": len(outcome_profile),
                "feature_family_availability_rows": len(feature_family_availability),
                "feature_target_separation_rows": len(separation),
                "redesign_screen_rows": len(redesign_screen),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
                "feature_importance": False,
                "target_variant_selection": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AH passed",
                bool(summary.iloc[0]["phase13ah_passed"]),
                "phase13ah",
            ),
            _gate_row(
                "Dataset loaded",
                len(dataset) > 0,
                f"rows={len(dataset)}",
            ),
            _gate_row(
                "Target variant feasibility report exists",
                len(feasibility) > 0,
                f"rows={len(feasibility)}",
            ),
            _gate_row(
                "Target assignment panel exists",
                len(assignment) > 0,
                f"rows={len(assignment)}",
            ),
            _gate_row(
                "Target distribution report exists",
                len(distribution) > 0,
                f"rows={len(distribution)}",
            ),
            _gate_row(
                "Class balance report exists",
                len(balance) > 0,
                f"rows={len(balance)}",
            ),
            _gate_row(
                "Target outcome profile exists",
                len(outcome_profile) > 0,
                f"rows={len(outcome_profile)}",
            ),
            _gate_row(
                "Feature family availability report exists",
                len(feature_family_availability) > 0,
                f"rows={len(feature_family_availability)}",
            ),
            _gate_row(
                "Feature-target separation report exists",
                len(separation) > 0,
                f"rows={len(separation)}",
            ),
            _gate_row(
                "Redesign screen report exists",
                len(redesign_screen) > 0,
                f"rows={len(redesign_screen)}",
            ),
            _gate_row(
                "Boundary passed",
                bool(boundary["passed"].all()),
                "phase13aj",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role")
                == "Target-feature diagnostic panel execution only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AI",
                "diagnostic": "Target-feature diagnostic panel execution",
                "verdict": "Completed — target-feature diagnostic panel execution passed"
                if bool(gate_report["passed"].all())
                else "Failed target-feature diagnostic panel execution",
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase13ah_result_check": phase13ah_check,
        "target_variant_feasibility_report": feasibility,
        "target_assignment_panel": assignment,
        "target_distribution_report": distribution,
        "class_balance_report": balance,
        "target_outcome_profile_report": outcome_profile,
        "feature_family_availability_report": feature_family_availability,
        "feature_target_separation_report": separation,
        "redesign_screen_report": redesign_screen,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13ai_redesign_panel_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AI target-feature diagnostic panel reports.")
    return outputs


def save_phase13aj_target_feature_diagnostic_result_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13aj_target_feature_diagnostic_result_audit")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = section.get("phase13ai_reports", {})
    inventory = _source_report_check(reports)
    phase13ai_check = _phase_result_check(
        reports["conclusion"],
        reports["gate_report"],
        "Phase 13AI",
    )

    feasibility = _read_csv_if_exists(reports["target_variant_feasibility_report"])
    balance = _read_csv_if_exists(reports["class_balance_report"])
    outcome = _read_csv_if_exists(reports["target_outcome_profile_report"])
    screen = _read_csv_if_exists(reports["redesign_screen_report"])

    forbidden_rows = []
    for path in section.get("forbidden_output_paths", []):
        report_path = Path(str(path))
        forbidden_rows.append(
            {
                "path": str(report_path),
                "present": report_path.exists(),
                "passed": not report_path.exists(),
            }
        )
    forbidden = pd.DataFrame(forbidden_rows)
    forbidden["result"] = forbidden["passed"].map(
        {True: "Passed", False: "Failed"}
    )

    feasible_target_exists = (
        not feasibility.empty and feasibility["feasible"].map(_bool_value).any()
    )
    viable_variant_exists = (
        not screen.empty
        and screen["viable_for_future_interpretation"].map(_bool_value).any()
    )
    boundary = _next_boundary_check(section)
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "phase13ai_passed": bool(phase13ai_check["passed"].all()),
                "result_reports_present": bool(inventory["present"].all())
                if not inventory.empty
                else False,
                "feasible_target_exists": feasible_target_exists,
                "viable_variant_exists": viable_variant_exists,
                "class_balance_report_rows": len(balance),
                "outcome_profile_rows": len(outcome),
                "forbidden_outputs_absent": bool(forbidden["passed"].all())
                if not forbidden.empty
                else True,
                "next_boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
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
                "Phase 13AI passed",
                bool(summary.iloc[0]["phase13ai_passed"]),
                "phase13ai",
            ),
            _gate_row(
                "Result reports present",
                bool(summary.iloc[0]["result_reports_present"]),
                "inventory",
            ),
            _gate_row(
                "Feasible target variant exists",
                feasible_target_exists,
                "feasibility",
            ),
            _gate_row(
                "Class balance report present",
                len(balance) > 0,
                f"rows={len(balance)}",
            ),
            _gate_row(
                "Economic ordering report present",
                len(outcome) > 0,
                f"rows={len(outcome)}",
            ),
            _gate_row(
                "Forbidden outputs absent",
                bool(summary.iloc[0]["forbidden_outputs_absent"]),
                "forbidden outputs",
            ),
            _gate_row(
                "Next boundary is interpretation-only",
                bool(boundary["passed"].all()),
                "phase13ak",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Target-feature diagnostic result audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AJ",
                "diagnostic": "Target-feature diagnostic result audit",
                "verdict": "Completed — target-feature diagnostic result audit passed"
                if bool(gate_report["passed"].all())
                else "Failed target-feature diagnostic result audit",
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "viable_variant_exists": viable_variant_exists,
            }
        ]
    )

    outputs = {
        "report_inventory_check": inventory,
        "phase13ai_result_check": phase13ai_check,
        "forbidden_output_check": forbidden,
        "next_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13aj_redesign_audit_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AJ target-feature diagnostic result audit reports.")
    return outputs


def _next_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    boundary = section.get("next_phase_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": "next_boundary_is_interpretation_only",
            "passed": "interpretation" in allowed and "decision" in allowed,
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": "next_boundary_blocks_model_holdout_signal",
            "passed": bool(
                "model training" in forbidden
                and "holdout prediction" in forbidden
                and "feature importance" in forbidden
                and "strategy backtest" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out