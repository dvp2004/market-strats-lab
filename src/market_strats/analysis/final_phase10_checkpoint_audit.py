from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE10H_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Final Phase 10 checkpoint / README-config-report consistency audit",
    "phase_branch": "Phase 10 macro/rates/inflation extension",
    "checkpoint_status": "Phase 10 closed — macro branch closed without promotion",
    "next_allowed_step": "Architecture review for richer information layers",
    "readme_path": "README.md",
    "expected_disabled_flags": {
        "phase10a_feature_family_feasibility_spec": False,
        "phase10b_macro_data_source_leakage_audit": False,
        "phase10c_macro_source_reliability_alignment_audit": False,
        "phase10d_diagnostic_macro_regime_analysis": False,
        "phase10e_preregistered_macro_hypothesis_spec": False,
        "phase10f_preregistered_macro_rule_test": False,
        "phase10g_macro_extension_closeout_audit": False,
        "relative_momentum_allocator": True,
    },
    "expected_report_prefixes": [],
    "expected_markdown_reports": [],
    "phase10g_reports": {
        "conclusion": "reports/phase10g_macro_closeout_conclusion.csv",
        "gate_report": "reports/phase10g_macro_closeout_gate_report.csv",
        "summary": "reports/phase10g_macro_closeout_summary.csv",
        "phase10f_failure_check": "reports/phase10g_macro_closeout_phase10f_failure_check.csv",
    },
    "required_readme_phrases": [],
    "forbidden_readme_phrases": [],
    "canonical_hierarchy_phrases": [],
    "gates": {
        "require_readme_required_phrases": True,
        "require_readme_forbidden_phrases_absent": True,
        "require_expected_reports_present": True,
        "require_config_flags_clean": True,
        "require_phase10g_closeout_passed": True,
        "require_phase10f_failure_locked": True,
        "require_no_successor_candidate": True,
        "require_final_candidate_unchanged": True,
        "require_canonical_hierarchy_present": True,
        "require_no_strategy_promotion": True,
        "required_audit_role": (
            "Final Phase 10 checkpoint / README-config-report consistency audit"
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
    user_config = config.get("phase10h_final_phase10_checkpoint_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE10H_CONFIG, user_config)


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


def _read_text_if_exists(path: str | Path) -> str:
    text_path = Path(path)

    if not text_path.exists():
        return ""

    return text_path.read_text(encoding="utf-8")


def _read_csv_if_exists(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)

    if not csv_path.exists():
        return pd.DataFrame()

    return pd.read_csv(csv_path)


def build_phase10h_readme_phrase_check(
    *,
    readme_text: str,
    required_phrases: list[str],
    forbidden_phrases: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for phrase in required_phrases:
        present = phrase in readme_text
        rows.append(
            {
                "check_type": "required",
                "phrase": phrase,
                "passed": present,
                "result": "Passed" if present else "Failed",
            }
        )

    for phrase in forbidden_phrases:
        absent = phrase not in readme_text
        rows.append(
            {
                "check_type": "forbidden",
                "phrase": phrase,
                "passed": absent,
                "result": "Passed" if absent else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase10h_config_flag_check(
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


def build_phase10h_report_inventory_check(
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
        present = report_path.exists()
        rows.append(
            {
                "check_type": "markdown_report",
                "expected_item": str(report_name),
                "present": present,
                "match_count": int(present),
                "matches": report_name if present else "",
            }
        )

    return pd.DataFrame(rows)


def build_phase10h_phase10g_closeout_check(
    *,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase10g_reports", {})
    conclusion = _read_csv_if_exists(reports.get("conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("gate_report", ""))
    summary = _read_csv_if_exists(reports.get("summary", ""))
    phase10f_failure_check = _read_csv_if_exists(
        reports.get("phase10f_failure_check", "")
    )

    closeout_verdict = ""
    closeout_all_gates_passed = False
    strategy_promotion = False
    successor_candidate_created = True
    final_candidate_changed = True
    phase10f_failure_locked = False
    phase10f_no_rule_passed = False
    phase10f_discipline_passed = False

    if not conclusion.empty:
        closeout_verdict = str(conclusion.iloc[0].get("verdict", ""))
        closeout_all_gates_passed = _bool_value(
            conclusion.iloc[0].get("all_gates_passed", False)
        )

    if not gate_report.empty and "passed" in gate_report.columns:
        closeout_all_gates_passed = closeout_all_gates_passed and bool(
            gate_report["passed"].map(_bool_value).all()
        )

    if not summary.empty:
        successor_candidate_created = _bool_value(
            summary.iloc[0].get("successor_candidate_created", True)
        )
        final_candidate_changed = _bool_value(
            summary.iloc[0].get("final_candidate_changed", True)
        )
        strategy_promotion = _bool_value(
            summary.iloc[0].get("strategy_promotion", False)
        )

    if not phase10f_failure_check.empty:
        checks = phase10f_failure_check.set_index("check")
        if "Phase 10F conclusion documents failure" in checks.index:
            phase10f_failure_locked = _bool_value(
                checks.loc["Phase 10F conclusion documents failure", "passed"]
            )
        if "Phase 10F conclusion says no rule passed" in checks.index:
            phase10f_no_rule_passed = _bool_value(
                checks.loc["Phase 10F conclusion says no rule passed", "passed"]
            )
        if "Phase 10F discipline gates passed" in checks.index:
            phase10f_discipline_passed = _bool_value(
                checks.loc["Phase 10F discipline gates passed", "passed"]
            )

    rows = [
        {
            "check": "Phase 10G conclusion report exists",
            "passed": not conclusion.empty,
            "detail": f"rows={len(conclusion)}",
        },
        {
            "check": "Phase 10G closeout passed",
            "passed": closeout_all_gates_passed
            and "closed without promotion" in closeout_verdict,
            "detail": f"verdict={closeout_verdict}",
        },
        {
            "check": "Phase 10F failure remains locked",
            "passed": phase10f_failure_locked,
            "detail": f"phase10f_failure_locked={phase10f_failure_locked}",
        },
        {
            "check": "No Phase 10F rule passed",
            "passed": phase10f_no_rule_passed,
            "detail": f"phase10f_no_rule_passed={phase10f_no_rule_passed}",
        },
        {
            "check": "Phase 10F discipline passed",
            "passed": phase10f_discipline_passed,
            "detail": f"phase10f_discipline_passed={phase10f_discipline_passed}",
        },
        {
            "check": "No successor candidate was created",
            "passed": not successor_candidate_created,
            "detail": f"successor_candidate_created={successor_candidate_created}",
        },
        {
            "check": "Final candidate remains unchanged",
            "passed": not final_candidate_changed,
            "detail": f"final_candidate_changed={final_candidate_changed}",
        },
        {
            "check": "No strategy promotion occurred",
            "passed": not strategy_promotion,
            "detail": f"strategy_promotion={strategy_promotion}",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase10h_canonical_hierarchy_check(
    *,
    readme_text: str,
    canonical_phrases: list[str],
) -> pd.DataFrame:
    rows = []

    for phrase in canonical_phrases:
        present = phrase in readme_text
        rows.append(
            {
                "hierarchy_phrase": phrase,
                "present": present,
                "passed": present,
                "result": "Passed" if present else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase10h_summary(
    *,
    phase_config: dict[str, Any],
    readme_phrase_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    report_inventory_check: pd.DataFrame,
    phase10g_closeout_check: pd.DataFrame,
    canonical_hierarchy_check: pd.DataFrame,
) -> pd.DataFrame:
    required_readme_passed = (
        bool(
            readme_phrase_check[
                readme_phrase_check["check_type"] == "required"
            ]["passed"].all()
        )
        if not readme_phrase_check.empty
        else False
    )
    forbidden_readme_absent = (
        bool(
            readme_phrase_check[
                readme_phrase_check["check_type"] == "forbidden"
            ]["passed"].all()
        )
        if not readme_phrase_check.empty
        else False
    )

    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "checkpoint_status": str(phase_config.get("checkpoint_status", "")),
                "next_allowed_step": str(phase_config.get("next_allowed_step", "")),
                "required_readme_phrases_passed": required_readme_passed,
                "forbidden_readme_phrases_absent": forbidden_readme_absent,
                "config_flags_clean": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "expected_reports_present": bool(report_inventory_check["present"].all())
                if not report_inventory_check.empty
                else False,
                "phase10g_closeout_passed": bool(
                    phase10g_closeout_check["passed"].all()
                )
                if not phase10g_closeout_check.empty
                else False,
                "canonical_hierarchy_present": bool(
                    canonical_hierarchy_check["passed"].all()
                )
                if not canonical_hierarchy_check.empty
                else False,
                "strategy_promotion": False,
                "successor_candidate_created": False,
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


def build_phase10h_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 10H summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_audit_role",
            "Final Phase 10 checkpoint / README-config-report consistency audit",
        )
    )

    rows = [
        _gate_row(
            "README required Phase 10 phrases are present",
            (not gates.get("require_readme_required_phrases", True))
            or bool(row["required_readme_phrases_passed"]),
            f"required_readme_phrases_passed={row['required_readme_phrases_passed']}",
        ),
        _gate_row(
            "README forbidden overclaim phrases are absent",
            (not gates.get("require_readme_forbidden_phrases_absent", True))
            or bool(row["forbidden_readme_phrases_absent"]),
            f"forbidden_readme_phrases_absent={row['forbidden_readme_phrases_absent']}",
        ),
        _gate_row(
            "Expected Phase 10 reports are present",
            (not gates.get("require_expected_reports_present", True))
            or bool(row["expected_reports_present"]),
            f"expected_reports_present={row['expected_reports_present']}",
        ),
        _gate_row(
            "Config flags match final Phase 10 checkpoint state",
            (not gates.get("require_config_flags_clean", True))
            or bool(row["config_flags_clean"]),
            f"config_flags_clean={row['config_flags_clean']}",
        ),
        _gate_row(
            "Phase 10G closeout passed",
            (not gates.get("require_phase10g_closeout_passed", True))
            or bool(row["phase10g_closeout_passed"]),
            f"phase10g_closeout_passed={row['phase10g_closeout_passed']}",
        ),
        _gate_row(
            "Phase 10F failure remains locked",
            (not gates.get("require_phase10f_failure_locked", True))
            or bool(row["phase10g_closeout_passed"]),
            "Phase 10G closeout must keep Phase 10F failure documented.",
        ),
        _gate_row(
            "No successor candidate was created",
            (not gates.get("require_no_successor_candidate", True))
            or not bool(row["successor_candidate_created"]),
            f"successor_candidate_created={row['successor_candidate_created']}",
        ),
        _gate_row(
            "Final candidate remains unchanged",
            (not gates.get("require_final_candidate_unchanged", True))
            or not bool(row["final_candidate_changed"]),
            f"final_candidate_changed={row['final_candidate_changed']}",
        ),
        _gate_row(
            "Canonical hierarchy is present",
            (not gates.get("require_canonical_hierarchy_present", True))
            or bool(row["canonical_hierarchy_present"]),
            f"canonical_hierarchy_present={row['canonical_hierarchy_present']}",
        ),
        _gate_row(
            "No strategy promotion occurred",
            (not gates.get("require_no_strategy_promotion", True))
            or not bool(row["strategy_promotion"]),
            f"strategy_promotion={row['strategy_promotion']}",
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


def build_phase10h_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — final Phase 10 checkpoint passed"
        interpretation = (
            "Phase 10H confirmed that Phase 10 is documented and closed correctly: "
            "reports are present, config flags are clean, Phase 10F failure remains "
            "locked, Phase 10G closeout is documented, no macro rule was promoted, "
            "no successor candidate was created, and the final hierarchy remains unchanged."
        )
    else:
        verdict = "Failed final Phase 10 checkpoint audit"
        interpretation = (
            "Phase 10H found a README, config, report, closeout, hierarchy, or "
            "promotion-boundary inconsistency. Correct it before architecture review."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 10H",
                "diagnostic": "Final Phase 10 checkpoint / README-config-report consistency audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase10h_markdown(
    *,
    readme_phrase_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    report_inventory_check: pd.DataFrame,
    phase10g_closeout_check: pd.DataFrame,
    canonical_hierarchy_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 10H — Final Phase 10 Checkpoint Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit verifies README, config, report inventory, Phase 10G closeout, "
            "canonical hierarchy, and promotion-boundary consistency after the macro "
            "branch was closed without promotion."
        ),
        "",
        "## README Phrase Check",
        "",
        readme_phrase_check.to_markdown(index=False),
        "",
        "## Config Flag Check",
        "",
        config_flag_check.to_markdown(index=False),
        "",
        "## Report Inventory Check",
        "",
        report_inventory_check.to_markdown(index=False),
        "",
        "## Phase 10G Closeout Check",
        "",
        phase10g_closeout_check.to_markdown(index=False),
        "",
        "## Canonical Hierarchy Check",
        "",
        canonical_hierarchy_check.to_markdown(index=False),
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
        "- This is a checkpoint audit, not a new strategy test.",
        "- It does not reopen macro-rule testing.",
        "- It does not perform architecture review.",
        "- It does not change the final candidate hierarchy.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase10h_final_phase10_checkpoint_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "readme_phrase_check": empty,
            "config_flag_check": empty,
            "report_inventory_check": empty,
            "phase10g_closeout_check": empty,
            "canonical_hierarchy_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    readme_text = _read_text_if_exists(phase_config.get("readme_path", "README.md"))

    readme_phrase_check = build_phase10h_readme_phrase_check(
        readme_text=readme_text,
        required_phrases=[
            str(item) for item in _as_list(phase_config.get("required_readme_phrases"))
        ],
        forbidden_phrases=[
            str(item) for item in _as_list(phase_config.get("forbidden_readme_phrases"))
        ],
    )
    config_flag_check = build_phase10h_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_disabled_flags", {}),
    )
    report_inventory_check = build_phase10h_report_inventory_check(
        reports_dir=reports_path,
        phase_config=phase_config,
    )
    phase10g_closeout_check = build_phase10h_phase10g_closeout_check(
        phase_config=phase_config,
    )
    canonical_hierarchy_check = build_phase10h_canonical_hierarchy_check(
        readme_text=readme_text,
        canonical_phrases=[
            str(item)
            for item in _as_list(phase_config.get("canonical_hierarchy_phrases"))
        ],
    )
    summary = build_phase10h_summary(
        phase_config=phase_config,
        readme_phrase_check=readme_phrase_check,
        config_flag_check=config_flag_check,
        report_inventory_check=report_inventory_check,
        phase10g_closeout_check=phase10g_closeout_check,
        canonical_hierarchy_check=canonical_hierarchy_check,
    )
    gate_report = build_phase10h_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase10h_conclusion(gate_report)

    readme_phrase_check.to_csv(
        reports_path / "phase10h_final_checkpoint_readme_phrase_check.csv",
        index=False,
    )
    config_flag_check.to_csv(
        reports_path / "phase10h_final_checkpoint_config_flag_check.csv",
        index=False,
    )
    report_inventory_check.to_csv(
        reports_path / "phase10h_final_checkpoint_report_inventory_check.csv",
        index=False,
    )
    phase10g_closeout_check.to_csv(
        reports_path / "phase10h_final_checkpoint_phase10g_closeout_check.csv",
        index=False,
    )
    canonical_hierarchy_check.to_csv(
        reports_path / "phase10h_final_checkpoint_canonical_hierarchy_check.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase10h_final_checkpoint_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase10h_final_checkpoint_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase10h_final_checkpoint_conclusion.csv",
        index=False,
    )

    write_phase10h_markdown(
        readme_phrase_check=readme_phrase_check,
        config_flag_check=config_flag_check,
        report_inventory_check=report_inventory_check,
        phase10g_closeout_check=phase10g_closeout_check,
        canonical_hierarchy_check=canonical_hierarchy_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase10h_final_phase10_checkpoint_audit.md",
    )

    print("Wrote Phase 10H final Phase 10 checkpoint audit reports.")

    return {
        "readme_phrase_check": readme_phrase_check,
        "config_flag_check": config_flag_check,
        "report_inventory_check": report_inventory_check,
        "phase10g_closeout_check": phase10g_closeout_check,
        "canonical_hierarchy_check": canonical_hierarchy_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }