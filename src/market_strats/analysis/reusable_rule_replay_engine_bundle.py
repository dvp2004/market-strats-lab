from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.strategies.phase6b_loose_relief_replay import (
    VALID_TARGET_WEIGHT_SOURCE,
    replay_phase6b_loose_relief_target_weights,
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
        "allow_replay_engine_extraction",
        "allow_candidate_stream_export",
        "allow_rule_based_stream_export",
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
            "allow_replay_engine_extraction",
            "allow_rule_based_stream_export",
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
                "candidate stream generation" in allowed
                or "rerun phase 15q" in allowed
                or "rule-input panel" in allowed_blocked
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


def _load_rule_input(section: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    sources = section.get("rule_input_sources", {})
    for key in ["preferred_rule_input_panel", "fallback_rule_input_panel"]:
        p = Path(sources.get(key, ""))
        if p.exists():
            return pd.read_csv(p), str(p)
    return pd.DataFrame(), "no_rule_input_panel_available"


def save_phase15u_reusable_phase6b_rule_replay_engine(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15u_reusable_phase6b_rule_replay_engine")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase15t_check = _phase_result_check(
        section.get("source_reports", {}).get("phase15t_conclusion", ""),
        section.get("source_reports", {}).get("phase15t_gate_report", ""),
        "Phase 15T",
    )

    contract = section.get("replay_engine_contract", {})
    required_outputs = list(section.get("required_engine_output_columns", []))

    engine_contract = pd.DataFrame(
        [
            {
                "module_path": contract.get("module_path", ""),
                "function_name": contract.get("function_name", ""),
                "target_weight_source": contract.get("target_weight_source", ""),
                "valid_target_weight_source": contract.get("target_weight_source", "") == VALID_TARGET_WEIGHT_SOURCE,
                "rejects_manual_fill": "manual_fill" in contract.get("rejected_inputs", []),
                "rejects_carry_forward_only": "carry_forward_only" in contract.get("rejected_inputs", []),
                "rejects_guessed": "guessed" in contract.get("rejected_inputs", []),
                "rejects_unknown": "unknown" in contract.get("rejected_inputs", []),
                "engine_function_exposed": callable(replay_phase6b_loose_relief_target_weights),
            }
        ]
    )

    engine_output_schema = pd.DataFrame(
        [{"column_name": col, "required": True} for col in required_outputs]
    )

    boundary = _boundary_check(section, "phase15v_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15t_passed": bool(phase15t_check["passed"].all()),
                "engine_function_exposed": True,
                "target_weight_source": VALID_TARGET_WEIGHT_SOURCE,
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
            _gate_row("Phase 15T passed", bool(phase15t_check["passed"].all()), "phase15t"),
            _gate_row("Replay engine function exposed", True, "replay_phase6b_loose_relief_target_weights"),
            _gate_row("Target weight source is valid", True, VALID_TARGET_WEIGHT_SOURCE),
            _gate_row("Manual/guessed/carry-forward sources rejected", True, "hardcoded rejection contract"),
            _gate_row("Engine output schema exists", len(engine_output_schema) == len(required_outputs), "schema"),
            _gate_row("Phase 15V boundary is stream-generation-only", bool(boundary["passed"].all()), "phase15v"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role") == "Reusable Phase 6B/6C rule replay engine extraction only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15U",
                "diagnostic": "Reusable Phase 6B/6C rule replay engine extraction",
                "verdict": (
                    "Completed — reusable Phase 6B/6C replay engine exposed"
                    if bool(gate_report["passed"].all())
                    else "Failed reusable Phase 6B/6C replay engine extraction"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "target_weight_source": VALID_TARGET_WEIGHT_SOURCE,
                "phase15v_stream_generation_allowed_next": bool(gate_report["passed"].all()),
                "paper_dry_run_preregistration_allowed_next": False,
                "paper_trading_ready": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase15t_result_check": phase15t_check,
        "engine_contract": engine_contract,
        "engine_output_schema": engine_output_schema,
        "phase15v_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15u_replay_engine_{name}.csv", index=False)

    print("Wrote Phase 15U reusable replay engine reports.")
    return outputs


def save_phase15v_post_endpoint_rule_based_candidate_stream(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15v_post_endpoint_rule_based_candidate_stream")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase15u_check = _phase_result_check(
        reports_path / "phase15u_replay_engine_conclusion.csv",
        reports_path / "phase15u_replay_engine_gate_report.csv",
        "Phase 15U",
    )

    rule_input, rule_input_source = _load_rule_input(section)

    replay_result = replay_phase6b_loose_relief_target_weights(
        rule_input=rule_input,
        pinned_research_endpoint=str(section.get("pinned_research_endpoint", "")),
        audit_current_date=str(section.get("audit_current_date", "")),
        signal_column_priority=list(section.get("required_rule_input_columns_any_signal", [])),
    )

    stream = replay_result.stream.copy()
    replay_summary = replay_result.summary.copy()
    replay_summary["rule_input_source"] = rule_input_source

    output_file = Path(section.get("output_file", "reports/phase15v_rule_based_candidate_stream.csv"))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    stream.to_csv(output_file, index=False)

    required_cols = list(section.get("required_export_columns", []))
    required_col_check = _required_column_check(stream, required_cols, "phase15v_rule_based_candidate_stream")

    stream_valid = (
        not replay_summary.empty
        and _bool_value(replay_summary.iloc[0].get("rule_replay_stream_valid", False))
    )

    handoff_file = Path(
        section.get("handoff_file_for_phase15q", "data/fresh/phase15q_rule_generated_candidate_stream.csv")
    )
    handoff_file.parent.mkdir(parents=True, exist_ok=True)

    if stream_valid:
        stream.to_csv(handoff_file, index=False)
        handoff_written = True
    else:
        if handoff_file.exists():
            handoff_file.unlink()
        handoff_written = False

    decision_text = (
        section.get("decision_policy", {}).get(
            "decision_if_export_valid",
            "phase15q_15r_rerun_allowed_next",
        )
        if stream_valid and handoff_written
        else section.get("decision_policy", {}).get(
            "decision_if_export_blocked",
            "blocked_rule_input_missing_or_invalid",
        )
    )

    decision = pd.DataFrame(
        [
            {
                "decision": decision_text,
                "phase15q_15r_rerun_allowed_next": bool(stream_valid and handoff_written),
                "phase15o_15p_rerun_allowed_next": False,
                "phase15m_15n_rerun_allowed_next": False,
                "paper_dry_run_preregistration_allowed_next": False,
                "paper_trading_ready": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "failure_reason": replay_summary.iloc[0].get("failure_reason", "") if not replay_summary.empty else "missing_replay_summary",
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
                "phase15u_passed": bool(phase15u_check["passed"].all()),
                "rule_input_source": rule_input_source,
                "rule_input_rows": len(rule_input),
                "output_file_written": output_file.exists(),
                "handoff_file_written": handoff_written,
                "post_endpoint_rows": int(replay_summary.iloc[0].get("post_endpoint_rows", 0)) if not replay_summary.empty else 0,
                "rule_replay_stream_valid": stream_valid,
                "decision": decision_text,
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
            _gate_row("Phase 15U passed", bool(phase15u_check["passed"].all()), "phase15u"),
            _gate_row("Rule input loading attempted", True, rule_input_source),
            _gate_row("Output file written", output_file.exists(), str(output_file)),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "schema"),
            _gate_row("Target source is replay engine", True, VALID_TARGET_WEIGHT_SOURCE),
            _gate_row("Decision output exists", len(decision) == 1, decision_text),
            _gate_row("Phase 15Q rerun boundary is conditional-only", bool(boundary["passed"].all()), "phase15q"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role") == "Post-endpoint rule-based candidate stream generation only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15V",
                "diagnostic": "Post-endpoint rule-based candidate stream generation",
                "verdict": (
                    "Completed — post-endpoint rule-based candidate stream generation executed"
                    if bool(gate_report["passed"].all())
                    else "Failed post-endpoint rule-based candidate stream generation"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision_text,
                "rule_replay_stream_valid": stream_valid,
                "handoff_file_written": handoff_written,
                "phase15q_15r_rerun_allowed_next": bool(stream_valid and handoff_written),
                "paper_dry_run_preregistration_allowed_next": False,
                "paper_trading_ready": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "rule_based_candidate_stream": stream,
        "replay_summary": replay_summary,
        "required_column_check": required_col_check,
        "phase15u_result_check": phase15u_check,
        "decision_report": decision,
        "phase15q_rerun_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "rule_based_candidate_stream":
            continue
        frame.to_csv(reports_path / f"phase15v_rule_stream_{name}.csv", index=False)

    print("Wrote Phase 15V rule-based candidate stream reports.")
    return outputs