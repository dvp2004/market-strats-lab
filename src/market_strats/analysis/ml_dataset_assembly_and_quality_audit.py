from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_PHASE13M_CONFIG: dict[str, Any] = {
    "enabled": False,
    "execution_role": "ML dataset assembly execution with macro availability guard only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13L",
    "proposed_next_phase": "Phase 13N",
    "allow_dataset_assembly_execution": True,
    "allow_target_calculation": True,
    "allow_macro_availability_repair": True,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_model_selection": False,
    "allow_feature_importance": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "input_data": {},
    "macro_availability_guard": {},
    "dataset_policy": {},
    "phase13n_boundary": {},
    "gates": {
        "require_phase13l_passed": True,
        "require_source_reports_present": True,
        "require_feature_panel_loaded": True,
        "require_price_source_found": True,
        "require_macro_guard_report": True,
        "require_macro_repaired_or_blocked": True,
        "require_dataset_created": True,
        "require_dataset_honest_label": True,
        "require_targets_calculated": True,
        "require_split_labels_created": True,
        "require_no_leakage_flags": True,
        "require_phase13n_boundary_quality_audit_only": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_feature_importance": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_execution_role": (
            "ML dataset assembly execution with macro availability guard only"
        ),
    },
}


DEFAULT_PHASE13N_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "ML dataset quality and leakage audit only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13M",
    "proposed_next_phase": "Phase 13O",
    "allow_model_training": False,
    "allow_model_selection": False,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_feature_importance": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "phase13m_reports": {},
    "quality_thresholds": {
        "min_dataset_rows": 100,
        "min_feature_value_columns": 4,
        "min_target_available_ratio": 0.80,
        "require_train_validation_holdout_rows": True,
        "max_leakage_flags": 0,
        "forbidden_columns": [],
    },
    "phase13o_boundary": {},
    "gates": {
        "require_phase13m_reports_present": True,
        "require_phase13m_conclusion_passed": True,
        "require_phase13m_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_dataset_quality": True,
        "require_target_quality": True,
        "require_split_quality": True,
        "require_macro_guard_quality": True,
        "require_honest_dataset_label": True,
        "require_no_forbidden_columns": True,
        "require_no_leakage_flags": True,
        "require_phase13o_boundary_prereg_only": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_feature_importance": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_audit_role": "ML dataset quality and leakage audit only",
    },
}


FEATURE_PANEL_FORBIDDEN_FRAGMENTS = [
    "signal",
    "trade_signal",
    "allocation",
    "target_weight",
    "model_prediction",
    "predicted_return",
    "strategy_return",
    "backtest_return",
    "paper_trade",
    "feature_importance",
]


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


def _get_phase13m_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13M_CONFIG,
        config.get("phase13m_ml_dataset_assembly_execution", {}),
    )


def _get_phase13n_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13N_CONFIG,
        config.get("phase13n_ml_dataset_quality_leakage_audit", {}),
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


def _normalise_date_column(frame: pd.DataFrame, candidates: list[str]) -> pd.DataFrame:
    out = frame.copy()
    date_col = next((col for col in candidates if col in out.columns), None)

    if date_col is None:
        date_like = [col for col in out.columns if "date" in str(col).lower()]
        date_col = date_like[0] if date_like else out.columns[0]

    out = out.rename(columns={date_col: "as_of_date"})
    out["as_of_date"] = pd.to_datetime(out["as_of_date"], errors="coerce")
    out = out.dropna(subset=["as_of_date"])
    out = out.sort_values("as_of_date").drop_duplicates("as_of_date")
    return out.reset_index(drop=True)


def _find_close_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in frame.columns:
            return str(col)

    numeric_cols = [
        col for col in frame.columns if pd.api.types.is_numeric_dtype(frame[col])
    ]
    return str(numeric_cols[0]) if numeric_cols else None


def _load_first_existing_csv(paths: list[str]) -> tuple[pd.DataFrame, str]:
    for path in paths:
        frame = _read_csv_if_exists(path)
        if not frame.empty:
            return frame, path
    return pd.DataFrame(), ""


def _extract_dataframes(value: Any) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []

    if isinstance(value, pd.DataFrame):
        return [value]

    if isinstance(value, dict):
        for item in value.values():
            frames.extend(_extract_dataframes(item))

    if isinstance(value, (list, tuple)):
        for item in value:
            frames.extend(_extract_dataframes(item))

    return frames


def _load_price_frame(
    *,
    phase_config: dict[str, Any],
    relative_momentum_outputs: Any | None,
    ticker_outputs: Any | None,
) -> tuple[pd.DataFrame, str]:
    input_config = phase_config.get("input_data", {})
    date_candidates = _as_list(input_config.get("date_column_candidates"))
    close_candidates = _as_list(input_config.get("close_column_candidates"))

    for frame in _extract_dataframes(ticker_outputs) + _extract_dataframes(
        relative_momentum_outputs
    ):
        if frame.empty:
            continue

        candidate = _normalise_date_column(frame, date_candidates)
        close_col = _find_close_column(candidate, close_candidates)

        if close_col is None:
            continue

        out = candidate[["as_of_date", close_col]].copy()
        out = out.rename(columns={close_col: "adjusted_close"})
        out["adjusted_close"] = pd.to_numeric(
            out["adjusted_close"],
            errors="coerce",
        )
        out = out.dropna(subset=["adjusted_close"])

        if not out.empty:
            return out.reset_index(drop=True), "in_memory_run_backtest_outputs"

    paths = [str(path) for path in _as_list(input_config.get("technical_price_candidates"))]
    frame, source_path = _load_first_existing_csv(paths)

    if frame.empty:
        return pd.DataFrame(), ""

    out = _normalise_date_column(frame, date_candidates)
    close_col = _find_close_column(out, close_candidates)

    if close_col is None:
        return pd.DataFrame(), source_path

    out = out[["as_of_date", close_col]].copy()
    out = out.rename(columns={close_col: "adjusted_close"})
    out["adjusted_close"] = pd.to_numeric(out["adjusted_close"], errors="coerce")
    out = out.dropna(subset=["adjusted_close"])
    return out.reset_index(drop=True), source_path


def _find_alias_column(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    exact_lookup = {str(col).lower(): str(col) for col in frame.columns}

    for alias in aliases:
        if str(alias).lower() in exact_lookup:
            return exact_lookup[str(alias).lower()]

    for col in frame.columns:
        col_lower = str(col).lower()
        for alias in aliases:
            if str(alias).lower() in col_lower:
                return str(col)

    return None


def _load_macro_frame(phase_config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    input_config = phase_config.get("input_data", {})
    date_candidates = _as_list(input_config.get("date_column_candidates"))
    paths = [str(path) for path in _as_list(input_config.get("macro_aligned_candidates"))]
    frame, source_path = _load_first_existing_csv(paths)

    if frame.empty:
        return pd.DataFrame(), ""

    out = _normalise_date_column(frame, date_candidates)
    aliases = input_config.get("macro_column_aliases", {})

    required_map = {
        "DGS2": _as_list(aliases.get("DGS2", ["DGS2"])),
        "DGS10": _as_list(aliases.get("DGS10", ["DGS10"])),
        "CPIAUCSL": _as_list(aliases.get("CPIAUCSL", ["CPIAUCSL"])),
        "UNRATE": _as_list(aliases.get("UNRATE", ["UNRATE"])),
    }

    repaired = pd.DataFrame({"as_of_date": out["as_of_date"]})

    for canonical, alias_list in required_map.items():
        col = _find_alias_column(out, alias_list)
        repaired[canonical] = pd.to_numeric(out[col], errors="coerce") if col else np.nan

    return repaired.reset_index(drop=True), source_path


def build_phase13m_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase13m_phase13l_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13l_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13l_gate_report", ""))

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

    out = pd.DataFrame(
        [
            {
                "check": "Phase 13L conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13L gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13m_input_source_check(
    *,
    feature_panel: pd.DataFrame,
    price_frame: pd.DataFrame,
    price_source: str,
    macro_frame: pd.DataFrame,
    macro_source: str,
) -> pd.DataFrame:
    rows = [
        {
            "source_type": "feature_panel",
            "source": "reports/phase13i_feature_panel.csv",
            "found": not feature_panel.empty,
            "rows": int(len(feature_panel)),
        },
        {
            "source_type": "price",
            "source": price_source,
            "found": not price_frame.empty,
            "rows": int(len(price_frame)),
        },
        {
            "source_type": "macro_aligned",
            "source": macro_source,
            "found": not macro_frame.empty,
            "rows": int(len(macro_frame)),
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["found"].map({True: "Passed", False: "Failed"})
    return out


def _feature_availability_ratio(
    frame: pd.DataFrame,
    *,
    family_id: str,
) -> float:
    if frame.empty or "family_id" not in frame.columns:
        return 0.0

    family = frame[frame["family_id"].astype(str).eq(family_id)].copy()

    if family.empty or "missingness_state" not in family.columns:
        return 0.0

    return float(family["missingness_state"].astype(str).eq("available").mean())


def _next_business_day(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series) + pd.offsets.BDay(1)


def _macro_feature_rows(
    *,
    frame: pd.DataFrame,
    feature_id: str,
    formula_id: str,
    value_col: str,
    state: pd.Series,
    reason: pd.Series,
    source_name: str,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "as_of_date": frame["as_of_date"],
            "observation_date": frame["as_of_date"],
            "release_date": pd.NaT,
            "availability_date": frame["as_of_date"],
            "decision_date": _next_business_day(frame["as_of_date"]),
            "family_id": "macro",
            "feature_id": feature_id,
            "formula_id": formula_id,
            "source_name": source_name,
            "source_version": "phase13m_macro_guard_repair",
            "raw_inputs_available": frame[value_col].notna(),
            "feature_value": frame[value_col],
            "feature_state": state,
            "state_reason": reason,
            "missingness_state": np.where(
                frame[value_col].notna(),
                "available",
                "unavailable",
            ),
            "leakage_flag": False,
            "contract_version": "phase13g_v1_phase13m_repair",
        }
    )


def _state_simple(
    value: pd.Series,
    supportive_mask: pd.Series,
    neutral_mask: pd.Series,
    missing_reason: str,
) -> tuple[pd.Series, pd.Series]:
    state = pd.Series("fragile", index=value.index, dtype="object")
    state.loc[neutral_mask] = "neutral"
    state.loc[supportive_mask] = "supportive"
    state.loc[value.isna()] = "unavailable"

    reason = pd.Series("value breached fragile threshold", index=value.index, dtype="object")
    reason.loc[neutral_mask] = "value fell inside neutral threshold"
    reason.loc[supportive_mask] = "value passed supportive threshold"
    reason.loc[value.isna()] = missing_reason
    return state, reason


def build_phase13m_macro_repair_panel(
    *,
    macro_frame: pd.DataFrame,
    macro_source: str,
) -> pd.DataFrame:
    if macro_frame.empty:
        return pd.DataFrame()

    frame = macro_frame.copy().sort_values("as_of_date").reset_index(drop=True)
    frame["macro_dgs2_level"] = pd.to_numeric(frame["DGS2"], errors="coerce")
    frame["macro_dgs10_minus_dgs2"] = (
        pd.to_numeric(frame["DGS10"], errors="coerce")
        - pd.to_numeric(frame["DGS2"], errors="coerce")
    )
    frame["macro_cpi_yoy"] = (
        pd.to_numeric(frame["CPIAUCSL"], errors="coerce")
        / pd.to_numeric(frame["CPIAUCSL"], errors="coerce").shift(252)
        - 1
    )
    frame["macro_unrate_3m_change"] = (
        pd.to_numeric(frame["UNRATE"], errors="coerce")
        - pd.to_numeric(frame["UNRATE"], errors="coerce").shift(63)
    )

    rows = []

    state, reason = _state_simple(
        frame["macro_dgs2_level"],
        frame["macro_dgs2_level"] < 2.50,
        frame["macro_dgs2_level"].between(2.50, 4.50),
        "DGS2 unavailable after macro guard repair",
    )
    rows.append(
        _macro_feature_rows(
            frame=frame,
            feature_id="macro_short_rate_state",
            formula_id="dgs2_level_regime",
            value_col="macro_dgs2_level",
            state=state,
            reason=reason,
            source_name=macro_source,
        )
    )

    state, reason = _state_simple(
        frame["macro_dgs10_minus_dgs2"],
        frame["macro_dgs10_minus_dgs2"] > 0.50,
        frame["macro_dgs10_minus_dgs2"].between(-0.50, 0.50),
        "DGS10 or DGS2 unavailable after macro guard repair",
    )
    rows.append(
        _macro_feature_rows(
            frame=frame,
            feature_id="macro_yield_curve_state",
            formula_id="dgs10_minus_dgs2_curve_regime",
            value_col="macro_dgs10_minus_dgs2",
            state=state,
            reason=reason,
            source_name=macro_source,
        )
    )

    state, reason = _state_simple(
        frame["macro_cpi_yoy"],
        frame["macro_cpi_yoy"] < 0.03,
        frame["macro_cpi_yoy"].between(0.03, 0.05),
        "CPI current or 12-month comparison unavailable after macro guard repair",
    )
    rows.append(
        _macro_feature_rows(
            frame=frame,
            feature_id="macro_inflation_state",
            formula_id="cpi_yoy_inflation_regime",
            value_col="macro_cpi_yoy",
            state=state,
            reason=reason,
            source_name=macro_source,
        )
    )

    labour_state = pd.Series("neutral", index=frame.index, dtype="object")
    labour_reason = pd.Series("labour state inside neutral band", index=frame.index)
    unrate = pd.to_numeric(frame["UNRATE"], errors="coerce")
    change = frame["macro_unrate_3m_change"]

    supportive = (unrate < 5.00) & (change <= 0.00)
    fragile = (unrate >= 6.00) | (change > 0.50)
    unavailable = unrate.isna() | change.isna()

    labour_state.loc[supportive] = "supportive"
    labour_state.loc[fragile] = "fragile"
    labour_state.loc[unavailable] = "unavailable"
    labour_reason.loc[supportive] = "low and non-rising unemployment"
    labour_reason.loc[fragile] = "high or quickly rising unemployment"
    labour_reason.loc[unavailable] = (
        "UNRATE current or 3-month comparison unavailable after macro guard repair"
    )

    rows.append(
        _macro_feature_rows(
            frame=frame,
            feature_id="macro_labour_state",
            formula_id="unrate_level_and_3m_change_regime",
            value_col="macro_unrate_3m_change",
            state=labour_state,
            reason=labour_reason,
            source_name=macro_source,
        )
    )

    out = pd.concat(rows, ignore_index=True)
    date_cols = [
        "as_of_date",
        "observation_date",
        "release_date",
        "availability_date",
        "decision_date",
    ]

    for col in date_cols:
        out[col] = pd.to_datetime(out[col], errors="coerce").dt.date

    return out


def build_phase13m_macro_guard_report(
    *,
    feature_panel: pd.DataFrame,
    macro_repair_panel: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    guard = phase_config.get("macro_availability_guard", {})
    threshold = float(guard.get("min_macro_available_ratio_to_use", 0.20))

    current_ratio = _feature_availability_ratio(feature_panel, family_id="macro")
    repaired_ratio = _feature_availability_ratio(macro_repair_panel, family_id="macro")

    repair_attempted = bool(guard.get("repair_attempt_required", True))
    repaired_successfully = repaired_ratio >= threshold
    macro_blocked = not repaired_successfully

    dataset_label = (
        str(guard.get("dataset_label_if_repaired", "multi_factor_dataset_v1"))
        if repaired_successfully
        else str(guard.get("dataset_label_if_blocked", "technical_only_macro_blocked_dataset_v1"))
    )

    return pd.DataFrame(
        [
            {
                "current_macro_available_ratio": current_ratio,
                "repair_attempted": repair_attempted,
                "repaired_macro_available_ratio": repaired_ratio,
                "min_macro_available_ratio_to_use": threshold,
                "repaired_successfully": repaired_successfully,
                "macro_blocked_for_dataset_v1": macro_blocked,
                "dataset_label": dataset_label,
                "macro_guard_result": "repaired" if repaired_successfully else "blocked",
                "interpretation": (
                    "Macro features repaired and allowed for dataset_v1."
                    if repaired_successfully
                    else str(
                        guard.get(
                            "macro_block_reason_if_unrepaired",
                            "Macro unavailable and blocked.",
                        )
                    )
                ),
            }
        ]
    )


def build_phase13m_repaired_or_blocked_feature_panel(
    *,
    feature_panel: pd.DataFrame,
    macro_repair_panel: pd.DataFrame,
    macro_guard_report: pd.DataFrame,
) -> pd.DataFrame:
    if feature_panel.empty or macro_guard_report.empty:
        return feature_panel.copy()

    repaired = _bool_value(macro_guard_report.iloc[0]["repaired_successfully"])
    technical = feature_panel[feature_panel["family_id"].astype(str).eq("technical")]

    if repaired:
        return pd.concat([technical, macro_repair_panel], ignore_index=True)

    return technical.copy().reset_index(drop=True)


def _wide_feature_dataset(feature_panel: pd.DataFrame) -> pd.DataFrame:
    frame = feature_panel.copy()
    frame["decision_date"] = pd.to_datetime(frame["decision_date"], errors="coerce")
    frame = frame.dropna(subset=["decision_date", "feature_id"])

    value = frame.pivot_table(
        index="decision_date",
        columns="feature_id",
        values="feature_value",
        aggfunc="first",
    )
    value.columns = [f"value__{col}" for col in value.columns]

    state = frame.pivot_table(
        index="decision_date",
        columns="feature_id",
        values="feature_state",
        aggfunc="first",
    )
    state.columns = [f"state__{col}" for col in state.columns]

    missingness = frame.pivot_table(
        index="decision_date",
        columns="feature_id",
        values="missingness_state",
        aggfunc="first",
    )
    missingness.columns = [f"missingness__{col}" for col in missingness.columns]

    wide = pd.concat([value, state, missingness], axis=1).reset_index()
    return wide


def _future_window_max_drawdown(close_values: np.ndarray, horizon: int) -> np.ndarray:
    out = np.full(len(close_values), np.nan)

    for idx in range(len(close_values)):
        window = close_values[idx : idx + horizon + 1]

        if len(window) < horizon + 1:
            continue

        running_max = np.maximum.accumulate(window)
        drawdowns = window / running_max - 1.0
        out[idx] = float(np.min(drawdowns))

    return out


def build_phase13m_target_frame(
    *,
    price_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    policy = phase_config.get("dataset_policy", {})
    horizon = int(policy.get("target_horizon_trading_days", 63))

    if price_frame.empty:
        return pd.DataFrame()

    frame = price_frame.copy().sort_values("as_of_date")
    frame["decision_date"] = pd.to_datetime(frame["as_of_date"], errors="coerce")
    frame["adjusted_close"] = pd.to_numeric(frame["adjusted_close"], errors="coerce")
    frame = frame.dropna(subset=["decision_date", "adjusted_close"])

    frame["future_return_63d"] = (
        frame["adjusted_close"].shift(-horizon) / frame["adjusted_close"] - 1.0
    )
    frame["future_63d_spy_return_state"] = np.select(
        [
            frame["future_return_63d"] > float(policy.get("primary_supportive_threshold", 0.05)),
            frame["future_return_63d"] < float(policy.get("primary_fragile_threshold", -0.05)),
        ],
        ["supportive", "fragile"],
        default="neutral",
    )
    frame.loc[frame["future_return_63d"].isna(), "future_63d_spy_return_state"] = (
        "unavailable"
    )

    frame["future_window_max_drawdown_63d"] = _future_window_max_drawdown(
        frame["adjusted_close"].to_numpy(dtype=float),
        horizon,
    )
    frame["future_63d_drawdown_risk_state"] = np.where(
        frame["future_window_max_drawdown_63d"]
        <= float(policy.get("secondary_fragile_drawdown_threshold", -0.10)),
        "fragile",
        "neutral",
    )
    frame.loc[
        frame["future_window_max_drawdown_63d"].isna(),
        "future_63d_drawdown_risk_state",
    ] = "unavailable"

    frame["target_available"] = frame["future_return_63d"].notna()

    return frame[
        [
            "decision_date",
            "future_return_63d",
            "future_63d_spy_return_state",
            "future_window_max_drawdown_63d",
            "future_63d_drawdown_risk_state",
            "target_available",
        ]
    ].reset_index(drop=True)


def _assign_split_label(dates: pd.Series, policy: dict[str, Any]) -> pd.Series:
    parsed = pd.to_datetime(dates, errors="coerce")
    labels = pd.Series("out_of_split", index=parsed.index, dtype="object")

    train = parsed.between(
        pd.Timestamp(policy.get("train_start", "1900-01-01")),
        pd.Timestamp(policy.get("train_end", "1900-01-01")),
    )
    validation = parsed.between(
        pd.Timestamp(policy.get("validation_start", "1900-01-01")),
        pd.Timestamp(policy.get("validation_end", "1900-01-01")),
    )
    holdout = parsed.between(
        pd.Timestamp(policy.get("holdout_start", "1900-01-01")),
        pd.Timestamp(policy.get("holdout_end", "1900-01-01")),
    )

    labels.loc[train] = "train"
    labels.loc[validation] = "validation"
    labels.loc[holdout] = "holdout"
    return labels


def build_phase13m_assembled_dataset(
    *,
    usable_feature_panel: pd.DataFrame,
    target_frame: pd.DataFrame,
    macro_guard_report: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    policy = phase_config.get("dataset_policy", {})

    wide = _wide_feature_dataset(usable_feature_panel)

    if wide.empty or target_frame.empty:
        return pd.DataFrame()

    dataset = wide.merge(target_frame, on="decision_date", how="left")
    dataset["split_label"] = _assign_split_label(dataset["decision_date"], policy)

    start = pd.Timestamp(policy.get("common_start_date", "1900-01-01"))
    end = pd.Timestamp(policy.get("canonical_endpoint", "2100-01-01"))
    dataset = dataset[
        pd.to_datetime(dataset["decision_date"]).between(start, end)
    ].copy()

    dataset["dataset_id"] = str(policy.get("dataset_id", "phase13m_dataset"))
    dataset["dataset_label"] = str(macro_guard_report.iloc[0]["dataset_label"])
    dataset["macro_blocked_for_dataset_v1"] = _bool_value(
        macro_guard_report.iloc[0]["macro_blocked_for_dataset_v1"]
    )
    dataset["macro_guard_result"] = str(macro_guard_report.iloc[0]["macro_guard_result"])

    first_cols = [
        "dataset_id",
        "dataset_label",
        "macro_blocked_for_dataset_v1",
        "macro_guard_result",
        "decision_date",
        "split_label",
        "future_return_63d",
        "future_63d_spy_return_state",
        "future_window_max_drawdown_63d",
        "future_63d_drawdown_risk_state",
        "target_available",
    ]
    remaining = [col for col in dataset.columns if col not in first_cols]
    return dataset[first_cols + remaining].reset_index(drop=True)


def build_phase13m_family_usage_report(
    *,
    usable_feature_panel: pd.DataFrame,
    macro_guard_report: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    if usable_feature_panel.empty:
        return pd.DataFrame()

    for family_id, group in usable_feature_panel.groupby("family_id"):
        rows.append(
            {
                "family_id": family_id,
                "used_in_dataset_v1": True,
                "rows": int(len(group)),
                "feature_count": int(group["feature_id"].nunique()),
                "available_ratio": float(
                    group["missingness_state"].astype(str).eq("available").mean()
                ),
            }
        )

    if _bool_value(macro_guard_report.iloc[0]["macro_blocked_for_dataset_v1"]):
        rows.append(
            {
                "family_id": "macro",
                "used_in_dataset_v1": False,
                "rows": 0,
                "feature_count": 0,
                "available_ratio": float(
                    macro_guard_report.iloc[0]["repaired_macro_available_ratio"]
                ),
            }
        )

    return pd.DataFrame(rows).drop_duplicates(
        subset=["family_id", "used_in_dataset_v1"],
        keep="first",
    )


def build_phase13m_target_summary(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame()

    return pd.DataFrame(
        [
            {
                "rows": int(len(dataset)),
                "target_available_rows": int(dataset["target_available"].sum()),
                "target_available_ratio": float(dataset["target_available"].mean()),
                "primary_target_classes": "; ".join(
                    sorted(dataset["future_63d_spy_return_state"].dropna().unique())
                ),
                "secondary_target_classes": "; ".join(
                    sorted(dataset["future_63d_drawdown_risk_state"].dropna().unique())
                ),
            }
        ]
    )


def build_phase13m_split_summary(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame()

    out = (
        dataset.groupby("split_label")
        .agg(
            rows=("split_label", "size"),
            target_available_rows=("target_available", "sum"),
            first_decision_date=("decision_date", "min"),
            last_decision_date=("decision_date", "max"),
        )
        .reset_index()
    )
    out["target_available_ratio"] = out["target_available_rows"] / out["rows"]
    return out


def build_phase13m_dataset_metadata(
    *,
    dataset: pd.DataFrame,
    macro_guard_report: pd.DataFrame,
) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame()

    value_columns = [col for col in dataset.columns if col.startswith("value__")]
    state_columns = [col for col in dataset.columns if col.startswith("state__")]
    missingness_columns = [
        col for col in dataset.columns if col.startswith("missingness__")
    ]

    return pd.DataFrame(
        [
            {
                "dataset_id": str(dataset["dataset_id"].iloc[0]),
                "dataset_label": str(dataset["dataset_label"].iloc[0]),
                "rows": int(len(dataset)),
                "value_feature_columns": int(len(value_columns)),
                "state_feature_columns": int(len(state_columns)),
                "missingness_feature_columns": int(len(missingness_columns)),
                "macro_guard_result": str(macro_guard_report.iloc[0]["macro_guard_result"]),
                "macro_blocked_for_dataset_v1": _bool_value(
                    macro_guard_report.iloc[0]["macro_blocked_for_dataset_v1"]
                ),
                "model_training": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )


def build_phase13m_phase13n_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13n_boundary", {})

    checks = [
        (
            "phase13n_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "quality" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13n_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "model training" in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation" in str(boundary.get("forbidden_next_step", "")).lower()
            and "strategy backtest" in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13n_may_audit_dataset",
            _bool_value(boundary.get("phase13n_may_audit_dataset", False)),
            _bool_value(boundary.get("phase13n_may_audit_dataset", False)),
        ),
        (
            "phase13n_may_audit_macro_guard",
            _bool_value(boundary.get("phase13n_may_audit_macro_guard", False)),
            _bool_value(boundary.get("phase13n_may_audit_macro_guard", False)),
        ),
        (
            "phase13n_may_train_model",
            _bool_value(boundary.get("phase13n_may_train_model", True)),
            not _bool_value(boundary.get("phase13n_may_train_model", True)),
        ),
        (
            "phase13n_may_select_model",
            _bool_value(boundary.get("phase13n_may_select_model", True)),
            not _bool_value(boundary.get("phase13n_may_select_model", True)),
        ),
        (
            "phase13n_may_create_signal",
            _bool_value(boundary.get("phase13n_may_create_signal", True)),
            not _bool_value(boundary.get("phase13n_may_create_signal", True)),
        ),
        (
            "phase13n_may_run_backtest",
            _bool_value(boundary.get("phase13n_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13n_may_run_backtest", True)),
        ),
        (
            "phase13n_may_promote_candidate",
            _bool_value(boundary.get("phase13n_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13n_may_promote_candidate", True)),
        ),
    ]
    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
        ("No model training", "allow_model_training"),
        ("No model selection", "allow_model_selection"),
        ("No feature importance", "allow_feature_importance"),
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


def build_phase13m_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13l_result_check: pd.DataFrame,
    input_source_check: pd.DataFrame,
    macro_guard_report: pd.DataFrame,
    dataset: pd.DataFrame,
    target_summary: pd.DataFrame,
    split_summary: pd.DataFrame,
    phase13n_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    leakage_count = 0
    if "leakage_flag" in dataset.columns:
        leakage_count = int(dataset["leakage_flag"].map(_bool_value).sum())

    return pd.DataFrame(
        [
            {
                "execution_role": str(phase_config.get("execution_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "source_reports_present": bool(source_report_check["present"].all())
                if not source_report_check.empty
                else False,
                "phase13l_result_passed": bool(phase13l_result_check["passed"].all())
                if not phase13l_result_check.empty
                else False,
                "input_sources_found": bool(input_source_check["found"].all())
                if not input_source_check.empty
                else False,
                "macro_guard_rows": int(len(macro_guard_report)),
                "macro_repaired": _bool_value(
                    macro_guard_report.iloc[0]["repaired_successfully"]
                )
                if not macro_guard_report.empty
                else False,
                "macro_blocked": _bool_value(
                    macro_guard_report.iloc[0]["macro_blocked_for_dataset_v1"]
                )
                if not macro_guard_report.empty
                else False,
                "dataset_label": str(macro_guard_report.iloc[0]["dataset_label"])
                if not macro_guard_report.empty
                else "",
                "dataset_rows": int(len(dataset)),
                "target_summary_rows": int(len(target_summary)),
                "split_summary_rows": int(len(split_summary)),
                "leakage_flag_count": leakage_count,
                "phase13n_boundary_passed": bool(
                    phase13n_boundary_check["passed"].all()
                )
                if not phase13n_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "model_training": False,
                "model_selection": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def _dataset_label_is_honest(summary_row: pd.Series) -> bool:
    label = str(summary_row["dataset_label"]).lower()
    macro_blocked = _bool_value(summary_row["macro_blocked"])
    macro_repaired = _bool_value(summary_row["macro_repaired"])

    if macro_blocked:
        return "technical_only" in label and "macro_blocked" in label

    if macro_repaired:
        return "multi_factor" in label or "technical_macro" in label

    return False


def build_phase13m_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13M summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_execution_role",
            "ML dataset assembly execution with macro availability guard only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13L passed",
            (not gates.get("require_phase13l_passed", True))
            or bool(row["phase13l_result_passed"]),
            f"phase13l_result_passed={bool(row['phase13l_result_passed'])}",
        ),
        _gate_row(
            "Source reports are present",
            (not gates.get("require_source_reports_present", True))
            or bool(row["source_reports_present"]),
            f"source_reports_present={bool(row['source_reports_present'])}",
        ),
        _gate_row(
            "Input sources were found",
            bool(row["input_sources_found"]),
            f"input_sources_found={bool(row['input_sources_found'])}",
        ),
        _gate_row(
            "Macro guard report exists",
            (not gates.get("require_macro_guard_report", True))
            or int(row["macro_guard_rows"]) > 0,
            f"macro_guard_rows={int(row['macro_guard_rows'])}",
        ),
        _gate_row(
            "Macro was repaired or explicitly blocked",
            (not gates.get("require_macro_repaired_or_blocked", True))
            or bool(row["macro_repaired"])
            or bool(row["macro_blocked"]),
            f"macro_repaired={bool(row['macro_repaired'])}; "
            f"macro_blocked={bool(row['macro_blocked'])}",
        ),
        _gate_row(
            "Dataset was created",
            (not gates.get("require_dataset_created", True))
            or int(row["dataset_rows"]) > 0,
            f"dataset_rows={int(row['dataset_rows'])}",
        ),
        _gate_row(
            "Dataset label is honest",
            (not gates.get("require_dataset_honest_label", True))
            or _dataset_label_is_honest(row),
            f"dataset_label={row['dataset_label']}",
        ),
        _gate_row(
            "Targets were calculated",
            (not gates.get("require_targets_calculated", True))
            or int(row["target_summary_rows"]) > 0,
            f"target_summary_rows={int(row['target_summary_rows'])}",
        ),
        _gate_row(
            "Split labels were created",
            (not gates.get("require_split_labels_created", True))
            or int(row["split_summary_rows"]) >= 3,
            f"split_summary_rows={int(row['split_summary_rows'])}",
        ),
        _gate_row(
            "No leakage flags are present",
            (not gates.get("require_no_leakage_flags", True))
            or int(row["leakage_flag_count"]) == 0,
            f"leakage_flag_count={int(row['leakage_flag_count'])}",
        ),
        _gate_row(
            "Phase 13N boundary is quality-audit-only",
            (not gates.get("require_phase13n_boundary_quality_audit_only", True))
            or bool(row["phase13n_boundary_passed"]),
            f"phase13n_boundary_passed={bool(row['phase13n_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks model/signal/backtest/paper-trading/promotion",
            bool(row["scope_boundary_passed"]),
            f"scope_boundary_passed={bool(row['scope_boundary_passed'])}",
        ),
        _gate_row(
            "Execution role is correct",
            str(row["execution_role"]) == required_role,
            f"execution_role={row['execution_role']}",
        ),
    ]
    out = pd.DataFrame(rows)
    out["all_gates_passed"] = bool(out["passed"].all())
    return out


def build_phase13m_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — ML dataset assembly with macro availability guard passed"
        if all_passed
        else "Failed ML dataset assembly with macro availability guard"
    )
    interpretation = (
        "Phase 13M assembled an ML dataset and calculated registered 63D targets "
        "only after applying a macro availability guard. If macro repair failed, "
        "the dataset was labelled technical-only/macro-blocked rather than "
        "multi-factor. It did not train models, select models, create signals, run "
        "backtests, deploy paper trading, promote a candidate, or change the final "
        "candidate."
        if all_passed
        else "Phase 13M found a source, macro guard, target, split, label, leakage, "
        "boundary, or scope issue."
    )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 13M",
                "diagnostic": "ML dataset assembly with macro availability guard",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def _write_markdown(
    *,
    title: str,
    sections: dict[str, pd.DataFrame],
    output_path: Path,
) -> None:
    lines = [f"# {title}", ""]

    for heading, frame in sections.items():
        lines.extend([f"## {heading}", frame.to_markdown(index=False), ""])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase13m_ml_dataset_assembly_execution(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: Any | None = None,
    ticker_outputs: Any | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13m_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13m_source_report_check(phase_config)
    phase13l_result_check = build_phase13m_phase13l_result_check(phase_config)

    source_reports = phase_config.get("source_reports", {})
    feature_panel = _read_csv_if_exists(source_reports.get("feature_panel", ""))

    price_frame, price_source = _load_price_frame(
        phase_config=phase_config,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
    )
    macro_frame, macro_source = _load_macro_frame(phase_config)

    input_source_check = build_phase13m_input_source_check(
        feature_panel=feature_panel,
        price_frame=price_frame,
        price_source=price_source,
        macro_frame=macro_frame,
        macro_source=macro_source,
    )

    macro_repair_panel = build_phase13m_macro_repair_panel(
        macro_frame=macro_frame,
        macro_source=macro_source,
    )
    macro_guard_report = build_phase13m_macro_guard_report(
        feature_panel=feature_panel,
        macro_repair_panel=macro_repair_panel,
        phase_config=phase_config,
    )
    usable_feature_panel = build_phase13m_repaired_or_blocked_feature_panel(
        feature_panel=feature_panel,
        macro_repair_panel=macro_repair_panel,
        macro_guard_report=macro_guard_report,
    )
    target_frame = build_phase13m_target_frame(
        price_frame=price_frame,
        phase_config=phase_config,
    )
    dataset = build_phase13m_assembled_dataset(
        usable_feature_panel=usable_feature_panel,
        target_frame=target_frame,
        macro_guard_report=macro_guard_report,
        phase_config=phase_config,
    )
    family_usage_report = build_phase13m_family_usage_report(
        usable_feature_panel=usable_feature_panel,
        macro_guard_report=macro_guard_report,
    )
    target_summary = build_phase13m_target_summary(dataset)
    split_summary = build_phase13m_split_summary(dataset)
    dataset_metadata = build_phase13m_dataset_metadata(
        dataset=dataset,
        macro_guard_report=macro_guard_report,
    )
    phase13n_boundary_check = build_phase13m_phase13n_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13m_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13l_result_check=phase13l_result_check,
        input_source_check=input_source_check,
        macro_guard_report=macro_guard_report,
        dataset=dataset,
        target_summary=target_summary,
        split_summary=split_summary,
        phase13n_boundary_check=phase13n_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13m_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13m_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13l_result_check": phase13l_result_check,
        "input_source_check": input_source_check,
        "macro_guard_report": macro_guard_report,
        "macro_repair_panel": macro_repair_panel,
        "family_usage_report": family_usage_report,
        "target_summary": target_summary,
        "split_summary": split_summary,
        "dataset_metadata": dataset_metadata,
        "phase13n_boundary_check": phase13n_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13m_dataset_{name}.csv", index=False)

    dataset.to_csv(reports_path / "phase13m_ml_feature_dataset_v1.csv", index=False)

    _write_markdown(
        title="Phase 13M — ML Dataset Assembly with Macro Availability Guard",
        sections={
            "Input Source Check": input_source_check,
            "Macro Guard Report": macro_guard_report,
            "Family Usage Report": family_usage_report,
            "Target Summary": target_summary,
            "Split Summary": split_summary,
            "Dataset Metadata": dataset_metadata,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13m_ml_dataset_assembly_macro_guard.md",
    )

    print("Wrote Phase 13M ML dataset assembly reports.")
    return {**outputs, "assembled_dataset": dataset}


def build_phase13n_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("phase13m_reports", {}).items():
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


def build_phase13n_phase13m_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase13m_reports", {})
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

    out = pd.DataFrame(
        [
            {
                "check": "Phase 13M conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13M gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13n_config_flag_check(
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


def build_phase13n_dataset_quality_check(
    *,
    dataset: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    min_rows = int(thresholds.get("min_dataset_rows", 100))
    min_feature_cols = int(thresholds.get("min_feature_value_columns", 4))
    value_cols = [col for col in dataset.columns if col.startswith("value__")]

    rows = [
        {
            "check": "Dataset has enough rows",
            "passed": len(dataset) >= min_rows,
            "detail": f"rows={len(dataset)}; min_rows={min_rows}",
        },
        {
            "check": "Dataset has enough feature-value columns",
            "passed": len(value_cols) >= min_feature_cols,
            "detail": f"value_feature_columns={len(value_cols)}",
        },
        {
            "check": "Dataset has dataset label",
            "passed": "dataset_label" in dataset.columns
            and dataset["dataset_label"].astype(str).str.len().gt(0).all(),
            "detail": "dataset_label present",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13n_target_quality_check(
    *,
    dataset: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    ratio = (
        float(dataset["target_available"].map(_bool_value).mean())
        if not dataset.empty and "target_available" in dataset.columns
        else 0.0
    )
    min_ratio = float(thresholds.get("min_target_available_ratio", 0.80))

    rows = [
        {
            "check": "Primary target column exists",
            "passed": "future_63d_spy_return_state" in dataset.columns,
            "detail": "future_63d_spy_return_state",
        },
        {
            "check": "Secondary target column exists",
            "passed": "future_63d_drawdown_risk_state" in dataset.columns,
            "detail": "future_63d_drawdown_risk_state",
        },
        {
            "check": "Target availability ratio is acceptable",
            "passed": ratio >= min_ratio,
            "detail": f"target_available_ratio={ratio:.4f}; min_ratio={min_ratio:.4f}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13n_split_quality_check(dataset: pd.DataFrame) -> pd.DataFrame:
    split_counts = (
        dataset["split_label"].value_counts().to_dict()
        if not dataset.empty and "split_label" in dataset.columns
        else {}
    )

    rows = [
        {
            "check": "Train split has rows",
            "passed": int(split_counts.get("train", 0)) > 0,
            "detail": f"train_rows={int(split_counts.get('train', 0))}",
        },
        {
            "check": "Validation split has rows",
            "passed": int(split_counts.get("validation", 0)) > 0,
            "detail": f"validation_rows={int(split_counts.get('validation', 0))}",
        },
        {
            "check": "Holdout split has rows",
            "passed": int(split_counts.get("holdout", 0)) > 0,
            "detail": f"holdout_rows={int(split_counts.get('holdout', 0))}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13n_macro_guard_quality_check(
    macro_guard_report: pd.DataFrame,
) -> pd.DataFrame:
    if macro_guard_report.empty:
        return pd.DataFrame(
            [
                {
                    "check": "Macro guard report exists",
                    "passed": False,
                    "detail": "missing",
                    "result": "Failed",
                }
            ]
        )

    row = macro_guard_report.iloc[0]
    repaired = _bool_value(row["repaired_successfully"])
    blocked = _bool_value(row["macro_blocked_for_dataset_v1"])
    label = str(row["dataset_label"]).lower()

    honest = (
        ("multi_factor" in label or "technical_macro" in label)
        if repaired
        else ("technical_only" in label and "macro_blocked" in label and blocked)
    )

    rows = [
        {
            "check": "Macro was repaired or blocked",
            "passed": repaired or blocked,
            "detail": f"repaired={repaired}; blocked={blocked}",
        },
        {
            "check": "Dataset label matches macro guard result",
            "passed": honest,
            "detail": f"dataset_label={label}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13n_forbidden_column_check(
    *,
    dataset: pd.DataFrame,
    forbidden_columns: list[str],
) -> pd.DataFrame:
    fragments = [str(item).lower() for item in forbidden_columns]
    matched = [
        str(col)
        for col in dataset.columns
        if any(fragment in str(col).lower() for fragment in fragments)
    ]
    return pd.DataFrame(
        [
            {
                "frame": "assembled_dataset",
                "matched_columns": "; ".join(matched),
                "passed": len(matched) == 0,
                "result": "Passed" if len(matched) == 0 else "Failed",
            }
        ]
    )


def build_phase13n_phase13o_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13o_boundary", {})

    checks = [
        (
            "phase13o_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "pre-registration" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13o_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "model training execution"
            in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation"
            in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13o_may_preregister_model_training",
            _bool_value(boundary.get("phase13o_may_preregister_model_training", False)),
            _bool_value(boundary.get("phase13o_may_preregister_model_training", False)),
        ),
        (
            "phase13o_may_train_model",
            _bool_value(boundary.get("phase13o_may_train_model", True)),
            not _bool_value(boundary.get("phase13o_may_train_model", True)),
        ),
        (
            "phase13o_may_select_model",
            _bool_value(boundary.get("phase13o_may_select_model", True)),
            not _bool_value(boundary.get("phase13o_may_select_model", True)),
        ),
        (
            "phase13o_may_create_signal",
            _bool_value(boundary.get("phase13o_may_create_signal", True)),
            not _bool_value(boundary.get("phase13o_may_create_signal", True)),
        ),
        (
            "phase13o_may_run_backtest",
            _bool_value(boundary.get("phase13o_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13o_may_run_backtest", True)),
        ),
        (
            "phase13o_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13o_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13o_may_deploy_paper_trading", True)),
        ),
        (
            "phase13o_may_promote_candidate",
            _bool_value(boundary.get("phase13o_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13o_may_promote_candidate", True)),
        ),
    ]
    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13n_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13m_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    dataset_quality_check: pd.DataFrame,
    target_quality_check: pd.DataFrame,
    split_quality_check: pd.DataFrame,
    macro_guard_quality_check: pd.DataFrame,
    forbidden_column_check: pd.DataFrame,
    phase13o_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13m_reports_present": bool(
                    report_inventory_check["present"].all()
                )
                if not report_inventory_check.empty
                else False,
                "phase13m_result_passed": bool(phase13m_result_check["passed"].all())
                if not phase13m_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "dataset_quality_passed": bool(dataset_quality_check["passed"].all())
                if not dataset_quality_check.empty
                else False,
                "target_quality_passed": bool(target_quality_check["passed"].all())
                if not target_quality_check.empty
                else False,
                "split_quality_passed": bool(split_quality_check["passed"].all())
                if not split_quality_check.empty
                else False,
                "macro_guard_quality_passed": bool(
                    macro_guard_quality_check["passed"].all()
                )
                if not macro_guard_quality_check.empty
                else False,
                "forbidden_column_check_passed": bool(
                    forbidden_column_check["passed"].all()
                )
                if not forbidden_column_check.empty
                else False,
                "phase13o_boundary_passed": bool(
                    phase13o_boundary_check["passed"].all()
                )
                if not phase13o_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "model_training": False,
                "model_selection": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13n_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13N summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get("required_audit_role", "ML dataset quality and leakage audit only")
    )

    rows = [
        _gate_row(
            "Phase 13M reports are present",
            (not gates.get("require_phase13m_reports_present", True))
            or bool(row["phase13m_reports_present"]),
            f"phase13m_reports_present={bool(row['phase13m_reports_present'])}",
        ),
        _gate_row(
            "Phase 13M conclusion and gates passed",
            (
                (not gates.get("require_phase13m_conclusion_passed", True))
                or bool(row["phase13m_result_passed"])
            )
            and (
                (not gates.get("require_phase13m_gate_report_passed", True))
                or bool(row["phase13m_result_passed"])
            ),
            f"phase13m_result_passed={bool(row['phase13m_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Dataset quality passed",
            bool(row["dataset_quality_passed"]),
            f"dataset_quality_passed={bool(row['dataset_quality_passed'])}",
        ),
        _gate_row(
            "Target quality passed",
            bool(row["target_quality_passed"]),
            f"target_quality_passed={bool(row['target_quality_passed'])}",
        ),
        _gate_row(
            "Split quality passed",
            bool(row["split_quality_passed"]),
            f"split_quality_passed={bool(row['split_quality_passed'])}",
        ),
        _gate_row(
            "Macro guard quality passed",
            bool(row["macro_guard_quality_passed"]),
            f"macro_guard_quality_passed={bool(row['macro_guard_quality_passed'])}",
        ),
        _gate_row(
            "No forbidden model/signal/backtest columns exist",
            bool(row["forbidden_column_check_passed"]),
            f"forbidden_column_check_passed="
            f"{bool(row['forbidden_column_check_passed'])}",
        ),
        _gate_row(
            "Phase 13O boundary is pre-registration-only",
            bool(row["phase13o_boundary_passed"]),
            f"phase13o_boundary_passed={bool(row['phase13o_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks model/signal/backtest/paper-trading/promotion",
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


def build_phase13n_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — ML dataset quality and leakage audit passed"
        if all_passed
        else "Failed ML dataset quality and leakage audit"
    )
    interpretation = (
        "Phase 13N audited dataset quality, target quality, split quality, macro "
        "guard honesty, forbidden columns, leakage, and boundaries. It did not train "
        "models, select models, create signals, run backtests, deploy paper trading, "
        "promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13N found a dataset, target, split, macro guard, forbidden-column, "
        "boundary, or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 13N",
                "diagnostic": "ML dataset quality and leakage audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def save_phase13n_ml_dataset_quality_leakage_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13n_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = phase_config.get("phase13m_reports", {})
    thresholds = phase_config.get("quality_thresholds", {})

    report_inventory_check = build_phase13n_report_inventory_check(phase_config)
    phase13m_result_check = build_phase13n_phase13m_result_check(phase_config)
    config_flag_check = build_phase13n_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )

    dataset = _read_csv_if_exists(reports.get("assembled_dataset", ""))
    macro_guard_report = _read_csv_if_exists(reports.get("macro_guard_report", ""))

    dataset_quality_check = build_phase13n_dataset_quality_check(
        dataset=dataset,
        thresholds=thresholds,
    )
    target_quality_check = build_phase13n_target_quality_check(
        dataset=dataset,
        thresholds=thresholds,
    )
    split_quality_check = build_phase13n_split_quality_check(dataset)
    macro_guard_quality_check = build_phase13n_macro_guard_quality_check(
        macro_guard_report
    )
    forbidden_column_check = build_phase13n_forbidden_column_check(
        dataset=dataset,
        forbidden_columns=_as_list(thresholds.get("forbidden_columns")),
    )
    phase13o_boundary_check = build_phase13n_phase13o_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13n_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13m_result_check=phase13m_result_check,
        config_flag_check=config_flag_check,
        dataset_quality_check=dataset_quality_check,
        target_quality_check=target_quality_check,
        split_quality_check=split_quality_check,
        macro_guard_quality_check=macro_guard_quality_check,
        forbidden_column_check=forbidden_column_check,
        phase13o_boundary_check=phase13o_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13n_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13n_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13m_result_check": phase13m_result_check,
        "config_flag_check": config_flag_check,
        "dataset_quality_check": dataset_quality_check,
        "target_quality_check": target_quality_check,
        "split_quality_check": split_quality_check,
        "macro_guard_quality_check": macro_guard_quality_check,
        "forbidden_column_check": forbidden_column_check,
        "phase13o_boundary_check": phase13o_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13n_quality_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13N — ML Dataset Quality / Leakage Audit",
        sections={
            "Report Inventory Check": report_inventory_check,
            "Phase 13M Result Check": phase13m_result_check,
            "Dataset Quality Check": dataset_quality_check,
            "Target Quality Check": target_quality_check,
            "Split Quality Check": split_quality_check,
            "Macro Guard Quality Check": macro_guard_quality_check,
            "Forbidden Column Check": forbidden_column_check,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path / "phase13n_ml_dataset_quality_leakage_audit.md",
    )

    print("Wrote Phase 13N ML dataset quality reports.")
    return outputs