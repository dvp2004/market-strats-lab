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
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def _gate_row(gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _phase_result_check(conclusion_path: str, gate_path: str, phase_name: str) -> pd.DataFrame:
    conclusion = _read_csv_if_exists(conclusion_path)
    gate = _read_csv_if_exists(gate_path)

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
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


def _first_existing_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {str(col).lower(): str(col) for col in frame.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def _required_column_summary(frame: pd.DataFrame, required: list[str]) -> tuple[int, str]:
    missing = [col for col in required if col not in frame.columns]
    return len(missing), ";".join(missing)


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_switch_log_execution_patch",
        "allow_paper_dry_run_preregistration",
        "allow_broker_api_integration",
        "allow_paper_trading_deployment",
        "allow_live_trading",
        "allow_real_money_deployment",
        "allow_paper_trading_ready_claim",
        "allow_candidate_promotion",
        "allow_final_candidate_change",
        "allow_model_training",
        "allow_unregistered_ml",
        "allow_optimisation",
        "allow_multi_asset_expansion",
        "allow_feature_importance",
        "allow_data_pull_execution",
        "allow_current_signal_generation",
    ]

    rows = []
    for key in keys:
        if key in section:
            value = _bool_value(section.get(key, False))
            rows.append({"scope_item": key, "value": value, "passed": not value})

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _boundary_check(section: dict[str, Any], key: str) -> pd.DataFrame:
    boundary = section.get(key, {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": f"{key}_allowed_next_step_is_bounded",
            "passed": bool(
                "fresh data" in allowed
                or "current signal" in allowed
                or "spec" in allowed
                or "audit" in allowed
            ),
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": f"{key}_blocks_forbidden_actions",
            "passed": bool(
                "broker" in forbidden
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


def _daily_stream_switch_count(exported: pd.DataFrame) -> int:
    if exported.empty:
        return 0

    date_col = _first_existing_col(exported, ["decision_date", "date"])
    mode_col = _first_existing_col(exported, ["mode", "current_mode", "regime", "state"])
    exposure_col = _first_existing_col(exported, ["exposure", "current_exposure", "target_exposure"])

    if date_col is None or exposure_col is None:
        return 0

    frame = exported.copy()
    frame["decision_date"] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame[frame["decision_date"].notna()].sort_values("decision_date")
    exposure = pd.to_numeric(frame[exposure_col], errors="coerce").ffill().fillna(0.0)

    if mode_col:
        mode = frame[mode_col].astype(str)
    else:
        mode = exposure.map(lambda x: "offensive_spy" if x >= 0.75 else "defensive_or_cash")

    changed = exposure.ne(exposure.shift(1)) | mode.ne(mode.shift(1))
    return max(int(changed.sum()) - 1, 0)


def _classify_candidate_source(
    *,
    path: str,
    frame: pd.DataFrame,
    expected_count: int,
    tolerance: int,
    required_cols: list[str],
) -> dict[str, Any]:
    p = Path(path)
    name = str(path).lower()
    present = p.exists()
    rows = len(frame)

    missing_count, missing_cols = _required_column_summary(frame, required_cols)

    has_date = _first_existing_col(
        frame,
        ["decision_date", "switch_date", "date", "event_date", "signal_date"],
    ) is not None
    has_mode_context = (
        _first_existing_col(frame, ["previous_mode", "from_mode", "old_mode", "prior_mode"]) is not None
        and _first_existing_col(frame, ["current_mode", "to_mode", "new_mode", "mode"]) is not None
    )
    has_exposure_context = (
        _first_existing_col(frame, ["previous_exposure", "from_exposure", "old_exposure"]) is not None
        and _first_existing_col(frame, ["current_exposure", "to_exposure", "new_exposure", "exposure"]) is not None
    )

    count_reconciled = abs(rows - expected_count) <= tolerance
    is_empty = rows == 0
    is_summary = "summary" in name and rows <= 5
    is_changed_switch_audit = "changed_switch_audit" in name
    is_visual_switch_log = "corrected_visual_switch_event_log" in name or "operational_switch_event_log" in name

    if is_empty:
        classification = "empty_or_missing_not_final_switch_source"
    elif is_changed_switch_audit and not count_reconciled:
        classification = "intermediate_changed_switch_diagnostic_not_final_operational_log"
    elif is_summary:
        classification = "summary_file_not_final_switch_log"
    elif count_reconciled and has_date and (missing_count == 0 or (has_mode_context and has_exposure_context)):
        classification = "possible_final_36_switch_source"
    elif is_visual_switch_log and not count_reconciled:
        classification = "generated_visual_or_operational_log_but_count_not_reconciled"
    else:
        classification = "candidate_source_not_final_switch_log"

    selected_as_true_36_source = classification == "possible_final_36_switch_source"

    return {
        "source_path": path,
        "present": present,
        "rows": rows,
        "expected_switch_count": expected_count,
        "distance_to_expected": abs(rows - expected_count),
        "count_reconciled": count_reconciled,
        "has_date_field": has_date,
        "has_mode_context": has_mode_context,
        "has_exposure_context": has_exposure_context,
        "missing_required_column_count": missing_count,
        "missing_required_columns": missing_cols,
        "is_changed_switch_audit": is_changed_switch_audit,
        "is_summary_file": is_summary,
        "classification": classification,
        "selected_as_true_36_source": selected_as_true_36_source,
    }


def _source_attribution_inventory(section: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    expected_count = int(section.get("expected_final_switch_count", 36))
    tolerance = int(section.get("switch_count_abs_tolerance", 2))
    required_cols = list(section.get("required_final_switch_columns", []))

    rows = []

    exported_path = str(section.get("exported_daily_file", ""))
    exported = _read_csv_if_exists(exported_path)
    rows.append(
        {
            "source_path": exported_path,
            "present": Path(exported_path).exists(),
            "rows": len(exported),
            "expected_switch_count": expected_count,
            "distance_to_expected": abs(_daily_stream_switch_count(exported) - expected_count),
            "count_reconciled": abs(_daily_stream_switch_count(exported) - expected_count) <= tolerance,
            "has_date_field": _first_existing_col(exported, ["decision_date", "date"]) is not None,
            "has_mode_context": _first_existing_col(exported, ["mode", "current_mode", "regime"]) is not None,
            "has_exposure_context": _first_existing_col(exported, ["exposure", "current_exposure"]) is not None,
            "missing_required_column_count": "",
            "missing_required_columns": "",
            "is_changed_switch_audit": False,
            "is_summary_file": False,
            "classification": "financial_daily_stream_not_final_switch_log",
            "selected_as_true_36_source": False,
            "reconstructed_switch_count_from_daily": _daily_stream_switch_count(exported),
        }
    )

    for source in section.get("candidate_switch_source_files", []):
        frame = _read_csv_if_exists(source)
        row = _classify_candidate_source(
            path=source,
            frame=frame,
            expected_count=expected_count,
            tolerance=tolerance,
            required_cols=required_cols,
        )
        row["reconstructed_switch_count_from_daily"] = ""
        rows.append(row)

    inventory = pd.DataFrame(rows)
    selected = inventory[inventory["selected_as_true_36_source"].map(_bool_value)].copy()
    return inventory, selected


def _attribution_decision(
    *,
    inventory: pd.DataFrame,
    selected: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    changed_audit = inventory[inventory["is_changed_switch_audit"].map(_bool_value)]
    changed_audit_rows = int(changed_audit.iloc[0]["rows"]) if not changed_audit.empty else 0
    changed_audit_intermediate = bool(
        not changed_audit.empty
        and changed_audit.iloc[0]["classification"]
        == "intermediate_changed_switch_diagnostic_not_final_operational_log"
    )

    true_source_found = not selected.empty

    if true_source_found:
        decision = "true_36_switch_source_found"
        next_action = "export_or_reuse_true_36_switch_log_for_fresh_signal_repair"
        selected_source = str(selected.iloc[0]["source_path"])
    else:
        decision = "true_36_switch_source_not_found_patch_required"
        next_action = "patch_final_candidate_reconstruction_to_emit_true_operational_switch_log"
        selected_source = ""

    return pd.DataFrame(
        [
            {
                "decision": decision,
                "next_action": next_action,
                "true_36_switch_source_found": true_source_found,
                "selected_true_36_switch_source": selected_source,
                "changed_switch_audit_rows": changed_audit_rows,
                "changed_switch_audit_classified_as_intermediate": changed_audit_intermediate,
                "source_code_patch_required": not true_source_found,
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "broker_api_integration_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def _patch_spec(section: dict[str, Any], decision: pd.DataFrame) -> pd.DataFrame:
    policy = section.get("reconstruction_spec_policy", {})
    patch_required = _bool_value(decision.iloc[0].get("source_code_patch_required", True))

    rows = []
    for target in policy.get("preferred_patch_targets", []):
        rows.append(
            {
                "patch_required": patch_required,
                "patch_target": target,
                "required_future_export_file": policy.get("required_future_export_file", ""),
                "required_future_export_source": policy.get("required_future_export_source", ""),
                "must_export_final_not_intermediate_switches": _bool_value(
                    policy.get("require_final_not_intermediate_switches", True)
                ),
                "must_reconcile_to_expected_36_switches": _bool_value(
                    policy.get("require_reconciliation_to_expected_36_switches", True)
                ),
                "execution_allowed_in_phase15e": False,
            }
        )

    return pd.DataFrame(rows)


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


def save_phase15e_operational_switch_source_attribution(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15e_operational_switch_source_attribution")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = _source_report_check(section.get("source_reports", {}))
    phase15d_check = _phase_result_check(
        section.get("source_reports", {}).get("phase15d_conclusion", ""),
        section.get("source_reports", {}).get("phase15d_gate_report", ""),
        "Phase 15D",
    )

    inventory, selected = _source_attribution_inventory(section)
    decision = _attribution_decision(inventory=inventory, selected=selected, section=section)
    patch_spec = _patch_spec(section, decision)

    boundary = _boundary_check(section, "phase15f_boundary")
    scope = _scope_check(section)

    true_source_status = pd.DataFrame(
        [
            {
                "expected_final_switch_count": int(section.get("expected_final_switch_count", 36)),
                "switch_count_abs_tolerance": int(section.get("switch_count_abs_tolerance", 2)),
                "true_36_switch_source_found": _bool_value(decision.iloc[0]["true_36_switch_source_found"]),
                "source_code_patch_required": _bool_value(decision.iloc[0]["source_code_patch_required"]),
                "paper_readiness_blocked": True,
                "reason": decision.iloc[0]["decision"],
            }
        ]
    )

    summary = pd.DataFrame(
        [
            {
                "attribution_role": section.get("attribution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15d_passed": bool(phase15d_check["passed"].all()),
                "candidate_sources_checked": len(inventory),
                "true_36_switch_source_found": _bool_value(decision.iloc[0]["true_36_switch_source_found"]),
                "changed_switch_audit_classified_as_intermediate": _bool_value(
                    decision.iloc[0]["changed_switch_audit_classified_as_intermediate"]
                ),
                "source_code_patch_required": _bool_value(decision.iloc[0]["source_code_patch_required"]),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
                "paper_dry_run": False,
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
            _gate_row("Phase 15D passed", bool(phase15d_check["passed"].all()), "phase15d"),
            _gate_row("Candidate source inventory exists", len(inventory) > 0, f"rows={len(inventory)}"),
            _gate_row("Attribution decision exists", len(decision) == 1, str(decision.iloc[0]["decision"])),
            _gate_row("True 36-switch source status exists", len(true_source_status) == 1, "status"),
            _gate_row(
                "Changed switch audit classified",
                "changed_switch_audit_classified_as_intermediate" in decision.columns,
                "changed switch audit",
            ),
            _gate_row(
                "Patch spec exists if true source not found",
                (
                    _bool_value(decision.iloc[0]["true_36_switch_source_found"])
                    or len(patch_spec) > 0
                ),
                "patch spec",
            ),
            _gate_row("Phase 15F boundary is spec-only", bool(boundary["passed"].all()), "phase15f"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Attribution role is correct",
                section.get("attribution_role")
                == "Operational switch source attribution and true 36-switch reconstruction spec only",
                section.get("attribution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15E",
                "diagnostic": "Operational switch source attribution and true 36-switch reconstruction spec",
                "verdict": (
                    "Completed — operational switch source attribution passed"
                    if bool(gate_report["passed"].all())
                    else "Failed operational switch source attribution"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision.iloc[0]["decision"],
                "true_36_switch_source_found": _bool_value(decision.iloc[0]["true_36_switch_source_found"]),
                "source_code_patch_required": _bool_value(decision.iloc[0]["source_code_patch_required"]),
                "paper_trading_ready": False,
                "paper_dry_run": False,
                "broker_api_integration": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_reports,
        "phase15d_result_check": phase15d_check,
        "candidate_source_inventory": inventory,
        "true_36_switch_source_status": true_source_status,
        "attribution_decision": decision,
        "reconstruction_patch_spec": patch_spec,
        "phase15f_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15e_switch_source_attribution_{name}.csv", index=False)

    print("Wrote Phase 15E operational switch source attribution reports.")
    return outputs


def _policy_frame(policy: dict[str, Any], policy_name: str) -> pd.DataFrame:
    rows = []
    for key, value in policy.items():
        if isinstance(value, list):
            value = ";".join(map(str, value))
        rows.append({"policy": policy_name, "field": key, "value": value})
    return pd.DataFrame(rows)


def _schema_frame(columns: list[str], schema_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "schema_name": schema_name,
                "column_name": col,
                "required": True,
                "generated_in_phase15f": False,
            }
            for col in columns
        ]
    )


def save_phase15f_fresh_data_extension_preregistration(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15f_fresh_data_extension_preregistration")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = _source_report_check(section.get("source_reports", {}))
    phase15e_check = _phase_result_check(
        section.get("source_reports", {}).get("phase15e_conclusion", ""),
        section.get("source_reports", {}).get("phase15e_gate_report", ""),
        "Phase 15E",
    )

    baseline_protection = _policy_frame(
        section.get("baseline_protection_policy", {}),
        "baseline_protection_policy",
    )
    fresh_data_source = _policy_frame(
        section.get("fresh_data_source_policy", {}),
        "fresh_data_source_policy",
    )
    current_signal_policy = _policy_frame(
        section.get("current_signal_update_policy", {}),
        "current_signal_update_policy",
    )
    current_signal_schema = _schema_frame(
        list(section.get("required_current_signal_output_columns", [])),
        "phase15g_current_signal_file",
    )
    cadence_policy = _policy_frame(section.get("cadence_policy", {}), "cadence_policy")
    failure_policy = _policy_frame(
        section.get("failure_handling_policy", {}),
        "failure_handling_policy",
    )
    boundary = _boundary_check(section, "phase15g_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "preregistration_role": section.get("preregistration_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15e_passed": bool(phase15e_check["passed"].all()),
                "pinned_research_endpoint": section.get("pinned_research_endpoint", ""),
                "audit_current_date": section.get("audit_current_date", ""),
                "baseline_protection_rules": len(baseline_protection),
                "fresh_data_source_rules": len(fresh_data_source),
                "current_signal_policy_rules": len(current_signal_policy),
                "current_signal_schema_columns": len(current_signal_schema),
                "cadence_rules": len(cadence_policy),
                "failure_handling_rules": len(failure_policy),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
                "data_pull_execution": False,
                "current_signal_generation": False,
                "paper_dry_run": False,
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
            _gate_row("Phase 15E passed", bool(phase15e_check["passed"].all()), "phase15e"),
            _gate_row("Baseline protection policy exists", len(baseline_protection) > 0, f"rows={len(baseline_protection)}"),
            _gate_row("Fresh data source policy exists", len(fresh_data_source) > 0, f"rows={len(fresh_data_source)}"),
            _gate_row("Current signal update policy exists", len(current_signal_policy) > 0, f"rows={len(current_signal_policy)}"),
            _gate_row("Current signal output schema exists", len(current_signal_schema) > 0, f"columns={len(current_signal_schema)}"),
            _gate_row("Cadence policy exists", len(cadence_policy) > 0, f"rows={len(cadence_policy)}"),
            _gate_row("Failure handling policy exists", len(failure_policy) > 0, f"rows={len(failure_policy)}"),
            _gate_row("Phase 15G boundary is current-signal-only", bool(boundary["passed"].all()), "phase15g"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Preregistration role is correct",
                section.get("preregistration_role")
                == "Fresh data extension pre-registration and current signal update spec only",
                section.get("preregistration_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15F",
                "diagnostic": "Fresh data extension pre-registration and current signal update spec",
                "verdict": (
                    "Completed — fresh data extension pre-registration passed"
                    if bool(gate_report["passed"].all())
                    else "Failed fresh data extension pre-registration"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "current_signal_generation_allowed_next": True,
                "data_pull_executed": False,
                "paper_trading_ready": False,
                "paper_dry_run": False,
                "broker_api_integration": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_reports,
        "phase15e_result_check": phase15e_check,
        "baseline_protection_policy": baseline_protection,
        "fresh_data_source_policy": fresh_data_source,
        "current_signal_update_policy": current_signal_policy,
        "current_signal_output_schema": current_signal_schema,
        "cadence_policy": cadence_policy,
        "failure_handling_policy": failure_policy,
        "phase15g_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15f_fresh_data_extension_{name}.csv", index=False)

    print("Wrote Phase 15F fresh data extension pre-registration reports.")
    return outputs