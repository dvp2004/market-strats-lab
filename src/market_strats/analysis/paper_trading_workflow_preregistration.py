from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()

    if clean in {"true", "1", "yes", "y"}:
        return True

    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False

    return bool(value)


def _section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return config.get(key, {}) or {}


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


def _phase_result_check(
    conclusion_path: str | Path,
    decision_path: str | Path | None,
    phase_name: str,
) -> pd.DataFrame:
    conclusion = _read_csv_if_exists(conclusion_path)
    decision = _read_csv_if_exists(decision_path) if decision_path else pd.DataFrame()

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )

    workflow_allowed = True
    if not decision.empty and "paper_workflow_preregistration_allowed" in decision.columns:
        workflow_allowed = _bool_value(
            decision.iloc[0].get("paper_workflow_preregistration_allowed", False)
        )

    out = pd.DataFrame(
        [
            {
                "check": f"{phase_name} conclusion passed",
                "passed": conclusion_passed,
                "detail": "conclusion",
            },
            {
                "check": f"{phase_name} allowed workflow preregistration",
                "passed": workflow_allowed,
                "detail": "paper_workflow_preregistration_allowed",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _source_report_check(paths: dict[str, str]) -> pd.DataFrame:
    rows = []

    for key, path in paths.items():
        p = Path(path)
        frame = _read_csv_if_exists(p)

        rows.append(
            {
                "report_key": key,
                "path": str(p),
                "present": p.exists(),
                "rows": len(frame),
                "passed": p.exists(),
                "result": "Passed" if p.exists() else "Failed",
            }
        )

    return pd.DataFrame(rows)


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_paper_trading_deployment",
        "allow_broker_api_integration",
        "allow_live_trading",
        "allow_real_money_deployment",
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


def _boundary_check(section: dict[str, Any], key: str) -> pd.DataFrame:
    boundary = section.get(key, {})
    allowed = str(
        boundary.get("allowed_next_step", boundary.get("allowed_next_step_if_not_ready", ""))
    ).lower()
    allowed_ready = str(boundary.get("allowed_next_step_if_ready", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": f"{key}_allowed_next_step_is_bounded",
            "passed": bool(
                "audit" in allowed
                or "reconstruction" in allowed
                or "repair" in allowed
                or "dry-run pre-registration" in allowed_ready
            ),
            "detail": boundary.get(
                "allowed_next_step",
                boundary.get("allowed_next_step_if_not_ready", ""),
            ),
        },
        {
            "check": f"{key}_blocks_forbidden_actions",
            "passed": bool(
                "paper-trading deployment" in forbidden
                and "live trading" in forbidden
                and "real-money" in forbidden
                and "candidate promotion" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _list_frame(items: list[str], column_name: str) -> pd.DataFrame:
    return pd.DataFrame([{column_name: item, "required": True} for item in items])


def _schema_frame(items: list[str], field_type: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "field_name": item,
                "field_type": field_type,
                "required": True,
                "paper_deployment_allowed": False,
            }
            for item in items
        ]
    )


def _endpoint_policy_frame(
    section: dict[str, Any],
    current_signal: pd.DataFrame,
) -> pd.DataFrame:
    policy = section.get("endpoint_policy", {})
    audit_date = pd.to_datetime(policy.get("audit_current_date", ""), errors="coerce")
    canonical_endpoint = pd.to_datetime(
        policy.get("canonical_backtest_endpoint", ""),
        errors="coerce",
    )

    latest_signal_date = pd.NaT
    if not current_signal.empty:
        latest_signal_date = pd.to_datetime(
            current_signal.iloc[0].get("latest_decision_date", ""),
            errors="coerce",
        )

    staleness_days = None
    signal_is_stale = True
    if pd.notna(audit_date) and pd.notna(latest_signal_date):
        staleness_days = int((audit_date.normalize() - latest_signal_date.normalize()).days)
        signal_is_stale = staleness_days > int(
            policy.get("max_signal_staleness_days_for_readiness", 3)
        )

    canonical_endpoint_issue = bool(
        pd.notna(latest_signal_date)
        and pd.notna(canonical_endpoint)
        and latest_signal_date.normalize() <= canonical_endpoint.normalize()
    )

    return pd.DataFrame(
        [
            {
                "audit_current_date": audit_date.date() if pd.notna(audit_date) else "",
                "canonical_backtest_endpoint": canonical_endpoint.date()
                if pd.notna(canonical_endpoint)
                else "",
                "latest_signal_date": latest_signal_date.date()
                if pd.notna(latest_signal_date)
                else "",
                "signal_staleness_days": staleness_days,
                "max_signal_staleness_days_for_readiness": policy.get(
                    "max_signal_staleness_days_for_readiness",
                    3,
                ),
                "signal_is_stale_for_readiness": signal_is_stale,
                "canonical_endpoint_issue": canonical_endpoint_issue,
                "blocks_paper_trading_readiness": bool(
                    signal_is_stale
                    or (
                        canonical_endpoint_issue
                        and _bool_value(policy.get("block_readiness_if_latest_signal_is_not_current", True))
                    )
                ),
                "warning": (
                    "Latest signal is from the canonical backtest endpoint, not a current/live data update."
                    if canonical_endpoint_issue
                    else ""
                ),
            }
        ]
    )


def _operational_switch_policy_frame(section: dict[str, Any]) -> pd.DataFrame:
    policy = section.get("operational_switch_policy", {})
    expected = int(policy.get("expected_canonical_switch_count", 36))
    observed = int(policy.get("exported_switch_count_observed", 0))
    switch_mismatch = expected != observed

    return pd.DataFrame(
        [
            {
                "expected_canonical_switch_count": expected,
                "exported_switch_count_observed": observed,
                "switch_count_reconciled": not switch_mismatch,
                "require_switch_reconstruction_before_readiness": _bool_value(
                    policy.get("require_switch_reconstruction_before_readiness", True)
                ),
                "require_switch_event_log_before_readiness": _bool_value(
                    policy.get("require_switch_event_log_before_readiness", True)
                ),
                "require_explainable_trade_segments_before_readiness": _bool_value(
                    policy.get("require_explainable_trade_segments_before_readiness", True)
                ),
                "failure_if_switch_mechanics_unresolved": _bool_value(
                    policy.get("failure_if_switch_mechanics_unresolved", True)
                ),
                "blocks_paper_trading_readiness": bool(
                    switch_mismatch
                    and _bool_value(policy.get("failure_if_switch_mechanics_unresolved", True))
                ),
                "warning": (
                    "Financial stream reconciles, but operational switch mechanics are not reconstructed."
                    if switch_mismatch
                    else ""
                ),
            }
        ]
    )


def _failure_conditions_frame(
    endpoint: pd.DataFrame,
    switches: pd.DataFrame,
) -> pd.DataFrame:
    rows = [
        {
            "failure_condition": "operational_switch_mechanics_unresolved",
            "triggered_now": _bool_value(
                switches.iloc[0].get("blocks_paper_trading_readiness", True)
            ),
            "blocks_readiness": True,
            "required_repair": "reconstruct/validate expected operational switches before paper trading",
        },
        {
            "failure_condition": "latest_signal_not_current",
            "triggered_now": _bool_value(
                endpoint.iloc[0].get("blocks_paper_trading_readiness", True)
            ),
            "blocks_readiness": True,
            "required_repair": "generate current signal from fresh data, not only canonical endpoint",
        },
        {
            "failure_condition": "signal_preview_only",
            "triggered_now": True,
            "blocks_readiness": True,
            "required_repair": "create audited paper signal file after workflow readiness passes",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["triggered_now"].map({True: "Blocking", False: "Clear"})
    return out


def save_phase15a_paper_trading_workflow_preregistration(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15a_paper_trading_workflow_preregistration")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase14h_check = _phase_result_check(
        section.get("corrected_visual_conclusion", ""),
        section.get("corrected_visual_decision_report", ""),
        "Phase 14H",
    )

    current_signal = _read_csv_if_exists(section.get("corrected_current_signal_report", ""))
    endpoint_policy = _endpoint_policy_frame(section, current_signal)
    switch_policy = _operational_switch_policy_frame(section)
    failure_conditions = _failure_conditions_frame(endpoint_policy, switch_policy)

    daily_signal_schema = _schema_frame(
        list(section.get("daily_signal_file_schema", {}).get("required_fields", [])),
        "daily_signal_file_field",
    )
    current_signal_schema = _schema_frame(
        list(section.get("current_signal_state_fields", {}).get("required_fields", [])),
        "current_signal_state_field",
    )
    manual_broker_template = _schema_frame(
        list(section.get("manual_paper_broker_entry_template", {}).get("required_fields", [])),
        "manual_paper_broker_field",
    )
    monitoring_dashboard = _list_frame(
        list(section.get("monitoring_dashboard_schema", {}).get("required_panels", [])),
        "dashboard_panel",
    )
    execution_checklist = _list_frame(
        list(section.get("execution_checklist", {}).get("required_checks", [])),
        "checklist_item",
    )
    journal_template = _schema_frame(
        list(section.get("paper_trading_journal_template", {}).get("required_fields", [])),
        "journal_field",
    )
    stop_conditions = _list_frame(
        list(section.get("stop_conditions", {}).get("required_conditions", [])),
        "stop_condition",
    )
    benchmark_rules = _list_frame(
        list(section.get("benchmark_update_rules", {}).get("required_rules", [])),
        "benchmark_update_rule",
    )

    source_reports = _source_report_check(
        {
            "exported_daily_file": section.get("exported_daily_file", ""),
            "corrected_current_signal_report": section.get("corrected_current_signal_report", ""),
            "corrected_visual_conclusion": section.get("corrected_visual_conclusion", ""),
            "corrected_visual_decision_report": section.get("corrected_visual_decision_report", ""),
        }
    )
    boundary = _boundary_check(section, "phase15b_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "preregistration_role": section.get("preregistration_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "candidate_system_id": section.get("candidate_system_id", ""),
                "phase14h_allows_workflow_preregistration": bool(phase14h_check["passed"].all()),
                "daily_signal_schema_fields": len(daily_signal_schema),
                "current_signal_schema_fields": len(current_signal_schema),
                "switch_reconstruction_required": _bool_value(
                    switch_policy.iloc[0].get("require_switch_reconstruction_before_readiness", True)
                ),
                "switch_mechanics_block_readiness": _bool_value(
                    switch_policy.iloc[0].get("blocks_paper_trading_readiness", True)
                ),
                "endpoint_blocks_readiness": _bool_value(
                    endpoint_policy.iloc[0].get("blocks_paper_trading_readiness", True)
                ),
                "failure_conditions_registered": len(failure_conditions),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "paper_trading_deployment": False,
                "broker_api_integration": False,
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
            _gate_row("Phase 14H allows workflow pre-registration", bool(phase14h_check["passed"].all()), "phase14h"),
            _gate_row("Daily signal file schema exists", len(daily_signal_schema) > 0, f"fields={len(daily_signal_schema)}"),
            _gate_row("Current signal state fields exist", len(current_signal_schema) > 0, f"fields={len(current_signal_schema)}"),
            _gate_row("Operational switch policy exists", len(switch_policy) == 1, "switch policy"),
            _gate_row("Endpoint freshness policy exists", len(endpoint_policy) == 1, "endpoint policy"),
            _gate_row("Manual paper broker template exists", len(manual_broker_template) > 0, f"fields={len(manual_broker_template)}"),
            _gate_row("Monitoring dashboard schema exists", len(monitoring_dashboard) > 0, f"panels={len(monitoring_dashboard)}"),
            _gate_row("Execution checklist exists", len(execution_checklist) > 0, f"checks={len(execution_checklist)}"),
            _gate_row("Journal template exists", len(journal_template) > 0, f"fields={len(journal_template)}"),
            _gate_row("Stop conditions exist", len(stop_conditions) > 0, f"conditions={len(stop_conditions)}"),
            _gate_row("Benchmark update rules exist", len(benchmark_rules) > 0, f"rules={len(benchmark_rules)}"),
            _gate_row("Phase 15B boundary is readiness-audit-only", bool(boundary["passed"].all()), "phase15b"),
            _gate_row("Scope blocks deployment/live trading/readiness claim", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Preregistration role is correct",
                section.get("preregistration_role") == "Paper-trading workflow pre-registration only",
                section.get("preregistration_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15A",
                "diagnostic": "Paper-trading workflow pre-registration",
                "verdict": (
                    "Completed — paper-trading workflow pre-registration passed"
                    if bool(gate_report["passed"].all())
                    else "Failed paper-trading workflow pre-registration"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "paper_trading_workflow_preregistered": bool(gate_report["passed"].all()),
                "paper_trading_ready": False,
                "paper_trading_deployment": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_reports,
        "phase14h_result_check": phase14h_check,
        "daily_signal_file_schema": daily_signal_schema,
        "current_signal_state_schema": current_signal_schema,
        "operational_switch_policy": switch_policy,
        "endpoint_freshness_policy": endpoint_policy,
        "manual_paper_broker_entry_template": manual_broker_template,
        "monitoring_dashboard_schema": monitoring_dashboard,
        "execution_checklist": execution_checklist,
        "paper_trading_journal_template": journal_template,
        "stop_conditions": stop_conditions,
        "benchmark_update_rules": benchmark_rules,
        "failure_conditions": failure_conditions,
        "phase15b_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15a_paper_workflow_{name}.csv", index=False)

    print("Wrote Phase 15A paper-trading workflow pre-registration reports.")
    return outputs


def _report_inventory(paths: dict[str, str]) -> pd.DataFrame:
    rows = []

    for key, path in paths.items():
        p = Path(path)
        frame = _read_csv_if_exists(p)

        rows.append(
            {
                "report_key": key,
                "path": str(p),
                "present": p.exists(),
                "rows": len(frame),
                "passed": p.exists() and len(frame) > 0,
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _readiness_decision(
    *,
    switch_policy: pd.DataFrame,
    endpoint_policy: pd.DataFrame,
    failure_conditions: pd.DataFrame,
    readiness_policy: dict[str, Any],
) -> pd.DataFrame:
    switch_ready = not _bool_value(
        switch_policy.iloc[0].get("blocks_paper_trading_readiness", True)
    )
    endpoint_ready = not _bool_value(
        endpoint_policy.iloc[0].get("blocks_paper_trading_readiness", True)
    )
    no_failure_conditions_triggered = not failure_conditions["triggered_now"].map(_bool_value).any()

    paper_trading_ready = bool(
        switch_ready
        and endpoint_ready
        and no_failure_conditions_triggered
        and not _bool_value(readiness_policy.get("block_readiness_if_any_required_condition_fails", True))
    )

    # If strict policy is enabled, readiness is only true when all required conditions clear.
    if _bool_value(readiness_policy.get("block_readiness_if_any_required_condition_fails", True)):
        paper_trading_ready = bool(
            switch_ready and endpoint_ready and no_failure_conditions_triggered
        )

    decision = (
        "paper_trading_dry_run_preregistration_allowed_next"
        if paper_trading_ready
        else "paper_trading_readiness_blocked_operational_repairs_required"
    )

    blockers = []
    if not switch_ready:
        blockers.append("operational_switch_mechanics_unresolved")
    if not endpoint_ready:
        blockers.append("latest_signal_not_current_or_endpoint_stale")
    if not no_failure_conditions_triggered:
        blockers.append("registered_failure_conditions_triggered")

    return pd.DataFrame(
        [
            {
                "decision": decision,
                "paper_trading_ready": paper_trading_ready,
                "paper_trading_deployment_allowed": False,
                "broker_api_integration_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "switch_mechanics_ready": switch_ready,
                "endpoint_freshness_ready": endpoint_ready,
                "failure_conditions_clear": no_failure_conditions_triggered,
                "blocking_reasons": "; ".join(blockers),
            }
        ]
    )


def save_phase15b_paper_trading_workflow_readiness_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15b_paper_trading_workflow_readiness_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    inventory = _report_inventory(section.get("phase15a_reports", {}))
    phase15a_check = _phase_result_check(
        section.get("phase15a_reports", {}).get("conclusion", ""),
        None,
        "Phase 15A",
    )

    switch_policy = _read_csv_if_exists(
        section.get("phase15a_reports", {}).get("operational_switch_policy", "")
    )
    endpoint_policy = _read_csv_if_exists(
        section.get("phase15a_reports", {}).get("endpoint_freshness_policy", "")
    )
    failure_conditions = _read_csv_if_exists(
        section.get("phase15a_reports", {}).get("failure_conditions", "")
    )

    readiness = _readiness_decision(
        switch_policy=switch_policy,
        endpoint_policy=endpoint_policy,
        failure_conditions=failure_conditions,
        readiness_policy=section.get("readiness_policy", {}),
    )
    boundary = _boundary_check(section, "phase15c_boundary")
    scope = _scope_check(section)

    operational_blockers = pd.DataFrame(
        [
            {
                "blocker": "operational_switch_mechanics_unresolved",
                "present": not _bool_value(readiness.iloc[0]["switch_mechanics_ready"]),
                "blocks_readiness": True,
            },
            {
                "blocker": "endpoint_signal_not_current",
                "present": not _bool_value(readiness.iloc[0]["endpoint_freshness_ready"]),
                "blocks_readiness": True,
            },
            {
                "blocker": "failure_conditions_triggered",
                "present": not _bool_value(readiness.iloc[0]["failure_conditions_clear"]),
                "blocks_readiness": True,
            },
        ]
    )
    operational_blockers["result"] = operational_blockers["present"].map(
        {True: "Blocking", False: "Clear"}
    )

    readiness_false_when_blockers_exist = not (
        operational_blockers["present"].map(_bool_value).any()
        and _bool_value(readiness.iloc[0]["paper_trading_ready"])
    )

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15a_passed": bool(phase15a_check["passed"].iloc[0]),
                "config_flags_clean": bool(flags["passed"].all()),
                "workflow_reports_present": bool(inventory["present"].all()) if not inventory.empty else False,
                "workflow_report_rows_non_empty": bool(inventory["passed"].all()) if not inventory.empty else False,
                "operational_blockers_present": bool(operational_blockers["present"].map(_bool_value).any()),
                "paper_trading_ready": _bool_value(readiness.iloc[0]["paper_trading_ready"]),
                "readiness_decision": readiness.iloc[0]["decision"],
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "paper_trading_deployment": False,
                "broker_api_integration": False,
                "live_trading": False,
                "real_money_deployment": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 15A passed", bool(phase15a_check["passed"].iloc[0]), "phase15a"),
            _gate_row("Config flags clean", bool(flags["passed"].all()), "runtime flags"),
            _gate_row("All workflow reports present", bool(inventory["present"].all()) if not inventory.empty else False, "inventory"),
            _gate_row("Operational blockers identified", bool(operational_blockers["present"].map(_bool_value).any()), "blockers"),
            _gate_row("Readiness decision report exists", len(readiness) == 1, str(readiness.iloc[0]["decision"])),
            _gate_row("Readiness false when blockers exist", readiness_false_when_blockers_exist, "readiness gate"),
            _gate_row("Phase 15C boundary is conditional-only", bool(boundary["passed"].all()), "phase15c"),
            _gate_row("Scope blocks deployment/live trading/promotion", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role") == "Paper-trading workflow readiness audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15B",
                "diagnostic": "Paper-trading workflow readiness audit",
                "verdict": (
                    "Completed — paper-trading workflow readiness audit passed with readiness blocked"
                    if bool(gate_report["passed"].all())
                    else "Failed paper-trading workflow readiness audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "paper_trading_ready": _bool_value(readiness.iloc[0]["paper_trading_ready"]),
                "paper_trading_deployment": False,
                "broker_api_integration": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "config_flag_check": flags,
        "report_inventory_check": inventory,
        "phase15a_result_check": phase15a_check,
        "operational_blocker_report": operational_blockers,
        "readiness_decision_report": readiness,
        "phase15c_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15b_paper_workflow_readiness_{name}.csv", index=False)

    print("Wrote Phase 15B paper-trading workflow readiness audit reports.")
    return outputs