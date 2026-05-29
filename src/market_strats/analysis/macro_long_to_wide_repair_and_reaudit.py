from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_PHASE13Q_CONFIG: dict[str, Any] = {
    "enabled": False,
    "execution_role": "Macro long-to-wide repair execution and guarded dataset reassembly only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13P",
    "proposed_next_phase": "Phase 13R",
    "allow_macro_repair_execution": True,
    "allow_dataset_reassembly": True,
    "allow_target_recalculation": True,
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
    "source_reports": {},
    "input_data": {},
    "macro_repair_policy": {},
    "macro_feature_policy": {},
    "dataset_policy": {},
    "phase13r_boundary": {},
    "gates": {
        "require_phase13p_passed": True,
        "require_source_reports_present": True,
        "require_macro_source_loaded": True,
        "require_long_to_wide_success": True,
        "require_required_macro_series_present": True,
        "require_macro_repair_panel_created": True,
        "require_macro_availability_threshold_passed": True,
        "require_dataset_reassembled": True,
        "require_dataset_honest_label": True,
        "require_targets_calculated": True,
        "require_split_labels_created": True,
        "require_no_leakage_flags": True,
        "require_phase13r_boundary_quality_audit_only": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_feature_importance": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_execution_role": (
            "Macro long-to-wide repair execution and guarded dataset reassembly only"
        ),
    },
}


DEFAULT_PHASE13R_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Repaired macro dataset quality and leakage audit only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13Q",
    "proposed_next_phase": "Phase 13S",
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
    "phase13q_reports": {},
    "quality_thresholds": {},
    "phase13s_boundary": {},
    "gates": {
        "require_phase13q_reports_present": True,
        "require_phase13q_conclusion_passed": True,
        "require_phase13q_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_macro_repair_quality": True,
        "require_dataset_quality": True,
        "require_target_quality": True,
        "require_split_quality": True,
        "require_honest_multifactor_label": True,
        "require_no_forbidden_columns": True,
        "require_no_leakage_flags": True,
        "require_phase13s_boundary_prereg_only": True,
        "require_no_model_training": True,
        "require_no_model_selection": True,
        "require_no_signal_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_feature_importance": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_audit_role": "Repaired macro dataset quality and leakage audit only",
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


def _get_phase13q_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13Q_CONFIG,
        config.get("phase13q_macro_long_to_wide_repair_execution", {}),
    )


def _get_phase13r_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13R_CONFIG,
        config.get("phase13r_repaired_macro_dataset_quality_audit", {}),
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


def _load_first_existing_csv(paths: list[str]) -> tuple[pd.DataFrame, str]:
    for path in paths:
        frame = _read_csv_if_exists(path)
        if not frame.empty:
            return frame, path
    return pd.DataFrame(), ""


def _find_column(frame: pd.DataFrame, candidates: list[str]) -> str:
    lower_map = {str(col).strip().lower(): str(col) for col in frame.columns}

    for candidate in candidates:
        clean = str(candidate).strip().lower()
        if clean in lower_map:
            return lower_map[clean]

    for col in frame.columns:
        col_lower = str(col).strip().lower()
        for candidate in candidates:
            if str(candidate).strip().lower() in col_lower:
                return str(col)

    return ""


def _next_business_day(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce") + pd.offsets.BDay(1)


def build_phase13q_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase13q_phase13p_result_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13p_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13p_gate_report", ""))

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
                "check": "Phase 13P conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13P gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def load_phase13q_macro_source(phase_config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    input_data = phase_config.get("input_data", {})
    paths = [str(path) for path in _as_list(input_data.get("macro_aligned_candidates"))]
    return _load_first_existing_csv(paths)


def build_phase13q_macro_source_check(
    *,
    macro_source: pd.DataFrame,
    macro_source_path: str,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    input_data = phase_config.get("input_data", {})

    date_col = _find_column(macro_source, _as_list(input_data.get("date_column_candidates")))
    series_col = _find_column(
        macro_source,
        _as_list(input_data.get("series_column_candidates")),
    )
    value_col = _find_column(
        macro_source,
        _as_list(input_data.get("value_column_candidates")),
    )
    available_date_col = _find_column(
        macro_source,
        _as_list(input_data.get("available_date_column_candidates")),
    )

    numeric_value_non_null = (
        int(pd.to_numeric(macro_source[value_col], errors="coerce").notna().sum())
        if value_col
        else 0
    )
    required = set(str(item) for item in _as_list(input_data.get("required_macro_series")))
    present_series = (
        set(macro_source[series_col].dropna().astype(str).unique())
        if series_col
        else set()
    )

    required_present = required.issubset(present_series)

    return pd.DataFrame(
        [
            {
                "source_path": macro_source_path,
                "rows": int(len(macro_source)),
                "columns": "; ".join(str(col) for col in macro_source.columns),
                "date_column": date_col,
                "series_column": series_col,
                "value_column": value_col,
                "available_date_column": available_date_col,
                "numeric_value_non_null": numeric_value_non_null,
                "required_macro_series_present": required_present,
                "present_required_series": "; ".join(sorted(required & present_series)),
                "long_format_detected": bool(date_col and series_col and value_col),
            }
        ]
    )


def build_phase13q_macro_wide_panel(
    *,
    macro_source: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    input_data = phase_config.get("input_data", {})
    required_series = [str(item) for item in _as_list(input_data.get("required_macro_series"))]

    if macro_source.empty:
        return pd.DataFrame()

    date_col = _find_column(macro_source, _as_list(input_data.get("date_column_candidates")))
    series_col = _find_column(
        macro_source,
        _as_list(input_data.get("series_column_candidates")),
    )
    value_col = _find_column(
        macro_source,
        _as_list(input_data.get("value_column_candidates")),
    )
    available_col = _find_column(
        macro_source,
        _as_list(input_data.get("available_date_column_candidates")),
    )

    if not date_col or not series_col or not value_col:
        return pd.DataFrame()

    frame = macro_source.copy()
    frame["as_of_date"] = pd.to_datetime(frame[date_col], errors="coerce")
    frame["series_id_clean"] = frame[series_col].astype(str)
    frame["numeric_value"] = pd.to_numeric(frame[value_col], errors="coerce")

    if available_col:
        frame["available_date"] = pd.to_datetime(frame[available_col], errors="coerce")
    else:
        frame["available_date"] = frame["as_of_date"]

    frame = frame.dropna(subset=["as_of_date", "series_id_clean"])
    frame = frame[frame["series_id_clean"].isin(required_series)]

    wide = frame.pivot_table(
        index="as_of_date",
        columns="series_id_clean",
        values="numeric_value",
        aggfunc="last",
    ).reset_index()

    available = frame.pivot_table(
        index="as_of_date",
        columns="series_id_clean",
        values="available_date",
        aggfunc="last",
    ).reset_index()

    for series in required_series:
        if series not in wide.columns:
            wide[series] = np.nan
        if series not in available.columns:
            available[series] = pd.NaT

    available_cols = {
        series: f"{series}_available_date"
        for series in required_series
        if series in available.columns
    }
    available = available.rename(columns=available_cols)

    out = wide.merge(available, on="as_of_date", how="left")
    out = out.sort_values("as_of_date").reset_index(drop=True)
    out["decision_date"] = out["as_of_date"]

    return out


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
    out = pd.DataFrame(
        {
            "as_of_date": frame["as_of_date"],
            "observation_date": frame["as_of_date"],
            "release_date": pd.NaT,
            "availability_date": frame["as_of_date"],
            "decision_date": frame["decision_date"],
            "family_id": "macro",
            "feature_id": feature_id,
            "formula_id": formula_id,
            "source_name": source_name,
            "source_version": "phase13q_long_to_wide_repair",
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
            "contract_version": "phase13g_v1_phase13q_repair",
        }
    )

    for col in [
        "as_of_date",
        "observation_date",
        "release_date",
        "availability_date",
        "decision_date",
    ]:
        out[col] = pd.to_datetime(out[col], errors="coerce").dt.date

    return out


def build_phase13q_macro_repair_panel(
    *,
    macro_wide_panel: pd.DataFrame,
    macro_source_path: str,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if macro_wide_panel.empty:
        return pd.DataFrame()

    policy = phase_config.get("macro_feature_policy", {})
    frame = macro_wide_panel.copy().sort_values("as_of_date").reset_index(drop=True)

    frame["macro_dgs2_level"] = pd.to_numeric(frame["DGS2"], errors="coerce")
    frame["macro_dgs10_minus_dgs2"] = (
        pd.to_numeric(frame["DGS10"], errors="coerce")
        - pd.to_numeric(frame["DGS2"], errors="coerce")
    )
    cpi = pd.to_numeric(frame["CPIAUCSL"], errors="coerce")
    frame["macro_cpi_yoy"] = (
        cpi / cpi.shift(int(policy.get("cpi_yoy_lookback_trading_days", 252))) - 1.0
    )
    unrate = pd.to_numeric(frame["UNRATE"], errors="coerce")
    frame["macro_unrate_3m_change"] = (
        unrate - unrate.shift(int(policy.get("unrate_change_lookback_trading_days", 63)))
    )

    rows = []

    state, reason = _state_simple(
        frame["macro_dgs2_level"],
        frame["macro_dgs2_level"] < float(policy.get("dgs2_supportive_below", 2.50)),
        frame["macro_dgs2_level"].between(
            float(policy.get("dgs2_supportive_below", 2.50)),
            float(policy.get("dgs2_neutral_upper", 4.50)),
        ),
        "DGS2 unavailable after long-to-wide repair",
    )
    rows.append(
        _macro_feature_rows(
            frame=frame,
            feature_id="macro_short_rate_state",
            formula_id="dgs2_level_regime",
            value_col="macro_dgs2_level",
            state=state,
            reason=reason,
            source_name=macro_source_path,
        )
    )

    state, reason = _state_simple(
        frame["macro_dgs10_minus_dgs2"],
        frame["macro_dgs10_minus_dgs2"]
        > float(policy.get("yield_curve_supportive_above", 0.50)),
        frame["macro_dgs10_minus_dgs2"].between(
            float(policy.get("yield_curve_neutral_lower", -0.50)),
            float(policy.get("yield_curve_neutral_upper", 0.50)),
        ),
        "DGS10 or DGS2 unavailable after long-to-wide repair",
    )
    rows.append(
        _macro_feature_rows(
            frame=frame,
            feature_id="macro_yield_curve_state",
            formula_id="dgs10_minus_dgs2_curve_regime",
            value_col="macro_dgs10_minus_dgs2",
            state=state,
            reason=reason,
            source_name=macro_source_path,
        )
    )

    state, reason = _state_simple(
        frame["macro_cpi_yoy"],
        frame["macro_cpi_yoy"] < float(policy.get("cpi_yoy_supportive_below", 0.03)),
        frame["macro_cpi_yoy"].between(
            float(policy.get("cpi_yoy_supportive_below", 0.03)),
            float(policy.get("cpi_yoy_neutral_upper", 0.05)),
        ),
        "CPI current or 12-month comparison unavailable after long-to-wide repair",
    )
    rows.append(
        _macro_feature_rows(
            frame=frame,
            feature_id="macro_inflation_state",
            formula_id="cpi_yoy_inflation_regime",
            value_col="macro_cpi_yoy",
            state=state,
            reason=reason,
            source_name=macro_source_path,
        )
    )

    labour_state = pd.Series("neutral", index=frame.index, dtype="object")
    labour_reason = pd.Series("labour state inside neutral band", index=frame.index)

    supportive = (
        (unrate < float(policy.get("unrate_supportive_below", 5.00)))
        & (frame["macro_unrate_3m_change"] <= 0.00)
    )
    fragile = (
        (unrate >= float(policy.get("unrate_fragile_above_or_equal", 6.00)))
        | (
            frame["macro_unrate_3m_change"]
            > float(policy.get("unrate_3m_fragile_change_above", 0.50))
        )
    )
    unavailable = unrate.isna() | frame["macro_unrate_3m_change"].isna()

    labour_state.loc[supportive] = "supportive"
    labour_state.loc[fragile] = "fragile"
    labour_state.loc[unavailable] = "unavailable"
    labour_reason.loc[supportive] = "low and non-rising unemployment"
    labour_reason.loc[fragile] = "high or quickly rising unemployment"
    labour_reason.loc[unavailable] = (
        "UNRATE current or 3-month comparison unavailable after long-to-wide repair"
    )

    rows.append(
        _macro_feature_rows(
            frame=frame,
            feature_id="macro_labour_state",
            formula_id="unrate_level_and_3m_change_regime",
            value_col="macro_unrate_3m_change",
            state=labour_state,
            reason=labour_reason,
            source_name=macro_source_path,
        )
    )

    return pd.concat(rows, ignore_index=True)


def _feature_availability_ratio(feature_panel: pd.DataFrame, family_id: str) -> float:
    if feature_panel.empty or "family_id" not in feature_panel.columns:
        return 0.0
    family = feature_panel[feature_panel["family_id"].astype(str).eq(family_id)]
    if family.empty:
        return 0.0
    return float(family["missingness_state"].astype(str).eq("available").mean())


def build_phase13q_macro_availability_report(
    *,
    macro_repair_panel: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    policy = phase_config.get("macro_repair_policy", {})
    threshold = float(policy.get("min_macro_available_ratio_to_use", 0.20))
    non_null_threshold = float(policy.get("min_macro_feature_value_non_null_ratio", 0.20))

    ratio = _feature_availability_ratio(macro_repair_panel, "macro")
    feature_profiles = []

    if not macro_repair_panel.empty:
        for feature_id, group in macro_repair_panel.groupby("feature_id"):
            feature_profiles.append(
                {
                    "feature_id": feature_id,
                    "rows": int(len(group)),
                    "value_non_null_ratio": float(
                        pd.to_numeric(group["feature_value"], errors="coerce")
                        .notna()
                        .mean()
                    ),
                    "available_ratio": float(
                        group["missingness_state"].astype(str).eq("available").mean()
                    ),
                }
            )

    feature_profile = pd.DataFrame(feature_profiles)
    all_feature_non_null_ok = (
        not feature_profile.empty
        and bool((feature_profile["value_non_null_ratio"] >= non_null_threshold).all())
    )
    repair_passed = ratio >= threshold and all_feature_non_null_ok

    return pd.DataFrame(
        [
            {
                "macro_available_ratio": ratio,
                "min_macro_available_ratio_to_use": threshold,
                "all_feature_non_null_threshold_passed": all_feature_non_null_ok,
                "macro_repair_passed": repair_passed,
                "dataset_label": str(
                    policy.get(
                        "dataset_label_if_repaired",
                        "multi_factor_technical_macro_dataset_v1",
                    )
                    if repair_passed
                    else policy.get(
                        "dataset_label_if_blocked",
                        "technical_only_macro_blocked_dataset_v1",
                    )
                ),
                "feature_profile_rows": int(len(feature_profile)),
            }
        ]
    )


def _load_price_frame(
    *,
    phase_config: dict[str, Any],
    relative_momentum_outputs: Any | None,
    ticker_outputs: Any | None,
) -> tuple[pd.DataFrame, str]:
    input_data = phase_config.get("input_data", {})
    date_candidates = _as_list(input_data.get("date_column_candidates"))
    close_candidates = _as_list(input_data.get("close_column_candidates"))

    for container in [ticker_outputs, relative_momentum_outputs]:
        for frame in _extract_dataframes(container):
            if frame.empty:
                continue
            candidate = frame.copy()
            date_col = _find_column(candidate, date_candidates)
            close_col = _find_column(candidate, close_candidates)
            if not date_col or not close_col:
                continue
            out = candidate[[date_col, close_col]].copy()
            out = out.rename(columns={date_col: "as_of_date", close_col: "adjusted_close"})
            out["as_of_date"] = pd.to_datetime(out["as_of_date"], errors="coerce")
            out["adjusted_close"] = pd.to_numeric(out["adjusted_close"], errors="coerce")
            out = out.dropna(subset=["as_of_date", "adjusted_close"])
            if not out.empty:
                return out.sort_values("as_of_date").drop_duplicates("as_of_date"), (
                    "in_memory_run_backtest_outputs"
                )

    paths = [str(path) for path in _as_list(input_data.get("technical_price_candidates"))]
    frame, path = _load_first_existing_csv(paths)

    if frame.empty:
        return pd.DataFrame(), ""

    date_col = _find_column(frame, date_candidates)
    close_col = _find_column(frame, close_candidates)

    if not date_col or not close_col:
        return pd.DataFrame(), path

    out = frame[[date_col, close_col]].copy()
    out = out.rename(columns={date_col: "as_of_date", close_col: "adjusted_close"})
    out["as_of_date"] = pd.to_datetime(out["as_of_date"], errors="coerce")
    out["adjusted_close"] = pd.to_numeric(out["adjusted_close"], errors="coerce")
    out = out.dropna(subset=["as_of_date", "adjusted_close"])
    return out.sort_values("as_of_date").drop_duplicates("as_of_date"), path


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

    return pd.concat([value, state, missingness], axis=1).reset_index()


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


def build_phase13q_target_frame(
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
            frame["future_return_63d"]
            > float(policy.get("primary_supportive_threshold", 0.05)),
            frame["future_return_63d"]
            < float(policy.get("primary_fragile_threshold", -0.05)),
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
    ]


def _assign_split_label(dates: pd.Series, policy: dict[str, Any]) -> pd.Series:
    parsed = pd.to_datetime(dates, errors="coerce")
    labels = pd.Series("out_of_split", index=parsed.index, dtype="object")

    labels.loc[
        parsed.between(pd.Timestamp(policy["train_start"]), pd.Timestamp(policy["train_end"]))
    ] = "train"
    labels.loc[
        parsed.between(
            pd.Timestamp(policy["validation_start"]),
            pd.Timestamp(policy["validation_end"]),
        )
    ] = "validation"
    labels.loc[
        parsed.between(
            pd.Timestamp(policy["holdout_start"]),
            pd.Timestamp(policy["holdout_end"]),
        )
    ] = "holdout"

    return labels


def build_phase13q_reassembled_dataset(
    *,
    technical_feature_panel: pd.DataFrame,
    macro_repair_panel: pd.DataFrame,
    macro_availability_report: pd.DataFrame,
    price_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    policy = phase_config.get("dataset_policy", {})

    if technical_feature_panel.empty or macro_repair_panel.empty:
        return pd.DataFrame()

    feature_panel = pd.concat([technical_feature_panel, macro_repair_panel], ignore_index=True)
    wide = _wide_feature_dataset(feature_panel)
    target = build_phase13q_target_frame(price_frame=price_frame, phase_config=phase_config)

    if wide.empty or target.empty:
        return pd.DataFrame()

    dataset = wide.merge(target, on="decision_date", how="left")
    start = pd.Timestamp(policy.get("common_start_date", "1900-01-01"))
    end = pd.Timestamp(policy.get("canonical_endpoint", "2100-01-01"))
    dataset = dataset[
        pd.to_datetime(dataset["decision_date"]).between(start, end)
    ].copy()

    dataset["split_label"] = _assign_split_label(dataset["decision_date"], policy)
    dataset["dataset_id"] = str(policy.get("dataset_id", "phase13q_ml_feature_dataset_v1"))
    dataset["dataset_label"] = str(macro_availability_report.iloc[0]["dataset_label"])
    dataset["macro_repair_passed"] = _bool_value(
        macro_availability_report.iloc[0]["macro_repair_passed"]
    )

    first_cols = [
        "dataset_id",
        "dataset_label",
        "macro_repair_passed",
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


def build_phase13q_family_usage_report(
    *,
    technical_feature_panel: pd.DataFrame,
    macro_repair_panel: pd.DataFrame,
) -> pd.DataFrame:
    feature_panel = pd.concat([technical_feature_panel, macro_repair_panel], ignore_index=True)
    rows = []

    for family_id, group in feature_panel.groupby("family_id"):
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

    return pd.DataFrame(rows)


def build_phase13q_target_summary(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame()

    return pd.DataFrame(
        [
            {
                "rows": int(len(dataset)),
                "target_available_rows": int(dataset["target_available"].map(_bool_value).sum()),
                "target_available_ratio": float(dataset["target_available"].map(_bool_value).mean()),
                "primary_target_classes": "; ".join(
                    sorted(dataset["future_63d_spy_return_state"].dropna().astype(str).unique())
                ),
                "secondary_target_classes": "; ".join(
                    sorted(dataset["future_63d_drawdown_risk_state"].dropna().astype(str).unique())
                ),
            }
        ]
    )


def build_phase13q_split_summary(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame()

    out = (
        dataset.groupby("split_label")
        .agg(
            rows=("split_label", "size"),
            target_available_rows=("target_available", lambda x: int(x.map(_bool_value).sum())),
            first_decision_date=("decision_date", "min"),
            last_decision_date=("decision_date", "max"),
        )
        .reset_index()
    )
    out["target_available_ratio"] = out["target_available_rows"] / out["rows"]
    return out


def build_phase13q_dataset_metadata(
    *,
    dataset: pd.DataFrame,
    macro_availability_report: pd.DataFrame,
) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame()

    value_cols = [col for col in dataset.columns if col.startswith("value__")]
    macro_value_cols = [col for col in value_cols if "macro_" in col]
    state_cols = [col for col in dataset.columns if col.startswith("state__")]
    missingness_cols = [col for col in dataset.columns if col.startswith("missingness__")]

    return pd.DataFrame(
        [
            {
                "dataset_id": str(dataset["dataset_id"].iloc[0]),
                "dataset_label": str(dataset["dataset_label"].iloc[0]),
                "rows": int(len(dataset)),
                "value_feature_columns": int(len(value_cols)),
                "macro_value_feature_columns": int(len(macro_value_cols)),
                "state_feature_columns": int(len(state_cols)),
                "missingness_feature_columns": int(len(missingness_cols)),
                "macro_available_ratio": float(
                    macro_availability_report.iloc[0]["macro_available_ratio"]
                ),
                "macro_repair_passed": _bool_value(
                    macro_availability_report.iloc[0]["macro_repair_passed"]
                ),
                "model_training": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
            }
        ]
    )


def build_phase13q_phase13r_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase13r_boundary", {})
    checks = [
        (
            "phase13r_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "quality" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13r_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "model training" in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation" in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13r_may_audit_macro_repair",
            _bool_value(boundary.get("phase13r_may_audit_macro_repair", False)),
            _bool_value(boundary.get("phase13r_may_audit_macro_repair", False)),
        ),
        (
            "phase13r_may_train_model",
            _bool_value(boundary.get("phase13r_may_train_model", True)),
            not _bool_value(boundary.get("phase13r_may_train_model", True)),
        ),
        (
            "phase13r_may_create_signal",
            _bool_value(boundary.get("phase13r_may_create_signal", True)),
            not _bool_value(boundary.get("phase13r_may_create_signal", True)),
        ),
        (
            "phase13r_may_run_backtest",
            _bool_value(boundary.get("phase13r_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13r_may_run_backtest", True)),
        ),
        (
            "phase13r_may_promote_candidate",
            _bool_value(boundary.get("phase13r_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13r_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13_scope_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    checks = [
        ("No model training", "allow_model_training"),
        ("No model selection", "allow_model_selection"),
        ("No signal creation", "allow_signal_creation"),
        ("No allocation rule creation", "allow_allocation_rule_creation"),
        ("No strategy backtest", "allow_strategy_backtest"),
        ("No empirical return weights", "allow_empirical_return_weights"),
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


def build_phase13q_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13p_result_check: pd.DataFrame,
    macro_source_check: pd.DataFrame,
    macro_wide_panel: pd.DataFrame,
    macro_repair_panel: pd.DataFrame,
    macro_availability_report: pd.DataFrame,
    dataset: pd.DataFrame,
    target_summary: pd.DataFrame,
    split_summary: pd.DataFrame,
    phase13r_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    leakage_count = 0
    if not macro_repair_panel.empty and "leakage_flag" in macro_repair_panel.columns:
        leakage_count = int(macro_repair_panel["leakage_flag"].map(_bool_value).sum())

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
                "phase13p_result_passed": bool(phase13p_result_check["passed"].all())
                if not phase13p_result_check.empty
                else False,
                "macro_source_loaded": not macro_source_check.empty
                and int(macro_source_check.iloc[0]["rows"]) > 0,
                "long_format_detected": _bool_value(
                    macro_source_check.iloc[0]["long_format_detected"]
                )
                if not macro_source_check.empty
                else False,
                "required_macro_series_present": _bool_value(
                    macro_source_check.iloc[0]["required_macro_series_present"]
                )
                if not macro_source_check.empty
                else False,
                "macro_wide_rows": int(len(macro_wide_panel)),
                "macro_repair_panel_rows": int(len(macro_repair_panel)),
                "macro_available_ratio": float(
                    macro_availability_report.iloc[0]["macro_available_ratio"]
                )
                if not macro_availability_report.empty
                else 0.0,
                "macro_repair_passed": _bool_value(
                    macro_availability_report.iloc[0]["macro_repair_passed"]
                )
                if not macro_availability_report.empty
                else False,
                "dataset_label": str(macro_availability_report.iloc[0]["dataset_label"])
                if not macro_availability_report.empty
                else "",
                "dataset_rows": int(len(dataset)),
                "target_summary_rows": int(len(target_summary)),
                "split_summary_rows": int(len(split_summary)),
                "leakage_flag_count": leakage_count,
                "phase13r_boundary_passed": bool(phase13r_boundary_check["passed"].all())
                if not phase13r_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "model_training": False,
                "model_selection": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def _dataset_label_is_honest(summary_row: pd.Series) -> bool:
    label = str(summary_row["dataset_label"]).lower()
    macro_passed = _bool_value(summary_row["macro_repair_passed"])

    if macro_passed:
        return "multi_factor" in label or "technical_macro" in label

    return "technical_only" in label and "macro_blocked" in label


def build_phase13q_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13Q summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_execution_role",
            "Macro long-to-wide repair execution and guarded dataset reassembly only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13P passed",
            bool(row["phase13p_result_passed"]),
            f"phase13p_result_passed={bool(row['phase13p_result_passed'])}",
        ),
        _gate_row(
            "Source reports are present",
            bool(row["source_reports_present"]),
            f"source_reports_present={bool(row['source_reports_present'])}",
        ),
        _gate_row(
            "Macro source loaded",
            bool(row["macro_source_loaded"]),
            f"macro_source_loaded={bool(row['macro_source_loaded'])}",
        ),
        _gate_row(
            "Long-to-wide repair succeeded",
            bool(row["long_format_detected"]) and int(row["macro_wide_rows"]) > 0,
            f"long_format_detected={bool(row['long_format_detected'])}; "
            f"macro_wide_rows={int(row['macro_wide_rows'])}",
        ),
        _gate_row(
            "Required macro series are present",
            bool(row["required_macro_series_present"]),
            f"required_macro_series_present={bool(row['required_macro_series_present'])}",
        ),
        _gate_row(
            "Macro repair panel was created",
            int(row["macro_repair_panel_rows"]) > 0,
            f"macro_repair_panel_rows={int(row['macro_repair_panel_rows'])}",
        ),
        _gate_row(
            "Macro availability threshold passed",
            bool(row["macro_repair_passed"]),
            f"macro_available_ratio={float(row['macro_available_ratio']):.4f}",
        ),
        _gate_row(
            "Dataset was reassembled",
            int(row["dataset_rows"]) > 0,
            f"dataset_rows={int(row['dataset_rows'])}",
        ),
        _gate_row(
            "Dataset label is honest",
            _dataset_label_is_honest(row),
            f"dataset_label={row['dataset_label']}",
        ),
        _gate_row(
            "Targets were calculated",
            int(row["target_summary_rows"]) > 0,
            f"target_summary_rows={int(row['target_summary_rows'])}",
        ),
        _gate_row(
            "Split labels were created",
            int(row["split_summary_rows"]) >= 3,
            f"split_summary_rows={int(row['split_summary_rows'])}",
        ),
        _gate_row(
            "No leakage flags are present",
            int(row["leakage_flag_count"]) == 0,
            f"leakage_flag_count={int(row['leakage_flag_count'])}",
        ),
        _gate_row(
            "Phase 13R boundary is quality-audit-only",
            bool(row["phase13r_boundary_passed"]),
            f"phase13r_boundary_passed={bool(row['phase13r_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks model/signal/backtest/promotion",
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


def build_phase13q_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — macro long-to-wide repair and guarded dataset reassembly passed"
        if all_passed
        else "Failed macro long-to-wide repair and guarded dataset reassembly"
    )
    interpretation = (
        "Phase 13Q normalised long-format macro data to wide form, recalculated "
        "macro feature states, reassembled the dataset with the macro guard, and "
        "recalculated registered targets. It did not train models, create signals, "
        "run backtests, deploy paper trading, promote a candidate, or change the "
        "final candidate."
        if all_passed
        else "Phase 13Q found a macro repair, dataset, target, split, label, boundary, "
        "or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 13Q",
                "diagnostic": "Macro long-to-wide repair and guarded dataset reassembly",
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


def save_phase13q_macro_long_to_wide_repair_execution(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: Any | None = None,
    ticker_outputs: Any | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13q_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13q_source_report_check(phase_config)
    phase13p_result_check = build_phase13q_phase13p_result_check(phase_config)
    macro_source, macro_source_path = load_phase13q_macro_source(phase_config)
    macro_source_check = build_phase13q_macro_source_check(
        macro_source=macro_source,
        macro_source_path=macro_source_path,
        phase_config=phase_config,
    )
    macro_wide_panel = build_phase13q_macro_wide_panel(
        macro_source=macro_source,
        phase_config=phase_config,
    )
    macro_repair_panel = build_phase13q_macro_repair_panel(
        macro_wide_panel=macro_wide_panel,
        macro_source_path=macro_source_path,
        phase_config=phase_config,
    )
    macro_availability_report = build_phase13q_macro_availability_report(
        macro_repair_panel=macro_repair_panel,
        phase_config=phase_config,
    )

    source_reports = phase_config.get("source_reports", {})
    feature_panel = _read_csv_if_exists(source_reports.get("feature_panel", ""))
    technical_feature_panel = (
        feature_panel[feature_panel["family_id"].astype(str).eq("technical")].copy()
        if not feature_panel.empty and "family_id" in feature_panel.columns
        else pd.DataFrame()
    )

    price_frame, price_source = _load_price_frame(
        phase_config=phase_config,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
    )

    dataset = build_phase13q_reassembled_dataset(
        technical_feature_panel=technical_feature_panel,
        macro_repair_panel=macro_repair_panel,
        macro_availability_report=macro_availability_report,
        price_frame=price_frame,
        phase_config=phase_config,
    )
    family_usage_report = build_phase13q_family_usage_report(
        technical_feature_panel=technical_feature_panel,
        macro_repair_panel=macro_repair_panel,
    )
    target_summary = build_phase13q_target_summary(dataset)
    split_summary = build_phase13q_split_summary(dataset)
    dataset_metadata = build_phase13q_dataset_metadata(
        dataset=dataset,
        macro_availability_report=macro_availability_report,
    )
    phase13r_boundary_check = build_phase13q_phase13r_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13q_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13p_result_check=phase13p_result_check,
        macro_source_check=macro_source_check,
        macro_wide_panel=macro_wide_panel,
        macro_repair_panel=macro_repair_panel,
        macro_availability_report=macro_availability_report,
        dataset=dataset,
        target_summary=target_summary,
        split_summary=split_summary,
        phase13r_boundary_check=phase13r_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13q_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13q_conclusion(gate_report)

    outputs = {
        "source_report_check": source_report_check,
        "phase13p_result_check": phase13p_result_check,
        "macro_source_check": macro_source_check,
        "macro_wide_panel": macro_wide_panel,
        "macro_repair_panel": macro_repair_panel,
        "macro_availability_report": macro_availability_report,
        "family_usage_report": family_usage_report,
        "target_summary": target_summary,
        "split_summary": split_summary,
        "dataset_metadata": dataset_metadata,
        "phase13r_boundary_check": phase13r_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13q_repair_{name}.csv", index=False)

    dataset.to_csv(reports_path / "phase13q_ml_feature_dataset_v1.csv", index=False)

    _write_markdown(
        title="Phase 13Q — Macro Long-to-Wide Repair and Guarded Dataset Reassembly",
        sections={
            "Macro Source Check": macro_source_check,
            "Macro Availability Report": macro_availability_report,
            "Family Usage Report": family_usage_report,
            "Target Summary": target_summary,
            "Split Summary": split_summary,
            "Dataset Metadata": dataset_metadata,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13q_macro_long_to_wide_repair_execution.md",
    )

    print("Wrote Phase 13Q macro long-to-wide repair reports.")
    return {**outputs, "reassembled_dataset": dataset}


def build_phase13r_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("phase13q_reports", {}).items():
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


def build_phase13r_phase13q_result_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    reports = phase_config.get("phase13q_reports", {})
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
                "check": "Phase 13Q conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13Q gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13r_config_flag_check(
    *,
    runtime_config: dict[str, Any],
    expected_flags: dict[str, Any],
) -> pd.DataFrame:
    rows = []
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


def build_phase13r_macro_repair_quality_check(
    *,
    macro_availability_report: pd.DataFrame,
    dataset_metadata: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    if macro_availability_report.empty or dataset_metadata.empty:
        return pd.DataFrame(
            [
                {
                    "check": "Macro repair reports exist",
                    "passed": False,
                    "detail": "missing macro availability or metadata",
                    "result": "Failed",
                }
            ]
        )

    macro_ratio = float(macro_availability_report.iloc[0]["macro_available_ratio"])
    min_ratio = float(thresholds.get("min_macro_available_ratio", 0.20))
    macro_cols = int(dataset_metadata.iloc[0]["macro_value_feature_columns"])
    min_macro_cols = int(thresholds.get("min_macro_value_feature_columns", 4))
    label = str(dataset_metadata.iloc[0]["dataset_label"])

    rows = [
        {
            "check": "Macro availability ratio passed",
            "passed": macro_ratio >= min_ratio,
            "detail": f"macro_available_ratio={macro_ratio:.4f}; min_ratio={min_ratio:.4f}",
        },
        {
            "check": "Macro value feature columns exist",
            "passed": macro_cols >= min_macro_cols,
            "detail": f"macro_value_feature_columns={macro_cols}",
        },
        {
            "check": "Dataset label is multi-factor after repair",
            "passed": label == str(thresholds.get("required_dataset_label")),
            "detail": f"dataset_label={label}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13r_dataset_quality_check(
    *,
    dataset: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    min_rows = int(thresholds.get("min_dataset_rows", 100))
    min_value_cols = int(thresholds.get("min_value_feature_columns", 8))
    value_cols = [col for col in dataset.columns if col.startswith("value__")]

    rows = [
        {
            "check": "Dataset has enough rows",
            "passed": len(dataset) >= min_rows,
            "detail": f"rows={len(dataset)}; min_rows={min_rows}",
        },
        {
            "check": "Dataset has enough value feature columns",
            "passed": len(value_cols) >= min_value_cols,
            "detail": f"value_feature_columns={len(value_cols)}",
        },
        {
            "check": "Dataset has honest label",
            "passed": "dataset_label" in dataset.columns
            and dataset["dataset_label"].astype(str).eq(
                str(thresholds.get("required_dataset_label"))
            ).all(),
            "detail": "dataset_label check",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13r_target_quality_check(
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
            "check": "Target availability ratio passed",
            "passed": ratio >= min_ratio,
            "detail": f"target_available_ratio={ratio:.4f}; min_ratio={min_ratio:.4f}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13r_split_quality_check(dataset: pd.DataFrame) -> pd.DataFrame:
    counts = (
        dataset["split_label"].value_counts().to_dict()
        if not dataset.empty and "split_label" in dataset.columns
        else {}
    )

    rows = [
        {
            "check": "Train split has rows",
            "passed": int(counts.get("train", 0)) > 0,
            "detail": f"train_rows={int(counts.get('train', 0))}",
        },
        {
            "check": "Validation split has rows",
            "passed": int(counts.get("validation", 0)) > 0,
            "detail": f"validation_rows={int(counts.get('validation', 0))}",
        },
        {
            "check": "Holdout split has rows",
            "passed": int(counts.get("holdout", 0)) > 0,
            "detail": f"holdout_rows={int(counts.get('holdout', 0))}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13r_forbidden_column_check(
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
                "frame": "reassembled_dataset",
                "matched_columns": "; ".join(matched),
                "passed": len(matched) == 0,
                "result": "Passed" if len(matched) == 0 else "Failed",
            }
        ]
    )


def build_phase13r_phase13s_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase13s_boundary", {})
    checks = [
        (
            "phase13s_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "pre-registration" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13s_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "model training execution"
            in str(boundary.get("forbidden_next_step", "")).lower()
            and "signal creation" in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13s_may_preregister_model_training",
            _bool_value(boundary.get("phase13s_may_preregister_model_training", False)),
            _bool_value(boundary.get("phase13s_may_preregister_model_training", False)),
        ),
        (
            "phase13s_may_train_model",
            _bool_value(boundary.get("phase13s_may_train_model", True)),
            not _bool_value(boundary.get("phase13s_may_train_model", True)),
        ),
        (
            "phase13s_may_create_signal",
            _bool_value(boundary.get("phase13s_may_create_signal", True)),
            not _bool_value(boundary.get("phase13s_may_create_signal", True)),
        ),
        (
            "phase13s_may_run_backtest",
            _bool_value(boundary.get("phase13s_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13s_may_run_backtest", True)),
        ),
        (
            "phase13s_may_promote_candidate",
            _bool_value(boundary.get("phase13s_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13s_may_promote_candidate", True)),
        ),
    ]

    out = pd.DataFrame(
        [{"boundary_item": item, "value": value, "passed": passed} for item, value, passed in checks]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13r_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13q_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    macro_repair_quality_check: pd.DataFrame,
    dataset_quality_check: pd.DataFrame,
    target_quality_check: pd.DataFrame,
    split_quality_check: pd.DataFrame,
    forbidden_column_check: pd.DataFrame,
    phase13s_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13q_reports_present": bool(report_inventory_check["present"].all())
                if not report_inventory_check.empty
                else False,
                "phase13q_result_passed": bool(phase13q_result_check["passed"].all())
                if not phase13q_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "macro_repair_quality_passed": bool(
                    macro_repair_quality_check["passed"].all()
                )
                if not macro_repair_quality_check.empty
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
                "forbidden_column_check_passed": bool(
                    forbidden_column_check["passed"].all()
                )
                if not forbidden_column_check.empty
                else False,
                "phase13s_boundary_passed": bool(phase13s_boundary_check["passed"].all())
                if not phase13s_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "model_training": False,
                "model_selection": False,
                "signal_creation": False,
                "strategy_backtest": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13r_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13R summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        phase_config.get("gates", {}).get(
            "required_audit_role",
            "Repaired macro dataset quality and leakage audit only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13Q reports are present",
            bool(row["phase13q_reports_present"]),
            f"phase13q_reports_present={bool(row['phase13q_reports_present'])}",
        ),
        _gate_row(
            "Phase 13Q conclusion and gates passed",
            bool(row["phase13q_result_passed"]),
            f"phase13q_result_passed={bool(row['phase13q_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Macro repair quality passed",
            bool(row["macro_repair_quality_passed"]),
            f"macro_repair_quality_passed={bool(row['macro_repair_quality_passed'])}",
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
            "No forbidden model/signal/backtest columns exist",
            bool(row["forbidden_column_check_passed"]),
            f"forbidden_column_check_passed={bool(row['forbidden_column_check_passed'])}",
        ),
        _gate_row(
            "Phase 13S boundary is pre-registration-only",
            bool(row["phase13s_boundary_passed"]),
            f"phase13s_boundary_passed={bool(row['phase13s_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks model/signal/backtest/promotion",
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


def build_phase13r_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — repaired macro dataset quality audit passed"
        if all_passed
        else "Failed repaired macro dataset quality audit"
    )
    interpretation = (
        "Phase 13R audited the repaired macro dataset, macro availability, dataset "
        "quality, target quality, split quality, forbidden columns, and boundaries. "
        "It did not train models, select models, create signals, run backtests, "
        "deploy paper trading, promote a candidate, or change the final candidate."
        if all_passed
        else "Phase 13R found a macro repair, dataset, target, split, forbidden-column, "
        "boundary, or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 13R",
                "diagnostic": "Repaired macro dataset quality audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def save_phase13r_repaired_macro_dataset_quality_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13r_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = phase_config.get("phase13q_reports", {})
    thresholds = phase_config.get("quality_thresholds", {})

    report_inventory_check = build_phase13r_report_inventory_check(phase_config)
    phase13q_result_check = build_phase13r_phase13q_result_check(phase_config)
    config_flag_check = build_phase13r_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )

    dataset = _read_csv_if_exists(reports.get("reassembled_dataset", ""))
    macro_availability_report = _read_csv_if_exists(
        reports.get("macro_availability_report", "")
    )
    dataset_metadata = _read_csv_if_exists(reports.get("dataset_metadata", ""))

    macro_repair_quality_check = build_phase13r_macro_repair_quality_check(
        macro_availability_report=macro_availability_report,
        dataset_metadata=dataset_metadata,
        thresholds=thresholds,
    )
    dataset_quality_check = build_phase13r_dataset_quality_check(
        dataset=dataset,
        thresholds=thresholds,
    )
    target_quality_check = build_phase13r_target_quality_check(
        dataset=dataset,
        thresholds=thresholds,
    )
    split_quality_check = build_phase13r_split_quality_check(dataset)
    forbidden_column_check = build_phase13r_forbidden_column_check(
        dataset=dataset,
        forbidden_columns=_as_list(thresholds.get("forbidden_columns")),
    )
    phase13s_boundary_check = build_phase13r_phase13s_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13r_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13q_result_check=phase13q_result_check,
        config_flag_check=config_flag_check,
        macro_repair_quality_check=macro_repair_quality_check,
        dataset_quality_check=dataset_quality_check,
        target_quality_check=target_quality_check,
        split_quality_check=split_quality_check,
        forbidden_column_check=forbidden_column_check,
        phase13s_boundary_check=phase13s_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13r_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13r_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13q_result_check": phase13q_result_check,
        "config_flag_check": config_flag_check,
        "macro_repair_quality_check": macro_repair_quality_check,
        "dataset_quality_check": dataset_quality_check,
        "target_quality_check": target_quality_check,
        "split_quality_check": split_quality_check,
        "forbidden_column_check": forbidden_column_check,
        "phase13s_boundary_check": phase13s_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13r_quality_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13R — Repaired Macro Dataset Quality Audit",
        sections={
            "Report Inventory Check": report_inventory_check,
            "Macro Repair Quality Check": macro_repair_quality_check,
            "Dataset Quality Check": dataset_quality_check,
            "Target Quality Check": target_quality_check,
            "Split Quality Check": split_quality_check,
            "Forbidden Column Check": forbidden_column_check,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path
        / "phase13r_repaired_macro_dataset_quality_audit.md",
    )

    print("Wrote Phase 13R repaired macro dataset quality audit reports.")
    return outputs