from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE11F_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Regime scoring diagnostic panel content audit only",
    "phase_branch": "Phase 11 architecture review",
    "source_phase": "Phase 11E",
    "proposed_next_phase": "Phase 11G",
    "source_template_reports": {},
    "allow_score_calculation": False,
    "allow_numeric_score_weights": False,
    "allow_empirical_return_weights": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "expected_components": [],
    "expected_active_components": [],
    "expected_blocked_families": [],
    "expected_directions": ["supportive", "neutral", "fragile"],
    "expected_boundary_items": [],
    "content_rules": {
        "require_phase11e_passed": True,
        "require_all_expected_templates_present": True,
        "require_all_template_schemas_passed": True,
        "require_expected_components_present": True,
        "require_blocked_components_flagged": True,
        "require_active_components_not_blocked": True,
        "require_three_directions_per_active_component": True,
        "require_direction_rows_non_signal": True,
        "require_missingness_blocks_return_inference": True,
        "require_missingness_blocks_silent_fill": True,
        "require_weighting_blocks_numeric_weights": True,
        "require_weighting_blocks_empirical_return_weights": True,
        "require_blocked_families_clean": True,
        "require_boundary_items_all_false": True,
    },
    "phase11g_boundary": {
        "allowed_next_step": "Regime scoring diagnostic panel closeout audit only",
        "forbidden_next_step": (
            "score calculation, signal creation, strategy backtest, model training, "
            "new data ingestion, or candidate promotion"
        ),
        "phase11g_may_close_diagnostic_panel_branch": True,
        "phase11g_may_calculate_scores": False,
        "phase11g_may_assign_weights": False,
        "phase11g_may_create_signal": False,
        "phase11g_may_test_strategy": False,
        "phase11g_may_train_model": False,
        "phase11g_may_ingest_new_data": False,
        "phase11g_may_promote_candidate": False,
    },
    "gates": {
        "require_source_templates_present": True,
        "require_phase11e_passed": True,
        "require_schema_compliance_passed": True,
        "require_component_content_consistency": True,
        "require_direction_content_consistency": True,
        "require_missingness_content_consistency": True,
        "require_weighting_content_consistency": True,
        "require_blocked_family_content_consistency": True,
        "require_boundary_content_consistency": True,
        "require_phase11g_boundary_closeout_only": True,
        "require_no_score_calculation": True,
        "require_no_numeric_score_weights": True,
        "require_no_empirical_return_weights": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "required_audit_role": "Regime scoring diagnostic panel content audit only",
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
        "phase11f_regime_scoring_diagnostic_panel_content_audit",
        {},
    )
    return _deep_merge_dict(DEFAULT_PHASE11F_CONFIG, user_config)


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


def _load_template_tables(phase_config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    paths = phase_config.get("source_template_reports", {})

    return {
        key: _read_csv_if_exists(path)
        for key, path in paths.items()
    }


def build_phase11f_source_template_inventory(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, report_path in phase_config.get(
        "source_template_reports", {}
    ).items():
        path = Path(str(report_path))
        frame = _read_csv_if_exists(path)

        rows.append(
            {
                "report_key": str(report_key),
                "report_path": str(path),
                "present": path.exists(),
                "rows": int(len(frame)),
                "columns": int(len(frame.columns)),
                "column_names": "; ".join(frame.columns.astype(str).tolist())
                if not frame.empty
                else "",
            }
        )

    return pd.DataFrame(rows)


def build_phase11f_phase11e_result_check(
    *,
    phase11e_conclusion: pd.DataFrame,
    schema_compliance: pd.DataFrame,
) -> pd.DataFrame:
    conclusion_passed = False
    verdict = ""

    if not phase11e_conclusion.empty:
        verdict = str(phase11e_conclusion.iloc[0].get("verdict", ""))
        conclusion_passed = _bool_value(
            phase11e_conclusion.iloc[0].get("all_gates_passed", False)
        ) and "passed" in verdict.lower()

    schema_passed = (
        bool(schema_compliance["schema_passed"].map(_bool_value).all())
        if not schema_compliance.empty and "schema_passed" in schema_compliance.columns
        else False
    )

    rows = [
        {
            "check": "Phase 11E template audit passed",
            "passed": conclusion_passed,
            "detail": f"verdict={verdict}",
        },
        {
            "check": "Phase 11E schema compliance passed",
            "passed": schema_passed,
            "detail": f"schema_rows={len(schema_compliance)}",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11f_component_content_check(
    *,
    component_availability: pd.DataFrame,
    expected_components: list[str],
    expected_active_components: list[str],
    expected_blocked_families: list[str],
) -> pd.DataFrame:
    component_ids = (
        set(component_availability["component_id"].dropna().astype(str).tolist())
        if not component_availability.empty and "component_id" in component_availability
        else set()
    )

    missing_components = [
        component for component in expected_components if component not in component_ids
    ]

    blocked_rows = (
        component_availability[
            component_availability["family"].astype(str).isin(expected_blocked_families)
        ]
        if not component_availability.empty and "family" in component_availability
        else pd.DataFrame()
    )

    active_rows = (
        component_availability[
            component_availability["component_id"]
            .astype(str)
            .isin(expected_active_components)
        ]
        if not component_availability.empty and "component_id" in component_availability
        else pd.DataFrame()
    )

    blocked_components_flagged = (
        not blocked_rows.empty
        and blocked_rows["expected_status"].astype(str).str.lower().eq("blocked").all()
        and blocked_rows["availability_status"].astype(str).str.lower().eq("blocked").all()
    )

    active_components_not_blocked = (
        not active_rows.empty
        and not active_rows["expected_status"].astype(str).str.lower().eq("blocked").any()
        and not active_rows["availability_status"].astype(str).str.lower().eq("blocked").any()
    )

    rows = [
        {
            "check": "Expected components are present",
            "passed": len(missing_components) == 0,
            "detail": "missing_components=" + "; ".join(missing_components),
        },
        {
            "check": "Blocked components are flagged",
            "passed": blocked_components_flagged,
            "detail": f"blocked_rows={len(blocked_rows)}",
        },
        {
            "check": "Active components are not blocked",
            "passed": active_components_not_blocked,
            "detail": f"active_rows={len(active_rows)}",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11f_direction_content_check(
    *,
    component_direction: pd.DataFrame,
    expected_active_components: list[str],
    expected_directions: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for component_id in expected_active_components:
        component_rows = (
            component_direction[
                component_direction["component_id"].astype(str) == str(component_id)
            ]
            if not component_direction.empty and "component_id" in component_direction
            else pd.DataFrame()
        )
        actual_directions = (
            set(component_rows["conceptual_direction"].dropna().astype(str).tolist())
            if not component_rows.empty and "conceptual_direction" in component_rows
            else set()
        )
        missing_directions = [
            direction for direction in expected_directions if direction not in actual_directions
        ]
        rows.append(
            {
                "component_id": component_id,
                "expected_direction_count": len(expected_directions),
                "actual_direction_count": len(actual_directions),
                "missing_directions": "; ".join(missing_directions),
                "directions_complete": len(missing_directions) == 0,
            }
        )

    direction_rows_non_signal = (
        bool(
            component_direction["trading_allowed"].map(_bool_value).eq(False).all()
            and component_direction["signal_allowed"].map(_bool_value).eq(False).all()
        )
        if not component_direction.empty
        and {"trading_allowed", "signal_allowed"}.issubset(component_direction.columns)
        else False
    )

    frame = pd.DataFrame(rows)
    frame["direction_rows_non_signal"] = direction_rows_non_signal
    frame["passed"] = frame["directions_complete"] & direction_rows_non_signal
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11f_missingness_content_check(
    missingness: pd.DataFrame,
) -> pd.DataFrame:
    return_inference_blocked = (
        bool(missingness["returns_inference_allowed"].map(_bool_value).eq(False).all())
        if not missingness.empty and "returns_inference_allowed" in missingness
        else False
    )
    silent_fill_blocked = (
        bool(missingness["silent_fill_allowed"].map(_bool_value).eq(False).all())
        if not missingness.empty and "silent_fill_allowed" in missingness
        else False
    )

    rows = [
        {
            "check": "Missingness blocks return inference",
            "passed": return_inference_blocked,
            "detail": f"rows={len(missingness)}",
        },
        {
            "check": "Missingness blocks silent fill",
            "passed": silent_fill_blocked,
            "detail": f"rows={len(missingness)}",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11f_weighting_content_check(
    weighting: pd.DataFrame,
) -> pd.DataFrame:
    numeric_weights_blocked = (
        bool(weighting["numeric_weight_allowed"].map(_bool_value).eq(False).all())
        if not weighting.empty and "numeric_weight_allowed" in weighting
        else False
    )
    empirical_weights_blocked = (
        bool(
            weighting["empirical_return_weight_allowed"]
            .map(_bool_value)
            .eq(False)
            .all()
        )
        if not weighting.empty and "empirical_return_weight_allowed" in weighting
        else False
    )
    cutoff_search_blocked = (
        bool(weighting["cutoff_search_allowed"].map(_bool_value).eq(False).all())
        if not weighting.empty and "cutoff_search_allowed" in weighting
        else False
    )
    prereg_required = (
        bool(weighting["pre_registration_required"].map(_bool_value).eq(True).all())
        if not weighting.empty and "pre_registration_required" in weighting
        else False
    )

    rows = [
        {
            "check": "Numeric weights are blocked",
            "passed": numeric_weights_blocked,
            "detail": f"rows={len(weighting)}",
        },
        {
            "check": "Empirical return weights are blocked",
            "passed": empirical_weights_blocked,
            "detail": f"rows={len(weighting)}",
        },
        {
            "check": "Cutoff search is blocked",
            "passed": cutoff_search_blocked,
            "detail": f"rows={len(weighting)}",
        },
        {
            "check": "Pre-registration is required",
            "passed": prereg_required,
            "detail": f"rows={len(weighting)}",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11f_blocked_family_content_check(
    *,
    blocked_family: pd.DataFrame,
    expected_blocked_families: list[str],
) -> pd.DataFrame:
    actual_families = (
        set(blocked_family["family"].dropna().astype(str).tolist())
        if not blocked_family.empty and "family" in blocked_family
        else set()
    )
    missing_families = [
        family for family in expected_blocked_families if family not in actual_families
    ]
    current_use_blocked = (
        bool(blocked_family["current_use_allowed"].map(_bool_value).eq(False).all())
        if not blocked_family.empty and "current_use_allowed" in blocked_family
        else False
    )
    score_component_blocked = (
        bool(blocked_family["score_component_allowed"].map(_bool_value).eq(False).all())
        if not blocked_family.empty and "score_component_allowed" in blocked_family
        else False
    )

    rows = [
        {
            "check": "Expected blocked families are present",
            "passed": len(missing_families) == 0,
            "detail": "missing_families=" + "; ".join(missing_families),
        },
        {
            "check": "Blocked families are not usable currently",
            "passed": current_use_blocked,
            "detail": f"rows={len(blocked_family)}",
        },
        {
            "check": "Blocked families cannot be score components",
            "passed": score_component_blocked,
            "detail": f"rows={len(blocked_family)}",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11f_boundary_content_check(
    *,
    boundary: pd.DataFrame,
    expected_boundary_items: list[str],
) -> pd.DataFrame:
    actual_items = (
        set(boundary["boundary_item"].dropna().astype(str).tolist())
        if not boundary.empty and "boundary_item" in boundary
        else set()
    )
    missing_items = [
        item for item in expected_boundary_items if item not in actual_items
    ]

    allowed_false = (
        bool(boundary["allowed"].map(_bool_value).eq(False).all())
        if not boundary.empty and "allowed" in boundary
        else False
    )
    expected_allowed_false = (
        bool(boundary["expected_allowed"].map(_bool_value).eq(False).all())
        if not boundary.empty and "expected_allowed" in boundary
        else False
    )
    passed_true = (
        bool(boundary["passed"].map(_bool_value).eq(True).all())
        if not boundary.empty and "passed" in boundary
        else False
    )

    rows = [
        {
            "check": "Expected boundary items are present",
            "passed": len(missing_items) == 0,
            "detail": "missing_boundary_items=" + "; ".join(missing_items),
        },
        {
            "check": "All boundary allowed values are false",
            "passed": allowed_false,
            "detail": f"rows={len(boundary)}",
        },
        {
            "check": "All expected allowed values are false",
            "passed": expected_allowed_false,
            "detail": f"rows={len(boundary)}",
        },
        {
            "check": "All boundary rows passed",
            "passed": passed_true,
            "detail": f"rows={len(boundary)}",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11f_phase11g_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase11g_boundary", {})

    rows = [
        {
            "boundary_item": "phase11g_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "closeout audit" in str(
                boundary.get("allowed_next_step", "")
            ).lower(),
        },
        {
            "boundary_item": "phase11g_forbidden_next_step",
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
            "boundary_item": "phase11g_may_close_diagnostic_panel_branch",
            "value": _bool_value(
                boundary.get("phase11g_may_close_diagnostic_panel_branch", False)
            ),
            "passed": _bool_value(
                boundary.get("phase11g_may_close_diagnostic_panel_branch", False)
            ),
        },
        {
            "boundary_item": "phase11g_may_calculate_scores",
            "value": _bool_value(boundary.get("phase11g_may_calculate_scores", True)),
            "passed": not _bool_value(
                boundary.get("phase11g_may_calculate_scores", True)
            ),
        },
        {
            "boundary_item": "phase11g_may_assign_weights",
            "value": _bool_value(boundary.get("phase11g_may_assign_weights", True)),
            "passed": not _bool_value(
                boundary.get("phase11g_may_assign_weights", True)
            ),
        },
        {
            "boundary_item": "phase11g_may_create_signal",
            "value": _bool_value(boundary.get("phase11g_may_create_signal", True)),
            "passed": not _bool_value(
                boundary.get("phase11g_may_create_signal", True)
            ),
        },
        {
            "boundary_item": "phase11g_may_test_strategy",
            "value": _bool_value(boundary.get("phase11g_may_test_strategy", True)),
            "passed": not _bool_value(
                boundary.get("phase11g_may_test_strategy", True)
            ),
        },
        {
            "boundary_item": "phase11g_may_train_model",
            "value": _bool_value(boundary.get("phase11g_may_train_model", True)),
            "passed": not _bool_value(
                boundary.get("phase11g_may_train_model", True)
            ),
        },
        {
            "boundary_item": "phase11g_may_ingest_new_data",
            "value": _bool_value(boundary.get("phase11g_may_ingest_new_data", True)),
            "passed": not _bool_value(
                boundary.get("phase11g_may_ingest_new_data", True)
            ),
        },
        {
            "boundary_item": "phase11g_may_promote_candidate",
            "value": _bool_value(boundary.get("phase11g_may_promote_candidate", True)),
            "passed": not _bool_value(
                boundary.get("phase11g_may_promote_candidate", True)
            ),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11f_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No score calculation", "allow_score_calculation"),
        ("No numeric score weights", "allow_numeric_score_weights"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No model training", "allow_model_training"),
        ("No new data ingestion", "allow_new_data_ingestion"),
        ("No candidate promotion", "allow_candidate_promotion"),
    ]

    rows = [
        {
            "scope_item": label,
            "value": _bool_value(phase_config.get(key, True)),
            "passed": not _bool_value(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11f_summary(
    *,
    phase_config: dict[str, Any],
    source_template_inventory: pd.DataFrame,
    phase11e_result_check: pd.DataFrame,
    component_content_check: pd.DataFrame,
    direction_content_check: pd.DataFrame,
    missingness_content_check: pd.DataFrame,
    weighting_content_check: pd.DataFrame,
    blocked_family_content_check: pd.DataFrame,
    boundary_content_check: pd.DataFrame,
    phase11g_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_templates_present": bool(
                    source_template_inventory["present"].all()
                )
                if not source_template_inventory.empty
                else False,
                "source_template_count": int(len(source_template_inventory)),
                "phase11e_result_passed": bool(phase11e_result_check["passed"].all())
                if not phase11e_result_check.empty
                else False,
                "component_content_passed": bool(component_content_check["passed"].all())
                if not component_content_check.empty
                else False,
                "direction_content_passed": bool(direction_content_check["passed"].all())
                if not direction_content_check.empty
                else False,
                "missingness_content_passed": bool(
                    missingness_content_check["passed"].all()
                )
                if not missingness_content_check.empty
                else False,
                "weighting_content_passed": bool(weighting_content_check["passed"].all())
                if not weighting_content_check.empty
                else False,
                "blocked_family_content_passed": bool(
                    blocked_family_content_check["passed"].all()
                )
                if not blocked_family_content_check.empty
                else False,
                "boundary_content_passed": bool(boundary_content_check["passed"].all())
                if not boundary_content_check.empty
                else False,
                "phase11g_boundary_passed": bool(phase11g_boundary_check["passed"].all())
                if not phase11g_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
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


def build_phase11f_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 11F summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_audit_role",
            "Regime scoring diagnostic panel content audit only",
        )
    )

    rows = [
        _gate_row(
            "Source templates are present",
            (not gates.get("require_source_templates_present", True))
            or bool(row["source_templates_present"]),
            f"source_template_count={int(row['source_template_count'])}",
        ),
        _gate_row(
            "Phase 11E template audit remains passed",
            (not gates.get("require_phase11e_passed", True))
            or bool(row["phase11e_result_passed"]),
            f"phase11e_result_passed={bool(row['phase11e_result_passed'])}",
        ),
        _gate_row(
            "Schema compliance remains passed",
            (not gates.get("require_schema_compliance_passed", True))
            or bool(row["phase11e_result_passed"]),
            "Schema compliance is checked through Phase 11E result check.",
        ),
        _gate_row(
            "Component content is consistent",
            (not gates.get("require_component_content_consistency", True))
            or bool(row["component_content_passed"]),
            f"component_content_passed={bool(row['component_content_passed'])}",
        ),
        _gate_row(
            "Direction content is consistent",
            (not gates.get("require_direction_content_consistency", True))
            or bool(row["direction_content_passed"]),
            f"direction_content_passed={bool(row['direction_content_passed'])}",
        ),
        _gate_row(
            "Missingness content is consistent",
            (not gates.get("require_missingness_content_consistency", True))
            or bool(row["missingness_content_passed"]),
            f"missingness_content_passed={bool(row['missingness_content_passed'])}",
        ),
        _gate_row(
            "Weighting content is consistent",
            (not gates.get("require_weighting_content_consistency", True))
            or bool(row["weighting_content_passed"]),
            f"weighting_content_passed={bool(row['weighting_content_passed'])}",
        ),
        _gate_row(
            "Blocked-family content is consistent",
            (not gates.get("require_blocked_family_content_consistency", True))
            or bool(row["blocked_family_content_passed"]),
            (
                "blocked_family_content_passed="
                f"{bool(row['blocked_family_content_passed'])}"
            ),
        ),
        _gate_row(
            "Boundary content is consistent",
            (not gates.get("require_boundary_content_consistency", True))
            or bool(row["boundary_content_passed"]),
            f"boundary_content_passed={bool(row['boundary_content_passed'])}",
        ),
        _gate_row(
            "Phase 11G boundary is closeout-only",
            (not gates.get("require_phase11g_boundary_closeout_only", True))
            or bool(row["phase11g_boundary_passed"]),
            f"phase11g_boundary_passed={bool(row['phase11g_boundary_passed'])}",
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
            "Audit role is correct",
            str(row["audit_role"]) == required_role,
            f"audit_role={row['audit_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase11f_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    if all_passed:
        verdict = "Completed — diagnostic panel content audit passed"
        interpretation = (
            "Phase 11F audited diagnostic panel template content from existing "
            "documented phase reports and confirmed component, direction, missingness, "
            "weighting, blocked-family, and boundary consistency. It did not calculate "
            "scores, assign weights, create signals, ingest new data, run strategy "
            "tests, train models, or promote a candidate."
        )
    else:
        verdict = "Failed diagnostic panel content audit"
        interpretation = (
            "Phase 11F found a source-template, content-consistency, boundary, or "
            "scope-control issue. Do not proceed to closeout."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 11F",
                "diagnostic": "Regime scoring diagnostic panel content audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase11f_markdown(
    *,
    source_template_inventory: pd.DataFrame,
    phase11e_result_check: pd.DataFrame,
    component_content_check: pd.DataFrame,
    direction_content_check: pd.DataFrame,
    missingness_content_check: pd.DataFrame,
    weighting_content_check: pd.DataFrame,
    blocked_family_content_check: pd.DataFrame,
    boundary_content_check: pd.DataFrame,
    phase11g_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 11F — Regime Scoring Diagnostic Panel Content Audit",
        "",
        "## Purpose",
        "",
        (
            "This phase audits diagnostic panel template content from existing "
            "documented phase reports. It does not calculate scores, assign weights, "
            "create signals, ingest new data, run strategy tests, train models, or "
            "promote a candidate."
        ),
        "",
        "## Source Template Inventory",
        "",
        source_template_inventory.to_markdown(index=False),
        "",
        "## Phase 11E Result Check",
        "",
        phase11e_result_check.to_markdown(index=False),
        "",
        "## Component Content Check",
        "",
        component_content_check.to_markdown(index=False),
        "",
        "## Direction Content Check",
        "",
        direction_content_check.to_markdown(index=False),
        "",
        "## Missingness Content Check",
        "",
        missingness_content_check.to_markdown(index=False),
        "",
        "## Weighting Content Check",
        "",
        weighting_content_check.to_markdown(index=False),
        "",
        "## Blocked-Family Content Check",
        "",
        blocked_family_content_check.to_markdown(index=False),
        "",
        "## Boundary Content Check",
        "",
        boundary_content_check.to_markdown(index=False),
        "",
        "## Phase 11G Boundary Check",
        "",
        phase11g_boundary_check.to_markdown(index=False),
        "",
        "## Scope Boundary Check",
        "",
        scope_boundary_check.to_markdown(index=False),
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
        "- This is a content audit only.",
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


def save_phase11f_regime_scoring_diagnostic_panel_content_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "source_template_inventory": empty,
            "phase11e_result_check": empty,
            "component_content_check": empty,
            "direction_content_check": empty,
            "missingness_content_check": empty,
            "weighting_content_check": empty,
            "blocked_family_content_check": empty,
            "boundary_content_check": empty,
            "phase11g_boundary_check": empty,
            "scope_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    template_tables = _load_template_tables(phase_config)

    source_template_inventory = build_phase11f_source_template_inventory(phase_config)
    phase11e_result_check = build_phase11f_phase11e_result_check(
        phase11e_conclusion=template_tables.get("phase11e_conclusion", pd.DataFrame()),
        schema_compliance=template_tables.get("schema_compliance", pd.DataFrame()),
    )
    component_content_check = build_phase11f_component_content_check(
        component_availability=template_tables.get(
            "component_availability_report",
            pd.DataFrame(),
        ),
        expected_components=[
            str(item) for item in _as_list(phase_config.get("expected_components"))
        ],
        expected_active_components=[
            str(item)
            for item in _as_list(phase_config.get("expected_active_components"))
        ],
        expected_blocked_families=[
            str(item)
            for item in _as_list(phase_config.get("expected_blocked_families"))
        ],
    )
    direction_content_check = build_phase11f_direction_content_check(
        component_direction=template_tables.get(
            "component_direction_report",
            pd.DataFrame(),
        ),
        expected_active_components=[
            str(item)
            for item in _as_list(phase_config.get("expected_active_components"))
        ],
        expected_directions=[
            str(item) for item in _as_list(phase_config.get("expected_directions"))
        ],
    )
    missingness_content_check = build_phase11f_missingness_content_check(
        template_tables.get("missingness_report", pd.DataFrame())
    )
    weighting_content_check = build_phase11f_weighting_content_check(
        template_tables.get("weighting_policy_report", pd.DataFrame())
    )
    blocked_family_content_check = build_phase11f_blocked_family_content_check(
        blocked_family=template_tables.get("blocked_family_report", pd.DataFrame()),
        expected_blocked_families=[
            str(item)
            for item in _as_list(phase_config.get("expected_blocked_families"))
        ],
    )
    boundary_content_check = build_phase11f_boundary_content_check(
        boundary=template_tables.get("boundary_report", pd.DataFrame()),
        expected_boundary_items=[
            str(item)
            for item in _as_list(phase_config.get("expected_boundary_items"))
        ],
    )
    phase11g_boundary_check = build_phase11f_phase11g_boundary_check(phase_config)
    scope_boundary_check = build_phase11f_scope_boundary_check(phase_config)

    summary = build_phase11f_summary(
        phase_config=phase_config,
        source_template_inventory=source_template_inventory,
        phase11e_result_check=phase11e_result_check,
        component_content_check=component_content_check,
        direction_content_check=direction_content_check,
        missingness_content_check=missingness_content_check,
        weighting_content_check=weighting_content_check,
        blocked_family_content_check=blocked_family_content_check,
        boundary_content_check=boundary_content_check,
        phase11g_boundary_check=phase11g_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase11f_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11f_conclusion(gate_report)

    source_template_inventory.to_csv(
        reports_path / "phase11f_content_source_template_inventory.csv",
        index=False,
    )
    phase11e_result_check.to_csv(
        reports_path / "phase11f_content_phase11e_result_check.csv",
        index=False,
    )
    component_content_check.to_csv(
        reports_path / "phase11f_content_component_check.csv",
        index=False,
    )
    direction_content_check.to_csv(
        reports_path / "phase11f_content_direction_check.csv",
        index=False,
    )
    missingness_content_check.to_csv(
        reports_path / "phase11f_content_missingness_check.csv",
        index=False,
    )
    weighting_content_check.to_csv(
        reports_path / "phase11f_content_weighting_check.csv",
        index=False,
    )
    blocked_family_content_check.to_csv(
        reports_path / "phase11f_content_blocked_family_check.csv",
        index=False,
    )
    boundary_content_check.to_csv(
        reports_path / "phase11f_content_boundary_check.csv",
        index=False,
    )
    phase11g_boundary_check.to_csv(
        reports_path / "phase11f_content_phase11g_boundary_check.csv",
        index=False,
    )
    scope_boundary_check.to_csv(
        reports_path / "phase11f_content_scope_boundary_check.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase11f_content_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase11f_content_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase11f_content_conclusion.csv",
        index=False,
    )

    write_phase11f_markdown(
        source_template_inventory=source_template_inventory,
        phase11e_result_check=phase11e_result_check,
        component_content_check=component_content_check,
        direction_content_check=direction_content_check,
        missingness_content_check=missingness_content_check,
        weighting_content_check=weighting_content_check,
        blocked_family_content_check=blocked_family_content_check,
        boundary_content_check=boundary_content_check,
        phase11g_boundary_check=phase11g_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase11f_regime_scoring_diagnostic_panel_content_audit.md",
    )

    print("Wrote Phase 11F regime scoring diagnostic panel content audit reports.")

    return {
        "source_template_inventory": source_template_inventory,
        "phase11e_result_check": phase11e_result_check,
        "component_content_check": component_content_check,
        "direction_content_check": direction_content_check,
        "missingness_content_check": missingness_content_check,
        "weighting_content_check": weighting_content_check,
        "blocked_family_content_check": blocked_family_content_check,
        "boundary_content_check": boundary_content_check,
        "phase11g_boundary_check": phase11g_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }