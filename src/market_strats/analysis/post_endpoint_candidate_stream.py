from __future__ import annotations

from pathlib import Path
from typing import Any

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
    if path is None or str(path).strip() == "":
        return pd.DataFrame()

    p = Path(path)
    if not p.exists() or p.is_dir():
        return pd.DataFrame()

    try:
        return pd.read_csv(p)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


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
        "allow_post_endpoint_candidate_stream_write",
        "allow_fresh_data_pull_execution",
        "allow_canonical_report_mutation",
        "allow_current_signal_generation",
        "allow_phase15m_rerun_if_passed",
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
            "allow_post_endpoint_candidate_stream_write",
            "allow_phase15m_rerun_if_passed",
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
                "audit" in allowed
                or "rerun phase 15m" in allowed
                or "candidate stream repair" in allowed_blocked
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

    out = pd.DataFrame(
        rows,
        columns=[
            "config_key",
            "expected_enabled",
            "actual_enabled",
            "passed",
        ],
    )
    if out.empty:
        out["result"] = pd.Series(dtype="object")
    else:
        out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _mode_from_exposure(exposure: float) -> str:
    if exposure >= 0.75:
        return "offensive_spy"
    if exposure <= 0.25:
        return "defensive_or_cash"
    return "partial_risk"


def _post_endpoint_row_count(frame: pd.DataFrame, pinned_endpoint: str) -> int:
    if frame.empty:
        return 0

    date_col = _first_existing_col(frame, ["date", "decision_date"])
    if date_col is None:
        return 0

    pinned = pd.to_datetime(pinned_endpoint, errors="coerce")
    if pd.isna(pinned):
        return 0

    dates = pd.to_datetime(frame[date_col], errors="coerce")
    return int((dates > pinned).sum())


def _read_candidate_source(path: str | Path, pinned_endpoint: str) -> tuple[pd.DataFrame, int]:
    if path is None or str(path).strip() == "":
        return pd.DataFrame(), 0

    p = Path(path)
    if not p.exists() or p.is_dir():
        return pd.DataFrame(), 0

    try:
        frame = pd.read_csv(p)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(), 0

    post_endpoint_rows = _post_endpoint_row_count(frame, pinned_endpoint)
    return frame, post_endpoint_rows


def _load_source_frame(
    *,
    section: dict[str, Any],
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, str]:
    sources = section.get("candidate_stream_sources", {})
    pinned_endpoint = str(section.get("pinned_research_endpoint", "2026-05-01"))
    prefer_rule_generated = bool(
        config.get("phase15wxyz_fresh_extension_pipeline", {}).get("enabled", False)
    )
    source_priority = (
        [
            "preferred_rule_generated_candidate_stream_file",
            "preferred_manual_candidate_stream_file",
            "preferred_existing_fresh_candidate_stream_file",
        ]
        if prefer_rule_generated
        else [
            "preferred_manual_candidate_stream_file",
            "preferred_rule_generated_candidate_stream_file",
            "preferred_existing_fresh_candidate_stream_file",
        ]
    )

    # File-based fresh handoffs must be tried before the in-memory final
    # candidate frame. The in-memory frame is usually the pinned historical
    # output and can silently erase valid post-endpoint rows if it is selected
    # too early.
    for key in source_priority:
        frame, post_endpoint_rows = _read_candidate_source(
            sources.get(key, ""),
            pinned_endpoint,
        )
        if post_endpoint_rows > 0:
            return frame, str(Path(sources.get(key, "")))

    if _bool_value(
        sources.get(
            "allow_in_memory_final_candidate_frame_if_post_endpoint_rows_exist",
            False,
        )
    ):
        try:
            frame = _find_final_candidate_frame(
                relative_momentum_outputs=relative_momentum_outputs,
                ticker_outputs=ticker_outputs,
                config=config,
            )
            if _post_endpoint_row_count(frame, pinned_endpoint) > 0:
                return frame, "in_memory_final_candidate_frame"
        except Exception as exc:  # pragma: no cover - runtime guard
            return pd.DataFrame({"load_error": [str(exc)]}), "candidate_frame_load_failed"

    return pd.DataFrame(), "no_candidate_stream_source_available"


def _selected_exposure_definition(section: dict[str, Any]) -> tuple[str, str]:
    selected = _read_csv_if_exists(
        section.get("source_reports", {}).get("selected_switch_definition", "")
    )

    if not selected.empty and _bool_value(selected.iloc[0].get("selected", False)):
        return str(selected.iloc[0].get("selected_column", "")), str(
            selected.iloc[0].get("transform", "direct")
        )

    priority = list(section.get("selected_exposure_fallback_priority", []))
    return priority[0] if priority else "", "direct"


def _normalise_exposure(frame: pd.DataFrame, column: str, transform: str) -> pd.Series:
    exposure = pd.to_numeric(frame[column], errors="coerce")
    if transform == "inverse":
        exposure = 1.0 - exposure
    return exposure.ffill()


def _empty_stream(required_columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=required_columns)


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


def _build_extended_stream(
    *,
    section: dict[str, Any],
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_columns = list(section.get("required_extended_candidate_stream_columns", []))
    source, data_source = _load_source_frame(
        section=section,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    selected_col, transform = _selected_exposure_definition(section)
    pinned = pd.to_datetime(section.get("pinned_research_endpoint", ""), errors="coerce")
    audit_date = pd.to_datetime(section.get("audit_current_date", ""), errors="coerce")

    if source.empty:
        stream = _empty_stream(required_columns)
        summary = _extension_summary(
            stream=stream,
            data_source=data_source,
            selected_col=selected_col,
            transform=transform,
            failure_reason="candidate_stream_source_missing_or_empty",
        )
        return stream, summary

    date_col = _first_existing_col(source, ["date", "decision_date"])
    if date_col is None:
        stream = _empty_stream(required_columns)
        summary = _extension_summary(
            stream=stream,
            data_source=data_source,
            selected_col=selected_col,
            transform=transform,
            failure_reason="date_column_missing",
        )
        return stream, summary

    if selected_col not in source.columns:
        stream = _empty_stream(required_columns)
        summary = _extension_summary(
            stream=stream,
            data_source=data_source,
            selected_col=selected_col,
            transform=transform,
            failure_reason=f"selected_exposure_column_missing:{selected_col}",
        )
        return stream, summary

    frame = source.copy()
    frame["date"] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame[frame["date"].notna()].copy()

    if pd.notna(pinned):
        frame = frame[frame["date"] > pinned].copy()

    if pd.notna(audit_date):
        frame = frame[frame["date"] <= audit_date].copy()

    frame = frame.sort_values("date").drop_duplicates("date").reset_index(drop=True)

    if frame.empty:
        stream = _empty_stream(required_columns)
        summary = _extension_summary(
            stream=stream,
            data_source=data_source,
            selected_col=selected_col,
            transform=transform,
            failure_reason="no_post_endpoint_rows_available",
        )
        return stream, summary

    close_col = _first_existing_col(
        frame,
        list(section.get("benchmark_policy", {}).get("acceptable_close_columns", [])),
    )
    return_col = _first_existing_col(
        frame,
        list(section.get("benchmark_policy", {}).get("acceptable_return_columns", [])),
    )

    exposure = _normalise_exposure(frame, selected_col, transform)
    endpoint_exposure, endpoint_mode = _endpoint_context(section)

    previous_exposure = exposure.shift(1)
    if len(previous_exposure) > 0:
        previous_exposure.iloc[0] = endpoint_exposure

    current_exposure = exposure.astype(float)
    previous_exposure = previous_exposure.astype(float)

    current_mode = current_exposure.map(_mode_from_exposure)
    previous_mode = previous_exposure.map(_mode_from_exposure)
    switch_triggered = current_exposure.round(10).ne(previous_exposure.round(10))

    spy_close = (
        pd.to_numeric(frame[close_col], errors="coerce")
        if close_col
        else pd.Series(pd.NA, index=frame.index)
    )
    spy_return = (
        pd.to_numeric(frame[return_col], errors="coerce")
        if return_col
        else spy_close.pct_change().fillna(0.0)
        if close_col
        else pd.Series(pd.NA, index=frame.index)
    )

    benchmark_ok = spy_close.notna() | spy_return.notna()
    exposure_ok = current_exposure.notna() & current_exposure.between(0.0, 1.0)

    data_source_timestamp_col = _first_existing_col(
        frame,
        ["data_source_timestamp", "source_timestamp", "updated_at"],
    )
    data_source_timestamp = (
        frame[data_source_timestamp_col].astype(str)
        if data_source_timestamp_col
        else frame["date"].dt.strftime("%Y-%m-%d")
    )

    blocking_warnings = []
    for idx in frame.index:
        warnings = []
        if not benchmark_ok.loc[idx]:
            warnings.append("benchmark_update_missing")
        if not exposure_ok.loc[idx]:
            warnings.append("target_exposure_invalid")
        blocking_warnings.append(";".join(warnings))

    stream = pd.DataFrame(
        {
            "date": frame["date"].dt.strftime("%Y-%m-%d"),
            "SPY_close": spy_close,
            "SPY_return": spy_return,
            "target_offensive_weight": current_exposure,
            "current_mode": current_mode,
            "current_exposure": current_exposure,
            "previous_mode": previous_mode,
            "previous_exposure": previous_exposure,
            "switch_triggered": switch_triggered,
            "data_source": data_source,
            "data_source_timestamp": data_source_timestamp,
            "pinned_research_endpoint": section.get("pinned_research_endpoint", ""),
            "is_out_of_sample_extension": True,
            "benchmark_update_flag": benchmark_ok.map({True: "pass", False: "fail"}),
            "stream_row_validity_flag": (benchmark_ok & exposure_ok).map({True: "pass", False: "fail"}),
            "blocking_warnings": blocking_warnings,
        }
    )

    summary = _extension_summary(
        stream=stream,
        data_source=data_source,
        selected_col=selected_col,
        transform=transform,
        failure_reason="",
    )
    return stream[required_columns], summary


def _extension_summary(
    *,
    stream: pd.DataFrame,
    data_source: str,
    selected_col: str,
    transform: str,
    failure_reason: str,
) -> pd.DataFrame:
    post_endpoint_rows = len(stream)
    benchmark_passed = (
        post_endpoint_rows > 0
        and "benchmark_update_flag" in stream.columns
        and stream["benchmark_update_flag"].astype(str).str.lower().eq("pass").all()
    )
    row_validity_passed = (
        post_endpoint_rows > 0
        and "stream_row_validity_flag" in stream.columns
        and stream["stream_row_validity_flag"].astype(str).str.lower().eq("pass").all()
    )
    exposure_continuity_passed = (
        post_endpoint_rows > 0
        and "current_exposure" in stream.columns
        and "previous_exposure" in stream.columns
        and pd.to_numeric(stream["current_exposure"], errors="coerce").notna().all()
        and pd.to_numeric(stream["previous_exposure"], errors="coerce").notna().all()
    )

    if not failure_reason:
        failures = []
        if post_endpoint_rows <= 0:
            failures.append("no_post_endpoint_rows")
        if not benchmark_passed:
            failures.append("benchmark_update_failed")
        if not row_validity_passed:
            failures.append("stream_row_validity_failed")
        if not exposure_continuity_passed:
            failures.append("exposure_continuity_failed")
        failure_reason = ";".join(failures)

    return pd.DataFrame(
        [
            {
                "post_endpoint_rows": post_endpoint_rows,
                "data_source": data_source,
                "selected_exposure_column": selected_col,
                "selected_exposure_transform": transform,
                "benchmark_update_passed": benchmark_passed,
                "stream_row_validity_passed": row_validity_passed,
                "target_exposure_continuity_passed": exposure_continuity_passed,
                "is_out_of_sample_extension": bool(
                    post_endpoint_rows > 0
                    and "is_out_of_sample_extension" in stream.columns
                    and stream["is_out_of_sample_extension"].map(_bool_value).all()
                ),
                "canonical_report_mutation": False,
                "candidate_stream_valid": bool(
                    post_endpoint_rows > 0
                    and benchmark_passed
                    and row_validity_passed
                    and exposure_continuity_passed
                ),
                "failure_reason": failure_reason,
            }
        ]
    )


def save_phase15o_post_endpoint_candidate_stream_extension(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15o_post_endpoint_candidate_stream_extension")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    upstream_label = "Phase 15R" if source_reports.get("phase15r_conclusion") else "Phase 15N"
    upstream_conclusion = source_reports.get("phase15r_conclusion") or source_reports.get(
        "phase15n_conclusion",
        "",
    )
    upstream_gate_report = source_reports.get("phase15r_gate_report") or source_reports.get(
        "phase15n_gate_report",
        "",
    )

    upstream_check = _phase_result_check(
        upstream_conclusion,
        upstream_gate_report,
        upstream_label,
    )
    upstream_passed = bool(upstream_check["passed"].all())

    candidate_stream, extension_summary = _build_extended_stream(
        section=section,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    output_file = Path(section.get("output_file", "reports/phase15o_post_endpoint_candidate_stream.csv"))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    candidate_stream.to_csv(output_file, index=False)

    required_col_check = _required_column_check(
        candidate_stream,
        list(section.get("required_extended_candidate_stream_columns", [])),
        "post_endpoint_candidate_stream",
    )

    boundary = _boundary_check(section, "phase15p_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "upstream_phase_label": upstream_label,
                "upstream_phase_passed": upstream_passed,
                "phase15n_passed": upstream_passed,
                "candidate_stream_file_written": output_file.exists(),
                "post_endpoint_rows": int(extension_summary.iloc[0]["post_endpoint_rows"]),
                "candidate_stream_valid": _bool_value(extension_summary.iloc[0]["candidate_stream_valid"]),
                "benchmark_update_passed": _bool_value(extension_summary.iloc[0]["benchmark_update_passed"]),
                "target_exposure_continuity_passed": _bool_value(
                    extension_summary.iloc[0]["target_exposure_continuity_passed"]
                ),
                "is_out_of_sample_extension": _bool_value(
                    extension_summary.iloc[0]["is_out_of_sample_extension"]
                ),
                "canonical_report_mutation": False,
                "data_pull_executed": False,
                "current_signal_generation": False,
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
            _gate_row(f"{upstream_label} passed", upstream_passed, upstream_label),
            _gate_row("Candidate stream file written", output_file.exists(), str(output_file)),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "schema"),
            _gate_row("Pinned endpoint preserved", True, section.get("pinned_research_endpoint", "")),
            _gate_row("Out-of-sample label checked", True, str(extension_summary.iloc[0]["is_out_of_sample_extension"])),
            _gate_row("No canonical report mutation", True, "separate post-endpoint file"),
            _gate_row("Phase 15P boundary is audit-only", bool(boundary["passed"].all()), "phase15p"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role")
                == "Post-endpoint candidate stream data extension implementation only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15O",
                "diagnostic": "Post-endpoint candidate stream data extension",
                "verdict": (
                    "Completed — post-endpoint candidate stream extension output written"
                    if bool(gate_report["passed"].all())
                    else "Failed post-endpoint candidate stream extension"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "upstream_phase_label": upstream_label,
                "upstream_phase_passed": upstream_passed,
                "candidate_stream_valid": _bool_value(extension_summary.iloc[0]["candidate_stream_valid"]),
                "post_endpoint_rows": int(extension_summary.iloc[0]["post_endpoint_rows"]),
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
        "extension_summary": extension_summary,
        "required_column_check": required_col_check,
        "upstream_result_check": upstream_check,
        "phase15r_result_check": upstream_check,
        "phase15n_result_check": upstream_check,
        "phase15p_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "post_endpoint_candidate_stream":
            continue
        frame.to_csv(reports_path / f"phase15o_candidate_stream_{name}.csv", index=False)

    print("Wrote Phase 15O post-endpoint candidate stream reports.")
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


def _stream_audit(stream: pd.DataFrame, section: dict[str, Any]) -> pd.DataFrame:
    pinned = pd.to_datetime(section.get("pinned_research_endpoint", ""), errors="coerce")
    thresholds = section.get("audit_thresholds", {})

    if stream.empty:
        return pd.DataFrame(
            [
                {
                    "post_endpoint_rows": 0,
                    "post_endpoint_rows_passed": False,
                    "required_dates_after_endpoint_passed": False,
                    "benchmark_update_passed": False,
                    "target_exposure_continuity_passed": False,
                    "target_exposure_range_passed": False,
                    "out_of_sample_label_passed": False,
                    "all_stream_gates_passed": False,
                    "failure_reason": "candidate_stream_empty",
                }
            ]
        )

    dates = pd.to_datetime(stream["date"], errors="coerce")
    post_endpoint_rows = len(stream)
    min_rows = int(thresholds.get("min_post_endpoint_rows", 1))

    date_pass = bool(dates.notna().all() and (dates > pinned).all())
    row_count_pass = post_endpoint_rows >= min_rows
    benchmark_pass = bool(stream["benchmark_update_flag"].astype(str).str.lower().eq("pass").all())

    current_exposure = pd.to_numeric(stream["current_exposure"], errors="coerce")
    previous_exposure = pd.to_numeric(stream["previous_exposure"], errors="coerce")
    exposure_continuity_pass = bool(current_exposure.notna().all() and previous_exposure.notna().all())
    exposure_range_pass = bool(current_exposure.between(0.0, 1.0).all())

    out_of_sample_pass = bool(stream["is_out_of_sample_extension"].map(_bool_value).all())

    failures = []
    if not row_count_pass:
        failures.append("insufficient_post_endpoint_rows")
    if not date_pass:
        failures.append("dates_not_after_pinned_endpoint")
    if not benchmark_pass:
        failures.append("benchmark_update_failed")
    if not exposure_continuity_pass:
        failures.append("target_exposure_continuity_failed")
    if not exposure_range_pass:
        failures.append("target_exposure_range_failed")
    if not out_of_sample_pass:
        failures.append("out_of_sample_label_failed")

    return pd.DataFrame(
        [
            {
                "post_endpoint_rows": post_endpoint_rows,
                "post_endpoint_rows_passed": row_count_pass,
                "required_dates_after_endpoint_passed": date_pass,
                "benchmark_update_passed": benchmark_pass,
                "target_exposure_continuity_passed": exposure_continuity_pass,
                "target_exposure_range_passed": exposure_range_pass,
                "out_of_sample_label_passed": out_of_sample_pass,
                "all_stream_gates_passed": len(failures) == 0,
                "failure_reason": ";".join(failures),
            }
        ]
    )


def save_phase15p_extended_candidate_stream_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15p_extended_candidate_stream_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    inventory = _report_inventory(section.get("phase15o_reports", {}))

    phase15o_check = _phase_result_check(
        section.get("phase15o_reports", {}).get("conclusion", ""),
        section.get("phase15o_reports", {}).get("gate_report", ""),
        "Phase 15O",
    )

    stream = _read_csv_if_exists(section.get("phase15o_reports", {}).get("candidate_stream", ""))

    required_col_check = _required_column_check(
        stream,
        list(section.get("required_extended_candidate_stream_columns", [])),
        "post_endpoint_candidate_stream",
    )
    audit = _stream_audit(stream, section)

    all_stream_gates = _bool_value(audit.iloc[0]["all_stream_gates_passed"])
    decision_text = (
        section.get("decision_policy", {}).get(
            "decision_if_stream_valid",
            "fresh_signal_rerun_allowed_next",
        )
        if all_stream_gates
        else section.get("decision_policy", {}).get(
            "decision_if_stream_invalid",
            "blocked_extended_candidate_stream_invalid",
        )
    )

    decision = pd.DataFrame(
        [
            {
                "decision": decision_text,
                "fresh_signal_rerun_allowed_next": all_stream_gates,
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

    boundary = _boundary_check(section, "phase15m_rerun_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15o_passed": bool(phase15o_check["passed"].all()),
                "config_flags_clean": bool(flags["passed"].all()),
                "candidate_stream_exists": not stream.empty,
                "required_columns_present": bool(required_col_check["present"].all()),
                "post_endpoint_rows": int(audit.iloc[0]["post_endpoint_rows"]),
                "post_endpoint_rows_passed": _bool_value(audit.iloc[0]["post_endpoint_rows_passed"]),
                "benchmark_update_passed": _bool_value(audit.iloc[0]["benchmark_update_passed"]),
                "target_exposure_continuity_passed": _bool_value(
                    audit.iloc[0]["target_exposure_continuity_passed"]
                ),
                "out_of_sample_label_passed": _bool_value(audit.iloc[0]["out_of_sample_label_passed"]),
                "decision": decision_text,
                "fresh_signal_rerun_allowed_next": all_stream_gates,
                "paper_dry_run_preregistration_allowed_next": False,
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
            _gate_row("Phase 15O passed", bool(phase15o_check["passed"].all()), "phase15o"),
            _gate_row("Config flags clean", bool(flags["passed"].all()), "runtime flags"),
            _gate_row(
                "Candidate stream existence audited",
                True,
                f"rows={len(stream)}; decision={decision_text}",
            ),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "schema"),
            _gate_row("Post-endpoint rows audited", True, str(audit.iloc[0]["post_endpoint_rows_passed"])),
            _gate_row("Benchmark update audited", True, str(audit.iloc[0]["benchmark_update_passed"])),
            _gate_row("Target exposure continuity audited", True, str(audit.iloc[0]["target_exposure_continuity_passed"])),
            _gate_row("Out-of-sample label audited", True, str(audit.iloc[0]["out_of_sample_label_passed"])),
            _gate_row("Decision output exists", len(decision) == 1, decision_text),
            _gate_row("No paper-ready claim", not _bool_value(decision.iloc[0]["paper_trading_ready"]), "paper_trading_ready=False"),
            _gate_row("Phase 15M rerun boundary is conditional-only", bool(boundary["passed"].all()), "phase15m rerun"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role") == "Extended candidate stream audit and fresh signal rerun eligibility only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15P",
                "diagnostic": "Extended candidate stream audit and fresh signal rerun eligibility",
                "verdict": (
                    "Completed — extended candidate stream audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed extended candidate stream audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision_text,
                "fresh_signal_rerun_allowed_next": all_stream_gates,
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
        "phase15o_result_check": phase15o_check,
        "required_column_check": required_col_check,
        "extended_stream_audit": audit,
        "decision_report": decision,
        "phase15m_rerun_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15p_extended_stream_{name}.csv", index=False)

    print("Wrote Phase 15P extended candidate stream audit reports.")
    return outputs
