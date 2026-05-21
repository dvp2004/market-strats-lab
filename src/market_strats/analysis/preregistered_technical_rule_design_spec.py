from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE9C_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Pre-registered design spec only",
    "proposed_test_phase": "Phase 9D",
    "allow_strategy_test": False,
    "allow_parameter_optimisation": False,
    "allow_strategy_promotion": False,
    "allowed_input_registry": [],
    "forbidden_input_keywords": [],
    "forbidden_actions": [],
    "required_validation_gates": [],
    "hypotheses": [],
    "gates": {
        "min_hypotheses": 1,
        "max_hypotheses": 2,
        "require_source_evidence": True,
        "require_allowed_inputs": True,
        "require_forbidden_inputs": True,
        "require_proposed_rule_logic": True,
        "require_validation_gates": True,
        "require_failure_conditions": True,
        "require_readme_wording": True,
        "require_promotion_constraints": True,
        "require_no_forbidden_inputs": True,
        "require_no_strategy_test": True,
        "require_no_parameter_optimisation": True,
        "require_no_strategy_promotion": True,
        "required_spec_role": "Pre-registered design spec only",
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
    user_config = config.get("phase9c_preregistered_technical_rule_design_spec", {})
    return _deep_merge_dict(DEFAULT_PHASE9C_CONFIG, user_config)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value]

    return [str(value)]


def _join_list(value: Any) -> str:
    return "; ".join(_as_list(value))


def _contains_forbidden_keyword(text: str, forbidden_keywords: list[str]) -> bool:
    clean_text = text.lower()

    return any(keyword.lower() in clean_text for keyword in forbidden_keywords)


def _hypothesis_text_blob(hypothesis: dict[str, Any]) -> str:
    """Return only the testable hypothesis text for forbidden-keyword checks.

    Do not scan the forbidden_inputs field itself. A valid pre-registration
    spec is supposed to document forbidden inputs, so scanning that field makes
    the audit fail for doing the right thing.
    """
    fields_to_scan = [
        "hypothesis_id",
        "name",
        "source_evidence",
        "allowed_inputs",
        "proposed_rule_logic",
        "validation_gates",
        "failure_conditions",
        "readme_wording_if_passed",
        "readme_wording_if_mixed",
        "readme_wording_if_failed",
        "promotion_constraints",
    ]

    values: list[str] = []

    for field in fields_to_scan:
        value = hypothesis.get(field)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value is not None:
            values.append(str(value))

    return " ".join(values)


def build_phase9c_hypothesis_spec(phase_config: dict[str, Any]) -> pd.DataFrame:
    hypotheses = phase_config.get("hypotheses", [])

    rows: list[dict[str, Any]] = []

    for hypothesis in hypotheses:
        rows.append(
            {
                "hypothesis_id": str(hypothesis.get("hypothesis_id", "")),
                "name": str(hypothesis.get("name", "")),
                "source_evidence": _join_list(hypothesis.get("source_evidence")),
                "allowed_inputs": _join_list(hypothesis.get("allowed_inputs")),
                "forbidden_inputs": _join_list(hypothesis.get("forbidden_inputs")),
                "proposed_rule_logic": _join_list(
                    hypothesis.get("proposed_rule_logic")
                ),
                "validation_gates": _join_list(hypothesis.get("validation_gates")),
                "failure_conditions": _join_list(hypothesis.get("failure_conditions")),
                "readme_wording_if_passed": str(
                    hypothesis.get("readme_wording_if_passed", "")
                ),
                "readme_wording_if_mixed": str(
                    hypothesis.get("readme_wording_if_mixed", "")
                ),
                "readme_wording_if_failed": str(
                    hypothesis.get("readme_wording_if_failed", "")
                ),
                "promotion_constraints": _join_list(
                    hypothesis.get("promotion_constraints")
                ),
                "source_evidence_count": len(_as_list(hypothesis.get("source_evidence"))),
                "allowed_input_count": len(_as_list(hypothesis.get("allowed_inputs"))),
                "forbidden_input_count": len(
                    _as_list(hypothesis.get("forbidden_inputs"))
                ),
                "proposed_rule_logic_count": len(
                    _as_list(hypothesis.get("proposed_rule_logic"))
                ),
                "validation_gate_count": len(
                    _as_list(hypothesis.get("validation_gates"))
                ),
                "failure_condition_count": len(
                    _as_list(hypothesis.get("failure_conditions"))
                ),
                "promotion_constraint_count": len(
                    _as_list(hypothesis.get("promotion_constraints"))
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase9c_allowed_inputs(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    allowed_registry = set(_as_list(phase_config.get("allowed_input_registry")))
    hypotheses = phase_config.get("hypotheses", [])

    rows: list[dict[str, Any]] = []

    for hypothesis in hypotheses:
        hypothesis_id = str(hypothesis.get("hypothesis_id", ""))
        for input_name in _as_list(hypothesis.get("allowed_inputs")):
            rows.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "allowed_input": input_name,
                    "in_allowed_registry": input_name in allowed_registry,
                }
            )

    return pd.DataFrame(rows)


def build_phase9c_forbidden_inputs(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    forbidden_keywords = _as_list(phase_config.get("forbidden_input_keywords"))
    hypotheses = phase_config.get("hypotheses", [])

    rows: list[dict[str, Any]] = []

    for hypothesis in hypotheses:
        hypothesis_id = str(hypothesis.get("hypothesis_id", ""))
        text_blob = _hypothesis_text_blob(hypothesis)

        for keyword in forbidden_keywords:
            rows.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "forbidden_keyword": keyword,
                    "present_in_hypothesis_text": _contains_forbidden_keyword(
                        text_blob,
                        [keyword],
                    ),
                }
            )

    return pd.DataFrame(rows)


def build_phase9c_validation_gates(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for gate in _as_list(phase_config.get("required_validation_gates")):
        rows.append(
            {
                "scope": "global_required_gate",
                "hypothesis_id": "",
                "validation_gate": gate,
            }
        )

    for hypothesis in phase_config.get("hypotheses", []):
        hypothesis_id = str(hypothesis.get("hypothesis_id", ""))
        for gate in _as_list(hypothesis.get("validation_gates")):
            rows.append(
                {
                    "scope": "hypothesis_gate",
                    "hypothesis_id": hypothesis_id,
                    "validation_gate": gate,
                }
            )

    return pd.DataFrame(rows)


def build_phase9c_forbidden_actions(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows = [
        {
            "forbidden_action": action,
            "documented": True,
        }
        for action in _as_list(phase_config.get("forbidden_actions"))
    ]

    return pd.DataFrame(rows)


def build_phase9c_summary(
    phase_config: dict[str, Any],
    hypothesis_spec: pd.DataFrame,
    allowed_inputs: pd.DataFrame,
    forbidden_inputs: pd.DataFrame,
    validation_gates: pd.DataFrame,
    forbidden_actions: pd.DataFrame,
) -> pd.DataFrame:
    if allowed_inputs.empty:
        allowed_inputs_all_registered = False
    else:
        allowed_inputs_all_registered = bool(allowed_inputs["in_allowed_registry"].all())

    if forbidden_inputs.empty:
        forbidden_keywords_absent = True
    else:
        forbidden_keywords_absent = not bool(
            forbidden_inputs["present_in_hypothesis_text"].any()
        )

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role")),
                "proposed_test_phase": str(phase_config.get("proposed_test_phase")),
                "hypothesis_count": int(len(hypothesis_spec)),
                "allowed_input_rows": int(len(allowed_inputs)),
                "allowed_inputs_all_registered": allowed_inputs_all_registered,
                "forbidden_keyword_rows": int(len(forbidden_inputs)),
                "forbidden_keywords_absent": forbidden_keywords_absent,
                "validation_gate_rows": int(len(validation_gates)),
                "forbidden_action_rows": int(len(forbidden_actions)),
                "allow_strategy_test": bool(phase_config.get("allow_strategy_test", False)),
                "allow_parameter_optimisation": bool(
                    phase_config.get("allow_parameter_optimisation", False)
                ),
                "allow_strategy_promotion": bool(
                    phase_config.get("allow_strategy_promotion", False)
                ),
                "diagnostic_role": "Pre-registration only",
                "strategy_promotion": False,
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


def _hypothesis_counts_pass(
    hypothesis_spec: pd.DataFrame,
    column: str,
) -> bool:
    if hypothesis_spec.empty or column not in hypothesis_spec.columns:
        return False

    return bool((hypothesis_spec[column] > 0).all())


def _readme_wording_pass(hypothesis_spec: pd.DataFrame) -> bool:
    required = [
        "readme_wording_if_passed",
        "readme_wording_if_mixed",
        "readme_wording_if_failed",
    ]

    if hypothesis_spec.empty:
        return False

    for column in required:
        if column not in hypothesis_spec.columns:
            return False
        if not bool(hypothesis_spec[column].astype(str).str.len().gt(0).all()):
            return False

    return True


def build_phase9c_gate_report(
    phase_config: dict[str, Any],
    hypothesis_spec: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 9C summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    hypothesis_count = int(row["hypothesis_count"])
    min_hypotheses = int(gates.get("min_hypotheses", 1))
    max_hypotheses = int(gates.get("max_hypotheses", 2))
    required_role = str(
        gates.get("required_spec_role", "Pre-registered design spec only")
    )

    rows = [
        _gate_row(
            "Hypothesis count is bounded",
            min_hypotheses <= hypothesis_count <= max_hypotheses,
            f"{hypothesis_count} hypotheses; allowed {min_hypotheses}-{max_hypotheses}",
        ),
        _gate_row(
            "Source evidence is documented",
            (not gates.get("require_source_evidence", True))
            or _hypothesis_counts_pass(hypothesis_spec, "source_evidence_count"),
            "Each hypothesis must cite Phase 9A/9B evidence.",
        ),
        _gate_row(
            "Allowed inputs are documented",
            (not gates.get("require_allowed_inputs", True))
            or _hypothesis_counts_pass(hypothesis_spec, "allowed_input_count"),
            "Each hypothesis must list allowed inputs.",
        ),
        _gate_row(
            "Forbidden inputs are documented",
            (not gates.get("require_forbidden_inputs", True))
            or _hypothesis_counts_pass(hypothesis_spec, "forbidden_input_count"),
            "Each hypothesis must list forbidden inputs.",
        ),
        _gate_row(
            "Proposed rule logic is documented",
            (not gates.get("require_proposed_rule_logic", True))
            or _hypothesis_counts_pass(hypothesis_spec, "proposed_rule_logic_count"),
            "Each hypothesis must define logic before testing.",
        ),
        _gate_row(
            "Validation gates are documented",
            (not gates.get("require_validation_gates", True))
            or _hypothesis_counts_pass(hypothesis_spec, "validation_gate_count"),
            "Each hypothesis must define validation gates.",
        ),
        _gate_row(
            "Failure conditions are documented",
            (not gates.get("require_failure_conditions", True))
            or _hypothesis_counts_pass(hypothesis_spec, "failure_condition_count"),
            "Each hypothesis must define failure conditions.",
        ),
        _gate_row(
            "README wording outcomes are documented",
            (not gates.get("require_readme_wording", True))
            or _readme_wording_pass(hypothesis_spec),
            "Pass/mixed/fail wording must be pre-written.",
        ),
        _gate_row(
            "Promotion constraints are documented",
            (not gates.get("require_promotion_constraints", True))
            or _hypothesis_counts_pass(hypothesis_spec, "promotion_constraint_count"),
            "Each hypothesis must define promotion constraints.",
        ),
        _gate_row(
            "Allowed inputs stay inside registry",
            bool(row["allowed_inputs_all_registered"]),
            f"allowed_inputs_all_registered={bool(row['allowed_inputs_all_registered'])}",
        ),
        _gate_row(
            "Forbidden keywords are absent from allowed hypothesis text",
            (not gates.get("require_no_forbidden_inputs", True))
            or bool(row["forbidden_keywords_absent"]),
            f"forbidden_keywords_absent={bool(row['forbidden_keywords_absent'])}",
        ),
        _gate_row(
            "Spec does not allow strategy testing",
            (not gates.get("require_no_strategy_test", True))
            or not bool(row["allow_strategy_test"]),
            f"allow_strategy_test={bool(row['allow_strategy_test'])}",
        ),
        _gate_row(
            "Spec does not allow parameter optimisation",
            (not gates.get("require_no_parameter_optimisation", True))
            or not bool(row["allow_parameter_optimisation"]),
            (
                "allow_parameter_optimisation="
                f"{bool(row['allow_parameter_optimisation'])}"
            ),
        ),
        _gate_row(
            "Spec does not allow strategy promotion",
            (not gates.get("require_no_strategy_promotion", True))
            or not bool(row["allow_strategy_promotion"]),
            f"allow_strategy_promotion={bool(row['allow_strategy_promotion'])}",
        ),
        _gate_row(
            "Spec role is correct",
            str(row["spec_role"]) == required_role,
            f"spec_role={row['spec_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase9c_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — pre-registered spec only"
        interpretation = (
            "Phase 9C pre-registered the only technical-rule hypotheses allowed "
            "for a later Phase 9D test. It did not run performance tests, tune "
            "parameters, or promote a strategy."
        )
    else:
        verdict = "Failed pre-registration discipline"
        interpretation = (
            "Phase 9C did not satisfy every specification gate. Do not proceed "
            "to Phase 9D until the design spec is corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 9C",
                "diagnostic": "Pre-registered technical rule design spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase9c_markdown(
    *,
    hypothesis_spec: pd.DataFrame,
    allowed_inputs: pd.DataFrame,
    forbidden_inputs: pd.DataFrame,
    validation_gates: pd.DataFrame,
    forbidden_actions: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 9C — Pre-Registered Technical Rule Design Spec",
        "",
        "## Purpose",
        "",
        (
            "This report pre-registers the only technical-rule hypotheses allowed "
            "to move into a later Phase 9D test."
        ),
        "",
        (
            "It is not a strategy test, not a backtest, not parameter optimisation, "
            "and not strategy promotion."
        ),
        "",
        "## Hypothesis Spec",
        "",
        hypothesis_spec.to_markdown(index=False),
        "",
        "## Allowed Inputs",
        "",
        allowed_inputs.to_markdown(index=False),
        "",
        "## Forbidden Keyword Check",
        "",
        forbidden_inputs.to_markdown(index=False),
        "",
        "## Validation Gates",
        "",
        validation_gates.to_markdown(index=False),
        "",
        "## Forbidden Actions",
        "",
        forbidden_actions.to_markdown(index=False),
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
        "- This is a specification only.",
        "- It does not test or promote any rule.",
        "- The later Phase 9D test must follow this spec or be rejected.",
        "- Passing this phase does not imply the hypotheses will work.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase9c_preregistered_technical_rule_design_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "hypothesis_spec": empty,
            "allowed_inputs": empty,
            "forbidden_inputs": empty,
            "validation_gates": empty,
            "forbidden_actions": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    hypothesis_spec = build_phase9c_hypothesis_spec(phase_config)
    allowed_inputs = build_phase9c_allowed_inputs(phase_config)
    forbidden_inputs = build_phase9c_forbidden_inputs(phase_config)
    validation_gates = build_phase9c_validation_gates(phase_config)
    forbidden_actions = build_phase9c_forbidden_actions(phase_config)
    summary = build_phase9c_summary(
        phase_config,
        hypothesis_spec,
        allowed_inputs,
        forbidden_inputs,
        validation_gates,
        forbidden_actions,
    )
    gate_report = build_phase9c_gate_report(
        phase_config,
        hypothesis_spec,
        summary,
    )
    conclusion = build_phase9c_conclusion(gate_report)

    hypothesis_spec.to_csv(
        reports_path / "phase9c_preregistered_rule_hypothesis_spec.csv",
        index=False,
    )
    allowed_inputs.to_csv(
        reports_path / "phase9c_preregistered_rule_allowed_inputs.csv",
        index=False,
    )
    forbidden_inputs.to_csv(
        reports_path / "phase9c_preregistered_rule_forbidden_inputs.csv",
        index=False,
    )
    validation_gates.to_csv(
        reports_path / "phase9c_preregistered_rule_validation_gates.csv",
        index=False,
    )
    forbidden_actions.to_csv(
        reports_path / "phase9c_preregistered_rule_forbidden_actions.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase9c_preregistered_rule_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase9c_preregistered_rule_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase9c_preregistered_rule_conclusion.csv",
        index=False,
    )

    write_phase9c_markdown(
        hypothesis_spec=hypothesis_spec,
        allowed_inputs=allowed_inputs,
        forbidden_inputs=forbidden_inputs,
        validation_gates=validation_gates,
        forbidden_actions=forbidden_actions,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase9c_preregistered_technical_rule_design_spec.md",
    )

    print("Wrote Phase 9C pre-registered technical rule design spec reports.")

    return {
        "hypothesis_spec": hypothesis_spec,
        "allowed_inputs": allowed_inputs,
        "forbidden_inputs": forbidden_inputs,
        "validation_gates": validation_gates,
        "forbidden_actions": forbidden_actions,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }