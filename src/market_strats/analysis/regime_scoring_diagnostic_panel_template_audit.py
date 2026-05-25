from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE11E_CONFIG: dict[str, Any] = {
    "enabled": False,
    "implementation_role": (
        "Regime scoring diagnostic panel template implementation audit only"
    ),
    "phase_branch": "Phase 11 architecture review",
    "source_phase": "Phase 11D",
    "proposed_next_phase": "Phase 11F",
    "source_design_reports": {},
    "expected_template_reports": [],
    "allow_score_calculation": False,
    "allow_numeric_score_weights": False,
    "allow_empirical_return_weights": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "template_policy": {
        "component_availability_status_source": (
            "Phase 11D component availability spec"
        ),
        "direction_source": "Phase 11D conceptual direction spec",
        "missingness_default_action": "flag_unavailable_or_blocked",
        "weighting_component_scope": "all_components",
        "boundary_expected_allowed": False,
        "create_schema_compliant_rows": True,
        "create_empty_return_columns": False,
        "create_score_columns": False,
        "create_signal_columns": False,
    },
    "phase11f_boundary": {
        "allowed_next_step": "Regime scoring diagnostic panel content audit only",
        "forbidden_next_step": (
            "score calculation, signal creation, strategy backtest, model training, "
            "new data ingestion, or candidate promotion"
        ),
        "phase11f_may_populate_templates_from_existing_phase_reports": True,
        "phase11f_may_calculate_scores": False,
        "phase11f_may_assign_weights": False,
        "phase11f_may_create_signal": False,
        "phase11f_may_test_strategy": False,
        "phase11f_may_train_model": False,
        "phase11f_may_ingest_new_data": False,
        "phase11f_may_promote_candidate": False,
    },
    "gates": {
        "require_source_design_reports_present": True,
        "require_template_reports_generated": True,
        "min_template_reports": 6,
        "require_schema_compliance": True,
        "require_component_availability_rows": True,
        "min_component_availability_rows": 5,
        "require_direction_rows": True,
        "min_direction_rows": 9,
        "require_missingness_rows": True,
        "min_missingness_rows": 5,
        "require_weighting_policy_rows": True,
        "min_weighting_policy_rows": 5,
        "require_blocked_family_rows": True,
        "min_blocked_family_rows": 2,
        "require_boundary_rows": True,
        "min_boundary_rows": 9,
        "require_non_signal_templates": True,
        "require_no_returns_usage": True,
        "require_weighting_non_empirical": True,
        "require_blocked_families_clean": True,
        "require_phase11f_boundary_content_audit_only": True,
        "require_no_score_calculation": True,
        "require_no_numeric_score_weights": True,
        "require_no_empirical_return_weights": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "required_implementation_role": (
            "Regime scoring diagnostic panel template implementation audit only"
        ),
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


def _get_phase_config(config: dict[str, Any]) -> dict[str, Any]:
    user_config = config.get(
        "phase11e_regime_scoring_diagnostic_panel_template_audit",
        {},
    )
    return _deep_merge_dict(DEFAULT_PHASE11E_CONFIG, user_config)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _split_required_columns(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()

    if not text:
        return []

    return [item.strip() for item in text.split(";") if item.strip()]


def _split_allowed_directions(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()

    if not text:
        return []

    return [item.strip() for item in text.split(";") if item.strip()]


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


def build_phase11e_source_design_inventory(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, report_path in phase_config.get("source_design_reports", {}).items():
        path = Path(str(report_path))
        frame = _read_csv_if_exists(path)

        rows.append(
            {
                "report_key": str(report_key),
                "report_path": str(path),
                "present": path.exists(),
                "rows": int(len(frame)),
                "columns": "; ".join(frame.columns.astype(str).tolist())
                if not frame.empty
                else "",
            }
        )

    return pd.DataFrame(rows)


def _required_columns_by_report(required_columns_spec: pd.DataFrame) -> dict[str, list[str]]:
    if required_columns_spec.empty:
        return {}

    grouped: dict[str, list[str]] = {}

    for report_name, group in required_columns_spec.groupby("report_name"):
        grouped[str(report_name)] = [
            str(item)
            for item in group["required_column"].dropna().astype(str).tolist()
        ]

    return grouped


def _frame_with_columns(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)

    for column in columns:
        if column not in frame.columns:
            frame[column] = ""

    return frame[columns]


def build_phase11e_component_availability_template(
    *,
    component_availability_spec: pd.DataFrame,
    required_columns: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, item in component_availability_spec.iterrows():
        expected_status = str(item.get("expected_status", ""))
        is_blocked = expected_status.lower() == "blocked"

        rows.append(
            {
                "component_id": str(item.get("component_id", "")),
                "family": str(item.get("family", "")),
                "expected_status": expected_status,
                "availability_status": expected_status,
                "source_dependency": str(item.get("source_dependency", "")),
                "unavailable_reason": "",
                "blocked_reason": "blocked_pending_source_leakage_audit"
                if is_blocked
                else "",
                "future_unblock_requirement": str(
                    item.get("future_unblock_requirement", "")
                ),
            }
        )

    return _frame_with_columns(rows, required_columns)


def build_phase11e_component_direction_template(
    *,
    conceptual_direction_spec: pd.DataFrame,
    required_columns: list[str],
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    direction_source = str(
        phase_config.get("template_policy", {}).get(
            "direction_source",
            "Phase 11D conceptual direction spec",
        )
    )

    for _, item in conceptual_direction_spec.iterrows():
        component_id = str(item.get("component_id", ""))
        family = str(item.get("family", ""))
        trading_allowed = _bool_value(item.get("trading_allowed", False))
        signal_allowed = _bool_value(item.get("signal_allowed", False))

        for direction in _split_allowed_directions(item.get("allowed_directions", "")):
            rows.append(
                {
                    "component_id": component_id,
                    "family": family,
                    "direction_id": f"{component_id}_{direction}",
                    "conceptual_direction": direction,
                    "direction_source": direction_source,
                    "trading_allowed": trading_allowed,
                    "signal_allowed": signal_allowed,
                    "notes": "template_only_no_score_no_signal",
                }
            )

    return _frame_with_columns(rows, required_columns)


def build_phase11e_missingness_template(
    *,
    component_availability_spec: pd.DataFrame,
    required_columns: list[str],
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    default_action = str(
        phase_config.get("template_policy", {}).get(
            "missingness_default_action",
            "flag_unavailable_or_blocked",
        )
    )

    for _, item in component_availability_spec.iterrows():
        expected_status = str(item.get("expected_status", ""))
        is_blocked = expected_status.lower() == "blocked"

        rows.append(
            {
                "component_id": str(item.get("component_id", "")),
                "family": str(item.get("family", "")),
                "evidence_status": expected_status,
                "missingness_reason": "blocked_pending_source_leakage_audit"
                if is_blocked
                else "",
                "handling_policy": "explicit_flag_no_return_inference",
                "returns_inference_allowed": False,
                "silent_fill_allowed": False,
                "default_action": default_action,
            }
        )

    return _frame_with_columns(rows, required_columns)


def build_phase11e_weighting_policy_template(
    *,
    weighting_policy_spec: pd.DataFrame,
    required_columns: list[str],
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    component_scope = str(
        phase_config.get("template_policy", {}).get(
            "weighting_component_scope",
            "all_components",
        )
    )

    for _, item in weighting_policy_spec.iterrows():
        rows.append(
            {
                "policy_id": str(item.get("policy_id", "")),
                "component_id": component_scope,
                "weighting_policy": str(item.get("policy", "")),
                "numeric_weight_allowed": _bool_value(
                    item.get("numeric_weight_allowed", False)
                ),
                "empirical_return_weight_allowed": _bool_value(
                    item.get("empirical_return_weight_allowed", False)
                ),
                "cutoff_search_allowed": False,
                "pre_registration_required": True,
            }
        )

    return _frame_with_columns(rows, required_columns)


def build_phase11e_blocked_family_template(
    *,
    blocked_family_spec: pd.DataFrame,
    required_columns: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, item in blocked_family_spec.iterrows():
        rows.append(
            {
                "family": str(item.get("family", "")),
                "blocked_status": str(item.get("blocked_status", "")),
                "blocked_reason": str(item.get("blocked_reason", "")),
                "unblock_requires": str(item.get("unblock_requires", "")),
                "current_use_allowed": _bool_value(
                    item.get("current_use_allowed", False)
                ),
                "score_component_allowed": _bool_value(
                    item.get("score_component_allowed", False)
                ),
            }
        )

    return _frame_with_columns(rows, required_columns)


def build_phase11e_boundary_template(
    *,
    phase_config: dict[str, Any],
    required_columns: list[str],
) -> pd.DataFrame:
    checks = [
        ("score_calculation", "allow_score_calculation"),
        ("numeric_score_weights", "allow_numeric_score_weights"),
        ("empirical_return_weights", "allow_empirical_return_weights"),
        ("signal_creation", "allow_signal_creation"),
        ("allocation_rule_creation", "allow_allocation_rule_creation"),
        ("strategy_backtest", "allow_strategy_backtest"),
        ("model_training", "allow_model_training"),
        ("new_data_ingestion", "allow_new_data_ingestion"),
        ("candidate_promotion", "allow_candidate_promotion"),
    ]
    rows: list[dict[str, Any]] = []

    for boundary_item, key in checks:
        actual = _bool_value(phase_config.get(key, True))
        expected = False

        rows.append(
            {
                "boundary_item": boundary_item,
                "allowed": actual,
                "expected_allowed": expected,
                "passed": actual is expected,
                "detail": f"{key}={actual}",
            }
        )

    return _frame_with_columns(rows, required_columns)


def build_phase11e_template_reports(
    *,
    phase_config: dict[str, Any],
    source_tables: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    required = _required_columns_by_report(
        source_tables["required_columns_spec"],
    )

    return {
        "component_availability_report": build_phase11e_component_availability_template(
            component_availability_spec=source_tables["component_availability_spec"],
            required_columns=required.get("component_availability_report", []),
        ),
        "component_direction_report": build_phase11e_component_direction_template(
            conceptual_direction_spec=source_tables["conceptual_direction_spec"],
            required_columns=required.get("component_direction_report", []),
            phase_config=phase_config,
        ),
        "missingness_report": build_phase11e_missingness_template(
            component_availability_spec=source_tables["component_availability_spec"],
            required_columns=required.get("missingness_report", []),
            phase_config=phase_config,
        ),
        "weighting_policy_report": build_phase11e_weighting_policy_template(
            weighting_policy_spec=source_tables["weighting_policy_spec"],
            required_columns=required.get("weighting_policy_report", []),
            phase_config=phase_config,
        ),
        "blocked_family_report": build_phase11e_blocked_family_template(
            blocked_family_spec=source_tables["blocked_family_spec"],
            required_columns=required.get("blocked_family_report", []),
        ),
        "boundary_report": build_phase11e_boundary_template(
            phase_config=phase_config,
            required_columns=required.get("boundary_report", []),
        ),
    }


def build_phase11e_schema_compliance_report(
    *,
    panel_layout_spec: pd.DataFrame,
    required_columns_spec: pd.DataFrame,
    template_reports: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    required = _required_columns_by_report(required_columns_spec)
    rows: list[dict[str, Any]] = []

    for _, panel in panel_layout_spec.iterrows():
        report_name = str(panel.get("report_name", ""))
        frame = template_reports.get(report_name, pd.DataFrame())
        expected_columns = required.get(report_name, [])
        missing_columns = [
            column for column in expected_columns if column not in frame.columns
        ]

        rows.append(
            {
                "report_name": report_name,
                "panel_id": str(panel.get("panel_id", "")),
                "expected_column_count": len(expected_columns),
                "actual_column_count": int(len(frame.columns)),
                "missing_column_count": len(missing_columns),
                "missing_columns": "; ".join(missing_columns),
                "row_count": int(len(frame)),
                "schema_passed": len(missing_columns) == 0
                and len(frame.columns) >= len(expected_columns),
            }
        )

    frame = pd.DataFrame(rows)
    frame["result"] = frame["schema_passed"].map(
        {True: "Passed", False: "Failed"}
    )

    return frame


def build_phase11e_template_inventory_report(
    *,
    template_reports: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows = [
        {
            "report_name": report_name,
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "column_names": "; ".join(frame.columns.astype(str).tolist()),
            "generated": True,
        }
        for report_name, frame in template_reports.items()
    ]

    return pd.DataFrame(rows)


def build_phase11e_phase11f_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase11f_boundary", {})

    rows = [
        {
            "boundary_item": "phase11f_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "content audit" in str(
                boundary.get("allowed_next_step", "")
            ).lower(),
        },
        {
            "boundary_item": "phase11f_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "score calculation"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase11f_may_populate_templates_from_existing_phase_reports",
            "value": _bool_value(
                boundary.get(
                    "phase11f_may_populate_templates_from_existing_phase_reports",
                    False,
                )
            ),
            "passed": _bool_value(
                boundary.get(
                    "phase11f_may_populate_templates_from_existing_phase_reports",
                    False,
                )
            ),
        },
        {
            "boundary_item": "phase11f_may_calculate_scores",
            "value": _bool_value(boundary.get("phase11f_may_calculate_scores", True)),
            "passed": not _bool_value(
                boundary.get("phase11f_may_calculate_scores", True)
            ),
        },
        {
            "boundary_item": "phase11f_may_assign_weights",
            "value": _bool_value(boundary.get("phase11f_may_assign_weights", True)),
            "passed": not _bool_value(
                boundary.get("phase11f_may_assign_weights", True)
            ),
        },
        {
            "boundary_item": "phase11f_may_create_signal",
            "value": _bool_value(boundary.get("phase11f_may_create_signal", True)),
            "passed": not _bool_value(
                boundary.get("phase11f_may_create_signal", True)
            ),
        },
        {
            "boundary_item": "phase11f_may_test_strategy",
            "value": _bool_value(boundary.get("phase11f_may_test_strategy", True)),
            "passed": not _bool_value(
                boundary.get("phase11f_may_test_strategy", True)
            ),
        },
        {
            "boundary_item": "phase11f_may_train_model",
            "value": _bool_value(boundary.get("phase11f_may_train_model", True)),
            "passed": not _bool_value(
                boundary.get("phase11f_may_train_model", True)
            ),
        },
        {
            "boundary_item": "phase11f_may_ingest_new_data",
            "value": _bool_value(boundary.get("phase11f_may_ingest_new_data", True)),
            "passed": not _bool_value(
                boundary.get("phase11f_may_ingest_new_data", True)
            ),
        },
        {
            "boundary_item": "phase11f_may_promote_candidate",
            "value": _bool_value(boundary.get("phase11f_may_promote_candidate", True)),
            "passed": not _bool_value(
                boundary.get("phase11f_may_promote_candidate", True)
            ),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def _all_false(frame: pd.DataFrame, columns: list[str]) -> bool:
    if frame.empty:
        return False

    for column in columns:
        if column not in frame.columns:
            return False
        if not frame[column].map(_bool_value).eq(False).all():
            return False

    return True


def build_phase11e_summary(
    *,
    phase_config: dict[str, Any],
    source_design_inventory: pd.DataFrame,
    template_inventory: pd.DataFrame,
    schema_compliance: pd.DataFrame,
    template_reports: dict[str, pd.DataFrame],
    phase11f_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    component_availability = template_reports["component_availability_report"]
    direction = template_reports["component_direction_report"]
    missingness = template_reports["missingness_report"]
    weighting = template_reports["weighting_policy_report"]
    blocked = template_reports["blocked_family_report"]
    boundary = template_reports["boundary_report"]

    source_reports_present = (
        bool(source_design_inventory["present"].all())
        if not source_design_inventory.empty
        else False
    )
    schema_compliance_passed = (
        bool(schema_compliance["schema_passed"].all())
        if not schema_compliance.empty
        else False
    )
    boundary_report_passed = (
        bool(boundary["passed"].map(_bool_value).all())
        if not boundary.empty and "passed" in boundary.columns
        else False
    )

    return pd.DataFrame(
        [
            {
                "implementation_role": str(
                    phase_config.get("implementation_role", "")
                ),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_design_reports_present": source_reports_present,
                "template_report_count": int(len(template_reports)),
                "template_inventory_rows": int(len(template_inventory)),
                "schema_compliance_passed": schema_compliance_passed,
                "component_availability_rows": int(len(component_availability)),
                "direction_rows": int(len(direction)),
                "missingness_rows": int(len(missingness)),
                "weighting_policy_rows": int(len(weighting)),
                "blocked_family_rows": int(len(blocked)),
                "boundary_rows": int(len(boundary)),
                "direction_non_signal": _all_false(
                    direction,
                    ["trading_allowed", "signal_allowed"],
                ),
                "missingness_no_return_inference": _all_false(
                    missingness,
                    ["returns_inference_allowed", "silent_fill_allowed"],
                ),
                "weighting_non_empirical": _all_false(
                    weighting,
                    ["numeric_weight_allowed", "empirical_return_weight_allowed"],
                ),
                "blocked_families_clean": _all_false(
                    blocked,
                    ["current_use_allowed", "score_component_allowed"],
                ),
                "boundary_report_passed": boundary_report_passed,
                "phase11f_boundary_passed": bool(
                    phase11f_boundary_check["passed"].all()
                )
                if not phase11f_boundary_check.empty
                else False,
                "strategy_promotion": False,
                "candidate_promotion": False,
            }
        ]
    )


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase11e_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 11E summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_implementation_role",
            "Regime scoring diagnostic panel template implementation audit only",
        )
    )

    rows = [
        _gate_row(
            "Source design reports are present",
            (not gates.get("require_source_design_reports_present", True))
            or bool(row["source_design_reports_present"]),
            (
                "source_design_reports_present="
                f"{bool(row['source_design_reports_present'])}"
            ),
        ),
        _gate_row(
            "Template reports are generated",
            (not gates.get("require_template_reports_generated", True))
            or int(row["template_report_count"])
            >= int(gates.get("min_template_reports", 6)),
            f"template_report_count={int(row['template_report_count'])}",
        ),
        _gate_row(
            "Template schemas are compliant",
            (not gates.get("require_schema_compliance", True))
            or bool(row["schema_compliance_passed"]),
            f"schema_compliance_passed={bool(row['schema_compliance_passed'])}",
        ),
        _gate_row(
            "Component availability template rows exist",
            (not gates.get("require_component_availability_rows", True))
            or int(row["component_availability_rows"])
            >= int(gates.get("min_component_availability_rows", 5)),
            (
                "component_availability_rows="
                f"{int(row['component_availability_rows'])}"
            ),
        ),
        _gate_row(
            "Direction template rows exist",
            (not gates.get("require_direction_rows", True))
            or int(row["direction_rows"]) >= int(gates.get("min_direction_rows", 9)),
            f"direction_rows={int(row['direction_rows'])}",
        ),
        _gate_row(
            "Missingness template rows exist",
            (not gates.get("require_missingness_rows", True))
            or int(row["missingness_rows"])
            >= int(gates.get("min_missingness_rows", 5)),
            f"missingness_rows={int(row['missingness_rows'])}",
        ),
        _gate_row(
            "Weighting-policy template rows exist",
            (not gates.get("require_weighting_policy_rows", True))
            or int(row["weighting_policy_rows"])
            >= int(gates.get("min_weighting_policy_rows", 5)),
            f"weighting_policy_rows={int(row['weighting_policy_rows'])}",
        ),
        _gate_row(
            "Blocked-family template rows exist",
            (not gates.get("require_blocked_family_rows", True))
            or int(row["blocked_family_rows"])
            >= int(gates.get("min_blocked_family_rows", 2)),
            f"blocked_family_rows={int(row['blocked_family_rows'])}",
        ),
        _gate_row(
            "Boundary template rows exist",
            (not gates.get("require_boundary_rows", True))
            or int(row["boundary_rows"]) >= int(gates.get("min_boundary_rows", 9)),
            f"boundary_rows={int(row['boundary_rows'])}",
        ),
        _gate_row(
            "Templates are non-signal",
            (not gates.get("require_non_signal_templates", True))
            or bool(row["direction_non_signal"]),
            f"direction_non_signal={bool(row['direction_non_signal'])}",
        ),
        _gate_row(
            "Templates do not use returns",
            (not gates.get("require_no_returns_usage", True))
            or bool(row["missingness_no_return_inference"]),
            (
                "missingness_no_return_inference="
                f"{bool(row['missingness_no_return_inference'])}"
            ),
        ),
        _gate_row(
            "Weighting templates are non-empirical",
            (not gates.get("require_weighting_non_empirical", True))
            or bool(row["weighting_non_empirical"]),
            f"weighting_non_empirical={bool(row['weighting_non_empirical'])}",
        ),
        _gate_row(
            "Blocked-family templates are clean",
            (not gates.get("require_blocked_families_clean", True))
            or bool(row["blocked_families_clean"]),
            f"blocked_families_clean={bool(row['blocked_families_clean'])}",
        ),
        _gate_row(
            "Boundary report passes",
            bool(row["boundary_report_passed"]),
            f"boundary_report_passed={bool(row['boundary_report_passed'])}",
        ),
        _gate_row(
            "Phase 11F boundary is content-audit only",
            (not gates.get("require_phase11f_boundary_content_audit_only", True))
            or bool(row["phase11f_boundary_passed"]),
            f"phase11f_boundary_passed={bool(row['phase11f_boundary_passed'])}",
        ),
        _gate_row(
            "No score calculation is allowed",
            (not gates.get("require_no_score_calculation", True))
            or not _bool_value(phase_config.get("allow_score_calculation", True)),
            f"allow_score_calculation={phase_config.get('allow_score_calculation')}",
        ),
        _gate_row(
            "No numeric score weights are allowed",
            (not gates.get("require_no_numeric_score_weights", True))
            or not _bool_value(phase_config.get("allow_numeric_score_weights", True)),
            (
                "allow_numeric_score_weights="
                f"{phase_config.get('allow_numeric_score_weights')}"
            ),
        ),
        _gate_row(
            "No empirical return weights are allowed",
            (not gates.get("require_no_empirical_return_weights", True))
            or not _bool_value(
                phase_config.get("allow_empirical_return_weights", True)
            ),
            (
                "allow_empirical_return_weights="
                f"{phase_config.get('allow_empirical_return_weights')}"
            ),
        ),
        _gate_row(
            "No signal creation is allowed",
            (not gates.get("require_no_signal_creation", True))
            or not _bool_value(phase_config.get("allow_signal_creation", True)),
            f"allow_signal_creation={phase_config.get('allow_signal_creation')}",
        ),
        _gate_row(
            "No allocation rule creation is allowed",
            (not gates.get("require_no_allocation_rule_creation", True))
            or not _bool_value(
                phase_config.get("allow_allocation_rule_creation", True)
            ),
            (
                "allow_allocation_rule_creation="
                f"{phase_config.get('allow_allocation_rule_creation')}"
            ),
        ),
        _gate_row(
            "No strategy backtest is allowed",
            (not gates.get("require_no_strategy_backtest", True))
            or not _bool_value(phase_config.get("allow_strategy_backtest", True)),
            f"allow_strategy_backtest={phase_config.get('allow_strategy_backtest')}",
        ),
        _gate_row(
            "No model training is allowed",
            (not gates.get("require_no_model_training", True))
            or not _bool_value(phase_config.get("allow_model_training", True)),
            f"allow_model_training={phase_config.get('allow_model_training')}",
        ),
        _gate_row(
            "No new data ingestion is allowed",
            (not gates.get("require_no_new_data_ingestion", True))
            or not _bool_value(phase_config.get("allow_new_data_ingestion", True)),
            f"allow_new_data_ingestion={phase_config.get('allow_new_data_ingestion')}",
        ),
        _gate_row(
            "No candidate promotion is allowed",
            (not gates.get("require_no_candidate_promotion", True))
            or not _bool_value(phase_config.get("allow_candidate_promotion", True)),
            f"allow_candidate_promotion={phase_config.get('allow_candidate_promotion')}",
        ),
        _gate_row(
            "Implementation role is correct",
            str(row["implementation_role"]) == required_role,
            f"implementation_role={row['implementation_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase11e_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    if all_passed:
        verdict = "Completed — diagnostic panel template audit passed"
        interpretation = (
            "Phase 11E created schema-compliant diagnostic panel templates and "
            "verified required columns, blocked-family rows, boundary rows, and "
            "non-signal/non-return constraints. It did not calculate scores, "
            "assign weights, create signals, ingest new data, run strategy tests, "
            "train models, or promote a candidate."
        )
    else:
        verdict = "Failed diagnostic panel template audit"
        interpretation = (
            "Phase 11E found a schema, template, blocked-family, boundary, or "
            "scope-control issue. Do not proceed to content audit."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 11E",
                "diagnostic": "Regime scoring diagnostic panel template audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase11e_markdown(
    *,
    source_design_inventory: pd.DataFrame,
    template_inventory: pd.DataFrame,
    schema_compliance: pd.DataFrame,
    phase11f_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 11E — Regime Scoring Diagnostic Panel Template Audit",
        "",
        "## Purpose",
        "",
        (
            "This phase creates schema-compliant diagnostic panel templates from "
            "the Phase 11D design. It does not calculate scores, assign weights, "
            "create signals, ingest new data, run strategy tests, train models, "
            "or promote a candidate."
        ),
        "",
        "## Source Design Inventory",
        "",
        source_design_inventory.to_markdown(index=False),
        "",
        "## Template Inventory",
        "",
        template_inventory.to_markdown(index=False),
        "",
        "## Schema Compliance",
        "",
        schema_compliance.to_markdown(index=False),
        "",
        "## Phase 11F Boundary Check",
        "",
        phase11f_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        "",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        conclusion.to_markdown(index=False),
        "",
        "## Limitations",
        "",
        "- This is a template implementation audit only.",
        "- It does not calculate regime scores.",
        "- It does not assign score weights.",
        "- It does not create signals or allocation rules.",
        "- It does not ingest new data.",
        "- It does not run a strategy backtest.",
        "- It does not train a model.",
        "- It does not promote a candidate.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase11e_regime_scoring_diagnostic_panel_template_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "source_design_inventory": empty,
            "template_inventory": empty,
            "schema_compliance": empty,
            "phase11f_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_design_inventory = build_phase11e_source_design_inventory(phase_config)
    source_report_paths = phase_config.get("source_design_reports", {})

    source_tables = {
        "panel_layout_spec": _read_csv_if_exists(
            source_report_paths.get("panel_layout_spec", "")
        ),
        "required_columns_spec": _read_csv_if_exists(
            source_report_paths.get("required_columns_spec", "")
        ),
        "component_availability_spec": _read_csv_if_exists(
            source_report_paths.get("component_availability_spec", "")
        ),
        "conceptual_direction_spec": _read_csv_if_exists(
            source_report_paths.get("conceptual_direction_spec", "")
        ),
        "weighting_policy_spec": _read_csv_if_exists(
            source_report_paths.get("weighting_policy_spec", "")
        ),
        "blocked_family_spec": _read_csv_if_exists(
            source_report_paths.get("blocked_family_spec", "")
        ),
    }

    template_reports = build_phase11e_template_reports(
        phase_config=phase_config,
        source_tables=source_tables,
    )
    schema_compliance = build_phase11e_schema_compliance_report(
        panel_layout_spec=source_tables["panel_layout_spec"],
        required_columns_spec=source_tables["required_columns_spec"],
        template_reports=template_reports,
    )
    template_inventory = build_phase11e_template_inventory_report(
        template_reports=template_reports,
    )
    phase11f_boundary_check = build_phase11e_phase11f_boundary_check(phase_config)
    summary = build_phase11e_summary(
        phase_config=phase_config,
        source_design_inventory=source_design_inventory,
        template_inventory=template_inventory,
        schema_compliance=schema_compliance,
        template_reports=template_reports,
        phase11f_boundary_check=phase11f_boundary_check,
    )
    gate_report = build_phase11e_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11e_conclusion(gate_report)

    template_reports["component_availability_report"].to_csv(
        reports_path / "phase11e_template_component_availability_report.csv",
        index=False,
    )
    template_reports["component_direction_report"].to_csv(
        reports_path / "phase11e_template_component_direction_report.csv",
        index=False,
    )
    template_reports["missingness_report"].to_csv(
        reports_path / "phase11e_template_missingness_report.csv",
        index=False,
    )
    template_reports["weighting_policy_report"].to_csv(
        reports_path / "phase11e_template_weighting_policy_report.csv",
        index=False,
    )
    template_reports["blocked_family_report"].to_csv(
        reports_path / "phase11e_template_blocked_family_report.csv",
        index=False,
    )
    template_reports["boundary_report"].to_csv(
        reports_path / "phase11e_template_boundary_report.csv",
        index=False,
    )

    source_design_inventory.to_csv(
        reports_path / "phase11e_template_source_design_inventory.csv",
        index=False,
    )
    template_inventory.to_csv(
        reports_path / "phase11e_template_inventory.csv",
        index=False,
    )
    schema_compliance.to_csv(
        reports_path / "phase11e_template_schema_compliance.csv",
        index=False,
    )
    phase11f_boundary_check.to_csv(
        reports_path / "phase11e_template_phase11f_boundary_check.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase11e_template_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase11e_template_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase11e_template_conclusion.csv",
        index=False,
    )

    write_phase11e_markdown(
        source_design_inventory=source_design_inventory,
        template_inventory=template_inventory,
        schema_compliance=schema_compliance,
        phase11f_boundary_check=phase11f_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase11e_regime_scoring_diagnostic_panel_template_audit.md",
    )

    print("Wrote Phase 11E regime scoring diagnostic panel template audit reports.")

    return {
        "source_design_inventory": source_design_inventory,
        "template_inventory": template_inventory,
        "schema_compliance": schema_compliance,
        "phase11f_boundary_check": phase11f_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }