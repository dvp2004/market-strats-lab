from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE11A_CONFIG: dict[str, Any] = {
    "enabled": False,
    "review_role": "Architecture review for richer information layers only",
    "phase_branch": "Phase 11 architecture review",
    "proposed_next_phase": "Phase 11B",
    "allow_new_indicator_rule": False,
    "allow_macro_rule_retry": False,
    "allow_sentiment_ingestion": False,
    "allow_fundamental_ingestion": False,
    "allow_model_training": False,
    "allow_strategy_backtest": False,
    "allow_candidate_promotion": False,
    "prior_branch_findings": {},
    "architecture_candidates": [],
    "recommended_next_step": {},
    "gates": {
        "require_prior_failures_documented": True,
        "require_architecture_candidates": True,
        "min_architecture_candidates": 5,
        "require_simple_overlay_rejected_as_immediate_next": True,
        "require_preferred_architecture_identified": True,
        "require_next_step_spec_only": True,
        "require_no_new_indicator_rule": True,
        "require_no_macro_rule_retry": True,
        "require_no_sentiment_ingestion": True,
        "require_no_fundamental_ingestion": True,
        "require_no_model_training": True,
        "require_no_strategy_backtest": True,
        "require_no_candidate_promotion": True,
        "required_review_role": "Architecture review for richer information layers only",
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
    user_config = config.get("phase11a_richer_information_architecture_review", {})
    return _deep_merge_dict(DEFAULT_PHASE11A_CONFIG, user_config)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _join_list(value: Any) -> str:
    return "; ".join(str(item) for item in _as_list(value))


def build_phase11a_prior_branch_findings(phase_config: dict[str, Any]) -> pd.DataFrame:
    findings = phase_config.get("prior_branch_findings", {})
    rows: list[dict[str, Any]] = []

    for branch_id, branch in findings.items():
        rows.append(
            {
                "branch_id": str(branch_id),
                "branch": str(branch.get("branch", "")),
                "diagnostic_evidence": str(branch.get("diagnostic_evidence", "")),
                "preregistration": str(branch.get("preregistration", "")),
                "rule_test_result": str(branch.get("rule_test_result", "")),
                "closeout": str(branch.get("closeout", "")),
                "implication": str(branch.get("implication", "")),
                "rule_extension_failed": "failed" in str(
                    branch.get("rule_test_result", "")
                ).lower(),
                "closed_without_promotion": "without promotion" in str(
                    branch.get("closeout", "")
                ).lower(),
            }
        )

    return pd.DataFrame(rows)


def build_phase11a_architecture_candidates(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for candidate in _as_list(phase_config.get("architecture_candidates")):
        rows.append(
            {
                "architecture_id": str(candidate.get("architecture_id", "")),
                "name": str(candidate.get("name", "")),
                "description": str(candidate.get("description", "")),
                "allowed_as_next_branch": bool(
                    candidate.get("allowed_as_next_branch", False)
                ),
                "reason": str(candidate.get("reason", "")),
                "complexity": str(candidate.get("complexity", "")),
                "overfit_risk": str(candidate.get("overfit_risk", "")),
                "interpretability": str(candidate.get("interpretability", "")),
                "validation_burden": str(candidate.get("validation_burden", "")),
                "recommended_role": str(candidate.get("recommended_role", "")),
            }
        )

    return pd.DataFrame(rows)


def build_phase11a_architecture_risk_matrix(
    architecture_candidates: pd.DataFrame,
) -> pd.DataFrame:
    if architecture_candidates.empty:
        return pd.DataFrame()

    risk_order = {
        "low": 1,
        "medium": 2,
        "medium_high": 3,
        "high": 4,
    }
    interpretability_order = {
        "low": 4,
        "medium": 3,
        "high": 1,
    }

    out = architecture_candidates.copy()
    out["overfit_risk_score"] = out["overfit_risk"].map(risk_order).fillna(3)
    out["complexity_score"] = out["complexity"].map(risk_order).fillna(3)
    out["validation_burden_score"] = out["validation_burden"].map(risk_order).fillna(3)
    out["interpretability_penalty"] = out["interpretability"].map(
        interpretability_order
    ).fillna(3)

    out["architecture_risk_score"] = (
        out["overfit_risk_score"]
        + out["complexity_score"]
        + out["validation_burden_score"]
        + out["interpretability_penalty"]
    )

    return out[
        [
            "architecture_id",
            "name",
            "allowed_as_next_branch",
            "complexity",
            "overfit_risk",
            "interpretability",
            "validation_burden",
            "architecture_risk_score",
            "recommended_role",
        ]
    ].sort_values(["allowed_as_next_branch", "architecture_risk_score"], ascending=[False, True])


def build_phase11a_recommendation(phase_config: dict[str, Any]) -> pd.DataFrame:
    recommendation = phase_config.get("recommended_next_step", {})

    return pd.DataFrame(
        [
            {
                "recommendation_id": str(recommendation.get("recommendation_id", "")),
                "phase": str(recommendation.get("phase", "")),
                "title": str(recommendation.get("title", "")),
                "recommendation": str(recommendation.get("recommendation", "")),
                "allowed_scope": _join_list(recommendation.get("allowed_scope")),
                "forbidden_scope": _join_list(recommendation.get("forbidden_scope")),
                "spec_only": "spec" in str(recommendation.get("title", "")).lower()
                or "spec" in str(recommendation.get("recommendation", "")).lower(),
                "strategy_test_allowed": any(
                    "strategy test" in str(item).lower()
                    and not str(item).lower().startswith("no")
                    for item in _as_list(recommendation.get("allowed_scope"))
                ),
            }
        ]
    )


def build_phase11a_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "boundary": "No new indicator rule",
            "value": bool(phase_config.get("allow_new_indicator_rule", True)),
            "passed": not bool(phase_config.get("allow_new_indicator_rule", True)),
        },
        {
            "boundary": "No macro rule retry",
            "value": bool(phase_config.get("allow_macro_rule_retry", True)),
            "passed": not bool(phase_config.get("allow_macro_rule_retry", True)),
        },
        {
            "boundary": "No sentiment ingestion",
            "value": bool(phase_config.get("allow_sentiment_ingestion", True)),
            "passed": not bool(phase_config.get("allow_sentiment_ingestion", True)),
        },
        {
            "boundary": "No fundamental ingestion",
            "value": bool(phase_config.get("allow_fundamental_ingestion", True)),
            "passed": not bool(phase_config.get("allow_fundamental_ingestion", True)),
        },
        {
            "boundary": "No model training",
            "value": bool(phase_config.get("allow_model_training", True)),
            "passed": not bool(phase_config.get("allow_model_training", True)),
        },
        {
            "boundary": "No strategy backtest",
            "value": bool(phase_config.get("allow_strategy_backtest", True)),
            "passed": not bool(phase_config.get("allow_strategy_backtest", True)),
        },
        {
            "boundary": "No candidate promotion",
            "value": bool(phase_config.get("allow_candidate_promotion", True)),
            "passed": not bool(phase_config.get("allow_candidate_promotion", True)),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase11a_summary(
    *,
    phase_config: dict[str, Any],
    prior_branch_findings: pd.DataFrame,
    architecture_candidates: pd.DataFrame,
    recommendation: pd.DataFrame,
    boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    simple_overlay = architecture_candidates[
        architecture_candidates["architecture_id"] == "A1_continue_simple_rule_overlays"
    ]

    simple_overlay_rejected = (
        not simple_overlay.empty
        and not bool(simple_overlay.iloc[0]["allowed_as_next_branch"])
    )

    preferred = architecture_candidates[
        architecture_candidates["recommended_role"]
        == "preferred_next_architecture_spec_candidate"
    ]

    return pd.DataFrame(
        [
            {
                "review_role": str(phase_config.get("review_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "prior_branch_count": int(len(prior_branch_findings)),
                "failed_rule_extension_count": int(
                    prior_branch_findings["rule_extension_failed"].sum()
                )
                if not prior_branch_findings.empty
                else 0,
                "closed_without_promotion_count": int(
                    prior_branch_findings["closed_without_promotion"].sum()
                )
                if not prior_branch_findings.empty
                else 0,
                "architecture_candidate_count": int(len(architecture_candidates)),
                "simple_overlay_rejected_as_next": bool(simple_overlay_rejected),
                "preferred_architecture_count": int(len(preferred)),
                "preferred_architecture_id": str(preferred.iloc[0]["architecture_id"])
                if not preferred.empty
                else "",
                "recommended_next_phase": str(recommendation.iloc[0]["phase"])
                if not recommendation.empty
                else "",
                "recommended_next_step_is_spec_only": bool(
                    recommendation.iloc[0]["spec_only"]
                )
                if not recommendation.empty
                else False,
                "strategy_test_allowed_next": bool(
                    recommendation.iloc[0]["strategy_test_allowed"]
                )
                if not recommendation.empty
                else True,
                "boundary_checks_passed": bool(boundary_check["passed"].all())
                if not boundary_check.empty
                else False,
                "strategy_promotion": False,
                "candidate_promotion": False,
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


def build_phase11a_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [_gate_row("Phase 11A summary exists", False, "No summary was created.")]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get("required_review_role", "Architecture review for richer information layers only")
    )

    rows = [
        _gate_row(
            "Prior rule-extension failures are documented",
            (not gates.get("require_prior_failures_documented", True))
            or int(row["failed_rule_extension_count"]) >= 2,
            f"failed_rule_extension_count={int(row['failed_rule_extension_count'])}",
        ),
        _gate_row(
            "Architecture candidates are documented",
            (not gates.get("require_architecture_candidates", True))
            or int(row["architecture_candidate_count"])
            >= int(gates.get("min_architecture_candidates", 5)),
            f"architecture_candidate_count={int(row['architecture_candidate_count'])}",
        ),
        _gate_row(
            "Simple overlay continuation is rejected as immediate next step",
            (not gates.get("require_simple_overlay_rejected_as_immediate_next", True))
            or bool(row["simple_overlay_rejected_as_next"]),
            f"simple_overlay_rejected_as_next={bool(row['simple_overlay_rejected_as_next'])}",
        ),
        _gate_row(
            "Preferred architecture is identified",
            (not gates.get("require_preferred_architecture_identified", True))
            or int(row["preferred_architecture_count"]) >= 1,
            f"preferred_architecture_id={row['preferred_architecture_id']}",
        ),
        _gate_row(
            "Next step is spec-only",
            (not gates.get("require_next_step_spec_only", True))
            or (
                bool(row["recommended_next_step_is_spec_only"])
                and not bool(row["strategy_test_allowed_next"])
            ),
            (
                "recommended_next_step_is_spec_only="
                f"{bool(row['recommended_next_step_is_spec_only'])}; "
                f"strategy_test_allowed_next={bool(row['strategy_test_allowed_next'])}"
            ),
        ),
        _gate_row(
            "No new indicator rule is allowed",
            (not gates.get("require_no_new_indicator_rule", True))
            or not bool(phase_config.get("allow_new_indicator_rule", True)),
            f"allow_new_indicator_rule={phase_config.get('allow_new_indicator_rule')}",
        ),
        _gate_row(
            "No macro rule retry is allowed",
            (not gates.get("require_no_macro_rule_retry", True))
            or not bool(phase_config.get("allow_macro_rule_retry", True)),
            f"allow_macro_rule_retry={phase_config.get('allow_macro_rule_retry')}",
        ),
        _gate_row(
            "No sentiment ingestion is allowed",
            (not gates.get("require_no_sentiment_ingestion", True))
            or not bool(phase_config.get("allow_sentiment_ingestion", True)),
            f"allow_sentiment_ingestion={phase_config.get('allow_sentiment_ingestion')}",
        ),
        _gate_row(
            "No fundamental ingestion is allowed",
            (not gates.get("require_no_fundamental_ingestion", True))
            or not bool(phase_config.get("allow_fundamental_ingestion", True)),
            (
                "allow_fundamental_ingestion="
                f"{phase_config.get('allow_fundamental_ingestion')}"
            ),
        ),
        _gate_row(
            "No model training is allowed",
            (not gates.get("require_no_model_training", True))
            or not bool(phase_config.get("allow_model_training", True)),
            f"allow_model_training={phase_config.get('allow_model_training')}",
        ),
        _gate_row(
            "No strategy backtest is allowed",
            (not gates.get("require_no_strategy_backtest", True))
            or not bool(phase_config.get("allow_strategy_backtest", True)),
            f"allow_strategy_backtest={phase_config.get('allow_strategy_backtest')}",
        ),
        _gate_row(
            "No candidate promotion is allowed",
            (not gates.get("require_no_candidate_promotion", True))
            or not bool(phase_config.get("allow_candidate_promotion", True)),
            f"allow_candidate_promotion={phase_config.get('allow_candidate_promotion')}",
        ),
        _gate_row(
            "Review role is correct",
            str(row["review_role"]) == required_role,
            f"review_role={row['review_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase11a_conclusion(gate_report: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    if all_passed:
        preferred = summary.iloc[0]["preferred_architecture_id"]
        verdict = "Completed — architecture review passed"
        interpretation = (
            "Phase 11A documented that simple rule overlays are not the preferred "
            "immediate next architecture after failed technical and macro rule "
            f"extensions. Preferred next step: {preferred}, as a spec-only phase."
        )
    else:
        verdict = "Failed architecture review discipline"
        interpretation = (
            "Phase 11A found that the architecture review is incomplete or violates "
            "scope boundaries. Do not proceed to richer-information modelling."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 11A",
                "diagnostic": "Architecture review for richer information layers",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase11a_markdown(
    *,
    prior_branch_findings: pd.DataFrame,
    architecture_candidates: pd.DataFrame,
    risk_matrix: pd.DataFrame,
    recommendation: pd.DataFrame,
    boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 11A — Architecture Review for Richer Information Layers",
        "",
        "## Purpose",
        "",
        (
            "This phase reviews future architecture options after technical and macro "
            "diagnostics both failed to become validated pre-registered rule overlays."
        ),
        "",
        (
            "It does not create indicators, macro retries, sentiment feeds, fundamental "
            "features, model training, strategy backtests, or candidate promotion."
        ),
        "",
        "## Prior Branch Findings",
        "",
        prior_branch_findings.to_markdown(index=False),
        "",
        "## Architecture Candidates",
        "",
        architecture_candidates.to_markdown(index=False),
        "",
        "## Architecture Risk Matrix",
        "",
        risk_matrix.to_markdown(index=False),
        "",
        "## Recommended Next Step",
        "",
        recommendation.to_markdown(index=False),
        "",
        "## Boundary Check",
        "",
        boundary_check.to_markdown(index=False),
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
        "- This is an architecture review only.",
        "- It does not test a new strategy.",
        "- It does not ingest sentiment or fundamentals.",
        "- It does not train ML models.",
        "- It does not promote a candidate.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase11a_richer_information_architecture_review(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "prior_branch_findings": empty,
            "architecture_candidates": empty,
            "risk_matrix": empty,
            "recommendation": empty,
            "boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    prior_branch_findings = build_phase11a_prior_branch_findings(phase_config)
    architecture_candidates = build_phase11a_architecture_candidates(phase_config)
    risk_matrix = build_phase11a_architecture_risk_matrix(architecture_candidates)
    recommendation = build_phase11a_recommendation(phase_config)
    boundary_check = build_phase11a_boundary_check(phase_config)
    summary = build_phase11a_summary(
        phase_config=phase_config,
        prior_branch_findings=prior_branch_findings,
        architecture_candidates=architecture_candidates,
        recommendation=recommendation,
        boundary_check=boundary_check,
    )
    gate_report = build_phase11a_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11a_conclusion(gate_report, summary)

    prior_branch_findings.to_csv(
        reports_path / "phase11a_architecture_prior_branch_findings.csv",
        index=False,
    )
    architecture_candidates.to_csv(
        reports_path / "phase11a_architecture_candidates.csv",
        index=False,
    )
    risk_matrix.to_csv(
        reports_path / "phase11a_architecture_risk_matrix.csv",
        index=False,
    )
    recommendation.to_csv(
        reports_path / "phase11a_architecture_recommendation.csv",
        index=False,
    )
    boundary_check.to_csv(
        reports_path / "phase11a_architecture_boundary_check.csv",
        index=False,
    )
    summary.to_csv(reports_path / "phase11a_architecture_summary.csv", index=False)
    gate_report.to_csv(
        reports_path / "phase11a_architecture_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase11a_architecture_conclusion.csv",
        index=False,
    )

    write_phase11a_markdown(
        prior_branch_findings=prior_branch_findings,
        architecture_candidates=architecture_candidates,
        risk_matrix=risk_matrix,
        recommendation=recommendation,
        boundary_check=boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase11a_richer_information_architecture_review.md",
    )

    print("Wrote Phase 11A richer-information architecture review reports.")

    return {
        "prior_branch_findings": prior_branch_findings,
        "architecture_candidates": architecture_candidates,
        "risk_matrix": risk_matrix,
        "recommendation": recommendation,
        "boundary_check": boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }