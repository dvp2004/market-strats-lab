from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.technical_indicator_expansion_diagnostic import (
    _get_phase_config as _get_phase9a_config,
)
from market_strats.analysis.technical_indicator_expansion_diagnostic import (
    _resolve_phase9a_input_frames,
    build_phase9a_analysis_frame,
    build_phase9a_indicator_frame,
    build_phase9a_regime_frame,
)


DEFAULT_PHASE9D_CONFIG: dict[str, Any] = {
    "enabled": False,
    "initial_capital": 10000.0,
    "ticker": "SPY",
    "baseline_strategy_name": "Final candidate",
    "rule_definitions": [],
    "holdout": {
        "start_date": "2021-01-01",
        "end_date": "2026-05-01",
    },
    "episode_definitions": {
        "crisis_2006_2010": {
            "start_date": "2006-04-28",
            "end_date": "2010-12-31",
        },
        "post_crisis_2011_2015": {
            "start_date": "2011-01-01",
            "end_date": "2015-12-31",
        },
        "bull_covid_2016_2020": {
            "start_date": "2016-01-01",
            "end_date": "2020-12-31",
        },
        "inflation_2021_2026": {
            "start_date": "2021-01-01",
            "end_date": "2026-05-01",
        },
    },
    "stress_friction": {
        "scenario_name": "phase8b_style_stress",
        "spread_bps": 5.0,
        "impact_bps_per_100pct_turnover": 10.0,
        "stress_drawdown_threshold": -0.10,
        "deep_stress_drawdown_threshold": -0.20,
        "stress_multiplier": 3.0,
        "deep_stress_multiplier": 5.0,
    },
    "gates": {
        "max_full_cagr_reduction_pts_vs_baseline": 0.15,
        "min_full_calmar_delta_vs_baseline": 0.0001,
        "require_full_drawdown_not_worse": True,
        "require_holdout_cagr_not_worse": True,
        "require_holdout_calmar_not_worse": True,
        "require_holdout_drawdown_not_worse": True,
        "max_episode_cagr_damage_pts": 0.25,
        "max_episode_calmar_damage": 0.02,
        "require_stress_calmar_not_worse": True,
        "require_stress_drawdown_not_worse": True,
        "require_behavioural_relative_drawdown_not_worse": True,
        "require_no_strategy_promotion": True,
        "max_allowed_role": "Candidate for further validation only",
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
    user_config = config.get("phase9d_preregistered_technical_rule_test", {})
    return _deep_merge_dict(DEFAULT_PHASE9D_CONFIG, user_config)


def _normalise_strategy_frame(frame: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    required_columns = {"date", "strategy_return"}
    missing = required_columns.difference(frame.columns)

    if missing:
        raise ValueError(f"{strategy_name} is missing required columns: {sorted(missing)}")

    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    out["strategy_return"] = pd.to_numeric(
        out["strategy_return"],
        errors="coerce",
    ).fillna(0.0)

    if "turnover" in out.columns:
        out["base_turnover"] = pd.to_numeric(
            out["turnover"],
            errors="coerce",
        ).fillna(0.0)
    elif "overlay_turnover" in out.columns:
        out["base_turnover"] = pd.to_numeric(
            out["overlay_turnover"],
            errors="coerce",
        ).fillna(0.0)
    else:
        out["base_turnover"] = 0.0

    out["base_turnover"] = out["base_turnover"].clip(lower=0.0)

    return out


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


def _equity_curve(returns: pd.Series, initial_capital: float) -> pd.Series:
    clean_returns = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    return initial_capital * (1.0 + clean_returns).cumprod()


def _drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def _max_drawdown(equity: pd.Series) -> float:
    return float(_drawdown(equity).min())


def _cagr(equity: pd.Series, dates: pd.Series) -> float:
    clean_dates = pd.to_datetime(dates).dropna().sort_values()

    if len(clean_dates) < 2 or equity.empty:
        return 0.0

    years = (clean_dates.iloc[-1] - clean_dates.iloc[0]).days / 365.25

    if years <= 0 or equity.iloc[0] <= 0:
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


def _metric_row(frame: pd.DataFrame, *, period: str, initial_capital: float) -> dict[str, Any]:
    equity = _equity_curve(frame["strategy_return"], initial_capital)
    cagr = _cagr(equity, frame["date"])
    max_dd = _max_drawdown(equity)

    return {
        "strategy": frame["strategy"].iloc[0],
        "rule_id": frame["rule_id"].iloc[0],
        "period": period,
        "start_date": pd.to_datetime(frame["date"].iloc[0]).date().isoformat(),
        "end_date": pd.to_datetime(frame["date"].iloc[-1]).date().isoformat(),
        "rows": int(len(frame)),
        "end_value": float(equity.iloc[-1]),
        "cagr": cagr,
        "volatility": _volatility(frame["strategy_return"], frame["date"]),
        "max_drawdown": max_dd,
        "calmar": _calmar(cagr, max_dd),
        "total_turnover": float(frame["turnover"].sum()),
        "trade_count": int((frame["turnover"] > 0).sum()),
    }


def _slice_frame(frame: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    out = frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()
    out = out.sort_values("date").reset_index(drop=True)

    if not out.empty:
        out.loc[out.index[0], "strategy_return"] = 0.0

    return out


def _turnover_from_active_flag(active_flag: pd.Series) -> pd.Series:
    active = active_flag.astype(int)
    turnover = active.diff().abs().fillna(active.iloc[0]).astype(float)
    return turnover


def _build_baseline_frame(
    analysis_frame: pd.DataFrame,
    final_candidate: pd.DataFrame,
) -> pd.DataFrame:
    candidate = _normalise_strategy_frame(final_candidate, "Final candidate")

    out = analysis_frame[
        [
            "date",
            "candidate_return",
            "buy_hold_return",
            "spy_12m_return",
            "rsi",
            "momentum_long",
        ]
    ].copy()

    out = out.merge(
        candidate[["date", "base_turnover"]],
        on="date",
        how="left",
    )
    out["base_turnover"] = out["base_turnover"].fillna(0.0)

    out["strategy"] = "Final candidate"
    out["rule_id"] = "baseline_final_candidate"
    out["strategy_return"] = out["candidate_return"]
    out["turnover"] = out["base_turnover"]

    return out[
        [
            "date",
            "strategy",
            "rule_id",
            "strategy_return",
            "turnover",
            "base_turnover",
            "candidate_return",
            "buy_hold_return",
            "spy_12m_return",
            "rsi",
            "momentum_long",
        ]
    ]


def _apply_rule(
    baseline_frame: pd.DataFrame,
    rule_definition: dict[str, Any],
) -> pd.DataFrame:
    rule_type = str(rule_definition.get("rule_type", ""))
    rule_id = str(rule_definition.get("rule_id", ""))
    name = str(rule_definition.get("name", rule_id))

    out = baseline_frame.copy()

    if rule_type == "oversold_rsi_reentry_relief":
        threshold = float(rule_definition.get("rsi_threshold", 30.0))
        active = pd.to_numeric(out["rsi"], errors="coerce") < threshold
        rule_return = np.where(active, out["buy_hold_return"], out["candidate_return"])

    elif rule_type == "negative_12m_momentum_defensive_confirmation":
        threshold = float(rule_definition.get("momentum_threshold", 0.0))
        active = pd.to_numeric(out["momentum_long"], errors="coerce") < threshold
        rule_return = np.where(active, out["spy_12m_return"], out["candidate_return"])

    else:
        raise ValueError(f"Unknown Phase 9D rule_type: {rule_type!r}")

    rule_turnover = _turnover_from_active_flag(pd.Series(active, index=out.index))

    out["strategy"] = name
    out["rule_id"] = rule_id
    out["strategy_return"] = pd.Series(rule_return, index=out.index).astype(float)
    out["turnover"] = out["base_turnover"] + rule_turnover
    out["rule_active"] = active.astype(bool)

    return out[
        [
            "date",
            "strategy",
            "rule_id",
            "strategy_return",
            "turnover",
            "candidate_return",
            "buy_hold_return",
            "spy_12m_return",
            "rsi",
            "momentum_long",
            "rule_active",
        ]
    ]


def build_phase9d_rule_return_frame(
    *,
    analysis_frame: pd.DataFrame,
    final_candidate: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    baseline = _build_baseline_frame(analysis_frame, final_candidate)

    frames = [baseline.assign(rule_active=False)]

    for rule_definition in phase_config.get("rule_definitions", []):
        frames.append(_apply_rule(baseline, rule_definition))

    return pd.concat(frames, ignore_index=True)


def build_phase9d_metrics(
    rule_return_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    initial_capital = float(phase_config.get("initial_capital", 10000.0))
    holdout = phase_config.get("holdout", {})
    episodes = phase_config.get("episode_definitions", {})

    rows: list[dict[str, Any]] = []

    for _, group in rule_return_frame.groupby(["strategy", "rule_id"], sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        rows.append(_metric_row(group, period="full", initial_capital=initial_capital))

        holdout_frame = _slice_frame(
            group,
            str(holdout.get("start_date", "2021-01-01")),
            str(holdout.get("end_date", "2026-05-01")),
        )
        if not holdout_frame.empty:
            rows.append(
                _metric_row(
                    holdout_frame,
                    period="holdout",
                    initial_capital=initial_capital,
                )
            )

        for episode_name, episode_config in episodes.items():
            episode_frame = _slice_frame(
                group,
                str(episode_config["start_date"]),
                str(episode_config["end_date"]),
            )
            if not episode_frame.empty:
                rows.append(
                    _metric_row(
                        episode_frame,
                        period=f"episode_{episode_name}",
                        initial_capital=initial_capital,
                    )
                )

    return pd.DataFrame(rows)


def _stress_multiplier(drawdowns: pd.Series, scenario: dict[str, Any]) -> pd.Series:
    stress_threshold = float(scenario.get("stress_drawdown_threshold", -0.10))
    deep_threshold = float(scenario.get("deep_stress_drawdown_threshold", -0.20))
    stress_multiplier = float(scenario.get("stress_multiplier", 1.0))
    deep_multiplier = float(scenario.get("deep_stress_multiplier", stress_multiplier))

    multiplier = pd.Series(1.0, index=drawdowns.index)
    multiplier = multiplier.mask(drawdowns <= stress_threshold, stress_multiplier)
    multiplier = multiplier.mask(drawdowns <= deep_threshold, deep_multiplier)

    return multiplier


def _apply_stress_friction(
    frame: pd.DataFrame,
    *,
    scenario: dict[str, Any],
    initial_capital: float,
) -> pd.DataFrame:
    out = frame.sort_values("date").reset_index(drop=True).copy()

    base_equity = _equity_curve(out["strategy_return"], initial_capital)
    base_drawdown = _drawdown(base_equity)

    spread_bps = float(scenario.get("spread_bps", 5.0))
    impact_bps = float(scenario.get("impact_bps_per_100pct_turnover", 10.0))

    multiplier = _stress_multiplier(base_drawdown, scenario)
    effective_cost_bps = (spread_bps + impact_bps * out["turnover"]) * multiplier
    extra_cost_return = out["turnover"] * effective_cost_bps / 10000.0

    out["base_strategy_return"] = out["strategy_return"]
    out["strategy_return"] = out["strategy_return"] - extra_cost_return
    out["stress_extra_cost_return"] = extra_cost_return
    out["stress_effective_cost_bps"] = effective_cost_bps

    return out


def build_phase9d_stress_metrics(
    rule_return_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    initial_capital = float(phase_config.get("initial_capital", 10000.0))
    scenario = phase_config.get("stress_friction", {})
    scenario_name = str(scenario.get("scenario_name", "phase8b_style_stress"))

    rows: list[dict[str, Any]] = []

    for _, group in rule_return_frame.groupby(["strategy", "rule_id"], sort=False):
        stressed = _apply_stress_friction(
            group,
            scenario=scenario,
            initial_capital=initial_capital,
        )
        row = _metric_row(
            stressed,
            period=f"stress_{scenario_name}",
            initial_capital=initial_capital,
        )
        row["total_stress_extra_cost_return"] = float(
            stressed["stress_extra_cost_return"].sum()
        )
        rows.append(row)

    return pd.DataFrame(rows)


def _relative_drawdown(rule_frame: pd.DataFrame, benchmark_return_column: str) -> float:
    rule_equity = _equity_curve(rule_frame["strategy_return"], 1.0)
    benchmark_equity = _equity_curve(rule_frame[benchmark_return_column], 1.0)
    relative_wealth = rule_equity / benchmark_equity
    relative_drawdown = relative_wealth / relative_wealth.cummax() - 1.0
    return float(relative_drawdown.min())


def _terminal_relative_wealth(
    rule_frame: pd.DataFrame,
    benchmark_return_column: str,
) -> float:
    rule_equity = _equity_curve(rule_frame["strategy_return"], 1.0)
    benchmark_equity = _equity_curve(rule_frame[benchmark_return_column], 1.0)
    return float((rule_equity / benchmark_equity).iloc[-1])


def build_phase9d_behavioural_metrics(
    rule_return_frame: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, group in rule_return_frame.groupby(["strategy", "rule_id"], sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        rows.append(
            {
                "strategy": group["strategy"].iloc[0],
                "rule_id": group["rule_id"].iloc[0],
                "terminal_relative_wealth_vs_buy_hold": _terminal_relative_wealth(
                    group,
                    "buy_hold_return",
                ),
                "terminal_relative_wealth_vs_spy_12m": _terminal_relative_wealth(
                    group,
                    "spy_12m_return",
                ),
                "relative_drawdown_vs_buy_hold": _relative_drawdown(
                    group,
                    "buy_hold_return",
                ),
                "relative_drawdown_vs_spy_12m": _relative_drawdown(
                    group,
                    "spy_12m_return",
                ),
            }
        )

    return pd.DataFrame(rows)


def _baseline_row(metrics: pd.DataFrame, period: str) -> pd.Series:
    rows = metrics[
        (metrics["rule_id"] == "baseline_final_candidate")
        & (metrics["period"] == period)
    ]

    if rows.empty:
        raise ValueError(f"Missing baseline metrics for period {period!r}")

    return rows.iloc[0]


def _candidate_rows(metrics: pd.DataFrame, period: str) -> pd.DataFrame:
    return metrics[
        (metrics["rule_id"] != "baseline_final_candidate")
        & (metrics["period"] == period)
    ].copy()


def build_phase9d_comparison_summary(
    metrics: pd.DataFrame,
    stress_metrics: pd.DataFrame,
    behavioural_metrics: pd.DataFrame,
) -> pd.DataFrame:
    baseline_full = _baseline_row(metrics, "full")
    baseline_holdout = _baseline_row(metrics, "holdout")
    baseline_stress = _baseline_row(stress_metrics, stress_metrics["period"].iloc[0])

    baseline_behaviour = behavioural_metrics[
        behavioural_metrics["rule_id"] == "baseline_final_candidate"
    ].iloc[0]

    rows: list[dict[str, Any]] = []

    for _, full_row in _candidate_rows(metrics, "full").iterrows():
        rule_id = str(full_row["rule_id"])
        holdout_row = metrics[
            (metrics["rule_id"] == rule_id) & (metrics["period"] == "holdout")
        ].iloc[0]
        stress_row = stress_metrics[stress_metrics["rule_id"] == rule_id].iloc[0]
        behaviour_row = behavioural_metrics[
            behavioural_metrics["rule_id"] == rule_id
        ].iloc[0]

        episode_rows = metrics[
            (metrics["rule_id"] == rule_id) & metrics["period"].str.startswith("episode_")
        ]
        episode_baseline = metrics[
            (metrics["rule_id"] == "baseline_final_candidate")
            & metrics["period"].str.startswith("episode_")
        ][["period", "cagr", "calmar"]].rename(
            columns={
                "cagr": "baseline_episode_cagr",
                "calmar": "baseline_episode_calmar",
            }
        )
        episode_compare = episode_rows.merge(episode_baseline, on="period", how="left")
        episode_compare["episode_cagr_delta"] = (
            episode_compare["cagr"] - episode_compare["baseline_episode_cagr"]
        )
        episode_compare["episode_calmar_delta"] = (
            episode_compare["calmar"] - episode_compare["baseline_episode_calmar"]
        )

        rows.append(
            {
                "rule_id": rule_id,
                "strategy": full_row["strategy"],
                "full_cagr": float(full_row["cagr"]),
                "baseline_full_cagr": float(baseline_full["cagr"]),
                "full_cagr_delta": float(full_row["cagr"] - baseline_full["cagr"]),
                "full_calmar": float(full_row["calmar"]),
                "baseline_full_calmar": float(baseline_full["calmar"]),
                "full_calmar_delta": float(
                    full_row["calmar"] - baseline_full["calmar"]
                ),
                "full_max_drawdown": float(full_row["max_drawdown"]),
                "baseline_full_max_drawdown": float(baseline_full["max_drawdown"]),
                "full_max_drawdown_delta": float(
                    full_row["max_drawdown"] - baseline_full["max_drawdown"]
                ),
                "holdout_cagr_delta": float(
                    holdout_row["cagr"] - baseline_holdout["cagr"]
                ),
                "holdout_calmar_delta": float(
                    holdout_row["calmar"] - baseline_holdout["calmar"]
                ),
                "holdout_max_drawdown_delta": float(
                    holdout_row["max_drawdown"] - baseline_holdout["max_drawdown"]
                ),
                "worst_episode_cagr_delta": float(
                    episode_compare["episode_cagr_delta"].min()
                ),
                "worst_episode_calmar_delta": float(
                    episode_compare["episode_calmar_delta"].min()
                ),
                "stress_cagr_delta": float(
                    stress_row["cagr"] - baseline_stress["cagr"]
                ),
                "stress_calmar_delta": float(
                    stress_row["calmar"] - baseline_stress["calmar"]
                ),
                "stress_max_drawdown_delta": float(
                    stress_row["max_drawdown"] - baseline_stress["max_drawdown"]
                ),
                "terminal_relative_wealth_vs_buy_hold_delta": float(
                    behaviour_row["terminal_relative_wealth_vs_buy_hold"]
                    - baseline_behaviour["terminal_relative_wealth_vs_buy_hold"]
                ),
                "relative_drawdown_vs_buy_hold_delta": float(
                    behaviour_row["relative_drawdown_vs_buy_hold"]
                    - baseline_behaviour["relative_drawdown_vs_buy_hold"]
                ),
                "role": "Candidate for further validation only",
                "strategy_promotion": False,
            }
        )

    return pd.DataFrame(rows)


def _gate_row(rule_id: str, gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase9d_gate_report(
    comparison_summary: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    max_cagr_reduction = (
        float(gates.get("max_full_cagr_reduction_pts_vs_baseline", 0.15)) / 100.0
    )
    min_calmar_delta = float(gates.get("min_full_calmar_delta_vs_baseline", 0.0001))
    max_episode_cagr_damage = (
        float(gates.get("max_episode_cagr_damage_pts", 0.25)) / 100.0
    )
    max_episode_calmar_damage = float(gates.get("max_episode_calmar_damage", 0.02))
    max_role = str(gates.get("max_allowed_role", "Candidate for further validation only"))

    rows: list[dict[str, Any]] = []

    for _, row in comparison_summary.iterrows():
        rule_id = str(row["rule_id"])

        rows.extend(
            [
                _gate_row(
                    rule_id,
                    "Full-period CAGR is not materially reduced",
                    float(row["full_cagr_delta"]) >= -max_cagr_reduction,
                    f"delta={row['full_cagr_delta']:.4%}; limit={-max_cagr_reduction:.4%}",
                ),
                _gate_row(
                    rule_id,
                    "Full-period Calmar improves versus final candidate",
                    float(row["full_calmar_delta"]) > min_calmar_delta,
                    f"delta={row['full_calmar_delta']:.4f}; required > {min_calmar_delta:.4f}",
                ),
                _gate_row(
                    rule_id,
                    "Full-period max drawdown is not worse",
                    (not gates.get("require_full_drawdown_not_worse", True))
                    or float(row["full_max_drawdown_delta"]) >= 0.0,
                    f"delta={row['full_max_drawdown_delta']:.4%}",
                ),
                _gate_row(
                    rule_id,
                    "Holdout CAGR is not worse",
                    (not gates.get("require_holdout_cagr_not_worse", True))
                    or float(row["holdout_cagr_delta"]) >= 0.0,
                    f"delta={row['holdout_cagr_delta']:.4%}",
                ),
                _gate_row(
                    rule_id,
                    "Holdout Calmar is not worse",
                    (not gates.get("require_holdout_calmar_not_worse", True))
                    or float(row["holdout_calmar_delta"]) >= 0.0,
                    f"delta={row['holdout_calmar_delta']:.4f}",
                ),
                _gate_row(
                    rule_id,
                    "Holdout max drawdown is not worse",
                    (not gates.get("require_holdout_drawdown_not_worse", True))
                    or float(row["holdout_max_drawdown_delta"]) >= 0.0,
                    f"delta={row['holdout_max_drawdown_delta']:.4%}",
                ),
                _gate_row(
                    rule_id,
                    "Episode CAGR damage is within limit",
                    float(row["worst_episode_cagr_delta"]) >= -max_episode_cagr_damage,
                    f"worst={row['worst_episode_cagr_delta']:.4%}; limit={-max_episode_cagr_damage:.4%}",
                ),
                _gate_row(
                    rule_id,
                    "Episode Calmar damage is within limit",
                    float(row["worst_episode_calmar_delta"]) >= -max_episode_calmar_damage,
                    f"worst={row['worst_episode_calmar_delta']:.4f}; limit={-max_episode_calmar_damage:.4f}",
                ),
                _gate_row(
                    rule_id,
                    "Stress Calmar is not worse",
                    (not gates.get("require_stress_calmar_not_worse", True))
                    or float(row["stress_calmar_delta"]) >= 0.0,
                    f"delta={row['stress_calmar_delta']:.4f}",
                ),
                _gate_row(
                    rule_id,
                    "Stress max drawdown is not worse",
                    (not gates.get("require_stress_drawdown_not_worse", True))
                    or float(row["stress_max_drawdown_delta"]) >= 0.0,
                    f"delta={row['stress_max_drawdown_delta']:.4%}",
                ),
                _gate_row(
                    rule_id,
                    "Behavioural relative drawdown versus Buy & Hold is not worse",
                    (
                        not gates.get(
                            "require_behavioural_relative_drawdown_not_worse",
                            True,
                        )
                    )
                    or float(row["relative_drawdown_vs_buy_hold_delta"]) >= 0.0,
                    f"delta={row['relative_drawdown_vs_buy_hold_delta']:.4%}",
                ),
                _gate_row(
                    rule_id,
                    "No strategy promotion",
                    (not gates.get("require_no_strategy_promotion", True))
                    or not bool(row["strategy_promotion"]),
                    f"strategy_promotion={bool(row['strategy_promotion'])}",
                ),
                _gate_row(
                    rule_id,
                    "Role remains bounded",
                    str(row["role"]) == max_role,
                    f"role={row['role']}",
                ),
            ]
        )

    gate_report = pd.DataFrame(rows)

    if gate_report.empty:
        return gate_report

    pass_map = gate_report.groupby("rule_id")["passed"].all().to_dict()
    gate_report["all_rule_gates_passed"] = gate_report["rule_id"].map(pass_map)
    gate_report["any_rule_passed"] = bool(any(pass_map.values()))

    return gate_report


def build_phase9d_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    if gate_report.empty:
        verdict = "Failed — no rule gates evaluated"
        passed_rules = ""
        interpretation = "Phase 9D did not evaluate any pre-registered rule gates."
    else:
        passed_rules_list = sorted(
            rule_id
            for rule_id, group in gate_report.groupby("rule_id")
            if bool(group["passed"].all())
        )
        passed_rules = "; ".join(passed_rules_list)

        if passed_rules_list:
            verdict = "Passed for further validation"
            interpretation = (
                "At least one pre-registered technical rule passed Phase 9D gates. "
                "This does not promote the rule; it only allows further validation."
            )
        else:
            verdict = "Failed / no pre-registered rule passed"
            interpretation = (
                "No pre-registered technical rule passed every Phase 9D gate. "
                "Do not tune the rules around this result."
            )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 9D",
                "diagnostic": "Pre-registered technical rule test",
                "verdict": verdict,
                "passed_rules": passed_rules,
                "all_gates_passed_for_at_least_one_rule": bool(passed_rules),
                "interpretation": interpretation,
            }
        ]
    )


def write_phase9d_markdown(
    *,
    metrics: pd.DataFrame,
    stress_metrics: pd.DataFrame,
    behavioural_metrics: pd.DataFrame,
    comparison_summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 9D — Pre-Registered Technical Rule Test",
        "",
        "## Purpose",
        "",
        (
            "This phase tests only the two Phase 9C pre-registered technical-rule "
            "hypotheses. It does not add new inputs, search thresholds, or promote "
            "a strategy."
        ),
        "",
        "## Metrics",
        "",
        metrics.to_markdown(index=False),
        "",
        "## Stress Metrics",
        "",
        stress_metrics.to_markdown(index=False),
        "",
        "## Behavioural Metrics",
        "",
        behavioural_metrics.to_markdown(index=False),
        "",
        "## Comparison Summary",
        "",
        comparison_summary.to_markdown(index=False),
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
        "- This is the first pre-registered technical-rule test.",
        "- Passing Phase 9D would only allow further validation.",
        "- Failing Phase 9D should be documented, not tuned away.",
        "- No new inputs or thresholds are allowed in this phase.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase9d_preregistered_technical_rule_test(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
    final_candidate: pd.DataFrame | None = None,
    spy_buy_hold: pd.DataFrame | None = None,
    spy_12m_momentum: pd.DataFrame | None = None,
    price_data: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "rule_return_frame": empty,
            "metrics": empty,
            "stress_metrics": empty,
            "behavioural_metrics": empty,
            "comparison_summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase9a_config = _get_phase9a_config(config)

    final_candidate, spy_buy_hold, spy_12m_momentum, prices = (
        _resolve_phase9a_input_frames(
            config=config,
            phase_config=phase9a_config,
            final_candidate=final_candidate,
            spy_buy_hold=spy_buy_hold,
            spy_12m_momentum=spy_12m_momentum,
            price_data=price_data,
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
        )
    )

    indicator_frame = build_phase9a_indicator_frame(prices, phase9a_config)
    regime_frame = build_phase9a_regime_frame(indicator_frame, phase9a_config)
    analysis_frame = build_phase9a_analysis_frame(
        final_candidate=final_candidate,
        spy_buy_hold=spy_buy_hold,
        spy_12m_momentum=spy_12m_momentum,
        regime_frame=regime_frame,
    )
    rule_return_frame = build_phase9d_rule_return_frame(
        analysis_frame=analysis_frame,
        final_candidate=final_candidate,
        phase_config=phase_config,
    )
    metrics = build_phase9d_metrics(rule_return_frame, phase_config)
    stress_metrics = build_phase9d_stress_metrics(rule_return_frame, phase_config)
    behavioural_metrics = build_phase9d_behavioural_metrics(rule_return_frame)
    comparison_summary = build_phase9d_comparison_summary(
        metrics,
        stress_metrics,
        behavioural_metrics,
    )
    gate_report = build_phase9d_gate_report(comparison_summary, phase_config)
    conclusion = build_phase9d_conclusion(gate_report)

    rule_return_frame.to_csv(
        reports_path / "phase9d_preregistered_rule_returns.csv",
        index=False,
    )
    metrics.to_csv(
        reports_path / "phase9d_preregistered_rule_metrics.csv",
        index=False,
    )
    stress_metrics.to_csv(
        reports_path / "phase9d_preregistered_rule_stress_metrics.csv",
        index=False,
    )
    behavioural_metrics.to_csv(
        reports_path / "phase9d_preregistered_rule_behavioural_metrics.csv",
        index=False,
    )
    comparison_summary.to_csv(
        reports_path / "phase9d_preregistered_rule_comparison_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase9d_preregistered_rule_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase9d_preregistered_rule_conclusion.csv",
        index=False,
    )

    write_phase9d_markdown(
        metrics=metrics,
        stress_metrics=stress_metrics,
        behavioural_metrics=behavioural_metrics,
        comparison_summary=comparison_summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase9d_preregistered_technical_rule_test.md",
    )

    print("Wrote Phase 9D pre-registered technical rule test reports.")

    return {
        "rule_return_frame": rule_return_frame,
        "metrics": metrics,
        "stress_metrics": stress_metrics,
        "behavioural_metrics": behavioural_metrics,
        "comparison_summary": comparison_summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }