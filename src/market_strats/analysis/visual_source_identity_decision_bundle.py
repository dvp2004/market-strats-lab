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
    rows = []
    for report_key, path in paths.items():
        p = Path(path)
        frame = _read_csv_if_exists(p)
        rows.append(
            {
                "report_key": report_key,
                "path": str(p),
                "present": p.exists(),
                "rows": len(frame),
                "result": "Passed" if p.exists() else "Failed",
            }
        )
    return pd.DataFrame(rows)


def _phase_result_check(conclusion_path: str, gate_path: str, phase_name: str) -> pd.DataFrame:
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
        "allow_live_trading",
        "allow_real_money_deployment",
        "allow_paper_trading_deployment",
        "allow_paper_trading_ready_claim",
        "allow_candidate_promotion",
        "allow_final_candidate_change",
        "allow_model_training",
        "allow_unregistered_ml",
        "allow_feature_importance",
    ]
    rows = []
    for key in keys:
        value = _bool_value(section.get(key, False))
        rows.append({"scope_item": key, "value": value, "passed": not value})
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _boundary_check(section: dict[str, Any], key: str) -> pd.DataFrame:
    boundary = section.get(key, {})
    allowed_failed = str(boundary.get("allowed_next_step_if_failed", "")).lower()
    allowed_passed = str(boundary.get("allowed_next_step_if_passed", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": f"{key}_failed_path_is_correction_only",
            "passed": "correction" in allowed_failed or "re-run" in allowed_failed or "rerun" in allowed_failed,
            "detail": boundary.get("allowed_next_step_if_failed", ""),
        },
        {
            "check": f"{key}_passed_path_is_workflow_prereg_only",
            "passed": "pre-registration" in allowed_passed or "preregistration" in allowed_passed,
            "detail": boundary.get("allowed_next_step_if_passed", ""),
        },
        {
            "check": f"{key}_blocks_forbidden_actions",
            "passed": (
                "live trading" in forbidden
                and "real-money" in forbidden
                and "paper-trading deployment" in forbidden
                and "candidate promotion" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _config_flag_check(config: dict[str, Any], expected: dict[str, bool]) -> pd.DataFrame:
    rows = []
    for key, expected_value in expected.items():
        actual = config.get(key, {}).get("enabled")
        rows.append(
            {
                "config_key": key,
                "expected_enabled": expected_value,
                "actual_enabled": actual,
                "passed": actual is expected_value,
            }
        )
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _candidate_metric_row(benchmark: pd.DataFrame) -> pd.Series | None:
    if benchmark.empty or "series" not in benchmark.columns:
        return None
    candidate = benchmark[benchmark["series"].astype(str).str.lower().eq("candidate")]
    if candidate.empty:
        return None
    return candidate.iloc[0]


def _source_identity_report(
    *,
    source_resolution: pd.DataFrame,
    route_selection: pd.DataFrame,
    policy: dict[str, Any],
) -> pd.DataFrame:
    expected_id = str(policy.get("expected_candidate_system_id", ""))
    required = [str(x).lower() for x in _as_list(policy.get("required_source_name_fragments"))]
    suspicious = [str(x).lower() for x in _as_list(policy.get("suspicious_source_name_fragments"))]

    source_name = ""
    if not source_resolution.empty:
        source_name = str(source_resolution.iloc[0].get("source_name", ""))

    selected_candidate_system_id = ""
    if not route_selection.empty:
        selected_candidate_system_id = str(route_selection.iloc[0].get("candidate_system_id", ""))

    source_lower = source_name.lower()
    expected_lower = expected_id.lower()

    expected_id_in_route = selected_candidate_system_id == expected_id
    expected_fragment_in_source = expected_lower in source_lower
    required_fragments_present = all(fragment in source_lower for fragment in required)
    suspicious_allocator_source = any(fragment in source_lower for fragment in suspicious)

    source_identity_passed = bool(
        expected_id_in_route
        and (expected_fragment_in_source or required_fragments_present)
        and not (suspicious_allocator_source and not expected_fragment_in_source)
    )

    source_identity_failed = not source_identity_passed

    return pd.DataFrame(
        [
            {
                "intended_candidate_system_id": expected_id,
                "selected_candidate_system_id": selected_candidate_system_id,
                "resolved_source_name": source_name,
                "expected_id_in_route": expected_id_in_route,
                "expected_fragment_in_source": expected_fragment_in_source,
                "required_fragments_present": required_fragments_present,
                "suspicious_allocator_source": suspicious_allocator_source,
                "source_identity_passed": source_identity_passed,
                "source_identity_failed": source_identity_failed,
                "interpretation": (
                    "Resolved source appears to match intended candidate."
                    if source_identity_passed
                    else "Resolved source does not clearly match intended Phase 6B/6C loose_relief candidate."
                ),
            }
        ]
    )


def _metric_reconciliation_report(
    *,
    benchmark: pd.DataFrame,
    config_section: dict[str, Any],
) -> pd.DataFrame:
    reconciliation = config_section.get("canonical_metric_reconciliation", {})
    tolerance = reconciliation.get("tolerance", {})
    cagr_tol = float(tolerance.get("cagr_abs_tolerance", 0.005))
    calmar_tol = float(tolerance.get("calmar_abs_tolerance", 0.025))
    dd_tol = float(tolerance.get("max_drawdown_abs_tolerance", 0.025))
    final_value_tol = float(tolerance.get("final_value_relative_tolerance", 0.05))

    candidate = _candidate_metric_row(benchmark)
    rows = []

    for system in reconciliation.get("canonical_systems", []):
        system_id = str(system.get("system_id", ""))
        compare_to_candidate = _bool_value(system.get("compare_to_phase14c_candidate", False))

        expected_cagr = float(system.get("expected_cagr", 0.0))
        expected_calmar = float(system.get("expected_calmar", 0.0))
        expected_max_dd = float(system.get("expected_max_drawdown", 0.0))
        expected_final_value = system.get("expected_final_value", None)

        observed_cagr = None
        observed_calmar = None
        observed_max_dd = None
        observed_final_value = None

        if compare_to_candidate and candidate is not None:
            observed_cagr = float(candidate.get("cagr", 0.0))
            observed_calmar = float(candidate.get("calmar", 0.0))
            observed_max_dd = float(candidate.get("max_drawdown", 0.0))
            observed_final_value = float(candidate.get("end_value", 0.0))

        cagr_pass = True
        calmar_pass = True
        dd_pass = True
        final_value_pass = True

        if compare_to_candidate and candidate is not None:
            cagr_pass = abs(observed_cagr - expected_cagr) <= cagr_tol
            calmar_pass = abs(observed_calmar - expected_calmar) <= calmar_tol
            dd_pass = abs(observed_max_dd - expected_max_dd) <= dd_tol

            if expected_final_value is not None:
                expected_final_value = float(expected_final_value)
                final_value_pass = (
                    abs(observed_final_value - expected_final_value) / expected_final_value
                    <= final_value_tol
                )

        rows.append(
            {
                "system_id": system_id,
                "label": system.get("label", ""),
                "required_in_side_by_side": _bool_value(system.get("required_in_side_by_side", False)),
                "compare_to_phase14c_candidate": compare_to_candidate,
                "expected_cagr": expected_cagr,
                "observed_cagr": observed_cagr,
                "cagr_reconciled": cagr_pass,
                "expected_calmar": expected_calmar,
                "observed_calmar": observed_calmar,
                "calmar_reconciled": calmar_pass,
                "expected_max_drawdown": expected_max_dd,
                "observed_max_drawdown": observed_max_dd,
                "max_drawdown_reconciled": dd_pass,
                "expected_final_value": expected_final_value,
                "observed_final_value": observed_final_value,
                "final_value_reconciled": final_value_pass,
                "metric_reconciliation_passed": bool(
                    cagr_pass and calmar_pass and dd_pass and final_value_pass
                ),
            }
        )

    return pd.DataFrame(rows)


def _side_by_side_comparison_report(
    metric_reconciliation: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for _, row in metric_reconciliation.iterrows():
        rows.append(
            {
                "system_id": row["system_id"],
                "label": row["label"],
                "source": "canonical_checkpoint",
                "cagr": row["expected_cagr"],
                "calmar": row["expected_calmar"],
                "max_drawdown": row["expected_max_drawdown"],
                "final_value": row.get("expected_final_value", None),
                "required_for_phase14e": row["required_in_side_by_side"],
            }
        )

    candidate = _candidate_metric_row(benchmark)
    if candidate is not None:
        rows.append(
            {
                "system_id": "phase14c_visualised_candidate",
                "label": "Phase 14C visualised candidate",
                "source": "phase14c_visual_backtest",
                "cagr": float(candidate.get("cagr", 0.0)),
                "calmar": float(candidate.get("calmar", 0.0)),
                "max_drawdown": float(candidate.get("max_drawdown", 0.0)),
                "final_value": float(candidate.get("end_value", 0.0)),
                "required_for_phase14e": True,
            }
        )

    return pd.DataFrame(rows)


def _current_signal_state_report(signal_preview: pd.DataFrame) -> pd.DataFrame:
    if signal_preview.empty:
        return pd.DataFrame(
            [
                {
                    "signal_determined": False,
                    "warning": "Signal preview file is empty or missing.",
                    "paper_trading_allowed": False,
                }
            ]
        )

    latest = signal_preview.copy()
    latest["decision_date"] = pd.to_datetime(latest["decision_date"], errors="coerce")
    latest = latest.sort_values("decision_date").tail(1)

    if latest.empty:
        return pd.DataFrame(
            [
                {
                    "signal_determined": False,
                    "warning": "Latest signal row could not be determined.",
                    "paper_trading_allowed": False,
                }
            ]
        )

    row = latest.iloc[0]
    preview_only = str(row.get("paper_trading_status", "")).lower() == "preview_only_not_deployment"
    live_allowed = _bool_value(row.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(row.get("real_money_allowed", False))

    return pd.DataFrame(
        [
            {
                "signal_determined": True,
                "latest_decision_date": row.get("decision_date", ""),
                "current_mode": row.get("mode", ""),
                "current_exposure": row.get("exposure", ""),
                "current_candidate_action": row.get("action_template", ""),
                "preview_only": preview_only,
                "paper_trading_allowed": False,
                "live_trading_allowed": live_allowed,
                "real_money_allowed": real_money_allowed,
                "data_timestamp_source": "phase14c_visual_backtest_signal_template_preview.csv",
                "warning": "" if preview_only else "Signal preview was not marked preview-only.",
            }
        ]
    )


def _interpretation_decision_report(
    source_identity: pd.DataFrame,
    metric_reconciliation: pd.DataFrame,
    current_signal: pd.DataFrame,
) -> pd.DataFrame:
    source_failed = _bool_value(source_identity.iloc[0].get("source_identity_failed", True))
    metric_failed = not bool(metric_reconciliation["metric_reconciliation_passed"].all())
    signal_determined = _bool_value(current_signal.iloc[0].get("signal_determined", False))

    if source_failed:
        decision = "source_identity_failed_block_paper_workflow"
        next_action = "candidate_source_correction_and_visual_rerun_required"
        reason = "Phase 14C visual source does not clearly match intended Phase 6B/6C loose_relief candidate."
    elif metric_failed:
        decision = "metric_reconciliation_failed_block_paper_workflow"
        next_action = "candidate_source_correction_and_visual_rerun_required"
        reason = "Phase 14C metrics do not reconcile with canonical candidate metrics within tolerance."
    elif not signal_determined:
        decision = "signal_state_unclear_block_paper_workflow"
        next_action = "signal_template_correction_required"
        reason = "Current signal state could not be determined."
    else:
        decision = "source_identity_passed_allow_workflow_preregistration"
        next_action = "paper_trading_workflow_preregistration_allowed_next"
        reason = "Source identity and metric reconciliation passed; workflow pre-registration may be considered."

    return pd.DataFrame(
        [
            {
                "decision": decision,
                "next_action": next_action,
                "decision_reason": reason,
                "source_identity_failed": source_failed,
                "metric_reconciliation_failed": metric_failed,
                "signal_determined": signal_determined,
                "paper_trading_workflow_preregistration_allowed": (
                    decision == "source_identity_passed_allow_workflow_preregistration"
                ),
                "paper_trading_deployment_allowed": False,
                "paper_trading_ready": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def save_phase14e_visual_backtest_interpretation_source_identity_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase14e_visual_backtest_interpretation_source_identity_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = section.get("source_reports", {})
    source_check = _source_report_check(reports)
    phase14d_check = _phase_result_check(
        reports["phase14d_conclusion"],
        reports["phase14d_gate_report"],
        "Phase 14D",
    )

    source_resolution = _read_csv_if_exists(reports["phase14c_source_resolution"])
    benchmark = _read_csv_if_exists(reports["phase14c_benchmark_comparison"])
    signal_preview = _read_csv_if_exists(reports["phase14c_signal_template_preview"])
    route_selection = _read_csv_if_exists(reports["phase13aw_route_selection"])

    source_identity = _source_identity_report(
        source_resolution=source_resolution,
        route_selection=route_selection,
        policy=section.get("source_identity_policy", {}),
    )
    metric_reconciliation = _metric_reconciliation_report(
        benchmark=benchmark,
        config_section=section,
    )
    side_by_side = _side_by_side_comparison_report(metric_reconciliation, benchmark)
    current_signal = _current_signal_state_report(signal_preview)
    interpretation = _interpretation_decision_report(
        source_identity,
        metric_reconciliation,
        current_signal,
    )
    boundary = _boundary_check(section, "phase14f_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase14d_passed": bool(phase14d_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all()) if not source_check.empty else False,
                "source_identity_passed": _bool_value(source_identity.iloc[0]["source_identity_passed"]),
                "source_identity_failed": _bool_value(source_identity.iloc[0]["source_identity_failed"]),
                "metric_reconciliation_passed": bool(metric_reconciliation["metric_reconciliation_passed"].all()),
                "current_signal_determined": _bool_value(current_signal.iloc[0].get("signal_determined", False)),
                "interpretation_decision": interpretation.iloc[0]["decision"],
                "paper_workflow_allowed": _bool_value(
                    interpretation.iloc[0]["paper_trading_workflow_preregistration_allowed"]
                ),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "live_trading": False,
                "real_money_deployment": False,
                "paper_trading_ready_claim": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 14D passed", bool(summary.iloc[0]["phase14d_passed"]), "phase14d"),
            _gate_row("Source identity report exists", len(source_identity) == 1, "source identity"),
            _gate_row("Metric reconciliation report exists", len(metric_reconciliation) > 0, "metrics"),
            _gate_row("Side-by-side comparison report exists", len(side_by_side) >= 5, f"rows={len(side_by_side)}"),
            _gate_row("Current signal state report exists", len(current_signal) == 1, "signal state"),
            _gate_row("Interpretation decision report exists", len(interpretation) == 1, str(interpretation.iloc[0]["decision"])),
            _gate_row("Phase 14F boundary is conditional-only", bool(boundary["passed"].all()), "phase14f"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role") == "Visual backtest interpretation and candidate source identity audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14E",
                "diagnostic": "Visual backtest interpretation and candidate source identity audit",
                "verdict": (
                    "Completed — visual source identity audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed visual source identity audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "source_identity_failed": _bool_value(source_identity.iloc[0]["source_identity_failed"]),
                "paper_trading_workflow_preregistration_allowed": _bool_value(
                    interpretation.iloc[0]["paper_trading_workflow_preregistration_allowed"]
                ),
                "paper_trading_ready": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase14d_result_check": phase14d_check,
        "source_identity_report": source_identity,
        "metric_reconciliation_report": metric_reconciliation,
        "side_by_side_comparison_report": side_by_side,
        "current_signal_state_report": current_signal,
        "interpretation_decision_report": interpretation,
        "phase14f_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase14e_source_identity_{name}.csv", index=False)

    print("Wrote Phase 14E visual source identity reports.")
    return outputs


def _correction_spec_report(section: dict[str, Any], interpretation: pd.DataFrame) -> pd.DataFrame:
    policy = section.get("correction_policy", {})
    source_failed = _bool_value(interpretation.iloc[0].get("source_identity_failed", True))
    metric_failed = _bool_value(interpretation.iloc[0].get("metric_reconciliation_failed", True))

    correction_required = source_failed or metric_failed

    return pd.DataFrame(
        [
            {
                "correction_required": correction_required,
                "reason": interpretation.iloc[0].get("decision_reason", ""),
                "intended_candidate_system_id": policy.get("intended_candidate_system_id", ""),
                "required_corrected_source_fragments": "; ".join(
                    map(str, _as_list(policy.get("required_corrected_source_fragments")))
                ),
                "required_corrected_visual_reports": "; ".join(
                    map(str, _as_list(policy.get("corrected_visual_rerun_required_reports")))
                ),
                "rerun_execution_allowed_in_phase14f": False,
                "paper_workflow_preregistration_allowed": not correction_required,
            }
        ]
    )


def _workflow_prereg_requirement_report(section: dict[str, Any], interpretation: pd.DataFrame) -> pd.DataFrame:
    allowed = _bool_value(
        interpretation.iloc[0].get("paper_trading_workflow_preregistration_allowed", False)
    )
    policy = section.get("paper_workflow_prereg_policy", {})
    rows = []

    for item in _as_list(policy.get("required_future_workflow_reports")):
        rows.append(
            {
                "workflow_requirement": item,
                "registered_now": allowed,
                "deployment_allowed": False,
                "paper_trading_ready": False,
            }
        )

    return pd.DataFrame(rows)


def _phase14g_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    return _boundary_check(section, "phase14g_boundary")


def save_phase14f_candidate_source_correction_or_workflow_prereg_decision(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase14f_candidate_source_correction_or_workflow_prereg_decision")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    reports = section.get("source_reports", {})
    source_check = _source_report_check(reports)
    phase14e_check = _phase_result_check(
        reports["phase14e_conclusion"],
        reports["phase14e_gate_report"],
        "Phase 14E",
    )

    interpretation = _read_csv_if_exists(reports["phase14e_interpretation_decision_report"])
    source_identity = _read_csv_if_exists(reports["phase14e_source_identity_report"])
    metric_reconciliation = _read_csv_if_exists(reports["phase14e_metric_reconciliation_report"])

    if interpretation.empty:
        interpretation = pd.DataFrame(
            [
                {
                    "decision": "missing_phase14e_interpretation",
                    "decision_reason": "Phase 14E interpretation was missing.",
                    "source_identity_failed": True,
                    "metric_reconciliation_failed": True,
                    "paper_trading_workflow_preregistration_allowed": False,
                }
            ]
        )

    source_failed = _bool_value(interpretation.iloc[0].get("source_identity_failed", True))
    metric_failed = _bool_value(interpretation.iloc[0].get("metric_reconciliation_failed", True))
    workflow_allowed = _bool_value(
        interpretation.iloc[0].get("paper_trading_workflow_preregistration_allowed", False)
    )

    correction_spec = _correction_spec_report(section, interpretation)
    workflow_requirements = _workflow_prereg_requirement_report(section, interpretation)
    boundary = _phase14g_boundary_check(section)
    scope = _scope_check(section)

    if source_failed or metric_failed:
        decision = section.get("correction_policy", {}).get(
            "decision_if_source_identity_failed",
            "pre_register_candidate_source_correction_and_visual_rerun",
        )
        next_phase = "Phase 14G - Candidate source correction implementation and visual backtest re-run"
    else:
        decision = section.get("correction_policy", {}).get(
            "decision_if_all_identity_checks_pass",
            "pre_register_paper_trading_workflow_requirements",
        )
        next_phase = "Phase 14G - Paper-trading workflow pre-registration"

    decision_report = pd.DataFrame(
        [
            {
                "decision": decision,
                "next_phase": next_phase,
                "source_identity_failed": source_failed,
                "metric_reconciliation_failed": metric_failed,
                "paper_trading_workflow_preregistration_allowed": workflow_allowed and not source_failed and not metric_failed,
                "correction_required": source_failed or metric_failed,
                "visual_rerun_required": source_failed or metric_failed,
                "paper_trading_deployment_allowed": False,
                "paper_trading_ready": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    summary = pd.DataFrame(
        [
            {
                "decision_role": section.get("decision_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase14e_passed": bool(phase14e_check["passed"].all()),
                "config_flags_clean": bool(flags["passed"].all()),
                "source_reports_present": bool(source_check["present"].all()) if not source_check.empty else False,
                "source_identity_failed": source_failed,
                "metric_reconciliation_failed": metric_failed,
                "decision": decision,
                "correction_required": source_failed or metric_failed,
                "paper_workflow_preregistration_allowed": _bool_value(
                    decision_report.iloc[0]["paper_trading_workflow_preregistration_allowed"]
                ),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "live_trading": False,
                "real_money_deployment": False,
                "paper_trading_ready_claim": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    correction_spec_exists_if_needed = (
        len(correction_spec) == 1
        and _bool_value(correction_spec.iloc[0]["correction_required"]) == (source_failed or metric_failed)
    )
    no_workflow_if_failed = not (
        (source_failed or metric_failed)
        and _bool_value(decision_report.iloc[0]["paper_trading_workflow_preregistration_allowed"])
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 14E passed", bool(summary.iloc[0]["phase14e_passed"]), "phase14e"),
            _gate_row("Config flags clean", bool(summary.iloc[0]["config_flags_clean"]), "runtime flags"),
            _gate_row("Decision report exists", len(decision_report) == 1, decision),
            _gate_row("Correction spec exists if source failed", correction_spec_exists_if_needed, "correction spec"),
            _gate_row("No paper workflow if source failed", no_workflow_if_failed, "workflow blocked if failed"),
            _gate_row("Phase 14G boundary is conditional-only", bool(boundary["passed"].all()), "phase14g"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Decision role is correct",
                section.get("decision_role") == "Candidate source correction or paper-trading workflow pre-registration decision only",
                section.get("decision_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14F",
                "diagnostic": "Candidate source correction or workflow pre-registration decision",
                "verdict": (
                    "Completed — candidate source correction/workflow decision passed"
                    if bool(gate_report["passed"].all())
                    else "Failed candidate source correction/workflow decision"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "correction_required": source_failed or metric_failed,
                "paper_trading_workflow_preregistration_allowed": _bool_value(
                    decision_report.iloc[0]["paper_trading_workflow_preregistration_allowed"]
                ),
                "paper_trading_ready": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "config_flag_check": flags,
        "source_report_check": source_check,
        "phase14e_result_check": phase14e_check,
        "source_identity_input_check": source_identity,
        "metric_reconciliation_input_check": metric_reconciliation,
        "correction_spec_report": correction_spec,
        "paper_workflow_requirement_report": workflow_requirements,
        "decision_report": decision_report,
        "phase14g_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase14f_source_correction_{name}.csv", index=False)

    print("Wrote Phase 14F candidate source correction/workflow decision reports.")
    return outputs