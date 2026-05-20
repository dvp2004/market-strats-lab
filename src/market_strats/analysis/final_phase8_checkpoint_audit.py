from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


DEFAULT_PHASE8G_CONFIG: dict[str, Any] = {
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
    "gates": {
        "require_all_readme_required_phrases": True,
        "require_no_forbidden_readme_phrases": True,
        "require_all_config_flags_match": True,
        "require_expected_phase8_reports_present": True,
        "require_final_candidate_wording_caveated": True,
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
    user_config = config.get("phase8g_final_phase8_checkpoint_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE8G_CONFIG, user_config)


def _contains_case_insensitive(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def build_phase8g_readme_phrase_check(
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


def _get_enabled_flag(config: dict[str, Any], key: str) -> bool | None:
    value = config.get(key)

    if not isinstance(value, dict):
        return None

    enabled = value.get("enabled")

    if enabled is None:
        return None

    return bool(enabled)


def build_phase8g_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, bool],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for key, expected_value in expected_flags.items():
        actual_value = _get_enabled_flag(runtime_config, key)
        passed = actual_value == bool(expected_value)

        rows.append(
            {
                "config_key": key,
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


def build_phase8g_report_inventory_check(
    *,
    reports_dir: str | Path,
    expected_report_prefixes: list[str],
) -> pd.DataFrame:
    reports_path = Path(reports_dir)
    rows: list[dict[str, Any]] = []

    existing_files = list(reports_path.glob("*")) if reports_path.exists() else []
    existing_names = [path.name for path in existing_files if path.is_file()]

    for prefix in expected_report_prefixes:
        matching_files = sorted(name for name in existing_names if name.startswith(prefix))
        passed = bool(matching_files)

        rows.append(
            {
                "expected_prefix": prefix,
                "matching_file_count": len(matching_files),
                "matching_files": "; ".join(matching_files[:10]),
                "passed": passed,
                "result": "Passed" if passed else "Failed",
                "detail": "Report files present" if passed else "No matching report files",
            }
        )

    return pd.DataFrame(rows)


def build_phase8g_canonical_check(
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
        "research-only",
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
            "item": "final_candidate_caveat_stack",
            "expected": "; ".join(caveat_phrases),
            "passed": all(_contains_case_insensitive(readme_text, phrase) for phrase in caveat_phrases),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})
    frame["detail"] = frame.apply(
        lambda row: "Canonical item present" if row["passed"] else "Canonical item missing",
        axis=1,
    )

    return frame


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase8g_gate_report(
    *,
    readme_phrase_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    report_inventory_check: pd.DataFrame,
    canonical_check: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    required_rows = readme_phrase_check[
        readme_phrase_check["check_type"] == "required_phrase"
    ]
    forbidden_rows = readme_phrase_check[
        readme_phrase_check["check_type"] == "forbidden_phrase"
    ]

    required_passed = bool(required_rows["passed"].all()) if not required_rows.empty else True
    forbidden_passed = bool(forbidden_rows["passed"].all()) if not forbidden_rows.empty else True
    config_passed = (
        bool(config_flag_check["passed"].all()) if not config_flag_check.empty else False
    )
    reports_passed = (
        bool(report_inventory_check["passed"].all())
        if not report_inventory_check.empty
        else False
    )

    caveat_row = canonical_check[canonical_check["item"] == "final_candidate_caveat_stack"]
    caveat_passed = bool(caveat_row["passed"].iloc[0]) if not caveat_row.empty else False
    canonical_passed = bool(canonical_check["passed"].all()) if not canonical_check.empty else False

    rows = [
        _gate_row(
            "README contains all required Phase 8 wording",
            (not gates.get("require_all_readme_required_phrases", True)) or required_passed,
            f"required_phrase_failures={(~required_rows['passed']).sum() if not required_rows.empty else 0}",
        ),
        _gate_row(
            "README contains no forbidden overclaiming phrases",
            (not gates.get("require_no_forbidden_readme_phrases", True)) or forbidden_passed,
            f"forbidden_phrase_failures={(~forbidden_rows['passed']).sum() if not forbidden_rows.empty else 0}",
        ),
        _gate_row(
            "Config flags match permanent checkpoint state",
            (not gates.get("require_all_config_flags_match", True)) or config_passed,
            f"config_flag_failures={(~config_flag_check['passed']).sum() if not config_flag_check.empty else 0}",
        ),
        _gate_row(
            "Expected Phase 8 report artefacts are present locally",
            (not gates.get("require_expected_phase8_reports_present", True)) or reports_passed,
            f"missing_prefixes={(~report_inventory_check['passed']).sum() if not report_inventory_check.empty else 0}",
        ),
        _gate_row(
            "Canonical hierarchy and dates are documented",
            canonical_passed,
            f"canonical_failures={(~canonical_check['passed']).sum() if not canonical_check.empty else 0}",
        ),
        _gate_row(
            "Final candidate wording includes full caveat stack",
            (not gates.get("require_final_candidate_wording_caveated", True)) or caveat_passed,
            f"caveat_stack_present={caveat_passed}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase8g_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — Phase 8 checkpoint consistent"
        interpretation = (
            "README wording, config flags, local report inventory, hierarchy, dates, "
            "and research-only boundary were internally consistent. This closes Phase 8 "
            "as a research checkpoint, not as production approval."
        )
    else:
        verdict = "Failed checkpoint consistency"
        interpretation = (
            "Phase 8 checkpoint consistency failed. Do not open Phase 9 until README "
            "wording, config flags, report inventory, or hierarchy issues are corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 8G",
                "diagnostic": "Final Phase 8 checkpoint / README consistency audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase8g_markdown(
    *,
    readme_phrase_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    report_inventory_check: pd.DataFrame,
    canonical_check: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 8G — Final Phase 8 Checkpoint / README Consistency Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit checks whether the README, config flags, local Phase 8 report "
            "artefacts, final hierarchy, canonical dates, and research-only boundary "
            "are internally consistent after Phases 8A–8F."
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


def save_phase8g_final_phase8_checkpoint_audit(
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

    readme_phrase_check = build_phase8g_readme_phrase_check(
        readme_text=readme_text,
        required_phrases=[
            str(value) for value in phase_config.get("required_readme_phrases", [])
        ],
        forbidden_phrases=[
            str(value) for value in phase_config.get("forbidden_readme_phrases", [])
        ],
    )
    config_flag_check = build_phase8g_config_flag_check(
        runtime_config=persisted_config,
        expected_flags={
            str(key): bool(value)
            for key, value in phase_config.get("expected_disabled_flags", {}).items()
        },
    )
    report_inventory_check = build_phase8g_report_inventory_check(
        reports_dir=reports_path,
        expected_report_prefixes=[
            str(value) for value in phase_config.get("expected_report_prefixes", [])
        ],
    )
    canonical_check = build_phase8g_canonical_check(
        readme_text=readme_text,
        phase_config=phase_config,
    )
    gate_report = build_phase8g_gate_report(
        readme_phrase_check=readme_phrase_check,
        config_flag_check=config_flag_check,
        report_inventory_check=report_inventory_check,
        canonical_check=canonical_check,
        phase_config=phase_config,
    )
    conclusion = build_phase8g_conclusion(gate_report)

    readme_phrase_check.to_csv(
        reports_path / "phase8g_final_checkpoint_readme_phrase_check.csv",
        index=False,
    )
    config_flag_check.to_csv(
        reports_path / "phase8g_final_checkpoint_config_flag_check.csv",
        index=False,
    )
    report_inventory_check.to_csv(
        reports_path / "phase8g_final_checkpoint_report_inventory_check.csv",
        index=False,
    )
    canonical_check.to_csv(
        reports_path / "phase8g_final_checkpoint_canonical_check.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase8g_final_checkpoint_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase8g_final_checkpoint_conclusion.csv",
        index=False,
    )

    write_phase8g_markdown(
        readme_phrase_check=readme_phrase_check,
        config_flag_check=config_flag_check,
        report_inventory_check=report_inventory_check,
        canonical_check=canonical_check,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase8g_final_phase8_checkpoint_audit.md",
    )

    print("Wrote Phase 8G final Phase 8 checkpoint audit reports.")

    return {
        "readme_phrase_check": readme_phrase_check,
        "config_flag_check": config_flag_check,
        "report_inventory_check": report_inventory_check,
        "canonical_check": canonical_check,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }