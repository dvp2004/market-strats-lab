from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE12E_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Diagnostic score interpretation and closeout audit only",
    "phase_branch": "Phase 12 diagnostic regime score branch",
    "source_phase": "Phase 12D",
    "proposed_next_phase": "Phase 12F",
    "allow_score_interpretation": True,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_score_reports": {},
    "expected_aggregate_state": "fragile",
    "allowed_score_states": ["supportive", "neutral", "fragile"],
    "interpretation_policy": {},
    "closeout_claims": {},
    "phase12f_boundary": {},
    "gates": {
        "require_source_score_reports_present": True,
        "require_phase12d_passed": True,
        "require_aggregate_state_allowed": True,
        "require_expected_fragile_state": True,
        "require_interpretation_created": True,
        "require_interpretation_diagnostic_only": True,
        "require_closeout_claims_locked": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "require_phase12f_boundary_checkpoint_only": True,
        "required_audit_role": "Diagnostic score interpretation and closeout audit only",
    },
}


DEFAULT_PHASE12F_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Final Phase 12 diagnostic score checkpoint audit only",
    "phase_branch": "Phase 12 diagnostic regime score branch",
    "checkpoint_status": (
        "Phase 12 closed — diagnostic regime score calculated, audited, "
        "interpreted, and bounded"
    ),
    "next_allowed_step": (
        "Separate future score-to-signal pre-registration spec only, if pursued"
    ),
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "expected_report_prefixes": [],
    "expected_markdown_reports": [],
    "phase_conclusion_reports": {},
    "phase_gate_reports": {},
    "required_phase_verdict_fragments": {},
    "branch_closure_claims": {},
    "future_phase13_boundary": {},
    "gates": {
        "require_report_inventory_present": True,
        "require_markdown_reports_present": True,
        "require_config_flags_clean_for_run": True,
        "require_phase_conclusions_passed": True,
        "require_phase_gate_reports_passed": True,
        "require_branch_closure_claims_locked": True,
        "require_future_phase13_boundary_prereg_only": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_audit_role": "Final Phase 12 diagnostic score checkpoint audit only",
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


def _get_phase12e_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE12E_CONFIG,
        config.get("phase12e_diagnostic_score_interpretation_closeout", {}),
    )


def _get_phase12f_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE12F_CONFIG,
        config.get("phase12f_final_diagnostic_score_checkpoint_audit", {}),
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


def build_phase12e_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for key, path in phase_config.get("source_score_reports", {}).items():
        file_path = Path(str(path))
        frame = _read_csv_if_exists(file_path)
        rows.append(
            {
                "report_key": str(key),
                "path": str(file_path),
                "present": file_path.exists(),
                "rows": int(len(frame)),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12e_phase12d_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_score_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase12d_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase12d_gate_report", ""))

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
            "check": "Phase 12D conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 12D gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12e_score_interpretation(
    *,
    phase_config: dict[str, Any],
    aggregate_score: pd.DataFrame,
    component_state_panel: pd.DataFrame,
) -> pd.DataFrame:
    policy = phase_config.get("interpretation_policy", {})

    aggregate_state = (
        str(aggregate_score.iloc[0].get("diagnostic_score_state", ""))
        if not aggregate_score.empty
        else ""
    )

    interpretation_key = f"{aggregate_state}_interpretation"
    interpretation = str(policy.get(interpretation_key, ""))

    components = (
        "; ".join(
            component_state_panel.apply(
                lambda row: (
                    f"{row.get('component_id')}={row.get('diagnostic_state')}"
                ),
                axis=1,
            ).tolist()
        )
        if not component_state_panel.empty
        else ""
    )

    return pd.DataFrame(
        [
            {
                "diagnostic_score_state": aggregate_state,
                "interpretation_role": str(policy.get("interpretation_role", "")),
                "interpretation": interpretation,
                "component_state_summary": components,
                "permitted_use": str(policy.get("permitted_use", "")),
                "prohibited_use": str(policy.get("prohibited_use", "")),
                "trading_signal_created": False,
                "allocation_rule_created": False,
                "strategy_backtest_run": False,
                "empirical_weights_assigned": False,
                "model_trained": False,
                "new_data_ingested": False,
                "candidate_promoted": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase12e_closeout_claims_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    claims = phase_config.get("closeout_claims", {})
    expected_true = ["diagnostic_score_interpreted"]
    expected_false = [
        "score_to_signal_created",
        "allocation_rule_created",
        "strategy_backtest_run",
        "empirical_weights_assigned",
        "model_trained",
        "new_data_ingested",
        "candidate_promoted",
        "final_candidate_changed",
    ]

    rows: list[dict[str, Any]] = []

    for claim in expected_true:
        actual = _bool_value(claims.get(claim, False))
        rows.append(
            {
                "claim": claim,
                "expected": True,
                "actual": actual,
                "passed": actual is True,
            }
        )

    for claim in expected_false:
        actual = _bool_value(claims.get(claim, True))
        rows.append(
            {
                "claim": claim,
                "expected": False,
                "actual": actual,
                "passed": actual is False,
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12e_phase12f_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase12f_boundary", {})

    checks = [
        (
            "phase12f_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "checkpoint audit" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase12f_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            (
                "signal" in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion" in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        ),
        (
            "phase12f_may_run_final_checkpoint",
            _bool_value(boundary.get("phase12f_may_run_final_checkpoint", False)),
            _bool_value(boundary.get("phase12f_may_run_final_checkpoint", False)),
        ),
        (
            "phase12f_may_create_signal",
            _bool_value(boundary.get("phase12f_may_create_signal", True)),
            not _bool_value(boundary.get("phase12f_may_create_signal", True)),
        ),
        (
            "phase12f_may_test_strategy",
            _bool_value(boundary.get("phase12f_may_test_strategy", True)),
            not _bool_value(boundary.get("phase12f_may_test_strategy", True)),
        ),
        (
            "phase12f_may_assign_empirical_weights",
            _bool_value(boundary.get("phase12f_may_assign_empirical_weights", True)),
            not _bool_value(
                boundary.get("phase12f_may_assign_empirical_weights", True)
            ),
        ),
        (
            "phase12f_may_train_model",
            _bool_value(boundary.get("phase12f_may_train_model", True)),
            not _bool_value(boundary.get("phase12f_may_train_model", True)),
        ),
        (
            "phase12f_may_ingest_new_data",
            _bool_value(boundary.get("phase12f_may_ingest_new_data", True)),
            not _bool_value(boundary.get("phase12f_may_ingest_new_data", True)),
        ),
        (
            "phase12f_may_promote_candidate",
            _bool_value(boundary.get("phase12f_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase12f_may_promote_candidate", True)),
        ),
        (
            "phase12f_may_change_final_candidate",
            _bool_value(boundary.get("phase12f_may_change_final_candidate", True)),
            not _bool_value(boundary.get("phase12f_may_change_final_candidate", True)),
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


def build_phase12e_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase12e_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase12d_result_check: pd.DataFrame,
    score_interpretation: pd.DataFrame,
    closeout_claims_check: pd.DataFrame,
    phase12f_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    allowed_states = set(str(item) for item in _as_list(phase_config.get("allowed_score_states")))
    aggregate_state = (
        str(score_interpretation.iloc[0]["diagnostic_score_state"])
        if not score_interpretation.empty
        else ""
    )
    expected_state = str(phase_config.get("expected_aggregate_state", ""))

    interpretation_text = (
        str(score_interpretation.iloc[0]["interpretation"])
        if not score_interpretation.empty
        else ""
    )
    prohibited_use = (
        str(score_interpretation.iloc[0]["prohibited_use"])
        if not score_interpretation.empty
        else ""
    )

    diagnostic_only = (
        "trading signal" in prohibited_use.lower()
        and "allocation rule" in prohibited_use.lower()
        and "strategy backtest" in prohibited_use.lower()
        and "candidate promotion" in prohibited_use.lower()
    )

    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_score_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase12d_result_passed": bool(phase12d_result_check["passed"].all())
                if not phase12d_result_check.empty
                else False,
                "aggregate_state": aggregate_state,
                "aggregate_state_allowed": aggregate_state in allowed_states,
                "aggregate_state_matches_expected": aggregate_state == expected_state,
                "interpretation_created": len(interpretation_text.strip()) > 0,
                "interpretation_diagnostic_only": diagnostic_only,
                "closeout_claims_locked": bool(closeout_claims_check["passed"].all())
                if not closeout_claims_check.empty
                else False,
                "phase12f_boundary_passed": bool(phase12f_boundary_check["passed"].all())
                if not phase12f_boundary_check.empty
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


def build_phase12e_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 12E summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_audit_role",
            "Diagnostic score interpretation and closeout audit only",
        )
    )

    rows = [
        _gate_row(
            "Source score reports are present",
            (not gates.get("require_source_score_reports_present", True))
            or bool(row["source_score_reports_present"]),
            f"source_score_reports_present={bool(row['source_score_reports_present'])}",
        ),
        _gate_row(
            "Phase 12D remains passed",
            (not gates.get("require_phase12d_passed", True))
            or bool(row["phase12d_result_passed"]),
            f"phase12d_result_passed={bool(row['phase12d_result_passed'])}",
        ),
        _gate_row(
            "Aggregate score state is allowed",
            (not gates.get("require_aggregate_state_allowed", True))
            or bool(row["aggregate_state_allowed"]),
            f"aggregate_state={row['aggregate_state']}",
        ),
        _gate_row(
            "Aggregate score state matches expected fragile state",
            (not gates.get("require_expected_fragile_state", True))
            or bool(row["aggregate_state_matches_expected"]),
            f"aggregate_state_matches_expected={bool(row['aggregate_state_matches_expected'])}",
        ),
        _gate_row(
            "Diagnostic interpretation was created",
            (not gates.get("require_interpretation_created", True))
            or bool(row["interpretation_created"]),
            f"interpretation_created={bool(row['interpretation_created'])}",
        ),
        _gate_row(
            "Interpretation remains diagnostic-only",
            (not gates.get("require_interpretation_diagnostic_only", True))
            or bool(row["interpretation_diagnostic_only"]),
            f"interpretation_diagnostic_only={bool(row['interpretation_diagnostic_only'])}",
        ),
        _gate_row(
            "Closeout claims are locked",
            (not gates.get("require_closeout_claims_locked", True))
            or bool(row["closeout_claims_locked"]),
            f"closeout_claims_locked={bool(row['closeout_claims_locked'])}",
        ),
        _gate_row(
            "Phase 12F boundary is checkpoint-only",
            (not gates.get("require_phase12f_boundary_checkpoint_only", True))
            or bool(row["phase12f_boundary_passed"]),
            f"phase12f_boundary_passed={bool(row['phase12f_boundary_passed'])}",
        ),
        _gate_row(
            "No signal/allocation/backtest/model/data/promotion/change is allowed",
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


def build_phase12e_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    verdict = (
        "Completed — diagnostic score interpretation closeout passed"
        if all_passed
        else "Failed diagnostic score interpretation closeout"
    )
    interpretation = (
        "Phase 12E interpreted the fragile diagnostic score as a research-only "
        "diagnostic and closed the score-interpretation branch without creating a "
        "signal, allocation rule, backtest, empirical weighting, model, new data "
        "ingestion, candidate promotion, or final-candidate change."
        if all_passed
        else "Phase 12E found an interpretation, closeout, boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 12E",
                "diagnostic": "Diagnostic score interpretation and closeout audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase12e_markdown(
    *,
    source_report_check: pd.DataFrame,
    phase12d_result_check: pd.DataFrame,
    score_interpretation: pd.DataFrame,
    closeout_claims_check: pd.DataFrame,
    phase12f_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 12E — Diagnostic Score Interpretation / Closeout Audit",
        "",
        "This phase interprets the diagnostic score as research-only context. It does "
        "not create signals, allocation rules, backtests, empirical weights, models, "
        "new data ingestion, candidate promotion, or final-candidate change.",
        "",
        "## Source Report Check",
        source_report_check.to_markdown(index=False),
        "",
        "## Phase 12D Result Check",
        phase12d_result_check.to_markdown(index=False),
        "",
        "## Score Interpretation",
        score_interpretation.to_markdown(index=False),
        "",
        "## Closeout Claims Check",
        closeout_claims_check.to_markdown(index=False),
        "",
        "## Phase 12F Boundary Check",
        phase12f_boundary_check.to_markdown(index=False),
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


def save_phase12e_diagnostic_score_interpretation_closeout(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase12e_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase12e_source_report_check(phase_config)
    phase12d_result_check = build_phase12e_phase12d_result_check(phase_config)

    reports = phase_config.get("source_score_reports", {})
    aggregate_score = _read_csv_if_exists(reports.get("aggregate_score", ""))
    component_state_panel = _read_csv_if_exists(reports.get("component_state_panel", ""))

    score_interpretation = build_phase12e_score_interpretation(
        phase_config=phase_config,
        aggregate_score=aggregate_score,
        component_state_panel=component_state_panel,
    )
    closeout_claims_check = build_phase12e_closeout_claims_check(phase_config)
    phase12f_boundary_check = build_phase12e_phase12f_boundary_check(phase_config)
    scope_boundary_check = build_phase12e_scope_boundary_check(phase_config)
    summary = build_phase12e_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase12d_result_check=phase12d_result_check,
        score_interpretation=score_interpretation,
        closeout_claims_check=closeout_claims_check,
        phase12f_boundary_check=phase12f_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase12e_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase12e_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase12d_result_check": phase12d_result_check,
        "score_interpretation": score_interpretation,
        "closeout_claims_check": closeout_claims_check,
        "phase12f_boundary_check": phase12f_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase12e_interpretation_{name}.csv", index=False)

    write_phase12e_markdown(
        source_report_check=source_report_check,
        phase12d_result_check=phase12d_result_check,
        score_interpretation=score_interpretation,
        closeout_claims_check=closeout_claims_check,
        phase12f_boundary_check=phase12f_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase12e_diagnostic_score_interpretation_closeout.md",
    )

    print("Wrote Phase 12E diagnostic score interpretation closeout reports.")
    return outputs


def build_phase12f_report_inventory_check(
    *,
    reports_dir: str | Path,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports_path = Path(reports_dir)
    rows: list[dict[str, Any]] = []

    for prefix in _as_list(phase_config.get("expected_report_prefixes")):
        matches = sorted(item.name for item in reports_path.glob(f"{prefix}*"))
        rows.append(
            {
                "check_type": "prefix",
                "expected_item": str(prefix),
                "present": len(matches) > 0,
                "match_count": len(matches),
                "matches": "; ".join(matches),
            }
        )

    for report_name in _as_list(phase_config.get("expected_markdown_reports")):
        report_path = reports_path / str(report_name)
        rows.append(
            {
                "check_type": "markdown",
                "expected_item": str(report_name),
                "present": report_path.exists(),
                "match_count": int(report_path.exists()),
                "matches": str(report_name) if report_path.exists() else "",
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12f_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for config_key, expected in expected_flags.items():
        actual = runtime_config.get(config_key, {}).get("enabled")
        passed = actual is expected
        rows.append(
            {
                "config_key": str(config_key),
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase12f_phase_conclusion_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    conclusion_reports = phase_config.get("phase_conclusion_reports", {})
    required_fragments = phase_config.get("required_phase_verdict_fragments", {})
    rows: list[dict[str, Any]] = []

    for phase_id, path in conclusion_reports.items():
        frame = _read_csv_if_exists(path)
        verdict = ""
        all_gates_passed = False

        if not frame.empty:
            verdict = str(frame.iloc[0].get("verdict", ""))
            all_gates_passed = _bool_value(
                frame.iloc[0].get("all_gates_passed", False)
            )

        required_fragment = str(required_fragments.get(phase_id, "")).lower()
        fragment_present = required_fragment in verdict.lower()
        passed = not frame.empty and all_gates_passed and fragment_present

        rows.append(
            {
                "phase_id": str(phase_id),
                "report_path": str(path),
                "present": not frame.empty,
                "verdict": verdict,
                "all_gates_passed": all_gates_passed,
                "required_fragment": required_fragment,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase12f_phase_gate_report_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for phase_id, path in phase_config.get("phase_gate_reports", {}).items():
        frame = _read_csv_if_exists(path)
        passed = (
            not frame.empty
            and "passed" in frame.columns
            and bool(frame["passed"].map(_bool_value).all())
        )
        rows.append(
            {
                "phase_id": str(phase_id),
                "report_path": str(path),
                "present": not frame.empty,
                "gate_rows": int(len(frame)),
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase12f_branch_closure_claims_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    claims = phase_config.get("branch_closure_claims", {})
    expected_true = ["diagnostic_score_exists", "diagnostic_score_interpreted"]
    expected_false = [
        "score_to_signal_created",
        "allocation_rule_created",
        "strategy_backtest_run",
        "empirical_weights_assigned",
        "model_trained",
        "new_data_ingested",
        "candidate_promoted",
        "final_candidate_changed",
    ]

    rows: list[dict[str, Any]] = []

    for claim in expected_true:
        actual = _bool_value(claims.get(claim, False))
        rows.append(
            {
                "claim": claim,
                "expected": True,
                "actual": actual,
                "passed": actual is True,
            }
        )

    for claim in expected_false:
        actual = _bool_value(claims.get(claim, True))
        rows.append(
            {
                "claim": claim,
                "expected": False,
                "actual": actual,
                "passed": actual is False,
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase12f_future_phase13_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("future_phase13_boundary", {})

    checks = [
        (
            "phase13_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "pre-registration spec" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            (
                "direct signal" in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion" in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        ),
        (
            "phase13_may_define_signal_spec",
            _bool_value(boundary.get("phase13_may_define_signal_spec", False)),
            _bool_value(boundary.get("phase13_may_define_signal_spec", False)),
        ),
        (
            "phase13_may_create_signal_immediately",
            _bool_value(boundary.get("phase13_may_create_signal_immediately", True)),
            not _bool_value(boundary.get("phase13_may_create_signal_immediately", True)),
        ),
        (
            "phase13_may_test_strategy",
            _bool_value(boundary.get("phase13_may_test_strategy", True)),
            not _bool_value(boundary.get("phase13_may_test_strategy", True)),
        ),
        (
            "phase13_may_assign_empirical_weights",
            _bool_value(boundary.get("phase13_may_assign_empirical_weights", True)),
            not _bool_value(boundary.get("phase13_may_assign_empirical_weights", True)),
        ),
        (
            "phase13_may_train_model",
            _bool_value(boundary.get("phase13_may_train_model", True)),
            not _bool_value(boundary.get("phase13_may_train_model", True)),
        ),
        (
            "phase13_may_ingest_new_data",
            _bool_value(boundary.get("phase13_may_ingest_new_data", True)),
            not _bool_value(boundary.get("phase13_may_ingest_new_data", True)),
        ),
        (
            "phase13_may_promote_candidate",
            _bool_value(boundary.get("phase13_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13_may_promote_candidate", True)),
        ),
        (
            "phase13_may_change_final_candidate",
            _bool_value(boundary.get("phase13_may_change_final_candidate", True)),
            not _bool_value(boundary.get("phase13_may_change_final_candidate", True)),
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


def build_phase12f_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase12f_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    phase_conclusion_check: pd.DataFrame,
    phase_gate_report_check: pd.DataFrame,
    branch_closure_claims_check: pd.DataFrame,
    future_phase13_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    prefix_rows = (
        report_inventory_check[report_inventory_check["check_type"] == "prefix"]
        if not report_inventory_check.empty
        else pd.DataFrame()
    )
    markdown_rows = (
        report_inventory_check[report_inventory_check["check_type"] == "markdown"]
        if not report_inventory_check.empty
        else pd.DataFrame()
    )

    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "checkpoint_status": str(phase_config.get("checkpoint_status", "")),
                "next_allowed_step": str(phase_config.get("next_allowed_step", "")),
                "report_prefixes_present": bool(prefix_rows["present"].all())
                if not prefix_rows.empty
                else False,
                "markdown_reports_present": bool(markdown_rows["present"].all())
                if not markdown_rows.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "phase_conclusions_passed": bool(phase_conclusion_check["passed"].all())
                if not phase_conclusion_check.empty
                else False,
                "phase_gate_reports_passed": bool(phase_gate_report_check["passed"].all())
                if not phase_gate_report_check.empty
                else False,
                "branch_closure_claims_locked": bool(
                    branch_closure_claims_check["passed"].all()
                )
                if not branch_closure_claims_check.empty
                else False,
                "future_phase13_boundary_passed": bool(
                    future_phase13_boundary_check["passed"].all()
                )
                if not future_phase13_boundary_check.empty
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


def build_phase12f_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 12F summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_audit_role",
            "Final Phase 12 diagnostic score checkpoint audit only",
        )
    )

    rows = [
        _gate_row(
            "Expected Phase 12 report prefixes are present",
            (not gates.get("require_report_inventory_present", True))
            or bool(row["report_prefixes_present"]),
            f"report_prefixes_present={bool(row['report_prefixes_present'])}",
        ),
        _gate_row(
            "Expected Phase 12 markdown reports are present",
            (not gates.get("require_markdown_reports_present", True))
            or bool(row["markdown_reports_present"]),
            f"markdown_reports_present={bool(row['markdown_reports_present'])}",
        ),
        _gate_row(
            "Config flags are clean for checkpoint run",
            (not gates.get("require_config_flags_clean_for_run", True))
            or bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Phase 12 conclusions passed",
            (not gates.get("require_phase_conclusions_passed", True))
            or bool(row["phase_conclusions_passed"]),
            f"phase_conclusions_passed={bool(row['phase_conclusions_passed'])}",
        ),
        _gate_row(
            "Phase 12 gate reports passed",
            (not gates.get("require_phase_gate_reports_passed", True))
            or bool(row["phase_gate_reports_passed"]),
            f"phase_gate_reports_passed={bool(row['phase_gate_reports_passed'])}",
        ),
        _gate_row(
            "Branch closure claims are locked",
            (not gates.get("require_branch_closure_claims_locked", True))
            or bool(row["branch_closure_claims_locked"]),
            f"branch_closure_claims_locked={bool(row['branch_closure_claims_locked'])}",
        ),
        _gate_row(
            "Future Phase 13 boundary is pre-registration-only",
            (not gates.get("require_future_phase13_boundary_prereg_only", True))
            or bool(row["future_phase13_boundary_passed"]),
            f"future_phase13_boundary_passed={bool(row['future_phase13_boundary_passed'])}",
        ),
        _gate_row(
            "No signal/allocation/backtest/model/data/promotion/change is allowed",
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


def build_phase12f_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    verdict = (
        "Completed — final Phase 12 diagnostic score checkpoint passed"
        if all_passed
        else "Failed final Phase 12 diagnostic score checkpoint"
    )
    interpretation = (
        "Phase 12F closed the diagnostic regime-score branch. Phase 12A-F reports "
        "and gates passed, the diagnostic score was calculated, audited, interpreted, "
        "and bounded, and no score-to-signal conversion, allocation rule, backtest, "
        "empirical weighting, model, new data ingestion, candidate promotion, or "
        "final-candidate change exists. Any future score-to-signal work requires a "
        "separate pre-registration phase."
        if all_passed
        else "Phase 12F found a report, config, conclusion, boundary, or closeout issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 12F",
                "diagnostic": "Final Phase 12 diagnostic score checkpoint audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase12f_markdown(
    *,
    report_inventory_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    phase_conclusion_check: pd.DataFrame,
    phase_gate_report_check: pd.DataFrame,
    branch_closure_claims_check: pd.DataFrame,
    future_phase13_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 12F — Final Diagnostic Score Checkpoint Audit",
        "",
        "This final checkpoint closes Phase 12. It does not create signals, allocation "
        "rules, backtests, empirical weights, models, new data ingestion, candidate "
        "promotion, or final-candidate change.",
        "",
        "## Report Inventory Check",
        report_inventory_check.to_markdown(index=False),
        "",
        "## Config Flag Check",
        config_flag_check.to_markdown(index=False),
        "",
        "## Phase Conclusion Check",
        phase_conclusion_check.to_markdown(index=False),
        "",
        "## Phase Gate Report Check",
        phase_gate_report_check.to_markdown(index=False),
        "",
        "## Branch Closure Claims Check",
        branch_closure_claims_check.to_markdown(index=False),
        "",
        "## Future Phase 13 Boundary Check",
        future_phase13_boundary_check.to_markdown(index=False),
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


def save_phase12f_final_diagnostic_score_checkpoint_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase12f_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase12f_report_inventory_check(
        reports_dir=reports_path,
        phase_config=phase_config,
    )
    config_flag_check = build_phase12f_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )
    phase_conclusion_check = build_phase12f_phase_conclusion_check(phase_config)
    phase_gate_report_check = build_phase12f_phase_gate_report_check(phase_config)
    branch_closure_claims_check = build_phase12f_branch_closure_claims_check(
        phase_config
    )
    future_phase13_boundary_check = build_phase12f_future_phase13_boundary_check(
        phase_config
    )
    scope_boundary_check = build_phase12f_scope_boundary_check(phase_config)

    summary = build_phase12f_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        config_flag_check=config_flag_check,
        phase_conclusion_check=phase_conclusion_check,
        phase_gate_report_check=phase_gate_report_check,
        branch_closure_claims_check=branch_closure_claims_check,
        future_phase13_boundary_check=future_phase13_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase12f_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase12f_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "config_flag_check": config_flag_check,
        "phase_conclusion_check": phase_conclusion_check,
        "phase_gate_report_check": phase_gate_report_check,
        "branch_closure_claims_check": branch_closure_claims_check,
        "future_phase13_boundary_check": future_phase13_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase12f_final_{name}.csv", index=False)

    write_phase12f_markdown(
        report_inventory_check=report_inventory_check,
        config_flag_check=config_flag_check,
        phase_conclusion_check=phase_conclusion_check,
        phase_gate_report_check=phase_gate_report_check,
        branch_closure_claims_check=branch_closure_claims_check,
        future_phase13_boundary_check=future_phase13_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase12f_final_diagnostic_score_checkpoint_audit.md",
    )

    print("Wrote Phase 12F final diagnostic score checkpoint audit reports.")
    return outputs