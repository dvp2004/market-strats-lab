from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.lookahead_signal_execution_audit import (
    _create_audited_overlay_result,
)


DEFAULT_PHASE10F_CONFIG: dict[str, Any] = {
    "enabled": False,
    "test_role": "Pre-registered macro-rule test only",
    "proposed_next_phase": "Phase 10G",
    "macro_aligned_series_path": "reports/phase10c_macro_aligned_series.csv",
    "canonical_start_date": "2006-04-28",
    "canonical_end_date": "2026-05-01",
    "holdout_start_date": "2016-01-01",
    "allow_new_thresholds": False,
    "allow_new_inputs": False,
    "allow_macro_signal_creation_outside_preregistered_rules": False,
    "allow_allocation_rule_creation_outside_preregistered_rules": False,
    "allow_model_feature_creation": False,
    "allow_model_training": False,
    "allow_strategy_promotion": False,
    "friction": {
        "stress_bps_per_rule_switch": 10.0,
        "max_stress_cagr_degradation_pts": 0.15,
        "max_stress_calmar_degradation": 0.010,
    },
    "episode_windows": [],
    "allowed_macro_input_registry": [],
    "rules": [],
    "validation_gates": {
        "max_full_cagr_damage_pts": 0.15,
        "max_episode_cagr_damage_pts": 0.25,
        "max_episode_calmar_damage": 0.020,
        "max_episode_drawdown_damage_pts": 1.00,
        "require_full_calmar_improvement_for_h1": True,
        "require_full_calmar_preservation_for_h2": True,
        "require_full_drawdown_not_worse": True,
        "require_holdout_not_worse": True,
        "require_episode_damage_control": True,
        "require_stress_friction_survival": True,
        "require_behavioural_relative_drawdown_not_worse": True,
        "require_no_raw_wealth_overclaim": True,
        "require_no_strategy_promotion": True,
    },
    "gates": {
        "expected_rule_ids": [
            "H1_supportive_low_rate_low_inflation_relief",
            "H2_high_rate_high_unemployment_stress_guard",
        ],
        "min_rules": 2,
        "max_rules": 2,
        "require_exact_rule_ids": True,
        "require_conditions_inside_registry": True,
        "require_locked_thresholds": True,
        "require_no_new_thresholds": True,
        "require_no_new_inputs": True,
        "require_no_model_feature_creation": True,
        "require_no_model_training": True,
        "require_no_strategy_promotion": True,
        "require_rule_metrics_generated": True,
        "require_rule_gate_report_generated": True,
        "required_test_role": "Pre-registered macro-rule test only",
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
    user_config = config.get("phase10f_preregistered_macro_rule_test", {})
    return _deep_merge_dict(DEFAULT_PHASE10F_CONFIG, user_config)


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


def _rules(phase_config: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in _as_list(phase_config.get("rules"))]


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

    return _normalise_strategy_frame(final_candidate, "Final candidate")


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

    return _normalise_strategy_frame(strategy_results[strategy_name], strategy_name)


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
    else:
        final_candidate = _normalise_strategy_frame(
            final_candidate,
            "Final candidate",
        )

    if spy_buy_hold is None:
        spy_buy_hold = _get_spy_strategy_result(ticker_outputs, "Buy and Hold")
    else:
        spy_buy_hold = _normalise_strategy_frame(spy_buy_hold, "SPY Buy & Hold")

    if spy_12m_momentum is None:
        spy_12m_momentum = _get_spy_strategy_result(
            ticker_outputs,
            "12-Month Absolute Momentum",
        )
    else:
        spy_12m_momentum = _normalise_strategy_frame(
            spy_12m_momentum,
            "SPY 12M Momentum",
        )

    return final_candidate, spy_buy_hold, spy_12m_momentum


def _load_macro_aligned_series(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)

    required = {"series_id", "trading_date", "value"}
    missing = required.difference(frame.columns)

    if missing:
        raise ValueError(f"Macro aligned series missing columns: {sorted(missing)}")

    out = frame.copy()
    out["trading_date"] = pd.to_datetime(out["trading_date"])
    out["value"] = pd.to_numeric(out["value"], errors="coerce")

    return out


def build_phase10f_macro_panel(
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

    if "CPIAUCSL" in panel.columns:
        panel["cpi_yoy"] = panel["CPIAUCSL"].pct_change(252)

    return panel


def _condition_mask(panel: pd.DataFrame, condition: dict[str, Any]) -> pd.Series:
    input_name = str(condition.get("input", ""))
    operator = str(condition.get("operator", "")).strip()
    threshold = float(condition.get("threshold"))

    if input_name not in panel.columns:
        return pd.Series(False, index=panel.index)

    values = pd.to_numeric(panel[input_name], errors="coerce")

    if operator == "<":
        return values < threshold

    if operator == ">":
        return values > threshold

    if operator == "<=":
        return values <= threshold

    if operator == ">=":
        return values >= threshold

    raise ValueError(f"Unsupported operator {operator!r} for {input_name}")


def build_phase10f_rule_activation_frame(
    *,
    macro_panel: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []

    for rule in _rules(phase_config):
        conditions = _as_list(rule.get("conditions"))
        activation_join = str(rule.get("activation_join", "AND")).upper()

        masks = [_condition_mask(macro_panel, condition) for condition in conditions]

        if not masks:
            active = pd.Series(False, index=macro_panel.index)
        elif activation_join == "AND":
            active = masks[0].copy()
            for mask in masks[1:]:
                active = active & mask
        elif activation_join == "OR":
            active = masks[0].copy()
            for mask in masks[1:]:
                active = active | mask
        else:
            raise ValueError(f"Unsupported activation_join {activation_join!r}")

        rows.append(
            pd.DataFrame(
                {
                    "date": macro_panel["date"],
                    "rule_id": str(rule.get("rule_id", "")),
                    "hypothesis_id": str(rule.get("hypothesis_id", "")),
                    "replacement_return_column": str(
                        rule.get("replacement_return_column", "")
                    ),
                    "active": active.fillna(False).astype(bool),
                }
            )
        )

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def build_phase10f_base_return_frame(
    *,
    final_candidate: pd.DataFrame,
    spy_buy_hold: pd.DataFrame,
    spy_12m_momentum: pd.DataFrame,
) -> pd.DataFrame:
    candidate = _normalise_strategy_frame(
        final_candidate,
        "Final candidate",
    ).rename(columns={"strategy_return": "candidate_return"})
    buy_hold = _normalise_strategy_frame(
        spy_buy_hold,
        "SPY Buy & Hold",
    ).rename(columns={"strategy_return": "buy_hold_return"})
    spy_12m = _normalise_strategy_frame(
        spy_12m_momentum,
        "SPY 12M Momentum",
    ).rename(columns={"strategy_return": "spy_12m_return"})

    return candidate.merge(buy_hold, on="date", how="inner").merge(
        spy_12m,
        on="date",
        how="inner",
    )


def build_phase10f_rule_returns(
    *,
    base_returns: pd.DataFrame,
    activation_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    friction = phase_config.get("friction", {})
    stress_bps = float(friction.get("stress_bps_per_rule_switch", 10.0))

    rows: list[pd.DataFrame] = []

    for rule in _rules(phase_config):
        rule_id = str(rule.get("rule_id", ""))
        replacement_column = str(rule.get("replacement_return_column", ""))

        active = activation_frame[activation_frame["rule_id"] == rule_id]
        frame = base_returns.merge(active, on="date", how="inner")

        if replacement_column not in frame.columns:
            raise ValueError(
                f"replacement_return_column {replacement_column!r} not found "
                f"for {rule_id}"
            )

        frame["strategy_return"] = np.where(
            frame["active"],
            frame[replacement_column],
            frame["candidate_return"],
        )
        frame["return_source"] = np.where(
            frame["active"],
            replacement_column,
            "candidate_return",
        )
        frame["rule_turnover"] = (
            frame["return_source"] != frame["return_source"].shift(1)
        ).astype(float)
        frame.loc[frame.index[0], "rule_turnover"] = float(frame["active"].iloc[0])
        frame["stress_extra_cost_return"] = (
            frame["rule_turnover"] * stress_bps / 10000.0
        )
        frame["stress_strategy_return"] = (
            frame["strategy_return"] - frame["stress_extra_cost_return"]
        )
        frame["rule_id"] = rule_id
        frame["hypothesis_id"] = str(rule.get("hypothesis_id", ""))
        frame["role"] = str(rule.get("role", "Candidate for further validation only"))

        rows.append(
            frame[
                [
                    "date",
                    "rule_id",
                    "hypothesis_id",
                    "role",
                    "active",
                    "return_source",
                    "candidate_return",
                    "buy_hold_return",
                    "spy_12m_return",
                    "strategy_return",
                    "rule_turnover",
                    "stress_extra_cost_return",
                    "stress_strategy_return",
                ]
            ]
        )

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


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
    return float(_drawdown(_equity_curve(returns)).min())


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


def _metric_row(
    *,
    frame: pd.DataFrame,
    rule_id: str,
    sample: str,
    return_column: str,
) -> dict[str, Any]:
    cagr = _cagr(frame[return_column], frame["date"])
    max_dd = _max_drawdown(frame[return_column])

    return {
        "rule_id": rule_id,
        "sample": sample,
        "return_column": return_column,
        "start_date": pd.to_datetime(frame["date"].iloc[0]).date().isoformat(),
        "end_date": pd.to_datetime(frame["date"].iloc[-1]).date().isoformat(),
        "rows": int(len(frame)),
        "active_days": int(frame["active"].sum()) if "active" in frame else 0,
        "switch_count": int(frame["rule_turnover"].sum())
        if "rule_turnover" in frame
        else 0,
        "cagr": cagr,
        "volatility": _volatility(frame[return_column], frame["date"]),
        "max_drawdown": max_dd,
        "calmar": _calmar(cagr, max_dd),
        "end_value": float(_equity_curve(frame[return_column], 10000.0).iloc[-1]),
    }


def build_phase10f_rule_metrics(
    *,
    rule_returns: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    holdout_start = pd.Timestamp(phase_config.get("holdout_start_date", "2016-01-01"))
    rows: list[dict[str, Any]] = []

    for rule_id, group in rule_returns.groupby("rule_id", sort=False):
        group = group.sort_values("date").reset_index(drop=True)

        rows.append(
            _metric_row(
                frame=group,
                rule_id=str(rule_id),
                sample="full",
                return_column="strategy_return",
            )
        )
        rows.append(
            _metric_row(
                frame=group,
                rule_id=str(rule_id),
                sample="stress_full",
                return_column="stress_strategy_return",
            )
        )

        holdout = group[group["date"] >= holdout_start].copy()

        if not holdout.empty:
            rows.append(
                _metric_row(
                    frame=holdout,
                    rule_id=str(rule_id),
                    sample="holdout",
                    return_column="strategy_return",
                )
            )

    return pd.DataFrame(rows)


def build_phase10f_benchmark_metrics(
    *,
    base_returns: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    holdout_start = pd.Timestamp(phase_config.get("holdout_start_date", "2016-01-01"))
    rows: list[dict[str, Any]] = []

    benchmarks = {
        "final_candidate": "candidate_return",
        "spy_buy_hold": "buy_hold_return",
        "spy_12m_momentum": "spy_12m_return",
    }

    for benchmark, column in benchmarks.items():
        full = base_returns.copy()
        full["active"] = False
        full["rule_turnover"] = 0.0
        rows.append(
            _metric_row(
                frame=full,
                rule_id=benchmark,
                sample="full",
                return_column=column,
            )
        )

        holdout = full[full["date"] >= holdout_start].copy()

        if not holdout.empty:
            rows.append(
                _metric_row(
                    frame=holdout,
                    rule_id=benchmark,
                    sample="holdout",
                    return_column=column,
                )
            )

    return pd.DataFrame(rows)


def _relative_max_drawdown(
    rule_frame: pd.DataFrame,
    rule_return_column: str,
    benchmark_return_column: str,
) -> float:
    rule_equity = _equity_curve(rule_frame[rule_return_column])
    benchmark_equity = _equity_curve(rule_frame[benchmark_return_column])
    relative_wealth = rule_equity / benchmark_equity
    relative_dd = relative_wealth / relative_wealth.cummax() - 1.0

    return float(relative_dd.min())


def build_phase10f_behavioural_metrics(rule_returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for rule_id, group in rule_returns.groupby("rule_id", sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        rule_rel_dd = _relative_max_drawdown(
            group,
            "strategy_return",
            "buy_hold_return",
        )
        baseline_rel_dd = _relative_max_drawdown(
            group,
            "candidate_return",
            "buy_hold_return",
        )

        rows.append(
            {
                "rule_id": str(rule_id),
                "rule_relative_max_drawdown_vs_buy_hold": rule_rel_dd,
                "baseline_relative_max_drawdown_vs_buy_hold": baseline_rel_dd,
                "relative_drawdown_delta": rule_rel_dd - baseline_rel_dd,
                "behavioural_regret_not_worse": rule_rel_dd >= baseline_rel_dd,
            }
        )

    return pd.DataFrame(rows)


def build_phase10f_episode_metrics(
    *,
    rule_returns: pd.DataFrame,
    base_returns: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for episode in _as_list(phase_config.get("episode_windows")):
        start = pd.Timestamp(episode.get("start_date"))
        end = pd.Timestamp(episode.get("end_date"))
        episode_name = str(episode.get("episode", ""))

        baseline = base_returns[
            (base_returns["date"] >= start) & (base_returns["date"] <= end)
        ].copy()

        if baseline.empty:
            continue

        baseline_candidate = baseline.copy()
        baseline_candidate["active"] = False
        baseline_candidate["rule_turnover"] = 0.0
        baseline_metric = _metric_row(
            frame=baseline_candidate,
            rule_id="final_candidate",
            sample=episode_name,
            return_column="candidate_return",
        )

        for rule_id, group in rule_returns.groupby("rule_id", sort=False):
            sample = group[(group["date"] >= start) & (group["date"] <= end)].copy()

            if sample.empty:
                continue

            metric = _metric_row(
                frame=sample,
                rule_id=str(rule_id),
                sample=episode_name,
                return_column="strategy_return",
            )
            rows.append(
                {
                    "rule_id": str(rule_id),
                    "episode": episode_name,
                    "rows": int(len(sample)),
                    "rule_cagr": metric["cagr"],
                    "baseline_cagr": baseline_metric["cagr"],
                    "cagr_delta": metric["cagr"] - baseline_metric["cagr"],
                    "rule_calmar": metric["calmar"],
                    "baseline_calmar": baseline_metric["calmar"],
                    "calmar_delta": metric["calmar"] - baseline_metric["calmar"],
                    "rule_max_drawdown": metric["max_drawdown"],
                    "baseline_max_drawdown": baseline_metric["max_drawdown"],
                    "drawdown_delta": (
                        metric["max_drawdown"] - baseline_metric["max_drawdown"]
                    ),
                }
            )

    return pd.DataFrame(rows)


def _lookup_metric(
    metrics: pd.DataFrame,
    *,
    rule_id: str,
    sample: str,
    column: str,
) -> float:
    rows = metrics[(metrics["rule_id"] == rule_id) & (metrics["sample"] == sample)]

    if rows.empty:
        return np.nan

    return float(rows.iloc[0][column])


def _gate_row(
    rule_id: str,
    gate: str,
    passed: bool,
    detail: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase10f_rule_gate_report(
    *,
    rule_metrics: pd.DataFrame,
    benchmark_metrics: pd.DataFrame,
    episode_metrics: pd.DataFrame,
    behavioural_metrics: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("validation_gates", {})
    friction = phase_config.get("friction", {})

    max_full_cagr_damage = float(gates.get("max_full_cagr_damage_pts", 0.15)) / 100.0
    max_episode_cagr_damage = (
        float(gates.get("max_episode_cagr_damage_pts", 0.25)) / 100.0
    )
    max_episode_calmar_damage = float(gates.get("max_episode_calmar_damage", 0.020))
    max_episode_dd_damage = (
        float(gates.get("max_episode_drawdown_damage_pts", 1.00)) / 100.0
    )
    max_stress_cagr_damage = (
        float(friction.get("max_stress_cagr_degradation_pts", 0.15)) / 100.0
    )
    max_stress_calmar_damage = float(
        friction.get("max_stress_calmar_degradation", 0.010)
    )

    baseline_full_cagr = _lookup_metric(
        benchmark_metrics,
        rule_id="final_candidate",
        sample="full",
        column="cagr",
    )
    baseline_full_calmar = _lookup_metric(
        benchmark_metrics,
        rule_id="final_candidate",
        sample="full",
        column="calmar",
    )
    baseline_full_dd = _lookup_metric(
        benchmark_metrics,
        rule_id="final_candidate",
        sample="full",
        column="max_drawdown",
    )
    baseline_holdout_cagr = _lookup_metric(
        benchmark_metrics,
        rule_id="final_candidate",
        sample="holdout",
        column="cagr",
    )
    baseline_holdout_calmar = _lookup_metric(
        benchmark_metrics,
        rule_id="final_candidate",
        sample="holdout",
        column="calmar",
    )
    baseline_holdout_dd = _lookup_metric(
        benchmark_metrics,
        rule_id="final_candidate",
        sample="holdout",
        column="max_drawdown",
    )
    buy_hold_full_cagr = _lookup_metric(
        benchmark_metrics,
        rule_id="spy_buy_hold",
        sample="full",
        column="cagr",
    )

    rows: list[dict[str, Any]] = []

    for rule_id in rule_metrics["rule_id"].drop_duplicates():
        full_cagr = _lookup_metric(
            rule_metrics,
            rule_id=str(rule_id),
            sample="full",
            column="cagr",
        )
        full_calmar = _lookup_metric(
            rule_metrics,
            rule_id=str(rule_id),
            sample="full",
            column="calmar",
        )
        full_dd = _lookup_metric(
            rule_metrics,
            rule_id=str(rule_id),
            sample="full",
            column="max_drawdown",
        )
        holdout_cagr = _lookup_metric(
            rule_metrics,
            rule_id=str(rule_id),
            sample="holdout",
            column="cagr",
        )
        holdout_calmar = _lookup_metric(
            rule_metrics,
            rule_id=str(rule_id),
            sample="holdout",
            column="calmar",
        )
        holdout_dd = _lookup_metric(
            rule_metrics,
            rule_id=str(rule_id),
            sample="holdout",
            column="max_drawdown",
        )
        stress_cagr = _lookup_metric(
            rule_metrics,
            rule_id=str(rule_id),
            sample="stress_full",
            column="cagr",
        )
        stress_calmar = _lookup_metric(
            rule_metrics,
            rule_id=str(rule_id),
            sample="stress_full",
            column="calmar",
        )

        if str(rule_id).startswith("H1"):
            calmar_gate = full_calmar > baseline_full_calmar
            calmar_gate_name = "Full-period Calmar improves versus final candidate"
        else:
            calmar_gate = full_calmar >= baseline_full_calmar
            calmar_gate_name = "Full-period Calmar is preserved versus final candidate"

        rows.append(
            _gate_row(
                str(rule_id),
                calmar_gate_name,
                calmar_gate,
                f"{full_calmar:.3f} vs baseline {baseline_full_calmar:.3f}",
            )
        )
        rows.append(
            _gate_row(
                str(rule_id),
                "Full-period CAGR damage is within limit",
                full_cagr >= baseline_full_cagr - max_full_cagr_damage,
                (
                    f"{full_cagr:.4%} vs baseline {baseline_full_cagr:.4%}; "
                    f"limit {max_full_cagr_damage:.4%}"
                ),
            )
        )
        rows.append(
            _gate_row(
                str(rule_id),
                "Full-period max drawdown is not worse",
                full_dd >= baseline_full_dd,
                f"{full_dd:.2%} vs baseline {baseline_full_dd:.2%}",
            )
        )
        rows.append(
            _gate_row(
                str(rule_id),
                "Holdout CAGR is not worse",
                holdout_cagr >= baseline_holdout_cagr,
                f"{holdout_cagr:.4%} vs baseline {baseline_holdout_cagr:.4%}",
            )
        )
        rows.append(
            _gate_row(
                str(rule_id),
                "Holdout Calmar is not worse",
                holdout_calmar >= baseline_holdout_calmar,
                f"{holdout_calmar:.3f} vs baseline {baseline_holdout_calmar:.3f}",
            )
        )
        rows.append(
            _gate_row(
                str(rule_id),
                "Holdout max drawdown is not worse",
                holdout_dd >= baseline_holdout_dd,
                f"{holdout_dd:.2%} vs baseline {baseline_holdout_dd:.2%}",
            )
        )

        rule_episode = episode_metrics[episode_metrics["rule_id"] == str(rule_id)]
        episode_damage_ok = True

        if not rule_episode.empty:
            episode_damage_ok = bool(
                (
                    rule_episode["cagr_delta"] >= -max_episode_cagr_damage
                ).all()
                and (
                    rule_episode["calmar_delta"] >= -max_episode_calmar_damage
                ).all()
                and (
                    rule_episode["drawdown_delta"] >= -max_episode_dd_damage
                ).all()
            )

        rows.append(
            _gate_row(
                str(rule_id),
                "Episode damage control passes",
                episode_damage_ok,
                "Episode CAGR/Calmar/drawdown damage must stay within limits.",
            )
        )
        rows.append(
            _gate_row(
                str(rule_id),
                "Stress friction degradation is controlled",
                (
                    stress_cagr >= full_cagr - max_stress_cagr_damage
                    and stress_calmar >= full_calmar - max_stress_calmar_damage
                ),
                (
                    f"stress CAGR {stress_cagr:.4%}; unstressed {full_cagr:.4%}; "
                    f"stress Calmar {stress_calmar:.3f}; unstressed {full_calmar:.3f}"
                ),
            )
        )

        behavioural = behavioural_metrics[
            behavioural_metrics["rule_id"] == str(rule_id)
        ]
        behavioural_ok = (
            bool(behavioural.iloc[0]["behavioural_regret_not_worse"])
            if not behavioural.empty
            else False
        )

        rows.append(
            _gate_row(
                str(rule_id),
                "Behavioural relative drawdown versus Buy & Hold is not worse",
                behavioural_ok,
                "Rule relative drawdown must not worsen versus baseline.",
            )
        )
        rows.append(
            _gate_row(
                str(rule_id),
                "Rule does not become raw-CAGR overclaim versus Buy & Hold",
                full_cagr < buy_hold_full_cagr,
                f"{full_cagr:.4%} vs Buy & Hold {buy_hold_full_cagr:.4%}",
            )
        )
        rows.append(
            _gate_row(
                str(rule_id),
                "No strategy promotion",
                True,
                "Maximum allowed role is candidate for further validation only.",
            )
        )

    gate_report = pd.DataFrame(rows)

    if gate_report.empty:
        return gate_report

    all_by_rule = gate_report.groupby("rule_id")["passed"].all().to_dict()
    gate_report["all_rule_gates_passed"] = gate_report["rule_id"].map(all_by_rule)
    gate_report["any_rule_passed"] = bool(any(all_by_rule.values()))

    return gate_report


def build_phase10f_rule_comparison_summary(
    *,
    rule_metrics: pd.DataFrame,
    benchmark_metrics: pd.DataFrame,
    rule_gate_report: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    baseline_full = benchmark_metrics[
        (benchmark_metrics["rule_id"] == "final_candidate")
        & (benchmark_metrics["sample"] == "full")
    ].iloc[0]

    for rule_id in rule_metrics["rule_id"].drop_duplicates():
        full = rule_metrics[
            (rule_metrics["rule_id"] == rule_id)
            & (rule_metrics["sample"] == "full")
        ].iloc[0]
        gates = rule_gate_report[rule_gate_report["rule_id"] == rule_id]
        all_passed = bool(gates["passed"].all()) if not gates.empty else False

        rows.append(
            {
                "rule_id": str(rule_id),
                "baseline_cagr": float(baseline_full["cagr"]),
                "rule_cagr": float(full["cagr"]),
                "cagr_delta": float(full["cagr"] - baseline_full["cagr"]),
                "baseline_calmar": float(baseline_full["calmar"]),
                "rule_calmar": float(full["calmar"]),
                "calmar_delta": float(full["calmar"] - baseline_full["calmar"]),
                "baseline_max_drawdown": float(baseline_full["max_drawdown"]),
                "rule_max_drawdown": float(full["max_drawdown"]),
                "drawdown_delta": float(
                    full["max_drawdown"] - baseline_full["max_drawdown"]
                ),
                "all_rule_gates_passed": all_passed,
                "strategy_promotion": False,
                "role": "Candidate for further validation only"
                if all_passed
                else "Rejected or mixed; no promotion",
            }
        )

    return pd.DataFrame(rows)


def build_phase10f_discipline_gate_report(
    *,
    phase_config: dict[str, Any],
    rule_metrics: pd.DataFrame,
    rule_gate_report: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    registry = set(str(item) for item in _as_list(
        phase_config.get("allowed_macro_input_registry")
    ))
    rules = _rules(phase_config)
    rule_ids = [str(rule.get("rule_id", "")) for rule in rules]
    expected_rule_ids = [str(item) for item in _as_list(gates.get("expected_rule_ids"))]

    conditions_inside_registry = True
    locked_thresholds = True

    for rule in rules:
        for condition in _as_list(rule.get("conditions")):
            input_name = str(condition.get("input", ""))
            derived = str(condition.get("derived_input", ""))
            conditions_inside_registry = (
                conditions_inside_registry
                and input_name in registry
                and derived in registry
            )
            locked_thresholds = locked_thresholds and bool(
                str(condition.get("locked_threshold_description", "")).strip()
            )

    rows = [
        {
            "gate": "Exact pre-registered rule IDs are used",
            "passed": sorted(rule_ids) == sorted(expected_rule_ids),
            "detail": "; ".join(rule_ids),
        },
        {
            "gate": "Rule count is bounded",
            "passed": int(gates.get("min_rules", 2))
            <= len(rules)
            <= int(gates.get("max_rules", 2)),
            "detail": f"rule_count={len(rules)}",
        },
        {
            "gate": "Rule condition inputs stay inside registry",
            "passed": conditions_inside_registry,
            "detail": f"conditions_inside_registry={conditions_inside_registry}",
        },
        {
            "gate": "Locked thresholds are documented",
            "passed": locked_thresholds,
            "detail": f"locked_thresholds={locked_thresholds}",
        },
        {
            "gate": "No new thresholds are allowed",
            "passed": not bool(phase_config.get("allow_new_thresholds", True)),
            "detail": f"allow_new_thresholds={phase_config.get('allow_new_thresholds')}",
        },
        {
            "gate": "No new inputs are allowed",
            "passed": not bool(phase_config.get("allow_new_inputs", True)),
            "detail": f"allow_new_inputs={phase_config.get('allow_new_inputs')}",
        },
        {
            "gate": "No model feature creation is allowed",
            "passed": not bool(phase_config.get("allow_model_feature_creation", True)),
            "detail": (
                "allow_model_feature_creation="
                f"{phase_config.get('allow_model_feature_creation')}"
            ),
        },
        {
            "gate": "No model training is allowed",
            "passed": not bool(phase_config.get("allow_model_training", True)),
            "detail": f"allow_model_training={phase_config.get('allow_model_training')}",
        },
        {
            "gate": "No strategy promotion is allowed",
            "passed": not bool(phase_config.get("allow_strategy_promotion", True)),
            "detail": (
                "allow_strategy_promotion="
                f"{phase_config.get('allow_strategy_promotion')}"
            ),
        },
        {
            "gate": "Rule metrics were generated",
            "passed": not rule_metrics.empty,
            "detail": f"metric_rows={len(rule_metrics)}",
        },
        {
            "gate": "Rule gate report was generated",
            "passed": not rule_gate_report.empty,
            "detail": f"gate_rows={len(rule_gate_report)}",
        },
        {
            "gate": "Test role is correct",
            "passed": str(phase_config.get("test_role", ""))
            == str(gates.get("required_test_role", "")),
            "detail": f"test_role={phase_config.get('test_role')}",
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})
    frame["all_discipline_gates_passed"] = bool(frame["passed"].all())

    return frame


def build_phase10f_conclusion(
    *,
    discipline_gate_report: pd.DataFrame,
    rule_gate_report: pd.DataFrame,
) -> pd.DataFrame:
    discipline_passed = bool(discipline_gate_report["passed"].all())

    if rule_gate_report.empty:
        any_rule_passed = False
        passed_rules = ""
    else:
        by_rule = rule_gate_report.groupby("rule_id")["passed"].all()
        any_rule_passed = bool(by_rule.any())
        passed_rules = "; ".join(by_rule[by_rule].index.astype(str).tolist())

    if not discipline_passed:
        verdict = "Failed pre-registered macro-rule test discipline"
        interpretation = (
            "Phase 10F did not satisfy discipline gates. Do not interpret rule "
            "results until pre-registration boundaries are fixed."
        )
    elif any_rule_passed:
        verdict = "Passed for further validation only"
        interpretation = (
            "At least one pre-registered macro rule passed configured gates. "
            "This is not promotion and does not change the final hierarchy."
        )
    else:
        verdict = "Failed / no pre-registered macro rule passed"
        interpretation = (
            "No pre-registered macro rule passed all configured gates. Document "
            "the failure and do not tune around it."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 10F",
                "diagnostic": "Pre-registered macro-rule test",
                "verdict": verdict,
                "discipline_gates_passed": discipline_passed,
                "any_rule_passed": any_rule_passed,
                "passed_rules": passed_rules,
                "strategy_promotion": False,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase10f_markdown(
    *,
    rule_metrics: pd.DataFrame,
    benchmark_metrics: pd.DataFrame,
    episode_metrics: pd.DataFrame,
    behavioural_metrics: pd.DataFrame,
    rule_gate_report: pd.DataFrame,
    rule_comparison_summary: pd.DataFrame,
    discipline_gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 10F — Pre-Registered Macro Rule Test",
        "",
        "## Purpose",
        "",
        (
            "This phase tests only the two Phase 10E pre-registered macro "
            "hypotheses. It does not add thresholds, inputs, sentiment, "
            "fundamentals, ML, optimisation, or promotion."
        ),
        "",
        "## Rule Metrics",
        "",
        rule_metrics.to_markdown(index=False),
        "",
        "## Benchmark Metrics",
        "",
        benchmark_metrics.to_markdown(index=False),
        "",
        "## Episode Metrics",
        "",
        episode_metrics.to_markdown(index=False),
        "",
        "## Behavioural Metrics",
        "",
        behavioural_metrics.to_markdown(index=False),
        "",
        "## Rule Gate Report",
        "",
        rule_gate_report.to_markdown(index=False),
        "",
        "## Rule Comparison Summary",
        "",
        rule_comparison_summary.to_markdown(index=False),
        "",
        "## Discipline Gate Report",
        "",
        discipline_gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        conclusion.to_markdown(index=False),
        "",
        "## Limitations",
        "",
        "- Passing this phase would only allow further validation.",
        "- No macro rule is promoted by Phase 10F.",
        "- Failed or mixed results must not be tuned around.",
        "- The final candidate hierarchy remains unchanged.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase10f_preregistered_macro_rule_test(
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
            "activation_frame": empty,
            "rule_returns": empty,
            "rule_metrics": empty,
            "benchmark_metrics": empty,
            "episode_metrics": empty,
            "behavioural_metrics": empty,
            "rule_gate_report": empty,
            "rule_comparison_summary": empty,
            "discipline_gate_report": empty,
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
            phase_config.get(
                "macro_aligned_series_path",
                "reports/phase10c_macro_aligned_series.csv",
            )
        )

    macro_panel = build_phase10f_macro_panel(
        macro_aligned_series=macro_aligned_series,
        phase_config=phase_config,
    )
    activation_frame = build_phase10f_rule_activation_frame(
        macro_panel=macro_panel,
        phase_config=phase_config,
    )
    base_returns = build_phase10f_base_return_frame(
        final_candidate=final_candidate,
        spy_buy_hold=spy_buy_hold,
        spy_12m_momentum=spy_12m_momentum,
    )
    rule_returns = build_phase10f_rule_returns(
        base_returns=base_returns,
        activation_frame=activation_frame,
        phase_config=phase_config,
    )
    rule_metrics = build_phase10f_rule_metrics(
        rule_returns=rule_returns,
        phase_config=phase_config,
    )
    benchmark_metrics = build_phase10f_benchmark_metrics(
        base_returns=base_returns,
        phase_config=phase_config,
    )
    episode_metrics = build_phase10f_episode_metrics(
        rule_returns=rule_returns,
        base_returns=base_returns,
        phase_config=phase_config,
    )
    behavioural_metrics = build_phase10f_behavioural_metrics(rule_returns)
    rule_gate_report = build_phase10f_rule_gate_report(
        rule_metrics=rule_metrics,
        benchmark_metrics=benchmark_metrics,
        episode_metrics=episode_metrics,
        behavioural_metrics=behavioural_metrics,
        phase_config=phase_config,
    )
    rule_comparison_summary = build_phase10f_rule_comparison_summary(
        rule_metrics=rule_metrics,
        benchmark_metrics=benchmark_metrics,
        rule_gate_report=rule_gate_report,
    )
    discipline_gate_report = build_phase10f_discipline_gate_report(
        phase_config=phase_config,
        rule_metrics=rule_metrics,
        rule_gate_report=rule_gate_report,
    )
    conclusion = build_phase10f_conclusion(
        discipline_gate_report=discipline_gate_report,
        rule_gate_report=rule_gate_report,
    )

    macro_panel.to_csv(reports_path / "phase10f_macro_panel.csv", index=False)
    activation_frame.to_csv(
        reports_path / "phase10f_macro_rule_activation_frame.csv",
        index=False,
    )
    rule_returns.to_csv(reports_path / "phase10f_macro_rule_returns.csv", index=False)
    rule_metrics.to_csv(reports_path / "phase10f_macro_rule_metrics.csv", index=False)
    benchmark_metrics.to_csv(
        reports_path / "phase10f_macro_benchmark_metrics.csv",
        index=False,
    )
    episode_metrics.to_csv(
        reports_path / "phase10f_macro_episode_metrics.csv",
        index=False,
    )
    behavioural_metrics.to_csv(
        reports_path / "phase10f_macro_behavioural_metrics.csv",
        index=False,
    )
    rule_gate_report.to_csv(
        reports_path / "phase10f_macro_rule_gate_report.csv",
        index=False,
    )
    rule_comparison_summary.to_csv(
        reports_path / "phase10f_macro_rule_comparison_summary.csv",
        index=False,
    )
    discipline_gate_report.to_csv(
        reports_path / "phase10f_macro_discipline_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(reports_path / "phase10f_macro_conclusion.csv", index=False)

    write_phase10f_markdown(
        rule_metrics=rule_metrics,
        benchmark_metrics=benchmark_metrics,
        episode_metrics=episode_metrics,
        behavioural_metrics=behavioural_metrics,
        rule_gate_report=rule_gate_report,
        rule_comparison_summary=rule_comparison_summary,
        discipline_gate_report=discipline_gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase10f_preregistered_macro_rule_test.md",
    )

    print("Wrote Phase 10F pre-registered macro rule test reports.")

    return {
        "macro_panel": macro_panel,
        "activation_frame": activation_frame,
        "rule_returns": rule_returns,
        "rule_metrics": rule_metrics,
        "benchmark_metrics": benchmark_metrics,
        "episode_metrics": episode_metrics,
        "behavioural_metrics": behavioural_metrics,
        "rule_gate_report": rule_gate_report,
        "rule_comparison_summary": rule_comparison_summary,
        "discipline_gate_report": discipline_gate_report,
        "conclusion": conclusion,
    }