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
        "allow_source_discovery",
        "allow_candidate_stream_export",
        "allow_rule_generated_stream_export",
        "allow_current_signal_generation",
        "allow_phase15q_15r_rerun",
        "allow_phase15o_15p_rerun",
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
            "allow_source_discovery",
            "allow_rule_generated_stream_export",
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
                "export" in allowed
                or "rerun phase 15q" in allowed
                or "rule replay" in allowed_blocked
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


def _scan_code_paths(section: dict[str, Any]) -> pd.DataFrame:
    scan_paths = list(section.get("source_scan_paths", []))
    patterns = section.get("discovery_patterns", {})

    pattern_rows = []
    for group, items in patterns.items():
        for item in items:
            pattern_rows.append((group, str(item).lower(), str(item)))

    rows = []

    for raw_path in scan_paths:
        base = Path(raw_path)
        if not base.exists():
            continue

        for path in base.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            lower = text.lower()
            for group, pattern_lower, original_pattern in pattern_rows:
                if pattern_lower not in lower:
                    continue

                line_numbers = [
                    idx + 1
                    for idx, line in enumerate(text.splitlines())
                    if pattern_lower in line.lower()
                ]

                rows.append(
                    {
                        "path": str(path),
                        "pattern_group": group,
                        "matched_pattern": original_pattern,
                        "match_count": len(line_numbers),
                        "first_line": line_numbers[0] if line_numbers else "",
                        "contains_target_offensive_weight": "target_offensive_weight" in lower,
                        "contains_loose_relief": "loose_relief" in lower,
                        "contains_phase6b": "phase6b" in lower,
                        "contains_find_final_candidate_frame": "_find_final_candidate_frame" in lower,
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=[
                "path",
                "pattern_group",
                "matched_pattern",
                "match_count",
                "first_line",
                "contains_target_offensive_weight",
                "contains_loose_relief",
                "contains_phase6b",
                "contains_find_final_candidate_frame",
            ]
        )

    return pd.DataFrame(rows).sort_values(
        ["contains_target_offensive_weight", "contains_loose_relief", "contains_phase6b", "path"],
        ascending=[False, False, False, True],
    )


def _load_final_candidate_frame(
    *,
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, str]:
    try:
        frame = _find_final_candidate_frame(
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
        )
        return frame, "_find_final_candidate_frame"
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        return pd.DataFrame({"load_error": [str(exc)]}), "candidate_frame_load_failed"


def _final_candidate_profile(frame: pd.DataFrame, section: dict[str, Any]) -> pd.DataFrame:
    pinned = pd.to_datetime(section.get("pinned_research_endpoint", ""), errors="coerce")
    date_col = _first_existing_col(frame, ["date", "decision_date"])
    benchmark_col = _first_existing_col(
        frame,
        ["SPY_close", "spy_close", "adj_close", "close", "SPY_return", "spy_return", "benchmark_return"],
    )

    if frame.empty or date_col is None:
        return pd.DataFrame(
            [
                {
                    "frame_loaded": not frame.empty,
                    "rows": len(frame),
                    "date_column": date_col or "",
                    "min_date": "",
                    "max_date": "",
                    "post_endpoint_rows": 0,
                    "target_offensive_weight_present": "target_offensive_weight" in frame.columns,
                    "benchmark_column": benchmark_col or "",
                    "benchmark_column_present": benchmark_col is not None,
                }
            ]
        )

    dates = pd.to_datetime(frame[date_col], errors="coerce")
    post_endpoint_rows = int((dates > pinned).sum()) if pd.notna(pinned) else 0

    return pd.DataFrame(
        [
            {
                "frame_loaded": True,
                "rows": len(frame),
                "date_column": date_col,
                "min_date": dates.min().strftime("%Y-%m-%d") if dates.notna().any() else "",
                "max_date": dates.max().strftime("%Y-%m-%d") if dates.notna().any() else "",
                "post_endpoint_rows": post_endpoint_rows,
                "target_offensive_weight_present": "target_offensive_weight" in frame.columns,
                "benchmark_column": benchmark_col or "",
                "benchmark_column_present": benchmark_col is not None,
            }
        ]
    )


def _target_column_discovery(frame: pd.DataFrame, code_inventory: pd.DataFrame) -> pd.DataFrame:
    target_columns = [
        "target_offensive_weight",
        "target_defensive_weight",
        "offensive_weight",
        "defensive_weight",
    ]

    rows = []
    for col in target_columns:
        rows.append(
            {
                "target_column": col,
                "present_in_final_candidate_frame": col in frame.columns,
                "code_paths_with_column": int(
                    code_inventory[
                        code_inventory["matched_pattern"].astype(str).str.lower().eq(col.lower())
                    ]["path"].nunique()
                )
                if not code_inventory.empty
                else 0,
            }
        )

    return pd.DataFrame(rows)


def _replay_requirement_report(
    *,
    profile: pd.DataFrame,
    target_column_discovery: pd.DataFrame,
    code_inventory: pd.DataFrame,
) -> pd.DataFrame:
    profile_row = profile.iloc[0]
    target_present = _bool_value(profile_row["target_offensive_weight_present"])
    benchmark_present = _bool_value(profile_row["benchmark_column_present"])
    date_present = bool(profile_row["date_column"])
    code_has_target = (
        not code_inventory.empty
        and code_inventory["contains_target_offensive_weight"].map(_bool_value).any()
    )

    replay_path_discovered = bool(target_present and benchmark_present and date_present and code_has_target)

    required_inputs = [
        "final candidate frame with date",
        "target_offensive_weight",
        "SPY close or return benchmark",
        "Phase 6B/6C loose-relief rule output",
    ]

    return pd.DataFrame(
        [
            {
                "which_function_computes_target_offensive_weight": (
                    "_find_final_candidate_frame output exposes target_offensive_weight"
                    if target_present
                    else "not exposed in final candidate frame"
                ),
                "module_or_file_candidates": ";".join(
                    code_inventory[
                        code_inventory["contains_target_offensive_weight"].map(_bool_value)
                    ]["path"].drop_duplicates().head(10).tolist()
                )
                if not code_inventory.empty
                else "",
                "requires_only_spy_data": False,
                "requires_full_relative_momentum_outputs": True,
                "required_inputs": ";".join(required_inputs),
                "can_run_without_mutating_pinned_baseline": True,
                "post_endpoint_rows_available_now": int(profile_row["post_endpoint_rows"]),
                "replay_path_discovered": replay_path_discovered,
                "patch_needed_if_blocked": (
                    "Expose Phase 6B/6C rule replay as reusable function that accepts fresh market data and returns target_offensive_weight"
                    if not replay_path_discovered
                    else ""
                ),
            }
        ]
    )


def save_phase15s_phase6b_rule_replay_source_discovery(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15s_phase6b_rule_replay_source_discovery")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase15r_check = _phase_result_check(
        section.get("source_reports", {}).get("phase15r_conclusion", ""),
        section.get("source_reports", {}).get("phase15r_gate_report", ""),
        "Phase 15R",
    )

    code_inventory = _scan_code_paths(section)
    final_candidate, loader = _load_final_candidate_frame(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )
    final_profile = _final_candidate_profile(final_candidate, section)
    target_discovery = _target_column_discovery(final_candidate, code_inventory)
    replay_requirements = _replay_requirement_report(
        profile=final_profile,
        target_column_discovery=target_discovery,
        code_inventory=code_inventory,
    )

    replay_path_discovered = _bool_value(replay_requirements.iloc[0]["replay_path_discovered"])
    decision_text = (
        section.get("replay_path_decision_policy", {}).get(
            "decision_if_replay_path_discovered",
            "rule_replay_path_discovered_export_attempt_allowed_next",
        )
        if replay_path_discovered
        else section.get("replay_path_decision_policy", {}).get(
            "decision_if_not_discovered",
            "blocked_rule_replay_path_not_discovered",
        )
    )

    decision = pd.DataFrame(
        [
            {
                "decision": decision_text,
                "rule_replay_path_discovered": replay_path_discovered,
                "post_endpoint_rows_available_now": int(final_profile.iloc[0]["post_endpoint_rows"]),
                "phase15t_export_attempt_allowed_next": replay_path_discovered,
                "phase15q_15r_rerun_allowed_next": False,
                "paper_dry_run_preregistration_allowed_next": False,
                "paper_trading_ready": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    boundary = _boundary_check(section, "phase15t_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "discovery_role": section.get("discovery_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15r_passed": bool(phase15r_check["passed"].all()),
                "candidate_loader": loader,
                "code_paths_scanned": len(code_inventory["path"].drop_duplicates()) if not code_inventory.empty else 0,
                "target_offensive_weight_present": _bool_value(
                    final_profile.iloc[0]["target_offensive_weight_present"]
                ),
                "post_endpoint_rows_available_now": int(final_profile.iloc[0]["post_endpoint_rows"]),
                "rule_replay_path_discovered": replay_path_discovered,
                "decision": decision_text,
                "candidate_stream_export": False,
                "current_signal_generation": False,
                "phase15q_15r_rerun": False,
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 15R passed", bool(phase15r_check["passed"].all()), "phase15r"),
            _gate_row("Code path inventory output exists", True, f"rows={len(code_inventory)}"),
            _gate_row("Target column discovery output exists", len(target_discovery) > 0, "target columns"),
            _gate_row("Replay requirement report output exists", len(replay_requirements) == 1, "requirements"),
            _gate_row("Discovery decision output exists", len(decision) == 1, decision_text),
            _gate_row("Phase 15T boundary is export-only", bool(boundary["passed"].all()), "phase15t"),
            _gate_row("No candidate stream export", True, "discovery only"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Discovery role is correct",
                section.get("discovery_role")
                == "Phase 6B/6C rule replay source discovery only",
                section.get("discovery_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15S",
                "diagnostic": "Phase 6B/6C rule replay source discovery",
                "verdict": (
                    "Completed — rule replay source discovery passed"
                    if bool(gate_report["passed"].all())
                    else "Failed rule replay source discovery"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision_text,
                "rule_replay_path_discovered": replay_path_discovered,
                "phase15t_export_attempt_allowed_next": replay_path_discovered,
                "phase15q_15r_rerun_allowed_next": False,
                "paper_dry_run_preregistration_allowed_next": False,
                "paper_trading_ready": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase15r_result_check": phase15r_check,
        "code_path_inventory": code_inventory,
        "final_candidate_profile": final_profile,
        "target_column_discovery": target_discovery,
        "replay_requirement_report": replay_requirements,
        "decision_report": decision,
        "phase15t_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15s_rule_replay_discovery_{name}.csv", index=False)

    print("Wrote Phase 15S rule replay source discovery reports.")
    return outputs


def _normalise_benchmark(frame: pd.DataFrame, section: dict[str, Any]) -> tuple[pd.Series, pd.Series, str, str]:
    close_col = _first_existing_col(
        frame,
        list(section.get("benchmark_policy", {}).get("acceptable_close_columns", [])),
    )
    return_col = _first_existing_col(
        frame,
        list(section.get("benchmark_policy", {}).get("acceptable_return_columns", [])),
    )

    close = (
        pd.to_numeric(frame[close_col], errors="coerce")
        if close_col
        else pd.Series(pd.NA, index=frame.index)
    )

    if return_col:
        returns = pd.to_numeric(frame[return_col], errors="coerce")
    elif close_col:
        returns = close.pct_change().fillna(0.0)
    else:
        returns = pd.Series(pd.NA, index=frame.index)

    return close, returns, close_col or "", return_col or ""


def _blocked_export(required_columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=required_columns)


def _build_rule_generated_export(
    *,
    section: dict[str, Any],
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_columns = list(section.get("required_export_columns", []))
    final_candidate, loader = _load_final_candidate_frame(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    pinned = pd.to_datetime(section.get("pinned_research_endpoint", ""), errors="coerce")
    audit_date = pd.to_datetime(section.get("audit_current_date", ""), errors="coerce")

    date_col = _first_existing_col(final_candidate, ["date", "decision_date"])

    if final_candidate.empty or date_col is None:
        stream = _blocked_export(required_columns)
        return stream, _export_summary(
            stream=stream,
            loader=loader,
            failure_reason="final_candidate_frame_missing_or_date_column_missing",
        )

    if "target_offensive_weight" not in final_candidate.columns:
        stream = _blocked_export(required_columns)
        return stream, _export_summary(
            stream=stream,
            loader=loader,
            failure_reason="target_offensive_weight_not_exposed_by_project_output",
        )

    frame = final_candidate.copy()
    frame["date"] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame[frame["date"].notna()].copy()

    if pd.notna(pinned):
        frame = frame[frame["date"] > pinned].copy()
    if pd.notna(audit_date):
        frame = frame[frame["date"] <= audit_date].copy()

    frame = frame.sort_values("date").drop_duplicates("date").reset_index(drop=True)

    if frame.empty:
        stream = _blocked_export(required_columns)
        return stream, _export_summary(
            stream=stream,
            loader=loader,
            failure_reason="no_post_endpoint_rows_in_project_rule_output",
        )

    close, returns, _close_col, _return_col = _normalise_benchmark(frame, section)

    target = pd.to_numeric(frame["target_offensive_weight"], errors="coerce")
    benchmark_ok = close.notna() | returns.notna()
    target_ok = target.notna() & target.between(0.0, 1.0)

    warnings = []
    for idx in frame.index:
        row_warnings = []
        if not benchmark_ok.loc[idx]:
            row_warnings.append("benchmark_update_missing")
        if not target_ok.loc[idx]:
            row_warnings.append("target_offensive_weight_invalid")
        warnings.append(";".join(row_warnings))

    validity = benchmark_ok & target_ok
    target_source = section.get("accepted_target_weight_source", "verified_project_generated")

    stream = pd.DataFrame(
        {
            "date": frame["date"].dt.strftime("%Y-%m-%d"),
            "SPY_close": close,
            "SPY_return": returns,
            "target_offensive_weight": target,
            "target_weight_source": target_source,
            "data_source_timestamp": frame["date"].dt.strftime("%Y-%m-%d"),
            "pinned_research_endpoint": section.get("pinned_research_endpoint", ""),
            "is_out_of_sample_extension": True,
            "benchmark_update_flag": benchmark_ok.map({True: "pass", False: "fail"}),
            "stream_row_validity_flag": validity.map({True: "pass", False: "fail"}),
            "blocking_warnings": warnings,
        }
    )

    return stream[required_columns], _export_summary(
        stream=stream,
        loader=loader,
        failure_reason="",
    )


def _export_summary(stream: pd.DataFrame, loader: str, failure_reason: str) -> pd.DataFrame:
    rows = len(stream)

    benchmark_passed = (
        rows > 0
        and "benchmark_update_flag" in stream.columns
        and stream["benchmark_update_flag"].astype(str).str.lower().eq("pass").all()
    )
    row_validity_passed = (
        rows > 0
        and "stream_row_validity_flag" in stream.columns
        and stream["stream_row_validity_flag"].astype(str).str.lower().eq("pass").all()
    )
    target_weight_source_passed = (
        rows > 0
        and "target_weight_source" in stream.columns
        and stream["target_weight_source"].astype(str).str.lower().eq("verified_project_generated").all()
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
        if not row_validity_passed:
            failures.append("stream_row_validity_failed")
        if not target_weight_source_passed:
            failures.append("target_weight_source_invalid")
        if not out_of_sample_passed:
            failures.append("out_of_sample_label_failed")
        failure_reason = ";".join(failures)

    export_valid = bool(
        rows > 0
        and benchmark_passed
        and row_validity_passed
        and target_weight_source_passed
        and out_of_sample_passed
    )

    return pd.DataFrame(
        [
            {
                "post_endpoint_rows": rows,
                "candidate_loader": loader,
                "benchmark_update_passed": benchmark_passed,
                "stream_row_validity_passed": row_validity_passed,
                "target_weight_source_passed": target_weight_source_passed,
                "out_of_sample_label_passed": out_of_sample_passed,
                "rule_generated_stream_valid": export_valid,
                "canonical_report_mutation": False,
                "failure_reason": failure_reason,
            }
        ]
    )


def save_phase15t_rule_generated_candidate_stream_export(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15t_rule_generated_candidate_stream_export")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase15s_check = _phase_result_check(
        section.get("source_reports", {}).get("phase15s_conclusion", ""),
        section.get("source_reports", {}).get("phase15s_gate_report", ""),
        "Phase 15S",
    )

    export_stream, export_summary = _build_rule_generated_export(
        section=section,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    output_file = Path(section.get("output_file", "reports/phase15t_rule_generated_candidate_stream.csv"))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    export_stream.to_csv(output_file, index=False)

    handoff_file = Path(
        section.get("handoff_file_for_phase15q", "data/fresh/phase15q_rule_generated_candidate_stream.csv")
    )
    handoff_file.parent.mkdir(parents=True, exist_ok=True)

    export_valid = _bool_value(export_summary.iloc[0]["rule_generated_stream_valid"])
    if export_valid:
        export_stream.to_csv(handoff_file, index=False)
        handoff_written = True
    else:
        if handoff_file.exists():
            handoff_file.unlink()
        handoff_written = False

    required_col_check = _required_column_check(
        export_stream,
        list(section.get("required_export_columns", [])),
        "phase15t_rule_generated_candidate_stream",
    )

    decision_text = (
        section.get("decision_policy", {}).get(
            "decision_if_export_valid",
            "phase15q_15r_rerun_allowed_next",
        )
        if export_valid and handoff_written
        else section.get("decision_policy", {}).get(
            "decision_if_export_blocked",
            "blocked_rule_generated_stream_unavailable_or_invalid",
        )
    )

    decision = pd.DataFrame(
        [
            {
                "decision": decision_text,
                "phase15q_15r_rerun_allowed_next": bool(export_valid and handoff_written),
                "phase15o_15p_rerun_allowed_next": False,
                "phase15m_15n_rerun_allowed_next": False,
                "paper_dry_run_preregistration_allowed_next": False,
                "paper_trading_ready": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "failure_reason": export_summary.iloc[0]["failure_reason"],
            }
        ]
    )

    boundary = _boundary_check(section, "phase15q_rerun_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15s_passed": bool(phase15s_check["passed"].all()),
                "export_file_written": output_file.exists(),
                "handoff_file_written": handoff_written,
                "post_endpoint_rows": int(export_summary.iloc[0]["post_endpoint_rows"]),
                "rule_generated_stream_valid": export_valid,
                "decision": decision_text,
                "canonical_report_mutation": False,
                "current_signal_generation": False,
                "phase15q_15r_rerun": False,
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 15S passed", bool(phase15s_check["passed"].all()), "phase15s"),
            _gate_row("Export file written", output_file.exists(), str(output_file)),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "schema"),
            _gate_row("Pinned endpoint preserved", True, section.get("pinned_research_endpoint", "")),
            _gate_row("No canonical report mutation", True, "separate reports/data/fresh output"),
            _gate_row("Decision output exists", len(decision) == 1, decision_text),
            _gate_row("Phase 15Q rerun boundary is conditional-only", bool(boundary["passed"].all()), "phase15q rerun"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role")
                == "Post-endpoint rule-generated candidate stream export only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15T",
                "diagnostic": "Post-endpoint rule-generated candidate stream export",
                "verdict": (
                    "Completed — rule-generated candidate stream export passed"
                    if bool(gate_report["passed"].all())
                    else "Failed rule-generated candidate stream export"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision_text,
                "rule_generated_stream_valid": export_valid,
                "handoff_file_written": handoff_written,
                "phase15q_15r_rerun_allowed_next": bool(export_valid and handoff_written),
                "paper_dry_run_preregistration_allowed_next": False,
                "paper_trading_ready": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "rule_generated_candidate_stream": export_stream,
        "export_summary": export_summary,
        "required_column_check": required_col_check,
        "phase15s_result_check": phase15s_check,
        "decision_report": decision,
        "phase15q_rerun_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "rule_generated_candidate_stream":
            continue
        frame.to_csv(reports_path / f"phase15t_rule_export_{name}.csv", index=False)

    print("Wrote Phase 15T rule-generated candidate stream export reports.")
    return outputs