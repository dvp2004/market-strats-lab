from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE11D_CONFIG: dict[str, Any] = {
    "enabled": False,
    "design_role": "Regime scoring diagnostic panel design only",
    "phase_branch": "Phase 11 architecture review",
    "source_phase": "Phase 11C",
    "proposed_next_phase": "Phase 11E",
    "source_rulebook": {},
    "allow_score_calculation": False,
    "allow_numeric_score_weights": False,
    "allow_empirical_return_weights": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "diagnostic_panel_sections": [],
    "component_availability_spec": [],
    "conceptual_direction_spec": [],
    "missingness_policy_spec": [],
    "weighting_policy_spec": [],
    "blocked_family_spec": [],
    "phase11e_boundary": {
        "allowed_next_step": "Regime scoring diagnostic panel implementation audit only",
        "forbidden_next_step": (
            "score calculation, signal creation, strategy backtest, model training, "
            "new data ingestion, or candidate promotion"
        ),
        "phase11e_may_build_empty_panel_templates": True,
        "phase11e_may_calculate_scores": False,
        "phase11e_may_assign_weights": False,
        "phase11e_may_create_signal": False,
        "phase11e_may_test_strategy": False,
        "phase11e_may_train_model": False,
        "phase11e_may_ingest_new_data": False,
        "phase11e_may_promote_candidate": False,
    },
    "gates": {
        "require_source_rulebook": True,
        "require_panel_sections": True,
        "min_panel_sections": 6,
        "require_required_columns": True,
        "require_component_availability_spec": True,
        "require_conceptual_direction_spec": True,
        "require_missingness_policy_spec": True,
        "min_missingness_policies": 5,
        "require_weighting_policy_spec": True,
        "min_weighting_policies": 5,
        "require_blocked_family_spec": True,
        "min_blocked_families": 2,
        "require_all_panels_non_signal": True,
        "require_all_panels_no_returns": True,
        "require_phase11e_boundary_design_only": True,
        "require_no_score_calculation": True,
        "require_no_numeric_score_weights": True,
        "require_no_empirical_return_weights": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "required_design_role": "Regime scoring diagnostic panel design only",
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
    user_config = config.get("phase11d_regime_scoring_diagnostic_panel_design", {})
    return _deep_merge_dict(DEFAULT_PHASE11D_CONFIG, user_config)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _join_list(value: Any) -> str:
    return "; ".join(str(item) for item in _as_list(value))


def build_phase11d_source_rulebook(phase_config: dict[str, Any]) -> pd.DataFrame:
    source = phase_config.get("source_rulebook", {})

    return pd.DataFrame(
        [
            {
                "source_spec": str(source.get("source_spec", "")),
                "rulebook_status": str(source.get("rulebook_status", "")),
                "rationale": str(source.get("rationale", "")),
                "source_rulebook_present": bool(
                    str(source.get("source_spec", "")).strip()
                ),
                "source_phase": str(phase_config.get("source_phase", "")),
            }
        ]
    )


def build_phase11d_panel_layout_spec(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for panel in _as_list(phase_config.get("diagnostic_panel_sections")):
        required_columns = _as_list(panel.get("required_columns"))
        rows.append(
            {
                "panel_id": str(panel.get("panel_id", "")),
                "report_name": str(panel.get("report_name", "")),
                "purpose": str(panel.get("purpose", "")),
                "required": bool(panel.get("required", False)),
                "allowed_to_use_returns": bool(
                    panel.get("allowed_to_use_returns", True)
                ),
                "allowed_to_create_signal": bool(
                    panel.get("allowed_to_create_signal", True)
                ),
                "required_column_count": int(len(required_columns)),
                "required_columns": _join_list(required_columns),
            }
        )

    return pd.DataFrame(rows)


def build_phase11d_required_columns_spec(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for panel in _as_list(phase_config.get("diagnostic_panel_sections")):
        panel_id = str(panel.get("panel_id", ""))
        report_name = str(panel.get("report_name", ""))

        for column in _as_list(panel.get("required_columns")):
            rows.append(
                {
                    "panel_id": panel_id,
                    "report_name": report_name,
                    "required_column": str(column),
                }
            )

    return pd.DataFrame(rows)


def build_phase11d_component_availability_spec(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for component in _as_list(phase_config.get("component_availability_spec")):
        rows.append(
            {
                "component_id": str(component.get("component_id", "")),
                "family": str(component.get("family", "")),
                "expected_status": str(component.get("expected_status", "")),
                "source_dependency": str(component.get("source_dependency", "")),
                "future_unblock_requirement": str(
                    component.get("future_unblock_requirement", "")
                ),
                "is_blocked": str(component.get("expected_status", "")).lower()
                == "blocked",
            }
        )

    return pd.DataFrame(rows)


def build_phase11d_conceptual_direction_spec(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for component in _as_list(phase_config.get("conceptual_direction_spec")):
        rows.append(
            {
                "component_id": str(component.get("component_id", "")),
                "family": str(component.get("family", "")),
                "allowed_directions": _join_list(component.get("allowed_directions")),
                "direction_count": len(_as_list(component.get("allowed_directions"))),
                "trading_allowed": bool(component.get("trading_allowed", True)),
                "signal_allowed": bool(component.get("signal_allowed", True)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11d_missingness_policy_spec(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for policy in _as_list(phase_config.get("missingness_policy_spec")):
        rows.append(
            {
                "policy_id": str(policy.get("policy_id", "")),
                "policy": str(policy.get("policy", "")),
                "required": bool(policy.get("required", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11d_weighting_policy_spec(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for policy in _as_list(phase_config.get("weighting_policy_spec")):
        rows.append(
            {
                "policy_id": str(policy.get("policy_id", "")),
                "policy": str(policy.get("policy", "")),
                "numeric_weight_allowed": bool(
                    policy.get("numeric_weight_allowed", True)
                ),
                "empirical_return_weight_allowed": bool(
                    policy.get("empirical_return_weight_allowed", True)
                ),
                "required": bool(policy.get("required", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase11d_blocked_family_spec(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for family in _as_list(phase_config.get("blocked_family_spec")):
        rows.append(
            {
                "family": str(family.get("family", "")),
                "blocked_status": str(family.get("blocked_status", "")),
                "blocked_reason": str(family.get("blocked_reason", "")),
                "unblock_requires": str(family.get("unblock_requires", "")),
                "current_use_allowed": bool(family.get("current_use_allowed", True)),
                "score_component_allowed": bool(
                    family.get("score_component_allowed", True)
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase11d_phase11e_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase11e_boundary", {})

    rows = [
        {
            "boundary_item": "phase11e_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "implementation audit" in str(
                boundary.get("allowed_next_step", "")
            ).lower(),
        },
        {
            "boundary_item": "phase11e_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "score calculation" in str(
                    boundary.get("forbidden_next_step", "")
                ).lower()
                and "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion" in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase11e_may_build_empty_panel_templates",
            "value": bool(boundary.get("phase11e_may_build_empty_panel_templates", False)),
            "passed": bool(
                boundary.get("phase11e_may_build_empty_panel_templates", False)
            ),
        },
        {
            "boundary_item": "phase11e_may_calculate_scores",
            "value": bool(boundary.get("phase11e_may_calculate_scores", True)),
            "passed": not bool(boundary.get("phase11e_may_calculate_scores", True)),
        },
        {
            "boundary_item": "phase11e_may_assign_weights",
            "value": bool(boundary.get("phase11e_may_assign_weights", True)),
            "passed": not bool(boundary.get("phase11e_may_assign_weights", True)),
        },
        {
            "boundary_item": "phase11e_may_create_signal",
            "value": bool(boundary.get("phase11e_may_create_signal", True)),
            "passed": not bool(boundary.get("phase11e_may_create_signal", True)),
        },
        {
            "boundary_item": "phase11e_may_test_strategy",
            "value": bool(boundary.get("phase11e_may_test_strategy", True)),
            "passed": not bool(boundary.get("phase11e_may_test_strategy", True)),
        },
        {
            "boundary_item": "phase11e_may_train_model",
            "value": bool(boundary.get("phase11e_may_train_model", True)),
            "passed": not bool(boundary.get("phase11e_may_train_model", True)),
        },
        {
            "boundary_item": "phase11e_may_ingest_new_data",
            "value": bool(boundary.get("phase11e_may_ingest_new_data", True)),
            "passed": not bool(boundary.get("phase11e_may_ingest_new_data", True)),
        },
        {
            "boundary_item": "phase11e_may_promote_candidate",
            "value": bool(boundary.get("phase11e_may_promote_candidate", True)),
            "passed": not bool(boundary.get("phase11e_may_promote_candidate", True)),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11d_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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
            "value": bool(phase_config.get(key, True)),
            "passed": not bool(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11d_summary(
    *,
    phase_config: dict[str, Any],
    source_rulebook: pd.DataFrame,
    panel_layout_spec: pd.DataFrame,
    required_columns_spec: pd.DataFrame,
    component_availability_spec: pd.DataFrame,
    conceptual_direction_spec: pd.DataFrame,
    missingness_policy_spec: pd.DataFrame,
    weighting_policy_spec: pd.DataFrame,
    blocked_family_spec: pd.DataFrame,
    phase11e_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    all_panels_no_returns = (
        bool(panel_layout_spec["allowed_to_use_returns"].eq(False).all())
        if not panel_layout_spec.empty
        else False
    )
    all_panels_non_signal = (
        bool(panel_layout_spec["allowed_to_create_signal"].eq(False).all())
        if not panel_layout_spec.empty
        else False
    )
    required_columns_present = (
        int(len(required_columns_spec)) > 0
        and bool(panel_layout_spec["required_column_count"].gt(0).all())
        if not panel_layout_spec.empty
        else False
    )
    directions_non_trading = (
        bool(
            conceptual_direction_spec["trading_allowed"].eq(False).all()
            and conceptual_direction_spec["signal_allowed"].eq(False).all()
        )
        if not conceptual_direction_spec.empty
        else False
    )
    weighting_non_empirical = (
        bool(
            weighting_policy_spec["numeric_weight_allowed"].eq(False).all()
            and weighting_policy_spec["empirical_return_weight_allowed"].eq(False).all()
        )
        if not weighting_policy_spec.empty
        else False
    )
    blocked_families_clean = (
        bool(
            blocked_family_spec["current_use_allowed"].eq(False).all()
            and blocked_family_spec["score_component_allowed"].eq(False).all()
        )
        if not blocked_family_spec.empty
        else False
    )

    return pd.DataFrame(
        [
            {
                "design_role": str(phase_config.get("design_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_rulebook_present": bool(
                    source_rulebook.iloc[0]["source_rulebook_present"]
                )
                if not source_rulebook.empty
                else False,
                "panel_section_count": int(len(panel_layout_spec)),
                "required_column_rows": int(len(required_columns_spec)),
                "required_columns_present": required_columns_present,
                "component_availability_rows": int(len(component_availability_spec)),
                "conceptual_direction_rows": int(len(conceptual_direction_spec)),
                "conceptual_directions_non_trading": directions_non_trading,
                "missingness_policy_count": int(len(missingness_policy_spec)),
                "required_missingness_policy_count": int(
                    missingness_policy_spec["required"].sum()
                )
                if not missingness_policy_spec.empty
                else 0,
                "weighting_policy_count": int(len(weighting_policy_spec)),
                "required_weighting_policy_count": int(
                    weighting_policy_spec["required"].sum()
                )
                if not weighting_policy_spec.empty
                else 0,
                "weighting_non_empirical": weighting_non_empirical,
                "blocked_family_count": int(len(blocked_family_spec)),
                "blocked_families_clean": blocked_families_clean,
                "all_panels_no_returns": all_panels_no_returns,
                "all_panels_non_signal": all_panels_non_signal,
                "phase11e_boundary_passed": bool(
                    phase11e_boundary_check["passed"].all()
                )
                if not phase11e_boundary_check.empty
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


def build_phase11d_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 11D summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_design_role",
            "Regime scoring diagnostic panel design only",
        )
    )

    rows = [
        _gate_row(
            "Source rulebook is documented",
            (not gates.get("require_source_rulebook", True))
            or bool(row["source_rulebook_present"]),
            f"source_rulebook_present={bool(row['source_rulebook_present'])}",
        ),
        _gate_row(
            "Diagnostic panel sections are documented",
            (not gates.get("require_panel_sections", True))
            or int(row["panel_section_count"]) >= int(gates.get("min_panel_sections", 6)),
            f"panel_section_count={int(row['panel_section_count'])}",
        ),
        _gate_row(
            "Required columns are documented",
            (not gates.get("require_required_columns", True))
            or bool(row["required_columns_present"]),
            f"required_column_rows={int(row['required_column_rows'])}",
        ),
        _gate_row(
            "Component availability spec is documented",
            (not gates.get("require_component_availability_spec", True))
            or int(row["component_availability_rows"]) > 0,
            f"component_availability_rows={int(row['component_availability_rows'])}",
        ),
        _gate_row(
            "Conceptual direction spec is documented",
            (not gates.get("require_conceptual_direction_spec", True))
            or (
                int(row["conceptual_direction_rows"]) > 0
                and bool(row["conceptual_directions_non_trading"])
            ),
            (
                f"conceptual_direction_rows={int(row['conceptual_direction_rows'])}; "
                "conceptual_directions_non_trading="
                f"{bool(row['conceptual_directions_non_trading'])}"
            ),
        ),
        _gate_row(
            "Missingness policy spec is documented",
            (not gates.get("require_missingness_policy_spec", True))
            or int(row["missingness_policy_count"])
            >= int(gates.get("min_missingness_policies", 5)),
            f"missingness_policy_count={int(row['missingness_policy_count'])}",
        ),
        _gate_row(
            "Weighting policy spec is documented",
            (not gates.get("require_weighting_policy_spec", True))
            or (
                int(row["weighting_policy_count"])
                >= int(gates.get("min_weighting_policies", 5))
                and bool(row["weighting_non_empirical"])
            ),
            (
                f"weighting_policy_count={int(row['weighting_policy_count'])}; "
                f"weighting_non_empirical={bool(row['weighting_non_empirical'])}"
            ),
        ),
        _gate_row(
            "Blocked family spec is documented",
            (not gates.get("require_blocked_family_spec", True))
            or (
                int(row["blocked_family_count"])
                >= int(gates.get("min_blocked_families", 2))
                and bool(row["blocked_families_clean"])
            ),
            (
                f"blocked_family_count={int(row['blocked_family_count'])}; "
                f"blocked_families_clean={bool(row['blocked_families_clean'])}"
            ),
        ),
        _gate_row(
            "All panels are non-signal panels",
            (not gates.get("require_all_panels_non_signal", True))
            or bool(row["all_panels_non_signal"]),
            f"all_panels_non_signal={bool(row['all_panels_non_signal'])}",
        ),
        _gate_row(
            "All panels avoid returns usage",
            (not gates.get("require_all_panels_no_returns", True))
            or bool(row["all_panels_no_returns"]),
            f"all_panels_no_returns={bool(row['all_panels_no_returns'])}",
        ),
        _gate_row(
            "Phase 11E boundary is implementation-audit only",
            (not gates.get("require_phase11e_boundary_design_only", True))
            or bool(row["phase11e_boundary_passed"]),
            f"phase11e_boundary_passed={bool(row['phase11e_boundary_passed'])}",
        ),
        _gate_row(
            "No score calculation is allowed",
            (not gates.get("require_no_score_calculation", True))
            or not bool(phase_config.get("allow_score_calculation", True)),
            f"allow_score_calculation={phase_config.get('allow_score_calculation')}",
        ),
        _gate_row(
            "No numeric score weights are allowed",
            (not gates.get("require_no_numeric_score_weights", True))
            or not bool(phase_config.get("allow_numeric_score_weights", True)),
            (
                "allow_numeric_score_weights="
                f"{phase_config.get('allow_numeric_score_weights')}"
            ),
        ),
        _gate_row(
            "No empirical return weights are allowed",
            (not gates.get("require_no_empirical_return_weights", True))
            or not bool(phase_config.get("allow_empirical_return_weights", True)),
            (
                "allow_empirical_return_weights="
                f"{phase_config.get('allow_empirical_return_weights')}"
            ),
        ),
        _gate_row(
            "No signal creation is allowed",
            (not gates.get("require_no_signal_creation", True))
            or not bool(phase_config.get("allow_signal_creation", True)),
            f"allow_signal_creation={phase_config.get('allow_signal_creation')}",
        ),
        _gate_row(
            "No allocation rule creation is allowed",
            (not gates.get("require_no_allocation_rule_creation", True))
            or not bool(phase_config.get("allow_allocation_rule_creation", True)),
            (
                "allow_allocation_rule_creation="
                f"{phase_config.get('allow_allocation_rule_creation')}"
            ),
        ),
        _gate_row(
            "No strategy backtest is allowed",
            (not gates.get("require_no_strategy_backtest", True))
            or not bool(phase_config.get("allow_strategy_backtest", True)),
            f"allow_strategy_backtest={phase_config.get('allow_strategy_backtest')}",
        ),
        _gate_row(
            "No model training is allowed",
            (not gates.get("require_no_model_training", True))
            or not bool(phase_config.get("allow_model_training", True)),
            f"allow_model_training={phase_config.get('allow_model_training')}",
        ),
        _gate_row(
            "No new data ingestion is allowed",
            (not gates.get("require_no_new_data_ingestion", True))
            or not bool(phase_config.get("allow_new_data_ingestion", True)),
            f"allow_new_data_ingestion={phase_config.get('allow_new_data_ingestion')}",
        ),
        _gate_row(
            "No candidate promotion is allowed",
            (not gates.get("require_no_candidate_promotion", True))
            or not bool(phase_config.get("allow_candidate_promotion", True)),
            f"allow_candidate_promotion={phase_config.get('allow_candidate_promotion')}",
        ),
        _gate_row(
            "Design role is correct",
            str(row["design_role"]) == required_role,
            f"design_role={row['design_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase11d_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    if all_passed:
        verdict = "Completed — diagnostic panel design passed"
        interpretation = (
            "Phase 11D defined diagnostic panel layouts, required columns, "
            "component availability checks, conceptual direction reports, "
            "missingness reports, weighting-policy reports, blocked-family "
            "reports, and boundary checks. It did not calculate scores, assign "
            "weights, create signals, run strategy tests, ingest new data, train "
            "models, or promote a candidate."
        )
    else:
        verdict = "Failed diagnostic panel design discipline"
        interpretation = (
            "Phase 11D violated panel-design boundaries or left required panel "
            "controls incomplete. Do not proceed to panel implementation audit."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 11D",
                "diagnostic": "Regime scoring diagnostic panel design",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase11d_markdown(
    *,
    source_rulebook: pd.DataFrame,
    panel_layout_spec: pd.DataFrame,
    required_columns_spec: pd.DataFrame,
    component_availability_spec: pd.DataFrame,
    conceptual_direction_spec: pd.DataFrame,
    missingness_policy_spec: pd.DataFrame,
    weighting_policy_spec: pd.DataFrame,
    blocked_family_spec: pd.DataFrame,
    phase11e_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 11D — Regime Scoring Diagnostic Panel Design",
        "",
        "## Purpose",
        "",
        (
            "This phase defines the diagnostic panel design for a future regime "
            "scoring layer. It does not calculate scores, assign weights, create "
            "signals, run strategy tests, ingest new data, train models, or "
            "promote a candidate."
        ),
        "",
        "## Source Rulebook",
        "",
        source_rulebook.to_markdown(index=False),
        "",
        "## Panel Layout Spec",
        "",
        panel_layout_spec.to_markdown(index=False),
        "",
        "## Required Columns Spec",
        "",
        required_columns_spec.to_markdown(index=False),
        "",
        "## Component Availability Spec",
        "",
        component_availability_spec.to_markdown(index=False),
        "",
        "## Conceptual Direction Spec",
        "",
        conceptual_direction_spec.to_markdown(index=False),
        "",
        "## Missingness Policy Spec",
        "",
        missingness_policy_spec.to_markdown(index=False),
        "",
        "## Weighting Policy Spec",
        "",
        weighting_policy_spec.to_markdown(index=False),
        "",
        "## Blocked Family Spec",
        "",
        blocked_family_spec.to_markdown(index=False),
        "",
        "## Phase 11E Boundary Check",
        "",
        phase11e_boundary_check.to_markdown(index=False),
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
        "- This is a diagnostic panel design phase only.",
        "- It does not calculate regime scores.",
        "- It does not assign score weights.",
        "- It does not create signals or allocation rules.",
        "- It does not run a strategy backtest.",
        "- It does not ingest new data or train a model.",
        "- It does not promote a candidate.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase11d_regime_scoring_diagnostic_panel_design(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "source_rulebook": empty,
            "panel_layout_spec": empty,
            "required_columns_spec": empty,
            "component_availability_spec": empty,
            "conceptual_direction_spec": empty,
            "missingness_policy_spec": empty,
            "weighting_policy_spec": empty,
            "blocked_family_spec": empty,
            "phase11e_boundary_check": empty,
            "scope_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_rulebook = build_phase11d_source_rulebook(phase_config)
    panel_layout_spec = build_phase11d_panel_layout_spec(phase_config)
    required_columns_spec = build_phase11d_required_columns_spec(phase_config)
    component_availability_spec = build_phase11d_component_availability_spec(
        phase_config
    )
    conceptual_direction_spec = build_phase11d_conceptual_direction_spec(phase_config)
    missingness_policy_spec = build_phase11d_missingness_policy_spec(phase_config)
    weighting_policy_spec = build_phase11d_weighting_policy_spec(phase_config)
    blocked_family_spec = build_phase11d_blocked_family_spec(phase_config)
    phase11e_boundary_check = build_phase11d_phase11e_boundary_check(phase_config)
    scope_boundary_check = build_phase11d_scope_boundary_check(phase_config)
    summary = build_phase11d_summary(
        phase_config=phase_config,
        source_rulebook=source_rulebook,
        panel_layout_spec=panel_layout_spec,
        required_columns_spec=required_columns_spec,
        component_availability_spec=component_availability_spec,
        conceptual_direction_spec=conceptual_direction_spec,
        missingness_policy_spec=missingness_policy_spec,
        weighting_policy_spec=weighting_policy_spec,
        blocked_family_spec=blocked_family_spec,
        phase11e_boundary_check=phase11e_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase11d_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11d_conclusion(gate_report)

    source_rulebook.to_csv(
        reports_path / "phase11d_diagnostic_panel_source_rulebook.csv",
        index=False,
    )
    panel_layout_spec.to_csv(
        reports_path / "phase11d_diagnostic_panel_layout_spec.csv",
        index=False,
    )
    required_columns_spec.to_csv(
        reports_path / "phase11d_diagnostic_panel_required_columns_spec.csv",
        index=False,
    )
    component_availability_spec.to_csv(
        reports_path / "phase11d_diagnostic_panel_component_availability_spec.csv",
        index=False,
    )
    conceptual_direction_spec.to_csv(
        reports_path / "phase11d_diagnostic_panel_conceptual_direction_spec.csv",
        index=False,
    )
    missingness_policy_spec.to_csv(
        reports_path / "phase11d_diagnostic_panel_missingness_policy_spec.csv",
        index=False,
    )
    weighting_policy_spec.to_csv(
        reports_path / "phase11d_diagnostic_panel_weighting_policy_spec.csv",
        index=False,
    )
    blocked_family_spec.to_csv(
        reports_path / "phase11d_diagnostic_panel_blocked_family_spec.csv",
        index=False,
    )
    phase11e_boundary_check.to_csv(
        reports_path / "phase11d_diagnostic_panel_phase11e_boundary_check.csv",
        index=False,
    )
    scope_boundary_check.to_csv(
        reports_path / "phase11d_diagnostic_panel_scope_boundary_check.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase11d_diagnostic_panel_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase11d_diagnostic_panel_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase11d_diagnostic_panel_conclusion.csv",
        index=False,
    )

    write_phase11d_markdown(
        source_rulebook=source_rulebook,
        panel_layout_spec=panel_layout_spec,
        required_columns_spec=required_columns_spec,
        component_availability_spec=component_availability_spec,
        conceptual_direction_spec=conceptual_direction_spec,
        missingness_policy_spec=missingness_policy_spec,
        weighting_policy_spec=weighting_policy_spec,
        blocked_family_spec=blocked_family_spec,
        phase11e_boundary_check=phase11e_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase11d_regime_scoring_diagnostic_panel_design.md",
    )

    print("Wrote Phase 11D regime scoring diagnostic panel design reports.")

    return {
        "source_rulebook": source_rulebook,
        "panel_layout_spec": panel_layout_spec,
        "required_columns_spec": required_columns_spec,
        "component_availability_spec": component_availability_spec,
        "conceptual_direction_spec": conceptual_direction_spec,
        "missingness_policy_spec": missingness_policy_spec,
        "weighting_policy_spec": weighting_policy_spec,
        "blocked_family_spec": blocked_family_spec,
        "phase11e_boundary_check": phase11e_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }