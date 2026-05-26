from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE13A_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Baseline SPY research arc freeze and transition spec only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 12F",
    "proposed_next_phase": "Phase 13B",
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "baseline_freeze": {},
    "transition_decision": {},
    "phase13b_boundary": {},
    "gates": {
        "require_phase12f_passed": True,
        "require_baseline_freeze_complete": True,
        "require_transition_decision": True,
        "require_no_score_to_signal_conversion": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "require_phase13b_boundary_architecture_only": True,
        "required_spec_role": "Baseline SPY research arc freeze and transition spec only",
    },
}


DEFAULT_PHASE13B_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Multi-factor long-term decision model architecture roadmap spec only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13A",
    "proposed_next_phase": "Phase 13C",
    "ultimate_goal": "",
    "allow_feature_ingestion": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "feature_family_registry": [],
    "architecture_candidates": [],
    "dissertation_integration_plan": [],
    "walk_forward_design": {},
    "visual_reporting_plan": [],
    "paper_trading_readiness_plan": [],
    "phase13c_boundary": {},
    "gates": {
        "require_phase13a_passed": True,
        "require_ultimate_goal_present": True,
        "require_feature_family_registry": True,
        "min_feature_families": 5,
        "require_technical_macro_fundamental_sentiment": True,
        "require_architecture_candidates": True,
        "min_architecture_candidates": 4,
        "require_dissertation_integration_plan": True,
        "require_walk_forward_design": True,
        "require_visual_reporting_plan": True,
        "min_visual_reports": 5,
        "require_paper_trading_readiness_plan": True,
        "min_paper_trading_gates": 5,
        "require_phase13c_boundary_feature_inventory_only": True,
        "require_no_feature_ingestion": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_spec_role": (
            "Multi-factor long-term decision model architecture roadmap spec only"
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


def _get_phase13a_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13A_CONFIG,
        config.get("phase13a_baseline_research_arc_freeze_spec", {}),
    )


def _get_phase13b_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13B_CONFIG,
        config.get("phase13b_multifactor_model_architecture_roadmap_spec", {}),
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


def _join_list(value: Any) -> str:
    return "; ".join(str(item) for item in _as_list(value))


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase13a_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase13a_phase12f_result_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase12f_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase12f_gate_report", ""))

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

    rows = [
        {
            "check": "Phase 12F conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 12F gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})

    return out


def build_phase13a_baseline_freeze_report(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    freeze = phase_config.get("baseline_freeze", {})

    return pd.DataFrame(
        [
            {
                "baseline_arc_name": str(freeze.get("baseline_arc_name", "")),
                "baseline_arc_status": str(freeze.get("baseline_arc_status", "")),
                "final_candidate": str(freeze.get("final_candidate", "")),
                "final_candidate_role": str(freeze.get("final_candidate_role", "")),
                "diagnostic_score_state": str(
                    freeze.get("diagnostic_score_state", "")
                ),
                "diagnostic_score_role": str(freeze.get("diagnostic_score_role", "")),
                "hierarchy_changed": _bool_value(
                    freeze.get("hierarchy_changed", True)
                ),
                "candidate_promoted": _bool_value(
                    freeze.get("candidate_promoted", True)
                ),
                "score_to_signal_created": _bool_value(
                    freeze.get("score_to_signal_created", True)
                ),
                "baseline_reusable_assets": _join_list(
                    freeze.get("baseline_reusable_assets")
                ),
            }
        ]
    )


def build_phase13a_transition_decision_report(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    decision = phase_config.get("transition_decision", {})

    return pd.DataFrame(
        [
            {
                "decision": str(decision.get("decision", "")),
                "reason": str(decision.get("reason", "")),
                "rejected_next_step": str(decision.get("rejected_next_step", "")),
                "accepted_next_step": str(decision.get("accepted_next_step", "")),
                "burden_of_proof": str(decision.get("burden_of_proof", "")),
            }
        ]
    )


def build_phase13a_phase13b_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13b_boundary", {})

    checks = [
        (
            "phase13b_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "architecture roadmap spec" in str(
                boundary.get("allowed_next_step", "")
            ).lower(),
        ),
        (
            "phase13b_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            (
                "feature ingestion"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy backtest"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "candidate promotion"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        ),
        (
            "phase13b_may_define_architecture",
            _bool_value(boundary.get("phase13b_may_define_architecture", False)),
            _bool_value(boundary.get("phase13b_may_define_architecture", False)),
        ),
        (
            "phase13b_may_define_feature_families",
            _bool_value(
                boundary.get("phase13b_may_define_feature_families", False)
            ),
            _bool_value(
                boundary.get("phase13b_may_define_feature_families", False)
            ),
        ),
        (
            "phase13b_may_define_walk_forward_design",
            _bool_value(
                boundary.get("phase13b_may_define_walk_forward_design", False)
            ),
            _bool_value(
                boundary.get("phase13b_may_define_walk_forward_design", False)
            ),
        ),
        (
            "phase13b_may_define_visual_reports",
            _bool_value(boundary.get("phase13b_may_define_visual_reports", False)),
            _bool_value(boundary.get("phase13b_may_define_visual_reports", False)),
        ),
        (
            "phase13b_may_define_paper_trading_requirements",
            _bool_value(
                boundary.get(
                    "phase13b_may_define_paper_trading_requirements",
                    False,
                )
            ),
            _bool_value(
                boundary.get(
                    "phase13b_may_define_paper_trading_requirements",
                    False,
                )
            ),
        ),
        (
            "phase13b_may_ingest_data",
            _bool_value(boundary.get("phase13b_may_ingest_data", True)),
            not _bool_value(boundary.get("phase13b_may_ingest_data", True)),
        ),
        (
            "phase13b_may_train_model",
            _bool_value(boundary.get("phase13b_may_train_model", True)),
            not _bool_value(boundary.get("phase13b_may_train_model", True)),
        ),
        (
            "phase13b_may_create_signal",
            _bool_value(boundary.get("phase13b_may_create_signal", True)),
            not _bool_value(boundary.get("phase13b_may_create_signal", True)),
        ),
        (
            "phase13b_may_run_backtest",
            _bool_value(boundary.get("phase13b_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13b_may_run_backtest", True)),
        ),
        (
            "phase13b_may_promote_candidate",
            _bool_value(boundary.get("phase13b_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13b_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [
            {
                "boundary_item": item,
                "value": value,
                "passed": passed,
            }
            for item, value, passed in checks
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})

    return out


def build_phase13a_scope_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    checks = [
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No model training", "allow_model_training"),
        ("No new data ingestion", "allow_new_data_ingestion"),
        ("No candidate promotion", "allow_candidate_promotion"),
        ("No final candidate change", "allow_final_candidate_change"),
    ]

    rows = [
        {
            "scope_item": label,
            "value": _bool_value(phase_config.get(key, True)),
            "passed": not _bool_value(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})

    return out


def build_phase13a_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase12f_result_check: pd.DataFrame,
    baseline_freeze_report: pd.DataFrame,
    transition_decision_report: pd.DataFrame,
    phase13b_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    freeze = baseline_freeze_report.iloc[0] if not baseline_freeze_report.empty else {}
    decision = (
        transition_decision_report.iloc[0]
        if not transition_decision_report.empty
        else {}
    )

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase12f_result_passed": bool(phase12f_result_check["passed"].all())
                if not phase12f_result_check.empty
                else False,
                "baseline_arc_frozen": "frozen" in str(
                    freeze.get("baseline_arc_status", "")
                ).lower(),
                "baseline_role_is_not_final_project": "not final project" in str(
                    freeze.get("final_candidate_role", "")
                ).lower(),
                "diagnostic_score_state": str(
                    freeze.get("diagnostic_score_state", "")
                ),
                "score_to_signal_created": _bool_value(
                    freeze.get("score_to_signal_created", True)
                ),
                "candidate_promoted": _bool_value(
                    freeze.get("candidate_promoted", True)
                ),
                "hierarchy_changed": _bool_value(
                    freeze.get("hierarchy_changed", True)
                ),
                "transition_to_multifactor": "multi-factor" in str(
                    decision.get("decision", "")
                ).lower()
                or "multi-factor" in str(decision.get("accepted_next_step", "")).lower(),
                "direct_score_to_signal_rejected": "score-to-signal" in str(
                    decision.get("rejected_next_step", "")
                ).lower(),
                "phase13b_boundary_passed": bool(
                    phase13b_boundary_check["passed"].all()
                )
                if not phase13b_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13a_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13A summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_spec_role",
            "Baseline SPY research arc freeze and transition spec only",
        )
    )

    rows = [
        _gate_row(
            "Phase 12F remains passed",
            (not gates.get("require_phase12f_passed", True))
            or bool(row["phase12f_result_passed"]),
            f"phase12f_result_passed={bool(row['phase12f_result_passed'])}",
        ),
        _gate_row(
            "Baseline arc is frozen",
            (not gates.get("require_baseline_freeze_complete", True))
            or bool(row["baseline_arc_frozen"]),
            f"baseline_arc_frozen={bool(row['baseline_arc_frozen'])}",
        ),
        _gate_row(
            "Baseline is not treated as final project endpoint",
            bool(row["baseline_role_is_not_final_project"]),
            (
                "baseline_role_is_not_final_project="
                f"{bool(row['baseline_role_is_not_final_project'])}"
            ),
        ),
        _gate_row(
            "Transition decision opens multi-factor architecture path",
            (not gates.get("require_transition_decision", True))
            or bool(row["transition_to_multifactor"]),
            f"transition_to_multifactor={bool(row['transition_to_multifactor'])}",
        ),
        _gate_row(
            "Direct fragile-score-to-signal conversion is rejected",
            (not gates.get("require_no_score_to_signal_conversion", True))
            or bool(row["direct_score_to_signal_rejected"])
            and not bool(row["score_to_signal_created"]),
            (
                f"direct_score_to_signal_rejected="
                f"{bool(row['direct_score_to_signal_rejected'])}; "
                f"score_to_signal_created={bool(row['score_to_signal_created'])}"
            ),
        ),
        _gate_row(
            "No hierarchy change or candidate promotion occurred",
            not bool(row["hierarchy_changed"]) and not bool(row["candidate_promoted"]),
            (
                f"hierarchy_changed={bool(row['hierarchy_changed'])}; "
                f"candidate_promoted={bool(row['candidate_promoted'])}"
            ),
        ),
        _gate_row(
            "Phase 13B boundary is architecture-only",
            (not gates.get("require_phase13b_boundary_architecture_only", True))
            or bool(row["phase13b_boundary_passed"]),
            f"phase13b_boundary_passed={bool(row['phase13b_boundary_passed'])}",
        ),
        _gate_row(
            "Scope boundary blocks signal/backtest/model/data/promotion/change",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Spec role is correct",
            str(row["spec_role"]) == required_role,
            f"spec_role={row['spec_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())

    return out


def build_phase13a_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    verdict = (
        "Completed — baseline research arc freeze and transition spec passed"
        if all_passed
        else "Failed baseline research arc freeze and transition spec"
    )
    interpretation = (
        "Phase 13A froze the SPY regime-switch arc as a baseline research "
        "framework and opened the multi-factor model architecture path. It did not "
        "convert the fragile diagnostic score into a signal, run a backtest, train "
        "a model, ingest new data, promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13A found a freeze, transition, boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13A",
                "diagnostic": "Baseline SPY research arc freeze / transition spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase13a_markdown(
    *,
    source_report_check: pd.DataFrame,
    phase12f_result_check: pd.DataFrame,
    baseline_freeze_report: pd.DataFrame,
    transition_decision_report: pd.DataFrame,
    phase13b_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 13A — Baseline SPY Research Arc Freeze / Transition Spec",
        "",
        "This phase freezes the SPY regime-switch arc as a baseline research framework "
        "and opens the multi-factor model architecture path. It does not convert the "
        "fragile diagnostic score into a signal, run a backtest, train a model, ingest "
        "new data, promote a candidate, or change the final candidate.",
        "",
        "## Source Report Check",
        source_report_check.to_markdown(index=False),
        "",
        "## Phase 12F Result Check",
        phase12f_result_check.to_markdown(index=False),
        "",
        "## Baseline Freeze Report",
        baseline_freeze_report.to_markdown(index=False),
        "",
        "## Transition Decision Report",
        transition_decision_report.to_markdown(index=False),
        "",
        "## Phase 13B Boundary Check",
        phase13b_boundary_check.to_markdown(index=False),
        "",
        "## Scope Boundary Check",
        scope_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        conclusion.to_markdown(index=False),
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13a_baseline_research_arc_freeze_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13a_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13a_source_report_check(phase_config)
    phase12f_result_check = build_phase13a_phase12f_result_check(phase_config)
    baseline_freeze_report = build_phase13a_baseline_freeze_report(phase_config)
    transition_decision_report = build_phase13a_transition_decision_report(
        phase_config
    )
    phase13b_boundary_check = build_phase13a_phase13b_boundary_check(phase_config)
    scope_boundary_check = build_phase13a_scope_boundary_check(phase_config)

    summary = build_phase13a_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase12f_result_check=phase12f_result_check,
        baseline_freeze_report=baseline_freeze_report,
        transition_decision_report=transition_decision_report,
        phase13b_boundary_check=phase13b_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13a_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13a_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase12f_result_check": phase12f_result_check,
        "baseline_freeze_report": baseline_freeze_report,
        "transition_decision_report": transition_decision_report,
        "phase13b_boundary_check": phase13b_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13a_baseline_freeze_{name}.csv", index=False)

    write_phase13a_markdown(
        source_report_check=source_report_check,
        phase12f_result_check=phase12f_result_check,
        baseline_freeze_report=baseline_freeze_report,
        transition_decision_report=transition_decision_report,
        phase13b_boundary_check=phase13b_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase13a_baseline_research_arc_freeze_spec.md",
    )

    print("Wrote Phase 13A baseline research arc freeze spec reports.")
    return outputs


def build_phase13b_phase13a_result_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13a_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13a_gate_report", ""))

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

    rows = [
        {
            "check": "Phase 13A conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 13A gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})

    return out


def build_phase13b_feature_family_registry(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("feature_family_registry")):
        rows.append(
            {
                "family_id": str(item.get("family_id", "")),
                "status": str(item.get("status", "")),
                "intended_role": str(item.get("intended_role", "")),
                "immediate_action": str(item.get("immediate_action", "")),
                "blocked_now": _bool_value(item.get("blocked_now", True)),
            }
        )

    return pd.DataFrame(rows)


def build_phase13b_architecture_candidates(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("architecture_candidates")):
        rows.append(
            {
                "architecture_id": str(item.get("architecture_id", "")),
                "role": str(item.get("role", "")),
                "description": str(item.get("description", "")),
                "priority": int(item.get("priority", 999)),
                "immediate_status": str(item.get("immediate_status", "")),
            }
        )

    return pd.DataFrame(rows).sort_values("priority").reset_index(drop=True)


def build_phase13b_dissertation_integration_plan(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("dissertation_integration_plan")):
        rows.append(
            {
                "item_id": str(item.get("item_id", "")),
                "integration_type": str(item.get("integration_type", "")),
                "planned_use": str(item.get("planned_use", "")),
                "allowed_now": _bool_value(item.get("allowed_now", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase13b_walk_forward_design(phase_config: dict[str, Any]) -> pd.DataFrame:
    design = phase_config.get("walk_forward_design", {})

    return pd.DataFrame(
        [
            {
                "design_id": str(design.get("design_id", "")),
                "train_window_policy": str(design.get("train_window_policy", "")),
                "validation_policy": str(design.get("validation_policy", "")),
                "test_policy": str(design.get("test_policy", "")),
                "rebalance_policy": str(design.get("rebalance_policy", "")),
                "leakage_controls": _join_list(design.get("leakage_controls")),
            }
        ]
    )


def build_phase13b_visual_reporting_plan(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("visual_reporting_plan")):
        rows.append(
            {
                "report_id": str(item.get("report_id", "")),
                "purpose": str(item.get("purpose", "")),
            }
        )

    return pd.DataFrame(rows)


def build_phase13b_paper_trading_readiness_plan(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("paper_trading_readiness_plan")):
        rows.append(
            {
                "gate_id": str(item.get("gate_id", "")),
                "requirement": str(item.get("requirement", "")),
            }
        )

    return pd.DataFrame(rows)


def build_phase13b_phase13c_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13c_boundary", {})

    checks = [
        (
            "phase13c_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "feature-source inventory" in str(
                boundary.get("allowed_next_step", "")
            ).lower()
            or "feature inventory" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13c_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            (
                "actual feature ingestion"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "model training"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy backtest"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        ),
        (
            "phase13c_may_define_data_inventory",
            _bool_value(boundary.get("phase13c_may_define_data_inventory", False)),
            _bool_value(boundary.get("phase13c_may_define_data_inventory", False)),
        ),
        (
            "phase13c_may_define_feature_contracts",
            _bool_value(
                boundary.get("phase13c_may_define_feature_contracts", False)
            ),
            _bool_value(
                boundary.get("phase13c_may_define_feature_contracts", False)
            ),
        ),
        (
            "phase13c_may_define_leakage_controls",
            _bool_value(
                boundary.get("phase13c_may_define_leakage_controls", False)
            ),
            _bool_value(
                boundary.get("phase13c_may_define_leakage_controls", False)
            ),
        ),
        (
            "phase13c_may_ingest_features",
            _bool_value(boundary.get("phase13c_may_ingest_features", True)),
            not _bool_value(boundary.get("phase13c_may_ingest_features", True)),
        ),
        (
            "phase13c_may_train_model",
            _bool_value(boundary.get("phase13c_may_train_model", True)),
            not _bool_value(boundary.get("phase13c_may_train_model", True)),
        ),
        (
            "phase13c_may_create_signal",
            _bool_value(boundary.get("phase13c_may_create_signal", True)),
            not _bool_value(boundary.get("phase13c_may_create_signal", True)),
        ),
        (
            "phase13c_may_run_backtest",
            _bool_value(boundary.get("phase13c_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13c_may_run_backtest", True)),
        ),
        (
            "phase13c_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13c_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13c_may_deploy_paper_trading", True)),
        ),
        (
            "phase13c_may_promote_candidate",
            _bool_value(boundary.get("phase13c_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13c_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [
            {
                "boundary_item": item,
                "value": value,
                "passed": passed,
            }
            for item, value, passed in checks
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})

    return out


def build_phase13b_scope_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    checks = [
        ("No feature ingestion", "allow_feature_ingestion"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No model training", "allow_model_training"),
        ("No paper trading deployment", "allow_paper_trading_deployment"),
        ("No candidate promotion", "allow_candidate_promotion"),
        ("No final candidate change", "allow_final_candidate_change"),
    ]

    rows = [
        {
            "scope_item": label,
            "value": _bool_value(phase_config.get(key, True)),
            "passed": not _bool_value(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})

    return out


def build_phase13b_summary(
    *,
    phase_config: dict[str, Any],
    phase13a_result_check: pd.DataFrame,
    feature_family_registry: pd.DataFrame,
    architecture_candidates: pd.DataFrame,
    dissertation_integration_plan: pd.DataFrame,
    walk_forward_design: pd.DataFrame,
    visual_reporting_plan: pd.DataFrame,
    paper_trading_readiness_plan: pd.DataFrame,
    phase13c_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    family_ids = (
        set(feature_family_registry["family_id"].dropna().astype(str).tolist())
        if not feature_family_registry.empty
        else set()
    )
    required_families = {"technical", "macro", "fundamental", "sentiment"}

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "ultimate_goal_present": len(
                    str(phase_config.get("ultimate_goal", "")).strip()
                )
                > 0,
                "phase13a_result_passed": bool(phase13a_result_check["passed"].all())
                if not phase13a_result_check.empty
                else False,
                "feature_family_count": int(len(feature_family_registry)),
                "required_families_present": required_families.issubset(family_ids),
                "architecture_candidate_count": int(len(architecture_candidates)),
                "dissertation_integration_items": int(len(dissertation_integration_plan)),
                "walk_forward_design_present": not walk_forward_design.empty,
                "visual_report_count": int(len(visual_reporting_plan)),
                "paper_trading_gate_count": int(len(paper_trading_readiness_plan)),
                "phase13c_boundary_passed": bool(phase13c_boundary_check["passed"].all())
                if not phase13c_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "feature_ingestion": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "model_training": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13b_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13B summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_spec_role",
            "Multi-factor long-term decision model architecture roadmap spec only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13A passed",
            (not gates.get("require_phase13a_passed", True))
            or bool(row["phase13a_result_passed"]),
            f"phase13a_result_passed={bool(row['phase13a_result_passed'])}",
        ),
        _gate_row(
            "Ultimate goal is documented",
            (not gates.get("require_ultimate_goal_present", True))
            or bool(row["ultimate_goal_present"]),
            f"ultimate_goal_present={bool(row['ultimate_goal_present'])}",
        ),
        _gate_row(
            "Feature family registry is complete enough",
            (not gates.get("require_feature_family_registry", True))
            or int(row["feature_family_count"]) >= int(
                gates.get("min_feature_families", 5)
            ),
            f"feature_family_count={int(row['feature_family_count'])}",
        ),
        _gate_row(
            "Technical, macro, fundamental, and sentiment families are present",
            (not gates.get("require_technical_macro_fundamental_sentiment", True))
            or bool(row["required_families_present"]),
            f"required_families_present={bool(row['required_families_present'])}",
        ),
        _gate_row(
            "Architecture candidates are documented",
            (not gates.get("require_architecture_candidates", True))
            or int(row["architecture_candidate_count"]) >= int(
                gates.get("min_architecture_candidates", 4)
            ),
            f"architecture_candidate_count={int(row['architecture_candidate_count'])}",
        ),
        _gate_row(
            "Dissertation integration plan exists",
            (not gates.get("require_dissertation_integration_plan", True))
            or int(row["dissertation_integration_items"]) > 0,
            (
                "dissertation_integration_items="
                f"{int(row['dissertation_integration_items'])}"
            ),
        ),
        _gate_row(
            "Walk-forward design is documented",
            (not gates.get("require_walk_forward_design", True))
            or bool(row["walk_forward_design_present"]),
            f"walk_forward_design_present={bool(row['walk_forward_design_present'])}",
        ),
        _gate_row(
            "Visual reporting plan is documented",
            (not gates.get("require_visual_reporting_plan", True))
            or int(row["visual_report_count"]) >= int(
                gates.get("min_visual_reports", 5)
            ),
            f"visual_report_count={int(row['visual_report_count'])}",
        ),
        _gate_row(
            "Paper-trading readiness plan is documented",
            (not gates.get("require_paper_trading_readiness_plan", True))
            or int(row["paper_trading_gate_count"]) >= int(
                gates.get("min_paper_trading_gates", 5)
            ),
            f"paper_trading_gate_count={int(row['paper_trading_gate_count'])}",
        ),
        _gate_row(
            "Phase 13C boundary is feature-inventory only",
            (not gates.get("require_phase13c_boundary_feature_inventory_only", True))
            or bool(row["phase13c_boundary_passed"]),
            f"phase13c_boundary_passed={bool(row['phase13c_boundary_passed'])}",
        ),
        _gate_row(
            "No feature/signal/backtest/model/paper-trading/promotion exists",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Spec role is correct",
            str(row["spec_role"]) == required_role,
            f"spec_role={row['spec_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())

    return out


def build_phase13b_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    verdict = (
        "Completed — multi-factor model architecture roadmap spec passed"
        if all_passed
        else "Failed multi-factor model architecture roadmap spec"
    )
    interpretation = (
        "Phase 13B defined the roadmap for the actual long-term multi-factor "
        "decision-model path using technical, macro, fundamental, sentiment, and "
        "dissertation-methodology components. It did not ingest features, create "
        "signals, run backtests, train models, deploy paper trading, promote a "
        "candidate, or change the final candidate."
        if all_passed
        else "Phase 13B found an architecture-roadmap, boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13B",
                "diagnostic": "Multi-factor model architecture roadmap spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase13b_markdown(
    *,
    phase13a_result_check: pd.DataFrame,
    feature_family_registry: pd.DataFrame,
    architecture_candidates: pd.DataFrame,
    dissertation_integration_plan: pd.DataFrame,
    walk_forward_design: pd.DataFrame,
    visual_reporting_plan: pd.DataFrame,
    paper_trading_readiness_plan: pd.DataFrame,
    phase13c_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 13B — Multi-Factor Long-Term Decision Model Architecture Roadmap Spec",
        "",
        "This phase defines the roadmap for the actual multi-factor model path. It "
        "does not ingest features, create signals, run backtests, train models, deploy "
        "paper trading, promote a candidate, or change the final candidate.",
        "",
        "## Phase 13A Result Check",
        phase13a_result_check.to_markdown(index=False),
        "",
        "## Feature Family Registry",
        feature_family_registry.to_markdown(index=False),
        "",
        "## Architecture Candidates",
        architecture_candidates.to_markdown(index=False),
        "",
        "## Dissertation Integration Plan",
        dissertation_integration_plan.to_markdown(index=False),
        "",
        "## Walk-Forward Design",
        walk_forward_design.to_markdown(index=False),
        "",
        "## Visual Reporting Plan",
        visual_reporting_plan.to_markdown(index=False),
        "",
        "## Paper-Trading Readiness Plan",
        paper_trading_readiness_plan.to_markdown(index=False),
        "",
        "## Phase 13C Boundary Check",
        phase13c_boundary_check.to_markdown(index=False),
        "",
        "## Scope Boundary Check",
        scope_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        conclusion.to_markdown(index=False),
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13b_multifactor_model_architecture_roadmap_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13b_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase13a_result_check = build_phase13b_phase13a_result_check(phase_config)
    feature_family_registry = build_phase13b_feature_family_registry(phase_config)
    architecture_candidates = build_phase13b_architecture_candidates(phase_config)
    dissertation_integration_plan = build_phase13b_dissertation_integration_plan(
        phase_config
    )
    walk_forward_design = build_phase13b_walk_forward_design(phase_config)
    visual_reporting_plan = build_phase13b_visual_reporting_plan(phase_config)
    paper_trading_readiness_plan = build_phase13b_paper_trading_readiness_plan(
        phase_config
    )
    phase13c_boundary_check = build_phase13b_phase13c_boundary_check(phase_config)
    scope_boundary_check = build_phase13b_scope_boundary_check(phase_config)

    summary = build_phase13b_summary(
        phase_config=phase_config,
        phase13a_result_check=phase13a_result_check,
        feature_family_registry=feature_family_registry,
        architecture_candidates=architecture_candidates,
        dissertation_integration_plan=dissertation_integration_plan,
        walk_forward_design=walk_forward_design,
        visual_reporting_plan=visual_reporting_plan,
        paper_trading_readiness_plan=paper_trading_readiness_plan,
        phase13c_boundary_check=phase13c_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13b_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13b_conclusion(gate_report)

    outputs = {
        "phase13a_result_check": phase13a_result_check,
        "feature_family_registry": feature_family_registry,
        "architecture_candidates": architecture_candidates,
        "dissertation_integration_plan": dissertation_integration_plan,
        "walk_forward_design": walk_forward_design,
        "visual_reporting_plan": visual_reporting_plan,
        "paper_trading_readiness_plan": paper_trading_readiness_plan,
        "phase13c_boundary_check": phase13c_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13b_roadmap_{name}.csv", index=False)

    write_phase13b_markdown(
        phase13a_result_check=phase13a_result_check,
        feature_family_registry=feature_family_registry,
        architecture_candidates=architecture_candidates,
        dissertation_integration_plan=dissertation_integration_plan,
        walk_forward_design=walk_forward_design,
        visual_reporting_plan=visual_reporting_plan,
        paper_trading_readiness_plan=paper_trading_readiness_plan,
        phase13c_boundary_check=phase13c_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase13b_multifactor_model_architecture_roadmap_spec.md",
    )

    print("Wrote Phase 13B multi-factor model architecture roadmap reports.")
    return outputs