from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


DEFAULT_PHASE9F_CONFIG: dict[str, Any] = {
    "enabled": False,
    "readme_path": "README.md",
    "config_path": "configs/spy_sma10.yaml",
    "canonical": {
        "final_candidate": "SPY 3D confirmed overlay + deep_drawdown_guard + loose_relief",
        "raw_wealth_benchmark": "SPY Buy & Hold",
        "simple_defensive_benchmark": "SPY 12M Momentum",
        "canonical_start_date": "2006-04-28",
        "canonical_end_date": "2026-05-01",
    },
    "required_readme_phrases": [],
    "forbidden_readme_phrases": [],
    "expected_disabled_flags": {},
    "expected_report_prefixes": [],
    "phase9_closeout_requirements": {
        "phase9a_role": "diagnostic only",
        "phase9b_role": "diagnostic only",
        "phase9c_role": "pre-registration only",
        "phase9d_result": "failed",
        "phase9e_result": "closed without promotion",
        "technical_rule_promoted": False,
        "successor_candidate_created": False,
        "final_candidate_changed": False,
    },
    "gates": {
        "require_all_readme_required_phrases": True,
        "require_no_forbidden_readme_phrases": True,
        "require_all_config_flags_match": True,
        "require_expected_phase9_reports_present": True,
        "require_canonical_hierarchy_documented": True,
        "require_phase9_closeout_documented": True,
        "require_no_technical_rule_promotion": True,
        "require_no_successor_candidate": True,
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
    user_config = config.get("phase9f_final_phase9_checkpoint_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE9F_CONFIG, user_config)


def _contains_case_insensitive(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()

    if clean in {"true", "1", "yes", "y"}:
        return True

    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False

    return bool(value)


def _get_enabled_flag(config: dict[str, Any], key: str) -> bool | None:
    value = config.get(key)

    if not isinstance(value, dict):
        return None

    enabled = value.get("enabled")

    if enabled is None:
        return None

    return bool(enabled)


def _load_report(reports_dir: str | Path, filename: str) -> pd.DataFrame:
    path = Path(reports_dir) / filename

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def build_phase9f_readme_phrase_check(
    *,
    readme_text: str,
    required_phrases: list[str],
    forbidden_phrases: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for phrase in required_phrases:
        present = _contains_case_insensitive(readme_text, phrase)
        rows.append(
            {
                "check_type": "required_phrase",
                "phrase": phrase,
                "passed": present,
                "result": "Passed" if present else "Failed",
                "detail": "Phrase present" if present else "Required phrase missing",
            }
        )

    for phrase in forbidden_phrases:
        present = _contains_case_insensitive(readme_text, phrase)
        rows.append(
            {
                "check_type": "forbidden_phrase",
                "phrase": phrase,
                "passed": not present,
                "result": "Passed" if not present else "Failed",
                "detail": "Phrase absent" if not present else "Forbidden phrase present",
            }
        )

    return pd.DataFrame(rows)


def build_phase9f_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, bool],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for key, expected_value in expected_flags.items():
        actual_value = _get_enabled_flag(runtime_config, str(key))
        passed = actual_value == bool(expected_value)

        rows.append(
            {
                "config_key": str(key),
                "expected_enabled": bool(expected_value),
                "actual_enabled": actual_value,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
                "detail": (
                    f"enabled={actual_value}"
                    if actual_value is not None
                    else "Config key missing or has no enabled flag"
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase9f_report_inventory_check(
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
        matching_files = sorted(name for name in existing_names if name.startswith(prefix))
        passed = bool(matching_files)

        rows.append(
            {
                "expected_prefix": prefix,
                "matching_file_count": len(matching_files),
                "matching_files": "; ".join(matching_files[:15]),
                "passed": passed,
                "result": "Passed" if passed else "Failed",
                "detail": "Report files present" if passed else "No matching report files",
            }
        )

    return pd.DataFrame(rows)


def build_phase9f_canonical_check(
    *,
    readme_text: str,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    canonical = phase_config.get("canonical", {})

    caveat_phrases = [
        "mixed rolling-window liveability",
        "meaningful spread/impact sensitivity",
        "mixed walk-forward evidence",
        "material behavioural-regret risk",
        "research-degrees-of-freedom caveat",
        "research-only/non-production boundary",
        "diagnostic-only Phase 9A technical-regime evidence",
        "diagnostic-only Phase 9B cluster-stability evidence",
        "Phase 9C pre-registered technical-rule design spec",
        "failed Phase 9D pre-registered technical-rule test",
        "Phase 9E technical-extension closeout with no rule promotion",
    ]

    rows = [
        {
            "item": "final_candidate",
            "expected": canonical.get("final_candidate"),
            "passed": _contains_case_insensitive(
                readme_text,
                str(canonical.get("final_candidate", "")),
            ),
        },
        {
            "item": "raw_wealth_benchmark",
            "expected": canonical.get("raw_wealth_benchmark"),
            "passed": _contains_case_insensitive(
                readme_text,
                str(canonical.get("raw_wealth_benchmark", "")),
            ),
        },
        {
            "item": "simple_defensive_benchmark",
            "expected": canonical.get("simple_defensive_benchmark"),
            "passed": _contains_case_insensitive(
                readme_text,
                str(canonical.get("simple_defensive_benchmark", "")),
            ),
        },
        {
            "item": "canonical_start_date",
            "expected": canonical.get("canonical_start_date"),
            "passed": _contains_case_insensitive(
                readme_text,
                str(canonical.get("canonical_start_date", "")),
            ),
        },
        {
            "item": "canonical_end_date",
            "expected": canonical.get("canonical_end_date"),
            "passed": _contains_case_insensitive(
                readme_text,
                str(canonical.get("canonical_end_date", "")),
            ),
        },
        {
            "item": "phase9_full_caveat_stack",
            "expected": "; ".join(caveat_phrases),
            "passed": all(
                _contains_case_insensitive(readme_text, phrase)
                for phrase in caveat_phrases
            ),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})
    frame["detail"] = frame.apply(
        lambda row: "Canonical item present"
        if row["passed"]
        else "Canonical item missing",
        axis=1,
    )

    return frame


def build_phase9f_closeout_check(
    *,
    reports_dir: str | Path,
    readme_text: str,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    requirements = phase_config.get("phase9_closeout_requirements", {})

    phase9d_conclusion = _load_report(
        reports_dir,
        "phase9d_preregistered_rule_conclusion.csv",
    )
    phase9e_conclusion = _load_report(
        reports_dir,
        "phase9e_technical_extension_conclusion.csv",
    )
    phase9e_summary = _load_report(
        reports_dir,
        "phase9e_technical_extension_closeout_summary.csv",
    )

    phase9d_failed = False
    phase9e_closed = False
    no_successor = False
    no_rule_promotion = False
    final_candidate_unchanged = False

    if not phase9d_conclusion.empty:
        verdict = str(phase9d_conclusion.iloc[0].get("verdict", "")).lower()
        phase9d_failed = str(requirements.get("phase9d_result", "failed")).lower() in verdict

    if not phase9e_conclusion.empty:
        verdict = str(phase9e_conclusion.iloc[0].get("verdict", "")).lower()
        phase9e_closed = "closed without promotion" in verdict

    if not phase9e_summary.empty:
        row = phase9e_summary.iloc[0]
        no_successor = not _bool_value(row.get("successor_candidate_created", False))
        no_rule_promotion = not _bool_value(row.get("rule_promotion_allowed", False))
        final_candidate_unchanged = not _bool_value(row.get("final_candidate_changed", False))

    readme_closeout_documented = (
        (
            _contains_case_insensitive(readme_text, "Phase 9A/9B")
            or (
                _contains_case_insensitive(readme_text, "Phase 9A")
                and _contains_case_insensitive(readme_text, "Phase 9B")
            )
        )
        and _contains_case_insensitive(readme_text, "Phase 9C")
        and _contains_case_insensitive(readme_text, "Phase 9D")
        and _contains_case_insensitive(readme_text, "Phase 9E")
        and _contains_case_insensitive(readme_text, "No technical rule was promoted")
    )

    rows = [
        {
            "check": "Phase 9D failure documented in reports",
            "passed": phase9d_failed,
            "detail": "Phase 9D conclusion verdict remains failed.",
        },
        {
            "check": "Phase 9E closeout documented in reports",
            "passed": phase9e_closed,
            "detail": "Phase 9E conclusion shows closeout without promotion.",
        },
        {
            "check": "No successor candidate created",
            "passed": no_successor,
            "detail": f"no_successor={no_successor}",
        },
        {
            "check": "No technical rule promotion allowed",
            "passed": no_rule_promotion,
            "detail": f"no_rule_promotion={no_rule_promotion}",
        },
        {
            "check": "Final candidate unchanged",
            "passed": final_candidate_unchanged,
            "detail": f"final_candidate_unchanged={final_candidate_unchanged}",
        },
        {
            "check": "README documents technical branch closeout",
            "passed": readme_closeout_documented,
            "detail": "README contains Phase 9A-9E closeout wording.",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase9f_summary(
    *,
    readme_phrase_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    report_inventory_check: pd.DataFrame,
    canonical_check: pd.DataFrame,
    closeout_check: pd.DataFrame,
) -> pd.DataFrame:
    required_rows = readme_phrase_check[
        readme_phrase_check["check_type"] == "required_phrase"
    ]
    forbidden_rows = readme_phrase_check[
        readme_phrase_check["check_type"] == "forbidden_phrase"
    ]

    required_failures = (
        int((~required_rows["passed"]).sum()) if not required_rows.empty else 0
    )
    forbidden_failures = (
        int((~forbidden_rows["passed"]).sum()) if not forbidden_rows.empty else 0
    )

    return pd.DataFrame(
        [
            {
                "required_readme_phrase_failures": required_failures,
                "forbidden_readme_phrase_failures": forbidden_failures,
                "config_flag_failures": int((~config_flag_check["passed"]).sum())
                if not config_flag_check.empty
                else 0,
                "missing_report_prefixes": int(
                    (~report_inventory_check["passed"]).sum()
                )
                if not report_inventory_check.empty
                else 0,
                "canonical_failures": int((~canonical_check["passed"]).sum())
                if not canonical_check.empty
                else 0,
                "closeout_failures": int((~closeout_check["passed"]).sum())
                if not closeout_check.empty
                else 0,
                "technical_rule_promoted": False,
                "successor_candidate_created": False,
                "final_candidate_changed": False,
                "checkpoint_role": "Final Phase 9 consistency audit",
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


def build_phase9f_gate_report(
    *,
    readme_phrase_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    report_inventory_check: pd.DataFrame,
    canonical_check: pd.DataFrame,
    closeout_check: pd.DataFrame,
    summary: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 9F summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]

    required_rows = readme_phrase_check[
        readme_phrase_check["check_type"] == "required_phrase"
    ]
    forbidden_rows = readme_phrase_check[
        readme_phrase_check["check_type"] == "forbidden_phrase"
    ]

    required_passed = bool(required_rows["passed"].all()) if not required_rows.empty else True
    forbidden_passed = (
        bool(forbidden_rows["passed"].all()) if not forbidden_rows.empty else True
    )
    config_passed = (
        bool(config_flag_check["passed"].all()) if not config_flag_check.empty else False
    )
    reports_passed = (
        bool(report_inventory_check["passed"].all())
        if not report_inventory_check.empty
        else False
    )
    canonical_passed = (
        bool(canonical_check["passed"].all()) if not canonical_check.empty else False
    )
    closeout_passed = (
        bool(closeout_check["passed"].all()) if not closeout_check.empty else False
    )

    rows = [
        _gate_row(
            "README contains all required Phase 9 wording",
            (not gates.get("require_all_readme_required_phrases", True))
            or required_passed,
            f"required_phrase_failures={row['required_readme_phrase_failures']}",
        ),
        _gate_row(
            "README contains no forbidden overclaiming phrases",
            (not gates.get("require_no_forbidden_readme_phrases", True))
            or forbidden_passed,
            f"forbidden_phrase_failures={row['forbidden_readme_phrase_failures']}",
        ),
        _gate_row(
            "Config flags match permanent checkpoint state",
            (not gates.get("require_all_config_flags_match", True)) or config_passed,
            f"config_flag_failures={row['config_flag_failures']}",
        ),
        _gate_row(
            "Expected Phase 9 report artefacts are present locally",
            (not gates.get("require_expected_phase9_reports_present", True))
            or reports_passed,
            f"missing_report_prefixes={row['missing_report_prefixes']}",
        ),
        _gate_row(
            "Canonical hierarchy and dates are documented",
            (not gates.get("require_canonical_hierarchy_documented", True))
            or canonical_passed,
            f"canonical_failures={row['canonical_failures']}",
        ),
        _gate_row(
            "Phase 9 closeout is documented",
            (not gates.get("require_phase9_closeout_documented", True))
            or closeout_passed,
            f"closeout_failures={row['closeout_failures']}",
        ),
        _gate_row(
            "No technical rule was promoted",
            (not gates.get("require_no_technical_rule_promotion", True))
            or not bool(row["technical_rule_promoted"]),
            f"technical_rule_promoted={bool(row['technical_rule_promoted'])}",
        ),
        _gate_row(
            "No successor candidate was created",
            (not gates.get("require_no_successor_candidate", True))
            or not bool(row["successor_candidate_created"]),
            f"successor_candidate_created={bool(row['successor_candidate_created'])}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase9f_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — Phase 9 checkpoint consistent"
        interpretation = (
            "Phase 9A/9B diagnostic evidence, Phase 9C pre-registration, Phase 9D "
            "failure, and Phase 9E closeout were documented consistently. No "
            "technical rule was promoted and the final candidate hierarchy remains "
            "unchanged."
        )
    else:
        verdict = "Failed checkpoint consistency"
        interpretation = (
            "Phase 9 checkpoint consistency failed. Do not open Phase 10 until "
            "README wording, config flags, report inventory, hierarchy, or closeout "
            "documentation is corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 9F",
                "diagnostic": "Final Phase 9 checkpoint / README consistency audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase9f_markdown(
    *,
    readme_phrase_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    report_inventory_check: pd.DataFrame,
    canonical_check: pd.DataFrame,
    closeout_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 9F — Final Phase 9 Checkpoint / README Consistency Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit checks whether the README, config flags, local Phase 9 report "
            "artefacts, final hierarchy, canonical dates, and technical-extension "
            "closeout are internally consistent after Phases 9A–9E."
        ),
        "",
        "It is not a strategy test and it is not production approval.",
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
        "## Canonical Check",
        "",
        canonical_check.to_markdown(index=False),
        "",
        "## Closeout Check",
        "",
        closeout_check.to_markdown(index=False),
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
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase9f_final_phase9_checkpoint_audit(
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
            "canonical_check": empty,
            "closeout_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    readme_path = Path(str(phase_config.get("readme_path", "README.md")))
    config_path = Path(str(phase_config.get("config_path", "configs/spy_sma10.yaml")))
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    if not readme_path.exists():
        raise FileNotFoundError(f"README path not found: {readme_path}")

    if not config_path.exists():
        raise FileNotFoundError(f"Config path not found: {config_path}")

    readme_text = readme_path.read_text(encoding="utf-8")

    with config_path.open("r", encoding="utf-8") as file:
        persisted_config = yaml.safe_load(file)

    readme_phrase_check = build_phase9f_readme_phrase_check(
        readme_text=readme_text,
        required_phrases=[
            str(value) for value in phase_config.get("required_readme_phrases", [])
        ],
        forbidden_phrases=[
            str(value) for value in phase_config.get("forbidden_readme_phrases", [])
        ],
    )
    config_flag_check = build_phase9f_config_flag_check(
        runtime_config=persisted_config,
        expected_flags={
            str(key): bool(value)
            for key, value in phase_config.get("expected_disabled_flags", {}).items()
        },
    )
    report_inventory_check = build_phase9f_report_inventory_check(
        reports_dir=reports_path,
        expected_report_prefixes=[
            str(value) for value in phase_config.get("expected_report_prefixes", [])
        ],
    )
    canonical_check = build_phase9f_canonical_check(
        readme_text=readme_text,
        phase_config=phase_config,
    )
    closeout_check = build_phase9f_closeout_check(
        reports_dir=reports_path,
        readme_text=readme_text,
        phase_config=phase_config,
    )
    summary = build_phase9f_summary(
        readme_phrase_check=readme_phrase_check,
        config_flag_check=config_flag_check,
        report_inventory_check=report_inventory_check,
        canonical_check=canonical_check,
        closeout_check=closeout_check,
    )
    gate_report = build_phase9f_gate_report(
        readme_phrase_check=readme_phrase_check,
        config_flag_check=config_flag_check,
        report_inventory_check=report_inventory_check,
        canonical_check=canonical_check,
        closeout_check=closeout_check,
        summary=summary,
        phase_config=phase_config,
    )
    conclusion = build_phase9f_conclusion(gate_report)

    readme_phrase_check.to_csv(
        reports_path / "phase9f_final_checkpoint_readme_phrase_check.csv",
        index=False,
    )
    config_flag_check.to_csv(
        reports_path / "phase9f_final_checkpoint_config_flag_check.csv",
        index=False,
    )
    report_inventory_check.to_csv(
        reports_path / "phase9f_final_checkpoint_report_inventory_check.csv",
        index=False,
    )
    canonical_check.to_csv(
        reports_path / "phase9f_final_checkpoint_canonical_check.csv",
        index=False,
    )
    closeout_check.to_csv(
        reports_path / "phase9f_final_checkpoint_closeout_check.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase9f_final_checkpoint_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase9f_final_checkpoint_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase9f_final_checkpoint_conclusion.csv",
        index=False,
    )

    write_phase9f_markdown(
        readme_phrase_check=readme_phrase_check,
        config_flag_check=config_flag_check,
        report_inventory_check=report_inventory_check,
        canonical_check=canonical_check,
        closeout_check=closeout_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase9f_final_phase9_checkpoint_audit.md",
    )

    print("Wrote Phase 9F final Phase 9 checkpoint audit reports.")

    return {
        "readme_phrase_check": readme_phrase_check,
        "config_flag_check": config_flag_check,
        "report_inventory_check": report_inventory_check,
        "canonical_check": canonical_check,
        "closeout_check": closeout_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }