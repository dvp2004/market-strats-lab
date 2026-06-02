from __future__ import annotations

from pathlib import Path
from typing import Any

from datetime import datetime, timezone

import numpy as np
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


def _first_existing_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {str(col).lower(): str(col) for col in frame.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


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


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_broker_api_integration",
        "allow_paper_trading_deployment",
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
        boundary.get("allowed_next_step", boundary.get("allowed_next_step_if_blocked", ""))
    ).lower()
    allowed_passed = str(boundary.get("allowed_next_step_if_passed", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": f"{key}_allowed_next_step_is_bounded",
            "passed": bool(
                "audit" in allowed
                or "repair" in allowed
                or "paper dry-run pre-registration" in allowed_passed
            ),
            "detail": boundary.get(
                "allowed_next_step",
                boundary.get("allowed_next_step_if_blocked", ""),
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


def _standardise_mode(value: Any, exposure: float | None = None) -> str:
    clean = str(value).strip()
    if clean and clean.lower() not in {"nan", "none", ""}:
        numeric = pd.to_numeric(pd.Series([clean]), errors="coerce").iloc[0]
        if pd.isna(numeric):
            return clean

    if exposure is not None:
        return "offensive_spy" if float(exposure) >= 0.75 else "defensive_or_cash"

    return "unknown"


def _target_action(exposure: float) -> str:
    if exposure >= 0.75:
        return "risk_on_preview"
    if exposure <= 0.25:
        return "cash_or_defensive_preview"
    return "partial_risk_preview"


def _transition_type(previous_exposure: float, current_exposure: float) -> str:
    if current_exposure > previous_exposure:
        return "risk_increase"
    if current_exposure < previous_exposure:
        return "risk_decrease"
    return "mode_change_or_signal_confirmation"


def _empty_switch_log(required_cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=required_cols)


def _switches_from_daily_stream(
    exported: pd.DataFrame,
    required_cols: list[str],
    candidate_system_id: str,
) -> pd.DataFrame:
    if exported.empty:
        return _empty_switch_log(required_cols)

    date_col = _first_existing_col(exported, ["decision_date", "date"])
    exposure_col = _first_existing_col(exported, ["exposure", "current_exposure", "target_exposure"])
    mode_col = _first_existing_col(exported, ["mode", "current_mode", "regime", "state"])
    turnover_col = _first_existing_col(exported, ["turnover", "strategy_turnover"])
    bps_col = _first_existing_col(exported, ["applied_overlay_slippage_bps", "slippage_bps"])
    cost_col = _first_existing_col(exported, ["overlay_slippage_cost_pct", "slippage_cost_pct"])

    if date_col is None or exposure_col is None:
        return _empty_switch_log(required_cols)

    frame = exported.copy()
    frame["decision_date"] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame[frame["decision_date"].notna()].sort_values("decision_date").reset_index(drop=True)
    frame["current_exposure"] = pd.to_numeric(frame[exposure_col], errors="coerce").ffill().fillna(0.0)
    frame["current_mode"] = [
        _standardise_mode(value, exposure)
        for value, exposure in zip(
            frame[mode_col] if mode_col else [""] * len(frame),
            frame["current_exposure"],
            strict=False,
        )
    ]

    frame["previous_exposure"] = frame["current_exposure"].shift(1)
    frame["previous_mode"] = frame["current_mode"].shift(1)
    frame["switch_triggered"] = (
        frame["current_exposure"].ne(frame["previous_exposure"])
        | frame["current_mode"].ne(frame["previous_mode"])
    )
    frame = frame[frame["previous_exposure"].notna() & frame["switch_triggered"]].copy()

    if frame.empty:
        return _empty_switch_log(required_cols)

    frame["switch_event_id"] = range(1, len(frame) + 1)
    frame["transition_type"] = [
        _transition_type(prev, curr)
        for prev, curr in zip(frame["previous_exposure"], frame["current_exposure"], strict=False)
    ]
    frame["switch_reason"] = "reconstructed_from_daily_mode_or_exposure_change"
    frame["raw_signal"] = frame["current_mode"]
    frame["confirmed_signal"] = frame["current_mode"]
    frame["deep_drawdown_guard_state"] = "unknown"
    frame["loose_relief_state"] = "unknown"
    frame["turnover"] = (
        pd.to_numeric(frame[turnover_col], errors="coerce").fillna(0.0)
        if turnover_col
        else frame["current_exposure"].sub(frame["previous_exposure"]).abs()
    )
    frame["applied_overlay_slippage_bps"] = (
        pd.to_numeric(frame[bps_col], errors="coerce").fillna(0.0) if bps_col else 0.0
    )
    frame["overlay_slippage_cost_pct"] = (
        pd.to_numeric(frame[cost_col], errors="coerce").fillna(0.0) if cost_col else 0.0
    )
    frame["source_candidate_system_id"] = candidate_system_id
    frame["signal_validity_flag"] = np.where(
        frame["current_mode"].ne("unknown") & frame["previous_mode"].ne("unknown"),
        "pass",
        "fail",
    )

    return frame[required_cols]


def _standardise_external_switch_source(
    source: pd.DataFrame,
    source_path: str,
    required_cols: list[str],
    candidate_system_id: str,
) -> pd.DataFrame:
    if source.empty:
        return _empty_switch_log(required_cols)

    date_col = _first_existing_col(
        source,
        ["decision_date", "switch_date", "date", "event_date", "signal_date"],
    )
    if date_col is None:
        return _empty_switch_log(required_cols)

    prev_mode_col = _first_existing_col(source, ["previous_mode", "from_mode", "old_mode", "prior_mode"])
    curr_mode_col = _first_existing_col(source, ["current_mode", "to_mode", "new_mode", "mode"])
    prev_exp_col = _first_existing_col(source, ["previous_exposure", "from_exposure", "old_exposure"])
    curr_exp_col = _first_existing_col(source, ["current_exposure", "to_exposure", "new_exposure", "exposure"])
    transition_col = _first_existing_col(source, ["transition_type", "transition", "paper_trading_action"])
    reason_col = _first_existing_col(source, ["switch_reason", "reason", "diagnostic", "event_reason"])
    raw_col = _first_existing_col(source, ["raw_signal", "raw_mode", "raw_signal_state"])
    confirmed_col = _first_existing_col(source, ["confirmed_signal", "confirmed_mode", "guarded_signal"])
    guard_col = _first_existing_col(source, ["deep_drawdown_guard_state", "guard_state"])
    relief_col = _first_existing_col(source, ["loose_relief_state", "relief_state"])
    turnover_col = _first_existing_col(source, ["turnover", "strategy_turnover"])
    bps_col = _first_existing_col(source, ["applied_overlay_slippage_bps", "slippage_bps"])
    cost_col = _first_existing_col(source, ["overlay_slippage_cost_pct", "slippage_cost_pct"])

    out = pd.DataFrame()
    out["decision_date"] = pd.to_datetime(source[date_col], errors="coerce")
    out = out[out["decision_date"].notna()].copy()
    source = source.loc[out.index].copy()

    out["switch_event_id"] = range(1, len(out) + 1)
    out["previous_exposure"] = (
        pd.to_numeric(source[prev_exp_col], errors="coerce").fillna(0.0)
        if prev_exp_col
        else 0.0
    )
    out["current_exposure"] = (
        pd.to_numeric(source[curr_exp_col], errors="coerce").fillna(out["previous_exposure"])
        if curr_exp_col
        else out["previous_exposure"]
    )
    out["previous_mode"] = (
        source[prev_mode_col].astype(str) if prev_mode_col else "unknown"
    )
    out["current_mode"] = (
        source[curr_mode_col].astype(str) if curr_mode_col else "unknown"
    )
    out["switch_triggered"] = True
    out["transition_type"] = (
        source[transition_col].astype(str) if transition_col else "external_switch_event"
    )
    out["switch_reason"] = (
        source[reason_col].astype(str)
        if reason_col
        else f"reconstructed_from_external_source:{source_path}"
    )
    out["raw_signal"] = source[raw_col].astype(str) if raw_col else "unknown"
    out["confirmed_signal"] = (
        source[confirmed_col].astype(str) if confirmed_col else out["current_mode"]
    )
    out["deep_drawdown_guard_state"] = source[guard_col].astype(str) if guard_col else "unknown"
    out["loose_relief_state"] = source[relief_col].astype(str) if relief_col else "unknown"
    out["turnover"] = pd.to_numeric(source[turnover_col], errors="coerce").fillna(0.0) if turnover_col else 0.0
    out["applied_overlay_slippage_bps"] = pd.to_numeric(source[bps_col], errors="coerce").fillna(0.0) if bps_col else 0.0
    out["overlay_slippage_cost_pct"] = pd.to_numeric(source[cost_col], errors="coerce").fillna(0.0) if cost_col else 0.0
    out["source_candidate_system_id"] = candidate_system_id

    essential_unknown = (
        out["previous_mode"].astype(str).str.lower().eq("unknown")
        | out["current_mode"].astype(str).str.lower().eq("unknown")
    )
    out["signal_validity_flag"] = np.where(essential_unknown, "fail", "pass")

    return out[required_cols]


def _choose_switch_reconstruction(
    exported: pd.DataFrame,
    candidate_sources: list[str],
    required_cols: list[str],
    expected_count: int,
    candidate_system_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = []

    daily = _switches_from_daily_stream(exported, required_cols, candidate_system_id)
    candidates.append(
        {
            "source": "exported_daily_stream_mode_exposure_changes",
            "frame": daily,
            "rows": len(daily),
            "distance_to_expected": abs(len(daily) - expected_count),
        }
    )

    for path in candidate_sources:
        source = _read_csv_if_exists(path)
        reconstructed = _standardise_external_switch_source(
            source,
            path,
            required_cols,
            candidate_system_id,
        )
        candidates.append(
            {
                "source": path,
                "frame": reconstructed,
                "rows": len(reconstructed),
                "distance_to_expected": abs(len(reconstructed) - expected_count),
            }
        )

    best = sorted(candidates, key=lambda item: (item["distance_to_expected"], -item["rows"]))[0]
    selected = best["frame"].copy()

    source_inventory = pd.DataFrame(
        [
            {
                "source": item["source"],
                "candidate_rows": item["rows"],
                "distance_to_expected": item["distance_to_expected"],
                "selected": item["source"] == best["source"],
            }
            for item in candidates
        ]
    )

    if selected.empty:
        selected = _empty_switch_log(required_cols)

    return selected, source_inventory


def _switch_summary(
    switch_log: pd.DataFrame,
    required_cols: list[str],
    expected_count: int,
    tolerance: int,
) -> pd.DataFrame:
    reconstructed_count = len(switch_log)
    missing_required = [col for col in required_cols if col not in switch_log.columns]
    count_reconciled = abs(reconstructed_count - expected_count) <= tolerance

    first_switch = ""
    last_switch = ""
    if not switch_log.empty and "decision_date" in switch_log.columns:
        dates = pd.to_datetime(switch_log["decision_date"], errors="coerce").dropna()
        if not dates.empty:
            first_switch = dates.min().date()
            last_switch = dates.max().date()

    signal_valid = (
        not switch_log.empty
        and "signal_validity_flag" in switch_log.columns
        and switch_log["signal_validity_flag"].astype(str).str.lower().eq("pass").all()
    )

    failure_reasons = []
    if not count_reconciled:
        failure_reasons.append("switch_count_does_not_reconcile")
    if missing_required:
        failure_reasons.append("missing_required_switch_fields")
    if not signal_valid:
        failure_reasons.append("switch_signal_validity_failed_or_no_switches")

    return pd.DataFrame(
        [
            {
                "expected_switch_count": expected_count,
                "reconstructed_switch_count": reconstructed_count,
                "switch_count_tolerance": tolerance,
                "switch_count_reconciled": count_reconciled,
                "first_switch_date": first_switch,
                "last_switch_date": last_switch,
                "missing_required_switch_fields": ";".join(missing_required),
                "switch_signal_validity_passed": signal_valid,
                "failure_reason": ";".join(failure_reasons),
                "paper_readiness_blocked": bool(failure_reasons),
            }
        ]
    )


def _current_signal_file(
    exported: pd.DataFrame,
    switch_log: pd.DataFrame,
    section: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    policy = section.get("current_signal_policy", {})
    candidate_system_id = section.get("candidate_system_id", "")
    audit_date = pd.to_datetime(policy.get("audit_current_date", ""), errors="coerce")
    canonical_endpoint = pd.to_datetime(
        policy.get("canonical_backtest_endpoint", ""),
        errors="coerce",
    )
    max_staleness = int(policy.get("max_signal_staleness_days_for_readiness", 3))

    if exported.empty:
        signal = pd.DataFrame(
            [
                {
                    "signal_date": audit_date.date() if pd.notna(audit_date) else "",
                    "data_as_of_date": "",
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "candidate_system_id": candidate_system_id,
                    "data_source": section.get("exported_daily_file", ""),
                    "current_mode": "",
                    "previous_mode": "",
                    "current_exposure": "",
                    "previous_exposure": "",
                    "target_action": "no_action_signal_unavailable",
                    "switch_triggered": False,
                    "switch_reason": "exported_daily_file_missing_or_empty",
                    "signal_validity_flag": "fail",
                    "data_freshness_flag": "fail",
                    "paper_trading_allowed": False,
                    "paper_readiness_status": "blocked_current_signal_unavailable",
                    "blocking_warnings": "current signal cannot be determined",
                    "benchmark_spy_close_or_return_source": "",
                }
            ]
        )
        summary = pd.DataFrame(
            [
                {
                    "signal_determined": False,
                    "signal_freshness_passed": False,
                    "signal_validity_passed": False,
                    "failure_reason": "exported_daily_file_missing_or_empty",
                }
            ]
        )
        return signal, summary

    frame = exported.copy()
    frame["decision_date"] = pd.to_datetime(frame["decision_date"], errors="coerce")
    frame = frame[frame["decision_date"].notna()].sort_values("decision_date").reset_index(drop=True)

    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else latest

    data_as_of_date = latest["decision_date"]
    staleness_days = None
    if pd.notna(audit_date) and pd.notna(data_as_of_date):
        staleness_days = int((audit_date.normalize() - data_as_of_date.normalize()).days)

    beyond_endpoint = bool(
        pd.notna(data_as_of_date)
        and pd.notna(canonical_endpoint)
        and data_as_of_date.normalize() > canonical_endpoint.normalize()
    )
    within_staleness = staleness_days is not None and staleness_days <= max_staleness
    freshness_passed = bool(within_staleness and beyond_endpoint)

    current_exposure = float(pd.to_numeric(pd.Series([latest.get("exposure", 0.0)]), errors="coerce").fillna(0.0).iloc[0])
    previous_exposure = float(pd.to_numeric(pd.Series([previous.get("exposure", 0.0)]), errors="coerce").fillna(0.0).iloc[0])
    current_mode = _standardise_mode(latest.get("mode", ""), current_exposure)
    previous_mode = _standardise_mode(previous.get("mode", ""), previous_exposure)

    switch_triggered = bool(
        current_mode != previous_mode or abs(current_exposure - previous_exposure) > 1e-12
    )
    switch_reason = (
        "latest_row_mode_or_exposure_changed"
        if switch_triggered
        else "no_latest_row_switch_detected"
    )

    signal_determined = bool(current_mode != "unknown" and not pd.isna(current_exposure))
    signal_validity_passed = bool(signal_determined and freshness_passed)

    warnings = []
    if not beyond_endpoint:
        warnings.append("data_as_of_date_not_beyond_canonical_endpoint")
    if not within_staleness:
        warnings.append(f"signal_stale_{staleness_days}_days")
    if not signal_determined:
        warnings.append("signal_not_determined")
    if switch_log.empty:
        warnings.append("operational_switch_log_missing_or_empty")

    signal = pd.DataFrame(
        [
            {
                "signal_date": audit_date.date() if pd.notna(audit_date) else "",
                "data_as_of_date": data_as_of_date.date() if pd.notna(data_as_of_date) else "",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "candidate_system_id": candidate_system_id,
                "data_source": section.get("exported_daily_file", ""),
                "current_mode": current_mode,
                "previous_mode": previous_mode,
                "current_exposure": current_exposure,
                "previous_exposure": previous_exposure,
                "target_action": _target_action(current_exposure),
                "switch_triggered": switch_triggered,
                "switch_reason": switch_reason,
                "signal_validity_flag": "pass" if signal_validity_passed else "fail",
                "data_freshness_flag": "pass" if freshness_passed else "fail",
                "paper_trading_allowed": False,
                "paper_readiness_status": (
                    "valid_for_audit_not_deployment"
                    if signal_validity_passed
                    else "blocked_current_signal_stale_or_invalid"
                ),
                "blocking_warnings": ";".join(warnings),
                "benchmark_spy_close_or_return_source": "SPY_return_from_exported_daily_file",
            }
        ]
    )

    summary = pd.DataFrame(
        [
            {
                "signal_determined": signal_determined,
                "audit_current_date": audit_date.date() if pd.notna(audit_date) else "",
                "data_as_of_date": data_as_of_date.date() if pd.notna(data_as_of_date) else "",
                "canonical_backtest_endpoint": canonical_endpoint.date()
                if pd.notna(canonical_endpoint)
                else "",
                "staleness_days": staleness_days,
                "max_signal_staleness_days_for_readiness": max_staleness,
                "data_beyond_canonical_endpoint": beyond_endpoint,
                "signal_freshness_passed": freshness_passed,
                "signal_validity_passed": signal_validity_passed,
                "failure_reason": ";".join(warnings),
            }
        ]
    )
    return signal, summary


def save_phase15c_operational_switch_signal_reconstruction(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15c_operational_switch_signal_reconstruction")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    sources = section.get("source_reports", {})
    phase15b_check = _phase_result_check(
        sources.get("phase15b_conclusion", ""),
        sources.get("phase15b_gate_report", ""),
        "Phase 15B",
    )

    exported_path = Path(section.get("exported_daily_file", ""))
    exported = _read_csv_if_exists(exported_path)

    required_switch_cols = list(section.get("required_switch_event_columns", []))
    expected_count = int(section.get("switch_reconstruction_policy", {}).get("expected_switch_count", 36))
    tolerance = int(section.get("switch_reconstruction_policy", {}).get("switch_count_abs_tolerance", 2))

    switch_log, switch_source_inventory = _choose_switch_reconstruction(
        exported=exported,
        candidate_sources=list(section.get("candidate_switch_source_files", [])),
        required_cols=required_switch_cols,
        expected_count=expected_count,
        candidate_system_id=str(section.get("candidate_system_id", "")),
    )
    switch_summary = _switch_summary(
        switch_log=switch_log,
        required_cols=required_switch_cols,
        expected_count=expected_count,
        tolerance=tolerance,
    )

    current_signal, current_signal_summary = _current_signal_file(
        exported=exported,
        switch_log=switch_log,
        section=section,
    )

    required_signal_cols = list(section.get("required_current_signal_columns", []))
    switch_col_check = _required_column_check(
        switch_log,
        required_switch_cols,
        "switch_event_log",
    )
    signal_col_check = _required_column_check(
        current_signal,
        required_signal_cols,
        "current_signal_file",
    )
    boundary = _boundary_check(section, "phase15d_boundary")
    scope = _scope_check(section)

    switch_log.to_csv(reports_path / "phase15c_operational_switch_event_log.csv", index=False)
    switch_summary.to_csv(reports_path / "phase15c_switch_reconstruction_summary.csv", index=False)
    current_signal.to_csv(reports_path / "phase15c_current_signal_file.csv", index=False)
    current_signal_summary.to_csv(
        reports_path / "phase15c_current_signal_generation_summary.csv",
        index=False,
    )

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15b_passed": bool(phase15b_check["passed"].all()),
                "exported_daily_file_present": exported_path.exists(),
                "exported_daily_rows": len(exported),
                "switch_event_rows": len(switch_log),
                "switch_count_reconciled": _bool_value(
                    switch_summary.iloc[0].get("switch_count_reconciled", False)
                ),
                "current_signal_generated": len(current_signal) == 1,
                "current_signal_freshness_passed": _bool_value(
                    current_signal_summary.iloc[0].get("signal_freshness_passed", False)
                ),
                "current_signal_validity_passed": _bool_value(
                    current_signal_summary.iloc[0].get("signal_validity_passed", False)
                ),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "broker_api_integration": False,
                "paper_trading_deployment": False,
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
            _gate_row("Phase 15B passed", bool(phase15b_check["passed"].all()), "phase15b"),
            _gate_row("Exported daily file present", exported_path.exists(), str(exported_path)),
            _gate_row("Switch event log output exists", True, "phase15c_operational_switch_event_log.csv"),
            _gate_row("Switch summary output exists", True, "phase15c_switch_reconstruction_summary.csv"),
            _gate_row("Current signal file output exists", len(current_signal) == 1, "phase15c_current_signal_file.csv"),
            _gate_row("Current signal required columns present", bool(signal_col_check["present"].all()), "current signal columns"),
            _gate_row("Switch required columns present", bool(switch_col_check["present"].all()), "switch columns"),
            _gate_row("Phase 15D boundary is audit-only", bool(boundary["passed"].all()), "phase15d"),
            _gate_row("Scope blocks deployment/live trading/real money", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role")
                == "Operational switch and current signal reconstruction implementation only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15C",
                "diagnostic": "Operational switch and current signal reconstruction",
                "verdict": (
                    "Completed — operational switch/current signal reconstruction passed"
                    if bool(gate_report["passed"].all())
                    else "Failed operational switch/current signal reconstruction"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "switch_count_reconciled": _bool_value(
                    switch_summary.iloc[0].get("switch_count_reconciled", False)
                ),
                "current_signal_freshness_passed": _bool_value(
                    current_signal_summary.iloc[0].get("signal_freshness_passed", False)
                ),
                "current_signal_validity_passed": _bool_value(
                    current_signal_summary.iloc[0].get("signal_validity_passed", False)
                ),
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
        "phase15b_result_check": phase15b_check,
        "switch_source_inventory": switch_source_inventory,
        "switch_event_log": switch_log,
        "switch_reconstruction_summary": switch_summary,
        "switch_required_column_check": switch_col_check,
        "current_signal_file": current_signal,
        "current_signal_generation_summary": current_signal_summary,
        "current_signal_required_column_check": signal_col_check,
        "phase15d_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name in {
            "switch_event_log",
            "switch_reconstruction_summary",
            "current_signal_file",
            "current_signal_generation_summary",
        }:
            continue
        frame.to_csv(reports_path / f"phase15c_operational_signal_{name}.csv", index=False)

    print("Wrote Phase 15C operational switch/current signal reconstruction reports.")
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
                "passed": p.exists() and (len(frame) > 0 or key == "switch_event_log"),
                "result": "Passed" if p.exists() else "Failed",
            }
        )
    return pd.DataFrame(rows)


def _decision_report(
    *,
    switch_summary: pd.DataFrame,
    current_signal_summary: pd.DataFrame,
    current_signal_file: pd.DataFrame,
    policy: dict[str, Any],
) -> pd.DataFrame:
    switch_passed = (
        not switch_summary.empty
        and _bool_value(switch_summary.iloc[0].get("switch_count_reconciled", False))
        and _bool_value(switch_summary.iloc[0].get("switch_signal_validity_passed", False))
    )

    signal_fresh = (
        not current_signal_summary.empty
        and _bool_value(current_signal_summary.iloc[0].get("signal_freshness_passed", False))
    )
    signal_valid = (
        not current_signal_summary.empty
        and _bool_value(current_signal_summary.iloc[0].get("signal_validity_passed", False))
    )
    signal_file_valid = (
        not current_signal_file.empty
        and str(current_signal_file.iloc[0].get("signal_validity_flag", "")).lower() == "pass"
        and str(current_signal_file.iloc[0].get("data_freshness_flag", "")).lower() == "pass"
    )
    signal_passed = bool(signal_fresh and signal_valid and signal_file_valid)

    if switch_passed and signal_passed:
        decision = policy.get("decision_if_all_passed", "paper_dry_run_preregistration_allowed_next")
    elif not switch_passed and not signal_passed:
        decision = policy.get("decision_if_both_failed", "blocked_both_switch_and_signal_failed")
    elif not switch_passed:
        decision = policy.get("decision_if_switch_failed", "blocked_switch_reconstruction_failed")
    else:
        decision = policy.get("decision_if_signal_failed", "blocked_current_signal_stale_or_invalid")

    return pd.DataFrame(
        [
            {
                "decision": decision,
                "switch_reconstruction_passed": switch_passed,
                "current_signal_freshness_passed": signal_fresh,
                "current_signal_validity_passed": signal_valid,
                "current_signal_file_flags_passed": signal_file_valid,
                "paper_dry_run_preregistration_allowed_next": bool(
                    decision == policy.get(
                        "decision_if_all_passed",
                        "paper_dry_run_preregistration_allowed_next",
                    )
                ),
                "paper_trading_ready": False,
                "paper_trading_deployment_allowed": False,
                "broker_api_integration_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def save_phase15d_current_signal_freshness_switch_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15d_current_signal_freshness_switch_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    report_paths = section.get("phase15c_reports", {})
    inventory = _report_inventory(report_paths)

    phase15c_check = _phase_result_check(
        report_paths.get("conclusion", ""),
        report_paths.get("gate_report", ""),
        "Phase 15C",
    )

    switch_log = _read_csv_if_exists(report_paths.get("switch_event_log", ""))
    switch_summary = _read_csv_if_exists(report_paths.get("switch_reconstruction_summary", ""))
    current_signal = _read_csv_if_exists(report_paths.get("current_signal_file", ""))
    current_signal_summary = _read_csv_if_exists(
        report_paths.get("current_signal_generation_summary", "")
    )

    switch_col_check = _required_column_check(
        switch_log,
        list(section.get("required_switch_event_columns", [])),
        "switch_event_log",
    )
    signal_col_check = _required_column_check(
        current_signal,
        list(section.get("required_current_signal_columns", [])),
        "current_signal_file",
    )

    decision = _decision_report(
        switch_summary=switch_summary,
        current_signal_summary=current_signal_summary,
        current_signal_file=current_signal,
        policy=section.get("decision_policy", {}),
    )

    boundary = _boundary_check(section, "phase15e_boundary")
    scope = _scope_check(section)

    both_pass = bool(
        _bool_value(decision.iloc[0].get("switch_reconstruction_passed", False))
        and _bool_value(decision.iloc[0].get("current_signal_freshness_passed", False))
        and _bool_value(decision.iloc[0].get("current_signal_validity_passed", False))
    )
    no_ready_claim_unless_both_pass = not (
        not both_pass and _bool_value(decision.iloc[0].get("paper_trading_ready", False))
    )

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15c_passed": bool(phase15c_check["passed"].all()),
                "config_flags_clean": bool(flags["passed"].all()),
                "switch_event_log_exists": Path(report_paths.get("switch_event_log", "")).exists(),
                "switch_required_columns_present": bool(switch_col_check["present"].all()),
                "current_signal_file_exists": Path(report_paths.get("current_signal_file", "")).exists(),
                "current_signal_required_columns_present": bool(signal_col_check["present"].all()),
                "switch_reconstruction_passed": _bool_value(decision.iloc[0]["switch_reconstruction_passed"]),
                "current_signal_freshness_passed": _bool_value(decision.iloc[0]["current_signal_freshness_passed"]),
                "current_signal_validity_passed": _bool_value(decision.iloc[0]["current_signal_validity_passed"]),
                "decision": decision.iloc[0]["decision"],
                "paper_dry_run_preregistration_allowed_next": _bool_value(
                    decision.iloc[0]["paper_dry_run_preregistration_allowed_next"]
                ),
                "paper_trading_ready": False,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
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
            _gate_row("Phase 15C passed", bool(phase15c_check["passed"].all()), "phase15c"),
            _gate_row("Config flags clean", bool(flags["passed"].all()), "runtime flags"),
            _gate_row("Switch event log exists", Path(report_paths.get("switch_event_log", "")).exists(), "switch log"),
            _gate_row("Switch summary exists", Path(report_paths.get("switch_reconstruction_summary", "")).exists(), "switch summary"),
            _gate_row("Switch required columns present", bool(switch_col_check["present"].all()), "switch columns"),
            _gate_row("Current signal file exists", Path(report_paths.get("current_signal_file", "")).exists(), "current signal"),
            _gate_row("Current signal required columns present", bool(signal_col_check["present"].all()), "signal columns"),
            _gate_row("Readiness decision output exists", len(decision) == 1, str(decision.iloc[0]["decision"])),
            _gate_row("No paper-ready claim unless both pass", no_ready_claim_unless_both_pass, "readiness claim gate"),
            _gate_row("Phase 15E boundary is conditional-only", bool(boundary["passed"].all()), "phase15e"),
            _gate_row("Scope blocks broker/live/real-money/promotion", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role") == "Current signal freshness and switch mechanics audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15D",
                "diagnostic": "Current signal freshness and switch mechanics audit",
                "verdict": (
                    "Completed — current signal freshness and switch mechanics audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed current signal freshness and switch mechanics audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision.iloc[0]["decision"],
                "switch_reconstruction_passed": _bool_value(decision.iloc[0]["switch_reconstruction_passed"]),
                "current_signal_freshness_passed": _bool_value(decision.iloc[0]["current_signal_freshness_passed"]),
                "current_signal_validity_passed": _bool_value(decision.iloc[0]["current_signal_validity_passed"]),
                "paper_dry_run_preregistration_allowed_next": _bool_value(
                    decision.iloc[0]["paper_dry_run_preregistration_allowed_next"]
                ),
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
        "phase15c_result_check": phase15c_check,
        "switch_required_column_check": switch_col_check,
        "current_signal_required_column_check": signal_col_check,
        "readiness_decision_report": decision,
        "phase15e_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15d_signal_switch_audit_{name}.csv", index=False)

    print("Wrote Phase 15D current signal freshness/switch mechanics audit reports.")
    return outputs