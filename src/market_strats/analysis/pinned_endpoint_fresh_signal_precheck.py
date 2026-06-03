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


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_fresh_data_extension",
        "allow_current_signal_generation",
        "allow_fresh_data_pull_execution",
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
        if key not in section:
            continue

        value = _bool_value(section.get(key, False))
        allowed_exception = key in {
            "allow_endpoint_consistency_audit",
            "allow_fresh_signal_preimplementation_check",
        }
        rows.append(
            {
                "scope_item": key,
                "value": value,
                "passed": (not value) or allowed_exception,
            }
        )

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
                or "pre-implementation" in allowed
                or "signal generation" in allowed
            ),
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": f"{key}_blocks_forbidden_actions",
            "passed": bool(
                "paper dry-run" in forbidden
                and "broker" in forbidden
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


def _mode_from_exposure(exposure: float) -> str:
    if exposure >= 0.75:
        return "offensive_spy"
    if exposure <= 0.25:
        return "defensive_or_cash"
    return "partial_risk"


def _target_action(mode: str) -> str:
    if mode == "offensive_spy":
        return "risk_on_preview"
    if mode == "defensive_or_cash":
        return "risk_off_preview"
    return "partial_risk_preview"


def _endpoint_daily_state(
    *,
    daily_stream: pd.DataFrame,
    endpoint: pd.Timestamp,
) -> tuple[str, float]:
    if daily_stream.empty or "decision_date" not in daily_stream.columns:
        return "", float("nan")

    frame = daily_stream.copy()
    frame["decision_date"] = pd.to_datetime(frame["decision_date"], errors="coerce")
    frame = frame[frame["decision_date"].notna()]
    frame = frame[frame["decision_date"] <= endpoint].sort_values("decision_date")

    if frame.empty:
        return "", float("nan")

    row = frame.iloc[-1]

    exposure = pd.to_numeric(pd.Series([row.get("exposure", "")]), errors="coerce").iloc[0]
    if pd.isna(exposure):
        exposure = pd.to_numeric(pd.Series([row.get("target_offensive_weight", "")]), errors="coerce").iloc[0]

    if pd.isna(exposure):
        return "", float("nan")

    mode = str(row.get("mode", "")).strip()
    if not mode or mode.lower() in {"nan", "none", "unknown", "1.0", "0.0"}:
        mode = _mode_from_exposure(float(exposure))

    return mode, float(exposure)


def _latest_switch_before_endpoint(
    *,
    switch_log: pd.DataFrame,
    endpoint: pd.Timestamp,
) -> pd.Series | None:
    if switch_log.empty or "decision_date" not in switch_log.columns:
        return None

    frame = switch_log.copy()
    frame["decision_date"] = pd.to_datetime(frame["decision_date"], errors="coerce")
    frame = frame[frame["decision_date"].notna()]
    frame = frame[frame["decision_date"] <= endpoint].sort_values("decision_date")

    if frame.empty:
        return None

    return frame.iloc[-1]


def save_phase15k_pinned_endpoint_signal_consistency_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15k_pinned_endpoint_signal_consistency_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    sources = section.get("source_reports", {})
    source_check = _source_report_check(sources)
    phase15j_check = _phase_result_check(
        sources.get("phase15j_conclusion", ""),
        sources.get("phase15j_gate_report", ""),
        "Phase 15J",
    )

    switch_log = _read_csv_if_exists(sources.get("switch_log", ""))
    daily_stream = _read_csv_if_exists(sources.get("exported_daily_stream", ""))

    endpoint = pd.to_datetime(section.get("canonical_endpoint", ""), errors="coerce")
    latest_switch = _latest_switch_before_endpoint(switch_log=switch_log, endpoint=endpoint)

    if latest_switch is None:
        latest_switch_date = ""
        previous_mode = ""
        current_mode = ""
        previous_exposure = float("nan")
        current_exposure = float("nan")
    else:
        latest_switch_date = pd.to_datetime(latest_switch["decision_date"]).strftime("%Y-%m-%d")
        previous_mode = str(latest_switch.get("previous_mode", ""))
        current_mode = str(latest_switch.get("current_mode", ""))
        previous_exposure = float(latest_switch.get("previous_exposure", float("nan")))
        current_exposure = float(latest_switch.get("current_exposure", float("nan")))

    daily_mode, daily_exposure = _endpoint_daily_state(
        daily_stream=daily_stream,
        endpoint=endpoint,
    )

    expected_latest_switch_date = str(section.get("expected_latest_switch_date", ""))
    expected_previous_mode = str(section.get("expected_previous_mode", ""))
    expected_current_mode = str(section.get("expected_current_mode", ""))
    expected_endpoint_mode = str(section.get("expected_endpoint_mode", ""))
    expected_endpoint_exposure = float(section.get("expected_endpoint_exposure", 1.0))

    endpoint_mode = current_mode or daily_mode
    endpoint_exposure = current_exposure if pd.notna(current_exposure) else daily_exposure

    warnings = []
    if str(latest_switch_date) != expected_latest_switch_date:
        warnings.append("latest_switch_date_mismatch")
    if previous_mode != expected_previous_mode:
        warnings.append("latest_switch_previous_mode_mismatch")
    if current_mode != expected_current_mode:
        warnings.append("latest_switch_current_mode_mismatch")
    if endpoint_mode != expected_endpoint_mode:
        warnings.append("endpoint_mode_mismatch")
    if abs(float(endpoint_exposure) - expected_endpoint_exposure) > 1e-9:
        warnings.append("endpoint_exposure_mismatch")

    consistency_passed = len(warnings) == 0

    endpoint_signal = pd.DataFrame(
        [
            {
                "endpoint_date": endpoint.strftime("%Y-%m-%d") if pd.notna(endpoint) else "",
                "candidate_system_id": section.get("candidate_system_id", ""),
                "latest_switch_date": latest_switch_date,
                "latest_switch_previous_mode": previous_mode,
                "latest_switch_current_mode": current_mode,
                "latest_switch_previous_exposure": previous_exposure,
                "latest_switch_current_exposure": current_exposure,
                "endpoint_mode": endpoint_mode,
                "endpoint_exposure": endpoint_exposure,
                "endpoint_signal_action": _target_action(endpoint_mode),
                "daily_stream_endpoint_mode": daily_mode,
                "daily_stream_endpoint_exposure": daily_exposure,
                "preview_only": True,
                "paper_dry_run_allowed": False,
                "paper_trading_allowed": False,
                "signal_consistency_passed": consistency_passed,
                "blocking_warnings": ";".join(warnings),
            }
        ]
    )

    required_col_check = _required_column_check(
        endpoint_signal,
        list(section.get("required_endpoint_signal_columns", [])),
        "pinned_endpoint_signal",
    )

    boundary = _boundary_check(section, "phase15l_boundary")
    scope = _scope_check(section)

    endpoint_signal.to_csv(reports_path / "phase15k_pinned_endpoint_signal_file.csv", index=False)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15j_passed": bool(phase15j_check["passed"].all()),
                "switch_log_present": not switch_log.empty,
                "latest_switch_date": latest_switch_date,
                "endpoint_mode": endpoint_mode,
                "endpoint_exposure": endpoint_exposure,
                "signal_consistency_passed": consistency_passed,
                "preview_only": True,
                "paper_dry_run_allowed": False,
                "paper_trading_allowed": False,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
                "fresh_data_extension": False,
                "current_signal_generation": False,
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
            _gate_row("Phase 15J passed", bool(phase15j_check["passed"].all()), "phase15j"),
            _gate_row("Switch log present", not switch_log.empty, f"rows={len(switch_log)}"),
            _gate_row(
                "Latest switch matches expected",
                str(latest_switch_date) == expected_latest_switch_date
                and previous_mode == expected_previous_mode
                and current_mode == expected_current_mode,
                f"{latest_switch_date}: {previous_mode}->{current_mode}",
            ),
            _gate_row("Endpoint signal consistent", consistency_passed, ";".join(warnings)),
            _gate_row("Endpoint signal file output exists", True, "phase15k_pinned_endpoint_signal_file.csv"),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "endpoint signal columns"),
            _gate_row("Endpoint signal is preview-only", True, "preview_only=True"),
            _gate_row("Paper dry-run blocked", not _bool_value(endpoint_signal.iloc[0]["paper_dry_run_allowed"]), "paper dry-run"),
            _gate_row("Paper trading blocked", not _bool_value(endpoint_signal.iloc[0]["paper_trading_allowed"]), "paper trading"),
            _gate_row("Phase 15L boundary is pre-implementation-only", bool(boundary["passed"].all()), "phase15l"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Pinned-endpoint operational signal consistency audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15K",
                "diagnostic": "Pinned-endpoint operational signal consistency audit",
                "verdict": (
                    "Completed — pinned-endpoint operational signal consistency audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed pinned-endpoint operational signal consistency audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "endpoint_signal_consistency_passed": consistency_passed,
                "fresh_current_signal_preimplementation_allowed_next": bool(gate_report["passed"].all()),
                "paper_dry_run_allowed": False,
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
        "source_report_check": source_check,
        "phase15j_result_check": phase15j_check,
        "pinned_endpoint_signal_file": endpoint_signal,
        "required_column_check": required_col_check,
        "phase15l_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "pinned_endpoint_signal_file":
            continue
        frame.to_csv(reports_path / f"phase15k_endpoint_signal_{name}.csv", index=False)

    print("Wrote Phase 15K pinned-endpoint signal consistency reports.")
    return outputs


def _policy_readiness_report(
    *,
    phase15f_policy: pd.DataFrame,
    required_keywords: list[str],
    report_name: str,
) -> pd.DataFrame:
    if phase15f_policy.empty:
        return pd.DataFrame(
            [
                {
                    "report_name": report_name,
                    "policy_present": False,
                    "required_keywords_found": False,
                    "missing_keywords": ";".join(required_keywords),
                    "passed": False,
                    "result": "Failed",
                }
            ]
        )

    combined = " ".join(
        phase15f_policy.astype(str).fillna("").to_numpy().ravel().tolist()
    ).lower()

    missing = [word for word in required_keywords if word.lower() not in combined]

    return pd.DataFrame(
        [
            {
                "report_name": report_name,
                "policy_present": True,
                "required_keywords_found": len(missing) == 0,
                "missing_keywords": ";".join(missing),
                "passed": len(missing) == 0,
                "result": "Passed" if len(missing) == 0 else "Failed",
            }
        ]
    )


def save_phase15l_fresh_data_current_signal_preimplementation_check(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15l_fresh_data_current_signal_preimplementation_check")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    sources = section.get("source_reports", {})
    source_check = _source_report_check(sources)
    phase15k_check = _phase_result_check(
        sources.get("phase15k_conclusion", ""),
        sources.get("phase15k_gate_report", ""),
        "Phase 15K",
    )

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))

    baseline_policy = _read_csv_if_exists(sources.get("phase15f_baseline_protection_policy", ""))
    fresh_data_policy = _read_csv_if_exists(sources.get("phase15f_fresh_data_source_policy", ""))
    signal_policy = _read_csv_if_exists(sources.get("phase15f_current_signal_update_policy", ""))
    signal_schema = _read_csv_if_exists(sources.get("phase15f_current_signal_output_schema", ""))
    cadence_policy = _read_csv_if_exists(sources.get("phase15f_cadence_policy", ""))
    failure_policy = _read_csv_if_exists(sources.get("phase15f_failure_handling_policy", ""))

    baseline_combined = (
        " ".join(baseline_policy.astype(str).fillna("").to_numpy().ravel().tolist()).lower()
        if not baseline_policy.empty
        else ""
    )

    baseline_ready = pd.DataFrame(
        [
            {
                "report_name": "baseline_protection",
                "policy_present": not baseline_policy.empty,
                "preserve_keyword_found": "preserve" in baseline_combined,
                "phase6b_keyword_found": "phase6b" in baseline_combined,
                "fresh_output_prefix_found": (
                    "phase15g_current_signal" in baseline_combined
                    or "phase15m_current_signal" in baseline_combined
                ),
                "passed": (
                    not baseline_policy.empty
                    and "preserve" in baseline_combined
                    and "phase6b" in baseline_combined
                    and (
                        "phase15g_current_signal" in baseline_combined
                        or "phase15m_current_signal" in baseline_combined
                    )
                ),
                "result": "",
            }
        ]
    )
    baseline_ready["result"] = baseline_ready["passed"].map(
        {True: "Passed", False: "Failed"}
    )
    fresh_data_ready = _policy_readiness_report(
        phase15f_policy=fresh_data_policy,
        required_keywords=["beyond", "timestamp", "data_as_of", "source"],
        report_name="fresh_data_source",
    )
    signal_policy_ready = _policy_readiness_report(
        phase15f_policy=signal_policy,
        required_keywords=["max_signal_staleness_days", "failed_data_pull", "source"],
        report_name="current_signal_update",
    )
    cadence_ready = _policy_readiness_report(
        phase15f_policy=cadence_policy,
        required_keywords=["daily", "3"],
        report_name="cadence",
    )
    failure_ready = _policy_readiness_report(
        phase15f_policy=failure_policy,
        required_keywords=["block", "failure"],
        report_name="failure_handling",
    )

    required_schema = list(
        section.get("phase15m_current_signal_output", {}).get("minimum_required_columns", [])
    )
    schema_cols = set(signal_schema.get("column_name", [])) if not signal_schema.empty else set()
    missing_schema_cols = sorted(set(required_schema) - schema_cols)

    current_signal_schema_ready = pd.DataFrame(
        [
            {
                "required_columns": len(required_schema),
                "present_columns": len(schema_cols),
                "missing_columns": ";".join(missing_schema_cols),
                "passed": len(missing_schema_cols) == 0,
                "result": "Passed" if len(missing_schema_cols) == 0 else "Failed",
            }
        ]
    )

    switch_log = _read_csv_if_exists(sources.get("switch_log", ""))
    pinned_signal = _read_csv_if_exists(sources.get("phase15k_endpoint_signal", ""))

    boundary = _boundary_check(section, "phase15m_boundary")
    scope = _scope_check(section)

    readiness_passed = bool(
        phase15k_check["passed"].all()
        and flags["passed"].all()
        and baseline_ready["passed"].all()
        and fresh_data_ready["passed"].all()
        and signal_policy_ready["passed"].all()
        and current_signal_schema_ready["passed"].all()
        and cadence_ready["passed"].all()
        and failure_ready["passed"].all()
        and not switch_log.empty
        and not pinned_signal.empty
        and boundary["passed"].all()
        and (scope.empty or scope["passed"].all())
    )

    decision = pd.DataFrame(
        [
            {
                "decision": section.get("decision_policy", {}).get(
                    "decision_if_ready",
                    "fresh_current_signal_generation_allowed_next",
                )
                if readiness_passed
                else section.get("decision_policy", {}).get(
                    "decision_if_failed",
                    "blocked_fresh_signal_preimplementation_check_failed",
                ),
                "fresh_current_signal_generation_allowed_next": readiness_passed,
                "data_pull_executed": False,
                "current_signal_generated": False,
                "paper_dry_run_allowed": False,
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

    summary = pd.DataFrame(
        [
            {
                "check_role": section.get("check_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15k_passed": bool(phase15k_check["passed"].all()),
                "config_flags_clean": bool(flags["passed"].all()),
                "baseline_protection_ready": bool(baseline_ready["passed"].all()),
                "fresh_data_policy_ready": bool(fresh_data_ready["passed"].all()),
                "current_signal_schema_ready": bool(current_signal_schema_ready["passed"].all()),
                "cadence_policy_ready": bool(cadence_ready["passed"].all()),
                "failure_handling_ready": bool(failure_ready["passed"].all()),
                "switch_log_available": not switch_log.empty,
                "pinned_endpoint_signal_available": not pinned_signal.empty,
                "decision": decision.iloc[0]["decision"],
                "fresh_current_signal_generation_allowed_next": readiness_passed,
                "data_pull_executed": False,
                "current_signal_generated": False,
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
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
            _gate_row("Phase 15K passed", bool(phase15k_check["passed"].all()), "phase15k"),
            _gate_row("Config flags clean", bool(flags["passed"].all()), "runtime flags"),
            _gate_row("Baseline protection ready", bool(baseline_ready["passed"].all()), "baseline"),
            _gate_row("Fresh data policy ready", bool(fresh_data_ready["passed"].all()), "fresh data"),
            _gate_row("Current signal schema ready", bool(current_signal_schema_ready["passed"].all()), "schema"),
            _gate_row("Cadence policy ready", bool(cadence_ready["passed"].all()), "cadence"),
            _gate_row("Failure handling ready", bool(failure_ready["passed"].all()), "failure handling"),
            _gate_row("Switch log available", not switch_log.empty, f"rows={len(switch_log)}"),
            _gate_row("Pinned endpoint signal available", not pinned_signal.empty, f"rows={len(pinned_signal)}"),
            _gate_row("Phase 15M boundary is signal-generation-only", bool(boundary["passed"].all()), "phase15m"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Check role is correct",
                section.get("check_role")
                == "Fresh data extension and current signal generation pre-implementation check only",
                section.get("check_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15L",
                "diagnostic": "Fresh data extension and current signal generation pre-implementation check",
                "verdict": (
                    "Completed — fresh current-signal pre-implementation check passed"
                    if bool(gate_report["passed"].all())
                    else "Failed fresh current-signal pre-implementation check"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision.iloc[0]["decision"],
                "fresh_current_signal_generation_allowed_next": readiness_passed,
                "data_pull_executed": False,
                "current_signal_generated": False,
                "paper_dry_run_allowed": False,
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
        "source_report_check": source_check,
        "phase15k_result_check": phase15k_check,
        "config_flag_check": flags,
        "baseline_protection_readiness": baseline_ready,
        "fresh_data_policy_readiness": fresh_data_ready,
        "current_signal_policy_readiness": signal_policy_ready,
        "current_signal_schema_readiness": current_signal_schema_ready,
        "cadence_policy_readiness": cadence_ready,
        "failure_handling_readiness": failure_ready,
        "decision_report": decision,
        "phase15m_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15l_fresh_signal_precheck_{name}.csv", index=False)

    print("Wrote Phase 15L fresh signal pre-implementation check reports.")
    return outputs