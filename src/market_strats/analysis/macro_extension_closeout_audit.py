from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE10G_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Macro extension closeout / failure documentation audit",
    "branch": "Phase 10 macro/rates/inflation extension",
    "status": "Closed — no macro rule promoted",
    "next_allowed_step": "Phase 10H final Phase 10 checkpoint audit or architecture review",
    "successor_candidate_created": False,
    "final_candidate_changed": False,
    "macro_rule_promotion_allowed": False,
    "strategy_promotion": False,
    "expected_disabled_flags": {
        "phase10a_feature_family_feasibility_spec": False,
        "phase10b_macro_data_source_leakage_audit": False,
        "phase10c_macro_source_reliability_alignment_audit": False,
        "phase10d_diagnostic_macro_regime_analysis": False,
        "phase10e_preregistered_macro_hypothesis_spec": False,
        "phase10f_preregistered_macro_rule_test": False,
        "relative_momentum_allocator": True,
    },
    "expected_report_prefixes": [],
    "expected_markdown_reports": [],
    "phase10f_reports": {
        "conclusion": "reports/phase10f_macro_conclusion.csv",
        "rule_gate_report": "reports/phase10f_macro_rule_gate_report.csv",
        "rule_comparison_summary": "reports/phase10f_macro_rule_comparison_summary.csv",
        "discipline_gate_report": "reports/phase10f_macro_discipline_gate_report.csv",
    },
    "required_phase10f_verdict": "Failed / no pre-registered macro rule passed",
    "gates": {
        "require_expected_reports_present": True,
        "require_config_flags_clean": True,
        "require_phase10f_failure_documented": True,
        "require_no_phase10f_rule_passed": True,
        "require_phase10f_discipline_passed": True,
        "require_no_strategy_promotion": True,
        "require_no_successor_candidate": True,
        "require_final_candidate_unchanged": True,
        "require_branch_closed_without_promotion": True,
        "required_audit_role": "Macro extension closeout / failure documentation audit",
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
    user_config = config.get("phase10g_macro_extension_closeout_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE10G_CONFIG, user_config)


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


def build_phase10g_report_inventory_check(
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
                "check_type": "markdown_report",
                "expected_item": str(report_name),
                "present": report_path.exists(),
                "match_count": int(report_path.exists()),
                "matches": report_name if report_path.exists() else "",
            }
        )

    return pd.DataFrame(rows)


def build_phase10g_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for key, expected in expected_flags.items():
        actual = runtime_config.get(key, {}).get("enabled")
        passed = actual is expected

        rows.append(
            {
                "config_key": key,
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase10g_phase10f_failure_check(
    *,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase10f_reports", {})
    required_verdict = str(
        phase_config.get(
            "required_phase10f_verdict",
            "Failed / no pre-registered macro rule passed",
        )
    )

    conclusion = _read_csv_if_exists(reports.get("conclusion", ""))
    rule_gate_report = _read_csv_if_exists(reports.get("rule_gate_report", ""))
    rule_comparison = _read_csv_if_exists(reports.get("rule_comparison_summary", ""))
    discipline_gate_report = _read_csv_if_exists(
        reports.get("discipline_gate_report", "")
    )

    verdict = ""
    conclusion_strategy_promotion = False
    any_rule_passed = False

    if not conclusion.empty:
        verdict = str(conclusion.iloc[0].get("verdict", ""))
        conclusion_strategy_promotion = _bool_value(
            conclusion.iloc[0].get("strategy_promotion", False)
        )
        any_rule_passed = _bool_value(conclusion.iloc[0].get("any_rule_passed", False))

    no_rule_passed_from_rule_gate = True
    if not rule_gate_report.empty and "all_rule_gates_passed" in rule_gate_report.columns:
        no_rule_passed_from_rule_gate = not bool(
            rule_gate_report["all_rule_gates_passed"].map(_bool_value).any()
        )

    no_rule_passed_from_comparison = True
    if not rule_comparison.empty and "all_rule_gates_passed" in rule_comparison.columns:
        no_rule_passed_from_comparison = not bool(
            rule_comparison["all_rule_gates_passed"].map(_bool_value).any()
        )

    discipline_passed = False
    if (
        not discipline_gate_report.empty
        and "all_discipline_gates_passed" in discipline_gate_report.columns
    ):
        discipline_passed = bool(
            discipline_gate_report["all_discipline_gates_passed"]
            .map(_bool_value)
            .all()
        )

    rows = [
        {
            "check": "Phase 10F conclusion report exists",
            "passed": not conclusion.empty,
            "detail": f"rows={len(conclusion)}",
            "result": "Passed" if not conclusion.empty else "Failed",
        },
        {
            "check": "Phase 10F conclusion documents failure",
            "passed": required_verdict in verdict,
            "detail": f"verdict={verdict}",
            "result": "Passed" if required_verdict in verdict else "Failed",
        },
        {
            "check": "Phase 10F conclusion says no rule passed",
            "passed": not any_rule_passed,
            "detail": f"any_rule_passed={any_rule_passed}",
            "result": "Passed" if not any_rule_passed else "Failed",
        },
        {
            "check": "No Phase 10F rule passed from rule gate report",
            "passed": no_rule_passed_from_rule_gate,
            "detail": f"gate_rows={len(rule_gate_report)}",
            "result": "Passed" if no_rule_passed_from_rule_gate else "Failed",
        },
        {
            "check": "No Phase 10F rule passed from comparison summary",
            "passed": no_rule_passed_from_comparison,
            "detail": f"comparison_rows={len(rule_comparison)}",
            "result": "Passed" if no_rule_passed_from_comparison else "Failed",
        },
        {
            "check": "Phase 10F discipline gates passed",
            "passed": discipline_passed,
            "detail": f"discipline_rows={len(discipline_gate_report)}",
            "result": "Passed" if discipline_passed else "Failed",
        },
        {
            "check": "Phase 10F did not promote a strategy",
            "passed": not conclusion_strategy_promotion,
            "detail": f"strategy_promotion={conclusion_strategy_promotion}",
            "result": "Passed" if not conclusion_strategy_promotion else "Failed",
        },
    ]

    return pd.DataFrame(rows)


def build_phase10g_closeout_summary(phase_config: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "branch": str(phase_config.get("branch", "")),
                "status": str(phase_config.get("status", "")),
                "next_allowed_step": str(phase_config.get("next_allowed_step", "")),
                "successor_candidate_created": bool(
                    phase_config.get("successor_candidate_created", False)
                ),
                "final_candidate_changed": bool(
                    phase_config.get("final_candidate_changed", False)
                ),
                "macro_rule_promotion_allowed": bool(
                    phase_config.get("macro_rule_promotion_allowed", False)
                ),
                "strategy_promotion": bool(
                    phase_config.get("strategy_promotion", False)
                ),
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


def build_phase10g_gate_report(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    phase10f_failure_check: pd.DataFrame,
    closeout_summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    closeout = closeout_summary.iloc[0] if not closeout_summary.empty else {}

    expected_reports_present = (
        bool(report_inventory_check["present"].all())
        if not report_inventory_check.empty
        else False
    )
    config_flags_clean = (
        bool(config_flag_check["passed"].all())
        if not config_flag_check.empty
        else False
    )

    phase10f_failure_documented = False
    no_phase10f_rule_passed = False
    phase10f_discipline_passed = False
    no_strategy_promotion_from_phase10f = False

    if not phase10f_failure_check.empty:
        checks = phase10f_failure_check.set_index("check")
        phase10f_failure_documented = _bool_value(
            checks.loc["Phase 10F conclusion documents failure", "passed"]
        )
        no_phase10f_rule_passed = bool(
            _bool_value(checks.loc["Phase 10F conclusion says no rule passed", "passed"])
            and _bool_value(
                checks.loc[
                    "No Phase 10F rule passed from rule gate report",
                    "passed",
                ]
            )
            and _bool_value(
                checks.loc[
                    "No Phase 10F rule passed from comparison summary",
                    "passed",
                ]
            )
        )
        phase10f_discipline_passed = _bool_value(
            checks.loc["Phase 10F discipline gates passed", "passed"]
        )
        no_strategy_promotion_from_phase10f = _bool_value(
            checks.loc["Phase 10F did not promote a strategy", "passed"]
        )

    branch_closed_without_promotion = (
        "closed" in str(closeout.get("status", "")).lower()
        and not bool(closeout.get("macro_rule_promotion_allowed", True))
        and not bool(closeout.get("strategy_promotion", True))
    )

    rows = [
        _gate_row(
            "Expected Phase 10 reports are present",
            (not gates.get("require_expected_reports_present", True))
            or expected_reports_present,
            f"missing_reports={int((~report_inventory_check['present']).sum()) if not report_inventory_check.empty else 'unknown'}",
        ),
        _gate_row(
            "Config flags match closeout state",
            (not gates.get("require_config_flags_clean", True)) or config_flags_clean,
            f"flag_failures={int((~config_flag_check['passed']).sum()) if not config_flag_check.empty else 'unknown'}",
        ),
        _gate_row(
            "Phase 10F failure is documented",
            (not gates.get("require_phase10f_failure_documented", True))
            or phase10f_failure_documented,
            "Phase 10F verdict must remain failed.",
        ),
        _gate_row(
            "No Phase 10F rule passed all gates",
            (not gates.get("require_no_phase10f_rule_passed", True))
            or no_phase10f_rule_passed,
            "No pre-registered macro rule may be treated as passed.",
        ),
        _gate_row(
            "Phase 10F discipline gates passed",
            (not gates.get("require_phase10f_discipline_passed", True))
            or phase10f_discipline_passed,
            "Failure must be valid, not caused by discipline violation.",
        ),
        _gate_row(
            "No strategy promotion occurred",
            (not gates.get("require_no_strategy_promotion", True))
            or (
                no_strategy_promotion_from_phase10f
                and not bool(closeout.get("strategy_promotion", True))
            ),
            "Phase 10F and Phase 10G must not promote a strategy.",
        ),
        _gate_row(
            "No successor candidate was created",
            (not gates.get("require_no_successor_candidate", True))
            or not bool(closeout.get("successor_candidate_created", True)),
            f"successor_candidate_created={closeout.get('successor_candidate_created', True)}",
        ),
        _gate_row(
            "Final candidate remains unchanged",
            (not gates.get("require_final_candidate_unchanged", True))
            or not bool(closeout.get("final_candidate_changed", True)),
            f"final_candidate_changed={closeout.get('final_candidate_changed', True)}",
        ),
        _gate_row(
            "Macro branch is closed without promotion",
            (not gates.get("require_branch_closed_without_promotion", True))
            or branch_closed_without_promotion,
            f"status={closeout.get('status', '')}",
        ),
        _gate_row(
            "Audit role is correct",
            str(phase_config.get("audit_role", ""))
            == str(gates.get("required_audit_role", "")),
            f"audit_role={phase_config.get('audit_role', '')}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase10g_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — macro extension closed without promotion"
        interpretation = (
            "Phase 10G documented that the macro/rates/inflation branch produced "
            "useful feasibility and diagnostic evidence, but Phase 10F failed and "
            "no pre-registered macro rule was promoted. The final candidate "
            "hierarchy remains unchanged."
        )
    else:
        verdict = "Failed macro extension closeout audit"
        interpretation = (
            "Phase 10G found inconsistency in reports, config flags, Phase 10F "
            "failure documentation, or promotion boundaries. Do not proceed until "
            "the closeout record is corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 10G",
                "diagnostic": "Macro extension closeout / failure documentation audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase10g_markdown(
    *,
    report_inventory_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    phase10f_failure_check: pd.DataFrame,
    closeout_summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 10G — Macro Branch Closeout / Failure Documentation Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit closes the Phase 10 macro/rates/inflation branch without "
            "promotion after the Phase 10F pre-registered macro-rule test failed."
        ),
        "",
        (
            "It confirms that no macro rule was promoted, no successor candidate "
            "was created, and the final candidate hierarchy remains unchanged."
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
        "## Phase 10F Failure Check",
        "",
        phase10f_failure_check.to_markdown(index=False),
        "",
        "## Closeout Summary",
        "",
        closeout_summary.to_markdown(index=False),
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
        "- This is a closeout audit, not a new strategy test.",
        "- It does not reopen macro-rule testing.",
        "- It does not validate a macro rule.",
        "- It does not change the final candidate hierarchy.",
        "- Any future richer-information work should start with architecture review, not threshold tuning.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase10g_macro_extension_closeout_audit(
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
            "phase10f_failure_check": empty,
            "closeout_summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase10g_report_inventory_check(
        reports_dir=reports_path,
        phase_config=phase_config,
    )
    config_flag_check = build_phase10g_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_disabled_flags", {}),
    )
    phase10f_failure_check = build_phase10g_phase10f_failure_check(
        phase_config=phase_config,
    )
    closeout_summary = build_phase10g_closeout_summary(phase_config)
    gate_report = build_phase10g_gate_report(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        config_flag_check=config_flag_check,
        phase10f_failure_check=phase10f_failure_check,
        closeout_summary=closeout_summary,
    )
    conclusion = build_phase10g_conclusion(gate_report)

    report_inventory_check.to_csv(
        reports_path / "phase10g_macro_closeout_report_inventory_check.csv",
        index=False,
    )
    config_flag_check.to_csv(
        reports_path / "phase10g_macro_closeout_config_flag_check.csv",
        index=False,
    )
    phase10f_failure_check.to_csv(
        reports_path / "phase10g_macro_closeout_phase10f_failure_check.csv",
        index=False,
    )
    closeout_summary.to_csv(
        reports_path / "phase10g_macro_closeout_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase10g_macro_closeout_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase10g_macro_closeout_conclusion.csv",
        index=False,
    )

    write_phase10g_markdown(
        report_inventory_check=report_inventory_check,
        config_flag_check=config_flag_check,
        phase10f_failure_check=phase10f_failure_check,
        closeout_summary=closeout_summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase10g_macro_extension_closeout_audit.md",
    )

    print("Wrote Phase 10G macro extension closeout audit reports.")

    return {
        "report_inventory_check": report_inventory_check,
        "config_flag_check": config_flag_check,
        "phase10f_failure_check": phase10f_failure_check,
        "closeout_summary": closeout_summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }