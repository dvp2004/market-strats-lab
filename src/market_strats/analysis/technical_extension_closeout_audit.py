from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE9E_CONFIG: dict[str, Any] = {
    "enabled": False,
    "closeout_scope": {
        "branch": "Phase 9 technical indicator extension",
        "status": "Closed — no rule promoted",
        "successor_candidate_created": False,
        "final_candidate_changed": False,
        "rule_promotion_allowed": False,
        "next_allowed_step": "Phase 9 final README/checkpoint consistency or pause",
    },
    "expected_disabled_flags": {},
    "expected_report_prefixes": [],
    "phase9d_expected": {
        "conclusion_verdict": "Failed / no pre-registered rule passed",
        "no_passed_rules": True,
        "no_strategy_promotion": True,
        "no_successor_candidate": True,
    },
    "required_closeout_wording": [],
    "gates": {
        "require_expected_reports_present": True,
        "require_config_flags_match": True,
        "require_phase9d_failure_documented": True,
        "require_no_phase9d_rule_passed": True,
        "require_no_strategy_promotion": True,
        "require_no_successor_candidate": True,
        "require_branch_closed_without_promotion": True,
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
    user_config = config.get("phase9e_technical_extension_closeout_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE9E_CONFIG, user_config)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()

    if clean in {"true", "1", "yes", "y"}:
        return True

    if clean in {"false", "0", "no", "n", ""}:
        return False

    return bool(value)


def _load_report(reports_dir: str | Path, filename: str) -> pd.DataFrame:
    path = Path(reports_dir) / filename

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def _get_enabled_flag(config: dict[str, Any], key: str) -> bool | None:
    value = config.get(key)

    if not isinstance(value, dict):
        return None

    enabled = value.get("enabled")

    if enabled is None:
        return None

    return bool(enabled)


def build_phase9e_report_inventory_check(
    *,
    reports_dir: str | Path,
    expected_report_prefixes: list[str],
) -> pd.DataFrame:
    reports_path = Path(reports_dir)
    existing_names = (
        [path.name for path in reports_path.glob("*") if path.is_file()]
        if reports_path.exists()
        else []
    )

    rows: list[dict[str, Any]] = []

    for prefix in expected_report_prefixes:
        matches = sorted(name for name in existing_names if name.startswith(prefix))
        rows.append(
            {
                "expected_prefix": prefix,
                "matching_file_count": len(matches),
                "matching_files": "; ".join(matches[:12]),
                "passed": bool(matches),
                "result": "Passed" if matches else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase9e_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, bool],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for key, expected in expected_flags.items():
        actual = _get_enabled_flag(runtime_config, str(key))
        passed = actual == bool(expected)

        rows.append(
            {
                "config_key": str(key),
                "expected_enabled": bool(expected),
                "actual_enabled": actual,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase9e_phase9d_failure_check(
    *,
    reports_dir: str | Path,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    expected = phase_config.get("phase9d_expected", {})
    expected_verdict = str(expected.get("conclusion_verdict", ""))

    conclusion = _load_report(
        reports_dir,
        "phase9d_preregistered_rule_conclusion.csv",
    )
    gate_report = _load_report(
        reports_dir,
        "phase9d_preregistered_rule_gate_report.csv",
    )
    comparison = _load_report(
        reports_dir,
        "phase9d_preregistered_rule_comparison_summary.csv",
    )

    verdict = ""
    passed_rules = ""
    phase9d_failure_documented = False

    if not conclusion.empty:
        verdict = str(conclusion.iloc[0].get("verdict", ""))
        passed_rules = str(conclusion.iloc[0].get("passed_rules", "")).strip()
        phase9d_failure_documented = verdict == expected_verdict

    no_passed_rules = True

    if not gate_report.empty and "all_rule_gates_passed" in gate_report.columns:
        no_passed_rules = not gate_report["all_rule_gates_passed"].map(
            _bool_value
        ).any()

    if passed_rules and passed_rules.lower() not in {"nan", "none"}:
        no_passed_rules = False

    no_strategy_promotion = True

    if not comparison.empty and "strategy_promotion" in comparison.columns:
        no_strategy_promotion = not comparison["strategy_promotion"].map(
            _bool_value
        ).any()

    role_bounded = True

    if not comparison.empty and "role" in comparison.columns:
        role_bounded = bool(
            comparison["role"].astype(str).str.contains(
                "Candidate for further validation only",
                regex=False,
            ).all()
        )

    rows = [
        {
            "check": "Phase 9D conclusion documents failure",
            "passed": phase9d_failure_documented,
            "detail": f"verdict={verdict}",
        },
        {
            "check": "No Phase 9D rule passed all gates",
            "passed": no_passed_rules,
            "detail": f"passed_rules={passed_rules}",
        },
        {
            "check": "Phase 9D comparison shows no strategy promotion",
            "passed": no_strategy_promotion,
            "detail": f"comparison_rows={len(comparison)}",
        },
        {
            "check": "Phase 9D rule roles remain bounded",
            "passed": role_bounded,
            "detail": f"comparison_rows={len(comparison)}",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase9e_closeout_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    phase9d_failure_check: pd.DataFrame,
) -> pd.DataFrame:
    scope = phase_config.get("closeout_scope", {})
    required_wording = phase_config.get("required_closeout_wording", [])

    reports_passed = (
        bool(report_inventory_check["passed"].all())
        if not report_inventory_check.empty
        else False
    )
    config_passed = (
        bool(config_flag_check["passed"].all())
        if not config_flag_check.empty
        else False
    )
    phase9d_checks_passed = (
        bool(phase9d_failure_check["passed"].all())
        if not phase9d_failure_check.empty
        else False
    )

    successor_created = bool(scope.get("successor_candidate_created", False))
    final_candidate_changed = bool(scope.get("final_candidate_changed", False))
    promotion_allowed = bool(scope.get("rule_promotion_allowed", False))
    status = str(scope.get("status", ""))

    branch_closed_without_promotion = (
        "closed" in status.lower()
        and "no rule promoted" in status.lower()
        and not successor_created
        and not final_candidate_changed
        and not promotion_allowed
    )

    return pd.DataFrame(
        [
            {
                "branch": str(scope.get("branch", "")),
                "status": status,
                "next_allowed_step": str(scope.get("next_allowed_step", "")),
                "successor_candidate_created": successor_created,
                "final_candidate_changed": final_candidate_changed,
                "rule_promotion_allowed": promotion_allowed,
                "reports_passed": reports_passed,
                "config_passed": config_passed,
                "phase9d_checks_passed": phase9d_checks_passed,
                "branch_closed_without_promotion": branch_closed_without_promotion,
                "required_closeout_wording_count": int(len(required_wording)),
                "closeout_role": "Failure documentation / branch closeout only",
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


def build_phase9e_gate_report(
    *,
    report_inventory_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    phase9d_failure_check: pd.DataFrame,
    closeout_summary: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if closeout_summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 9E summary exists",
                    False,
                    "No closeout summary was created.",
                )
            ]
        )

    row = closeout_summary.iloc[0]

    reports_passed = (
        bool(report_inventory_check["passed"].all())
        if not report_inventory_check.empty
        else False
    )
    config_passed = (
        bool(config_flag_check["passed"].all())
        if not config_flag_check.empty
        else False
    )

    phase9d_checks = {
        str(item["check"]): bool(item["passed"])
        for item in phase9d_failure_check.to_dict("records")
    }

    rows = [
        _gate_row(
            "Expected Phase 9 reports are present",
            (not gates.get("require_expected_reports_present", True))
            or reports_passed,
            f"missing_prefixes={(~report_inventory_check['passed']).sum()}",
        ),
        _gate_row(
            "Config flags match closeout state",
            (not gates.get("require_config_flags_match", True))
            or config_passed,
            f"flag_failures={(~config_flag_check['passed']).sum()}",
        ),
        _gate_row(
            "Phase 9D failure is documented",
            (not gates.get("require_phase9d_failure_documented", True))
            or phase9d_checks.get("Phase 9D conclusion documents failure", False),
            "Phase 9D verdict must remain failed.",
        ),
        _gate_row(
            "No Phase 9D rule passed all gates",
            (not gates.get("require_no_phase9d_rule_passed", True))
            or phase9d_checks.get("No Phase 9D rule passed all gates", False),
            "No pre-registered rule may be treated as passed.",
        ),
        _gate_row(
            "No strategy promotion occurred",
            (not gates.get("require_no_strategy_promotion", True))
            or phase9d_checks.get(
                "Phase 9D comparison shows no strategy promotion",
                False,
            ),
            "Phase 9D must not promote a rule.",
        ),
        _gate_row(
            "No successor candidate was created",
            (not gates.get("require_no_successor_candidate", True))
            or (
                not bool(row["successor_candidate_created"])
                and not bool(row["final_candidate_changed"])
            ),
            (
                "successor_candidate_created="
                f"{bool(row['successor_candidate_created'])}; "
                f"final_candidate_changed={bool(row['final_candidate_changed'])}"
            ),
        ),
        _gate_row(
            "Technical branch is closed without promotion",
            (not gates.get("require_branch_closed_without_promotion", True))
            or bool(row["branch_closed_without_promotion"]),
            f"status={row['status']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase9e_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — technical extension closed without promotion"
        interpretation = (
            "Phase 9E documented that Phase 9A/9B evidence stayed diagnostic, "
            "Phase 9C pre-registered two hypotheses, and Phase 9D rejected both "
            "rule implementations. No technical rule was promoted."
        )
    else:
        verdict = "Failed closeout discipline"
        interpretation = (
            "Phase 9E did not satisfy every closeout gate. Do not move on until "
            "the failed technical-extension branch is documented correctly."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 9E",
                "diagnostic": "Technical extension closeout / failure documentation audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase9e_markdown(
    *,
    report_inventory_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    phase9d_failure_check: pd.DataFrame,
    closeout_summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 9E — Technical Extension Closeout / Failure Documentation Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit closes the Phase 9 technical-extension branch after the "
            "Phase 9D pre-registered rule test failed."
        ),
        "",
        (
            "It does not create a new rule, tune a failed rule, or promote a "
            "successor candidate."
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
        "## Phase 9D Failure Check",
        "",
        phase9d_failure_check.to_markdown(index=False),
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
        "- It does not prove that all technical indicators are useless.",
        "- It only documents that the tested pre-registered Phase 9D rules failed.",
        "- Further technical variants should not be opened casually.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase9e_technical_extension_closeout_audit(
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
            "phase9d_failure_check": empty,
            "closeout_summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase9e_report_inventory_check(
        reports_dir=reports_path,
        expected_report_prefixes=[
            str(value) for value in phase_config.get("expected_report_prefixes", [])
        ],
    )
    config_flag_check = build_phase9e_config_flag_check(
        runtime_config=config,
        expected_flags={
            str(key): bool(value)
            for key, value in phase_config.get("expected_disabled_flags", {}).items()
        },
    )
    phase9d_failure_check = build_phase9e_phase9d_failure_check(
        reports_dir=reports_path,
        phase_config=phase_config,
    )
    closeout_summary = build_phase9e_closeout_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        config_flag_check=config_flag_check,
        phase9d_failure_check=phase9d_failure_check,
    )
    gate_report = build_phase9e_gate_report(
        report_inventory_check=report_inventory_check,
        config_flag_check=config_flag_check,
        phase9d_failure_check=phase9d_failure_check,
        closeout_summary=closeout_summary,
        phase_config=phase_config,
    )
    conclusion = build_phase9e_conclusion(gate_report)

    report_inventory_check.to_csv(
        reports_path / "phase9e_technical_extension_report_inventory_check.csv",
        index=False,
    )
    config_flag_check.to_csv(
        reports_path / "phase9e_technical_extension_config_flag_check.csv",
        index=False,
    )
    phase9d_failure_check.to_csv(
        reports_path / "phase9e_technical_extension_phase9d_failure_check.csv",
        index=False,
    )
    closeout_summary.to_csv(
        reports_path / "phase9e_technical_extension_closeout_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase9e_technical_extension_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase9e_technical_extension_conclusion.csv",
        index=False,
    )

    write_phase9e_markdown(
        report_inventory_check=report_inventory_check,
        config_flag_check=config_flag_check,
        phase9d_failure_check=phase9d_failure_check,
        closeout_summary=closeout_summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase9e_technical_extension_closeout_audit.md",
    )

    print("Wrote Phase 9E technical extension closeout audit reports.")

    return {
        "report_inventory_check": report_inventory_check,
        "config_flag_check": config_flag_check,
        "phase9d_failure_check": phase9d_failure_check,
        "closeout_summary": closeout_summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }