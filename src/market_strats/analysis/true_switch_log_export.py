from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.bid_ask_market_impact_diagnostic import (
    _find_final_candidate_frame,
)


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


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_fresh_data_extension",
        "allow_current_signal_generation",
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
    allowed = str(
        boundary.get("allowed_next_step", boundary.get("allowed_next_step_if_reconciled", ""))
    ).lower()
    allowed_failed = str(boundary.get("allowed_next_step_if_failed", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": f"{key}_allowed_next_step_is_bounded",
            "passed": bool(
                "audit" in allowed
                or "fresh data" in allowed
                or "current signal" in allowed
                or "repair" in allowed_failed
            ),
            "detail": boundary.get(
                "allowed_next_step",
                boundary.get("allowed_next_step_if_reconciled", ""),
            ),
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


def _required_column_check(frame: pd.DataFrame, required: list[str], frame_name: str) -> pd.DataFrame:
    rows = []
    for col in required:
        rows.append(
            {
                "frame": frame_name,
                "required_column": col,
                "present": col in frame.columns,
                "result": "Passed" if col in frame.columns else "Failed",
            }
        )
    return pd.DataFrame(rows)


def _normalise_mode(value: Any, exposure: float | None = None) -> str:
    raw = str(value).strip()
    numeric = pd.to_numeric(pd.Series([raw]), errors="coerce").iloc[0]

    if pd.notna(numeric):
        if float(numeric) >= 0.75:
            return "offensive_spy"
        if float(numeric) <= 0.25:
            return "defensive_or_cash"
        return "partial_risk"

    if raw and raw.lower() not in {"nan", "none", "unknown", ""}:
        clean = raw.lower()
        if clean in {"1", "1.0", "true"}:
            return "offensive_spy"
        if clean in {"0", "0.0", "false"}:
            return "defensive_or_cash"
        return raw

    if exposure is not None:
        if exposure >= 0.75:
            return "offensive_spy"
        if exposure <= 0.25:
            return "defensive_or_cash"
        return "partial_risk"

    return "unknown"


def _exposure_from_mode(mode: pd.Series) -> pd.Series:
    text = mode.astype(str).str.lower()
    return pd.Series(
        np.where(
            text.str.contains("offensive|risk_on|spy|equity", regex=True),
            1.0,
            np.where(
                text.str.contains("defensive|cash|risk_off", regex=True),
                0.0,
                np.nan,
            ),
        ),
        index=mode.index,
    )


def _transition_type(previous_exposure: float, current_exposure: float) -> str:
    if current_exposure > previous_exposure:
        return "risk_increase"
    if current_exposure < previous_exposure:
        return "risk_decrease"
    return "mode_change_or_signal_confirmation"


def _select_columns(frame: pd.DataFrame, policy: dict[str, Any]) -> dict[str, str | None]:
    return {
        "date_col": _first_existing_col(frame, list(policy.get("date_columns", []))),
        "mode_col": _first_existing_col(frame, list(policy.get("mode_columns", []))),
        "exposure_col": _first_existing_col(frame, list(policy.get("exposure_columns", []))),
        "raw_signal_col": _first_existing_col(frame, list(policy.get("raw_signal_columns", []))),
        "confirmed_signal_col": _first_existing_col(frame, list(policy.get("confirmed_signal_columns", []))),
        "deep_drawdown_guard_col": _first_existing_col(frame, list(policy.get("deep_drawdown_guard_columns", []))),
        "loose_relief_col": _first_existing_col(frame, list(policy.get("loose_relief_columns", []))),
        "turnover_col": _first_existing_col(frame, list(policy.get("turnover_columns", []))),
        "slippage_bps_col": _first_existing_col(frame, list(policy.get("slippage_bps_columns", []))),
        "slippage_cost_col": _first_existing_col(frame, list(policy.get("slippage_cost_columns", []))),
    }


def _column_selection_report(frame: pd.DataFrame, selected: dict[str, str | None]) -> pd.DataFrame:
    rows = []
    for role, col in selected.items():
        rows.append(
            {
                "column_role": role,
                "selected_column": col or "",
                "selected": col is not None,
                "available_columns": ";".join(map(str, frame.columns)),
            }
        )
    return pd.DataFrame(rows)


def _empty_switch_log(required_columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=required_columns)


def _build_true_switch_log(
    *,
    final_candidate: pd.DataFrame,
    section: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_columns = list(section.get("required_switch_event_columns", []))
    policy = section.get("candidate_column_policy", {})
    selected = _select_columns(final_candidate, policy)
    column_report = _column_selection_report(final_candidate, selected)

    date_col = selected["date_col"]
    if date_col is None:
        return _empty_switch_log(required_columns), column_report

    canonical_endpoint = pd.to_datetime(section.get("canonical_endpoint", ""), errors="coerce")

    frame = final_candidate.copy()
    frame["decision_date"] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame[frame["decision_date"].notna()].copy()

    if pd.notna(canonical_endpoint):
        frame = frame[frame["decision_date"] <= canonical_endpoint].copy()

    frame = frame.sort_values("decision_date").drop_duplicates("decision_date").reset_index(drop=True)

    if frame.empty:
        return _empty_switch_log(required_columns), column_report

    exposure_col = selected["exposure_col"]
    mode_col = selected["mode_col"]

    if exposure_col:
        exposure = pd.to_numeric(frame[exposure_col], errors="coerce")
    elif mode_col:
        exposure = _exposure_from_mode(frame[mode_col])
    else:
        exposure = pd.Series(np.nan, index=frame.index)

    exposure = exposure.ffill().fillna(0.0)

    if mode_col:
        mode = pd.Series(
            [_normalise_mode(value, exp) for value, exp in zip(frame[mode_col], exposure, strict=False)],
            index=frame.index,
        )
    else:
        mode = pd.Series(
            [_normalise_mode("", exp) for exp in exposure],
            index=frame.index,
        )

    raw_signal_col = selected["raw_signal_col"]
    confirmed_signal_col = selected["confirmed_signal_col"]
    raw_signal = frame[raw_signal_col].astype(str) if raw_signal_col else mode
    confirmed_signal = frame[confirmed_signal_col].astype(str) if confirmed_signal_col else mode

    turnover_col = selected["turnover_col"]
    if turnover_col:
        turnover = pd.to_numeric(frame[turnover_col], errors="coerce").fillna(0.0)
    else:
        turnover = exposure.diff().abs().fillna(0.0)

    bps_col = selected["slippage_bps_col"]
    cost_col = selected["slippage_cost_col"]
    guard_col = selected["deep_drawdown_guard_col"]
    relief_col = selected["loose_relief_col"]

    previous_mode = mode.shift(1)
    previous_exposure = exposure.shift(1)
    switch_triggered = (
        mode.ne(previous_mode)
        | exposure.ne(previous_exposure)
        | (pd.to_numeric(turnover, errors="coerce").fillna(0.0) > 0)
    )

    events = frame[previous_exposure.notna() & switch_triggered].copy()
    event_index = events.index

    if events.empty:
        return _empty_switch_log(required_columns), column_report

    out = pd.DataFrame()
    out["switch_event_id"] = range(1, len(events) + 1)
    out["decision_date"] = events["decision_date"].dt.date
    out["previous_mode"] = previous_mode.loc[event_index].astype(str).to_numpy()
    out["current_mode"] = mode.loc[event_index].astype(str).to_numpy()
    out["previous_exposure"] = previous_exposure.loc[event_index].astype(float).to_numpy()
    out["current_exposure"] = exposure.loc[event_index].astype(float).to_numpy()
    out["switch_triggered"] = True
    out["transition_type"] = [
        _transition_type(prev, curr)
        for prev, curr in zip(out["previous_exposure"], out["current_exposure"], strict=False)
    ]
    out["switch_reason"] = "final_candidate_mode_exposure_or_turnover_change"
    out["raw_signal"] = raw_signal.loc[event_index].astype(str).to_numpy()
    out["confirmed_signal"] = confirmed_signal.loc[event_index].astype(str).to_numpy()
    out["deep_drawdown_guard_state"] = (
        frame.loc[event_index, guard_col].astype(str).to_numpy()
        if guard_col
        else "not_exported_from_final_candidate_frame"
    )
    out["loose_relief_state"] = (
        frame.loc[event_index, relief_col].astype(str).to_numpy()
        if relief_col
        else "not_exported_from_final_candidate_frame"
    )
    out["turnover"] = turnover.loc[event_index].astype(float).to_numpy()
    out["applied_overlay_slippage_bps"] = (
        pd.to_numeric(frame.loc[event_index, bps_col], errors="coerce").fillna(0.0).to_numpy()
        if bps_col
        else 0.0
    )
    out["overlay_slippage_cost_pct"] = (
        pd.to_numeric(frame.loc[event_index, cost_col], errors="coerce").fillna(0.0).to_numpy()
        if cost_col
        else 0.0
    )
    out["source_candidate_system_id"] = section.get("candidate_system_id", "")
    out["signal_validity_flag"] = np.where(
        out["previous_mode"].astype(str).str.lower().ne("unknown")
        & out["current_mode"].astype(str).str.lower().ne("unknown"),
        "pass",
        "fail",
    )

    return out[required_columns], column_report


def _switch_summary(
    switch_log: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    policy = section.get("switch_reconstruction_policy", {})
    expected_count = int(policy.get("expected_switch_count", 36))
    tolerance = int(policy.get("switch_count_abs_tolerance", 2))
    canonical_endpoint = pd.to_datetime(section.get("canonical_endpoint", ""), errors="coerce")

    count = len(switch_log)
    count_reconciled = abs(count - expected_count) <= tolerance

    first_switch = ""
    last_switch = ""
    dates_after_endpoint = 0
    if not switch_log.empty and "decision_date" in switch_log.columns:
        dates = pd.to_datetime(switch_log["decision_date"], errors="coerce").dropna()
        if not dates.empty:
            first_switch = dates.min().date()
            last_switch = dates.max().date()
            if pd.notna(canonical_endpoint):
                dates_after_endpoint = int((dates > canonical_endpoint).sum())

    signal_validity_passed = (
        not switch_log.empty
        and "signal_validity_flag" in switch_log.columns
        and switch_log["signal_validity_flag"].astype(str).str.lower().eq("pass").all()
    )

    transition_populated = (
        not switch_log.empty
        and "transition_type" in switch_log.columns
        and switch_log["transition_type"].astype(str).str.strip().ne("").all()
    )

    turnover_coherent = (
        "turnover" in switch_log.columns
        and pd.to_numeric(switch_log["turnover"], errors="coerce").fillna(0.0).ge(0.0).all()
    )
    slippage_coherent = (
        "applied_overlay_slippage_bps" in switch_log.columns
        and "overlay_slippage_cost_pct" in switch_log.columns
        and pd.to_numeric(switch_log["applied_overlay_slippage_bps"], errors="coerce").fillna(0.0).ge(0.0).all()
        and pd.to_numeric(switch_log["overlay_slippage_cost_pct"], errors="coerce").fillna(0.0).ge(0.0).all()
    )

    failure_reasons = []
    if not count_reconciled:
        failure_reasons.append("switch_count_not_reconciled")
    if not first_switch or not last_switch:
        failure_reasons.append("first_or_last_switch_date_missing")
    if dates_after_endpoint > 0:
        failure_reasons.append("switch_dates_after_canonical_endpoint")
    if not signal_validity_passed:
        failure_reasons.append("signal_validity_flags_failed")
    if not transition_populated:
        failure_reasons.append("transition_type_missing")
    if not turnover_coherent:
        failure_reasons.append("turnover_not_coherent")
    if not slippage_coherent:
        failure_reasons.append("slippage_not_coherent")

    return pd.DataFrame(
        [
            {
                "expected_switch_count": expected_count,
                "reconstructed_switch_count": count,
                "switch_count_tolerance": tolerance,
                "switch_count_reconciled": count_reconciled,
                "first_switch_date": first_switch,
                "last_switch_date": last_switch,
                "dates_after_canonical_endpoint": dates_after_endpoint,
                "signal_validity_passed": signal_validity_passed,
                "transition_types_populated": transition_populated,
                "turnover_fields_coherent": turnover_coherent,
                "slippage_fields_coherent": slippage_coherent,
                "fresh_signal_phase_allowed_next": bool(
                    count_reconciled
                    and dates_after_endpoint == 0
                    and signal_validity_passed
                    and transition_populated
                    and turnover_coherent
                    and slippage_coherent
                ),
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "failure_reason": ";".join(failure_reasons),
            }
        ]
    )


def _source_rejection_report() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source": "reports/regime_switch_overlay_offensive_relief_changed_switch_audit.csv",
                "accepted_as_final_switch_log": False,
                "reason": "94-row changed-switch audit is intermediate diagnostic and does not reconcile to expected final 36 switches",
            },
            {
                "source": "reports/phase6b_loose_relief_execution_realistic_overlay_daily.csv",
                "accepted_as_final_switch_log": False,
                "reason": "financial daily stream is not sufficient unless final operational mode/exposure/turnover switches reconcile to 36",
            },
        ]
    )


def save_phase15g_true_final_switch_log_export(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15g_true_final_switch_log_export")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    phase15f_check = _phase_result_check(
        source_reports.get("phase15f_conclusion", ""),
        source_reports.get("phase15f_gate_report", ""),
        "Phase 15F",
    )

    final_candidate = _find_final_candidate_frame(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    switch_log, column_selection = _build_true_switch_log(
        final_candidate=final_candidate,
        section=section,
    )
    switch_summary = _switch_summary(switch_log, section)

    output_file = Path(section.get("exported_switch_log_file", ""))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    switch_log.to_csv(output_file, index=False)

    required_cols = list(section.get("required_switch_event_columns", []))
    required_col_check = _required_column_check(switch_log, required_cols, "true_switch_log")

    source_rejection = _source_rejection_report()
    boundary = _boundary_check(section, "phase15h_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15f_passed": bool(phase15f_check["passed"].all()),
                "final_candidate_reconstruction_attempted": True,
                "final_candidate_rows": len(final_candidate),
                "switch_log_file": str(output_file),
                "switch_log_file_written": output_file.exists(),
                "switch_event_rows": len(switch_log),
                "switch_count_reconciled": _bool_value(switch_summary.iloc[0]["switch_count_reconciled"]),
                "fresh_signal_phase_allowed_next": _bool_value(
                    switch_summary.iloc[0]["fresh_signal_phase_allowed_next"]
                ),
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
                "fresh_data_extension": False,
                "current_signal_generation": False,
                "broker_api_integration": False,
                "paper_trading_deployment": False,
                "live_trading": False,
                "real_money_deployment": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 15F passed", bool(phase15f_check["passed"].all()), "phase15f"),
            _gate_row("Final candidate reconstruction attempted", True, "_find_final_candidate_frame"),
            _gate_row("Switch log file written", output_file.exists(), str(output_file)),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "required switch columns"),
            _gate_row("Switch summary output exists", len(switch_summary) == 1, "switch summary"),
            _gate_row(
                "No dates after canonical endpoint",
                int(switch_summary.iloc[0]["dates_after_canonical_endpoint"]) == 0,
                f"dates_after_endpoint={switch_summary.iloc[0]['dates_after_canonical_endpoint']}",
            ),
            _gate_row("Intermediate diagnostic sources rejected", True, "94-row changed-switch audit not accepted"),
            _gate_row("Phase 15H boundary is audit-only", bool(boundary["passed"].all()), "phase15h"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role")
                == "True final 36-switch operational log export implementation only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15G",
                "diagnostic": "True final 36-switch operational log export",
                "verdict": (
                    "Completed — true switch log export implementation passed"
                    if bool(gate_report["passed"].all())
                    else "Failed true switch log export implementation"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "switch_count_reconciled": _bool_value(switch_summary.iloc[0]["switch_count_reconciled"]),
                "fresh_signal_phase_allowed_next": _bool_value(
                    switch_summary.iloc[0]["fresh_signal_phase_allowed_next"]
                ),
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "broker_api_integration": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase15f_result_check": phase15f_check,
        "column_selection_report": column_selection,
        "source_rejection_report": source_rejection,
        "switch_log": switch_log,
        "switch_summary": switch_summary,
        "required_column_check": required_col_check,
        "phase15h_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "switch_log":
            continue
        frame.to_csv(reports_path / f"phase15g_true_switch_log_export_{name}.csv", index=False)

    print("Wrote Phase 15G true final switch log export reports.")
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
                "passed": p.exists() and (len(frame) > 0 or key == "switch_log"),
                "result": "Passed" if p.exists() else "Failed",
            }
        )
    return pd.DataFrame(rows)


def _decision_report(
    *,
    switch_summary: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    policy = section.get("decision_policy", {})
    reconciled = (
        not switch_summary.empty
        and _bool_value(switch_summary.iloc[0].get("fresh_signal_phase_allowed_next", False))
    )

    decision = (
        policy.get(
            "decision_if_reconciled",
            "canonical_switch_log_reconciled_fresh_signal_phase_allowed_next",
        )
        if reconciled
        else policy.get("decision_if_failed", "blocked_true_switch_log_export_failed")
    )

    return pd.DataFrame(
        [
            {
                "decision": decision,
                "switch_log_reconciled": reconciled,
                "fresh_signal_generation_allowed_next": reconciled,
                "paper_dry_run_preregistration_allowed": False,
                "paper_trading_ready": False,
                "broker_api_integration_allowed": False,
                "paper_trading_deployment_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def save_phase15h_switch_log_reconciliation_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15h_switch_log_reconciliation_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    report_paths = section.get("phase15g_reports", {})
    inventory = _report_inventory(report_paths)

    phase15g_check = _phase_result_check(
        report_paths.get("conclusion", ""),
        report_paths.get("gate_report", ""),
        "Phase 15G",
    )

    switch_log = _read_csv_if_exists(report_paths.get("switch_log", ""))
    switch_summary = _read_csv_if_exists(report_paths.get("switch_summary", ""))

    required_cols = list(section.get("required_switch_event_columns", []))
    required_col_check = _required_column_check(switch_log, required_cols, "true_switch_log")
    decision = _decision_report(switch_summary=switch_summary, section=section)

    boundary = _boundary_check(section, "phase15i_boundary")
    scope = _scope_check(section)

    no_ready_claim_unless_reconciled = not (
        not _bool_value(decision.iloc[0]["switch_log_reconciled"])
        and _bool_value(decision.iloc[0]["paper_trading_ready"])
    )

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15g_passed": bool(phase15g_check["passed"].all()),
                "config_flags_clean": bool(flags["passed"].all()),
                "switch_file_exists": Path(report_paths.get("switch_log", "")).exists(),
                "required_columns_present": bool(required_col_check["present"].all()),
                "switch_summary_exists": Path(report_paths.get("switch_summary", "")).exists(),
                "switch_log_reconciled": _bool_value(decision.iloc[0]["switch_log_reconciled"]),
                "fresh_signal_generation_allowed_next": _bool_value(
                    decision.iloc[0]["fresh_signal_generation_allowed_next"]
                ),
                "decision": decision.iloc[0]["decision"],
                "paper_dry_run_preregistration_allowed": False,
                "paper_trading_ready": False,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
                "broker_api_integration": False,
                "paper_trading_deployment": False,
                "live_trading": False,
                "real_money_deployment": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 15G passed", bool(phase15g_check["passed"].all()), "phase15g"),
            _gate_row("Config flags clean", bool(flags["passed"].all()), "runtime flags"),
            _gate_row("Switch file exists", Path(report_paths.get("switch_log", "")).exists(), "switch file"),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "required columns"),
            _gate_row("Switch summary exists", Path(report_paths.get("switch_summary", "")).exists(), "summary"),
            _gate_row("Reconciliation decision output exists", len(decision) == 1, str(decision.iloc[0]["decision"])),
            _gate_row(
                "No paper-ready claim unless reconciled",
                no_ready_claim_unless_reconciled,
                "readiness gate",
            ),
            _gate_row("Phase 15I boundary is conditional-only", bool(boundary["passed"].all()), "phase15i"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Switch log reconciliation and fresh signal eligibility audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15H",
                "diagnostic": "Switch log reconciliation and fresh signal eligibility audit",
                "verdict": (
                    "Completed — switch log reconciliation audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed switch log reconciliation audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision.iloc[0]["decision"],
                "switch_log_reconciled": _bool_value(decision.iloc[0]["switch_log_reconciled"]),
                "fresh_signal_generation_allowed_next": _bool_value(
                    decision.iloc[0]["fresh_signal_generation_allowed_next"]
                ),
                "paper_dry_run_preregistration_allowed": False,
                "paper_trading_ready": False,
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
        "phase15g_result_check": phase15g_check,
        "required_column_check": required_col_check,
        "reconciliation_decision_report": decision,
        "phase15i_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15h_switch_log_reconciliation_{name}.csv", index=False)

    print("Wrote Phase 15H switch log reconciliation audit reports.")
    return outputs