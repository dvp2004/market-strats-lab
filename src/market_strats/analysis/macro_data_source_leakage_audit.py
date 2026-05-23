from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE10B_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Data-source and leakage feasibility audit only",
    "proposed_next_phase": "Phase 10C",
    "recommended_family": "macro_rates_inflation",
    "allow_data_download": False,
    "allow_feature_engineering": False,
    "allow_signal_creation": False,
    "allow_model_training": False,
    "allow_strategy_test": False,
    "allow_strategy_promotion": False,
    "phase10c_boundary": {
        "allowed_next_step": "data-source reliability and point-in-time alignment audit only",
        "forbidden_next_step": "macro signal backtest or allocation rule test",
        "phase10c_may_download_data": True,
        "phase10c_may_create_strategy_signal": False,
        "phase10c_may_test_strategy": False,
        "phase10c_may_promote_candidate": False,
    },
    "source_candidates": [],
    "gates": {
        "min_source_candidates": 5,
        "require_recommended_family_macro_rates_inflation": True,
        "require_no_data_download": True,
        "require_no_feature_engineering": True,
        "require_no_signal_creation": True,
        "require_no_model_training": True,
        "require_no_strategy_test": True,
        "require_no_strategy_promotion": True,
        "require_each_source_has_release_policy": True,
        "require_each_source_has_revision_policy": True,
        "require_each_source_has_leakage_controls": True,
        "require_at_least_one_vintage_capable_source": True,
        "require_at_least_one_rates_source": True,
        "require_at_least_one_inflation_source": True,
        "require_no_source_allowed_for_strategy_test_now": True,
        "require_phase10c_boundary_is_data_audit_only": True,
        "required_audit_role": "Data-source and leakage feasibility audit only",
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
    user_config = config.get("phase10b_macro_data_source_leakage_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE10B_CONFIG, user_config)


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


def _sources(phase_config: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in _as_list(phase_config.get("source_candidates"))]


def build_phase10b_source_catalog(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for source in _sources(phase_config):
        active_disqualifiers = _as_list(source.get("active_disqualifiers"))

        rows.append(
            {
                "source_id": str(source.get("source_id", "")),
                "name": str(source.get("name", "")),
                "provider_type": str(source.get("provider_type", "")),
                "macro_role": str(source.get("macro_role", "")),
                "source_family": str(source.get("source_family", "")),
                "frequency": str(source.get("frequency", "")),
                "expected_history_coverage": str(
                    source.get("expected_history_coverage", "")
                ),
                "example_series": _join_list(source.get("example_series")),
                "has_release_calendar_or_timestamp": bool(
                    source.get("has_release_calendar_or_timestamp", False)
                ),
                "has_vintage_or_revision_support": bool(
                    source.get("has_vintage_or_revision_support", False)
                ),
                "supports_point_in_time_alignment": bool(
                    source.get("supports_point_in_time_alignment", False)
                ),
                "allowed_for_phase10c_source_audit": bool(
                    source.get("allowed_for_phase10c_source_audit", False)
                ),
                "allowed_for_strategy_test_now": bool(
                    source.get("allowed_for_strategy_test_now", False)
                ),
                "active_disqualifier_count": len(active_disqualifiers),
                "active_disqualifiers": _join_list(active_disqualifiers),
            }
        )

    return pd.DataFrame(rows)


def build_phase10b_timing_revision_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for source in _sources(phase_config):
        release_policy = str(source.get("release_date_policy", "")).strip()
        revision_policy = str(source.get("revision_policy", "")).strip()

        rows.append(
            {
                "source_id": str(source.get("source_id", "")),
                "release_date_policy": release_policy,
                "revision_policy": revision_policy,
                "has_release_policy": bool(release_policy),
                "has_revision_policy": bool(revision_policy),
                "has_release_calendar_or_timestamp": bool(
                    source.get("has_release_calendar_or_timestamp", False)
                ),
                "has_vintage_or_revision_support": bool(
                    source.get("has_vintage_or_revision_support", False)
                ),
                "supports_point_in_time_alignment": bool(
                    source.get("supports_point_in_time_alignment", False)
                ),
            }
        )

    frame = pd.DataFrame(rows)

    if frame.empty:
        return frame

    frame["timing_revision_ready_for_audit"] = (
        frame["has_release_policy"]
        & frame["has_revision_policy"]
        & (
            frame["supports_point_in_time_alignment"]
            | frame["has_vintage_or_revision_support"]
        )
    )

    return frame


def build_phase10b_leakage_control_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for source in _sources(phase_config):
        source_id = str(source.get("source_id", ""))
        known_risks = _as_list(source.get("known_leakage_risks"))
        required_controls = _as_list(source.get("required_controls"))

        rows.append(
            {
                "source_id": source_id,
                "known_leakage_risk_count": len(known_risks),
                "known_leakage_risks": _join_list(known_risks),
                "required_control_count": len(required_controls),
                "required_controls": _join_list(required_controls),
                "has_leakage_risks_documented": len(known_risks) > 0,
                "has_required_controls_documented": len(required_controls) > 0,
            }
        )

    frame = pd.DataFrame(rows)

    if frame.empty:
        return frame

    frame["leakage_controls_ready_for_audit"] = (
        frame["has_leakage_risks_documented"]
        & frame["has_required_controls_documented"]
    )

    return frame


def build_phase10b_source_recommendation(
    source_catalog: pd.DataFrame,
    timing_revision_check: pd.DataFrame,
    leakage_control_check: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if source_catalog.empty:
        return pd.DataFrame()

    merged = source_catalog.merge(
        timing_revision_check[
            [
                "source_id",
                "timing_revision_ready_for_audit",
            ]
        ],
        on="source_id",
        how="left",
    ).merge(
        leakage_control_check[
            ["source_id", "leakage_controls_ready_for_audit"]
        ],
        on="source_id",
        how="left",
    )

    merged["source_audit_candidate"] = (
        merged["allowed_for_phase10c_source_audit"].astype(bool)
        & merged["timing_revision_ready_for_audit"].fillna(False).astype(bool)
        & merged["leakage_controls_ready_for_audit"].fillna(False).astype(bool)
    )
    merged["strategy_test_blocked"] = ~merged["allowed_for_strategy_test_now"].astype(
        bool
    )

    recommended_sources = merged[
        merged["source_audit_candidate"] & merged["strategy_test_blocked"]
    ].copy()

    if recommended_sources.empty:
        recommendation = (
            "Do not open Phase 10C; no macro/rates/inflation source passed "
            "the feasibility audit."
        )
    else:
        recommendation = (
            "Open Phase 10C as a data-source reliability and point-in-time "
            "alignment audit only. Do not create macro signals or test strategies."
        )

    return pd.DataFrame(
        [
            {
                "recommended_family": str(phase_config.get("recommended_family", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "recommended_source_count_for_phase10c_audit": int(
                    len(recommended_sources)
                ),
                "recommended_sources_for_phase10c_audit": "; ".join(
                    recommended_sources["source_id"].astype(str).tolist()
                ),
                "vintage_capable_source_count": int(
                    merged["has_vintage_or_revision_support"].fillna(False).sum()
                ),
                "any_source_allowed_for_strategy_test_now": bool(
                    merged["allowed_for_strategy_test_now"].astype(bool).any()
                ),
                "phase10c_allowed": bool(len(recommended_sources) > 0),
                "recommendation": recommendation,
            }
        ]
    )


def build_phase10b_phase10c_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase10c_boundary", {})

    rows = [
        {
            "boundary_item": "phase10c_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "audit" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase10c_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
            or "backtest" in str(boundary.get("forbidden_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase10c_may_download_data",
            "value": bool(boundary.get("phase10c_may_download_data", False)),
            "passed": bool(boundary.get("phase10c_may_download_data", False)),
        },
        {
            "boundary_item": "phase10c_may_create_strategy_signal",
            "value": bool(boundary.get("phase10c_may_create_strategy_signal", True)),
            "passed": not bool(boundary.get("phase10c_may_create_strategy_signal", True)),
        },
        {
            "boundary_item": "phase10c_may_test_strategy",
            "value": bool(boundary.get("phase10c_may_test_strategy", True)),
            "passed": not bool(boundary.get("phase10c_may_test_strategy", True)),
        },
        {
            "boundary_item": "phase10c_may_promote_candidate",
            "value": bool(boundary.get("phase10c_may_promote_candidate", True)),
            "passed": not bool(boundary.get("phase10c_may_promote_candidate", True)),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase10b_summary(
    phase_config: dict[str, Any],
    source_catalog: pd.DataFrame,
    timing_revision_check: pd.DataFrame,
    leakage_control_check: pd.DataFrame,
    recommendation: pd.DataFrame,
    phase10c_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    recommended = recommendation.iloc[0] if not recommendation.empty else {}

    source_roles = (
        source_catalog["macro_role"].astype(str).tolist()
        if not source_catalog.empty and "macro_role" in source_catalog.columns
        else []
    )

    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "recommended_family": str(phase_config.get("recommended_family", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_candidate_count": int(len(source_catalog)),
                "release_policy_ready_count": int(
                    timing_revision_check["has_release_policy"].sum()
                )
                if not timing_revision_check.empty
                else 0,
                "revision_policy_ready_count": int(
                    timing_revision_check["has_revision_policy"].sum()
                )
                if not timing_revision_check.empty
                else 0,
                "leakage_controls_ready_count": int(
                    leakage_control_check["leakage_controls_ready_for_audit"].sum()
                )
                if not leakage_control_check.empty
                else 0,
                "vintage_capable_source_count": int(
                    recommended.get("vintage_capable_source_count", 0)
                ),
                "recommended_source_count_for_phase10c_audit": int(
                    recommended.get("recommended_source_count_for_phase10c_audit", 0)
                ),
                "has_rates_source": any("rates" in role for role in source_roles),
                "has_inflation_source": any("inflation" in role for role in source_roles),
                "phase10c_allowed": _bool_value(
                    recommended.get("phase10c_allowed", False)
                ),
                "phase10c_boundary_passed": bool(
                    phase10c_boundary_check["passed"].all()
                )
                if not phase10c_boundary_check.empty
                else False,
                "allow_data_download": bool(
                    phase_config.get("allow_data_download", False)
                ),
                "allow_feature_engineering": bool(
                    phase_config.get("allow_feature_engineering", False)
                ),
                "allow_signal_creation": bool(
                    phase_config.get("allow_signal_creation", False)
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


def build_phase10b_gate_report(
    phase_config: dict[str, Any],
    source_catalog: pd.DataFrame,
    timing_revision_check: pd.DataFrame,
    leakage_control_check: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 10B summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]

    min_sources = int(gates.get("min_source_candidates", 5))
    required_role = str(
        gates.get("required_audit_role", "Data-source and leakage feasibility audit only")
    )

    all_sources_have_release_policy = (
        bool(timing_revision_check["has_release_policy"].all())
        if not timing_revision_check.empty
        else False
    )
    all_sources_have_revision_policy = (
        bool(timing_revision_check["has_revision_policy"].all())
        if not timing_revision_check.empty
        else False
    )
    all_sources_have_leakage_controls = (
        bool(leakage_control_check["leakage_controls_ready_for_audit"].all())
        if not leakage_control_check.empty
        else False
    )
    no_source_allowed_for_strategy_test_now = (
        not bool(source_catalog["allowed_for_strategy_test_now"].astype(bool).any())
        if not source_catalog.empty
        else False
    )

    rows = [
        _gate_row(
            "Source candidate count is sufficient",
            int(row["source_candidate_count"]) >= min_sources,
            f"{int(row['source_candidate_count'])} sources; required >= {min_sources}",
        ),
        _gate_row(
            "Recommended family is macro/rates/inflation",
            (
                not gates.get(
                    "require_recommended_family_macro_rates_inflation",
                    True,
                )
            )
            or str(row["recommended_family"]) == "macro_rates_inflation",
            f"recommended_family={row['recommended_family']}",
        ),
        _gate_row(
            "No data download is allowed in Phase 10B",
            (not gates.get("require_no_data_download", True))
            or not bool(row["allow_data_download"]),
            f"allow_data_download={bool(row['allow_data_download'])}",
        ),
        _gate_row(
            "No feature engineering is allowed in Phase 10B",
            (not gates.get("require_no_feature_engineering", True))
            or not bool(row["allow_feature_engineering"]),
            f"allow_feature_engineering={bool(row['allow_feature_engineering'])}",
        ),
        _gate_row(
            "No signal creation is allowed in Phase 10B",
            (not gates.get("require_no_signal_creation", True))
            or not bool(row["allow_signal_creation"]),
            f"allow_signal_creation={bool(row['allow_signal_creation'])}",
        ),
        _gate_row(
            "No model training is allowed in Phase 10B",
            (not gates.get("require_no_model_training", True))
            or not bool(row["allow_model_training"]),
            f"allow_model_training={bool(row['allow_model_training'])}",
        ),
        _gate_row(
            "No strategy test is allowed in Phase 10B",
            (not gates.get("require_no_strategy_test", True))
            or not bool(row["allow_strategy_test"]),
            f"allow_strategy_test={bool(row['allow_strategy_test'])}",
        ),
        _gate_row(
            "No strategy promotion is allowed in Phase 10B",
            (not gates.get("require_no_strategy_promotion", True))
            or not bool(row["allow_strategy_promotion"]),
            f"allow_strategy_promotion={bool(row['allow_strategy_promotion'])}",
        ),
        _gate_row(
            "Each source has a release-date policy",
            (not gates.get("require_each_source_has_release_policy", True))
            or all_sources_have_release_policy,
            f"release_policy_ready_count={int(row['release_policy_ready_count'])}",
        ),
        _gate_row(
            "Each source has a revision policy",
            (not gates.get("require_each_source_has_revision_policy", True))
            or all_sources_have_revision_policy,
            f"revision_policy_ready_count={int(row['revision_policy_ready_count'])}",
        ),
        _gate_row(
            "Each source has leakage controls",
            (not gates.get("require_each_source_has_leakage_controls", True))
            or all_sources_have_leakage_controls,
            f"leakage_controls_ready_count={int(row['leakage_controls_ready_count'])}",
        ),
        _gate_row(
            "At least one source has vintage/revision support",
            (not gates.get("require_at_least_one_vintage_capable_source", True))
            or int(row["vintage_capable_source_count"]) > 0,
            f"vintage_capable_source_count={int(row['vintage_capable_source_count'])}",
        ),
        _gate_row(
            "At least one rates source is present",
            (not gates.get("require_at_least_one_rates_source", True))
            or bool(row["has_rates_source"]),
            f"has_rates_source={bool(row['has_rates_source'])}",
        ),
        _gate_row(
            "At least one inflation source is present",
            (not gates.get("require_at_least_one_inflation_source", True))
            or bool(row["has_inflation_source"]),
            f"has_inflation_source={bool(row['has_inflation_source'])}",
        ),
        _gate_row(
            "No source is allowed for strategy testing now",
            (not gates.get("require_no_source_allowed_for_strategy_test_now", True))
            or no_source_allowed_for_strategy_test_now,
            f"no_source_allowed_for_strategy_test_now={no_source_allowed_for_strategy_test_now}",
        ),
        _gate_row(
            "Phase 10C boundary is data-audit only",
            (not gates.get("require_phase10c_boundary_is_data_audit_only", True))
            or bool(row["phase10c_boundary_passed"]),
            f"phase10c_boundary_passed={bool(row['phase10c_boundary_passed'])}",
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


def build_phase10b_conclusion(
    gate_report: pd.DataFrame,
    recommendation: pd.DataFrame,
) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if recommendation.empty:
        recommended_sources = ""
        next_phase = ""
        phase10c_allowed = False
    else:
        row = recommendation.iloc[0]
        recommended_sources = str(row.get("recommended_sources_for_phase10c_audit", ""))
        next_phase = str(row.get("proposed_next_phase", ""))
        phase10c_allowed = _bool_value(row.get("phase10c_allowed", False))

    if all_passed and phase10c_allowed:
        verdict = "Completed — macro data-source leakage audit passed"
        interpretation = (
            "Phase 10B found that macro/rates/inflation data-source candidates "
            "are feasible enough to audit in Phase 10C. Phase 10C is allowed only "
            "as a data-source reliability and point-in-time alignment audit, not "
            "as a signal or strategy test."
        )
    else:
        verdict = "Failed macro data-source leakage feasibility"
        interpretation = (
            "Phase 10B did not satisfy every data-source/leakage gate. Do not "
            "open Phase 10C until the feasibility issues are corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 10B",
                "diagnostic": "Macro / rates / inflation data-source leakage feasibility audit",
                "verdict": verdict,
                "recommended_sources_for_phase10c_audit": recommended_sources,
                "next_phase": next_phase,
                "phase10c_allowed": phase10c_allowed,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase10b_markdown(
    *,
    source_catalog: pd.DataFrame,
    timing_revision_check: pd.DataFrame,
    leakage_control_check: pd.DataFrame,
    recommendation: pd.DataFrame,
    phase10c_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 10B — Macro / Rates / Inflation Data-Source & Leakage Feasibility Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit checks whether macro/rates/inflation data sources are "
            "feasible enough for a later point-in-time data-source audit."
        ),
        "",
        (
            "It does not download data, engineer features, create signals, train "
            "models, test strategies, or promote candidates."
        ),
        "",
        "## Source Catalog",
        "",
        source_catalog.to_markdown(index=False),
        "",
        "## Timing / Revision Check",
        "",
        timing_revision_check.to_markdown(index=False),
        "",
        "## Leakage Control Check",
        "",
        leakage_control_check.to_markdown(index=False),
        "",
        "## Phase 10C Boundary Check",
        "",
        phase10c_boundary_check.to_markdown(index=False),
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
        "- This is a feasibility audit only.",
        "- It does not prove macro data improves the strategy.",
        "- It does not fetch or validate actual source files.",
        "- Phase 10C must remain a data-source and point-in-time alignment audit.",
        "- No macro signal or strategy test is allowed from this phase alone.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase10b_macro_data_source_leakage_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "source_catalog": empty,
            "timing_revision_check": empty,
            "leakage_control_check": empty,
            "recommendation": empty,
            "phase10c_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_catalog = build_phase10b_source_catalog(phase_config)
    timing_revision_check = build_phase10b_timing_revision_check(phase_config)
    leakage_control_check = build_phase10b_leakage_control_check(phase_config)
    recommendation = build_phase10b_source_recommendation(
        source_catalog,
        timing_revision_check,
        leakage_control_check,
        phase_config,
    )
    phase10c_boundary_check = build_phase10b_phase10c_boundary_check(phase_config)
    summary = build_phase10b_summary(
        phase_config,
        source_catalog,
        timing_revision_check,
        leakage_control_check,
        recommendation,
        phase10c_boundary_check,
    )
    gate_report = build_phase10b_gate_report(
        phase_config,
        source_catalog,
        timing_revision_check,
        leakage_control_check,
        summary,
    )
    conclusion = build_phase10b_conclusion(gate_report, recommendation)

    source_catalog.to_csv(
        reports_path / "phase10b_macro_source_catalog.csv",
        index=False,
    )
    timing_revision_check.to_csv(
        reports_path / "phase10b_macro_timing_revision_check.csv",
        index=False,
    )
    leakage_control_check.to_csv(
        reports_path / "phase10b_macro_leakage_control_check.csv",
        index=False,
    )
    recommendation.to_csv(
        reports_path / "phase10b_macro_source_recommendation.csv",
        index=False,
    )
    phase10c_boundary_check.to_csv(
        reports_path / "phase10b_macro_phase10c_boundary_check.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase10b_macro_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase10b_macro_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase10b_macro_conclusion.csv",
        index=False,
    )

    write_phase10b_markdown(
        source_catalog=source_catalog,
        timing_revision_check=timing_revision_check,
        leakage_control_check=leakage_control_check,
        recommendation=recommendation,
        phase10c_boundary_check=phase10c_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase10b_macro_data_source_leakage_audit.md",
    )

    print("Wrote Phase 10B macro data-source leakage audit reports.")

    return {
        "source_catalog": source_catalog,
        "timing_revision_check": timing_revision_check,
        "leakage_control_check": leakage_control_check,
        "recommendation": recommendation,
        "phase10c_boundary_check": phase10c_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }