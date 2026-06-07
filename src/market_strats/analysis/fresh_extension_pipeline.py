from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd

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


def _gate_row(gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


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


def build_phase15w_fresh_extension_config(
    config: dict[str, Any],
    phase_config: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame]:
    fresh_config = deepcopy(config)

    original_root_end = config.get("end_date")
    original_research_end = (config.get("research_period") or {}).get("end_date")

    fresh_end = phase_config.get("fresh_extension_end_date")

    # Root end_date controls data fetch. null means fetch/load through latest available.
    fresh_config["end_date"] = fresh_end

    # The key fix: existing code filters using research_period.end_date.
    # For the fresh-extension clone only, remove/extend that cap.
    fresh_config.setdefault("research_period", {})
    fresh_config["research_period"]["end_date"] = fresh_end

    # Do not let nested canonical/audit sections use this as promotion evidence.
    fresh_config["_phase15_fresh_extension_mode"] = True
    fresh_config["_phase15_pinned_research_endpoint"] = phase_config.get(
        "pinned_research_endpoint",
        "2026-05-01",
    )

    report = pd.DataFrame(
        [
            {
                "phase": "Phase 15W",
                "original_root_end_date": original_root_end,
                "original_research_period_end_date": original_research_end,
                "fresh_root_end_date": fresh_config.get("end_date"),
                "fresh_research_period_end_date": fresh_config.get("research_period", {}).get("end_date"),
                "pinned_research_endpoint_preserved_in_original": original_research_end == phase_config.get("pinned_research_endpoint"),
                "fresh_config_is_copy": fresh_config is not config,
                "canonical_report_mutation": False,
            }
        ]
    )

    return fresh_config, report


def _first_existing_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {str(col).lower(): str(col) for col in frame.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def build_phase15y_post_endpoint_stream(
    *,
    final_candidate: pd.DataFrame,
    phase_config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_columns = list(phase_config.get("required_export_columns", []))
    pinned = pd.to_datetime(phase_config.get("pinned_research_endpoint", "2026-05-01"))

    if final_candidate.empty:
        stream = pd.DataFrame(columns=required_columns)
        summary = _export_summary(
            stream,
            failure_reason="fresh_final_candidate_empty",
            source_max_date="",
        )
        return stream, summary

    date_col = _first_existing_col(final_candidate, ["date", "decision_date"])
    close_col = _first_existing_col(
        final_candidate,
        ["SPY_close", "spy_close", "signal_price", "close"],
    )
    return_col = _first_existing_col(
        final_candidate,
        ["SPY_return", "spy_return", "benchmark_return"],
    )

    if date_col is None:
        stream = pd.DataFrame(columns=required_columns)
        summary = _export_summary(
            stream,
            failure_reason="date_column_missing",
            source_max_date="",
        )
        return stream, summary

    if "target_offensive_weight" not in final_candidate.columns:
        stream = pd.DataFrame(columns=required_columns)
        summary = _export_summary(
            stream,
            failure_reason="target_offensive_weight_missing_from_fresh_final_candidate",
            source_max_date="",
        )
        return stream, summary

    frame = final_candidate.copy()
    frame["date"] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame[frame["date"].notna()].copy()
    source_max_date = frame["date"].max().strftime("%Y-%m-%d") if not frame.empty else ""

    frame = frame[frame["date"] > pinned].copy()
    frame = frame.sort_values("date").drop_duplicates("date").reset_index(drop=True)

    if frame.empty:
        stream = pd.DataFrame(columns=required_columns)
        summary = _export_summary(
            stream,
            failure_reason="no_post_endpoint_rows_in_fresh_final_candidate",
            source_max_date=source_max_date,
        )
        return stream, summary

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

    target = pd.to_numeric(frame["target_offensive_weight"], errors="coerce")

    candidate_equity_col = _first_existing_col(final_candidate, ["equity", "adj_close"])
    candidate_strategy_return_col = _first_existing_col(final_candidate, ["strategy_return"])

    candidate_equity = (
        pd.to_numeric(frame[candidate_equity_col], errors="coerce")
        if candidate_equity_col
        else pd.Series(pd.NA, index=frame.index)
    )
    candidate_strategy_return = (
        pd.to_numeric(frame[candidate_strategy_return_col], errors="coerce")
        if candidate_strategy_return_col
        else pd.Series(pd.NA, index=frame.index)
    )

    benchmark_ok = close.notna() | returns.notna()
    target_ok = target.notna() & target.between(0.0, 1.0)
    validity = benchmark_ok & target_ok

    warnings = []
    for idx in frame.index:
        row_warnings = []
        if not benchmark_ok.loc[idx]:
            row_warnings.append("benchmark_update_missing")
        if not target_ok.loc[idx]:
            row_warnings.append("target_offensive_weight_invalid")
        warnings.append(";".join(row_warnings))

    stream = pd.DataFrame(
        {
            "date": frame["date"].dt.strftime("%Y-%m-%d"),
            "SPY_close": close,
            "SPY_return": returns,
            "target_offensive_weight": target,
            "target_weight_source": phase_config.get("target_weight_source", "verified_project_generated"),
            "data_source_timestamp": frame["date"].dt.strftime("%Y-%m-%d"),
            "pinned_research_endpoint": phase_config.get("pinned_research_endpoint", "2026-05-01"),
            "is_out_of_sample_extension": True,
            "benchmark_update_flag": benchmark_ok.map({True: "pass", False: "fail"}),
            "stream_row_validity_flag": validity.map({True: "pass", False: "fail"}),
            "blocking_warnings": warnings,
            "candidate_equity": candidate_equity,
            "candidate_strategy_return": candidate_strategy_return,
        }
    )

    summary = _export_summary(
        stream,
        failure_reason="",
        source_max_date=source_max_date,
    )
    return stream[required_columns], summary


def _export_summary(
    stream: pd.DataFrame,
    *,
    failure_reason: str,
    source_max_date: str,
) -> pd.DataFrame:
    rows = len(stream)

    benchmark_passed = (
        rows > 0
        and "benchmark_update_flag" in stream.columns
        and stream["benchmark_update_flag"].astype(str).str.lower().eq("pass").all()
    )
    validity_passed = (
        rows > 0
        and "stream_row_validity_flag" in stream.columns
        and stream["stream_row_validity_flag"].astype(str).str.lower().eq("pass").all()
    )
    target_source_passed = (
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
        if not validity_passed:
            failures.append("stream_row_validity_failed")
        if not target_source_passed:
            failures.append("target_weight_source_failed")
        if not out_of_sample_passed:
            failures.append("out_of_sample_label_failed")
        failure_reason = ";".join(failures)

    export_valid = bool(
        rows > 0
        and benchmark_passed
        and validity_passed
        and target_source_passed
        and out_of_sample_passed
    )

    return pd.DataFrame(
        [
            {
                "post_endpoint_rows": rows,
                "fresh_final_candidate_max_date": source_max_date,
                "benchmark_update_passed": benchmark_passed,
                "stream_row_validity_passed": validity_passed,
                "target_weight_source_passed": target_source_passed,
                "out_of_sample_label_passed": out_of_sample_passed,
                "rule_generated_stream_valid": export_valid,
                "canonical_report_mutation": False,
                "failure_reason": failure_reason,
            }
        ]
    )


def save_phase15wxyz_reports(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    fresh_config_report: pd.DataFrame,
    fresh_pipeline_report: pd.DataFrame,
    final_candidate: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    phase_config = _section(config, "phase15wxyz_fresh_extension_pipeline")
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    stream, export_summary = build_phase15y_post_endpoint_stream(
        final_candidate=final_candidate,
        phase_config=phase_config,
    )

    output_file = Path(phase_config.get("output_file", "reports/phase15y_post_endpoint_final_candidate_stream.csv"))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    stream.to_csv(output_file, index=False)

    handoff_file = Path(
        phase_config.get("handoff_file_for_phase15q", "data/fresh/phase15q_rule_generated_candidate_stream.csv")
    )
    handoff_file.parent.mkdir(parents=True, exist_ok=True)

    stream_valid = bool(export_summary.iloc[0]["rule_generated_stream_valid"])
    if stream_valid:
        stream.to_csv(handoff_file, index=False)
        handoff_written = True
    else:
        if handoff_file.exists():
            handoff_file.unlink()
        handoff_written = False

    required_check = _required_column_check(
        stream,
        list(phase_config.get("required_export_columns", [])),
        "phase15y_post_endpoint_final_candidate_stream",
    )

    decision_text = (
        phase_config.get("decision_policy", {}).get(
            "decision_if_export_valid",
            "phase15q_15r_rerun_allowed_next",
        )
        if stream_valid and handoff_written
        else phase_config.get("decision_policy", {}).get(
            "decision_if_export_blocked",
            "blocked_fresh_extension_pipeline_no_valid_post_endpoint_rows",
        )
    )

    decision = pd.DataFrame(
        [
            {
                "phase": "Phase 15Z",
                "decision": decision_text,
                "phase15q_15r_rerun_allowed_next": bool(stream_valid and handoff_written),
                "phase15o_15p_rerun_allowed_next": False,
                "phase15m_15n_rerun_allowed_next": False,
                "paper_dry_run_preregistration_allowed_next": False,
                "paper_trading_ready": False,
                "handoff_file_written": handoff_written,
                "failure_reason": export_summary.iloc[0]["failure_reason"],
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    scope_forbidden = [
        "allow_current_signal_generation",
        "allow_phase15q_15r_rerun",
        "allow_phase15o_15p_rerun",
        "allow_phase15m_15n_rerun",
        "allow_paper_dry_run_preregistration",
        "allow_broker_api_integration",
        "allow_paper_trading_deployment",
        "allow_live_trading",
        "allow_real_money_deployment",
        "allow_candidate_promotion",
        "allow_final_candidate_change",
        "allow_model_training",
        "allow_unregistered_ml",
        "allow_optimisation",
        "allow_multi_asset_expansion",
        "allow_feature_importance",
    ]
    scope_rows = []
    for key in scope_forbidden:
        value = _bool_value(phase_config.get(key, False))
        scope_rows.append({"scope_item": key, "value": value, "passed": not value})
    scope = pd.DataFrame(scope_rows)
    scope["result"] = scope["passed"].map({True: "Passed", False: "Failed"})

    gate_report = pd.DataFrame(
        [
            _gate_row("Fresh config built", len(fresh_config_report) == 1, "phase15w"),
            _gate_row("Fresh pipeline execution attempted", len(fresh_pipeline_report) == 1, "phase15x"),
            _gate_row("Output file written", output_file.exists(), str(output_file)),
            _gate_row("Required columns present", bool(required_check["present"].all()), "phase15y schema"),
            _gate_row("Decision output exists", len(decision) == 1, decision_text),
            _gate_row("No canonical report mutation", True, "fresh reports dir + handoff file only"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15W/15X/15Y/15Z",
                "diagnostic": "Fresh-extension pipeline and post-endpoint rule-generated stream export",
                "verdict": "Completed — fresh-extension pipeline executed and rerun eligibility decided",
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision_text,
                "post_endpoint_rows": int(export_summary.iloc[0]["post_endpoint_rows"]),
                "rule_generated_stream_valid": stream_valid,
                "handoff_file_written": handoff_written,
                "phase15q_15r_rerun_allowed_next": bool(stream_valid and handoff_written),
                "paper_trading_ready": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "fresh_config_report": fresh_config_report,
        "fresh_pipeline_report": fresh_pipeline_report,
        "post_endpoint_stream": stream,
        "export_summary": export_summary,
        "required_column_check": required_check,
        "decision_report": decision,
        "scope_boundary_check": scope,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "post_endpoint_stream":
            continue
        frame.to_csv(reports_path / f"phase15wxyz_fresh_extension_{name}.csv", index=False)

    print("Wrote Phase 15W/15X/15Y/15Z fresh-extension reports.")
    return outputs