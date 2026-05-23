from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE10E_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Pre-registered macro hypothesis design spec only",
    "proposed_test_phase": "Phase 10F",
    "allow_macro_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_model_feature_creation": False,
    "allow_model_training": False,
    "allow_strategy_test": False,
    "allow_strategy_promotion": False,
    "allowed_macro_input_registry": [],
    "allowed_evaluation_inputs": [],
    "forbidden_inputs": [],
    "hypotheses": [],
    "phase10f_boundary": {
        "allowed_next_step": "pre-registered macro-rule test only",
        "forbidden_next_step": "open-ended macro optimisation, ML model, or candidate promotion",
        "phase10f_may_test_only_preregistered_hypotheses": True,
        "phase10f_may_create_new_thresholds": False,
        "phase10f_may_add_new_inputs": False,
        "phase10f_may_train_model": False,
        "phase10f_may_promote_candidate": False,
    },
    "gates": {
        "min_hypotheses": 2,
        "max_hypotheses": 2,
        "require_source_evidence": True,
        "require_allowed_inputs": True,
        "require_allowed_inputs_inside_registry": True,
        "require_forbidden_inputs": True,
        "require_fixed_thresholds": True,
        "require_validation_gates": True,
        "require_failure_conditions": True,
        "require_readme_wording": True,
        "require_phase10f_boundary": True,
        "require_no_macro_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_model_feature_creation": True,
        "require_no_model_training": True,
        "require_no_strategy_test": True,
        "require_no_strategy_promotion": True,
        "required_spec_role": "Pre-registered macro hypothesis design spec only",
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
    user_config = config.get("phase10e_preregistered_macro_hypothesis_spec", {})
    return _deep_merge_dict(DEFAULT_PHASE10E_CONFIG, user_config)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _join_list(value: Any) -> str:
    return "; ".join(str(item) for item in _as_list(value))


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()

    if clean in {"true", "1", "yes", "y"}:
        return True
    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False

    return bool(value)


def _hypotheses(phase_config: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in _as_list(phase_config.get("hypotheses"))]


def build_phase10e_hypothesis_spec(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for hypothesis in _hypotheses(phase_config):
        fixed_thresholds = hypothesis.get("fixed_macro_thresholds", {})
        if not isinstance(fixed_thresholds, dict):
            fixed_thresholds = {}

        rows.append(
            {
                "hypothesis_id": str(hypothesis.get("hypothesis_id", "")),
                "name": str(hypothesis.get("name", "")),
                "source_phase": str(hypothesis.get("source_phase", "")),
                "source_evidence": _join_list(hypothesis.get("source_evidence")),
                "allowed_macro_inputs": _join_list(
                    hypothesis.get("allowed_macro_inputs")
                ),
                "allowed_macro_input_count": len(
                    _as_list(hypothesis.get("allowed_macro_inputs"))
                ),
                "fixed_macro_thresholds": "; ".join(
                    f"{key}={value}" for key, value in fixed_thresholds.items()
                ),
                "fixed_threshold_count": len(fixed_thresholds),
                "proposed_phase10f_test_logic": str(
                    hypothesis.get("proposed_phase10f_test_logic", "")
                ),
                "forbidden_tuning": _join_list(hypothesis.get("forbidden_tuning")),
                "validation_gates": _join_list(hypothesis.get("validation_gates")),
                "validation_gate_count": len(
                    _as_list(hypothesis.get("validation_gates"))
                ),
                "failure_conditions": _join_list(
                    hypothesis.get("failure_conditions")
                ),
                "failure_condition_count": len(
                    _as_list(hypothesis.get("failure_conditions"))
                ),
                "readme_wording_if_passed": str(
                    hypothesis.get("readme_wording_if_passed", "")
                ),
                "readme_wording_if_mixed": str(
                    hypothesis.get("readme_wording_if_mixed", "")
                ),
                "readme_wording_if_failed": str(
                    hypothesis.get("readme_wording_if_failed", "")
                ),
                "max_allowed_role_after_phase10f": str(
                    hypothesis.get(
                        "max_allowed_role_after_phase10f",
                        "Candidate for further validation only",
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase10e_allowed_inputs(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    registry = set(str(item) for item in _as_list(phase_config.get("allowed_macro_input_registry")))

    for hypothesis in _hypotheses(phase_config):
        hypothesis_id = str(hypothesis.get("hypothesis_id", ""))

        for item in _as_list(hypothesis.get("allowed_macro_inputs")):
            item_str = str(item)
            rows.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "allowed_macro_input": item_str,
                    "registered": item_str in registry,
                }
            )

    frame = pd.DataFrame(rows)

    if not frame.empty:
        frame["result"] = frame["registered"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase10e_registry(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {"input_type": "macro_input", "name": str(item)}
        for item in _as_list(phase_config.get("allowed_macro_input_registry"))
    ]
    rows.extend(
        {"input_type": "evaluation_input", "name": str(item)}
        for item in _as_list(phase_config.get("allowed_evaluation_inputs"))
    )

    return pd.DataFrame(rows)


def build_phase10e_forbidden_inputs(phase_config: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "forbidden_input": str(item),
                "reason": "Not allowed in Phase 10F macro-rule test unless a later pre-registration explicitly permits it.",
            }
            for item in _as_list(phase_config.get("forbidden_inputs"))
        ]
    )


def build_phase10e_validation_gates(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for hypothesis in _hypotheses(phase_config):
        hypothesis_id = str(hypothesis.get("hypothesis_id", ""))

        for gate in _as_list(hypothesis.get("validation_gates")):
            rows.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "validation_gate": str(gate),
                }
            )

    return pd.DataFrame(rows)


def build_phase10e_failure_conditions(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for hypothesis in _hypotheses(phase_config):
        hypothesis_id = str(hypothesis.get("hypothesis_id", ""))

        for condition in _as_list(hypothesis.get("failure_conditions")):
            rows.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "failure_condition": str(condition),
                }
            )

    return pd.DataFrame(rows)


def build_phase10e_phase10f_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase10f_boundary", {})

    rows = [
        {
            "boundary_item": "phase10f_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "pre-registered" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase10f_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": (
                "optimisation" in str(boundary.get("forbidden_next_step", "")).lower()
                or "promotion" in str(boundary.get("forbidden_next_step", "")).lower()
                or "model" in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        },
        {
            "boundary_item": "phase10f_may_test_only_preregistered_hypotheses",
            "value": bool(boundary.get("phase10f_may_test_only_preregistered_hypotheses", False)),
            "passed": bool(boundary.get("phase10f_may_test_only_preregistered_hypotheses", False)),
        },
        {
            "boundary_item": "phase10f_may_create_new_thresholds",
            "value": bool(boundary.get("phase10f_may_create_new_thresholds", True)),
            "passed": not bool(boundary.get("phase10f_may_create_new_thresholds", True)),
        },
        {
            "boundary_item": "phase10f_may_add_new_inputs",
            "value": bool(boundary.get("phase10f_may_add_new_inputs", True)),
            "passed": not bool(boundary.get("phase10f_may_add_new_inputs", True)),
        },
        {
            "boundary_item": "phase10f_may_train_model",
            "value": bool(boundary.get("phase10f_may_train_model", True)),
            "passed": not bool(boundary.get("phase10f_may_train_model", True)),
        },
        {
            "boundary_item": "phase10f_may_promote_candidate",
            "value": bool(boundary.get("phase10f_may_promote_candidate", True)),
            "passed": not bool(boundary.get("phase10f_may_promote_candidate", True)),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase10e_summary(
    phase_config: dict[str, Any],
    hypothesis_spec: pd.DataFrame,
    allowed_inputs: pd.DataFrame,
    forbidden_inputs: pd.DataFrame,
    validation_gates: pd.DataFrame,
    failure_conditions: pd.DataFrame,
    phase10f_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    allowed_registered = (
        bool(allowed_inputs["registered"].all()) if not allowed_inputs.empty else False
    )

    required_readme_columns = [
        "readme_wording_if_passed",
        "readme_wording_if_mixed",
        "readme_wording_if_failed",
    ]
    readme_wording_complete = (
        bool(
            hypothesis_spec[required_readme_columns]
            .apply(lambda column: column.astype(str).str.strip().ne("").all())
            .all()
        )
        if not hypothesis_spec.empty
        else False
    )

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "proposed_test_phase": str(phase_config.get("proposed_test_phase", "")),
                "hypothesis_count": int(len(hypothesis_spec)),
                "allowed_input_rows": int(len(allowed_inputs)),
                "allowed_inputs_all_registered": allowed_registered,
                "forbidden_input_rows": int(len(forbidden_inputs)),
                "validation_gate_rows": int(len(validation_gates)),
                "failure_condition_rows": int(len(failure_conditions)),
                "readme_wording_complete": readme_wording_complete,
                "phase10f_boundary_passed": bool(
                    phase10f_boundary_check["passed"].all()
                )
                if not phase10f_boundary_check.empty
                else False,
                "allow_macro_signal_creation": bool(
                    phase_config.get("allow_macro_signal_creation", False)
                ),
                "allow_allocation_rule_creation": bool(
                    phase_config.get("allow_allocation_rule_creation", False)
                ),
                "allow_model_feature_creation": bool(
                    phase_config.get("allow_model_feature_creation", False)
                ),
                "allow_model_training": bool(
                    phase_config.get("allow_model_training", False)
                ),
                "allow_strategy_test": bool(
                    phase_config.get("allow_strategy_test", False)
                ),
                "allow_strategy_promotion": bool(
                    phase_config.get("allow_strategy_promotion", False)
                ),
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


def build_phase10e_gate_report(
    phase_config: dict[str, Any],
    hypothesis_spec: pd.DataFrame,
    allowed_inputs: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 10E summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    min_hypotheses = int(gates.get("min_hypotheses", 2))
    max_hypotheses = int(gates.get("max_hypotheses", 2))
    required_role = str(
        gates.get(
            "required_spec_role",
            "Pre-registered macro hypothesis design spec only",
        )
    )

    source_evidence_complete = (
        bool(hypothesis_spec["source_evidence"].astype(str).str.strip().ne("").all())
        if not hypothesis_spec.empty
        else False
    )
    allowed_inputs_complete = (
        int(row["allowed_input_rows"]) > 0
        and bool(row["allowed_inputs_all_registered"])
    )
    fixed_thresholds_complete = (
        bool((hypothesis_spec["fixed_threshold_count"] > 0).all())
        if not hypothesis_spec.empty
        else False
    )
    validation_gates_complete = int(row["validation_gate_rows"]) >= int(
        row["hypothesis_count"]
    )
    failure_conditions_complete = int(row["failure_condition_rows"]) >= int(
        row["hypothesis_count"]
    )

    rows = [
        _gate_row(
            "Hypothesis count is bounded",
            min_hypotheses <= int(row["hypothesis_count"]) <= max_hypotheses,
            f"{int(row['hypothesis_count'])} hypotheses; allowed {min_hypotheses}-{max_hypotheses}",
        ),
        _gate_row(
            "Source evidence is documented",
            (not gates.get("require_source_evidence", True))
            or source_evidence_complete,
            "Each hypothesis must document Phase 10D evidence.",
        ),
        _gate_row(
            "Allowed macro inputs are documented",
            (not gates.get("require_allowed_inputs", True))
            or int(row["allowed_input_rows"]) > 0,
            f"allowed_input_rows={int(row['allowed_input_rows'])}",
        ),
        _gate_row(
            "Allowed macro inputs stay inside registry",
            (not gates.get("require_allowed_inputs_inside_registry", True))
            or allowed_inputs_complete,
            f"allowed_inputs_all_registered={bool(row['allowed_inputs_all_registered'])}",
        ),
        _gate_row(
            "Forbidden inputs are documented",
            (not gates.get("require_forbidden_inputs", True))
            or int(row["forbidden_input_rows"]) > 0,
            f"forbidden_input_rows={int(row['forbidden_input_rows'])}",
        ),
        _gate_row(
            "Fixed thresholds are documented",
            (not gates.get("require_fixed_thresholds", True))
            or fixed_thresholds_complete,
            "Each hypothesis must lock fixed macro thresholds.",
        ),
        _gate_row(
            "Validation gates are documented",
            (not gates.get("require_validation_gates", True))
            or validation_gates_complete,
            f"validation_gate_rows={int(row['validation_gate_rows'])}",
        ),
        _gate_row(
            "Failure conditions are documented",
            (not gates.get("require_failure_conditions", True))
            or failure_conditions_complete,
            f"failure_condition_rows={int(row['failure_condition_rows'])}",
        ),
        _gate_row(
            "README wording outcomes are documented",
            (not gates.get("require_readme_wording", True))
            or bool(row["readme_wording_complete"]),
            f"readme_wording_complete={bool(row['readme_wording_complete'])}",
        ),
        _gate_row(
            "Phase 10F boundary is pre-registered-test only",
            (not gates.get("require_phase10f_boundary", True))
            or bool(row["phase10f_boundary_passed"]),
            f"phase10f_boundary_passed={bool(row['phase10f_boundary_passed'])}",
        ),
        _gate_row(
            "Spec does not allow macro signal creation",
            (not gates.get("require_no_macro_signal_creation", True))
            or not bool(row["allow_macro_signal_creation"]),
            f"allow_macro_signal_creation={bool(row['allow_macro_signal_creation'])}",
        ),
        _gate_row(
            "Spec does not allow allocation rule creation",
            (not gates.get("require_no_allocation_rule_creation", True))
            or not bool(row["allow_allocation_rule_creation"]),
            f"allow_allocation_rule_creation={bool(row['allow_allocation_rule_creation'])}",
        ),
        _gate_row(
            "Spec does not allow model feature creation",
            (not gates.get("require_no_model_feature_creation", True))
            or not bool(row["allow_model_feature_creation"]),
            f"allow_model_feature_creation={bool(row['allow_model_feature_creation'])}",
        ),
        _gate_row(
            "Spec does not allow model training",
            (not gates.get("require_no_model_training", True))
            or not bool(row["allow_model_training"]),
            f"allow_model_training={bool(row['allow_model_training'])}",
        ),
        _gate_row(
            "Spec does not allow strategy testing",
            (not gates.get("require_no_strategy_test", True))
            or not bool(row["allow_strategy_test"]),
            f"allow_strategy_test={bool(row['allow_strategy_test'])}",
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


def build_phase10e_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — pre-registered macro hypothesis spec only"
        interpretation = (
            "Phase 10E pre-registered the only macro hypotheses allowed for a "
            "later Phase 10F test. It did not create a macro signal, allocation "
            "rule, model feature, strategy test, or candidate promotion."
        )
    else:
        verdict = "Failed macro hypothesis pre-registration discipline"
        interpretation = (
            "Phase 10E did not satisfy every pre-registration gate. Do not open "
            "Phase 10F until the macro hypothesis spec is corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 10E",
                "diagnostic": "Pre-registered macro hypothesis design spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase10e_markdown(
    *,
    registry: pd.DataFrame,
    hypothesis_spec: pd.DataFrame,
    allowed_inputs: pd.DataFrame,
    forbidden_inputs: pd.DataFrame,
    validation_gates: pd.DataFrame,
    failure_conditions: pd.DataFrame,
    phase10f_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 10E — Pre-Registered Macro Hypothesis Design Spec",
        "",
        "## Purpose",
        "",
        (
            "This phase pre-registers the only macro hypotheses allowed to move "
            "into a later Phase 10F macro-rule test."
        ),
        "",
        (
            "It does not create macro signals, allocation overlays, model features, "
            "model training, strategy tests, or candidate promotion."
        ),
        "",
        "## Registry",
        "",
        registry.to_markdown(index=False),
        "",
        "## Hypothesis Spec",
        "",
        hypothesis_spec.to_markdown(index=False),
        "",
        "## Allowed Inputs",
        "",
        allowed_inputs.to_markdown(index=False),
        "",
        "## Forbidden Inputs",
        "",
        forbidden_inputs.to_markdown(index=False),
        "",
        "## Validation Gates",
        "",
        validation_gates.to_markdown(index=False),
        "",
        "## Failure Conditions",
        "",
        failure_conditions.to_markdown(index=False),
        "",
        "## Phase 10F Boundary Check",
        "",
        phase10f_boundary_check.to_markdown(index=False),
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
        "- This is a pre-registration spec only.",
        "- Phase 10D macro diagnostics are not trading rules.",
        "- Phase 10F may only test the pre-registered hypotheses.",
        "- Passing Phase 10F would not promote a macro rule automatically.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase10e_preregistered_macro_hypothesis_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "registry": empty,
            "hypothesis_spec": empty,
            "allowed_inputs": empty,
            "forbidden_inputs": empty,
            "validation_gates": empty,
            "failure_conditions": empty,
            "phase10f_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    registry = build_phase10e_registry(phase_config)
    hypothesis_spec = build_phase10e_hypothesis_spec(phase_config)
    allowed_inputs = build_phase10e_allowed_inputs(phase_config)
    forbidden_inputs = build_phase10e_forbidden_inputs(phase_config)
    validation_gates = build_phase10e_validation_gates(phase_config)
    failure_conditions = build_phase10e_failure_conditions(phase_config)
    phase10f_boundary_check = build_phase10e_phase10f_boundary_check(phase_config)
    summary = build_phase10e_summary(
        phase_config=phase_config,
        hypothesis_spec=hypothesis_spec,
        allowed_inputs=allowed_inputs,
        forbidden_inputs=forbidden_inputs,
        validation_gates=validation_gates,
        failure_conditions=failure_conditions,
        phase10f_boundary_check=phase10f_boundary_check,
    )
    gate_report = build_phase10e_gate_report(
        phase_config=phase_config,
        hypothesis_spec=hypothesis_spec,
        allowed_inputs=allowed_inputs,
        summary=summary,
    )
    conclusion = build_phase10e_conclusion(gate_report)

    registry.to_csv(reports_path / "phase10e_macro_input_registry.csv", index=False)
    hypothesis_spec.to_csv(
        reports_path / "phase10e_macro_hypothesis_spec.csv",
        index=False,
    )
    allowed_inputs.to_csv(
        reports_path / "phase10e_macro_allowed_inputs.csv",
        index=False,
    )
    forbidden_inputs.to_csv(
        reports_path / "phase10e_macro_forbidden_inputs.csv",
        index=False,
    )
    validation_gates.to_csv(
        reports_path / "phase10e_macro_validation_gates.csv",
        index=False,
    )
    failure_conditions.to_csv(
        reports_path / "phase10e_macro_failure_conditions.csv",
        index=False,
    )
    phase10f_boundary_check.to_csv(
        reports_path / "phase10e_macro_phase10f_boundary_check.csv",
        index=False,
    )
    summary.to_csv(reports_path / "phase10e_macro_summary.csv", index=False)
    gate_report.to_csv(reports_path / "phase10e_macro_gate_report.csv", index=False)
    conclusion.to_csv(reports_path / "phase10e_macro_conclusion.csv", index=False)

    write_phase10e_markdown(
        registry=registry,
        hypothesis_spec=hypothesis_spec,
        allowed_inputs=allowed_inputs,
        forbidden_inputs=forbidden_inputs,
        validation_gates=validation_gates,
        failure_conditions=failure_conditions,
        phase10f_boundary_check=phase10f_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase10e_preregistered_macro_hypothesis_spec.md",
    )

    print("Wrote Phase 10E pre-registered macro hypothesis spec reports.")

    return {
        "registry": registry,
        "hypothesis_spec": hypothesis_spec,
        "allowed_inputs": allowed_inputs,
        "forbidden_inputs": forbidden_inputs,
        "validation_gates": validation_gates,
        "failure_conditions": failure_conditions,
        "phase10f_boundary_check": phase10f_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }