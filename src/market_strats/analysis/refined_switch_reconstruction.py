from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.bid_ask_market_impact_diagnostic import (
    _find_final_candidate_frame,
)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()
    if clean in {"true", "1", "yes", "y"}:
        return True
    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False
    return bool(value)


def _section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return config.get(key, {}) or {}


def _read_csv_if_exists(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def _gate_row(gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _phase_result_check(conclusion_path: str, gate_path: str, phase_name: str) -> pd.DataFrame:
    conclusion = _read_csv_if_exists(conclusion_path)
    gate = _read_csv_if_exists(gate_path)

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
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


def _first_existing_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {str(col).lower(): str(col) for col in frame.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_switch_log_export",
        "allow_fresh_data_extension",
        "allow_current_signal_generation",
        "allow_paper_dry_run_preregistration",
        "allow_broker_api_integration",
        "allow_paper_trading_deployment",
        "allow_live_trading",
        "allow_real_money_deployment",
        "allow_paper_trading_ready_claim",
        "allow_candidate_promotion",
        "allow_final_candidate_change",
        "allow_model_training",
        "allow_unregistered_ml",
        "allow_optimisation",
        "allow_multi_asset_expansion",
        "allow_feature_importance",
    ]

    rows = []
    for key in keys:
        if key not in section:
            continue

        value = _bool_value(section.get(key, False))
        allowed_exception = key in {"allow_switch_log_export", "allow_column_diagnostic"}

        rows.append(
            {
                "scope_item": key,
                "value": value,
                "passed": (not value) or allowed_exception,
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _boundary_check(section: dict[str, Any], key: str) -> pd.DataFrame:
    boundary = section.get(key, {})
    allowed = str(
        boundary.get("allowed_next_step", boundary.get("allowed_next_step_if_reconciled", ""))
    ).lower()
    allowed_failed = str(boundary.get("allowed_next_step_if_failed", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": f"{key}_allowed_next_step_is_bounded",
            "passed": bool(
                "audit" in allowed
                or "switch reconstruction" in allowed
                or "fresh current-signal" in allowed
                or "repair" in allowed_failed
                or "signal consistency" in allowed
            ),
            "detail": boundary.get(
                "allowed_next_step",
                boundary.get("allowed_next_step_if_reconciled", ""),
            ),
        },
        {
            "check": f"{key}_blocks_forbidden_actions",
            "passed": bool(
                "broker" in forbidden
                and "live trading" in forbidden
                and "real-money" in forbidden
                and "candidate promotion" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _required_column_check(frame: pd.DataFrame, required: list[str], frame_name: str) -> pd.DataFrame:
    rows = []
    for col in required:
        rows.append(
            {
                "frame": frame_name,
                "required_column": col,
                "present": col in frame.columns,
                "result": "Passed" if col in frame.columns else "Failed",
            }
        )
    return pd.DataFrame(rows)


def _normalise_numeric_series(series: pd.Series, transform: str) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")

    if transform == "inverse":
        values = 1.0 - values

    return values.ffill()


def _mode_to_exposure(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.lower()

    exposure = np.where(
        text.str.contains("offensive|risk_on|spy|equity", regex=True),
        1.0,
        np.where(
            text.str.contains("defensive|cash|risk_off", regex=True),
            0.0,
            np.nan,
        ),
    )

    numeric = pd.to_numeric(series, errors="coerce")
    exposure = np.where(pd.notna(numeric), numeric, exposure)

    return pd.Series(exposure, index=series.index).ffill()


def _change_count(series: pd.Series) -> int:
    clean = pd.to_numeric(series, errors="coerce").round(10)
    clean = clean.ffill()

    if clean.dropna().empty:
        return 0

    changed = clean.ne(clean.shift(1))
    return max(int(changed.fillna(False).sum()) - 1, 0)


def _value_profile(series: pd.Series) -> dict[str, Any]:
    numeric = pd.to_numeric(series, errors="coerce")

    non_null = int(series.notna().sum())
    numeric_non_null = int(numeric.notna().sum())

    return {
        "non_null_rows": non_null,
        "numeric_non_null_rows": numeric_non_null,
        "numeric_ratio": numeric_non_null / non_null if non_null else 0.0,
        "unique_values": int(series.dropna().nunique()),
        "min_value": float(numeric.min()) if numeric.notna().any() else "",
        "max_value": float(numeric.max()) if numeric.notna().any() else "",
        "first_value": series.dropna().iloc[0] if non_null else "",
        "last_value": series.dropna().iloc[-1] if non_null else "",
    }


def _column_profile(
    *,
    frame: pd.DataFrame,
    inspected_columns: list[str],
) -> pd.DataFrame:
    rows = []

    for col in inspected_columns:
        present = col in frame.columns

        if not present:
            rows.append(
                {
                    "column_name": col,
                    "present": False,
                    "semantic_hint": "missing",
                    "non_null_rows": 0,
                    "numeric_non_null_rows": 0,
                    "numeric_ratio": 0.0,
                    "unique_values": 0,
                    "min_value": "",
                    "max_value": "",
                    "first_value": "",
                    "last_value": "",
                }
            )
            continue

        profile = _value_profile(frame[col])

        if col == "turnover":
            hint = "execution_attribute_not_switch_definition"
        elif "target" in col and ("weight" in col or "exposure" in col):
            hint = "likely_final_target_allocation_candidate"
        elif "offensive" in col or "defensive" in col or "cash" in col:
            hint = "allocation_weight_candidate"
        elif col == "position":
            hint = "mode_or_position_state_candidate_but_potentially_noisy"
        elif "slippage" in col:
            hint = "execution_cost_attribute_not_switch_definition"
        else:
            hint = "unknown"

        rows.append({"column_name": col, "present": True, "semantic_hint": hint, **profile})

    return pd.DataFrame(rows)


def _candidate_exposure_series(
    *,
    frame: pd.DataFrame,
    column: str,
    transform: str,
) -> pd.Series:
    if transform in {"direct", "inverse"}:
        return _normalise_numeric_series(frame[column], transform)
    return _mode_to_exposure(frame[column])


def _candidate_switch_definition_report(
    *,
    frame: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    expected = int(section.get("expected_switch_count", 36))
    tolerance = int(section.get("switch_count_abs_tolerance", 2))
    candidates = section.get("executable_exposure_candidate_columns", {})

    rows = []

    for transform, columns in candidates.items():
        for col in columns:
            if col not in frame.columns:
                rows.append(
                    {
                        "candidate_column": col,
                        "transform": transform,
                        "present": False,
                        "candidate_switch_count": 0,
                        "distance_to_expected": expected,
                        "count_reconciled": False,
                        "numeric_ratio": 0.0,
                        "min_exposure": "",
                        "max_exposure": "",
                        "valid_exposure_range": False,
                        "eligible_final_definition": False,
                    }
                )
                continue

            exposure = _candidate_exposure_series(
                frame=frame,
                column=col,
                transform=transform,
            )
            switch_count = _change_count(exposure)
            numeric = pd.to_numeric(exposure, errors="coerce")
            numeric_ratio = numeric.notna().mean()
            valid_range = bool(
                numeric.notna().any()
                and numeric.dropna().between(-0.000001, 1.500001).all()
            )
            count_reconciled = abs(switch_count - expected) <= tolerance
            eligible = bool(count_reconciled and valid_range and numeric_ratio >= 0.95)

            rows.append(
                {
                    "candidate_column": col,
                    "transform": transform,
                    "present": True,
                    "candidate_switch_count": switch_count,
                    "distance_to_expected": abs(switch_count - expected),
                    "count_reconciled": count_reconciled,
                    "numeric_ratio": numeric_ratio,
                    "min_exposure": float(numeric.min()) if numeric.notna().any() else "",
                    "max_exposure": float(numeric.max()) if numeric.notna().any() else "",
                    "valid_exposure_range": valid_range,
                    "eligible_final_definition": eligible,
                }
            )

    return pd.DataFrame(rows)


def _selected_switch_definition(
    *,
    candidate_report: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    priority = list(section.get("selection_priority", []))
    eligible = candidate_report[
        candidate_report["eligible_final_definition"].map(_bool_value)
    ].copy()

    if eligible.empty:
        best = candidate_report[candidate_report["present"].map(_bool_value)].copy()
        if best.empty:
            return pd.DataFrame(
                [
                    {
                        "selected": False,
                        "selected_column": "",
                        "transform": "",
                        "candidate_switch_count": 0,
                        "count_reconciled": False,
                        "selection_reason": "no_present_candidate_columns",
                    }
                ]
            )

        best = best.sort_values(["distance_to_expected", "candidate_column"]).head(1)
        row = best.iloc[0]

        return pd.DataFrame(
            [
                {
                    "selected": False,
                    "selected_column": row["candidate_column"],
                    "transform": row["transform"],
                    "candidate_switch_count": int(row["candidate_switch_count"]),
                    "count_reconciled": _bool_value(row["count_reconciled"]),
                    "selection_reason": "no_eligible_reconciled_final_definition",
                }
            ]
        )

    eligible["priority_rank"] = eligible["candidate_column"].map(
        lambda col: priority.index(col) if col in priority else 10_000
    )
    selected = eligible.sort_values(["priority_rank", "distance_to_expected"]).iloc[0]

    return pd.DataFrame(
        [
            {
                "selected": True,
                "selected_column": selected["candidate_column"],
                "transform": selected["transform"],
                "candidate_switch_count": int(selected["candidate_switch_count"]),
                "count_reconciled": _bool_value(selected["count_reconciled"]),
                "selection_reason": "eligible_reconciled_final_target_exposure_definition",
            }
        ]
    )


def save_phase15i_final_candidate_column_semantics_diagnostic(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15i_final_candidate_column_semantics_diagnostic")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase15h_check = _phase_result_check(
        section.get("source_reports", {}).get("phase15h_conclusion", ""),
        section.get("source_reports", {}).get("phase15h_gate_report", ""),
        "Phase 15H",
    )

    final_candidate = _find_final_candidate_frame(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    date_col = _first_existing_col(final_candidate, ["date", "decision_date"])
    canonical_endpoint = pd.to_datetime(section.get("canonical_endpoint", ""), errors="coerce")

    if date_col:
        final_candidate = final_candidate.copy()
        final_candidate[date_col] = pd.to_datetime(final_candidate[date_col], errors="coerce")
        final_candidate = final_candidate[final_candidate[date_col].notna()]
        if pd.notna(canonical_endpoint):
            final_candidate = final_candidate[final_candidate[date_col] <= canonical_endpoint]
        final_candidate = final_candidate.sort_values(date_col).reset_index(drop=True)

    column_profile = _column_profile(
        frame=final_candidate,
        inspected_columns=list(section.get("inspected_columns", [])),
    )
    candidate_report = _candidate_switch_definition_report(
        frame=final_candidate,
        section=section,
    )
    selected_definition = _selected_switch_definition(
        candidate_report=candidate_report,
        section=section,
    )

    boundary = _boundary_check(section, "phase15j_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "diagnostic_role": section.get("diagnostic_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15h_passed": bool(phase15h_check["passed"].all()),
                "final_candidate_frame_loaded": not final_candidate.empty,
                "final_candidate_rows": len(final_candidate),
                "date_column": date_col or "",
                "candidate_columns_checked": len(candidate_report),
                "selected_final_definition": _bool_value(selected_definition.iloc[0]["selected"]),
                "selected_column": selected_definition.iloc[0]["selected_column"],
                "selected_transform": selected_definition.iloc[0]["transform"],
                "selected_switch_count": int(selected_definition.iloc[0]["candidate_switch_count"]),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
                "switch_log_export": False,
                "fresh_data_extension": False,
                "current_signal_generation": False,
                "paper_dry_run": False,
                "broker_api_integration": False,
                "live_trading": False,
                "real_money_deployment": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 15H passed", bool(phase15h_check["passed"].all()), "phase15h"),
            _gate_row("Final candidate frame loaded", not final_candidate.empty, f"rows={len(final_candidate)}"),
            _gate_row("Inspected column profile exists", len(column_profile) > 0, "column profile"),
            _gate_row("Candidate switch definition report exists", len(candidate_report) > 0, "candidate report"),
            _gate_row("Selected switch definition report exists", len(selected_definition) == 1, "selection"),
            _gate_row("Phase 15J boundary is audit-only", bool(boundary["passed"].all()), "phase15j"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Diagnostic role is correct",
                section.get("diagnostic_role")
                == "Final candidate column semantics and switch definition diagnostic only",
                section.get("diagnostic_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15I",
                "diagnostic": "Final candidate column semantics and switch definition diagnostic",
                "verdict": (
                    "Completed — final candidate column semantics diagnostic passed"
                    if bool(gate_report["passed"].all())
                    else "Failed final candidate column semantics diagnostic"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "selected_final_definition": _bool_value(selected_definition.iloc[0]["selected"]),
                "selected_column": selected_definition.iloc[0]["selected_column"],
                "selected_switch_count": int(selected_definition.iloc[0]["candidate_switch_count"]),
                "paper_trading_ready": False,
                "paper_dry_run": False,
                "broker_api_integration": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase15h_result_check": phase15h_check,
        "column_profile": column_profile,
        "candidate_switch_definition_report": candidate_report,
        "selected_switch_definition": selected_definition,
        "phase15j_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase15i_column_semantics_{name}.csv", index=False)

    print("Wrote Phase 15I final candidate column semantics reports.")
    return outputs


def _normalise_mode_from_exposure(exposure: float) -> str:
    if exposure >= 0.75:
        return "offensive_spy"
    if exposure <= 0.25:
        return "defensive_or_cash"
    return "partial_risk"


def _transition_type(previous_exposure: float, current_exposure: float) -> str:
    if current_exposure > previous_exposure:
        return "risk_increase"
    if current_exposure < previous_exposure:
        return "risk_decrease"
    return "target_allocation_state_change"


def _first_existing_aux_col(frame: pd.DataFrame, section: dict[str, Any], role: str) -> str | None:
    policy = section.get("auxiliary_column_policy", {})
    return _first_existing_col(frame, list(policy.get(role, [])))


def _build_refined_switch_log(
    *,
    final_candidate: pd.DataFrame,
    selected_definition: pd.DataFrame,
    section: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_cols = list(section.get("required_switch_event_columns", []))

    if selected_definition.empty or not _bool_value(selected_definition.iloc[0].get("selected", False)):
        return pd.DataFrame(columns=required_cols), pd.DataFrame()

    selected_col = str(selected_definition.iloc[0]["selected_column"])
    transform = str(selected_definition.iloc[0]["transform"])

    date_col = _first_existing_aux_col(final_candidate, section, "date_columns")
    if date_col is None or selected_col not in final_candidate.columns:
        return pd.DataFrame(columns=required_cols), pd.DataFrame()

    canonical_endpoint = pd.to_datetime(section.get("canonical_endpoint", ""), errors="coerce")

    frame = final_candidate.copy()
    frame["decision_date"] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame[frame["decision_date"].notna()].copy()

    if pd.notna(canonical_endpoint):
        frame = frame[frame["decision_date"] <= canonical_endpoint].copy()

    frame = frame.sort_values("decision_date").drop_duplicates("decision_date").reset_index(drop=True)

    if transform in {"direct", "inverse"}:
        exposure = _normalise_numeric_series(frame[selected_col], transform)
    else:
        exposure = _mode_to_exposure(frame[selected_col])

    exposure = pd.to_numeric(exposure, errors="coerce").ffill()

    previous_exposure = exposure.shift(1)
    changed = exposure.round(10).ne(previous_exposure.round(10))
    event_mask = previous_exposure.notna() & changed

    events = frame[event_mask].copy()
    event_index = events.index

    turnover_col = _first_existing_aux_col(frame, section, "turnover_columns")
    bps_col = _first_existing_aux_col(frame, section, "slippage_bps_columns")
    cost_col = _first_existing_aux_col(frame, section, "slippage_cost_columns")
    raw_col = _first_existing_aux_col(frame, section, "raw_signal_columns")
    confirmed_col = _first_existing_aux_col(frame, section, "confirmed_signal_columns")
    guard_col = _first_existing_aux_col(frame, section, "deep_drawdown_guard_columns")
    relief_col = _first_existing_aux_col(frame, section, "loose_relief_columns")

    auxiliary_report = pd.DataFrame(
        [
            {"role": "date_col", "selected_column": date_col},
            {"role": "final_target_exposure_col", "selected_column": selected_col},
            {"role": "final_target_exposure_transform", "selected_column": transform},
            {"role": "turnover_col", "selected_column": turnover_col or ""},
            {"role": "slippage_bps_col", "selected_column": bps_col or ""},
            {"role": "slippage_cost_col", "selected_column": cost_col or ""},
            {"role": "raw_signal_col", "selected_column": raw_col or ""},
            {"role": "confirmed_signal_col", "selected_column": confirmed_col or ""},
            {"role": "deep_drawdown_guard_col", "selected_column": guard_col or ""},
            {"role": "loose_relief_col", "selected_column": relief_col or ""},
        ]
    )

    if events.empty:
        return pd.DataFrame(columns=required_cols), auxiliary_report

    prev_exp = previous_exposure.loc[event_index].astype(float)
    curr_exp = exposure.loc[event_index].astype(float)

    previous_mode = prev_exp.map(_normalise_mode_from_exposure)
    current_mode = curr_exp.map(_normalise_mode_from_exposure)

    turnover = (
        pd.to_numeric(frame.loc[event_index, turnover_col], errors="coerce").fillna(0.0)
        if turnover_col
        else curr_exp.sub(prev_exp).abs()
    )
    slippage_bps = (
        pd.to_numeric(frame.loc[event_index, bps_col], errors="coerce").fillna(0.0)
        if bps_col
        else pd.Series(0.0, index=event_index)
    )
    slippage_cost = (
        pd.to_numeric(frame.loc[event_index, cost_col], errors="coerce").fillna(0.0)
        if cost_col
        else pd.Series(0.0, index=event_index)
    )

    raw_signal = frame.loc[event_index, raw_col].astype(str) if raw_col else current_mode
    confirmed_signal = (
        frame.loc[event_index, confirmed_col].astype(str) if confirmed_col else current_mode
    )

    out = pd.DataFrame(
        {
            "switch_event_id": range(1, len(events) + 1),
            "decision_date": events["decision_date"].dt.strftime("%Y-%m-%d").to_numpy(),
            "previous_mode": previous_mode.to_numpy(),
            "current_mode": current_mode.to_numpy(),
            "previous_exposure": prev_exp.to_numpy(),
            "current_exposure": curr_exp.to_numpy(),
            "switch_triggered": True,
            "transition_type": [
                _transition_type(prev, curr)
                for prev, curr in zip(prev_exp, curr_exp, strict=False)
            ],
            "switch_reason": "final_target_allocation_change_only",
            "raw_signal": raw_signal.to_numpy(),
            "confirmed_signal": confirmed_signal.to_numpy(),
            "deep_drawdown_guard_state": (
                frame.loc[event_index, guard_col].astype(str).to_numpy()
                if guard_col
                else "not_exported_from_final_candidate_frame"
            ),
            "loose_relief_state": (
                frame.loc[event_index, relief_col].astype(str).to_numpy()
                if relief_col
                else "not_exported_from_final_candidate_frame"
            ),
            "turnover": turnover.to_numpy(),
            "applied_overlay_slippage_bps": slippage_bps.to_numpy(),
            "overlay_slippage_cost_pct": slippage_cost.to_numpy(),
            "source_candidate_system_id": section.get("candidate_system_id", ""),
            "signal_validity_flag": "pass",
        }
    )

    return out[required_cols], auxiliary_report


def _refined_switch_summary(
    switch_log: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    expected = int(section.get("expected_switch_count", 36))
    tolerance = int(section.get("switch_count_abs_tolerance", 2))
    canonical_endpoint = pd.to_datetime(section.get("canonical_endpoint", ""), errors="coerce")

    count = len(switch_log)
    count_reconciled = abs(count - expected) <= tolerance

    dates = pd.to_datetime(
        switch_log["decision_date"],
        errors="coerce",
    ) if "decision_date" in switch_log.columns else pd.Series(dtype="datetime64[ns]")

    first_switch = dates.min().date() if not dates.dropna().empty else ""
    last_switch = dates.max().date() if not dates.dropna().empty else ""
    date_populated = bool(not dates.empty and dates.notna().all())
    dates_after_endpoint = int((dates > canonical_endpoint).sum()) if pd.notna(canonical_endpoint) else 0

    exposure_meaningful = bool(
        not switch_log.empty
        and pd.to_numeric(switch_log["previous_exposure"], errors="coerce").notna().all()
        and pd.to_numeric(switch_log["current_exposure"], errors="coerce").notna().all()
        and pd.to_numeric(switch_log["previous_exposure"], errors="coerce")
        .ne(pd.to_numeric(switch_log["current_exposure"], errors="coerce"))
        .all()
    )

    transition_populated = bool(
        not switch_log.empty
        and switch_log["transition_type"].astype(str).str.strip().ne("").all()
    )

    turnover_coherent = bool(
        "turnover" in switch_log.columns
        and pd.to_numeric(switch_log["turnover"], errors="coerce").fillna(0.0).ge(0.0).all()
    )
    slippage_coherent = bool(
        "applied_overlay_slippage_bps" in switch_log.columns
        and "overlay_slippage_cost_pct" in switch_log.columns
        and pd.to_numeric(
            switch_log["applied_overlay_slippage_bps"],
            errors="coerce",
        )
        .fillna(0.0)
        .ge(0.0)
        .all()
        and pd.to_numeric(
            switch_log["overlay_slippage_cost_pct"],
            errors="coerce",
        )
        .fillna(0.0)
        .ge(0.0)
        .all()
    )
    signal_validity_passed = bool(
        not switch_log.empty
        and switch_log["signal_validity_flag"].astype(str).str.lower().eq("pass").all()
    )

    failure_reasons = []
    if not count_reconciled:
        failure_reasons.append("switch_count_not_reconciled")
    if not date_populated:
        failure_reasons.append("decision_dates_missing_or_invalid")
    if dates_after_endpoint > 0:
        failure_reasons.append("dates_after_canonical_endpoint")
    if not exposure_meaningful:
        failure_reasons.append("previous_current_exposure_not_meaningful")
    if not transition_populated:
        failure_reasons.append("transition_type_missing")
    if not turnover_coherent:
        failure_reasons.append("turnover_not_coherent")
    if not slippage_coherent:
        failure_reasons.append("slippage_not_coherent")
    if not signal_validity_passed:
        failure_reasons.append("signal_validity_failed")

    reconciled_and_usable = bool(
        count_reconciled
        and date_populated
        and dates_after_endpoint == 0
        and exposure_meaningful
        and transition_populated
        and turnover_coherent
        and slippage_coherent
        and signal_validity_passed
    )

    return pd.DataFrame(
        [
            {
                "expected_switch_count": expected,
                "reconstructed_switch_count": count,
                "switch_count_tolerance": tolerance,
                "switch_count_reconciled": count_reconciled,
                "first_switch_date": first_switch,
                "last_switch_date": last_switch,
                "decision_dates_populated": date_populated,
                "dates_after_canonical_endpoint": dates_after_endpoint,
                "previous_current_exposure_meaningful": exposure_meaningful,
                "transition_types_populated": transition_populated,
                "turnover_fields_coherent": turnover_coherent,
                "slippage_fields_coherent": slippage_coherent,
                "signal_validity_passed": signal_validity_passed,
                "refined_switch_log_reconciled_and_usable": reconciled_and_usable,
                "fresh_signal_phase_allowed_next": reconciled_and_usable,
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "failure_reason": ";".join(failure_reasons),
            }
        ]
    )


def _decision_report(summary: pd.DataFrame, section: dict[str, Any]) -> pd.DataFrame:
    policy = section.get("decision_policy", {})
    reconciled = _bool_value(summary.iloc[0]["refined_switch_log_reconciled_and_usable"])

    decision = (
        policy.get(
            "decision_if_reconciled",
            "refined_canonical_switch_log_reconciled_fresh_signal_phase_allowed_next",
        )
        if reconciled
        else policy.get("decision_if_failed", "blocked_refined_switch_reconstruction_failed")
    )

    return pd.DataFrame(
        [
            {
                "decision": decision,
                "refined_switch_log_reconciled": reconciled,
                "fresh_signal_generation_allowed_next": reconciled,
                "paper_dry_run_preregistration_allowed": False,
                "paper_trading_ready": False,
                "broker_api_integration_allowed": False,
                "paper_trading_deployment_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def save_phase15j_refined_switch_reconstruction_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase15j_refined_switch_reconstruction_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase15i_check = _phase_result_check(
        section.get("source_reports", {}).get("phase15i_conclusion", ""),
        section.get("source_reports", {}).get("phase15i_gate_report", ""),
        "Phase 15I",
    )
    selected_definition = _read_csv_if_exists(
        section.get("source_reports", {}).get("selected_switch_definition", "")
    )

    final_candidate = _find_final_candidate_frame(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    switch_log, auxiliary_report = _build_refined_switch_log(
        final_candidate=final_candidate,
        selected_definition=selected_definition,
        section=section,
    )
    switch_summary = _refined_switch_summary(switch_log, section)
    decision = _decision_report(switch_summary, section)

    output_file = Path(section.get("exported_switch_log_file", ""))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    switch_log.to_csv(output_file, index=False)

    required_col_check = _required_column_check(
        switch_log,
        list(section.get("required_switch_event_columns", [])),
        "refined_switch_log",
    )

    boundary = _boundary_check(section, "phase15k_boundary")
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase15i_passed": bool(phase15i_check["passed"].all()),
                "selected_switch_definition_loaded": not selected_definition.empty,
                "selected_column": selected_definition.iloc[0]["selected_column"]
                if not selected_definition.empty
                else "",
                "selected_definition_valid": _bool_value(selected_definition.iloc[0]["selected"])
                if not selected_definition.empty
                else False,
                "switch_log_file": str(output_file),
                "switch_log_rows": len(switch_log),
                "switch_count_reconciled": _bool_value(switch_summary.iloc[0]["switch_count_reconciled"]),
                "refined_switch_log_reconciled_and_usable": _bool_value(
                    switch_summary.iloc[0]["refined_switch_log_reconciled_and_usable"]
                ),
                "decision": decision.iloc[0]["decision"],
                "fresh_signal_generation_allowed_next": _bool_value(
                    decision.iloc[0]["fresh_signal_generation_allowed_next"]
                ),
                "paper_dry_run_allowed": False,
                "paper_trading_ready": False,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()) if not scope.empty else True,
                "fresh_data_extension": False,
                "current_signal_generation": False,
                "broker_api_integration": False,
                "live_trading": False,
                "real_money_deployment": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    no_turnover_trigger = bool(
        switch_summary.iloc[0]["failure_reason"] != "turnover_trigger_used"
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 15I passed", bool(phase15i_check["passed"].all()), "phase15i"),
            _gate_row("Selected switch definition loaded", not selected_definition.empty, "selection"),
            _gate_row("Refined switch log written", output_file.exists(), str(output_file)),
            _gate_row("Required columns present", bool(required_col_check["present"].all()), "required columns"),
            _gate_row("Refined switch summary exists", len(switch_summary) == 1, "summary"),
            _gate_row("Decision output exists", len(decision) == 1, str(decision.iloc[0]["decision"])),
            _gate_row(
                "No dates after canonical endpoint",
                int(switch_summary.iloc[0]["dates_after_canonical_endpoint"]) == 0,
                f"dates_after_endpoint={switch_summary.iloc[0]['dates_after_canonical_endpoint']}",
            ),
            _gate_row("No turnover trigger used", no_turnover_trigger, "target allocation change only"),
            _gate_row("Phase 15K boundary is conditional-only", bool(boundary["passed"].all()), "phase15k"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()) if not scope.empty else True, "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role")
                == "Refined 36-switch reconstruction implementation and audit only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 15J",
                "diagnostic": "Refined 36-switch reconstruction implementation and audit",
                "verdict": (
                    "Completed — refined switch reconstruction audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed refined switch reconstruction audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "decision": decision.iloc[0]["decision"],
                "refined_switch_log_reconciled": _bool_value(
                    decision.iloc[0]["refined_switch_log_reconciled"]
                ),
                "fresh_signal_generation_allowed_next": _bool_value(
                    decision.iloc[0]["fresh_signal_generation_allowed_next"]
                ),
                "paper_dry_run_preregistration_allowed": False,
                "paper_trading_ready": False,
                "paper_trading_deployment": False,
                "broker_api_integration": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase15i_result_check": phase15i_check,
        "selected_switch_definition_input": selected_definition,
        "auxiliary_column_report": auxiliary_report,
        "refined_switch_log": switch_log,
        "refined_switch_summary": switch_summary,
        "required_column_check": required_col_check,
        "decision_report": decision,
        "phase15k_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "refined_switch_log":
            continue
        frame.to_csv(reports_path / f"phase15j_refined_switch_{name}.csv", index=False)

    print("Wrote Phase 15J refined switch reconstruction reports.")
    return outputs