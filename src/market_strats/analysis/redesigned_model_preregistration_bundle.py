from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


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


def _read_csv_if_exists(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)

    if not csv_path.exists():
        return pd.DataFrame()

    return pd.read_csv(csv_path)


def _gate_row(gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return config.get(key, {}) or {}


def _source_report_check(paths: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in paths.items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)

        rows.append(
            {
                "report_key": report_key,
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": len(frame),
            }
        )

    out = pd.DataFrame(rows)

    if not out.empty:
        out["result"] = out["present"].map({True: "Passed", False: "Failed"})

    return out


def _phase_result_check(
    conclusion_path: str,
    gate_path: str,
    phase_name: str,
) -> pd.DataFrame:
    conclusion = _read_csv_if_exists(conclusion_path)
    gate = _read_csv_if_exists(gate_path)

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_passed = (
        not gate.empty
        and "passed" in gate.columns
        and bool(gate["passed"].map(_bool_value).all())
    )

    out = pd.DataFrame(
        [
            {
                "check": f"{phase_name} conclusion passed",
                "passed": conclusion_passed,
                "detail": "conclusion",
            },
            {
                "check": f"{phase_name} gate report passed",
                "passed": gate_passed,
                "detail": "gate_report",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_model_training",
        "allow_repair_execution",
        "allow_model_selection",
        "allow_holdout_prediction_generation",
        "allow_feature_importance",
        "allow_signal_creation",
        "allow_strategy_backtest",
        "allow_paper_trading_deployment",
        "allow_candidate_promotion",
        "allow_final_candidate_change",
    ]

    rows = []
    for key in keys:
        value = _bool_value(section.get(key, False))
        rows.append({"scope_item": key, "value": value, "passed": not value})

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _normalise_list_columns(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)

    for col in frame.columns:
        frame[col] = frame[col].apply(
            lambda value: "; ".join(map(str, value))
            if isinstance(value, list)
            else value
        )

    return frame


def _boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    rows = []

    for key in ["phase13al_boundary", "phase13am_boundary"]:
        boundary = section.get(key, {})
        allowed = str(
            boundary.get("allowed_next_step", boundary.get("allowed_future_step", ""))
        )
        forbidden = str(
            boundary.get("forbidden_next_step", boundary.get("forbidden_future_step", ""))
        )

        rows.append(
            {
                "boundary": key,
                "allowed": allowed,
                "forbidden": forbidden,
                "passed": bool(
                    (
                        "checkpoint" in allowed.lower()
                        or "pre-registration" in allowed.lower()
                        or "preregistration" in allowed.lower()
                    )
                    and "model training" in forbidden.lower()
                    and "holdout prediction" in forbidden.lower()
                    and "feature importance" in forbidden.lower()
                    and "strategy backtest" in forbidden.lower()
                ),
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _select_candidate_target(
    screen: pd.DataFrame,
    policy: dict[str, Any],
) -> tuple[str, list[str], str]:
    if screen.empty:
        return "", [], "No redesign screen was available."

    preferred_order = [
        str(item)
        for item in _as_list(policy.get("preferred_viable_target_order"))
    ]

    viable = screen[screen["viable_for_future_interpretation"].map(_bool_value)].copy()
    viable_ids = set(viable["target_variant_id"].astype(str))

    for target_id in preferred_order:
        if target_id in viable_ids:
            backups = [
                item
                for item in preferred_order
                if item in viable_ids and item != target_id
            ]
            return (
                target_id,
                backups,
                (
                    "Chosen as candidate target for future pre-registered "
                    "model run because it was viable and highest in the "
                    "pre-registered preference order."
                ),
            )

    return "", sorted(viable_ids), "No preferred viable target was available."


def _target_detail(
    target_id: str,
    balance: pd.DataFrame,
    outcome: pd.DataFrame,
) -> dict[str, Any]:
    balance_row = balance[
        balance["target_variant_id"].astype(str).eq(target_id)
    ]

    train_ratio = 0.0
    validation_ratio = 0.0

    if not balance_row.empty:
        train_ratio = float(balance_row.iloc[0].get("train_fragile_ratio", 0.0))
        validation_ratio = float(
            balance_row.iloc[0].get("validation_fragile_ratio", 0.0)
        )

    target_outcome = outcome[
        outcome["target_variant_id"].astype(str).eq(target_id)
    ].copy()

    def outcome_mean(class_label: str, outcome_col: str) -> float:
        row = target_outcome[
            target_outcome["class_label"].astype(str).eq(class_label)
            & target_outcome["outcome_column"].astype(str).eq(outcome_col)
        ]
        if row.empty:
            return 0.0
        return float(row.iloc[0].get("mean", 0.0))

    return {
        "candidate_target_variant": target_id,
        "train_fragile_ratio": train_ratio,
        "validation_fragile_ratio": validation_ratio,
        "fragile_mean_63d_return": outcome_mean("fragile", "future_return_63d"),
        "neutral_mean_63d_return": outcome_mean("neutral", "future_return_63d"),
        "supportive_mean_63d_return": outcome_mean("supportive", "future_return_63d"),
        "fragile_mean_63d_drawdown": outcome_mean(
            "fragile",
            "future_window_max_drawdown_63d",
        ),
        "neutral_mean_63d_drawdown": outcome_mean(
            "neutral",
            "future_window_max_drawdown_63d",
        ),
    }


def _feature_family_status(feature_families: pd.DataFrame) -> pd.DataFrame:
    if feature_families.empty:
        return pd.DataFrame()

    out = feature_families.copy()
    out["usable_currently"] = (
        pd.to_numeric(out["value_feature_columns"], errors="coerce").fillna(0) > 0
    )
    out["required_for_next_model_run"] = out["family_id"].astype(str).isin(
        ["technical", "macro"]
    )
    return out


def _blocked_target_report(
    feasibility: pd.DataFrame,
    screen: pd.DataFrame,
    policy: dict[str, Any],
) -> pd.DataFrame:
    blocked_ids = set(str(item) for item in _as_list(policy.get("blocked_targets")))
    rows = []

    for target_id in sorted(blocked_ids):
        feasible_row = feasibility[
            feasibility["target_variant_id"].astype(str).eq(target_id)
        ]
        screen_row = screen[screen["target_variant_id"].astype(str).eq(target_id)]

        feasible = (
            _bool_value(feasible_row.iloc[0].get("feasible", False))
            if not feasible_row.empty
            else False
        )
        viable = (
            _bool_value(
                screen_row.iloc[0].get("viable_for_future_interpretation", False)
            )
            if not screen_row.empty
            else False
        )

        if target_id == "original_63d_return_state":
            reason = "Original target failed validation fragile-balance gate."
        elif "21d" in target_id:
            reason = "Blocked because 21D outcome columns are unavailable."
        elif "126d" in target_id:
            reason = "Blocked because 126D outcome columns are unavailable."
        else:
            reason = "Blocked by pre-registered target decision policy."

        rows.append(
            {
                "target_variant_id": target_id,
                "feasible": feasible,
                "viable_for_future_interpretation": viable,
                "blocked_for_next_model_run": True,
                "block_reason": reason,
            }
        )

    return pd.DataFrame(rows)


def save_phase13ak_target_feature_redesign_interpretation_decision(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(
        config,
        "phase13ak_target_feature_redesign_interpretation_decision",
    )

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    source_check = _source_report_check(source_reports)
    phase13aj_check = _phase_result_check(
        source_reports["phase13aj_conclusion"],
        source_reports["phase13aj_gate_report"],
        "Phase 13AJ",
    )

    feasibility = _read_csv_if_exists(source_reports["feasibility_report"])
    balance = _read_csv_if_exists(source_reports["class_balance_report"])
    outcome = _read_csv_if_exists(source_reports["target_outcome_profile_report"])
    feature_families = _read_csv_if_exists(
        source_reports["feature_family_availability_report"]
    )
    screen = _read_csv_if_exists(source_reports["redesign_screen_report"])

    policy = section.get("target_decision_policy", {})
    candidate_target, backup_targets, decision_reason = _select_candidate_target(
        screen,
        policy,
    )
    target_info = _target_detail(candidate_target, balance, outcome)
    feature_status = _feature_family_status(feature_families)
    blocked_targets = _blocked_target_report(feasibility, screen, policy)
    boundary = _boundary_check(section)
    scope = _scope_check(section)

    candidate_decision = pd.DataFrame(
        [
            {
                "decision": policy.get(
                    "primary_decision",
                    "pre_register_redesigned_model_run",
                ),
                "candidate_target_variant": candidate_target,
                "backup_target_variants": "; ".join(backup_targets),
                "decision_reason": decision_reason,
                "target_candidate_for_future_model_run": bool(candidate_target),
                "target_variant_promoted": False,
                "model_selected": False,
                "holdout_permission": False,
                "feature_importance_permission": False,
                "signal_permission": False,
                "backtest_permission": False,
                "candidate_promotion": False,
                **target_info,
            }
        ]
    )

    technical_available = False
    macro_available = False
    if not feature_status.empty:
        technical_rows = feature_status[
            feature_status["family_id"].astype(str).eq("technical")
        ]
        macro_rows = feature_status[
            feature_status["family_id"].astype(str).eq("macro")
        ]
        technical_available = (
            _bool_value(technical_rows.iloc[0].get("usable_currently", False))
            if not technical_rows.empty
            else False
        )
        macro_available = (
            _bool_value(macro_rows.iloc[0].get("usable_currently", False))
            if not macro_rows.empty
            else False
        )

    summary = pd.DataFrame(
        [
            {
                "decision_role": section.get("decision_role", ""),
                "phase_branch": section.get("phase_branch", ""),
                "source_phase": section.get("source_phase", ""),
                "proposed_next_phase": section.get("proposed_next_phase", ""),
                "phase13aj_passed": bool(phase13aj_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all())
                if not source_check.empty
                else False,
                "candidate_target_variant": candidate_target,
                "viable_target_exists": bool(candidate_target),
                "backup_target_count": len(backup_targets),
                "technical_features_available": technical_available,
                "macro_features_available": macro_available,
                "blocked_target_rows": len(blocked_targets),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AJ passed",
                bool(summary.iloc[0]["phase13aj_passed"]),
                "phase13aj",
            ),
            _gate_row(
                "Source reports present",
                bool(summary.iloc[0]["source_reports_present"]),
                "source reports",
            ),
            _gate_row(
                "Viable target exists",
                bool(summary.iloc[0]["viable_target_exists"]),
                f"candidate={candidate_target}",
            ),
            _gate_row(
                "Candidate target decision report exists",
                len(candidate_decision) == 1,
                "candidate decision",
            ),
            _gate_row(
                "Blocked target report exists",
                len(blocked_targets) > 0,
                f"rows={len(blocked_targets)}",
            ),
            _gate_row(
                "Technical and macro feature families are available",
                technical_available and macro_available,
                f"technical={technical_available}; macro={macro_available}",
            ),
            _gate_row(
                "Boundaries passed",
                bool(boundary["passed"].all()),
                "phase13al/phase13am",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Decision role is correct",
                section.get("decision_role")
                == (
                    "Target-feature redesign interpretation and candidate "
                    "target decision only"
                ),
                section.get("decision_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AK",
                "diagnostic": (
                    "Target-feature redesign interpretation and candidate "
                    "target decision"
                ),
                "verdict": (
                    "Completed — target-feature redesign interpretation passed"
                    if bool(gate_report["passed"].all())
                    else "Failed target-feature redesign interpretation"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13aj_result_check": phase13aj_check,
        "candidate_target_decision_report": candidate_decision,
        "blocked_target_report": blocked_targets,
        "feature_family_status_report": feature_status,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13ak_target_decision_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AK target-feature interpretation reports.")
    return outputs


def _forbidden_overclaim_check(
    report_paths: list[str],
    forbidden_phrases: list[str],
) -> pd.DataFrame:
    rows = []

    for phrase in forbidden_phrases:
        matched_paths = []

        for path in report_paths:
            report_path = Path(path)
            if not report_path.exists():
                continue

            text = report_path.read_text(encoding="utf-8", errors="ignore").lower()
            if phrase.lower() in text:
                matched_paths.append(str(report_path))

        rows.append(
            {
                "phrase": phrase,
                "matched_paths": "; ".join(matched_paths),
                "passed": len(matched_paths) == 0,
                "result": "Passed" if len(matched_paths) == 0 else "Failed",
            }
        )

    return pd.DataFrame(rows)


def save_phase13al_target_feature_redesign_checkpoint_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13al_target_feature_redesign_checkpoint_audit")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = []
    for key, expected in section.get("expected_runtime_flags", {}).items():
        actual = config.get(key, {}).get("enabled")
        flags.append(
            {
                "config_key": key,
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": actual is expected,
            }
        )

    config_check = pd.DataFrame(flags)
    config_check["result"] = config_check["passed"].map(
        {True: "Passed", False: "Failed"}
    )

    reports = section.get("phase13ak_reports", {})
    inventory = _source_report_check(reports)
    phase13ak_check = _phase_result_check(
        reports["conclusion"],
        reports["gate_report"],
        "Phase 13AK",
    )
    candidate = _read_csv_if_exists(reports["candidate_target_decision_report"])

    candidate_clean = (
        not candidate.empty
        and not candidate["model_selected"].map(_bool_value).any()
        and not candidate["signal_permission"].map(_bool_value).any()
        and not candidate["backtest_permission"].map(_bool_value).any()
        and not candidate["candidate_promotion"].map(_bool_value).any()
    )

    overclaim = _forbidden_overclaim_check(
        list(reports.values()),
        _as_list(section.get("forbidden_overclaim_phrases")),
    )
    scope = _scope_check(section)
    boundary = _phase13am_boundary_check(section)

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "phase13ak_passed": bool(phase13ak_check["passed"].all()),
                "config_flags_clean": bool(config_check["passed"].all()),
                "phase13ak_reports_present": bool(inventory["present"].all())
                if not inventory.empty
                else False,
                "candidate_target_decision_clean": candidate_clean,
                "forbidden_overclaim_absent": bool(overclaim["passed"].all())
                if not overclaim.empty
                else True,
                "phase13am_boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AK passed",
                bool(summary.iloc[0]["phase13ak_passed"]),
                "phase13ak",
            ),
            _gate_row(
                "Config flags clean",
                bool(summary.iloc[0]["config_flags_clean"]),
                "runtime flags",
            ),
            _gate_row(
                "Phase 13AK reports present",
                bool(summary.iloc[0]["phase13ak_reports_present"]),
                "inventory",
            ),
            _gate_row(
                "Candidate target decision clean",
                candidate_clean,
                "no model/signal/backtest/promotion permission",
            ),
            _gate_row(
                "Forbidden overclaim absent",
                bool(summary.iloc[0]["forbidden_overclaim_absent"]),
                "overclaim",
            ),
            _gate_row(
                "Phase 13AM boundary is preregistration only",
                bool(boundary["passed"].all()),
                "phase13am",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Target-feature redesign checkpoint audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AL",
                "diagnostic": "Target-feature redesign checkpoint audit",
                "verdict": (
                    "Completed — target-feature redesign checkpoint audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed target-feature redesign checkpoint audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "config_flag_check": config_check,
        "report_inventory_check": inventory,
        "phase13ak_result_check": phase13ak_check,
        "candidate_target_boundary_check": pd.DataFrame(
            [
                {
                    "check": "candidate_target_decision_clean",
                    "passed": candidate_clean,
                    "result": "Passed" if candidate_clean else "Failed",
                }
            ]
        ),
        "forbidden_overclaim_check": overclaim,
        "phase13am_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13al_target_checkpoint_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AL target-feature checkpoint reports.")
    return outputs


def _phase13am_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    boundary = section.get("phase13am_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": "phase13am_boundary_is_preregistration_only",
            "passed": "pre-registration" in allowed or "preregistration" in allowed,
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": "phase13am_boundary_blocks_forbidden_actions",
            "passed": bool(
                "model training" in forbidden
                and "holdout prediction" in forbidden
                and "feature importance" in forbidden
                and "strategy backtest" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _flatten_dict_to_policy_frame(policy: dict[str, Any]) -> pd.DataFrame:
    rows = []

    for key, value in policy.items():
        rows.append(
            {
                "policy_key": key,
                "policy_value": "; ".join(map(str, value))
                if isinstance(value, list)
                else value,
            }
        )

    return pd.DataFrame(rows)


def save_phase13am_redesigned_model_run_preregistration(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13am_redesigned_model_run_preregistration")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    source_check = _source_report_check(source_reports)
    phase13al_check = _phase_result_check(
        source_reports["phase13al_conclusion"],
        source_reports["phase13al_gate_report"],
        "Phase 13AL",
    )

    candidate = _read_csv_if_exists(source_reports["candidate_target_decision_report"])
    assignment = _read_csv_if_exists(source_reports["target_assignment_panel"])
    dataset = _read_csv_if_exists(source_reports["dataset"])

    fallback_target = section.get("redesigned_model_run", {}).get(
        "primary_target_variant_fallback",
        "return_drawdown_63d_composite",
    )
    candidate_target = fallback_target

    if not candidate.empty:
        candidate_target = str(candidate.iloc[0].get("candidate_target_variant", ""))

    target_column_available = candidate_target in assignment.columns

    model_run_spec = pd.DataFrame(
        [
            {
                **section.get("redesigned_model_run", {}),
                "candidate_target_variant": candidate_target,
                "target_column_available": target_column_available,
                "model_training": False,
                "holdout_predictions": False,
                "model_selection": False,
            }
        ]
    )

    feature_policy = _flatten_dict_to_policy_frame(section.get("feature_policy", {}))
    preprocessing_policy = _flatten_dict_to_policy_frame(
        section.get("preprocessing_policy", {})
    )
    model_families = _normalise_list_columns(
        section.get("registered_model_families", [])
    )
    success_gates = _flatten_dict_to_policy_frame(
        section.get("validation_success_gates", {})
    )
    boundary = _model_run_boundary_check(section)
    scope = _scope_check(section)

    numeric_prefixes = tuple(
        section.get("feature_policy", {}).get("numeric_feature_prefixes", [])
    )
    categorical_prefixes = tuple(
        section.get("feature_policy", {}).get("categorical_feature_prefixes", [])
    )

    numeric_features = [
        col for col in dataset.columns if str(col).startswith(numeric_prefixes)
    ]
    categorical_features = [
        col for col in dataset.columns if str(col).startswith(categorical_prefixes)
    ]

    summary = pd.DataFrame(
        [
            {
                "spec_role": section.get("spec_role", ""),
                "phase13al_passed": bool(phase13al_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all())
                if not source_check.empty
                else False,
                "candidate_target_variant": candidate_target,
                "target_assignment_column_available": target_column_available,
                "numeric_feature_columns": len(numeric_features),
                "categorical_feature_columns": len(categorical_features),
                "registered_model_count": len(model_families),
                "success_gate_rows": len(success_gates),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AL passed",
                bool(summary.iloc[0]["phase13al_passed"]),
                "phase13al",
            ),
            _gate_row(
                "Candidate target available",
                bool(candidate_target),
                candidate_target,
            ),
            _gate_row(
                "Target assignment column available",
                target_column_available,
                candidate_target,
            ),
            _gate_row(
                "Feature policy registered",
                len(feature_policy) > 0,
                f"rows={len(feature_policy)}",
            ),
            _gate_row(
                "Preprocessing policy registered",
                len(preprocessing_policy) > 0,
                f"rows={len(preprocessing_policy)}",
            ),
            _gate_row(
                "Model families registered",
                len(model_families) >= 5,
                f"rows={len(model_families)}",
            ),
            _gate_row(
                "Success gates registered",
                len(success_gates) > 0,
                f"rows={len(success_gates)}",
            ),
            _gate_row(
                "Boundaries passed",
                bool(boundary["passed"].all()),
                "phase13an/phase13ao",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Spec role is correct",
                section.get("spec_role")
                == "Redesigned model run pre-registration spec only",
                section.get("spec_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AM",
                "diagnostic": "Redesigned model run pre-registration spec",
                "verdict": (
                    "Completed — redesigned model run pre-registration passed"
                    if bool(gate_report["passed"].all())
                    else "Failed redesigned model run pre-registration"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13al_result_check": phase13al_check,
        "model_run_spec": model_run_spec,
        "feature_policy": feature_policy,
        "preprocessing_policy": preprocessing_policy,
        "registered_model_families": model_families,
        "validation_success_gates": success_gates,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13am_model_prereg_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AM redesigned model run pre-registration reports.")
    return outputs


def _model_run_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    rows = []

    for key in ["phase13an_boundary", "phase13ao_boundary"]:
        boundary = section.get(key, {})
        allowed = str(
            boundary.get("allowed_next_step", boundary.get("allowed_future_step", ""))
        ).lower()
        forbidden = str(
            boundary.get("forbidden_next_step", boundary.get("forbidden_future_step", ""))
        ).lower()

        rows.append(
            {
                "boundary": key,
                "allowed": allowed,
                "forbidden": forbidden,
                "passed": bool(
                    (
                        "readiness" in allowed
                        or "train/validation" in allowed
                        or "training" in allowed
                    )
                    and "holdout prediction" in forbidden
                    and "feature importance" in forbidden
                    and "strategy backtest" in forbidden
                ),
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _prefix_columns(columns: list[str], prefixes: tuple[str, ...]) -> list[str]:
    return [col for col in columns if str(col).startswith(prefixes)]


def _forbidden_feature_fragment_check(
    feature_cols: list[str],
    fragments: list[str],
) -> pd.DataFrame:
    rows = []

    for fragment in fragments:
        matched = [
            col for col in feature_cols if fragment.lower() in str(col).lower()
        ]
        rows.append(
            {
                "fragment": fragment,
                "matched_columns": "; ".join(matched),
                "passed": len(matched) == 0,
                "result": "Passed" if len(matched) == 0 else "Failed",
            }
        )

    return pd.DataFrame(rows)


def save_phase13an_redesigned_model_run_readiness_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase13an_redesigned_model_run_readiness_audit")

    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = []
    for key, expected in section.get("expected_runtime_flags", {}).items():
        actual = config.get(key, {}).get("enabled")
        flags.append(
            {
                "config_key": key,
                "expected_enabled": expected,
                "actual_enabled": actual,
                "passed": actual is expected,
            }
        )

    config_check = pd.DataFrame(flags)
    config_check["result"] = config_check["passed"].map(
        {True: "Passed", False: "Failed"}
    )

    prereg_reports = section.get("phase13am_reports", {})
    inventory = _source_report_check(prereg_reports)
    phase13am_check = _phase_result_check(
        prereg_reports["conclusion"],
        prereg_reports["gate_report"],
        "Phase 13AM",
    )

    source_reports = section.get("source_reports", {})
    candidate = _read_csv_if_exists(source_reports["candidate_target_decision_report"])
    assignment = _read_csv_if_exists(source_reports["target_assignment_panel"])
    dataset = _read_csv_if_exists(source_reports["dataset"])
    model_run_spec = _read_csv_if_exists(prereg_reports["model_run_spec"])

    target_id = ""
    if not candidate.empty:
        target_id = str(candidate.iloc[0].get("candidate_target_variant", ""))

    target_ready = target_id in assignment.columns
    combined = dataset.copy()

    if target_ready:
        combined["redesigned_target"] = assignment[target_id].astype(str)

    thresholds = section.get("readiness_thresholds", {})
    train_label = "train"
    validation_label = "validation"

    train = combined[combined["split_label"].astype(str).eq(train_label)].copy()
    validation = combined[
        combined["split_label"].astype(str).eq(validation_label)
    ].copy()

    train_ready = len(train) >= int(thresholds.get("min_train_rows", 500))
    validation_ready = len(validation) >= int(
        thresholds.get("min_validation_rows", 200)
    )

    train_fragile_ratio = (
        float(train["redesigned_target"].eq("fragile").mean())
        if target_ready and len(train)
        else 0.0
    )
    validation_fragile_ratio = (
        float(validation["redesigned_target"].eq("fragile").mean())
        if target_ready and len(validation)
        else 0.0
    )

    target_balance_ready = (
        train_fragile_ratio >= float(thresholds.get("min_train_fragile_ratio", 0.12))
        and validation_fragile_ratio
        >= float(thresholds.get("min_validation_fragile_ratio", 0.12))
    )

    feature_policy = config.get(
        "phase13am_redesigned_model_run_preregistration",
        {},
    ).get("feature_policy", {})
    numeric_prefixes = tuple(feature_policy.get("numeric_feature_prefixes", []))
    categorical_prefixes = tuple(
        feature_policy.get("categorical_feature_prefixes", [])
    )

    numeric_features = _prefix_columns(list(dataset.columns), numeric_prefixes)
    categorical_features = _prefix_columns(list(dataset.columns), categorical_prefixes)
    feature_cols = numeric_features + categorical_features

    feature_matrix_ready = (
        len(numeric_features) >= int(thresholds.get("min_numeric_features", 4))
        and len(categorical_features)
        >= int(thresholds.get("min_categorical_features", 4))
    )

    forbidden_fragments = _as_list(feature_policy.get("forbidden_feature_fragments"))
    forbidden_feature_check = _forbidden_feature_fragment_check(
        feature_cols,
        [str(item) for item in forbidden_fragments],
    )

    holdout_locked = True
    if not model_run_spec.empty and "holdout_locked" in model_run_spec.columns:
        holdout_locked = _bool_value(model_run_spec.iloc[0].get("holdout_locked", True))

    boundary = _phase13ao_boundary_check(section)
    scope = _scope_check(section)

    target_readiness = pd.DataFrame(
        [
            {
                "candidate_target_variant": target_id,
                "target_assignment_column_ready": target_ready,
                "train_rows": len(train),
                "validation_rows": len(validation),
                "train_ready": train_ready,
                "validation_ready": validation_ready,
                "train_fragile_ratio": train_fragile_ratio,
                "validation_fragile_ratio": validation_fragile_ratio,
                "target_balance_ready": target_balance_ready,
            }
        ]
    )

    feature_matrix_readiness = pd.DataFrame(
        [
            {
                "numeric_feature_columns": len(numeric_features),
                "categorical_feature_columns": len(categorical_features),
                "total_feature_columns": len(feature_cols),
                "feature_matrix_ready": feature_matrix_ready,
                "numeric_features": "; ".join(numeric_features),
                "categorical_features": "; ".join(categorical_features),
            }
        ]
    )

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "phase13am_passed": bool(phase13am_check["passed"].all()),
                "config_flags_clean": bool(config_check["passed"].all()),
                "model_prereg_reports_present": bool(inventory["present"].all())
                if not inventory.empty
                else False,
                "candidate_target_column_ready": target_ready,
                "train_validation_rows_ready": train_ready and validation_ready,
                "target_balance_ready": target_balance_ready,
                "feature_matrix_ready": feature_matrix_ready,
                "forbidden_feature_fragments_absent": bool(
                    forbidden_feature_check["passed"].all()
                )
                if not forbidden_feature_check.empty
                else True,
                "holdout_locked": holdout_locked,
                "phase13ao_boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "model_training": False,
                "holdout_prediction": False,
                "model_selection": False,
                "feature_importance": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row(
                "Phase 13AM passed",
                bool(summary.iloc[0]["phase13am_passed"]),
                "phase13am",
            ),
            _gate_row(
                "Config flags clean",
                bool(summary.iloc[0]["config_flags_clean"]),
                "runtime flags",
            ),
            _gate_row(
                "Model preregistration reports present",
                bool(summary.iloc[0]["model_prereg_reports_present"]),
                "inventory",
            ),
            _gate_row(
                "Candidate target column ready",
                target_ready,
                target_id,
            ),
            _gate_row(
                "Train/validation rows ready",
                train_ready and validation_ready,
                f"train={len(train)}; validation={len(validation)}",
            ),
            _gate_row(
                "Target fragile balance ready",
                target_balance_ready,
                (
                    f"train_fragile={train_fragile_ratio:.4f}; "
                    f"validation_fragile={validation_fragile_ratio:.4f}"
                ),
            ),
            _gate_row(
                "Feature matrix ready",
                feature_matrix_ready,
                (
                    f"numeric={len(numeric_features)}; "
                    f"categorical={len(categorical_features)}"
                ),
            ),
            _gate_row(
                "Forbidden feature fragments absent",
                bool(summary.iloc[0]["forbidden_feature_fragments_absent"]),
                "feature leak check",
            ),
            _gate_row(
                "Holdout locked",
                holdout_locked,
                "holdout_locked",
            ),
            _gate_row(
                "Phase 13AO boundary is train/validation only",
                bool(boundary["passed"].all()),
                "phase13ao",
            ),
            _gate_row(
                "Scope blocks forbidden actions",
                bool(scope["passed"].all()),
                "scope",
            ),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Redesigned model run readiness and leakage audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 13AN",
                "diagnostic": "Redesigned model run readiness and leakage audit",
                "verdict": (
                    "Completed — redesigned model run readiness audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed redesigned model run readiness audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "config_flag_check": config_check,
        "report_inventory_check": inventory,
        "phase13am_result_check": phase13am_check,
        "target_readiness_check": target_readiness,
        "feature_matrix_readiness_check": feature_matrix_readiness,
        "forbidden_feature_fragment_check": forbidden_feature_check,
        "phase13ao_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(
            reports_path / f"phase13an_model_readiness_{name}.csv",
            index=False,
        )

    print("Wrote Phase 13AN redesigned model run readiness reports.")
    return outputs


def _phase13ao_boundary_check(section: dict[str, Any]) -> pd.DataFrame:
    boundary = section.get("phase13ao_boundary", {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": "phase13ao_boundary_is_train_validation_training_only",
            "passed": "train/validation" in allowed and "training" in allowed,
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": "phase13ao_boundary_blocks_holdout_signal_backtest",
            "passed": bool(
                "holdout prediction" in forbidden
                and "feature importance" in forbidden
                and "strategy backtest" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out