from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE11G_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Final Phase 11 regime scoring closeout/checkpoint audit only",
    "phase_branch": "Phase 11 regime scoring architecture and diagnostic panel branch",
    "checkpoint_status": (
        "Phase 11 closed — regime scoring architecture and diagnostic panel "
        "prepared without scoring"
    ),
    "next_allowed_step": "Phase 12A score-calculation pre-registration spec only",
    "allow_score_calculation": False,
    "allow_numeric_score_weights": False,
    "allow_empirical_return_weights": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_model_training": False,
    "allow_new_data_ingestion": False,
    "allow_candidate_promotion": False,
    "expected_runtime_flags": {},
    "expected_report_prefixes": [],
    "expected_markdown_reports": [],
    "phase_conclusion_reports": {},
    "phase_gate_reports": {},
    "required_phase_verdict_fragments": {},
    "expected_boundary_reports": {},
    "branch_closure_claims": {
        "regime_score_exists": False,
        "signal_exists": False,
        "allocation_rule_exists": False,
        "strategy_test_exists": False,
        "model_exists": False,
        "new_data_ingested": False,
        "candidate_promoted": False,
        "final_candidate_changed": False,
    },
    "phase12a_boundary": {
        "allowed_next_step": "Score-calculation pre-registration spec only",
        "forbidden_next_step": (
            "actual score calculation, signal creation, allocation rule, "
            "strategy backtest, model training, new data ingestion, or "
            "candidate promotion"
        ),
        "phase12a_may_define_score_formula_spec": True,
        "phase12a_may_define_non_return_weight_policy": True,
        "phase12a_may_calculate_scores": False,
        "phase12a_may_assign_empirical_weights": False,
        "phase12a_may_create_signal": False,
        "phase12a_may_test_strategy": False,
        "phase12a_may_train_model": False,
        "phase12a_may_ingest_new_data": False,
        "phase12a_may_promote_candidate": False,
    },
    "gates": {
        "require_report_inventory_present": True,
        "require_markdown_reports_present": True,
        "require_config_flags_clean_for_run": True,
        "require_phase_conclusions_passed": True,
        "require_phase_gate_reports_passed": True,
        "require_phase11f_locked": True,
        "require_boundary_reports_passed": True,
        "require_no_score_signal_model_strategy_promotion": True,
        "require_phase12a_boundary_spec_only": True,
        "require_no_score_calculation": True,
        "require_no_numeric_score_weights": True,
        "require_no_empirical_return_weights": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_model_training": True,
        "require_no_new_data_ingestion": True,
        "require_no_candidate_promotion": True,
        "required_audit_role": (
            "Final Phase 11 regime scoring closeout/checkpoint audit only"
        ),
    },
}


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


def _get_phase_config(config: dict[str, Any]) -> dict[str, Any]:
    user_config = config.get("phase11g_final_regime_scoring_checkpoint_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE11G_CONFIG, user_config)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()

    if clean in {"true", "1", "yes", "y"}:
        return True

    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False

    return bool(value)


def _read_csv_if_exists(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)

    if not csv_path.exists():
        return pd.DataFrame()

    return pd.read_csv(csv_path)


def build_phase11g_report_inventory_check(
    *,
    reports_dir: str | Path,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports_path = Path(reports_dir)
    rows: list[dict[str, Any]] = []

    for prefix in _as_list(phase_config.get("expected_report_prefixes")):
        matches = sorted(item.name for item in reports_path.glob(f"{prefix}*"))
        rows.append(
            {
                "check_type": "prefix",
                "expected_item": str(prefix),
                "present": len(matches) > 0,
                "match_count": len(matches),
                "matches": "; ".join(matches),
            }
        )

    for report_name in _as_list(phase_config.get("expected_markdown_reports")):
        report_path = reports_path / str(report_name)
        rows.append(
            {
                "check_type": "markdown",
                "expected_item": str(report_name),
                "present": report_path.exists(),
                "match_count": int(report_path.exists()),
                "matches": str(report_name) if report_path.exists() else "",
            }
        )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["result"] = frame["present"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11g_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for config_key, expected in expected_flags.items():
        actual = runtime_config.get(config_key, {}).get("enabled")
        passed = actual is expected
        rows.append(
            {
                "config_key": str(config_key),
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase11g_phase_conclusion_check(
    *,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    conclusion_reports = phase_config.get("phase_conclusion_reports", {})
    required_fragments = phase_config.get("required_phase_verdict_fragments", {})
    rows: list[dict[str, Any]] = []

    for phase_id, path in conclusion_reports.items():
        frame = _read_csv_if_exists(path)
        verdict = ""
        all_gates_passed = False

        if not frame.empty:
            verdict = str(frame.iloc[0].get("verdict", ""))
            all_gates_passed = _bool_value(
                frame.iloc[0].get("all_gates_passed", False)
            )

        required_fragment = str(required_fragments.get(phase_id, "")).lower()
        fragment_present = required_fragment in verdict.lower()

        passed = not frame.empty and all_gates_passed and fragment_present

        rows.append(
            {
                "phase_id": str(phase_id),
                "report_path": str(path),
                "present": not frame.empty,
                "verdict": verdict,
                "all_gates_passed": all_gates_passed,
                "required_fragment": required_fragment,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase11g_phase_gate_report_check(
    *,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for phase_id, path in phase_config.get("phase_gate_reports", {}).items():
        frame = _read_csv_if_exists(path)
        gates_passed = False

        if not frame.empty and "passed" in frame.columns:
            gates_passed = bool(frame["passed"].map(_bool_value).all())

        rows.append(
            {
                "phase_id": str(phase_id),
                "report_path": str(path),
                "present": not frame.empty,
                "gate_rows": int(len(frame)),
                "passed": gates_passed,
                "result": "Passed" if gates_passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase11g_boundary_report_check(
    *,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("expected_boundary_reports", {}).items():
        frame = _read_csv_if_exists(path)
        passed = False

        if not frame.empty and "passed" in frame.columns:
            passed = bool(frame["passed"].map(_bool_value).all())

        rows.append(
            {
                "report_key": str(report_key),
                "report_path": str(path),
                "present": not frame.empty,
                "rows": int(len(frame)),
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase11g_branch_closure_check(
    *,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    claims = phase_config.get("branch_closure_claims", {})
    rows: list[dict[str, Any]] = []

    for claim, value in claims.items():
        actual = _bool_value(value)
        passed = not actual

        rows.append(
            {
                "claim": str(claim),
                "actual": actual,
                "expected": False,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase11g_phase12a_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase12a_boundary", {})

    rows = [
        {
            "boundary_item": "phase12a_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "pre-registration spec" in str(
                boundary.get("allowed_next_step", "")
            ).lower(),
        },
        {
            "boundary_item": "phase12a_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "score calculation"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "promotion"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase12a_may_define_score_formula_spec",
            "value": _bool_value(
                boundary.get("phase12a_may_define_score_formula_spec", False)
            ),
            "passed": _bool_value(
                boundary.get("phase12a_may_define_score_formula_spec", False)
            ),
        },
        {
            "boundary_item": "phase12a_may_define_non_return_weight_policy",
            "value": _bool_value(
                boundary.get("phase12a_may_define_non_return_weight_policy", False)
            ),
            "passed": _bool_value(
                boundary.get("phase12a_may_define_non_return_weight_policy", False)
            ),
        },
        {
            "boundary_item": "phase12a_may_calculate_scores",
            "value": _bool_value(boundary.get("phase12a_may_calculate_scores", True)),
            "passed": not _bool_value(
                boundary.get("phase12a_may_calculate_scores", True)
            ),
        },
        {
            "boundary_item": "phase12a_may_assign_empirical_weights",
            "value": _bool_value(
                boundary.get("phase12a_may_assign_empirical_weights", True)
            ),
            "passed": not _bool_value(
                boundary.get("phase12a_may_assign_empirical_weights", True)
            ),
        },
        {
            "boundary_item": "phase12a_may_create_signal",
            "value": _bool_value(boundary.get("phase12a_may_create_signal", True)),
            "passed": not _bool_value(
                boundary.get("phase12a_may_create_signal", True)
            ),
        },
        {
            "boundary_item": "phase12a_may_test_strategy",
            "value": _bool_value(boundary.get("phase12a_may_test_strategy", True)),
            "passed": not _bool_value(
                boundary.get("phase12a_may_test_strategy", True)
            ),
        },
        {
            "boundary_item": "phase12a_may_train_model",
            "value": _bool_value(boundary.get("phase12a_may_train_model", True)),
            "passed": not _bool_value(
                boundary.get("phase12a_may_train_model", True)
            ),
        },
        {
            "boundary_item": "phase12a_may_ingest_new_data",
            "value": _bool_value(boundary.get("phase12a_may_ingest_new_data", True)),
            "passed": not _bool_value(
                boundary.get("phase12a_may_ingest_new_data", True)
            ),
        },
        {
            "boundary_item": "phase12a_may_promote_candidate",
            "value": _bool_value(boundary.get("phase12a_may_promote_candidate", True)),
            "passed": not _bool_value(
                boundary.get("phase12a_may_promote_candidate", True)
            ),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11g_scope_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    checks = [
        ("No score calculation", "allow_score_calculation"),
        ("No numeric score weights", "allow_numeric_score_weights"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No model training", "allow_model_training"),
        ("No new data ingestion", "allow_new_data_ingestion"),
        ("No candidate promotion", "allow_candidate_promotion"),
    ]

    rows = [
        {
            "scope_item": label,
            "value": _bool_value(phase_config.get(key, True)),
            "passed": not _bool_value(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11g_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    phase_conclusion_check: pd.DataFrame,
    phase_gate_report_check: pd.DataFrame,
    boundary_report_check: pd.DataFrame,
    branch_closure_check: pd.DataFrame,
    phase12a_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    prefix_rows = (
        report_inventory_check[report_inventory_check["check_type"] == "prefix"]
        if not report_inventory_check.empty
        else pd.DataFrame()
    )
    markdown_rows = (
        report_inventory_check[report_inventory_check["check_type"] == "markdown"]
        if not report_inventory_check.empty
        else pd.DataFrame()
    )

    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "checkpoint_status": str(phase_config.get("checkpoint_status", "")),
                "next_allowed_step": str(phase_config.get("next_allowed_step", "")),
                "report_prefixes_present": bool(prefix_rows["present"].all())
                if not prefix_rows.empty
                else False,
                "markdown_reports_present": bool(markdown_rows["present"].all())
                if not markdown_rows.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "phase_conclusions_passed": bool(
                    phase_conclusion_check["passed"].all()
                )
                if not phase_conclusion_check.empty
                else False,
                "phase_gate_reports_passed": bool(
                    phase_gate_report_check["passed"].all()
                )
                if not phase_gate_report_check.empty
                else False,
                "boundary_reports_passed": bool(boundary_report_check["passed"].all())
                if not boundary_report_check.empty
                else False,
                "branch_closure_clean": bool(branch_closure_check["passed"].all())
                if not branch_closure_check.empty
                else False,
                "phase12a_boundary_passed": bool(
                    phase12a_boundary_check["passed"].all()
                )
                if not phase12a_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase11g_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [_gate_row("Phase 11G summary exists", False, "No summary was created.")]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_audit_role",
            "Final Phase 11 regime scoring closeout/checkpoint audit only",
        )
    )

    rows = [
        _gate_row(
            "Expected Phase 11 report prefixes are present",
            (not gates.get("require_report_inventory_present", True))
            or bool(row["report_prefixes_present"]),
            f"report_prefixes_present={bool(row['report_prefixes_present'])}",
        ),
        _gate_row(
            "Expected Phase 11 markdown reports are present",
            (not gates.get("require_markdown_reports_present", True))
            or bool(row["markdown_reports_present"]),
            f"markdown_reports_present={bool(row['markdown_reports_present'])}",
        ),
        _gate_row(
            "Config flags are clean for closeout run",
            (not gates.get("require_config_flags_clean_for_run", True))
            or bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Phase 11 conclusions passed",
            (not gates.get("require_phase_conclusions_passed", True))
            or bool(row["phase_conclusions_passed"]),
            f"phase_conclusions_passed={bool(row['phase_conclusions_passed'])}",
        ),
        _gate_row(
            "Phase 11 gate reports passed",
            (not gates.get("require_phase_gate_reports_passed", True))
            or bool(row["phase_gate_reports_passed"]),
            f"phase_gate_reports_passed={bool(row['phase_gate_reports_passed'])}",
        ),
        _gate_row(
            "Phase 11F is locked as passed",
            (not gates.get("require_phase11f_locked", True))
            or bool(row["phase_conclusions_passed"])
            and bool(row["phase_gate_reports_passed"]),
            "Phase 11F conclusion and gate report must remain passed.",
        ),
        _gate_row(
            "Boundary reports passed",
            (not gates.get("require_boundary_reports_passed", True))
            or bool(row["boundary_reports_passed"]),
            f"boundary_reports_passed={bool(row['boundary_reports_passed'])}",
        ),
        _gate_row(
            "No score, signal, model, strategy, or promotion exists",
            (not gates.get("require_no_score_signal_model_strategy_promotion", True))
            or bool(row["branch_closure_clean"]),
            f"branch_closure_clean={bool(row['branch_closure_clean'])}",
        ),
        _gate_row(
            "Phase 12A boundary is pre-registration-spec only",
            (not gates.get("require_phase12a_boundary_spec_only", True))
            or bool(row["phase12a_boundary_passed"]),
            f"phase12a_boundary_passed={bool(row['phase12a_boundary_passed'])}",
        ),
        _gate_row(
            "No score calculation is allowed",
            (not gates.get("require_no_score_calculation", True))
            or bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "No numeric score weights are allowed",
            (not gates.get("require_no_numeric_score_weights", True))
            or bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "No empirical return weights are allowed",
            (not gates.get("require_no_empirical_return_weights", True))
            or bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "No signal creation is allowed",
            (not gates.get("require_no_signal_creation", True))
            or bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "No allocation rule creation is allowed",
            (not gates.get("require_no_allocation_rule_creation", True))
            or bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "No strategy backtest is allowed",
            (not gates.get("require_no_strategy_backtest", True))
            or bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "No model training is allowed",
            (not gates.get("require_no_model_training", True))
            or bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "No new data ingestion is allowed",
            (not gates.get("require_no_new_data_ingestion", True))
            or bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "No candidate promotion is allowed",
            (not gates.get("require_no_candidate_promotion", True))
            or bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Audit role is correct",
            str(row["audit_role"]) == required_role,
            f"audit_role={row['audit_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase11g_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    if all_passed:
        verdict = "Completed — final Phase 11 regime scoring checkpoint passed"
        interpretation = (
            "Phase 11G closed the regime-scoring architecture and diagnostic-panel "
            "branch. Phase 11A-F reports and gates passed, diagnostic panel templates "
            "and content were verified, no score/signal/allocation rule/backtest/model/"
            "new data ingestion/promotion exists, and the next allowed step is only "
            "Phase 12A score-calculation pre-registration spec."
        )
    else:
        verdict = "Failed final Phase 11 regime scoring checkpoint"
        interpretation = (
            "Phase 11G found a report, config, boundary, conclusion, or closeout "
            "inconsistency. Do not proceed to score-calculation pre-registration."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 11G",
                "diagnostic": "Final Phase 11 regime scoring closeout/checkpoint audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase11g_markdown(
    *,
    report_inventory_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    phase_conclusion_check: pd.DataFrame,
    phase_gate_report_check: pd.DataFrame,
    boundary_report_check: pd.DataFrame,
    branch_closure_check: pd.DataFrame,
    phase12a_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 11G — Final Regime Scoring Closeout / Checkpoint Audit",
        "",
        "## Purpose",
        "",
        (
            "This combined closeout/checkpoint audit verifies that Phase 11A-F are "
            "complete, documented, and bounded. It does not calculate scores, assign "
            "weights, create signals, run backtests, ingest new data, train models, "
            "or promote a candidate."
        ),
        "",
        "## Report Inventory Check",
        "",
        report_inventory_check.to_markdown(index=False),
        "",
        "## Config Flag Check",
        "",
        config_flag_check.to_markdown(index=False),
        "",
        "## Phase Conclusion Check",
        "",
        phase_conclusion_check.to_markdown(index=False),
        "",
        "## Phase Gate Report Check",
        "",
        phase_gate_report_check.to_markdown(index=False),
        "",
        "## Boundary Report Check",
        "",
        boundary_report_check.to_markdown(index=False),
        "",
        "## Branch Closure Check",
        "",
        branch_closure_check.to_markdown(index=False),
        "",
        "## Phase 12A Boundary Check",
        "",
        phase12a_boundary_check.to_markdown(index=False),
        "",
        "## Scope Boundary Check",
        "",
        scope_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        "",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        conclusion.to_markdown(index=False),
        "",
        "## Limitations",
        "",
        "- This is a closeout/checkpoint audit only.",
        "- It does not calculate a regime score.",
        "- It does not assign score weights.",
        "- It does not create signals or allocation rules.",
        "- It does not run a strategy backtest.",
        "- It does not ingest new data or train a model.",
        "- It does not promote a candidate.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase11g_final_regime_scoring_checkpoint_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "report_inventory_check": empty,
            "config_flag_check": empty,
            "phase_conclusion_check": empty,
            "phase_gate_report_check": empty,
            "boundary_report_check": empty,
            "branch_closure_check": empty,
            "phase12a_boundary_check": empty,
            "scope_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase11g_report_inventory_check(
        reports_dir=reports_path,
        phase_config=phase_config,
    )
    config_flag_check = build_phase11g_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )
    phase_conclusion_check = build_phase11g_phase_conclusion_check(
        phase_config=phase_config,
    )
    phase_gate_report_check = build_phase11g_phase_gate_report_check(
        phase_config=phase_config,
    )
    boundary_report_check = build_phase11g_boundary_report_check(
        phase_config=phase_config,
    )
    branch_closure_check = build_phase11g_branch_closure_check(
        phase_config=phase_config,
    )
    phase12a_boundary_check = build_phase11g_phase12a_boundary_check(phase_config)
    scope_boundary_check = build_phase11g_scope_boundary_check(phase_config)
    summary = build_phase11g_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        config_flag_check=config_flag_check,
        phase_conclusion_check=phase_conclusion_check,
        phase_gate_report_check=phase_gate_report_check,
        boundary_report_check=boundary_report_check,
        branch_closure_check=branch_closure_check,
        phase12a_boundary_check=phase12a_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase11g_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11g_conclusion(gate_report)

    report_inventory_check.to_csv(
        reports_path / "phase11g_final_checkpoint_report_inventory_check.csv",
        index=False,
    )
    config_flag_check.to_csv(
        reports_path / "phase11g_final_checkpoint_config_flag_check.csv",
        index=False,
    )
    phase_conclusion_check.to_csv(
        reports_path / "phase11g_final_checkpoint_phase_conclusion_check.csv",
        index=False,
    )
    phase_gate_report_check.to_csv(
        reports_path / "phase11g_final_checkpoint_phase_gate_report_check.csv",
        index=False,
    )
    boundary_report_check.to_csv(
        reports_path / "phase11g_final_checkpoint_boundary_report_check.csv",
        index=False,
    )
    branch_closure_check.to_csv(
        reports_path / "phase11g_final_checkpoint_branch_closure_check.csv",
        index=False,
    )
    phase12a_boundary_check.to_csv(
        reports_path / "phase11g_final_checkpoint_phase12a_boundary_check.csv",
        index=False,
    )
    scope_boundary_check.to_csv(
        reports_path / "phase11g_final_checkpoint_scope_boundary_check.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase11g_final_checkpoint_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase11g_final_checkpoint_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase11g_final_checkpoint_conclusion.csv",
        index=False,
    )

    write_phase11g_markdown(
        report_inventory_check=report_inventory_check,
        config_flag_check=config_flag_check,
        phase_conclusion_check=phase_conclusion_check,
        phase_gate_report_check=phase_gate_report_check,
        boundary_report_check=boundary_report_check,
        branch_closure_check=branch_closure_check,
        phase12a_boundary_check=phase12a_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase11g_final_regime_scoring_checkpoint_audit.md",
    )

    print("Wrote Phase 11G final regime scoring checkpoint audit reports.")

    return {
        "report_inventory_check": report_inventory_check,
        "config_flag_check": config_flag_check,
        "phase_conclusion_check": phase_conclusion_check,
        "phase_gate_report_check": phase_gate_report_check,
        "boundary_report_check": boundary_report_check,
        "branch_closure_check": branch_closure_check,
        "phase12a_boundary_check": phase12a_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }