from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.lookahead_signal_execution_audit import (
    _create_audited_overlay_result,
)


DEFAULT_PHASE10D_CONFIG: dict[str, Any] = {
    "enabled": False,
    "diagnostic_role": "Diagnostic-only macro regime analysis",
    "proposed_next_phase": "Phase 10E",
    "canonical_start_date": "2006-04-28",
    "canonical_end_date": "2026-05-01",
    "macro_aligned_series_path": "reports/phase10c_macro_aligned_series.csv",
    "allow_macro_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_model_feature_creation": False,
    "allow_model_training": False,
    "allow_strategy_test": False,
    "allow_strategy_promotion": False,
    "phase10e_boundary": {
        "allowed_next_step": "pre-registered macro hypothesis design spec only",
        "forbidden_next_step": "macro allocation rule, predictive model, or strategy test",
        "phase10e_may_create_hypothesis_spec": True,
        "phase10e_may_create_strategy_signal": False,
        "phase10e_may_test_strategy": False,
        "phase10e_may_train_model": False,
        "phase10e_may_promote_candidate": False,
    },
    "regime_definitions": {},
    "gates": {
        "min_macro_panel_rows": 4000,
        "min_regime_families": 5,
        "min_regime_metric_rows": 10,
        "min_rows_per_regime": 126,
        "require_macro_panel_loaded": True,
        "require_unrate_present": True,
        "require_dgs2_present": True,
        "require_dgs10_present": True,
        "require_cpi_present": True,
        "require_regime_metrics_generated": True,
        "require_no_macro_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_model_feature_creation": True,
        "require_no_model_training": True,
        "require_no_strategy_test": True,
        "require_no_strategy_promotion": True,
        "require_phase10e_boundary_spec_only": True,
        "required_diagnostic_role": "Diagnostic-only macro regime analysis",
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
    user_config = config.get("phase10d_diagnostic_macro_regime_analysis", {})
    return _deep_merge_dict(DEFAULT_PHASE10D_CONFIG, user_config)


def _normalise_strategy_frame(frame: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    required = {"date", "strategy_return"}
    missing = required.difference(frame.columns)

    if missing:
        raise ValueError(f"{strategy_name} missing required columns: {sorted(missing)}")

    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    out["strategy_return"] = pd.to_numeric(
        out["strategy_return"],
        errors="coerce",
    ).fillna(0.0)

    return out[["date", "strategy_return"]]


def _find_final_candidate_frame(
    *,
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    config: dict[str, Any],
) -> pd.DataFrame:
    if relative_momentum_outputs is None:
        raise ValueError("relative_momentum_outputs is required.")

    if ticker_outputs is None:
        raise ValueError("ticker_outputs is required.")

    final_candidate = _create_audited_overlay_result(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    ).copy()

    required = {"date", "strategy_return"}
    missing = required.difference(final_candidate.columns)

    if missing:
        raise ValueError(
            "Reconstructed final candidate missing required columns: "
            f"{sorted(missing)}"
        )

    return final_candidate.sort_values("date").reset_index(drop=True)


def _get_spy_strategy_result(
    ticker_outputs: dict[str, Any] | None,
    strategy_name: str,
) -> pd.DataFrame:
    if not ticker_outputs or "SPY" not in ticker_outputs:
        raise ValueError("ticker_outputs must contain SPY outputs.")

    strategy_results = ticker_outputs["SPY"].get("strategy_results", {})

    if strategy_name not in strategy_results:
        available = sorted(strategy_results.keys())
        raise ValueError(
            f"SPY strategy {strategy_name!r} not found. Available: {available}"
        )

    return strategy_results[strategy_name]


def _resolve_strategy_frames(
    *,
    config: dict[str, Any],
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    final_candidate: pd.DataFrame | None,
    spy_buy_hold: pd.DataFrame | None,
    spy_12m_momentum: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if final_candidate is None:
        final_candidate = _find_final_candidate_frame(
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
        )

    if spy_buy_hold is None:
        spy_buy_hold = _get_spy_strategy_result(ticker_outputs, "Buy and Hold")

    if spy_12m_momentum is None:
        spy_12m_momentum = _get_spy_strategy_result(
            ticker_outputs,
            "12-Month Absolute Momentum",
        )

    return final_candidate, spy_buy_hold, spy_12m_momentum


def _infer_periods_per_year(dates: pd.Series) -> float:
    clean_dates = pd.to_datetime(dates).dropna().sort_values()

    if len(clean_dates) < 2:
        return 252.0

    elapsed_days = (clean_dates.iloc[-1] - clean_dates.iloc[0]).days

    if elapsed_days <= 0:
        return 252.0

    observations_per_year = (len(clean_dates) - 1) / (elapsed_days / 365.25)

    if observations_per_year > 300:
        return 365.25

    return 252.0


def _equity_curve(returns: pd.Series, initial_capital: float = 1.0) -> pd.Series:
    clean_returns = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    return initial_capital * (1.0 + clean_returns).cumprod()


def _drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def _max_drawdown(returns: pd.Series) -> float:
    equity = _equity_curve(returns)
    return float(_drawdown(equity).min())


def _cagr(returns: pd.Series, dates: pd.Series) -> float:
    clean_dates = pd.to_datetime(dates).dropna().sort_values()

    if len(clean_dates) < 2:
        return 0.0

    years = (clean_dates.iloc[-1] - clean_dates.iloc[0]).days / 365.25

    if years <= 0:
        return 0.0

    equity = _equity_curve(returns)

    if equity.empty or equity.iloc[0] <= 0:
        return 0.0

    return float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)


def _volatility(returns: pd.Series, dates: pd.Series) -> float:
    periods_per_year = _infer_periods_per_year(dates)
    clean_returns = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    return float(clean_returns.std(ddof=0) * np.sqrt(periods_per_year))


def _calmar(cagr: float, max_drawdown: float) -> float:
    if max_drawdown >= 0:
        return np.nan

    return float(cagr / abs(max_drawdown))


def _load_macro_aligned_series(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)

    required = {"source_id", "series_id", "trading_date", "value"}
    missing = required.difference(frame.columns)

    if missing:
        raise ValueError(f"Macro aligned series missing columns: {sorted(missing)}")

    out = frame.copy()
    out["trading_date"] = pd.to_datetime(out["trading_date"])
    out["value"] = pd.to_numeric(out["value"], errors="coerce")

    return out


def build_phase10d_macro_panel(
    *,
    macro_aligned_series: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    start = pd.Timestamp(phase_config.get("canonical_start_date", "2006-04-28"))
    end = pd.Timestamp(phase_config.get("canonical_end_date", "2026-05-01"))

    panel = macro_aligned_series.pivot_table(
        index="trading_date",
        columns="series_id",
        values="value",
        aggfunc="last",
    ).reset_index()
    panel.columns.name = None
    panel = panel.rename(columns={"trading_date": "date"})
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= start) & (panel["date"] <= end)].copy()
    panel = panel.sort_values("date").reset_index(drop=True)

    if {"DGS10", "DGS2"}.issubset(panel.columns):
        panel["yield_curve_10y_2y"] = panel["DGS10"] - panel["DGS2"]

    if "UNRATE" in panel.columns:
        lookback = int(
            phase_config.get("regime_definitions", {})
            .get("unemployment_6m_change", {})
            .get("lookback_trading_days", 126)
        )
        panel["unrate_6m_change"] = panel["UNRATE"] - panel["UNRATE"].shift(lookback)

    if "CPIAUCSL" in panel.columns:
        lookback = int(
            phase_config.get("regime_definitions", {})
            .get("inflation_yoy", {})
            .get("lookback_trading_days", 252)
        )
        panel["cpi_yoy"] = panel["CPIAUCSL"].pct_change(lookback)

    return panel


def _bucket_three_way(
    values: pd.Series,
    *,
    low_threshold: float,
    high_threshold: float,
    low_label: str,
    normal_label: str,
    high_label: str,
) -> pd.Series:
    conditions = [
        values < low_threshold,
        values > high_threshold,
    ]
    choices = [low_label, high_label]

    return pd.Series(
        np.select(conditions, choices, default=normal_label),
        index=values.index,
    ).where(values.notna())


def build_phase10d_regime_frame(
    *,
    macro_panel: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    regime_defs = phase_config.get("regime_definitions", {})
    rows: list[pd.DataFrame] = []

    if "UNRATE" in macro_panel.columns and "unemployment_level" in regime_defs:
        config = regime_defs["unemployment_level"]
        labels = config.get("labels", {})
        frame = pd.DataFrame(
            {
                "date": macro_panel["date"],
                "regime_family": "unemployment_level",
                "regime_bucket": _bucket_three_way(
                    macro_panel["UNRATE"],
                    low_threshold=float(config.get("low_threshold", 4.0)),
                    high_threshold=float(config.get("high_threshold", 6.0)),
                    low_label=str(labels.get("low", "low_unemployment")),
                    normal_label=str(labels.get("normal", "normal_unemployment")),
                    high_label=str(labels.get("high", "high_unemployment")),
                ),
                "regime_value": macro_panel["UNRATE"],
            }
        )
        rows.append(frame)

    if (
        "unrate_6m_change" in macro_panel.columns
        and "unemployment_6m_change" in regime_defs
    ):
        config = regime_defs["unemployment_6m_change"]
        labels = config.get("labels", {})
        frame = pd.DataFrame(
            {
                "date": macro_panel["date"],
                "regime_family": "unemployment_6m_change",
                "regime_bucket": _bucket_three_way(
                    macro_panel["unrate_6m_change"],
                    low_threshold=float(config.get("falling_threshold", -0.30)),
                    high_threshold=float(config.get("rising_threshold", 0.30)),
                    low_label=str(labels.get("falling", "unemployment_falling")),
                    normal_label=str(labels.get("stable", "unemployment_stable")),
                    high_label=str(labels.get("rising", "unemployment_rising")),
                ),
                "regime_value": macro_panel["unrate_6m_change"],
            }
        )
        rows.append(frame)

    if "yield_curve_10y_2y" in macro_panel.columns and "yield_curve_10y_2y" in regime_defs:
        config = regime_defs["yield_curve_10y_2y"]
        labels = config.get("labels", {})
        frame = pd.DataFrame(
            {
                "date": macro_panel["date"],
                "regime_family": "yield_curve_10y_2y",
                "regime_bucket": _bucket_three_way(
                    macro_panel["yield_curve_10y_2y"],
                    low_threshold=float(config.get("inverted_threshold", 0.0)),
                    high_threshold=float(config.get("steep_threshold", 1.0)),
                    low_label=str(labels.get("inverted", "yield_curve_inverted")),
                    normal_label=str(labels.get("normal", "yield_curve_normal")),
                    high_label=str(labels.get("steep", "yield_curve_steep")),
                ),
                "regime_value": macro_panel["yield_curve_10y_2y"],
            }
        )
        rows.append(frame)

    if "DGS2" in macro_panel.columns and "short_rate_level" in regime_defs:
        config = regime_defs["short_rate_level"]
        labels = config.get("labels", {})
        frame = pd.DataFrame(
            {
                "date": macro_panel["date"],
                "regime_family": "short_rate_level",
                "regime_bucket": _bucket_three_way(
                    macro_panel["DGS2"],
                    low_threshold=float(config.get("low_threshold", 1.5)),
                    high_threshold=float(config.get("high_threshold", 4.0)),
                    low_label=str(labels.get("low", "low_short_rates")),
                    normal_label=str(labels.get("normal", "normal_short_rates")),
                    high_label=str(labels.get("high", "high_short_rates")),
                ),
                "regime_value": macro_panel["DGS2"],
            }
        )
        rows.append(frame)

    if "cpi_yoy" in macro_panel.columns and "inflation_yoy" in regime_defs:
        config = regime_defs["inflation_yoy"]
        labels = config.get("labels", {})
        frame = pd.DataFrame(
            {
                "date": macro_panel["date"],
                "regime_family": "inflation_yoy",
                "regime_bucket": _bucket_three_way(
                    macro_panel["cpi_yoy"],
                    low_threshold=float(config.get("low_threshold", 0.02)),
                    high_threshold=float(config.get("high_threshold", 0.04)),
                    low_label=str(labels.get("low", "low_inflation")),
                    normal_label=str(labels.get("normal", "normal_inflation")),
                    high_label=str(labels.get("high", "high_inflation")),
                ),
                "regime_value": macro_panel["cpi_yoy"],
            }
        )
        rows.append(frame)

    if not rows:
        return pd.DataFrame(
            columns=["date", "regime_family", "regime_bucket", "regime_value"]
        )

    out = pd.concat(rows, ignore_index=True)
    out = out.dropna(subset=["regime_bucket"]).sort_values(
        ["regime_family", "date"]
    ).reset_index(drop=True)

    return out


def build_phase10d_analysis_frame(
    *,
    final_candidate: pd.DataFrame,
    spy_buy_hold: pd.DataFrame,
    spy_12m_momentum: pd.DataFrame,
    regime_frame: pd.DataFrame,
) -> pd.DataFrame:
    candidate = _normalise_strategy_frame(final_candidate, "Final candidate").rename(
        columns={"strategy_return": "candidate_return"}
    )
    buy_hold = _normalise_strategy_frame(spy_buy_hold, "SPY Buy & Hold").rename(
        columns={"strategy_return": "buy_hold_return"}
    )
    spy_12m = _normalise_strategy_frame(
        spy_12m_momentum,
        "SPY 12M Momentum",
    ).rename(columns={"strategy_return": "spy_12m_return"})

    returns = candidate.merge(buy_hold, on="date", how="inner").merge(
        spy_12m,
        on="date",
        how="inner",
    )

    analysis = regime_frame.merge(returns, on="date", how="inner")
    analysis["candidate_minus_buy_hold_return"] = (
        analysis["candidate_return"] - analysis["buy_hold_return"]
    )
    analysis["candidate_minus_spy_12m_return"] = (
        analysis["candidate_return"] - analysis["spy_12m_return"]
    )

    return analysis.sort_values(["regime_family", "regime_bucket", "date"]).reset_index(
        drop=True
    )


def _metric_values(frame: pd.DataFrame, return_column: str) -> dict[str, float]:
    cagr = _cagr(frame[return_column], frame["date"])
    max_dd = _max_drawdown(frame[return_column])

    return {
        "cagr": cagr,
        "volatility": _volatility(frame[return_column], frame["date"]),
        "max_drawdown": max_dd,
        "calmar": _calmar(cagr, max_dd),
    }


def build_phase10d_regime_metrics(
    *,
    analysis_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    min_rows = int(phase_config.get("gates", {}).get("min_rows_per_regime", 126))
    rows: list[dict[str, Any]] = []

    group_columns = ["regime_family", "regime_bucket"]

    for (regime_family, regime_bucket), group in analysis_frame.groupby(group_columns):
        group = group.sort_values("date").reset_index(drop=True)

        if len(group) < min_rows:
            continue

        candidate = _metric_values(group, "candidate_return")
        buy_hold = _metric_values(group, "buy_hold_return")
        spy_12m = _metric_values(group, "spy_12m_return")

        rows.append(
            {
                "regime_family": regime_family,
                "regime_bucket": regime_bucket,
                "rows": int(len(group)),
                "start_date": pd.to_datetime(group["date"].iloc[0]).date().isoformat(),
                "end_date": pd.to_datetime(group["date"].iloc[-1]).date().isoformat(),
                "avg_regime_value": float(group["regime_value"].mean()),
                "candidate_cagr": candidate["cagr"],
                "buy_hold_cagr": buy_hold["cagr"],
                "spy_12m_cagr": spy_12m["cagr"],
                "candidate_minus_buy_hold_cagr": (
                    candidate["cagr"] - buy_hold["cagr"]
                ),
                "candidate_minus_spy_12m_cagr": (
                    candidate["cagr"] - spy_12m["cagr"]
                ),
                "candidate_calmar": candidate["calmar"],
                "buy_hold_calmar": buy_hold["calmar"],
                "spy_12m_calmar": spy_12m["calmar"],
                "candidate_minus_buy_hold_calmar": (
                    candidate["calmar"] - buy_hold["calmar"]
                ),
                "candidate_minus_spy_12m_calmar": (
                    candidate["calmar"] - spy_12m["calmar"]
                ),
                "candidate_max_drawdown": candidate["max_drawdown"],
                "buy_hold_max_drawdown": buy_hold["max_drawdown"],
                "spy_12m_max_drawdown": spy_12m["max_drawdown"],
                "candidate_drawdown_advantage_vs_buy_hold": (
                    candidate["max_drawdown"] - buy_hold["max_drawdown"]
                ),
                "candidate_drawdown_advantage_vs_spy_12m": (
                    candidate["max_drawdown"] - spy_12m["max_drawdown"]
                ),
                "avg_daily_excess_vs_buy_hold": float(
                    group["candidate_minus_buy_hold_return"].mean()
                ),
                "avg_daily_excess_vs_spy_12m": float(
                    group["candidate_minus_spy_12m_return"].mean()
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase10d_helpful_regime_report(regime_metrics: pd.DataFrame) -> pd.DataFrame:
    if regime_metrics.empty:
        return pd.DataFrame()

    out = regime_metrics.copy()
    out["helpful_vs_buy_hold"] = (
        (out["candidate_minus_buy_hold_calmar"] > 0)
        & (out["candidate_drawdown_advantage_vs_buy_hold"] > 0)
    )
    out["helpful_vs_spy_12m"] = (
        (out["candidate_minus_spy_12m_calmar"] > 0)
        & (out["candidate_drawdown_advantage_vs_spy_12m"] > 0)
    )
    out["helpful_both_benchmarks"] = (
        out["helpful_vs_buy_hold"] & out["helpful_vs_spy_12m"]
    )

    return out.sort_values(
        [
            "helpful_both_benchmarks",
            "candidate_minus_spy_12m_calmar",
            "candidate_minus_buy_hold_calmar",
        ],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def build_phase10d_weak_regime_report(regime_metrics: pd.DataFrame) -> pd.DataFrame:
    if regime_metrics.empty:
        return pd.DataFrame()

    out = regime_metrics.copy()
    out["weak_vs_buy_hold"] = (
        (out["candidate_minus_buy_hold_calmar"] < 0)
        | (out["candidate_minus_buy_hold_cagr"] < 0)
    )
    out["weak_vs_spy_12m"] = (
        (out["candidate_minus_spy_12m_calmar"] < 0)
        | (out["candidate_minus_spy_12m_cagr"] < 0)
    )
    out["weak_both_benchmarks"] = out["weak_vs_buy_hold"] & out["weak_vs_spy_12m"]

    return out.sort_values(
        [
            "weak_both_benchmarks",
            "candidate_minus_spy_12m_calmar",
            "candidate_minus_buy_hold_calmar",
        ],
        ascending=[False, True, True],
    ).reset_index(drop=True)


def build_phase10d_phase10e_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase10e_boundary", {})

    rows = [
        {
            "boundary_item": "phase10e_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "spec" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase10e_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
            or "model" in str(boundary.get("forbidden_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase10e_may_create_hypothesis_spec",
            "value": bool(boundary.get("phase10e_may_create_hypothesis_spec", False)),
            "passed": bool(boundary.get("phase10e_may_create_hypothesis_spec", False)),
        },
        {
            "boundary_item": "phase10e_may_create_strategy_signal",
            "value": bool(boundary.get("phase10e_may_create_strategy_signal", True)),
            "passed": not bool(boundary.get("phase10e_may_create_strategy_signal", True)),
        },
        {
            "boundary_item": "phase10e_may_test_strategy",
            "value": bool(boundary.get("phase10e_may_test_strategy", True)),
            "passed": not bool(boundary.get("phase10e_may_test_strategy", True)),
        },
        {
            "boundary_item": "phase10e_may_train_model",
            "value": bool(boundary.get("phase10e_may_train_model", True)),
            "passed": not bool(boundary.get("phase10e_may_train_model", True)),
        },
        {
            "boundary_item": "phase10e_may_promote_candidate",
            "value": bool(boundary.get("phase10e_may_promote_candidate", True)),
            "passed": not bool(boundary.get("phase10e_may_promote_candidate", True)),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase10d_summary(
    *,
    phase_config: dict[str, Any],
    macro_panel: pd.DataFrame,
    regime_frame: pd.DataFrame,
    regime_metrics: pd.DataFrame,
    helpful_regime_report: pd.DataFrame,
    weak_regime_report: pd.DataFrame,
    phase10e_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "diagnostic_role": str(phase_config.get("diagnostic_role", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "macro_panel_rows": int(len(macro_panel)),
                "regime_family_count": int(regime_frame["regime_family"].nunique())
                if not regime_frame.empty
                else 0,
                "regime_metric_rows": int(len(regime_metrics)),
                "helpful_regime_rows": int(
                    helpful_regime_report["helpful_both_benchmarks"].sum()
                )
                if not helpful_regime_report.empty
                else 0,
                "weak_regime_rows": int(
                    weak_regime_report["weak_both_benchmarks"].sum()
                )
                if not weak_regime_report.empty
                else 0,
                "phase10e_boundary_passed": bool(
                    phase10e_boundary_check["passed"].all()
                )
                if not phase10e_boundary_check.empty
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


def build_phase10d_gate_report(
    *,
    phase_config: dict[str, Any],
    macro_panel: pd.DataFrame,
    regime_metrics: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 10D summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    required_role = str(
        gates.get("required_diagnostic_role", "Diagnostic-only macro regime analysis")
    )

    rows = [
        _gate_row(
            "Macro panel loaded",
            (not gates.get("require_macro_panel_loaded", True))
            or int(row["macro_panel_rows"]) >= int(gates.get("min_macro_panel_rows", 4000)),
            f"macro_panel_rows={int(row['macro_panel_rows'])}",
        ),
        _gate_row(
            "UNRATE is present",
            (not gates.get("require_unrate_present", True))
            or "UNRATE" in macro_panel.columns,
            f"columns={list(macro_panel.columns)}",
        ),
        _gate_row(
            "DGS2 is present",
            (not gates.get("require_dgs2_present", True)) or "DGS2" in macro_panel.columns,
            f"columns={list(macro_panel.columns)}",
        ),
        _gate_row(
            "DGS10 is present",
            (not gates.get("require_dgs10_present", True)) or "DGS10" in macro_panel.columns,
            f"columns={list(macro_panel.columns)}",
        ),
        _gate_row(
            "CPIAUCSL is present",
            (not gates.get("require_cpi_present", True))
            or "CPIAUCSL" in macro_panel.columns,
            f"columns={list(macro_panel.columns)}",
        ),
        _gate_row(
            "Regime family count is sufficient",
            int(row["regime_family_count"]) >= int(gates.get("min_regime_families", 5)),
            f"regime_family_count={int(row['regime_family_count'])}",
        ),
        _gate_row(
            "Regime metrics were generated",
            (not gates.get("require_regime_metrics_generated", True))
            or int(row["regime_metric_rows"])
            >= int(gates.get("min_regime_metric_rows", 10)),
            f"regime_metric_rows={int(row['regime_metric_rows'])}",
        ),
        _gate_row(
            "No macro signal creation is allowed",
            (not gates.get("require_no_macro_signal_creation", True))
            or not bool(row["allow_macro_signal_creation"]),
            f"allow_macro_signal_creation={bool(row['allow_macro_signal_creation'])}",
        ),
        _gate_row(
            "No allocation rule creation is allowed",
            (not gates.get("require_no_allocation_rule_creation", True))
            or not bool(row["allow_allocation_rule_creation"]),
            (
                "allow_allocation_rule_creation="
                f"{bool(row['allow_allocation_rule_creation'])}"
            ),
        ),
        _gate_row(
            "No model feature creation is allowed",
            (not gates.get("require_no_model_feature_creation", True))
            or not bool(row["allow_model_feature_creation"]),
            f"allow_model_feature_creation={bool(row['allow_model_feature_creation'])}",
        ),
        _gate_row(
            "No model training is allowed",
            (not gates.get("require_no_model_training", True))
            or not bool(row["allow_model_training"]),
            f"allow_model_training={bool(row['allow_model_training'])}",
        ),
        _gate_row(
            "No strategy test is allowed",
            (not gates.get("require_no_strategy_test", True))
            or not bool(row["allow_strategy_test"]),
            f"allow_strategy_test={bool(row['allow_strategy_test'])}",
        ),
        _gate_row(
            "No strategy promotion is allowed",
            (not gates.get("require_no_strategy_promotion", True))
            or not bool(row["allow_strategy_promotion"]),
            f"allow_strategy_promotion={bool(row['allow_strategy_promotion'])}",
        ),
        _gate_row(
            "Phase 10E boundary is spec-only",
            (not gates.get("require_phase10e_boundary_spec_only", True))
            or bool(row["phase10e_boundary_passed"]),
            f"phase10e_boundary_passed={bool(row['phase10e_boundary_passed'])}",
        ),
        _gate_row(
            "Diagnostic role is correct",
            str(row["diagnostic_role"]) == required_role,
            f"diagnostic_role={row['diagnostic_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase10d_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — diagnostic-only macro regime analysis"
        interpretation = (
            "Phase 10D produced diagnostic macro/rates/inflation regime analysis. "
            "It did not create macro signals, allocation rules, model features, "
            "strategy tests, or candidate promotion. Phase 10E may only be a "
            "pre-registered macro hypothesis design spec."
        )
    else:
        verdict = "Failed diagnostic macro regime analysis"
        interpretation = (
            "Phase 10D did not satisfy every diagnostic gate. Do not proceed to "
            "Phase 10E until macro panel, regime metrics, or boundary issues are fixed."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 10D",
                "diagnostic": "Diagnostic-only macro regime analysis",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase10d_markdown(
    *,
    macro_panel: pd.DataFrame,
    regime_frame: pd.DataFrame,
    regime_metrics: pd.DataFrame,
    helpful_regime_report: pd.DataFrame,
    weak_regime_report: pd.DataFrame,
    phase10e_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 10D — Diagnostic-Only Macro Regime Analysis",
        "",
        "## Purpose",
        "",
        (
            "This diagnostic examines whether macro/rates/inflation regimes help "
            "explain where the final candidate behaves better or worse versus SPY "
            "Buy & Hold and SPY 12M Momentum."
        ),
        "",
        (
            "It does not create macro signals, allocation rules, predictive model "
            "features, model training, strategy tests, or candidate promotion."
        ),
        "",
        "## Macro Panel Preview",
        "",
        macro_panel.head(20).to_markdown(index=False),
        "",
        "## Regime Frame Preview",
        "",
        regime_frame.head(30).to_markdown(index=False),
        "",
        "## Regime Metrics",
        "",
        regime_metrics.to_markdown(index=False),
        "",
        "## Helpful Regime Report",
        "",
        helpful_regime_report.to_markdown(index=False),
        "",
        "## Weak Regime Report",
        "",
        weak_regime_report.to_markdown(index=False),
        "",
        "## Phase 10E Boundary Check",
        "",
        phase10e_boundary_check.to_markdown(index=False),
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
        "- This is diagnostic analysis only.",
        "- Macro regimes are not trading signals.",
        "- Current/revised macro data still carries revision-risk caveats.",
        "- No macro rule or model is validated by this phase.",
        "- Phase 10E may only pre-register hypotheses, not test a strategy.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase10d_diagnostic_macro_regime_analysis(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
    final_candidate: pd.DataFrame | None = None,
    spy_buy_hold: pd.DataFrame | None = None,
    spy_12m_momentum: pd.DataFrame | None = None,
    macro_aligned_series: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "macro_panel": empty,
            "regime_frame": empty,
            "analysis_frame": empty,
            "regime_metrics": empty,
            "helpful_regime_report": empty,
            "weak_regime_report": empty,
            "phase10e_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    final_candidate, spy_buy_hold, spy_12m_momentum = _resolve_strategy_frames(
        config=config,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        final_candidate=final_candidate,
        spy_buy_hold=spy_buy_hold,
        spy_12m_momentum=spy_12m_momentum,
    )

    if macro_aligned_series is None:
        macro_aligned_series = _load_macro_aligned_series(
            phase_config.get("macro_aligned_series_path", "reports/phase10c_macro_aligned_series.csv")
        )

    macro_panel = build_phase10d_macro_panel(
        macro_aligned_series=macro_aligned_series,
        phase_config=phase_config,
    )
    regime_frame = build_phase10d_regime_frame(
        macro_panel=macro_panel,
        phase_config=phase_config,
    )
    analysis_frame = build_phase10d_analysis_frame(
        final_candidate=final_candidate,
        spy_buy_hold=spy_buy_hold,
        spy_12m_momentum=spy_12m_momentum,
        regime_frame=regime_frame,
    )
    regime_metrics = build_phase10d_regime_metrics(
        analysis_frame=analysis_frame,
        phase_config=phase_config,
    )
    helpful_regime_report = build_phase10d_helpful_regime_report(regime_metrics)
    weak_regime_report = build_phase10d_weak_regime_report(regime_metrics)
    phase10e_boundary_check = build_phase10d_phase10e_boundary_check(phase_config)
    summary = build_phase10d_summary(
        phase_config=phase_config,
        macro_panel=macro_panel,
        regime_frame=regime_frame,
        regime_metrics=regime_metrics,
        helpful_regime_report=helpful_regime_report,
        weak_regime_report=weak_regime_report,
        phase10e_boundary_check=phase10e_boundary_check,
    )
    gate_report = build_phase10d_gate_report(
        phase_config=phase_config,
        macro_panel=macro_panel,
        regime_metrics=regime_metrics,
        summary=summary,
    )
    conclusion = build_phase10d_conclusion(gate_report)

    macro_panel.to_csv(reports_path / "phase10d_macro_panel.csv", index=False)
    regime_frame.to_csv(reports_path / "phase10d_macro_regime_frame.csv", index=False)
    analysis_frame.to_csv(reports_path / "phase10d_macro_analysis_frame.csv", index=False)
    regime_metrics.to_csv(reports_path / "phase10d_macro_regime_metrics.csv", index=False)
    helpful_regime_report.to_csv(
        reports_path / "phase10d_macro_helpful_regime_report.csv",
        index=False,
    )
    weak_regime_report.to_csv(
        reports_path / "phase10d_macro_weak_regime_report.csv",
        index=False,
    )
    phase10e_boundary_check.to_csv(
        reports_path / "phase10d_macro_phase10e_boundary_check.csv",
        index=False,
    )
    summary.to_csv(reports_path / "phase10d_macro_summary.csv", index=False)
    gate_report.to_csv(reports_path / "phase10d_macro_gate_report.csv", index=False)
    conclusion.to_csv(reports_path / "phase10d_macro_conclusion.csv", index=False)

    write_phase10d_markdown(
        macro_panel=macro_panel,
        regime_frame=regime_frame,
        regime_metrics=regime_metrics,
        helpful_regime_report=helpful_regime_report,
        weak_regime_report=weak_regime_report,
        phase10e_boundary_check=phase10e_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase10d_diagnostic_macro_regime_analysis.md",
    )

    print("Wrote Phase 10D diagnostic-only macro regime analysis reports.")

    return {
        "macro_panel": macro_panel,
        "regime_frame": regime_frame,
        "analysis_frame": analysis_frame,
        "regime_metrics": regime_metrics,
        "helpful_regime_report": helpful_regime_report,
        "weak_regime_report": weak_regime_report,
        "phase10e_boundary_check": phase10e_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }