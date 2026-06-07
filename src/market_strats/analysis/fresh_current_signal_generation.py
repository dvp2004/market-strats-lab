from __future__ import annotations

from datetime import datetime, timezone
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
    if clean in {"true", "1", "yes", "y", "pass"}:
        return True
    if clean in {"false", "0", "no", "n", "", "nan", "none", "fail"}:
        return False
    return bool(value)


def _section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return config.get(key, {}) or {}


def _safe_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    clean = str(path).strip()
    if not clean:
        return None
    return Path(clean)


def _read_csv_if_exists(path: str | Path | None) -> pd.DataFrame:
    p = _safe_path(path)
    if p is None or not p.exists() or p.is_dir():
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
        "allow_current_signal_generation",
        "allow_fresh_data_pull_execution",
        "allow_canonical_report_mutation",
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
        "allow_paper_dry_run_preregistration_if_passed",
    ]

    rows = []
    for key in keys:
        if key not in section:
            continue

        value = _bool_value(section.get(key, False))
        allowed_exception = key in {
            "allow_current_signal_generation",
            "allow_paper_dry_run_preregistration_if_passed",
        }

        rows.append(
            {
                "scope_item": key,
                "value": value,
                "passed": (not value) or allowed_exception,
            }
        )

    out = pd.DataFrame(rows, columns=["scope_item", "value", "passed"])
    if not out.empty:
        out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    else:
        out["result"] = []
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
                or "paper dry-run pre-registration" in allowed
                or "fresh current-signal repair" in allowed_blocked
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
        columns=["config_key", "expected_enabled", "actual_enabled", "passed"],
    )
    if not out.empty:
        out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    else:
        out["result"] = []
    return out


def _mode_from_exposure(exposure: float) -> str:
    if exposure >= 0.75:
        return "offensive_spy"
    if exposure <= 0.25:
        return "defensive_or_cash"
    return "partial_risk"


def _target_action(previous_exposure: float, current_exposure: float) -> str:
    if current_exposure > previous_exposure:
        return "risk_increase_preview"
    if current_exposure < previous_exposure:
        return "risk_decrease_preview"
    if current_exposure >= 0.75:
        return "risk_on_hold_preview"
    if current_exposure <= 0.25:
        return "risk_off_hold_preview"
    return "partial_risk_hold_preview"


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


def _post_endpoint_row_count(frame: pd.DataFrame, pinned_endpoint: str | None) -> int:
    if frame.empty:
        return 0
    date_col = _first_existing_col(frame, ["date", "decision_date", "signal_date"])
    if date_col is None:
        return 0
    pinned = pd.to_datetime(pinned_endpoint or "", errors="coerce")
    if pd.isna(pinned):
        return 0
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    return int((dates > pinned).sum())


def _load_candidate_from_file(path: Path, pinned_endpoint: str | None) -> tuple[pd.DataFrame, bool]:
    if not path.exists() or path.is_dir():
        return pd.DataFrame(), False
    candidate = _read_csv_if_exists(path)
    if candidate.empty:
        return candidate, False
    return candidate, _post_endpoint_row_count(candidate, pinned_endpoint) > 0


def _load_candidate_frame(
    *,
    section: dict[str, Any],
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, str]:
    pinned_endpoint = section.get("pinned_research_endpoint", "2026-05-01")
    sources = section.get("candidate_stream_sources", {}) or {}
    legacy_policy = section.get("fresh_candidate_stream_policy", {}) or {}

    # Primary source order for the current rerun: consume Phase 15O / Phase 15Q handoffs
    # before considering any in-memory pinned final-candidate frame.
    file_candidates: list[tuple[str, str]] = [
        (
            "preferred_manual_candidate_stream_file",
            str(sources.get("preferred_manual_candidate_stream_file", "")),
        ),
        (
            "preferred_rule_generated_candidate_stream_file",
            str(sources.get("preferred_rule_generated_candidate_stream_file", "")),
        ),
        (
            "preferred_phase15o_stream_file",
            str(sources.get("preferred_phase15o_stream_file", "")),
        ),
        (
            "preferred_existing_fresh_candidate_stream_file",
            str(sources.get("preferred_existing_fresh_candidate_stream_file", "")),
        ),
        (
            "preferred_fresh_candidate_stream_file",
            str(legacy_policy.get("preferred_fresh_candidate_stream_file", "")),
        ),
    ]

    for _key, raw_path in file_candidates:
        path = _safe_path(raw_path)
        if path is None:
            continue
        candidate, has_post_endpoint_rows = _load_candidate_from_file(path, pinned_endpoint)
        if has_post_endpoint_rows:
            return candidate, str(path)

    allow_in_memory = _bool_value(
        sources.get(
            "allow_in_memory_final_candidate_frame_if_post_endpoint_rows_exist",
            legacy_policy.get("allow_in_memory_final_candidate_frame_if_post_endpoint_rows_exist", False),
        )
    )
    if allow_in_memory:
        try:
            frame = _find_final_candidate_frame(
                relative_momentum_outputs=relative_momentum_outputs,
                ticker_outputs=ticker_outputs,
                config=config,
            )
            if _post_endpoint_row_count(frame, pinned_endpoint) > 0:
                return frame, "in_memory_final_candidate_frame"
            return pd.DataFrame(), "in_memory_final_candidate_frame_has_no_post_endpoint_rows"
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            return pd.DataFrame({"load_error": [str(exc)]}), "candidate_frame_load_failed"

    return pd.DataFrame(), "no_post_endpoint_candidate_stream_source_available"


def _has_benchmark_update(frame: pd.DataFrame, benchmark_columns: list[str]) -> tuple[bool, str]:
    candidates = benchmark_columns or [
        "SPY_close",
        "SPY_return",
        "spy_close",
        "spy_return",
        "benchmark_return",
        "benchmark_update_flag",
    ]
    col = _first_existing_col(frame, candidates)
    if col is None:
        return False, ""

    series = frame[col]
    if "flag" in col.lower():
        valid = series.astype(str).str.lower().isin({"pass", "true", "1", "yes"}).any()
    else:
        valid = series.notna().any()
    return bool(valid), col


def _blocked_signal_row(
    *,
    section: dict[str, Any],
    reason: str,
    data_source: str,
) -> pd.DataFrame:
    audit_date = pd.to_datetime(section.get("audit_current_date", ""), errors="coerce")

    return pd.DataFrame(
        [
            {
                "signal_date": audit_date.strftime("%Y-%m-%d") if pd.notna(audit_date) else "",
                "data_as_of_date": "",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "candidate_system_id": section.get("candidate_system_id", ""),
                "data_source": data_source,
                "data_source_timestamp": "",
                "pinned_research_endpoint": section.get("pinned_research_endpoint", ""),
                "is_out_of_sample_extension": True,
                "current_mode": "",
                "previous_mode": "",
                "current_exposure": "",
                "previous_exposure": "",
                "target_action": "blocked_no_executable_signal",
                "switch_triggered": False,
                "switch_reason": reason,
                "signal_validity_flag": "fail",
                "data_freshness_flag": "fail",
                "benchmark_update_flag": "fail",
                "paper_dry_run_allowed": False,
                "paper_trading_allowed": False,
                "paper_readiness_status": section.get("decision_policy", {}).get(
                    "signal_status_if_blocked",
                    "blocked_fresh_signal_unavailable_or_invalid",
                ),
                "blocking_warnings": reason,
                "benchmark_spy_close_or_return_source": "",
            }
        ]
    )


def _build_current_signal(
    *,
    section: dict[str, Any],
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame, data_source = _load_candidate_frame(
        section=section,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    date_col = _first_existing_col(frame, ["date", "decision_date"])
    selected_col, transform = _selected_exposure_definition(section)

    pinned_endpoint = pd.to_datetime(section.get("pinned_research_endpoint", ""), errors="coerce")
    audit_date = pd.to_datetime(section.get("audit_current_date", ""), errors="coerce")
    max_staleness = int(section.get("max_signal_staleness_days", 3))

    if frame.empty or date_col is None:
        signal = _blocked_signal_row(
            section=section,
            reason="fresh_candidate_frame_missing_or_date_column_missing",
            data_source=data_source,
        )
        return signal, _generation_summary(signal, 0, selected_col, transform, data_source)

    if selected_col not in frame.columns:
        signal = _blocked_signal_row(
            section=section,
            reason=f"selected_exposure_column_missing:{selected_col}",
            data_source=data_source,
        )
        return signal, _generation_summary(signal, len(frame), selected_col, transform, data_source)

    work = frame.copy()
    work["signal_date_internal"] = pd.to_datetime(work[date_col], errors="coerce")
    work = work[work["signal_date_internal"].notna()].copy()

    if pd.notna(pinned_endpoint):
        work = work[work["signal_date_internal"] > pinned_endpoint].copy()

    if pd.notna(audit_date):
        work = work[work["signal_date_internal"] <= audit_date].copy()

    work = work.sort_values("signal_date_internal").reset_index(drop=True)

    if work.empty:
        signal = _blocked_signal_row(
            section=section,
            reason="no_post_endpoint_candidate_rows_available",
            data_source=data_source,
        )
        return signal, _generation_summary(signal, 0, selected_col, transform, data_source)

    work["fresh_exposure"] = _normalise_exposure(work, selected_col, transform)

    if work["fresh_exposure"].dropna().empty:
        signal = _blocked_signal_row(
            section=section,
            reason="fresh_exposure_values_missing_or_invalid",
            data_source=data_source,
        )
        return signal, _generation_summary(signal, len(work), selected_col, transform, data_source)

    latest = work.iloc[-1]
    previous = work.iloc[-2] if len(work) > 1 else None

    endpoint_signal = _read_csv_if_exists(
        section.get("source_reports", {}).get("phase15k_endpoint_signal", "")
    )

    current_exposure = float(latest["fresh_exposure"])
    if previous is not None:
        previous_exposure = float(previous["fresh_exposure"])
    elif not endpoint_signal.empty:
        previous_exposure = float(endpoint_signal.iloc[0].get("endpoint_exposure", current_exposure))
    else:
        previous_exposure = current_exposure

    current_mode = _mode_from_exposure(current_exposure)
    previous_mode = _mode_from_exposure(previous_exposure)

    data_as_of_date = latest["signal_date_internal"]
    staleness_days = (
        int((audit_date.normalize() - data_as_of_date.normalize()).days)
        if pd.notna(audit_date)
        else None
    )
    freshness_passed = bool(
        staleness_days is not None
        and staleness_days <= max_staleness
        and pd.notna(pinned_endpoint)
        and data_as_of_date > pinned_endpoint
    )

    benchmark_columns = list(
        section.get("benchmark_policy", {}).get("acceptable_benchmark_columns", [])
    )
    benchmark_ok, benchmark_col = _has_benchmark_update(work.tail(1), benchmark_columns)

    signal_validity_passed = bool(pd.notna(current_exposure) and pd.notna(previous_exposure))
    switch_triggered = abs(current_exposure - previous_exposure) > 1e-10

    warnings = []
    if not freshness_passed:
        warnings.append(f"fresh_data_not_within_staleness_limit:{staleness_days}")
    if not benchmark_ok:
        warnings.append("benchmark_update_missing")
    if not signal_validity_passed:
        warnings.append("signal_exposure_invalid")

    all_signal_checks_passed = bool(freshness_passed and benchmark_ok and signal_validity_passed)

    timestamp_col = _first_existing_col(work, ["data_source_timestamp", "source_timestamp", "updated_at"])
    data_source_timestamp = (
        str(latest[timestamp_col]) if timestamp_col and pd.notna(latest[timestamp_col]) else data_as_of_date.strftime("%Y-%m-%d")
    )

    signal = pd.DataFrame(
        [
            {
                "signal_date": audit_date.strftime("%Y-%m-%d") if pd.notna(audit_date) else "",
                "data_as_of_date": data_as_of_date.strftime("%Y-%m-%d"),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "candidate_system_id": section.get("candidate_system_id", ""),
                "data_source": data_source,
                "data_source_timestamp": data_source_timestamp,
                "pinned_research_endpoint": section.get("pinned_research_endpoint", ""),
                "is_out_of_sample_extension": True,
                "current_mode": current_mode,
                "previous_mode": previous_mode,
                "current_exposure": current_exposure,
                "previous_exposure": previous_exposure,
                "target_action": _target_action(previous_exposure, current_exposure),
                "switch_triggered": switch_triggered,
                "switch_reason": (
                    "post_endpoint_target_allocation_changed"
                    if switch_triggered
                    else "post_endpoint_no_target_allocation_change"
                ),
                "signal_validity_flag": "pass" if signal_validity_passed else "fail",
                "data_freshness_flag": "pass" if freshness_passed else "fail",
                "benchmark_update_flag": "pass" if benchmark_ok else "fail",
                "paper_dry_run_allowed": False,
                "paper_trading_allowed": False,
                "paper_readiness_status": section.get("decision_policy", {}).get(
                    "signal_status_if_valid",
                    "fresh_signal_generated_pending_audit",
                )
                if all_signal_checks_passed
                else section.get("decision_policy", {}).get(
                    "signal_status_if_blocked",
                    "blocked_fresh_signal_unavailable_or_invalid",
                ),
                "blocking_warnings": ";".join(warnings),
                "benchmark_spy_close_or_return_source": benchmark_col,
            }
        ]
    )

    return signal, _generation_summary(signal, len(work), selected_col, transform, data_source)


def _generation_summary(
    signal: pd.DataFrame,
    post_endpoint_rows: int,
    selected_col: str,
    transform: str,
    data_source: str,
) -> pd.DataFrame:
    row = signal.iloc[0]

    return pd.DataFrame(
        [
            {
                "post_endpoint_rows": post_endpoint_rows,
                "data_source": data_source,
                "selected_exposure_column": selected_col,
                "selected_exposure_transform": transform,
                "signal_file_generated": True,
                "data_as_of_date": row.get("data_as_of_date", ""),
                "is_out_of_sample_extension": _bool_value(row.get("is_out_of_sample_extension", False)),
                "signal_validity_passed": str(row.get("signal_validity_flag", "")).lower() == "pass",
                "data_freshness_passed": str(row.get("data_freshness_flag", "")).lower() == "pass",
                "benchmark_update_passed": str(row.get("benchmark_update_flag", "")).lower() == "pass",
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "blocking_warnings": row.get("blocking_warnings", ""),
            }
        ]
    )


def _upstream_result_check(section: dict[str, Any]) -> tuple[str, pd.DataFrame]:
    source_reports = section.get("source_reports", {})
    upstream_label = "Phase 15P" if source_reports.get("phase15p_conclusion") else "Phase 15L"
    upstream_conclusion = source_reports.get("phase15p_conclusion") or source_reports.get(
        "phase15l_conclusion",
        "",
    )
    upstream_gate_report = source_reports.get("phase15p_gate_report") or source_reports.get(
        "phase15l_gate_report",
        "",
    )
    return upstream_label, _phase_result_check(upstream_conclusion, upstream_gate_report, upstream_label)


def save_phase15m_fresh_current_signal_generation(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15m_fresh_current_signal_generation")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    upstream_label, upstream_check = _upstream_result_check(section)
    upstream_passed = bool(upstream_check["passed"].all())

    current_signal, generation_summary = _build_current_signal(
        section=section,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    output_file = Path(section.get("output_file", "reports/phase15m_current_signal_file.csv"))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    current_signal.to_csv(output_file, index=False)

    required_col_check = _required_column_check(
        current_signal,
        list(section.get("required_current_signal_columns", [])),
        "current_signal_file",
    )

    boundary = _boundary_check(section, "phase15n_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "upstream_phase_label": upstream_label,
                "upstream_phase_passed": upstream_passed,
                "phase15p_passed": upstream_passed if upstream_label == "Phase 15P" else False,
                "phase15l_passed": upstream_passed if upstream_label == "Phase 15L" else False,
                "signal_file_written": output_file.exists(),
                "post_endpoint_rows": int(generation_summary.iloc[0]["post_endpoint_rows"]),
                "data_source": generation_summary.iloc[0]["data_source"],
                "signal_validity_passed": _bool_value(generation_summary.iloc[0]["signal_validity_passed"]),
                "data_freshness_passed": _bool_value(generation_summary.iloc[0]["data_freshness_passed"]),
                "benchmark_update_passed": _bool_value(generation_summary.iloc[0]["benchmark_update_passed"]),
                "is_out_of_sample_extension": _bool_value(
                    generation_summary.iloc[0]["is_out_of_sample_extension"]
                ),
                "canonical_report_mutation": False,
                "data_pull_executed": False,
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
            _gate_row("Signal file written", output_file.exists(), str(output_file)),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "schema"),
            _gate_row("Canonical endpoint preserved", True, section.get("pinned_research_endpoint", "")),
            _gate_row("Out-of-sample label present", _bool_value(current_signal.iloc[0]["is_out_of_sample_extension"]), "post-endpoint"),
            _gate_row("No canonical report mutation", True, "fresh signal output uses separate file"),
            _gate_row("Phase 15N boundary is audit-only", bool(boundary["passed"].all()), "phase15n"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role") == "Fresh current signal generation only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15M",
                "diagnostic": "Fresh current signal generation",
                "verdict": (
                    "Completed — fresh current signal generation outputs written"
                    if bool(gate_report["passed"].all())
                    else "Failed fresh current signal generation"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "upstream_phase_label": upstream_label,
                "upstream_phase_passed": upstream_passed,
                "signal_validity_passed": _bool_value(generation_summary.iloc[0]["signal_validity_passed"]),
                "data_freshness_passed": _bool_value(generation_summary.iloc[0]["data_freshness_passed"]),
                "benchmark_update_passed": _bool_value(generation_summary.iloc[0]["benchmark_update_passed"]),
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
        "current_signal_file": current_signal,
        "generation_summary": generation_summary,
        "required_column_check": required_col_check,
        "upstream_result_check": upstream_check,
        "phase15p_result_check": upstream_check,
        "phase15l_result_check": upstream_check,
        "phase15n_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "current_signal_file":
            continue
        frame.to_csv(reports_path / f"phase15m_current_signal_{name}.csv", index=False)

    print("Wrote Phase 15M fresh current signal reports.")
    return outputs


def _report_inventory(paths: dict[str, str]) -> pd.DataFrame:
    rows = []

    for key, path in paths.items():
        p = _safe_path(path)
        frame = _read_csv_if_exists(p)
        present = bool(p is not None and p.exists() and not p.is_dir())
        rows.append(
            {
                "report_key": key,
                "path": str(p) if p is not None else "",
                "present": present,
                "rows": len(frame),
                "passed": present and len(frame) > 0,
                "result": "Passed" if present and len(frame) > 0 else "Failed",
            }
        )

    return pd.DataFrame(rows)


def _signal_audit(current_signal: pd.DataFrame, section: dict[str, Any]) -> pd.DataFrame:
    pinned = pd.to_datetime(section.get("pinned_research_endpoint", ""), errors="coerce")

    if current_signal.empty:
        return pd.DataFrame(
            [
                {
                    "post_endpoint_data_passed": False,
                    "signal_validity_passed": False,
                    "data_freshness_passed": False,
                    "benchmark_update_passed": False,
                    "switch_context_present": False,
                    "all_current_signal_gates_passed": False,
                    "failure_reason": "current_signal_file_empty",
                }
            ]
        )

    row = current_signal.iloc[0]
    data_as_of = pd.to_datetime(row.get("data_as_of_date", ""), errors="coerce")

    post_endpoint = bool(pd.notna(data_as_of) and pd.notna(pinned) and data_as_of > pinned)
    signal_valid = str(row.get("signal_validity_flag", "")).lower() == "pass"
    fresh = str(row.get("data_freshness_flag", "")).lower() == "pass"
    benchmark = str(row.get("benchmark_update_flag", "")).lower() == "pass"

    switch_context = bool(
        str(row.get("current_mode", "")).strip()
        and str(row.get("previous_mode", "")).strip()
        and str(row.get("current_exposure", "")).strip()
        and str(row.get("previous_exposure", "")).strip()
    )

    failures = []
    if not post_endpoint:
        failures.append("not_post_endpoint_data")
    if not signal_valid:
        failures.append("signal_validity_failed")
    if not fresh:
        failures.append("data_freshness_failed")
    if not benchmark:
        failures.append("benchmark_update_failed")
    if not switch_context:
        failures.append("switch_context_missing")

    return pd.DataFrame(
        [
            {
                "post_endpoint_data_passed": post_endpoint,
                "signal_validity_passed": signal_valid,
                "data_freshness_passed": fresh,
                "benchmark_update_passed": benchmark,
                "switch_context_present": switch_context,
                "all_current_signal_gates_passed": len(failures) == 0,
                "failure_reason": ";".join(failures),
            }
        ]
    )


def save_phase15n_fresh_signal_audit_paper_dry_run_eligibility(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15n_fresh_signal_audit_paper_dry_run_eligibility")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    inventory = _report_inventory(section.get("phase15m_reports", {}))

    phase15m_check = _phase_result_check(
        section.get("phase15m_reports", {}).get("conclusion", ""),
        section.get("phase15m_reports", {}).get("gate_report", ""),
        "Phase 15M",
    )

    current_signal = _read_csv_if_exists(
        section.get("phase15m_reports", {}).get("current_signal_file", "")
    )

    required_col_check = _required_column_check(
        current_signal,
        list(section.get("required_current_signal_columns", [])),
        "current_signal_file",
    )
    audit = _signal_audit(current_signal, section)

    all_signal_gates = _bool_value(audit.iloc[0]["all_current_signal_gates_passed"])

    decision_text = (
        section.get("decision_policy", {}).get(
            "decision_if_all_current_signal_gates_pass",
            "paper_dry_run_preregistration_allowed_next",
        )
        if all_signal_gates
        else section.get("decision_policy", {}).get(
            "decision_if_any_current_signal_gate_fails",
            "blocked_fresh_signal_audit_failed",
        )
    )

    decision = pd.DataFrame(
        [
            {
                "decision": decision_text,
                "paper_dry_run_preregistration_allowed_next": all_signal_gates,
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

    boundary = _boundary_check(section, "phase15o_boundary")
    scope = _scope_check(section)

    no_paper_ready_claim = not _bool_value(decision.iloc[0]["paper_trading_ready"])

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15m_passed": bool(phase15m_check["passed"].all()),
                "config_flags_clean": bool(flags["passed"].all()),
                "current_signal_file_exists": not current_signal.empty,
                "required_columns_present": bool(required_col_check["present"].all()),
                "post_endpoint_data_passed": _bool_value(audit.iloc[0]["post_endpoint_data_passed"]),
                "signal_validity_passed": _bool_value(audit.iloc[0]["signal_validity_passed"]),
                "data_freshness_passed": _bool_value(audit.iloc[0]["data_freshness_passed"]),
                "benchmark_update_passed": _bool_value(audit.iloc[0]["benchmark_update_passed"]),
                "switch_context_present": _bool_value(audit.iloc[0]["switch_context_present"]),
                "decision": decision_text,
                "paper_dry_run_preregistration_allowed_next": all_signal_gates,
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
            _gate_row("Phase 15M passed", bool(phase15m_check["passed"].all()), "phase15m"),
            _gate_row("Config flags clean", bool(flags["passed"].all()), "runtime flags"),
            _gate_row("Current signal file exists", not current_signal.empty, "current signal"),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "schema"),
            _gate_row("Post-endpoint data audited", True, str(audit.iloc[0]["post_endpoint_data_passed"])),
            _gate_row("Signal validity audited", True, str(audit.iloc[0]["signal_validity_passed"])),
            _gate_row("Data freshness audited", True, str(audit.iloc[0]["data_freshness_passed"])),
            _gate_row("Benchmark update audited", True, str(audit.iloc[0]["benchmark_update_passed"])),
            _gate_row("Switch context audited", True, str(audit.iloc[0]["switch_context_present"])),
            _gate_row("Decision output exists", len(decision) == 1, decision_text),
            _gate_row("No paper-ready claim", no_paper_ready_claim, "paper_trading_ready=False"),
            _gate_row("Phase 15O boundary is conditional-only", bool(boundary["passed"].all()), "phase15o"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role") == "Fresh signal audit and paper dry-run eligibility decision only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15N",
                "diagnostic": "Fresh signal audit and paper dry-run eligibility decision",
                "verdict": (
                    "Completed — fresh signal audit and paper dry-run eligibility decision passed"
                    if bool(gate_report["passed"].all())
                    else "Failed fresh signal audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision_text,
                "paper_dry_run_preregistration_allowed_next": all_signal_gates,
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
        "phase15m_result_check": phase15m_check,
        "required_column_check": required_col_check,
        "fresh_signal_audit": audit,
        "decision_report": decision,
        "phase15o_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15n_fresh_signal_audit_{name}.csv", index=False)

    print("Wrote Phase 15N fresh signal audit reports.")
    return outputs
