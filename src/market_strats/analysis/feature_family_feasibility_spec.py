from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE10A_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": "Feature-family feasibility spec only",
    "proposed_next_phase": "Phase 10B",
    "allow_data_ingestion": False,
    "allow_model_training": False,
    "allow_strategy_test": False,
    "allow_strategy_promotion": False,
    "expected_first_family": "macro_rates_inflation",
    "scoring_weights": {
        "conceptual_relevance": 1.25,
        "data_availability": 1.00,
        "leakage_control": 1.50,
        "update_frequency_fit": 1.00,
        "validation_clarity": 1.25,
        "overfit_resistance": 1.50,
        "implementation_readiness": 1.00,
    },
    "feature_families": [],
    "gates": {
        "min_feature_families": 4,
        "max_feature_families": 4,
        "require_expected_first_family": True,
        "require_no_active_disqualifier_for_recommended_family": True,
        "require_data_requirements": True,
        "require_leakage_controls": True,
        "require_validation_requirements": True,
        "require_scorecard": True,
        "require_no_data_ingestion": True,
        "require_no_model_training": True,
        "require_no_strategy_test": True,
        "require_no_strategy_promotion": True,
        "required_spec_role": "Feature-family feasibility spec only",
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
    user_config = config.get("phase10a_feature_family_feasibility_spec", {})
    return _deep_merge_dict(DEFAULT_PHASE10A_CONFIG, user_config)


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


def _families(phase_config: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in _as_list(phase_config.get("feature_families"))]


def build_phase10a_family_spec(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for family in _families(phase_config):
        disqualifiers = _as_list(family.get("disqualifiers"))
        active_disqualifiers = [
            str(item.get("name", ""))
            for item in disqualifiers
            if isinstance(item, dict) and _bool_value(item.get("active", False))
        ]

        rows.append(
            {
                "family_id": str(family.get("family_id", "")),
                "name": str(family.get("name", "")),
                "role": str(family.get("role", "")),
                "candidate_priority": int(family.get("candidate_priority", 999)),
                "rationale": _join_list(family.get("rationale")),
                "allowed_feature_examples": _join_list(
                    family.get("allowed_feature_examples")
                ),
                "data_requirement_count": len(_as_list(family.get("data_requirements"))),
                "leakage_control_count": len(_as_list(family.get("leakage_controls"))),
                "validation_requirement_count": len(
                    _as_list(family.get("validation_requirements"))
                ),
                "active_disqualifier_count": len(active_disqualifiers),
                "active_disqualifiers": "; ".join(active_disqualifiers),
            }
        )

    return pd.DataFrame(rows)


def build_phase10a_data_requirements(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for family in _families(phase_config):
        family_id = str(family.get("family_id", ""))

        for requirement in _as_list(family.get("data_requirements")):
            if not isinstance(requirement, dict):
                continue

            rows.append(
                {
                    "family_id": family_id,
                    "data_type": str(requirement.get("data_type", "")),
                    "frequency": str(requirement.get("frequency", "")),
                    "timing_requirement": str(
                        requirement.get("timing_requirement", "")
                    ),
                    "revision_policy": str(requirement.get("revision_policy", "")),
                    "minimum_history_requirement": str(
                        requirement.get("minimum_history_requirement", "")
                    ),
                }
            )

    return pd.DataFrame(rows)


def build_phase10a_leakage_controls(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for family in _families(phase_config):
        family_id = str(family.get("family_id", ""))

        for control in _as_list(family.get("leakage_controls")):
            rows.append(
                {
                    "family_id": family_id,
                    "leakage_control": str(control),
                }
            )

    return pd.DataFrame(rows)


def build_phase10a_validation_requirements(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for family in _families(phase_config):
        family_id = str(family.get("family_id", ""))

        for requirement in _as_list(family.get("validation_requirements")):
            rows.append(
                {
                    "family_id": family_id,
                    "validation_requirement": str(requirement),
                }
            )

    return pd.DataFrame(rows)


def build_phase10a_scorecard(phase_config: dict[str, Any]) -> pd.DataFrame:
    weights = {
        str(key): float(value)
        for key, value in phase_config.get("scoring_weights", {}).items()
    }
    rows: list[dict[str, Any]] = []

    for family in _families(phase_config):
        family_id = str(family.get("family_id", ""))
        scorecard = family.get("scorecard", {})

        if not isinstance(scorecard, dict):
            scorecard = {}

        row: dict[str, Any] = {
            "family_id": family_id,
            "name": str(family.get("name", "")),
            "candidate_priority": int(family.get("candidate_priority", 999)),
        }

        weighted_score = 0.0
        max_weighted_score = 0.0

        for metric, weight in weights.items():
            score = float(scorecard.get(metric, 0.0))
            row[metric] = score
            weighted_score += score * weight
            max_weighted_score += 5.0 * weight

        row["weighted_score"] = weighted_score
        row["max_weighted_score"] = max_weighted_score
        row["weighted_score_pct"] = (
            weighted_score / max_weighted_score if max_weighted_score else 0.0
        )

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame = frame.sort_values(
        ["weighted_score", "candidate_priority"],
        ascending=[False, True],
    ).reset_index(drop=True)
    frame["score_rank"] = frame.index + 1

    return frame


def build_phase10a_recommendation(
    family_spec: pd.DataFrame,
    scorecard: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if scorecard.empty:
        return pd.DataFrame(
            [
                {
                    "recommended_family_id": "",
                    "recommended_family_name": "",
                    "expected_first_family": str(
                        phase_config.get("expected_first_family", "")
                    ),
                    "matches_expected_first_family": False,
                    "recommended_family_active_disqualifiers": "",
                    "recommended_family_has_active_disqualifier": True,
                    "next_phase": str(phase_config.get("proposed_next_phase", "")),
                    "recommendation": "No recommendation; scorecard empty.",
                }
            ]
        )

    top = scorecard.iloc[0]
    top_family_id = str(top["family_id"])
    expected = str(phase_config.get("expected_first_family", ""))

    family_rows = family_spec[family_spec["family_id"] == top_family_id]
    active_disqualifiers = ""

    if not family_rows.empty:
        active_disqualifiers = str(family_rows.iloc[0].get("active_disqualifiers", ""))

    has_active_disqualifier = bool(active_disqualifiers.strip())

    recommendation = (
        f"Open {phase_config.get('proposed_next_phase', 'Phase 10B')} as a "
        f"data-source and leakage audit for {top_family_id}. Do not model yet."
    )

    return pd.DataFrame(
        [
            {
                "recommended_family_id": top_family_id,
                "recommended_family_name": str(top["name"]),
                "expected_first_family": expected,
                "matches_expected_first_family": top_family_id == expected,
                "recommended_family_active_disqualifiers": active_disqualifiers,
                "recommended_family_has_active_disqualifier": has_active_disqualifier,
                "weighted_score": float(top["weighted_score"]),
                "weighted_score_pct": float(top["weighted_score_pct"]),
                "next_phase": str(phase_config.get("proposed_next_phase", "")),
                "recommendation": recommendation,
            }
        ]
    )


def build_phase10a_summary(
    phase_config: dict[str, Any],
    family_spec: pd.DataFrame,
    data_requirements: pd.DataFrame,
    leakage_controls: pd.DataFrame,
    validation_requirements: pd.DataFrame,
    scorecard: pd.DataFrame,
    recommendation: pd.DataFrame,
) -> pd.DataFrame:
    recommended = recommendation.iloc[0] if not recommendation.empty else {}

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "family_count": int(len(family_spec)),
                "data_requirement_rows": int(len(data_requirements)),
                "leakage_control_rows": int(len(leakage_controls)),
                "validation_requirement_rows": int(len(validation_requirements)),
                "scorecard_rows": int(len(scorecard)),
                "recommended_family_id": str(
                    recommended.get("recommended_family_id", "")
                ),
                "matches_expected_first_family": _bool_value(
                    recommended.get("matches_expected_first_family", False)
                ),
                "recommended_family_has_active_disqualifier": _bool_value(
                    recommended.get(
                        "recommended_family_has_active_disqualifier",
                        True,
                    )
                ),
                "allow_data_ingestion": bool(
                    phase_config.get("allow_data_ingestion", False)
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


def _counts_positive_by_family(
    family_spec: pd.DataFrame,
    column: str,
) -> bool:
    if family_spec.empty or column not in family_spec.columns:
        return False

    return bool((family_spec[column] > 0).all())


def build_phase10a_gate_report(
    phase_config: dict[str, Any],
    family_spec: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 10A summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    family_count = int(row["family_count"])
    min_families = int(gates.get("min_feature_families", 4))
    max_families = int(gates.get("max_feature_families", 4))
    required_role = str(
        gates.get("required_spec_role", "Feature-family feasibility spec only")
    )

    rows = [
        _gate_row(
            "Feature-family count is bounded",
            min_families <= family_count <= max_families,
            f"{family_count} families; allowed {min_families}-{max_families}",
        ),
        _gate_row(
            "Recommended family matches expected first family",
            (not gates.get("require_expected_first_family", True))
            or bool(row["matches_expected_first_family"]),
            f"recommended_family_id={row['recommended_family_id']}",
        ),
        _gate_row(
            "Recommended family has no active disqualifier",
            (
                not gates.get(
                    "require_no_active_disqualifier_for_recommended_family",
                    True,
                )
            )
            or not bool(row["recommended_family_has_active_disqualifier"]),
            (
                "recommended_family_has_active_disqualifier="
                f"{bool(row['recommended_family_has_active_disqualifier'])}"
            ),
        ),
        _gate_row(
            "Each family documents data requirements",
            (not gates.get("require_data_requirements", True))
            or _counts_positive_by_family(family_spec, "data_requirement_count"),
            "Every family must define data requirements.",
        ),
        _gate_row(
            "Each family documents leakage controls",
            (not gates.get("require_leakage_controls", True))
            or _counts_positive_by_family(family_spec, "leakage_control_count"),
            "Every family must define leakage controls.",
        ),
        _gate_row(
            "Each family documents validation requirements",
            (not gates.get("require_validation_requirements", True))
            or _counts_positive_by_family(
                family_spec,
                "validation_requirement_count",
            ),
            "Every family must define validation requirements.",
        ),
        _gate_row(
            "Scorecard exists for all families",
            (not gates.get("require_scorecard", True))
            or int(row["scorecard_rows"]) == family_count,
            f"scorecard_rows={int(row['scorecard_rows'])}",
        ),
        _gate_row(
            "Spec does not allow data ingestion",
            (not gates.get("require_no_data_ingestion", True))
            or not bool(row["allow_data_ingestion"]),
            f"allow_data_ingestion={bool(row['allow_data_ingestion'])}",
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


def build_phase10a_conclusion(
    gate_report: pd.DataFrame,
    recommendation: pd.DataFrame,
) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if recommendation.empty:
        recommended_family = ""
        next_phase = ""
    else:
        recommended_family = str(recommendation.iloc[0]["recommended_family_id"])
        next_phase = str(recommendation.iloc[0]["next_phase"])

    if all_passed:
        verdict = "Completed — feature-family feasibility spec only"
        interpretation = (
            f"Phase 10A selected {recommended_family} as the first non-price "
            f"feature family to audit in {next_phase}. This does not ingest data, "
            "train a model, test a strategy, or promote a candidate."
        )
    else:
        verdict = "Failed feature-family feasibility discipline"
        interpretation = (
            "Phase 10A did not satisfy every feasibility gate. Do not open Phase "
            "10B until the feature-family specification is corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 10A",
                "diagnostic": "Feature-family feasibility spec",
                "verdict": verdict,
                "recommended_family": recommended_family,
                "next_phase": next_phase,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase10a_markdown(
    *,
    family_spec: pd.DataFrame,
    data_requirements: pd.DataFrame,
    leakage_controls: pd.DataFrame,
    validation_requirements: pd.DataFrame,
    scorecard: pd.DataFrame,
    recommendation: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 10A — Feature-Family Feasibility Spec",
        "",
        "## Purpose",
        "",
        (
            "This report evaluates which non-price feature family should be audited "
            "next. It is a specification only."
        ),
        "",
        (
            "It does not ingest data, train a model, test a strategy, or promote a "
            "candidate."
        ),
        "",
        "## Family Spec",
        "",
        family_spec.to_markdown(index=False),
        "",
        "## Data Requirements",
        "",
        data_requirements.to_markdown(index=False),
        "",
        "## Leakage Controls",
        "",
        leakage_controls.to_markdown(index=False),
        "",
        "## Validation Requirements",
        "",
        validation_requirements.to_markdown(index=False),
        "",
        "## Scorecard",
        "",
        scorecard.to_markdown(index=False),
        "",
        "## Recommendation",
        "",
        recommendation.to_markdown(index=False),
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
        "- This is a feasibility specification only.",
        "- It does not prove that macro, fundamental, sentiment, or ML features work.",
        "- The recommended family must still pass a data-source and leakage audit.",
        "- No Phase 10 strategy test is allowed from this phase alone.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase10a_feature_family_feasibility_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "family_spec": empty,
            "data_requirements": empty,
            "leakage_controls": empty,
            "validation_requirements": empty,
            "scorecard": empty,
            "recommendation": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    family_spec = build_phase10a_family_spec(phase_config)
    data_requirements = build_phase10a_data_requirements(phase_config)
    leakage_controls = build_phase10a_leakage_controls(phase_config)
    validation_requirements = build_phase10a_validation_requirements(phase_config)
    scorecard = build_phase10a_scorecard(phase_config)
    recommendation = build_phase10a_recommendation(
        family_spec,
        scorecard,
        phase_config,
    )
    summary = build_phase10a_summary(
        phase_config,
        family_spec,
        data_requirements,
        leakage_controls,
        validation_requirements,
        scorecard,
        recommendation,
    )
    gate_report = build_phase10a_gate_report(
        phase_config,
        family_spec,
        summary,
    )
    conclusion = build_phase10a_conclusion(gate_report, recommendation)

    family_spec.to_csv(
        reports_path / "phase10a_feature_family_spec.csv",
        index=False,
    )
    data_requirements.to_csv(
        reports_path / "phase10a_feature_family_data_requirements.csv",
        index=False,
    )
    leakage_controls.to_csv(
        reports_path / "phase10a_feature_family_leakage_controls.csv",
        index=False,
    )
    validation_requirements.to_csv(
        reports_path / "phase10a_feature_family_validation_requirements.csv",
        index=False,
    )
    scorecard.to_csv(
        reports_path / "phase10a_feature_family_scorecard.csv",
        index=False,
    )
    recommendation.to_csv(
        reports_path / "phase10a_feature_family_recommendation.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase10a_feature_family_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase10a_feature_family_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase10a_feature_family_conclusion.csv",
        index=False,
    )

    write_phase10a_markdown(
        family_spec=family_spec,
        data_requirements=data_requirements,
        leakage_controls=leakage_controls,
        validation_requirements=validation_requirements,
        scorecard=scorecard,
        recommendation=recommendation,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase10a_feature_family_feasibility_spec.md",
    )

    print("Wrote Phase 10A feature-family feasibility spec reports.")

    return {
        "family_spec": family_spec,
        "data_requirements": data_requirements,
        "leakage_controls": leakage_controls,
        "validation_requirements": validation_requirements,
        "scorecard": scorecard,
        "recommendation": recommendation,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }