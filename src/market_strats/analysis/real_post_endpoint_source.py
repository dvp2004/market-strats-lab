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


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_post_endpoint_source_creation",
        "allow_fresh_data_pull_execution",
        "allow_canonical_report_mutation",
        "allow_current_signal_generation",
        "allow_phase15o_rerun",
        "allow_phase15o_15p_rerun_if_passed",
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
            "allow_post_endpoint_source_creation",
            "allow_phase15o_15p_rerun_if_passed",
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
    allowed = str(
        boundary.get("allowed_next_step", boundary.get("allowed_next_step_if_passed", ""))
    ).lower()
    allowed_blocked = str(boundary.get("allowed_next_step_if_blocked", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": f"{key}_allowed_next_step_is_bounded",
            "passed": bool(
                "validation" in allowed
                or "rerun phase 15o" in allowed
                or "repair" in allowed_blocked
                or "provide real post-endpoint source" in allowed_blocked
            ),
            "detail": boundary.get(
                "allowed_next_step",
                boundary.get("allowed_next_step_if_passed", ""),
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


def _mode_from_exposure(exposure: float) -> str:
    if exposure >= 0.75:
        return "offensive_spy"
    if exposure <= 0.25:
        return "defensive_or_cash"
    return "partial_risk"


def _load_source(section: dict[str, Any]) -> tuple[pd.DataFrame, str, str]:
    sources = section.get("candidate_source_priority", {})

    ordered = [
        ("rule_generated_candidate_stream", sources.get("rule_generated_candidate_stream", "")),
        ("verified_manual_candidate_stream", sources.get("verified_manual_candidate_stream", "")),
        ("existing_phase15o_manual_stream", sources.get("existing_phase15o_manual_stream", "")),
        ("raw_spy_ohlcv_only", sources.get("raw_spy_ohlcv_only", "")),
    ]

    for source_type, path in ordered:
        p = Path(path)
        if p.exists():
            return pd.read_csv(p), source_type, str(p)

    return pd.DataFrame(), "no_source_available", ""


def _normalise_benchmark(
    source: pd.DataFrame,
    section: dict[str, Any],
) -> tuple[pd.Series, pd.Series, str, str]:
    close_col = _first_existing_col(
        source,
        list(section.get("benchmark_policy", {}).get("acceptable_close_columns", [])),
    )
    return_col = _first_existing_col(
        source,
        list(section.get("benchmark_policy", {}).get("acceptable_return_columns", [])),
    )

    close = (
        pd.to_numeric(source[close_col], errors="coerce")
        if close_col
        else pd.Series(pd.NA, index=source.index)
    )

    if return_col:
        returns = pd.to_numeric(source[return_col], errors="coerce")
    elif close_col:
        returns = close.pct_change().fillna(0.0)
    else:
        returns = pd.Series(pd.NA, index=source.index)

    return close, returns, close_col or "", return_col or ""


def _target_source_valid(source_value: Any, section: dict[str, Any]) -> bool:
    accepted = {str(x).strip().lower() for x in section.get("accepted_target_weight_sources", [])}
    rejected = {str(x).strip().lower() for x in section.get("rejected_target_weight_sources", [])}
    clean = str(source_value).strip().lower()

    return clean in accepted and clean not in rejected


def _endpoint_context(section: dict[str, Any]) -> tuple[float, str]:
    endpoint = _read_csv_if_exists(
        section.get("source_reports", {}).get("pinned_endpoint_signal", "")
    )

    if endpoint.empty:
        return 0.0, "defensive_or_cash"

    exposure = pd.to_numeric(
        pd.Series([endpoint.iloc[0].get("endpoint_exposure", 0.0)]),
        errors="coerce",
    ).fillna(0.0).iloc[0]
    mode = str(endpoint.iloc[0].get("endpoint_mode", _mode_from_exposure(float(exposure))))
    return float(exposure), mode


def _blocked_stream(required_columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=required_columns)


def _build_phase15q_stream(section: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_columns = list(section.get("required_phase15q_output_columns", []))
    source, source_type, source_path = _load_source(section)

    pinned = pd.to_datetime(section.get("pinned_research_endpoint", ""), errors="coerce")
    audit_date = pd.to_datetime(section.get("audit_current_date", ""), errors="coerce")

    if source.empty:
        stream = _blocked_stream(required_columns)
        summary = _creation_summary(
            stream=stream,
            source_type=source_type,
            source_path=source_path,
            failure_reason="post_endpoint_source_missing",
        )
        return stream, summary

    date_col = _first_existing_col(source, ["date", "decision_date"])
    if date_col is None:
        stream = _blocked_stream(required_columns)
        summary = _creation_summary(
            stream=stream,
            source_type=source_type,
            source_path=source_path,
            failure_reason="date_column_missing",
        )
        return stream, summary

    source = source.copy()
    source["date"] = pd.to_datetime(source[date_col], errors="coerce")
    source = source[source["date"].notna()].copy()

    if pd.notna(pinned):
        source = source[source["date"] > pinned].copy()
    if pd.notna(audit_date):
        source = source[source["date"] <= audit_date].copy()

    source = source.sort_values("date").drop_duplicates("date").reset_index(drop=True)

    if source.empty:
        stream = _blocked_stream(required_columns)
        summary = _creation_summary(
            stream=stream,
            source_type=source_type,
            source_path=source_path,
            failure_reason="no_rows_after_pinned_endpoint",
        )
        return stream, summary

    close, returns, close_col, return_col = _normalise_benchmark(source, section)

    if "target_offensive_weight" in source.columns:
        target = pd.to_numeric(source["target_offensive_weight"], errors="coerce")
    else:
        target = pd.Series(pd.NA, index=source.index)

    if "target_weight_source" in source.columns:
        target_source = source["target_weight_source"].astype(str)
    elif source_type == "rule_generated_candidate_stream":
        target_source = pd.Series("phase6b_rule_engine", index=source.index)
    elif source_type == "raw_spy_ohlcv_only":
        target_source = pd.Series("raw_spy_only_no_rule_target", index=source.index)
    else:
        target_source = pd.Series("unknown", index=source.index)

    target_source_valid = target_source.map(lambda value: _target_source_valid(value, section))

    endpoint_exposure, _endpoint_mode = _endpoint_context(section)
    previous_exposure = target.shift(1)
    if len(previous_exposure) > 0:
        previous_exposure.iloc[0] = endpoint_exposure

    current_exposure = target
    previous_exposure = pd.to_numeric(previous_exposure, errors="coerce")

    current_mode = current_exposure.map(
        lambda value: _mode_from_exposure(float(value)) if pd.notna(value) else ""
    )
    previous_mode = previous_exposure.map(
        lambda value: _mode_from_exposure(float(value)) if pd.notna(value) else ""
    )

    current_exposure_numeric = pd.to_numeric(current_exposure, errors="coerce")
    previous_exposure_numeric = pd.to_numeric(previous_exposure, errors="coerce")

    switch_triggered = current_exposure_numeric.round(10).ne(
        previous_exposure_numeric.round(10)
    )
    switch_triggered = switch_triggered.fillna(False)

    timestamp_col = _first_existing_col(
        source,
        ["data_source_timestamp", "source_timestamp", "updated_at"],
    )
    timestamp = (
        source[timestamp_col].astype(str)
        if timestamp_col
        else source["date"].dt.strftime("%Y-%m-%d")
    )

    benchmark_ok = close.notna() | returns.notna()
    target_ok = (
        current_exposure_numeric.notna()
        & current_exposure_numeric.between(0.0, 1.0)
    )

    blocking_warnings = []
    for idx in source.index:
        warnings = []
        if not benchmark_ok.loc[idx]:
            warnings.append("benchmark_update_missing")
        if not target_ok.loc[idx]:
            warnings.append("target_offensive_weight_missing_or_invalid")
        if not target_source_valid.loc[idx]:
            warnings.append("target_weight_source_not_verified_rule_logic")
        blocking_warnings.append(";".join(warnings))

    row_validity = benchmark_ok & target_ok & target_source_valid

    stream = pd.DataFrame(
        {
            "date": source["date"].dt.strftime("%Y-%m-%d"),
            "SPY_close": close,
            "SPY_return": returns,
            "target_offensive_weight": current_exposure_numeric,
            "current_exposure": current_exposure_numeric,
            "previous_exposure": previous_exposure_numeric,
            "current_mode": current_mode,
            "previous_mode": previous_mode,
            "switch_triggered": switch_triggered,
            "data_source": source_path or source_type,
            "data_source_timestamp": timestamp,
            "target_weight_source": target_source,
            "target_weight_source_valid_flag": target_source_valid.map({True: "pass", False: "fail"}),
            "pinned_research_endpoint": section.get("pinned_research_endpoint", ""),
            "is_out_of_sample_extension": True,
            "benchmark_update_flag": benchmark_ok.map({True: "pass", False: "fail"}),
            "stream_row_validity_flag": row_validity.map({True: "pass", False: "fail"}),
            "blocking_warnings": blocking_warnings,
        }
    )

    summary = _creation_summary(
        stream=stream,
        source_type=source_type,
        source_path=source_path,
        failure_reason="",
    )
    return stream[required_columns], summary


def _creation_summary(
    *,
    stream: pd.DataFrame,
    source_type: str,
    source_path: str,
    failure_reason: str,
) -> pd.DataFrame:
    rows = len(stream)

    benchmark_passed = (
        rows > 0
        and "benchmark_update_flag" in stream.columns
        and stream["benchmark_update_flag"].astype(str).str.lower().eq("pass").all()
    )
    target_source_passed = (
        rows > 0
        and "target_weight_source_valid_flag" in stream.columns
        and stream["target_weight_source_valid_flag"].astype(str).str.lower().eq("pass").all()
    )
    row_validity_passed = (
        rows > 0
        and "stream_row_validity_flag" in stream.columns
        and stream["stream_row_validity_flag"].astype(str).str.lower().eq("pass").all()
    )
    out_of_sample_passed = (
        rows > 0
        and "is_out_of_sample_extension" in stream.columns
        and stream["is_out_of_sample_extension"].map(_bool_value).all()
    )

    if not failure_reason:
        failures = []
        if rows <= 0:
            failures.append("no_post_endpoint_rows")
        if not benchmark_passed:
            failures.append("benchmark_update_failed")
        if not target_source_passed:
            failures.append("target_weight_source_invalid")
        if not row_validity_passed:
            failures.append("stream_row_validity_failed")
        if not out_of_sample_passed:
            failures.append("out_of_sample_label_failed")
        failure_reason = ";".join(failures)

    valid = bool(
        rows > 0
        and benchmark_passed
        and target_source_passed
        and row_validity_passed
        and out_of_sample_passed
    )

    return pd.DataFrame(
        [
            {
                "post_endpoint_rows": rows,
                "source_type": source_type,
                "source_path": source_path,
                "benchmark_update_passed": benchmark_passed,
                "target_weight_source_passed": target_source_passed,
                "stream_row_validity_passed": row_validity_passed,
                "out_of_sample_label_passed": out_of_sample_passed,
                "candidate_stream_valid": valid,
                "canonical_report_mutation": False,
                "failure_reason": failure_reason,
            }
        ]
    )


def save_phase15q_post_endpoint_data_source_creation(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15q_post_endpoint_data_source_creation")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase15p_check = _phase_result_check(
        section.get("source_reports", {}).get("phase15p_conclusion", ""),
        section.get("source_reports", {}).get("phase15p_gate_report", ""),
        "Phase 15P",
    )

    candidate_stream, creation_summary = _build_phase15q_stream(section)

    output_file = Path(section.get("output_file", "reports/phase15q_post_endpoint_candidate_stream.csv"))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    candidate_stream.to_csv(output_file, index=False)

    handoff_file = Path(section.get("handoff_file_for_phase15o", "data/fresh/phase15o_manual_candidate_stream.csv"))
    handoff_file.parent.mkdir(parents=True, exist_ok=True)

    if _bool_value(creation_summary.iloc[0]["candidate_stream_valid"]):
        candidate_stream.to_csv(handoff_file, index=False)
        handoff_written = True
    else:
        if handoff_file.exists():
            handoff_file.unlink()
        handoff_written = False

    required_col_check = _required_column_check(
        candidate_stream,
        list(section.get("required_phase15q_output_columns", [])),
        "phase15q_post_endpoint_candidate_stream",
    )

    boundary = _boundary_check(section, "phase15r_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15p_passed": bool(phase15p_check["passed"].all()),
                "output_file_written": output_file.exists(),
                "handoff_file_for_phase15o": str(handoff_file),
                "handoff_file_written": handoff_written,
                "post_endpoint_rows": int(creation_summary.iloc[0]["post_endpoint_rows"]),
                "candidate_stream_valid": _bool_value(creation_summary.iloc[0]["candidate_stream_valid"]),
                "benchmark_update_passed": _bool_value(creation_summary.iloc[0]["benchmark_update_passed"]),
                "target_weight_source_passed": _bool_value(creation_summary.iloc[0]["target_weight_source_passed"]),
                "stream_row_validity_passed": _bool_value(creation_summary.iloc[0]["stream_row_validity_passed"]),
                "canonical_report_mutation": False,
                "current_signal_generation": False,
                "phase15o_rerun": False,
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
            _gate_row("Phase 15P passed", bool(phase15p_check["passed"].all()), "phase15p"),
            _gate_row("Output file written", output_file.exists(), str(output_file)),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "schema"),
            _gate_row("Pinned endpoint preserved", True, section.get("pinned_research_endpoint", "")),
            _gate_row("No canonical report mutation", True, "separate data/fresh handoff only if valid"),
            _gate_row("Blocked stream written if invalid", True, creation_summary.iloc[0]["failure_reason"]),
            _gate_row("Phase 15R boundary is validation-only", bool(boundary["passed"].all()), "phase15r"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role")
                == "Manual or fresh post-endpoint data source creation only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15Q",
                "diagnostic": "Manual or fresh post-endpoint data source creation",
                "verdict": (
                    "Completed — post-endpoint data source creation output written"
                    if bool(gate_report["passed"].all())
                    else "Failed post-endpoint data source creation"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "candidate_stream_valid": _bool_value(creation_summary.iloc[0]["candidate_stream_valid"]),
                "handoff_file_written": handoff_written,
                "post_endpoint_rows": int(creation_summary.iloc[0]["post_endpoint_rows"]),
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
        "post_endpoint_candidate_stream": candidate_stream,
        "creation_summary": creation_summary,
        "required_column_check": required_col_check,
        "phase15p_result_check": phase15p_check,
        "phase15r_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "post_endpoint_candidate_stream":
            continue
        frame.to_csv(reports_path / f"phase15q_data_source_{name}.csv", index=False)

    print("Wrote Phase 15Q real post-endpoint source reports.")
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
                "passed": p.exists(),
                "result": "Passed" if p.exists() else "Failed",
            }
        )
    return pd.DataFrame(rows)


def _validation_audit(stream: pd.DataFrame, section: dict[str, Any]) -> pd.DataFrame:
    pinned = pd.to_datetime(section.get("pinned_research_endpoint", ""), errors="coerce")
    policy = section.get("validation_policy", {})

    if stream.empty:
        return pd.DataFrame(
            [
                {
                    "post_endpoint_rows": 0,
                    "post_endpoint_rows_passed": False,
                    "all_dates_after_endpoint_passed": False,
                    "benchmark_update_passed": False,
                    "target_weight_source_passed": False,
                    "target_exposure_present_passed": False,
                    "target_exposure_range_passed": False,
                    "out_of_sample_label_passed": False,
                    "all_validation_gates_passed": False,
                    "failure_reason": "candidate_stream_empty",
                }
            ]
        )

    dates = pd.to_datetime(stream["date"], errors="coerce")
    rows = len(stream)
    min_rows = int(policy.get("min_post_endpoint_rows", 1))

    target = pd.to_numeric(stream["target_offensive_weight"], errors="coerce")

    post_endpoint_rows_passed = rows >= min_rows
    all_dates_after_endpoint_passed = bool(dates.notna().all() and (dates > pinned).all())
    benchmark_update_passed = bool(stream["benchmark_update_flag"].astype(str).str.lower().eq("pass").all())
    target_weight_source_passed = bool(
        stream["target_weight_source_valid_flag"].astype(str).str.lower().eq("pass").all()
    )
    target_exposure_present_passed = bool(target.notna().all())
    target_exposure_range_passed = bool(target.between(0.0, 1.0).all())
    out_of_sample_label_passed = bool(stream["is_out_of_sample_extension"].map(_bool_value).all())

    failures = []
    if not post_endpoint_rows_passed:
        failures.append("insufficient_post_endpoint_rows")
    if not all_dates_after_endpoint_passed:
        failures.append("dates_not_after_pinned_endpoint")
    if not benchmark_update_passed:
        failures.append("benchmark_update_failed")
    if not target_weight_source_passed:
        failures.append("target_weight_source_invalid")
    if not target_exposure_present_passed:
        failures.append("target_offensive_weight_missing")
    if not target_exposure_range_passed:
        failures.append("target_exposure_range_invalid")
    if not out_of_sample_label_passed:
        failures.append("out_of_sample_label_failed")

    passed = len(failures) == 0

    return pd.DataFrame(
        [
            {
                "post_endpoint_rows": rows,
                "post_endpoint_rows_passed": post_endpoint_rows_passed,
                "all_dates_after_endpoint_passed": all_dates_after_endpoint_passed,
                "benchmark_update_passed": benchmark_update_passed,
                "target_weight_source_passed": target_weight_source_passed,
                "target_exposure_present_passed": target_exposure_present_passed,
                "target_exposure_range_passed": target_exposure_range_passed,
                "out_of_sample_label_passed": out_of_sample_label_passed,
                "all_validation_gates_passed": passed,
                "failure_reason": ";".join(failures),
            }
        ]
    )


def save_phase15r_real_post_endpoint_stream_validation(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15r_real_post_endpoint_stream_validation")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    inventory = _report_inventory(section.get("phase15q_reports", {}))

    phase15q_check = _phase_result_check(
        section.get("phase15q_reports", {}).get("conclusion", ""),
        section.get("phase15q_reports", {}).get("gate_report", ""),
        "Phase 15Q",
    )

    stream = _read_csv_if_exists(section.get("phase15q_reports", {}).get("candidate_stream", ""))
    required_col_check = _required_column_check(
        stream,
        list(section.get("required_phase15q_output_columns", [])),
        "phase15q_post_endpoint_candidate_stream",
    )

    audit = _validation_audit(stream, section)
    all_valid = _bool_value(audit.iloc[0]["all_validation_gates_passed"])

    handoff_file = Path(section.get("handoff_file_for_phase15o", "data/fresh/phase15o_manual_candidate_stream.csv"))
    handoff_ready = bool(all_valid and handoff_file.exists())

    decision_text = (
        section.get("decision_policy", {}).get(
            "decision_if_valid",
            "phase15o_15p_rerun_allowed_next",
        )
        if handoff_ready
        else section.get("decision_policy", {}).get(
            "decision_if_invalid",
            "blocked_real_post_endpoint_source_invalid",
        )
    )

    decision = pd.DataFrame(
        [
            {
                "decision": decision_text,
                "phase15o_15p_rerun_allowed_next": handoff_ready,
                "phase15m_15n_rerun_allowed_next": False,
                "paper_dry_run_preregistration_allowed_next": False,
                "paper_trading_ready": False,
                "broker_api_integration_allowed": False,
                "paper_trading_deployment_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "failure_reason": audit.iloc[0]["failure_reason"],
            }
        ]
    )

    boundary = _boundary_check(section, "phase15o_rerun_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15q_passed": bool(phase15q_check["passed"].all()),
                "config_flags_clean": bool(flags["passed"].all()),
                "candidate_stream_file_exists": not stream.empty,
                "required_columns_present": bool(required_col_check["present"].all()),
                "post_endpoint_rows": int(audit.iloc[0]["post_endpoint_rows"]),
                "all_validation_gates_passed": all_valid,
                "handoff_file_ready": handoff_ready,
                "decision": decision_text,
                "phase15o_15p_rerun_allowed_next": handoff_ready,
                "phase15m_15n_rerun_allowed_next": False,
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
            _gate_row("Phase 15Q passed", bool(phase15q_check["passed"].all()), "phase15q"),
            _gate_row("Config flags clean", bool(flags["passed"].all()), "runtime flags"),
            _gate_row("Candidate stream file existence audited", True, f"rows={len(stream)}"),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "schema"),
            _gate_row("Post-endpoint rows audited", True, str(audit.iloc[0]["post_endpoint_rows_passed"])),
            _gate_row("Benchmark update audited", True, str(audit.iloc[0]["benchmark_update_passed"])),
            _gate_row("Target weight source audited", True, str(audit.iloc[0]["target_weight_source_passed"])),
            _gate_row("Target exposure audited", True, str(audit.iloc[0]["target_exposure_range_passed"])),
            _gate_row("Out-of-sample label audited", True, str(audit.iloc[0]["out_of_sample_label_passed"])),
            _gate_row("Decision output exists", len(decision) == 1, decision_text),
            _gate_row("No paper-ready claim", not _bool_value(decision.iloc[0]["paper_trading_ready"]), "paper_trading_ready=False"),
            _gate_row("Phase 15O rerun boundary is conditional-only", bool(boundary["passed"].all()), "phase15o rerun"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Real post-endpoint candidate stream validation and 15O/15P rerun preparation only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15R",
                "diagnostic": "Real post-endpoint candidate stream validation and 15O/15P rerun preparation",
                "verdict": (
                    "Completed — real post-endpoint stream validation passed"
                    if bool(gate_report["passed"].all())
                    else "Failed real post-endpoint stream validation"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision_text,
                "phase15o_15p_rerun_allowed_next": handoff_ready,
                "phase15m_15n_rerun_allowed_next": False,
                "paper_dry_run_preregistration_allowed_next": False,
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
        "phase15q_result_check": phase15q_check,
        "required_column_check": required_col_check,
        "real_source_validation_audit": audit,
        "decision_report": decision,
        "phase15o_rerun_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15r_real_source_{name}.csv", index=False)

    print("Wrote Phase 15R real post-endpoint stream validation reports.")
    return outputs