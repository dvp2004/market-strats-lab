from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE13C_CONFIG: dict[str, Any] = {
    "enabled": False,
    "spec_role": (
        "Multi-factor feature-source inventory and leakage-feasibility spec only"
    ),
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13B",
    "proposed_next_phase": "Phase 13D",
    "allow_feature_ingestion": False,
    "allow_feature_calculation": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "feature_source_inventory": [],
    "feature_contract_requirements": [],
    "leakage_control_policy": [],
    "blocked_family_policy": {},
    "phase13d_boundary": {},
    "gates": {
        "require_phase13b_passed": True,
        "require_feature_source_inventory": True,
        "min_feature_families": 5,
        "require_technical_macro_fundamental_sentiment": True,
        "require_feature_contract_requirements": True,
        "min_contract_requirements": 8,
        "require_leakage_control_policy": True,
        "min_leakage_controls": 6,
        "require_blocked_family_policy": True,
        "require_fundamental_blocked_now": True,
        "require_sentiment_blocked_now": True,
        "require_phase13d_boundary_readiness_only": True,
        "require_no_feature_ingestion": True,
        "require_no_feature_calculation": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_spec_role": (
            "Multi-factor feature-source inventory and leakage-feasibility spec only"
        ),
    },
}


DEFAULT_PHASE13D_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Feature contract and data availability readiness audit only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13C",
    "proposed_next_phase": "Phase 13E",
    "allow_feature_ingestion": False,
    "allow_feature_calculation": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "phase13c_reports": {},
    "readiness_claims": {},
    "phase13e_boundary": {},
    "gates": {
        "require_phase13c_reports_present": True,
        "require_phase13c_conclusion_passed": True,
        "require_phase13c_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_readiness_claims_locked": True,
        "require_contract_coverage": True,
        "require_blocked_families_respected": True,
        "require_phase13e_boundary_schema_only": True,
        "require_no_feature_ingestion": True,
        "require_no_feature_calculation": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_audit_role": (
            "Feature contract and data availability readiness audit only"
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


def _get_phase13c_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13C_CONFIG,
        config.get("phase13c_multifactor_feature_source_inventory_spec", {}),
    )


def _get_phase13d_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13D_CONFIG,
        config.get("phase13d_feature_contract_readiness_audit", {}),
    )


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


def _join_list(value: Any) -> str:
    return "; ".join(str(item) for item in _as_list(value))


def _read_csv_if_exists(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)

    if not csv_path.exists():
        return pd.DataFrame()

    return pd.read_csv(csv_path)


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase13c_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("source_reports", {}).items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "report_key": str(report_key),
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": int(len(frame)),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13c_phase13b_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13b_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13b_gate_report", ""))

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_report_passed = (
        not gate_report.empty
        and "passed" in gate_report.columns
        and bool(gate_report["passed"].map(_bool_value).all())
    )

    rows = [
        {
            "check": "Phase 13B conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 13B gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13c_feature_source_inventory(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("feature_source_inventory")):
        rows.append(
            {
                "family_id": str(item.get("family_id", "")),
                "family_status": str(item.get("family_status", "")),
                "candidate_sources": _join_list(item.get("candidate_sources")),
                "feature_examples": _join_list(item.get("feature_examples")),
                "timing_frequency": str(item.get("timing_frequency", "")),
                "point_in_time_requirement": str(
                    item.get("point_in_time_requirement", "")
                ),
                "revision_risk": str(item.get("revision_risk", "")),
                "leakage_risk": str(item.get("leakage_risk", "")),
                "immediate_decision": str(item.get("immediate_decision", "")),
                "blocked_now": _bool_value(item.get("blocked_now", True)),
            }
        )

    return pd.DataFrame(rows)


def build_phase13c_feature_contract_requirements(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("feature_contract_requirements")):
        rows.append(
            {
                "requirement_id": str(item.get("requirement_id", "")),
                "requirement": str(item.get("requirement", "")),
                "required": _bool_value(item.get("required", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase13c_leakage_control_policy(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in _as_list(phase_config.get("leakage_control_policy")):
        rows.append(
            {
                "control_id": str(item.get("control_id", "")),
                "control": str(item.get("control", "")),
                "required": _bool_value(item.get("required", False)),
            }
        )

    return pd.DataFrame(rows)


def build_phase13c_blocked_family_policy(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    policy = phase_config.get("blocked_family_policy", {})

    return pd.DataFrame(
        [
            {
                "fundamental_blocked_until": str(
                    policy.get("fundamental_blocked_until", "")
                ),
                "sentiment_blocked_until": str(
                    policy.get("sentiment_blocked_until", "")
                ),
                "dissertation_direct_alpha_blocked_until": str(
                    policy.get("dissertation_direct_alpha_blocked_until", "")
                ),
                "blocked_families_may_appear_in_roadmap": _bool_value(
                    policy.get("blocked_families_may_appear_in_roadmap", False)
                ),
                "blocked_families_may_be_ingested_now": _bool_value(
                    policy.get("blocked_families_may_be_ingested_now", True)
                ),
                "blocked_families_may_be_used_in_model_now": _bool_value(
                    policy.get("blocked_families_may_be_used_in_model_now", True)
                ),
            }
        ]
    )


def build_phase13c_phase13d_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13d_boundary", {})

    checks = [
        (
            "phase13d_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "readiness audit" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13d_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            (
                "feature ingestion"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy backtest"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "model training"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        ),
        (
            "phase13d_may_audit_inventory",
            _bool_value(boundary.get("phase13d_may_audit_inventory", False)),
            _bool_value(boundary.get("phase13d_may_audit_inventory", False)),
        ),
        (
            "phase13d_may_audit_contract_requirements",
            _bool_value(
                boundary.get("phase13d_may_audit_contract_requirements", False)
            ),
            _bool_value(
                boundary.get("phase13d_may_audit_contract_requirements", False)
            ),
        ),
        (
            "phase13d_may_ingest_features",
            _bool_value(boundary.get("phase13d_may_ingest_features", True)),
            not _bool_value(boundary.get("phase13d_may_ingest_features", True)),
        ),
        (
            "phase13d_may_calculate_features",
            _bool_value(boundary.get("phase13d_may_calculate_features", True)),
            not _bool_value(boundary.get("phase13d_may_calculate_features", True)),
        ),
        (
            "phase13d_may_train_model",
            _bool_value(boundary.get("phase13d_may_train_model", True)),
            not _bool_value(boundary.get("phase13d_may_train_model", True)),
        ),
        (
            "phase13d_may_create_signal",
            _bool_value(boundary.get("phase13d_may_create_signal", True)),
            not _bool_value(boundary.get("phase13d_may_create_signal", True)),
        ),
        (
            "phase13d_may_run_backtest",
            _bool_value(boundary.get("phase13d_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13d_may_run_backtest", True)),
        ),
        (
            "phase13d_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13d_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13d_may_deploy_paper_trading", True)),
        ),
        (
            "phase13d_may_promote_candidate",
            _bool_value(boundary.get("phase13d_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13d_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [
            {
                "boundary_item": item,
                "value": value,
                "passed": passed,
            }
            for item, value, passed in checks
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No feature ingestion", "allow_feature_ingestion"),
        ("No feature calculation", "allow_feature_calculation"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No model training", "allow_model_training"),
        ("No paper trading deployment", "allow_paper_trading_deployment"),
        ("No candidate promotion", "allow_candidate_promotion"),
        ("No final candidate change", "allow_final_candidate_change"),
    ]

    rows = [
        {
            "scope_item": label,
            "value": _bool_value(phase_config.get(key, True)),
            "passed": not _bool_value(phase_config.get(key, True)),
        }
        for label, key in checks
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13c_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13b_result_check: pd.DataFrame,
    feature_source_inventory: pd.DataFrame,
    feature_contract_requirements: pd.DataFrame,
    leakage_control_policy: pd.DataFrame,
    blocked_family_policy: pd.DataFrame,
    phase13d_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    families = (
        set(feature_source_inventory["family_id"].dropna().astype(str).tolist())
        if not feature_source_inventory.empty
        else set()
    )
    required_families = {"technical", "macro", "fundamental", "sentiment"}

    fundamental_rows = (
        feature_source_inventory[
            feature_source_inventory["family_id"].astype(str) == "fundamental"
        ]
        if not feature_source_inventory.empty
        else pd.DataFrame()
    )
    sentiment_rows = (
        feature_source_inventory[
            feature_source_inventory["family_id"].astype(str) == "sentiment"
        ]
        if not feature_source_inventory.empty
        else pd.DataFrame()
    )

    blocked_policy_clean = (
        not blocked_family_policy.empty
        and _bool_value(
            blocked_family_policy.iloc[0]["blocked_families_may_appear_in_roadmap"]
        )
        and not _bool_value(
            blocked_family_policy.iloc[0]["blocked_families_may_be_ingested_now"]
        )
        and not _bool_value(
            blocked_family_policy.iloc[0]["blocked_families_may_be_used_in_model_now"]
        )
    )

    return pd.DataFrame(
        [
            {
                "spec_role": str(phase_config.get("spec_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase13b_result_passed": bool(phase13b_result_check["passed"].all())
                if not phase13b_result_check.empty
                else False,
                "feature_family_count": int(len(feature_source_inventory)),
                "required_families_present": required_families.issubset(families),
                "contract_requirement_count": int(len(feature_contract_requirements)),
                "contract_requirements_required": bool(
                    feature_contract_requirements["required"].map(_bool_value).all()
                )
                if not feature_contract_requirements.empty
                else False,
                "leakage_control_count": int(len(leakage_control_policy)),
                "leakage_controls_required": bool(
                    leakage_control_policy["required"].map(_bool_value).all()
                )
                if not leakage_control_policy.empty
                else False,
                "fundamental_blocked_now": bool(
                    fundamental_rows["blocked_now"].map(_bool_value).all()
                )
                if not fundamental_rows.empty
                else False,
                "sentiment_blocked_now": bool(
                    sentiment_rows["blocked_now"].map(_bool_value).all()
                )
                if not sentiment_rows.empty
                else False,
                "blocked_family_policy_clean": blocked_policy_clean,
                "phase13d_boundary_passed": bool(
                    phase13d_boundary_check["passed"].all()
                )
                if not phase13d_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "feature_ingestion": False,
                "feature_calculation": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "model_training": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13c_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13C summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_spec_role",
            "Multi-factor feature-source inventory and leakage-feasibility spec only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13B passed",
            (not gates.get("require_phase13b_passed", True))
            or bool(row["phase13b_result_passed"]),
            f"phase13b_result_passed={bool(row['phase13b_result_passed'])}",
        ),
        _gate_row(
            "Feature-source inventory is complete enough",
            (not gates.get("require_feature_source_inventory", True))
            or int(row["feature_family_count"])
            >= int(gates.get("min_feature_families", 5)),
            f"feature_family_count={int(row['feature_family_count'])}",
        ),
        _gate_row(
            "Technical, macro, fundamental, and sentiment are present",
            (not gates.get("require_technical_macro_fundamental_sentiment", True))
            or bool(row["required_families_present"]),
            f"required_families_present={bool(row['required_families_present'])}",
        ),
        _gate_row(
            "Feature contract requirements are documented",
            (not gates.get("require_feature_contract_requirements", True))
            or (
                int(row["contract_requirement_count"])
                >= int(gates.get("min_contract_requirements", 8))
                and bool(row["contract_requirements_required"])
            ),
            (
                f"contract_requirement_count="
                f"{int(row['contract_requirement_count'])}; "
                f"contract_requirements_required="
                f"{bool(row['contract_requirements_required'])}"
            ),
        ),
        _gate_row(
            "Leakage controls are documented",
            (not gates.get("require_leakage_control_policy", True))
            or (
                int(row["leakage_control_count"])
                >= int(gates.get("min_leakage_controls", 6))
                and bool(row["leakage_controls_required"])
            ),
            (
                f"leakage_control_count={int(row['leakage_control_count'])}; "
                f"leakage_controls_required="
                f"{bool(row['leakage_controls_required'])}"
            ),
        ),
        _gate_row(
            "Fundamental family remains blocked until audit",
            (not gates.get("require_fundamental_blocked_now", True))
            or bool(row["fundamental_blocked_now"]),
            f"fundamental_blocked_now={bool(row['fundamental_blocked_now'])}",
        ),
        _gate_row(
            "Sentiment family remains blocked until audit",
            (not gates.get("require_sentiment_blocked_now", True))
            or bool(row["sentiment_blocked_now"]),
            f"sentiment_blocked_now={bool(row['sentiment_blocked_now'])}",
        ),
        _gate_row(
            "Blocked-family policy is clean",
            (not gates.get("require_blocked_family_policy", True))
            or bool(row["blocked_family_policy_clean"]),
            f"blocked_family_policy_clean={bool(row['blocked_family_policy_clean'])}",
        ),
        _gate_row(
            "Phase 13D boundary is readiness-only",
            (not gates.get("require_phase13d_boundary_readiness_only", True))
            or bool(row["phase13d_boundary_passed"]),
            f"phase13d_boundary_passed={bool(row['phase13d_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks feature/model/signal/backtest/paper-trading/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Spec role is correct",
            str(row["spec_role"]) == required_role,
            f"spec_role={row['spec_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13c_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    verdict = (
        "Completed — feature-source inventory and leakage-feasibility spec passed"
        if all_passed
        else "Failed feature-source inventory and leakage-feasibility spec"
    )
    interpretation = (
        "Phase 13C defined the multi-factor feature-source inventory, contract "
        "requirements, leakage controls, and blocked-family policy. It did not "
        "ingest features, calculate features, create signals, run backtests, train "
        "models, deploy paper trading, promote a candidate, or change the final "
        "candidate."
        if all_passed
        else "Phase 13C found an inventory, leakage, blocked-family, or boundary issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13C",
                "diagnostic": "Multi-factor feature-source inventory spec",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase13c_markdown(
    *,
    source_report_check: pd.DataFrame,
    phase13b_result_check: pd.DataFrame,
    feature_source_inventory: pd.DataFrame,
    feature_contract_requirements: pd.DataFrame,
    leakage_control_policy: pd.DataFrame,
    blocked_family_policy: pd.DataFrame,
    phase13d_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 13C — Multi-Factor Feature-Source Inventory / Leakage Spec",
        "",
        "This phase defines feature-source inventory and leakage controls only. It does "
        "not ingest features, calculate features, create signals, run backtests, train "
        "models, deploy paper trading, promote a candidate, or change the final "
        "candidate.",
        "",
        "## Source Report Check",
        source_report_check.to_markdown(index=False),
        "",
        "## Phase 13B Result Check",
        phase13b_result_check.to_markdown(index=False),
        "",
        "## Feature Source Inventory",
        feature_source_inventory.to_markdown(index=False),
        "",
        "## Feature Contract Requirements",
        feature_contract_requirements.to_markdown(index=False),
        "",
        "## Leakage Control Policy",
        leakage_control_policy.to_markdown(index=False),
        "",
        "## Blocked Family Policy",
        blocked_family_policy.to_markdown(index=False),
        "",
        "## Phase 13D Boundary Check",
        phase13d_boundary_check.to_markdown(index=False),
        "",
        "## Scope Boundary Check",
        scope_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        conclusion.to_markdown(index=False),
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13c_multifactor_feature_source_inventory_spec(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13c_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13c_source_report_check(phase_config)
    phase13b_result_check = build_phase13c_phase13b_result_check(phase_config)
    feature_source_inventory = build_phase13c_feature_source_inventory(phase_config)
    feature_contract_requirements = build_phase13c_feature_contract_requirements(
        phase_config
    )
    leakage_control_policy = build_phase13c_leakage_control_policy(phase_config)
    blocked_family_policy = build_phase13c_blocked_family_policy(phase_config)
    phase13d_boundary_check = build_phase13c_phase13d_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13c_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13b_result_check=phase13b_result_check,
        feature_source_inventory=feature_source_inventory,
        feature_contract_requirements=feature_contract_requirements,
        leakage_control_policy=leakage_control_policy,
        blocked_family_policy=blocked_family_policy,
        phase13d_boundary_check=phase13d_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13c_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13c_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13b_result_check": phase13b_result_check,
        "feature_source_inventory": feature_source_inventory,
        "feature_contract_requirements": feature_contract_requirements,
        "leakage_control_policy": leakage_control_policy,
        "blocked_family_policy": blocked_family_policy,
        "phase13d_boundary_check": phase13d_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13c_inventory_{name}.csv", index=False)

    write_phase13c_markdown(
        source_report_check=source_report_check,
        phase13b_result_check=phase13b_result_check,
        feature_source_inventory=feature_source_inventory,
        feature_contract_requirements=feature_contract_requirements,
        leakage_control_policy=leakage_control_policy,
        blocked_family_policy=blocked_family_policy,
        phase13d_boundary_check=phase13d_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase13c_multifactor_feature_source_inventory_spec.md",
    )

    print("Wrote Phase 13C feature-source inventory spec reports.")
    return outputs


def build_phase13d_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("phase13c_reports", {}).items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "report_key": str(report_key),
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": int(len(frame)),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13d_phase13c_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase13c_reports", {})
    conclusion = _read_csv_if_exists(reports.get("conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("gate_report", ""))

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_report_passed = (
        not gate_report.empty
        and "passed" in gate_report.columns
        and bool(gate_report["passed"].map(_bool_value).all())
    )

    rows = [
        {
            "check": "Phase 13C conclusion passed",
            "passed": conclusion_passed,
            "detail": str(conclusion.iloc[0].get("verdict", ""))
            if not conclusion.empty
            else "missing",
        },
        {
            "check": "Phase 13C gate report passed",
            "passed": gate_report_passed,
            "detail": f"gate_rows={len(gate_report)}",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13d_config_flag_check(
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
                "config_key": str(key),
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": passed,
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase13d_readiness_claims_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    claims = phase_config.get("readiness_claims", {})

    expected_true = [
        "phase13c_inventory_exists",
        "technical_contract_feasible",
        "macro_contract_feasible_with_lagging",
        "fundamental_blocked_until_audit",
        "sentiment_blocked_until_audit",
        "dissertation_methodology_only",
    ]
    expected_false = [
        "feature_ingested",
        "feature_calculated",
        "signal_created",
        "backtest_run",
        "model_trained",
        "paper_trading_deployed",
        "candidate_promoted",
        "final_candidate_changed",
    ]

    rows: list[dict[str, Any]] = []

    for claim in expected_true:
        actual = _bool_value(claims.get(claim, False))
        rows.append(
            {
                "claim": claim,
                "expected": True,
                "actual": actual,
                "passed": actual is True,
            }
        )

    for claim in expected_false:
        actual = _bool_value(claims.get(claim, True))
        rows.append(
            {
                "claim": claim,
                "expected": False,
                "actual": actual,
                "passed": actual is False,
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13d_contract_coverage_check(
    *,
    feature_source_inventory: pd.DataFrame,
    feature_contract_requirements: pd.DataFrame,
    leakage_control_policy: pd.DataFrame,
) -> pd.DataFrame:
    required_families = {"technical", "macro", "fundamental", "sentiment"}

    families = (
        set(feature_source_inventory["family_id"].dropna().astype(str).tolist())
        if not feature_source_inventory.empty
        else set()
    )

    rows = [
        {
            "check": "Required feature families present",
            "passed": required_families.issubset(families),
            "detail": "families=" + "; ".join(sorted(families)),
        },
        {
            "check": "Contract requirements present",
            "passed": len(feature_contract_requirements) >= 8
            and bool(feature_contract_requirements["required"].map(_bool_value).all()),
            "detail": f"contract_rows={len(feature_contract_requirements)}",
        },
        {
            "check": "Leakage controls present",
            "passed": len(leakage_control_policy) >= 6
            and bool(leakage_control_policy["required"].map(_bool_value).all()),
            "detail": f"leakage_rows={len(leakage_control_policy)}",
        },
        {
            "check": "Technical is not blocked",
            "passed": not bool(
                feature_source_inventory[
                    feature_source_inventory["family_id"].astype(str) == "technical"
                ]["blocked_now"].map(_bool_value).all()
            ),
            "detail": "technical should be contract-feasible",
        },
        {
            "check": "Macro is not blocked but requires strict lagging",
            "passed": not bool(
                feature_source_inventory[
                    feature_source_inventory["family_id"].astype(str) == "macro"
                ]["blocked_now"].map(_bool_value).all()
            ),
            "detail": "macro should be feasible only with lag/revision controls",
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13d_blocked_family_check(
    feature_source_inventory: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for family in ["fundamental", "sentiment"]:
        family_rows = feature_source_inventory[
            feature_source_inventory["family_id"].astype(str) == family
        ]
        blocked = (
            bool(family_rows["blocked_now"].map(_bool_value).all())
            if not family_rows.empty
            else False
        )
        rows.append(
            {
                "family_id": family,
                "present": not family_rows.empty,
                "blocked_now": blocked,
                "passed": not family_rows.empty and blocked,
                "result": "Passed" if not family_rows.empty and blocked else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase13d_phase13e_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13e_boundary", {})

    checks = [
        (
            "phase13e_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "schema design spec" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13e_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            (
                "actual feature ingestion"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "model training"
                in str(boundary.get("forbidden_next_step", "")).lower()
                and "strategy backtest"
                in str(boundary.get("forbidden_next_step", "")).lower()
            ),
        ),
        (
            "phase13e_may_define_feature_schema",
            _bool_value(boundary.get("phase13e_may_define_feature_schema", False)),
            _bool_value(boundary.get("phase13e_may_define_feature_schema", False)),
        ),
        (
            "phase13e_may_define_transform_rules",
            _bool_value(boundary.get("phase13e_may_define_transform_rules", False)),
            _bool_value(boundary.get("phase13e_may_define_transform_rules", False)),
        ),
        (
            "phase13e_may_define_visual_feature_reports",
            _bool_value(
                boundary.get("phase13e_may_define_visual_feature_reports", False)
            ),
            _bool_value(
                boundary.get("phase13e_may_define_visual_feature_reports", False)
            ),
        ),
        (
            "phase13e_may_ingest_features",
            _bool_value(boundary.get("phase13e_may_ingest_features", True)),
            not _bool_value(boundary.get("phase13e_may_ingest_features", True)),
        ),
        (
            "phase13e_may_calculate_features",
            _bool_value(boundary.get("phase13e_may_calculate_features", True)),
            not _bool_value(boundary.get("phase13e_may_calculate_features", True)),
        ),
        (
            "phase13e_may_train_model",
            _bool_value(boundary.get("phase13e_may_train_model", True)),
            not _bool_value(boundary.get("phase13e_may_train_model", True)),
        ),
        (
            "phase13e_may_create_signal",
            _bool_value(boundary.get("phase13e_may_create_signal", True)),
            not _bool_value(boundary.get("phase13e_may_create_signal", True)),
        ),
        (
            "phase13e_may_run_backtest",
            _bool_value(boundary.get("phase13e_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13e_may_run_backtest", True)),
        ),
        (
            "phase13e_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13e_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13e_may_deploy_paper_trading", True)),
        ),
        (
            "phase13e_may_promote_candidate",
            _bool_value(boundary.get("phase13e_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13e_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [
            {
                "boundary_item": item,
                "value": value,
                "passed": passed,
            }
            for item, value, passed in checks
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13d_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13c_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    readiness_claims_check: pd.DataFrame,
    contract_coverage_check: pd.DataFrame,
    blocked_family_check: pd.DataFrame,
    phase13e_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13c_reports_present": bool(report_inventory_check["present"].all())
                if not report_inventory_check.empty
                else False,
                "phase13c_result_passed": bool(phase13c_result_check["passed"].all())
                if not phase13c_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "readiness_claims_locked": bool(readiness_claims_check["passed"].all())
                if not readiness_claims_check.empty
                else False,
                "contract_coverage_passed": bool(contract_coverage_check["passed"].all())
                if not contract_coverage_check.empty
                else False,
                "blocked_families_respected": bool(blocked_family_check["passed"].all())
                if not blocked_family_check.empty
                else False,
                "phase13e_boundary_passed": bool(
                    phase13e_boundary_check["passed"].all()
                )
                if not phase13e_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "feature_ingestion": False,
                "feature_calculation": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "model_training": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13d_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13D summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_audit_role",
            "Feature contract and data availability readiness audit only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13C reports are present",
            (not gates.get("require_phase13c_reports_present", True))
            or bool(row["phase13c_reports_present"]),
            f"phase13c_reports_present={bool(row['phase13c_reports_present'])}",
        ),
        _gate_row(
            "Phase 13C conclusion and gates passed",
            (
                (not gates.get("require_phase13c_conclusion_passed", True))
                or bool(row["phase13c_result_passed"])
            )
            and (
                (not gates.get("require_phase13c_gate_report_passed", True))
                or bool(row["phase13c_result_passed"])
            ),
            f"phase13c_result_passed={bool(row['phase13c_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            (not gates.get("require_config_flags_clean_for_run", True))
            or bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Readiness claims are locked",
            (not gates.get("require_readiness_claims_locked", True))
            or bool(row["readiness_claims_locked"]),
            f"readiness_claims_locked={bool(row['readiness_claims_locked'])}",
        ),
        _gate_row(
            "Contract coverage passed",
            (not gates.get("require_contract_coverage", True))
            or bool(row["contract_coverage_passed"]),
            f"contract_coverage_passed={bool(row['contract_coverage_passed'])}",
        ),
        _gate_row(
            "Blocked families are respected",
            (not gates.get("require_blocked_families_respected", True))
            or bool(row["blocked_families_respected"]),
            f"blocked_families_respected={bool(row['blocked_families_respected'])}",
        ),
        _gate_row(
            "Phase 13E boundary is schema-only",
            (not gates.get("require_phase13e_boundary_schema_only", True))
            or bool(row["phase13e_boundary_passed"]),
            f"phase13e_boundary_passed={bool(row['phase13e_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks feature/model/signal/backtest/paper-trading/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Audit role is correct",
            str(row["audit_role"]) == required_role,
            f"audit_role={row['audit_role']}",
        ),
    ]

    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13d_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False

    verdict = (
        "Completed — feature contract readiness audit passed"
        if all_passed
        else "Failed feature contract readiness audit"
    )
    interpretation = (
        "Phase 13D verified that Phase 13C feature-source inventory, leakage "
        "controls, contract requirements, and blocked-family policies are ready for "
        "schema design. It did not ingest or calculate features, create signals, "
        "run backtests, train models, deploy paper trading, promote a candidate, "
        "or change the final candidate."
        if all_passed
        else "Phase 13D found a readiness, contract, blocked-family, boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13D",
                "diagnostic": "Feature contract readiness audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase13d_markdown(
    *,
    report_inventory_check: pd.DataFrame,
    phase13c_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    readiness_claims_check: pd.DataFrame,
    contract_coverage_check: pd.DataFrame,
    blocked_family_check: pd.DataFrame,
    phase13e_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 13D — Feature Contract / Data Availability Readiness Audit",
        "",
        "This phase audits readiness only. It does not ingest or calculate features, "
        "create signals, run backtests, train models, deploy paper trading, promote "
        "a candidate, or change the final candidate.",
        "",
        "## Report Inventory Check",
        report_inventory_check.to_markdown(index=False),
        "",
        "## Phase 13C Result Check",
        phase13c_result_check.to_markdown(index=False),
        "",
        "## Config Flag Check",
        config_flag_check.to_markdown(index=False),
        "",
        "## Readiness Claims Check",
        readiness_claims_check.to_markdown(index=False),
        "",
        "## Contract Coverage Check",
        contract_coverage_check.to_markdown(index=False),
        "",
        "## Blocked Family Check",
        blocked_family_check.to_markdown(index=False),
        "",
        "## Phase 13E Boundary Check",
        phase13e_boundary_check.to_markdown(index=False),
        "",
        "## Scope Boundary Check",
        scope_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        conclusion.to_markdown(index=False),
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13d_feature_contract_readiness_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13d_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    report_inventory_check = build_phase13d_report_inventory_check(phase_config)
    phase13c_result_check = build_phase13d_phase13c_result_check(phase_config)
    config_flag_check = build_phase13d_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )
    readiness_claims_check = build_phase13d_readiness_claims_check(phase_config)

    reports = phase_config.get("phase13c_reports", {})
    feature_source_inventory = _read_csv_if_exists(
        reports.get("feature_source_inventory", "")
    )
    feature_contract_requirements = _read_csv_if_exists(
        reports.get("feature_contract_requirements", "")
    )
    leakage_control_policy = _read_csv_if_exists(
        reports.get("leakage_control_policy", "")
    )

    contract_coverage_check = build_phase13d_contract_coverage_check(
        feature_source_inventory=feature_source_inventory,
        feature_contract_requirements=feature_contract_requirements,
        leakage_control_policy=leakage_control_policy,
    )
    blocked_family_check = build_phase13d_blocked_family_check(
        feature_source_inventory
    )
    phase13e_boundary_check = build_phase13d_phase13e_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13d_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13c_result_check=phase13c_result_check,
        config_flag_check=config_flag_check,
        readiness_claims_check=readiness_claims_check,
        contract_coverage_check=contract_coverage_check,
        blocked_family_check=blocked_family_check,
        phase13e_boundary_check=phase13e_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13d_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13d_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13c_result_check": phase13c_result_check,
        "config_flag_check": config_flag_check,
        "readiness_claims_check": readiness_claims_check,
        "contract_coverage_check": contract_coverage_check,
        "blocked_family_check": blocked_family_check,
        "phase13e_boundary_check": phase13e_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13d_contract_{name}.csv", index=False)

    write_phase13d_markdown(
        report_inventory_check=report_inventory_check,
        phase13c_result_check=phase13c_result_check,
        config_flag_check=config_flag_check,
        readiness_claims_check=readiness_claims_check,
        contract_coverage_check=contract_coverage_check,
        blocked_family_check=blocked_family_check,
        phase13e_boundary_check=phase13e_boundary_check,
        scope_boundary_check=scope_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase13d_feature_contract_readiness_audit.md",
    )

    print("Wrote Phase 13D feature contract readiness audit reports.")
    return outputs