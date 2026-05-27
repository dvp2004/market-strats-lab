from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_PHASE13I_CONFIG: dict[str, Any] = {
    "enabled": False,
    "execution_role": "Technical and macro feature calculation execution only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13H",
    "proposed_next_phase": "Phase 13J",
    "allow_feature_calculation": True,
    "allow_feature_panel_creation": True,
    "allow_visual_feature_reports": True,
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "source_reports": {},
    "input_data": {},
    "calculation_policy": {
        "contract_version": "phase13g_v1",
        "source_version": "generated_from_existing_project_reports",
        "technical_decision_lag_trading_days": 1,
        "macro_decision_lag_trading_days": 1,
        "max_allowed_leakage_flags": 0,
        "min_registered_features": 8,
        "required_families": ["technical", "macro"],
        "required_feature_ids": [],
    },
    "phase13j_boundary": {},
    "gates": {
        "require_phase13h_passed": True,
        "require_input_sources_found": True,
        "require_registered_features_present": True,
        "min_registered_features": 8,
        "require_feature_panel_created": True,
        "require_required_feature_ids_present": True,
        "require_output_schema_columns_present": True,
        "require_visual_reports_created": True,
        "require_no_leakage_flags": True,
        "require_no_signal_columns": True,
        "require_no_model_columns": True,
        "require_phase13j_boundary_quality_audit_only": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_execution_role": (
            "Technical and macro feature calculation execution only"
        ),
    },
}


DEFAULT_PHASE13J_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Feature panel quality and leakage audit only",
    "phase_branch": "Phase 13 multi-factor model architecture planning",
    "source_phase": "Phase 13I",
    "proposed_next_phase": "Phase 13K",
    "allow_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_strategy_backtest": False,
    "allow_empirical_return_weights": False,
    "allow_model_training": False,
    "allow_paper_trading_deployment": False,
    "allow_candidate_promotion": False,
    "allow_final_candidate_change": False,
    "expected_runtime_flags": {},
    "phase13i_reports": {},
    "quality_thresholds": {
        "min_feature_ids": 8,
        "min_panel_rows": 100,
        "max_leakage_flags": 0,
        "min_available_state_ratio": 0.20,
        "allowed_feature_states": [
            "supportive",
            "neutral",
            "fragile",
            "unavailable",
            "blocked",
        ],
        "forbidden_columns": [],
    },
    "phase13k_boundary": {},
    "gates": {
        "require_phase13i_reports_present": True,
        "require_phase13i_conclusion_passed": True,
        "require_phase13i_gate_report_passed": True,
        "require_config_flags_clean_for_run": True,
        "require_feature_panel_quality": True,
        "require_output_schema_quality": True,
        "require_missingness_quality": True,
        "require_leakage_quality": True,
        "require_visual_reports_quality": True,
        "require_no_forbidden_columns": True,
        "require_phase13k_boundary_planning_only": True,
        "require_no_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_strategy_backtest": True,
        "require_no_empirical_return_weights": True,
        "require_no_model_training": True,
        "require_no_paper_trading_deployment": True,
        "require_no_candidate_promotion": True,
        "require_no_final_candidate_change": True,
        "required_audit_role": "Feature panel quality and leakage audit only",
    },
}


REQUIRED_FEATURE_PANEL_COLUMNS = [
    "as_of_date",
    "observation_date",
    "release_date",
    "availability_date",
    "decision_date",
    "family_id",
    "feature_id",
    "formula_id",
    "source_name",
    "source_version",
    "raw_inputs_available",
    "feature_value",
    "feature_state",
    "state_reason",
    "missingness_state",
    "leakage_flag",
    "contract_version",
]


FORBIDDEN_COLUMN_FRAGMENTS = [
    "signal",
    "allocation",
    "target_weight",
    "model_prediction",
    "predicted_return",
    "strategy_return",
    "backtest_return",
    "paper_trade",
]


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


def _get_phase13i_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13I_CONFIG,
        config.get("phase13i_feature_calculation_execution", {}),
    )


def _get_phase13j_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge_dict(
        DEFAULT_PHASE13J_CONFIG,
        config.get("phase13j_feature_panel_quality_leakage_audit", {}),
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
        date_like = [
            col for col in out.columns if "date" in str(col).lower()
        ]
        date_col = date_like[0] if date_like else out.columns[0]

    out = out.rename(columns={date_col: "as_of_date"})
    out["as_of_date"] = pd.to_datetime(out["as_of_date"], errors="coerce")
    out = out.dropna(subset=["as_of_date"])
    out = out.sort_values("as_of_date").drop_duplicates("as_of_date")
    return out.reset_index(drop=True)


def _find_close_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in frame.columns:
            return col

    for col in frame.columns:
        clean = str(col).lower()
        if clean in {"close", "adj close", "adjusted_close", "adj_close"}:
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

        if close_col is not None:
            out = candidate[["as_of_date", close_col]].copy()
            out = out.rename(columns={close_col: "adjusted_close"})
            out["adjusted_close"] = pd.to_numeric(
                out["adjusted_close"],
                errors="coerce",
            )
            out = out.dropna(subset=["adjusted_close"])
            if len(out) > 0:
                return out, "in_memory_run_backtest_outputs"

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


def _load_macro_frame(phase_config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    input_config = phase_config.get("input_data", {})
    date_candidates = _as_list(input_config.get("date_column_candidates"))
    paths = [str(path) for path in _as_list(input_config.get("macro_aligned_candidates"))]
    frame, source_path = _load_first_existing_csv(paths)

    if frame.empty:
        return pd.DataFrame(), ""

    out = _normalise_date_column(frame, date_candidates)
    macro_cols = input_config.get("macro_columns", {})

    required = [
        str(macro_cols.get("dgs2", "DGS2")),
        str(macro_cols.get("dgs10", "DGS10")),
        str(macro_cols.get("cpi", "CPIAUCSL")),
        str(macro_cols.get("unrate", "UNRATE")),
    ]

    for col in required:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")

    return out[["as_of_date", *required]].reset_index(drop=True), source_path


def build_phase13i_source_report_check(phase_config: dict[str, Any]) -> pd.DataFrame:
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


def build_phase13i_phase13h_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("source_reports", {})
    conclusion = _read_csv_if_exists(reports.get("phase13h_conclusion", ""))
    gate_report = _read_csv_if_exists(reports.get("phase13h_gate_report", ""))

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
                "check": "Phase 13H conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13H gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13i_input_source_check(
    *,
    price_frame: pd.DataFrame,
    price_source: str,
    macro_frame: pd.DataFrame,
    macro_source: str,
) -> pd.DataFrame:
    rows = [
        {
            "source_type": "technical_price",
            "source": price_source,
            "found": not price_frame.empty,
            "rows": int(len(price_frame)),
            "start_date": str(price_frame["as_of_date"].min().date())
            if not price_frame.empty
            else "",
            "end_date": str(price_frame["as_of_date"].max().date())
            if not price_frame.empty
            else "",
        },
        {
            "source_type": "macro_aligned",
            "source": macro_source,
            "found": not macro_frame.empty,
            "rows": int(len(macro_frame)),
            "start_date": str(macro_frame["as_of_date"].min().date())
            if not macro_frame.empty
            else "",
            "end_date": str(macro_frame["as_of_date"].max().date())
            if not macro_frame.empty
            else "",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["found"].map({True: "Passed", False: "Failed"})
    return out


def _next_business_day(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series) + pd.offsets.BDay(1)


def _state_from_threshold(
    value: float | None,
    *,
    supportive: bool,
    neutral: bool,
    missing_reason: str,
) -> tuple[str, str]:
    if value is None or pd.isna(value):
        return "unavailable", missing_reason

    if supportive:
        return "supportive", "value passed supportive threshold"

    if neutral:
        return "neutral", "value fell inside neutral threshold"

    return "fragile", "value breached fragile threshold"


def _feature_rows(
    *,
    frame: pd.DataFrame,
    family_id: str,
    feature_id: str,
    formula_id: str,
    value_col: str,
    state_col: str,
    state_reason_col: str,
    source_name: str,
    source_version: str,
    contract_version: str,
) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "as_of_date": frame["as_of_date"],
            "observation_date": frame["as_of_date"],
            "release_date": pd.NaT,
            "availability_date": frame["as_of_date"],
            "decision_date": _next_business_day(frame["as_of_date"]),
            "family_id": family_id,
            "feature_id": feature_id,
            "formula_id": formula_id,
            "source_name": source_name,
            "source_version": source_version,
            "raw_inputs_available": frame[value_col].notna(),
            "feature_value": frame[value_col],
            "feature_state": frame[state_col],
            "state_reason": frame[state_reason_col],
            "missingness_state": np.where(frame[value_col].notna(), "available", "unavailable"),
            "leakage_flag": False,
            "contract_version": contract_version,
        }
    )
    return out


def _calculate_technical_features(
    price_frame: pd.DataFrame,
    *,
    source_name: str,
    source_version: str,
    contract_version: str,
) -> pd.DataFrame:
    if price_frame.empty:
        return pd.DataFrame(columns=REQUIRED_FEATURE_PANEL_COLUMNS)

    frame = price_frame.copy()
    frame["adjusted_close"] = pd.to_numeric(frame["adjusted_close"], errors="coerce")
    frame = frame.dropna(subset=["adjusted_close"]).sort_values("as_of_date")
    frame["return_1d"] = frame["adjusted_close"].pct_change()

    frame["technical_trend_distance"] = (
        frame["adjusted_close"] / frame["adjusted_close"].rolling(200).mean() - 1
    )
    frame["technical_momentum_252d"] = (
        frame["adjusted_close"] / frame["adjusted_close"].shift(252) - 1
    )
    frame["technical_volatility_63d_ann"] = (
        frame["return_1d"].rolling(63).std() * np.sqrt(252)
    )
    frame["technical_drawdown_252d"] = (
        frame["adjusted_close"] / frame["adjusted_close"].rolling(252).max() - 1
    )

    state_specs = [
        (
            "technical_trend_state",
            "trend_price_vs_sma_200",
            "technical_trend_distance",
            lambda x: x > 0.00,
            lambda x: -0.05 <= x <= 0.00,
            "insufficient 200-day trend history",
        ),
        (
            "technical_momentum_state",
            "momentum_252d_total_return",
            "technical_momentum_252d",
            lambda x: x > 0.00,
            lambda x: -0.10 <= x <= 0.00,
            "insufficient 252-day momentum history",
        ),
        (
            "technical_volatility_state",
            "volatility_63d_annualised",
            "technical_volatility_63d_ann",
            lambda x: x < 0.15,
            lambda x: 0.15 <= x <= 0.25,
            "insufficient 63-day volatility history",
        ),
        (
            "technical_drawdown_state",
            "drawdown_from_252d_high",
            "technical_drawdown_252d",
            lambda x: x > -0.05,
            lambda x: -0.15 <= x <= -0.05,
            "insufficient 252-day drawdown history",
        ),
    ]

    rows = []

    for feature_id, formula_id, value_col, supportive_fn, neutral_fn, missing in state_specs:
        state_col = f"{feature_id}_calc_state"
        reason_col = f"{feature_id}_state_reason"

        states = [
            _state_from_threshold(
                value,
                supportive=False if pd.isna(value) else supportive_fn(float(value)),
                neutral=False if pd.isna(value) else neutral_fn(float(value)),
                missing_reason=missing,
            )
            for value in frame[value_col]
        ]

        frame[state_col] = [state for state, _ in states]
        frame[reason_col] = [reason for _, reason in states]

        rows.append(
            _feature_rows(
                frame=frame,
                family_id="technical",
                feature_id=feature_id,
                formula_id=formula_id,
                value_col=value_col,
                state_col=state_col,
                state_reason_col=reason_col,
                source_name=source_name,
                source_version=source_version,
                contract_version=contract_version,
            )
        )

    return pd.concat(rows, ignore_index=True)[REQUIRED_FEATURE_PANEL_COLUMNS]


def _calculate_macro_features(
    macro_frame: pd.DataFrame,
    *,
    source_name: str,
    source_version: str,
    contract_version: str,
    macro_columns: dict[str, str],
) -> pd.DataFrame:
    if macro_frame.empty:
        return pd.DataFrame(columns=REQUIRED_FEATURE_PANEL_COLUMNS)

    frame = macro_frame.copy().sort_values("as_of_date")
    dgs2 = str(macro_columns.get("dgs2", "DGS2"))
    dgs10 = str(macro_columns.get("dgs10", "DGS10"))
    cpi = str(macro_columns.get("cpi", "CPIAUCSL"))
    unrate = str(macro_columns.get("unrate", "UNRATE"))

    frame["macro_dgs2_level"] = frame[dgs2]
    frame["macro_dgs10_minus_dgs2"] = frame[dgs10] - frame[dgs2]
    frame["macro_cpi_yoy"] = frame[cpi] / frame[cpi].shift(252) - 1
    frame["macro_unrate_3m_change"] = frame[unrate] - frame[unrate].shift(63)

    state_specs = [
        (
            "macro_short_rate_state",
            "dgs2_level_regime",
            "macro_dgs2_level",
            lambda x: x < 2.50,
            lambda x: 2.50 <= x <= 4.50,
            "DGS2 unavailable after lag",
        ),
        (
            "macro_yield_curve_state",
            "dgs10_minus_dgs2_curve_regime",
            "macro_dgs10_minus_dgs2",
            lambda x: x > 0.50,
            lambda x: -0.50 <= x <= 0.50,
            "DGS10 or DGS2 unavailable after lag",
        ),
        (
            "macro_inflation_state",
            "cpi_yoy_inflation_regime",
            "macro_cpi_yoy",
            lambda x: x < 0.03,
            lambda x: 0.03 <= x <= 0.05,
            "CPI current or 12-month comparison unavailable",
        ),
        (
            "macro_labour_state",
            "unrate_level_and_3m_change_regime",
            "macro_unrate_3m_change",
            lambda x: False,
            lambda x: True,
            "UNRATE current or 3-month comparison unavailable",
        ),
    ]

    rows = []

    for feature_id, formula_id, value_col, supportive_fn, neutral_fn, missing in state_specs:
        state_col = f"{feature_id}_calc_state"
        reason_col = f"{feature_id}_state_reason"

        states = []

        for idx, value in enumerate(frame[value_col]):
            if feature_id == "macro_labour_state":
                current_unrate = frame[unrate].iloc[idx]
                change = value

                if pd.isna(current_unrate) or pd.isna(change):
                    states.append(("unavailable", missing))
                elif current_unrate < 5.00 and change <= 0.00:
                    states.append(("supportive", "low and non-rising unemployment"))
                elif current_unrate >= 6.00 or change > 0.50:
                    states.append(("fragile", "high or quickly rising unemployment"))
                else:
                    states.append(("neutral", "labour state inside neutral band"))
                continue

            states.append(
                _state_from_threshold(
                    value,
                    supportive=False if pd.isna(value) else supportive_fn(float(value)),
                    neutral=False if pd.isna(value) else neutral_fn(float(value)),
                    missing_reason=missing,
                )
            )

        frame[state_col] = [state for state, _ in states]
        frame[reason_col] = [reason for _, reason in states]

        rows.append(
            _feature_rows(
                frame=frame,
                family_id="macro",
                feature_id=feature_id,
                formula_id=formula_id,
                value_col=value_col,
                state_col=state_col,
                state_reason_col=reason_col,
                source_name=source_name,
                source_version=source_version,
                contract_version=contract_version,
            )
        )

    return pd.concat(rows, ignore_index=True)[REQUIRED_FEATURE_PANEL_COLUMNS]


def build_phase13i_feature_panel(
    *,
    price_frame: pd.DataFrame,
    macro_frame: pd.DataFrame,
    price_source: str,
    macro_source: str,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    policy = phase_config.get("calculation_policy", {})
    input_data = phase_config.get("input_data", {})
    contract_version = str(policy.get("contract_version", "phase13g_v1"))
    source_version = str(policy.get("source_version", "project_reports"))

    technical = _calculate_technical_features(
        price_frame,
        source_name=price_source or "missing_price_source",
        source_version=source_version,
        contract_version=contract_version,
    )
    macro = _calculate_macro_features(
        macro_frame,
        source_name=macro_source or "missing_macro_source",
        source_version=source_version,
        contract_version=contract_version,
        macro_columns=input_data.get("macro_columns", {}),
    )

    panel = pd.concat([technical, macro], ignore_index=True)

    if panel.empty:
        return pd.DataFrame(columns=REQUIRED_FEATURE_PANEL_COLUMNS)

    for col in [
        "as_of_date",
        "observation_date",
        "release_date",
        "availability_date",
        "decision_date",
    ]:
        panel[col] = pd.to_datetime(panel[col], errors="coerce").dt.date

    return panel[REQUIRED_FEATURE_PANEL_COLUMNS]


def build_phase13i_visual_reports(
    feature_panel: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    if feature_panel.empty:
        empty = pd.DataFrame()
        return {
            "feature_state_timeline": empty,
            "feature_availability_heatmap": empty,
            "leakage_audit_panel": empty,
            "model_feature_matrix_preview": empty,
            "decision_rationale_template": empty,
        }

    timeline = feature_panel.pivot_table(
        index="as_of_date",
        columns="feature_id",
        values="feature_state",
        aggfunc="first",
    ).reset_index()

    availability = feature_panel.copy()
    availability["is_available"] = availability["missingness_state"].eq("available")
    availability = availability.pivot_table(
        index="as_of_date",
        columns="feature_id",
        values="is_available",
        aggfunc="first",
    ).reset_index()

    leakage = feature_panel[
        [
            "as_of_date",
            "observation_date",
            "release_date",
            "availability_date",
            "decision_date",
            "family_id",
            "feature_id",
            "leakage_flag",
        ]
    ].copy()

    matrix_preview = feature_panel.pivot_table(
        index="as_of_date",
        columns="feature_id",
        values="feature_value",
        aggfunc="first",
    ).reset_index()

    rationale = feature_panel[
        [
            "decision_date",
            "family_id",
            "feature_id",
            "feature_state",
            "state_reason",
            "missingness_state",
        ]
    ].copy()

    return {
        "feature_state_timeline": timeline,
        "feature_availability_heatmap": availability,
        "leakage_audit_panel": leakage,
        "model_feature_matrix_preview": matrix_preview,
        "decision_rationale_template": rationale,
    }


def _forbidden_columns(frame: pd.DataFrame) -> list[str]:
    columns = [str(col) for col in frame.columns]
    return [
        col
        for col in columns
        if any(fragment in col.lower() for fragment in FORBIDDEN_COLUMN_FRAGMENTS)
    ]


def build_phase13i_phase13j_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13j_boundary", {})
    checks = [
        (
            "phase13j_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "quality" in str(boundary.get("allowed_next_step", "")).lower()
            and "leakage" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13j_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "signal creation" in str(boundary.get("forbidden_next_step", "")).lower()
            and "model training" in str(boundary.get("forbidden_next_step", "")).lower()
            and "strategy backtest"
            in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13j_may_audit_feature_panel",
            _bool_value(boundary.get("phase13j_may_audit_feature_panel", False)),
            _bool_value(boundary.get("phase13j_may_audit_feature_panel", False)),
        ),
        (
            "phase13j_may_audit_leakage",
            _bool_value(boundary.get("phase13j_may_audit_leakage", False)),
            _bool_value(boundary.get("phase13j_may_audit_leakage", False)),
        ),
        (
            "phase13j_may_create_signal",
            _bool_value(boundary.get("phase13j_may_create_signal", True)),
            not _bool_value(boundary.get("phase13j_may_create_signal", True)),
        ),
        (
            "phase13j_may_train_model",
            _bool_value(boundary.get("phase13j_may_train_model", True)),
            not _bool_value(boundary.get("phase13j_may_train_model", True)),
        ),
        (
            "phase13j_may_run_backtest",
            _bool_value(boundary.get("phase13j_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13j_may_run_backtest", True)),
        ),
        (
            "phase13j_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13j_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13j_may_deploy_paper_trading", True)),
        ),
        (
            "phase13j_may_promote_candidate",
            _bool_value(boundary.get("phase13j_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13j_may_promote_candidate", True)),
        ),
    ]
    out = pd.DataFrame(
        [
            {"boundary_item": item, "value": value, "passed": passed}
            for item, value, passed in checks
        ]
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


def build_phase13i_summary(
    *,
    phase_config: dict[str, Any],
    source_report_check: pd.DataFrame,
    phase13h_result_check: pd.DataFrame,
    input_source_check: pd.DataFrame,
    feature_panel: pd.DataFrame,
    visual_reports: dict[str, pd.DataFrame],
    phase13j_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    policy = phase_config.get("calculation_policy", {})
    required_ids = set(_as_list(policy.get("required_feature_ids")))
    actual_ids = (
        set(feature_panel["feature_id"].dropna().astype(str).tolist())
        if not feature_panel.empty
        else set()
    )
    leakage_flags = (
        int(feature_panel["leakage_flag"].map(_bool_value).sum())
        if not feature_panel.empty
        else 0
    )
    forbidden = _forbidden_columns(feature_panel)

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
                "phase13h_result_passed": bool(phase13h_result_check["passed"].all())
                if not phase13h_result_check.empty
                else False,
                "input_sources_found": bool(input_source_check["found"].all())
                if not input_source_check.empty
                else False,
                "feature_panel_rows": int(len(feature_panel)),
                "feature_id_count": int(len(actual_ids)),
                "required_feature_ids_present": required_ids.issubset(actual_ids),
                "output_schema_columns_present": set(
                    REQUIRED_FEATURE_PANEL_COLUMNS
                ).issubset(set(feature_panel.columns)),
                "leakage_flag_count": leakage_flags,
                "visual_report_count": int(
                    sum(not frame.empty for frame in visual_reports.values())
                ),
                "forbidden_columns": "; ".join(forbidden),
                "no_forbidden_columns": len(forbidden) == 0,
                "phase13j_boundary_passed": bool(
                    phase13j_boundary_check["passed"].all()
                )
                if not phase13j_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "signal_creation": False,
                "strategy_backtest": False,
                "model_training": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13i_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13I summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get(
            "required_execution_role",
            "Technical and macro feature calculation execution only",
        )
    )

    rows = [
        _gate_row(
            "Phase 13H passed",
            (not gates.get("require_phase13h_passed", True))
            or bool(row["phase13h_result_passed"]),
            f"phase13h_result_passed={bool(row['phase13h_result_passed'])}",
        ),
        _gate_row(
            "Input sources were found",
            (not gates.get("require_input_sources_found", True))
            or bool(row["input_sources_found"]),
            f"input_sources_found={bool(row['input_sources_found'])}",
        ),
        _gate_row(
            "Feature panel was created",
            (not gates.get("require_feature_panel_created", True))
            or int(row["feature_panel_rows"]) > 0,
            f"feature_panel_rows={int(row['feature_panel_rows'])}",
        ),
        _gate_row(
            "Required feature IDs are present",
            (not gates.get("require_required_feature_ids_present", True))
            or bool(row["required_feature_ids_present"]),
            f"required_feature_ids_present={bool(row['required_feature_ids_present'])}",
        ),
        _gate_row(
            "Output schema columns are present",
            (not gates.get("require_output_schema_columns_present", True))
            or bool(row["output_schema_columns_present"]),
            f"output_schema_columns_present={bool(row['output_schema_columns_present'])}",
        ),
        _gate_row(
            "Visual reports were created",
            (not gates.get("require_visual_reports_created", True))
            or int(row["visual_report_count"]) >= 5,
            f"visual_report_count={int(row['visual_report_count'])}",
        ),
        _gate_row(
            "No leakage flags are present",
            (not gates.get("require_no_leakage_flags", True))
            or int(row["leakage_flag_count"]) == 0,
            f"leakage_flag_count={int(row['leakage_flag_count'])}",
        ),
        _gate_row(
            "No forbidden signal/model/backtest columns exist",
            bool(row["no_forbidden_columns"]),
            f"forbidden_columns={row['forbidden_columns']}",
        ),
        _gate_row(
            "Phase 13J boundary is quality-audit-only",
            (not gates.get("require_phase13j_boundary_quality_audit_only", True))
            or bool(row["phase13j_boundary_passed"]),
            f"phase13j_boundary_passed={bool(row['phase13j_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks signal/model/backtest/paper-trading/promotion",
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


def build_phase13i_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — feature calculation execution passed"
        if all_passed
        else "Failed feature calculation execution"
    )
    interpretation = (
        "Phase 13I calculated technical and macro feature panels, feature states, "
        "availability/missingness outputs, leakage audit outputs, and visual feature "
        "reports. It did not create signals, allocation rules, models, strategy "
        "backtests, paper-trading logic, candidate promotion, or final-candidate "
        "changes."
        if all_passed
        else "Phase 13I found an input, feature-panel, leakage, visual-report, "
        "boundary, or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 13I",
                "diagnostic": "Feature calculation execution",
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


def save_phase13i_feature_calculation_execution(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: Any | None = None,
    ticker_outputs: Any | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13i_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_report_check = build_phase13i_source_report_check(phase_config)
    phase13h_result_check = build_phase13i_phase13h_result_check(phase_config)
    price_frame, price_source = _load_price_frame(
        phase_config=phase_config,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
    )
    macro_frame, macro_source = _load_macro_frame(phase_config)

    input_source_check = build_phase13i_input_source_check(
        price_frame=price_frame,
        price_source=price_source,
        macro_frame=macro_frame,
        macro_source=macro_source,
    )
    feature_panel = build_phase13i_feature_panel(
        price_frame=price_frame,
        macro_frame=macro_frame,
        price_source=price_source,
        macro_source=macro_source,
        phase_config=phase_config,
    )
    visual_reports = build_phase13i_visual_reports(feature_panel)
    phase13j_boundary_check = build_phase13i_phase13j_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13i_summary(
        phase_config=phase_config,
        source_report_check=source_report_check,
        phase13h_result_check=phase13h_result_check,
        input_source_check=input_source_check,
        feature_panel=feature_panel,
        visual_reports=visual_reports,
        phase13j_boundary_check=phase13j_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13i_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13i_conclusion(gate_report)

    outputs = {
        "input_source_check": input_source_check,
        "feature_panel": feature_panel,
        **visual_reports,
        "source_report_check": source_report_check,
        "phase13h_result_check": phase13h_result_check,
        "phase13j_boundary_check": phase13j_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13i_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13I — Feature Calculation Execution",
        sections={
            "Input Source Check": input_source_check,
            "Feature Panel Sample": feature_panel.head(25),
            "Feature State Timeline Sample": visual_reports[
                "feature_state_timeline"
            ].head(25),
            "Leakage Audit Panel Sample": visual_reports[
                "leakage_audit_panel"
            ].head(25),
            "Summary": summary,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path / "phase13i_feature_calculation_execution.md",
    )

    print("Wrote Phase 13I feature calculation execution reports.")
    return outputs


def build_phase13j_report_inventory_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for report_key, path in phase_config.get("phase13i_reports", {}).items():
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


def build_phase13j_phase13i_result_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    reports = phase_config.get("phase13i_reports", {})
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
                "check": "Phase 13I conclusion passed",
                "passed": conclusion_passed,
                "detail": str(conclusion.iloc[0].get("verdict", ""))
                if not conclusion.empty
                else "missing",
            },
            {
                "check": "Phase 13I gate report passed",
                "passed": gate_report_passed,
                "detail": f"gate_rows={len(gate_report)}",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13j_config_flag_check(
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


def build_phase13j_feature_panel_quality_check(
    *,
    feature_panel: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    min_rows = int(thresholds.get("min_panel_rows", 100))
    min_features = int(thresholds.get("min_feature_ids", 8))

    feature_ids = (
        set(feature_panel["feature_id"].dropna().astype(str).tolist())
        if not feature_panel.empty and "feature_id" in feature_panel.columns
        else set()
    )
    available_ratio = (
        float(feature_panel["missingness_state"].eq("available").mean())
        if not feature_panel.empty and "missingness_state" in feature_panel.columns
        else 0.0
    )

    rows = [
        {
            "check": "Feature panel has enough rows",
            "passed": len(feature_panel) >= min_rows,
            "detail": f"rows={len(feature_panel)}; min_rows={min_rows}",
        },
        {
            "check": "Feature panel has enough feature IDs",
            "passed": len(feature_ids) >= min_features,
            "detail": f"feature_ids={len(feature_ids)}; min_features={min_features}",
        },
        {
            "check": "Available-state ratio is acceptable",
            "passed": available_ratio >= float(
                thresholds.get("min_available_state_ratio", 0.20)
            ),
            "detail": f"available_ratio={available_ratio:.4f}",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13j_output_schema_quality_check(feature_panel: pd.DataFrame) -> pd.DataFrame:
    actual = set(feature_panel.columns)
    required = set(REQUIRED_FEATURE_PANEL_COLUMNS)

    rows = [
        {
            "check": "Required feature-panel columns present",
            "passed": required.issubset(actual),
            "detail": "missing=" + "; ".join(sorted(required - actual)),
        },
        {
            "check": "Feature states use allowed categorical states",
            "passed": set(feature_panel.get("feature_state", pd.Series(dtype=str)))
            .difference(
                {"supportive", "neutral", "fragile", "unavailable", "blocked"}
            )
            == set(),
            "detail": "feature_state vocabulary check",
        },
        {
            "check": "Leakage flag column is boolean-compatible",
            "passed": feature_panel.get("leakage_flag", pd.Series(dtype=bool))
            .map(_bool_value)
            .isin([True, False])
            .all(),
            "detail": "leakage_flag boolean compatibility",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13j_missingness_quality_check(feature_panel: pd.DataFrame) -> pd.DataFrame:
    missingness = (
        set(feature_panel["missingness_state"].dropna().astype(str).tolist())
        if not feature_panel.empty and "missingness_state" in feature_panel.columns
        else set()
    )
    allowed = {"available", "missing", "stale", "unavailable", "blocked"}

    rows = [
        {
            "check": "Missingness states use allowed vocabulary",
            "passed": missingness.issubset(allowed),
            "detail": "states=" + "; ".join(sorted(missingness)),
        },
        {
            "check": "Unavailable rows have state reasons",
            "passed": bool(
                feature_panel.loc[
                    feature_panel["missingness_state"].astype(str) != "available",
                    "state_reason",
                ]
                .astype(str)
                .str.len()
                .gt(0)
                .all()
            )
            if not feature_panel.empty
            else False,
            "detail": "unavailable rows must explain missingness",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13j_leakage_quality_check(
    *,
    feature_panel: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    max_flags = int(thresholds.get("max_leakage_flags", 0))
    flags = (
        int(feature_panel["leakage_flag"].map(_bool_value).sum())
        if not feature_panel.empty and "leakage_flag" in feature_panel.columns
        else 999999
    )

    rows = [
        {
            "check": "Leakage flag count is acceptable",
            "passed": flags <= max_flags,
            "detail": f"leakage_flags={flags}; max_allowed={max_flags}",
        },
        {
            "check": "Decision date is after or equal to availability date",
            "passed": bool(
                (
                    pd.to_datetime(feature_panel["decision_date"])
                    >= pd.to_datetime(feature_panel["availability_date"])
                ).all()
            )
            if not feature_panel.empty
            else False,
            "detail": "decision_date >= availability_date",
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13j_visual_reports_quality_check(
    visual_reports: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    required = [
        "feature_state_timeline",
        "feature_availability_heatmap",
        "leakage_audit_panel",
        "model_feature_matrix_preview",
        "decision_rationale_template",
    ]

    rows = [
        {
            "report": name,
            "present": name in visual_reports,
            "rows": int(len(visual_reports.get(name, pd.DataFrame()))),
            "passed": name in visual_reports
            and not visual_reports.get(name, pd.DataFrame()).empty,
        }
        for name in required
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13j_forbidden_column_check(
    *,
    frames: dict[str, pd.DataFrame],
    forbidden_columns: list[str],
) -> pd.DataFrame:
    fragments = [str(item).lower() for item in forbidden_columns]
    rows = []

    for frame_name, frame in frames.items():
        matched = [
            str(col)
            for col in frame.columns
            if any(fragment in str(col).lower() for fragment in fragments)
        ]
        rows.append(
            {
                "frame": frame_name,
                "matched_columns": "; ".join(matched),
                "passed": len(matched) == 0,
                "result": "Passed" if len(matched) == 0 else "Failed",
            }
        )

    return pd.DataFrame(rows)


def build_phase13j_phase13k_boundary_check(
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    boundary = phase_config.get("phase13k_boundary", {})
    checks = [
        (
            "phase13k_allowed_next_step",
            str(boundary.get("allowed_next_step", "")),
            "planning" in str(boundary.get("allowed_next_step", "")).lower(),
        ),
        (
            "phase13k_forbidden_next_step",
            str(boundary.get("forbidden_next_step", "")),
            "signal creation" in str(boundary.get("forbidden_next_step", "")).lower()
            and "model training" in str(boundary.get("forbidden_next_step", "")).lower()
            and "strategy backtest"
            in str(boundary.get("forbidden_next_step", "")).lower(),
        ),
        (
            "phase13k_may_interpret_features",
            _bool_value(boundary.get("phase13k_may_interpret_features", False)),
            _bool_value(boundary.get("phase13k_may_interpret_features", False)),
        ),
        (
            "phase13k_may_plan_model_dataset",
            _bool_value(boundary.get("phase13k_may_plan_model_dataset", False)),
            _bool_value(boundary.get("phase13k_may_plan_model_dataset", False)),
        ),
        (
            "phase13k_may_create_signal",
            _bool_value(boundary.get("phase13k_may_create_signal", True)),
            not _bool_value(boundary.get("phase13k_may_create_signal", True)),
        ),
        (
            "phase13k_may_train_model",
            _bool_value(boundary.get("phase13k_may_train_model", True)),
            not _bool_value(boundary.get("phase13k_may_train_model", True)),
        ),
        (
            "phase13k_may_run_backtest",
            _bool_value(boundary.get("phase13k_may_run_backtest", True)),
            not _bool_value(boundary.get("phase13k_may_run_backtest", True)),
        ),
        (
            "phase13k_may_deploy_paper_trading",
            _bool_value(boundary.get("phase13k_may_deploy_paper_trading", True)),
            not _bool_value(boundary.get("phase13k_may_deploy_paper_trading", True)),
        ),
        (
            "phase13k_may_promote_candidate",
            _bool_value(boundary.get("phase13k_may_promote_candidate", True)),
            not _bool_value(boundary.get("phase13k_may_promote_candidate", True)),
        ),
    ]
    out = pd.DataFrame(
        [
            {"boundary_item": item, "value": value, "passed": passed}
            for item, value, passed in checks
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def build_phase13j_summary(
    *,
    phase_config: dict[str, Any],
    report_inventory_check: pd.DataFrame,
    phase13i_result_check: pd.DataFrame,
    config_flag_check: pd.DataFrame,
    feature_panel_quality_check: pd.DataFrame,
    output_schema_quality_check: pd.DataFrame,
    missingness_quality_check: pd.DataFrame,
    leakage_quality_check: pd.DataFrame,
    visual_reports_quality_check: pd.DataFrame,
    forbidden_column_check: pd.DataFrame,
    phase13k_boundary_check: pd.DataFrame,
    scope_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "phase_branch": str(phase_config.get("phase_branch", "")),
                "source_phase": str(phase_config.get("source_phase", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "phase13i_reports_present": bool(
                    report_inventory_check["present"].all()
                )
                if not report_inventory_check.empty
                else False,
                "phase13i_result_passed": bool(phase13i_result_check["passed"].all())
                if not phase13i_result_check.empty
                else False,
                "config_flags_clean_for_run": bool(config_flag_check["passed"].all())
                if not config_flag_check.empty
                else False,
                "feature_panel_quality_passed": bool(
                    feature_panel_quality_check["passed"].all()
                )
                if not feature_panel_quality_check.empty
                else False,
                "output_schema_quality_passed": bool(
                    output_schema_quality_check["passed"].all()
                )
                if not output_schema_quality_check.empty
                else False,
                "missingness_quality_passed": bool(
                    missingness_quality_check["passed"].all()
                )
                if not missingness_quality_check.empty
                else False,
                "leakage_quality_passed": bool(leakage_quality_check["passed"].all())
                if not leakage_quality_check.empty
                else False,
                "visual_reports_quality_passed": bool(
                    visual_reports_quality_check["passed"].all()
                )
                if not visual_reports_quality_check.empty
                else False,
                "forbidden_column_check_passed": bool(
                    forbidden_column_check["passed"].all()
                )
                if not forbidden_column_check.empty
                else False,
                "phase13k_boundary_passed": bool(
                    phase13k_boundary_check["passed"].all()
                )
                if not phase13k_boundary_check.empty
                else False,
                "scope_boundary_passed": bool(scope_boundary_check["passed"].all())
                if not scope_boundary_check.empty
                else False,
                "signal_creation": False,
                "strategy_backtest": False,
                "model_training": False,
                "paper_trading_deployment": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def build_phase13j_gate_report(
    *,
    phase_config: dict[str, Any],
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame([_gate_row("Phase 13J summary exists", False, "No summary.")])

    row = summary.iloc[0]
    required_role = str(
        gates.get("required_audit_role", "Feature panel quality and leakage audit only")
    )

    rows = [
        _gate_row(
            "Phase 13I reports are present",
            (not gates.get("require_phase13i_reports_present", True))
            or bool(row["phase13i_reports_present"]),
            f"phase13i_reports_present={bool(row['phase13i_reports_present'])}",
        ),
        _gate_row(
            "Phase 13I conclusion and gates passed",
            (
                (not gates.get("require_phase13i_conclusion_passed", True))
                or bool(row["phase13i_result_passed"])
            )
            and (
                (not gates.get("require_phase13i_gate_report_passed", True))
                or bool(row["phase13i_result_passed"])
            ),
            f"phase13i_result_passed={bool(row['phase13i_result_passed'])}",
        ),
        _gate_row(
            "Config flags are clean for run",
            (not gates.get("require_config_flags_clean_for_run", True))
            or bool(row["config_flags_clean_for_run"]),
            f"config_flags_clean_for_run={bool(row['config_flags_clean_for_run'])}",
        ),
        _gate_row(
            "Feature panel quality passed",
            (not gates.get("require_feature_panel_quality", True))
            or bool(row["feature_panel_quality_passed"]),
            f"feature_panel_quality_passed={bool(row['feature_panel_quality_passed'])}",
        ),
        _gate_row(
            "Output schema quality passed",
            (not gates.get("require_output_schema_quality", True))
            or bool(row["output_schema_quality_passed"]),
            f"output_schema_quality_passed={bool(row['output_schema_quality_passed'])}",
        ),
        _gate_row(
            "Missingness quality passed",
            (not gates.get("require_missingness_quality", True))
            or bool(row["missingness_quality_passed"]),
            f"missingness_quality_passed={bool(row['missingness_quality_passed'])}",
        ),
        _gate_row(
            "Leakage quality passed",
            (not gates.get("require_leakage_quality", True))
            or bool(row["leakage_quality_passed"]),
            f"leakage_quality_passed={bool(row['leakage_quality_passed'])}",
        ),
        _gate_row(
            "Visual reports quality passed",
            (not gates.get("require_visual_reports_quality", True))
            or bool(row["visual_reports_quality_passed"]),
            f"visual_reports_quality_passed={bool(row['visual_reports_quality_passed'])}",
        ),
        _gate_row(
            "No forbidden signal/model/backtest columns exist",
            (not gates.get("require_no_forbidden_columns", True))
            or bool(row["forbidden_column_check_passed"]),
            f"forbidden_column_check_passed={bool(row['forbidden_column_check_passed'])}",
        ),
        _gate_row(
            "Phase 13K boundary is planning-only",
            (not gates.get("require_phase13k_boundary_planning_only", True))
            or bool(row["phase13k_boundary_passed"]),
            f"phase13k_boundary_passed={bool(row['phase13k_boundary_passed'])}",
        ),
        _gate_row(
            "Scope blocks signal/model/backtest/paper-trading/promotion",
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


def build_phase13j_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    verdict = (
        "Completed — feature panel quality and leakage audit passed"
        if all_passed
        else "Failed feature panel quality and leakage audit"
    )
    interpretation = (
        "Phase 13J audited feature-panel quality, output schema, missingness, "
        "leakage, visual reports, and forbidden columns. It did not create signals, "
        "allocation rules, models, strategy backtests, paper-trading logic, candidate "
        "promotion, or final-candidate changes."
        if all_passed
        else "Phase 13J found a feature quality, leakage, visual-report, forbidden-column, "
        "boundary, or scope issue."
    )
    return pd.DataFrame(
        [
            {
                "phase": "Phase 13J",
                "diagnostic": "Feature panel quality and leakage audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
                "interpretation": interpretation,
            }
        ]
    )


def save_phase13j_feature_panel_quality_leakage_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase13j_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = phase_config.get("phase13i_reports", {})
    thresholds = phase_config.get("quality_thresholds", {})

    report_inventory_check = build_phase13j_report_inventory_check(phase_config)
    phase13i_result_check = build_phase13j_phase13i_result_check(phase_config)
    config_flag_check = build_phase13j_config_flag_check(
        runtime_config=config,
        expected_flags=phase_config.get("expected_runtime_flags", {}),
    )

    feature_panel = _read_csv_if_exists(reports.get("feature_panel", ""))
    visual_reports = {
        "feature_state_timeline": _read_csv_if_exists(
            reports.get("feature_state_timeline", "")
        ),
        "feature_availability_heatmap": _read_csv_if_exists(
            reports.get("feature_availability_heatmap", "")
        ),
        "leakage_audit_panel": _read_csv_if_exists(
            reports.get("leakage_audit_panel", "")
        ),
        "model_feature_matrix_preview": _read_csv_if_exists(
            reports.get("model_feature_matrix_preview", "")
        ),
        "decision_rationale_template": _read_csv_if_exists(
            reports.get("decision_rationale_template", "")
        ),
    }

    feature_panel_quality_check = build_phase13j_feature_panel_quality_check(
        feature_panel=feature_panel,
        thresholds=thresholds,
    )
    output_schema_quality_check = build_phase13j_output_schema_quality_check(
        feature_panel
    )
    missingness_quality_check = build_phase13j_missingness_quality_check(feature_panel)
    leakage_quality_check = build_phase13j_leakage_quality_check(
        feature_panel=feature_panel,
        thresholds=thresholds,
    )
    visual_reports_quality_check = build_phase13j_visual_reports_quality_check(
        visual_reports
    )
    forbidden_column_check = build_phase13j_forbidden_column_check(
        frames={"feature_panel": feature_panel, **visual_reports},
        forbidden_columns=_as_list(thresholds.get("forbidden_columns")),
    )
    phase13k_boundary_check = build_phase13j_phase13k_boundary_check(phase_config)
    scope_boundary_check = build_phase13_scope_boundary_check(phase_config)

    summary = build_phase13j_summary(
        phase_config=phase_config,
        report_inventory_check=report_inventory_check,
        phase13i_result_check=phase13i_result_check,
        config_flag_check=config_flag_check,
        feature_panel_quality_check=feature_panel_quality_check,
        output_schema_quality_check=output_schema_quality_check,
        missingness_quality_check=missingness_quality_check,
        leakage_quality_check=leakage_quality_check,
        visual_reports_quality_check=visual_reports_quality_check,
        forbidden_column_check=forbidden_column_check,
        phase13k_boundary_check=phase13k_boundary_check,
        scope_boundary_check=scope_boundary_check,
    )
    gate_report = build_phase13j_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase13j_conclusion(gate_report)

    outputs = {
        "report_inventory_check": report_inventory_check,
        "phase13i_result_check": phase13i_result_check,
        "config_flag_check": config_flag_check,
        "feature_panel_quality_check": feature_panel_quality_check,
        "output_schema_quality_check": output_schema_quality_check,
        "missingness_quality_check": missingness_quality_check,
        "leakage_quality_check": leakage_quality_check,
        "visual_reports_quality_check": visual_reports_quality_check,
        "forbidden_column_check": forbidden_column_check,
        "phase13k_boundary_check": phase13k_boundary_check,
        "scope_boundary_check": scope_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase13j_quality_{name}.csv", index=False)

    _write_markdown(
        title="Phase 13J — Feature Panel Quality / Leakage Audit",
        sections={
            "Report Inventory Check": report_inventory_check,
            "Phase 13I Result Check": phase13i_result_check,
            "Feature Panel Quality Check": feature_panel_quality_check,
            "Output Schema Quality Check": output_schema_quality_check,
            "Missingness Quality Check": missingness_quality_check,
            "Leakage Quality Check": leakage_quality_check,
            "Visual Reports Quality Check": visual_reports_quality_check,
            "Forbidden Column Check": forbidden_column_check,
            "Summary": summary,
            "Gate Report": gate_report,
            "Conclusion": conclusion,
        },
        output_path=reports_path / "phase13j_feature_panel_quality_leakage_audit.md",
    )

    print("Wrote Phase 13J feature panel quality / leakage audit reports.")
    return outputs