from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from market_strats.analysis.dynamic_multi_asset_opportunity_engine import (
    DEFAULT_UNIVERSE,
    _bool_value,
    _daily_drawdowns,
    _plot_bar,
    _plot_lines,
    _read_csv,
    _returns_with_cash,
    _write_csv,
    build_feature_store,
    compute_opportunity_scores,
    load_asset_prices,
)
from market_strats.analysis.dynamic_opportunity_diagnostics import (
    _cap_weights,
    _common_comparison_extended,
    _market_risk_on,
    _metrics,
    _rebalance_execution_dates,
    V1StrategySpec,
)


PHASE22C_SECTION = "phase22c_dynamic_opportunity_return_enhancement"
PHASE22A_SECTION = "phase22a_dynamic_multi_asset_opportunity_engine"
PHASE22B_SECTION = "phase22b_dynamic_opportunity_diagnostics"

V2_STRATEGIES = [
    "dynamic_top3_opportunity_v2_conviction",
    "dynamic_top4_opportunity_v2_breadth",
    "dynamic_core_satellite_v2_return_tilt",
]
DEFENSIVE_ASSETS = ["GLD", "TLT", "AGG"]


@dataclass(frozen=True)
class V2StrategySpec:
    strategy_name: str
    mode: str
    top_n: int
    max_single_asset_weight: float
    max_btc_weight: float
    max_oil_weight: float
    max_commodity_weight: float
    score_power: float
    inverse_vol_blend: float
    turnover_buffer: float


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE22C_SECTION, {}) or {}


def _resolve_path(value: object, default: Path) -> Path:
    return Path(value) if value else default


def _strategy_specs(section: dict[str, Any]) -> list[V2StrategySpec]:
    max_btc = float(section.get("max_btc_weight", 0.05))
    max_oil = float(section.get("max_oil_weight", 0.10))
    max_commodity = float(section.get("max_commodity_weight", 0.20))
    return [
        V2StrategySpec(
            strategy_name="dynamic_top3_opportunity_v2_conviction",
            mode="conviction",
            top_n=3,
            max_single_asset_weight=float(section.get("max_single_asset_weight", 0.50)),
            max_btc_weight=max_btc,
            max_oil_weight=max_oil,
            max_commodity_weight=max_commodity,
            score_power=1.50,
            inverse_vol_blend=0.25,
            turnover_buffer=0.04,
        ),
        V2StrategySpec(
            strategy_name="dynamic_top4_opportunity_v2_breadth",
            mode="breadth",
            top_n=4,
            max_single_asset_weight=min(
                float(section.get("max_single_asset_weight", 0.50)),
                0.40,
            ),
            max_btc_weight=max_btc,
            max_oil_weight=max_oil,
            max_commodity_weight=max_commodity,
            score_power=1.25,
            inverse_vol_blend=0.35,
            turnover_buffer=0.06,
        ),
        V2StrategySpec(
            strategy_name="dynamic_core_satellite_v2_return_tilt",
            mode="core_satellite",
            top_n=3,
            max_single_asset_weight=float(section.get("max_single_asset_weight", 0.50)),
            max_btc_weight=max_btc,
            max_oil_weight=max_oil,
            max_commodity_weight=max_commodity,
            score_power=1.35,
            inverse_vol_blend=0.25,
            turnover_buffer=0.05,
        ),
    ]


def _zscore(values: pd.Series) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce")
    std = values.std(skipna=True)
    if not np.isfinite(std) or std == 0:
        return pd.Series(0.0, index=values.index, dtype=float)
    return (values - values.mean(skipna=True)) / std


def _v2_score_frame(scores_for_signal: pd.DataFrame) -> pd.DataFrame:
    frame = scores_for_signal.loc[scores_for_signal["symbol"] != "CASH"].copy()
    if frame.empty:
        return frame
    frame["base_opportunity_score"] = pd.to_numeric(
        frame["opportunity_score"], errors="coerce"
    )
    frame["fast_momentum_z"] = _zscore(frame.get("return_21d", pd.Series(index=frame.index)))
    frame["medium_momentum_z"] = _zscore(frame.get("return_63d", pd.Series(index=frame.index)))
    frame["volatility_z"] = _zscore(frame.get("volatility_63d", pd.Series(index=frame.index)))
    above_50 = pd.to_numeric(
        frame.get("price_above_50d_ma", pd.Series(index=frame.index)),
        errors="coerce",
    ).fillna(0.0)
    above_200 = pd.to_numeric(
        frame.get("price_above_200d_ma", pd.Series(index=frame.index)),
        errors="coerce",
    ).fillna(0.0)
    frame["trend_confirmation"] = 0.40 * above_50 + 0.60 * above_200
    frame["v2_conviction_score"] = (
        frame["base_opportunity_score"]
        + 0.20 * frame["fast_momentum_z"]
        + 0.10 * frame["medium_momentum_z"]
        + 0.15 * frame["trend_confirmation"]
        - 0.10 * frame["volatility_z"]
    )
    drawdown = pd.to_numeric(
        frame.get("drawdown_from_252d_high", pd.Series(index=frame.index)),
        errors="coerce",
    )
    volatility = pd.to_numeric(
        frame.get("volatility_63d", pd.Series(index=frame.index)),
        errors="coerce",
    )
    frame["eligible_v2"] = (
        frame["v2_conviction_score"].notna()
        & volatility.notna()
        & (volatility > 0)
        & (drawdown.fillna(-1.0) >= -0.35)
        & ((above_50 >= 0.5) | (above_200 >= 0.5))
    )
    frame["positive_trend_breadth_member"] = (
        frame["v2_conviction_score"].fillna(-np.inf) > 0
    ) & (above_200 >= 0.5)
    return frame


def _breadth(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    return float(frame["positive_trend_breadth_member"].mean())


def _risk_budget(
    *,
    mode: str,
    risk_on: bool,
    breadth: float,
    top_score: float,
) -> float:
    if mode == "conviction":
        if risk_on and breadth >= 0.50:
            return 1.00
        if risk_on:
            return 0.90
        return 0.65 if top_score > 0.50 else 0.45
    if mode == "breadth":
        if risk_on:
            return float(np.clip(0.60 + 0.70 * breadth, 0.70, 1.00))
        return float(np.clip(0.35 + 0.55 * breadth, 0.35, 0.70))
    if mode == "core_satellite":
        return 1.00 if risk_on else 0.55
    return 0.75


def _conviction_weights(frame: pd.DataFrame, spec: V2StrategySpec) -> pd.Series:
    selected = (
        frame.loc[frame["eligible_v2"] & (frame["v2_conviction_score"] > 0)]
        .sort_values("v2_conviction_score", ascending=False)
        .head(spec.top_n)
        .copy()
    )
    if selected.empty:
        return pd.Series(dtype=float)
    selected = selected.set_index("symbol")
    score = pd.to_numeric(selected["v2_conviction_score"], errors="coerce")
    score = (score - score.min() + 0.05).clip(lower=0.01) ** spec.score_power
    score = score / score.sum()
    inv_vol = 1.0 / pd.to_numeric(
        selected["volatility_63d"], errors="coerce"
    ).clip(lower=1e-6)
    inv_vol = inv_vol.replace([np.inf, -np.inf], np.nan).dropna()
    if inv_vol.empty:
        return score
    inv_vol = inv_vol / inv_vol.sum()
    weights = (1.0 - spec.inverse_vol_blend) * score + spec.inverse_vol_blend * inv_vol
    return weights / weights.sum()


def _defensive_weights(
    scores_for_signal: pd.DataFrame,
    total_weight: float,
) -> pd.Series:
    if total_weight <= 1e-12:
        return pd.Series(dtype=float)
    indexed = scores_for_signal.set_index("symbol")
    available = [asset for asset in DEFENSIVE_ASSETS if asset in indexed.index]
    defensive_risk_budget = total_weight * 0.60
    cash_weight = total_weight - defensive_risk_budget
    if not available:
        return pd.Series({"CASH": total_weight})
    vol = pd.to_numeric(indexed.loc[available, "volatility_63d"], errors="coerce")
    inv_vol = (1.0 / vol.clip(lower=1e-6)).replace([np.inf, -np.inf], np.nan).dropna()
    if inv_vol.empty:
        return pd.Series({"CASH": total_weight})
    inv_vol = inv_vol / inv_vol.sum() * defensive_risk_budget
    result = inv_vol.copy()
    result.loc["CASH"] = cash_weight
    return result


def _apply_turnover_buffer(
    *,
    desired: pd.Series,
    previous: pd.Series,
    buffer: float,
) -> pd.Series:
    if previous.empty or previous.get("CASH", 0.0) > 0.999:
        return desired
    index = sorted(set(desired.index) | set(previous.index))
    desired_aligned = desired.reindex(index).fillna(0.0)
    previous_aligned = previous.reindex(index).fillna(0.0)
    delta = desired_aligned - previous_aligned
    buffered = desired_aligned.copy()
    buffered.loc[delta.abs() < buffer] = previous_aligned.loc[delta.abs() < buffer]
    # A modest persistence blend reduces churn without freezing genuine rank changes.
    buffered = 0.80 * buffered + 0.20 * previous_aligned
    total = float(buffered.sum())
    if total <= 0:
        return pd.Series({"CASH": 1.0})
    return buffered / total


def _as_v1_spec(spec: V2StrategySpec) -> V1StrategySpec:
    return V1StrategySpec(
        strategy_name=spec.strategy_name,
        top_n=spec.top_n,
        max_single_asset_weight=spec.max_single_asset_weight,
        max_btc_weight=spec.max_btc_weight,
        max_oil_weight=spec.max_oil_weight,
        max_commodity_weight=spec.max_commodity_weight,
        mode=spec.mode,
    )


def _weights_for_signal_v2(
    *,
    scores_for_signal: pd.DataFrame,
    spec: V2StrategySpec,
    previous_weights: pd.Series,
) -> tuple[pd.Series, dict[str, Any]]:
    frame = _v2_score_frame(scores_for_signal)
    if frame.empty:
        return pd.Series({"CASH": 1.0}), {
            "breadth": 0.0,
            "risk_budget": 0.0,
            "top_score": np.nan,
            "allocation_reason": "no_v2_score_rows_cash_only",
        }
    risk_on = _market_risk_on(scores_for_signal)
    breadth = _breadth(frame)
    top_score_value = pd.to_numeric(frame["v2_conviction_score"], errors="coerce").max()
    top_score = float(top_score_value) if pd.notna(top_score_value) else np.nan
    opportunity = _conviction_weights(frame, spec)
    if opportunity.empty:
        return pd.Series({"CASH": 1.0}), {
            "breadth": breadth,
            "risk_budget": 0.0,
            "top_score": top_score,
            "allocation_reason": "no_positive_trend_confirmed_assets_cash_only",
        }

    risk_budget = _risk_budget(
        mode=spec.mode,
        risk_on=risk_on,
        breadth=breadth,
        top_score=top_score,
    )
    if spec.mode == "core_satellite":
        if risk_on:
            core = pd.Series({"SPY": 0.36, "QQQ": 0.24})
            satellite_weight = 0.40
            defensive_weight = 0.0
        else:
            core = pd.Series({"SPY": 0.18, "QQQ": 0.12})
            satellite_weight = 0.25
            defensive_weight = 0.45
        raw = core.add(opportunity * satellite_weight, fill_value=0.0)
        raw = raw.add(
            _defensive_weights(scores_for_signal, defensive_weight),
            fill_value=0.0,
        )
        allocation_reason = (
            "risk_on_core_60_satellite_40"
            if risk_on
            else "risk_off_core_30_satellite_25_defensive_45"
        )
    else:
        raw = opportunity * risk_budget
        raw = raw.add(
            _defensive_weights(scores_for_signal, 1.0 - risk_budget),
            fill_value=0.0,
        )
        allocation_reason = (
            f"{spec.mode}_risk_budget_{risk_budget:.2f}_breadth_{breadth:.2f}"
        )

    raw = raw[raw > 1e-12]
    if raw.sum() < 1.0:
        raw.loc["CASH"] = raw.get("CASH", 0.0) + (1.0 - raw.sum())
    desired = _cap_weights(raw, _as_v1_spec(spec))
    buffered = _apply_turnover_buffer(
        desired=desired,
        previous=previous_weights,
        buffer=spec.turnover_buffer,
    )
    final_weights = _cap_weights(buffered, _as_v1_spec(spec))
    metadata = {
        "breadth": breadth,
        "risk_budget": risk_budget,
        "top_score": top_score,
        "allocation_reason": allocation_reason,
        "risk_on": risk_on,
    }
    return final_weights, metadata


def simulate_v2_strategy(
    *,
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    spec: V2StrategySpec,
    starting_cash: float,
    transaction_cost_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if prices.empty or scores.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    returns = _returns_with_cash(prices)
    scores = scores.copy()
    scores["date"] = pd.to_datetime(scores["date"])
    score_counts = scores.groupby("date")["symbol"].nunique()
    eligible_score_dates = score_counts.loc[score_counts >= 3].index
    common_dates = pd.DatetimeIndex(sorted(set(returns.index) & set(eligible_score_dates)))
    if len(common_dates) < 260:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    common_dates = common_dates[common_dates >= common_dates.min() + pd.Timedelta(days=252)]
    pairs = _rebalance_execution_dates(common_dates)
    score_by_date = {pd.Timestamp(date): group.copy() for date, group in scores.groupby("date")}

    current_weights = pd.Series({"CASH": 1.0})
    current_value = float(starting_cash)
    equity_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for pair_index, (signal_date, execution_date) in enumerate(pairs):
        signal_scores = score_by_date.get(pd.Timestamp(signal_date), pd.DataFrame())
        if signal_scores.empty:
            continue
        target_weights, metadata = _weights_for_signal_v2(
            scores_for_signal=signal_scores,
            spec=spec,
            previous_weights=current_weights,
        )
        turnover_index = sorted(set(target_weights.index) | set(current_weights.index))
        asset_turnover = (
            target_weights.reindex(turnover_index).fillna(0.0)
            - current_weights.reindex(turnover_index).fillna(0.0)
        ).abs()
        turnover = float(asset_turnover.sum())
        cost = current_value * turnover * float(transaction_cost_bps) / 10_000.0
        current_value -= cost
        event_rows.append(
            {
                "strategy_name": spec.strategy_name,
                "signal_date": signal_date.date().isoformat(),
                "execution_date": execution_date.date().isoformat(),
                "selected_assets": ",".join(
                    asset
                    for asset, weight in target_weights.items()
                    if asset != "CASH" and weight > 1e-6
                ),
                "target_weights": ";".join(
                    f"{asset}:{weight:.6f}" for asset, weight in target_weights.items()
                ),
                "asset_turnover": ";".join(
                    f"{asset}:{value:.6f}"
                    for asset, value in asset_turnover.items()
                    if value > 1e-9
                ),
                "turnover": turnover,
                "transaction_cost_bps": transaction_cost_bps,
                "transaction_cost_usd": cost,
                "market_risk_on_flag": metadata.get("risk_on", False),
                "positive_trend_breadth": metadata.get("breadth", 0.0),
                "risk_budget": metadata.get("risk_budget", 0.0),
                "top_v2_conviction_score": metadata.get("top_score", np.nan),
                "allocation_reason": metadata.get("allocation_reason", ""),
                "v2_mode": spec.mode,
            }
        )
        current_weights = target_weights
        next_execution = (
            pairs[pair_index + 1][1]
            if pair_index + 1 < len(pairs)
            else returns.index[-1] + pd.Timedelta(days=1)
        )
        period_dates = returns.index[
            (returns.index >= execution_date) & (returns.index < next_execution)
        ]
        for date in period_dates:
            daily_return = float(
                (
                    current_weights.reindex(returns.columns).fillna(0.0)
                    * returns.loc[date].fillna(0.0)
                ).sum()
            )
            current_value *= 1.0 + daily_return
            equity_rows.append(
                {
                    "date": date.date().isoformat(),
                    "strategy_name": spec.strategy_name,
                    "portfolio_value": current_value,
                    "transaction_cost_bps": transaction_cost_bps,
                }
            )
            for asset, weight in current_weights.items():
                weight_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "strategy_name": spec.strategy_name,
                        "asset": asset,
                        "weight": float(weight),
                        "transaction_cost_bps": transaction_cost_bps,
                    }
                )
    return pd.DataFrame(equity_rows), pd.DataFrame(weight_rows), pd.DataFrame(event_rows)


def _cost_sensitivity(
    *,
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    specs: list[V2StrategySpec],
    starting_cash: float,
    transaction_cost_cases: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    equity_frames: list[pd.DataFrame] = []
    weight_frames: list[pd.DataFrame] = []
    event_frames: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for spec in specs:
        for cost_case in transaction_cost_cases:
            equity, weights, events = simulate_v2_strategy(
                prices=prices,
                scores=scores,
                spec=spec,
                starting_cash=starting_cash,
                transaction_cost_bps=cost_case,
            )
            if equity.empty:
                continue
            metric = _metrics(equity, events, weights)
            metric.update(
                {
                    "strategy_name": spec.strategy_name,
                    "transaction_cost_bps": cost_case,
                    "paper_only": True,
                    "promotion_allowed": False,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                }
            )
            cost_rows.append(
                {
                    "strategy_name": spec.strategy_name,
                    "transaction_cost_bps": cost_case,
                    "strategy_cost_case": f"{spec.strategy_name}_{cost_case}bps",
                    "final_value": metric["final_value"],
                    "CAGR": metric["CAGR"],
                    "max_drawdown": metric["max_drawdown"],
                    "Calmar": metric["Calmar"],
                }
            )
            if cost_case == 0:
                metric_rows.append(metric)
                equity_frames.append(equity)
                weight_frames.append(weights)
                event_frames.append(events)
    return (
        pd.concat(equity_frames, ignore_index=True) if equity_frames else pd.DataFrame(),
        pd.concat(weight_frames, ignore_index=True) if weight_frames else pd.DataFrame(),
        pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame(),
        pd.DataFrame(metric_rows),
        pd.DataFrame(cost_rows),
    )


def _turnover_diagnostics(events: pd.DataFrame, costs: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for strategy, group in events.groupby("strategy_name"):
        execution_dates = pd.to_datetime(group["execution_date"], errors="coerce").dropna()
        years = max(
            (execution_dates.max() - execution_dates.min()).days / 365.25
            if len(execution_dates) > 1
            else 1.0,
            1.0,
        )
        average_turnover = float(pd.to_numeric(group["turnover"], errors="coerce").mean())
        annualized_turnover = float(pd.to_numeric(group["turnover"], errors="coerce").sum() / years)
        cost_drag = np.nan
        cost_rows = costs.loc[costs["strategy_name"] == strategy]
        if not cost_rows.empty:
            lookup = cost_rows.set_index("transaction_cost_bps")["final_value"].to_dict()
            if lookup.get(0) and 25 in lookup:
                cost_drag = (float(lookup[0]) - float(lookup[25])) / float(lookup[0]) * 100
        rows.append(
            {
                "strategy": strategy,
                "average_turnover": average_turnover,
                "annualized_turnover": annualized_turnover,
                "cost_drag_25bps_pct": cost_drag,
                "rebalance_count": len(group),
            }
        )
    return pd.DataFrame(rows)


def _latest_allocation_audit(
    *,
    scores: pd.DataFrame,
    weights: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame()
    latest_date = pd.to_datetime(weights["date"]).max()
    latest_weights = weights.loc[pd.to_datetime(weights["date"]) == latest_date].copy()
    latest_score_date = pd.to_datetime(scores["date"]).max() if not scores.empty else pd.NaT
    latest_scores = (
        _v2_score_frame(scores.loc[pd.to_datetime(scores["date"]) == latest_score_date])
        if pd.notna(latest_score_date)
        else pd.DataFrame()
    )
    score_lookup = (
        latest_scores.set_index("symbol")[
            ["base_opportunity_score", "v2_conviction_score", "eligible_v2"]
        ].to_dict("index")
        if not latest_scores.empty
        else {}
    )
    event_lookup: dict[str, dict[str, Any]] = {}
    if not events.empty:
        latest_event_date = pd.to_datetime(events["execution_date"]).max()
        event_lookup = {
            str(row.strategy_name): row._asdict()
            for row in events.loc[
                pd.to_datetime(events["execution_date"]) == latest_event_date
            ].itertuples(index=False)
        }
    rows = []
    for row in latest_weights.itertuples(index=False):
        score_data = score_lookup.get(str(row.asset), {})
        event_data = event_lookup.get(str(row.strategy_name), {})
        rows.append(
            {
                "date": str(row.date),
                "strategy_name": row.strategy_name,
                "asset": row.asset,
                "weight": float(row.weight),
                "base_opportunity_score": score_data.get("base_opportunity_score", np.nan),
                "v2_conviction_score": score_data.get("v2_conviction_score", np.nan),
                "eligible_v2": score_data.get("eligible_v2", row.asset == "CASH"),
                "positive_trend_breadth": event_data.get("positive_trend_breadth", np.nan),
                "risk_budget": event_data.get("risk_budget", np.nan),
                "allocation_reason": event_data.get("allocation_reason", ""),
            }
        )
    return pd.DataFrame(rows)


def _cost_lookup(costs: pd.DataFrame, cost_case: int) -> dict[str, dict[str, float]]:
    if costs.empty:
        return {}
    rows = costs.loc[pd.to_numeric(costs["transaction_cost_bps"], errors="coerce") == cost_case]
    return {
        str(row.strategy_name): {
            "CAGR": float(row.CAGR),
            "final_value": float(row.final_value),
        }
        for row in rows.itertuples(index=False)
    }


def _return_enhancement_scorecard(
    *,
    comparison: pd.DataFrame,
    costs: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()
    comparison_lookup = comparison.set_index("strategy_name").to_dict("index")
    spy = comparison_lookup.get("SPY Buy & Hold Benchmark", {})
    v1_rows = comparison.loc[
        comparison["strategy_name"].astype(str).str.contains("_v1", regex=False)
    ]
    best_v1_cagr = float(v1_rows["CAGR"].max()) if not v1_rows.empty else np.nan
    best_v1_calmar = float(v1_rows["Calmar"].max()) if not v1_rows.empty else np.nan
    min_cagr_improvement = float(section.get("min_cagr_improvement_vs_v1_pp", 0.25))
    max_drawdown_worsening = float(section.get("max_drawdown_worsening_vs_spy_pp", 5.0))
    max_cost_drag = float(section.get("max_25bps_cagr_drag_pp", 1.0))
    min_rolling_win = float(section.get("min_rolling_3y_win_rate_vs_spy", 45.0))
    cost_0 = _cost_lookup(costs, 0)
    cost_25 = _cost_lookup(costs, 25)
    rows = []
    for strategy in V2_STRATEGIES:
        metrics = comparison_lookup.get(strategy)
        if metrics is None:
            continue
        cagr = float(metrics.get("CAGR", np.nan))
        max_dd = float(metrics.get("max_drawdown", np.nan))
        calmar = float(metrics.get("Calmar", np.nan))
        rolling_win = float(metrics.get("rolling_3y_win_rate_vs_SPY", np.nan))
        cagr_0 = cost_0.get(strategy, {}).get("CAGR", np.nan)
        cagr_25 = cost_25.get(strategy, {}).get("CAGR", np.nan)
        cost_drag = cagr_0 - cagr_25 if pd.notna(cagr_0) and pd.notna(cagr_25) else np.nan
        return_pass = bool(pd.notna(best_v1_cagr) and cagr >= best_v1_cagr + min_cagr_improvement)
        spy_dd = float(spy.get("max_drawdown", np.nan))
        drawdown_pass = bool(
            pd.notna(spy_dd)
            and pd.notna(max_dd)
            and max_dd >= spy_dd - max_drawdown_worsening
        )
        cost_pass = bool(pd.notna(cost_drag) and cost_drag <= max_cost_drag)
        rolling_pass = bool(pd.isna(rolling_win) or rolling_win >= min_rolling_win)
        rows.append(
            {
                "strategy_name": strategy,
                "CAGR": cagr,
                "CAGR_vs_best_v1_pp": cagr - best_v1_cagr if pd.notna(best_v1_cagr) else np.nan,
                "CAGR_vs_SPY_pp": cagr - float(spy.get("CAGR", np.nan)),
                "max_drawdown": max_dd,
                "max_drawdown_vs_SPY_pp": max_dd - spy_dd if pd.notna(spy_dd) else np.nan,
                "Calmar": calmar,
                "Calmar_vs_best_v1": calmar - best_v1_calmar if pd.notna(best_v1_calmar) else np.nan,
                "rolling_3y_win_rate_vs_SPY": rolling_win,
                "CAGR_0bps": cagr_0,
                "CAGR_25bps": cagr_25,
                "CAGR_drag_25bps_pp": cost_drag,
                "return_enhancement_pass": return_pass,
                "drawdown_guard_pass": drawdown_pass,
                "cost_survival_pass": cost_pass,
                "rolling_consistency_pass": rolling_pass,
                "all_research_gates_passed": (
                    return_pass and drawdown_pass and cost_pass and rolling_pass
                ),
                "promotion_allowed": False,
            }
        )
    scorecard = pd.DataFrame(rows)
    if scorecard.empty:
        return scorecard
    # Transparent rank, not an adoption score. Higher return/Calmar and lower cost drag rank better.
    scorecard["research_rank_score"] = (
        scorecard["CAGR"].rank(pct=True)
        + scorecard["Calmar"].rank(pct=True)
        + scorecard["rolling_3y_win_rate_vs_SPY"].fillna(50.0).rank(pct=True)
        - scorecard["CAGR_drag_25bps_pp"].fillna(np.inf).rank(pct=True)
    )
    scorecard["research_rank"] = scorecard["research_rank_score"].rank(
        method="dense", ascending=False
    )
    return scorecard.sort_values(["research_rank", "strategy_name"]).reset_index(drop=True)


def _plot_scatter(comparison: pd.DataFrame, path: Path) -> None:
    if comparison.empty:
        fig, ax = plt.subplots(figsize=(9, 4.8))
        ax.axis("off")
        ax.set_title("Phase22C Risk/Return")
        ax.text(0.5, 0.5, "No comparison data", ha="center", va="center")
    else:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.scatter(comparison["max_drawdown"], comparison["CAGR"])
        for row in comparison.itertuples(index=False):
            ax.annotate(
                str(row.strategy_name)[:28],
                (row.max_drawdown, row.CAGR),
                fontsize=7,
            )
        ax.set_title("Phase22C Risk/Return")
        ax.set_xlabel("Max drawdown (%)")
        ax.set_ylabel("CAGR (%)")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _write_charts(
    *,
    visuals_dir: Path,
    common_equity: pd.DataFrame,
    v2_equity: pd.DataFrame,
    comparison: pd.DataFrame,
    turnover: pd.DataFrame,
    scorecard: pd.DataFrame,
    latest_audit: pd.DataFrame,
) -> list[Path]:
    visuals_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        visuals_dir / "phase22c_v2_equity_curves.png",
        visuals_dir / "phase22c_v2_drawdowns.png",
        visuals_dir / "phase22c_v2_final_value_bar.png",
        visuals_dir / "phase22c_v2_risk_return_scatter.png",
        visuals_dir / "phase22c_v2_turnover_bar.png",
        visuals_dir / "phase22c_return_enhancement_bar.png",
        visuals_dir / "phase22c_latest_weights_bar.png",
    ]
    _plot_lines(
        common_equity,
        "portfolio_value",
        paths[0],
        "Phase22C Common-Period Equity Curves",
        "Portfolio value",
    )
    _plot_lines(
        _daily_drawdowns(v2_equity) if not v2_equity.empty else pd.DataFrame(),
        "drawdown_pct",
        paths[1],
        "Phase22C v2 Drawdowns",
        "Drawdown (%)",
    )
    _plot_bar(
        comparison,
        "strategy_name",
        "final_value",
        paths[2],
        "Phase22C Common-Period Final Value",
    )
    _plot_scatter(comparison, paths[3])
    _plot_bar(
        turnover,
        "strategy",
        "annualized_turnover",
        paths[4],
        "Phase22C Annualized Turnover",
    )
    _plot_bar(
        scorecard,
        "strategy_name",
        "CAGR_vs_best_v1_pp",
        paths[5],
        "CAGR Improvement vs Best v1 (pp)",
    )
    latest = latest_audit.loc[latest_audit["weight"] > 1e-9].copy()
    _plot_bar(
        latest,
        "asset",
        "weight",
        paths[6],
        "Phase22C Latest v2 Weights",
    )
    return paths


def _write_research_summary(
    *,
    path: Path,
    decision: str,
    metrics: pd.DataFrame,
    comparison: pd.DataFrame,
    scorecard: pd.DataFrame,
    turnover: pd.DataFrame,
    latest_audit: pd.DataFrame,
) -> None:
    lines = [
        "# Phase 22C Dynamic Opportunity v2 Return Enhancement",
        "",
        "NO LIVE TRADING",
        "NO REAL MONEY",
        "NO BROKER/API",
        "NO STRATEGY PROMOTION",
        "RESEARCH ONLY",
        "NOT ADDED TO DAILY PAPER RUNNER",
        "",
        f"Decision: `{decision}`",
        "",
        "v2 architecture: conviction-weighted sizing, fast/medium momentum confirmation, breadth-sensitive risk budgets, explicit caps, and turnover buffering.",
        "",
        "v2 metrics:",
        metrics.to_markdown(index=False) if not metrics.empty else "No v2 metrics available.",
        "",
        "Common-period comparison:",
        comparison.to_markdown(index=False) if not comparison.empty else "No comparison available.",
        "",
        "Return-enhancement scorecard:",
        scorecard.to_markdown(index=False) if not scorecard.empty else "No scorecard available.",
        "",
        "Turnover diagnostics:",
        turnover.to_markdown(index=False) if not turnover.empty else "No turnover diagnostics available.",
        "",
        "Latest score-to-weight audit:",
        latest_audit.to_markdown(index=False) if not latest_audit.empty else "No latest allocation audit available.",
        "",
        "Interpretation: Phase22C is a constrained research test. Passing a research gate does not authorize promotion, paper tracking, live trading, real money, or broker connectivity.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_missing_sources(
    *,
    output_dir: Path,
    dashboard_dir: Path,
    missing: list[str],
) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    decision = "phase22c_failed_missing_phase22a_or_phase22b_inputs"
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 22C",
                "phase22c_decision": decision,
                "all_gates_passed": False,
                "missing_sources": ";".join(missing),
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    gates = pd.DataFrame(
        [
            {
                "gate_id": "phase22a_and_phase22b_inputs_available",
                "passed": False,
                "notes": ";".join(missing),
            },
            {
                "gate_id": "safety_flags_false",
                "passed": True,
                "notes": "research only",
            },
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 22C",
                "phase22c_decision": decision,
                "all_gates_passed": False,
                "notes": "Phase22C failed closed because required Phase22A/22B inputs were missing.",
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    dashboard = pd.DataFrame(
        [
            {
                "phase22c_decision": decision,
                "all_gates_passed": False,
                "v2_strategy_count": 0,
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Missing inputs: " + ";".join(missing),
            }
        ]
    )
    _write_csv(summary, output_dir / "phase22c_summary.csv")
    _write_csv(gates, output_dir / "phase22c_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase22c_conclusion.csv")
    _write_csv(
        dashboard,
        dashboard_dir / "phase22c_dynamic_opportunity_return_enhancement_status.csv",
    )
    (output_dir / "phase22c_research_summary.md").write_text(
        "# Phase 22C Dynamic Opportunity v2 Return Enhancement\n\n"
        "NO LIVE TRADING\nNO REAL MONEY\nNO BROKER/API\nNO STRATEGY PROMOTION\n"
        "RESEARCH ONLY\nNOT ADDED TO DAILY PAPER RUNNER\n\n"
        f"Decision: `{decision}`\n\nMissing sources: {', '.join(missing)}\n",
        encoding="utf-8",
    )
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "dashboard": dashboard,
    }


def save_phase22c_dynamic_opportunity_return_enhancement(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config)
    if not _bool_value(section.get("enabled", False)):
        return {}

    reports_path = Path(reports_dir)
    root = reports_path.parent.resolve()
    phase22a_section = config.get(PHASE22A_SECTION, {}) or {}
    phase22b_section = config.get(PHASE22B_SECTION, {}) or {}
    phase22a_dir = _resolve_path(
        section.get("phase22a_input_dir") or phase22a_section.get("output_dir"),
        reports_path / "strategy_factory" / "dynamic_opportunity_engine",
    )
    phase22b_dir = _resolve_path(
        section.get("phase22b_input_dir") or phase22b_section.get("output_dir"),
        reports_path / "strategy_factory" / "dynamic_opportunity_engine_diagnostics",
    )
    output_dir = _resolve_path(
        section.get("output_dir"),
        reports_path / "strategy_factory" / "dynamic_opportunity_return_enhancement",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        reports_path / "paper_trading" / "dashboard",
    )
    visuals_dir = output_dir / "visuals"
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    visuals_dir.mkdir(parents=True, exist_ok=True)

    required_paths = [
        phase22a_dir / "phase22a_dynamic_strategy_daily_equity.csv",
        phase22b_dir / "phase22b_v1_daily_equity.csv",
        phase22b_dir / "phase22b_v1_strategy_metrics.csv",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        return _write_missing_sources(
            output_dir=output_dir,
            dashboard_dir=dashboard_dir,
            missing=missing,
        )

    starting_cash = float(section.get("starting_cash", 10_000))
    transaction_cost_cases = [
        int(value)
        for value in section.get("transaction_cost_bps_cases", [0, 10, 25])
    ]
    for required_case in (0, 25):
        if required_case not in transaction_cost_cases:
            transaction_cost_cases.append(required_case)
    transaction_cost_cases = sorted(set(transaction_cost_cases))

    prices, availability = load_asset_prices(root, DEFAULT_UNIVERSE)
    feature_store = build_feature_store(prices)
    scores = compute_opportunity_scores(feature_store)
    if scores.empty:
        scores = _read_csv(phase22a_dir / "phase22a_opportunity_scores.csv")
    if prices.empty or scores.empty:
        missing_data = []
        if prices.empty:
            missing_data.append("local_asset_prices")
        if scores.empty:
            missing_data.append("phase22a_opportunity_scores")
        return _write_missing_sources(
            output_dir=output_dir,
            dashboard_dir=dashboard_dir,
            missing=missing_data,
        )

    specs = _strategy_specs(section)
    v2_equity, v2_weights, v2_events, v2_metrics, v2_costs = _cost_sensitivity(
        prices=prices,
        scores=scores,
        specs=specs,
        starting_cash=starting_cash,
        transaction_cost_cases=transaction_cost_cases,
    )
    v2_drawdowns = (
        _daily_drawdowns(v2_equity) if not v2_equity.empty else pd.DataFrame()
    )
    turnover = _turnover_diagnostics(v2_events, v2_costs)
    latest_audit = _latest_allocation_audit(
        scores=scores,
        weights=v2_weights,
        events=v2_events,
    )

    v0_equity = _read_csv(
        phase22a_dir / "phase22a_dynamic_strategy_daily_equity.csv"
    )
    v1_equity = _read_csv(phase22b_dir / "phase22b_v1_daily_equity.csv")
    benchmark_path = (
        root
        / "reports"
        / "paper_trading"
        / "regime_informed_tracking"
        / "performance"
        / "regime_informed_historical_daily_equity.csv"
    )
    comparison, common_equity = _common_comparison_extended(
        benchmark_equity_path=benchmark_path,
        equity_frames=[v0_equity, v1_equity, v2_equity],
        starting_cash=starting_cash,
        turnover_diagnostics=turnover,
        tc=v2_costs,
    )
    scorecard = _return_enhancement_scorecard(
        comparison=comparison,
        costs=v2_costs,
        section=section,
    )

    _write_csv(availability, output_dir / "phase22c_asset_universe_availability.csv")
    _write_csv(v2_metrics, output_dir / "phase22c_v2_strategy_metrics.csv")
    _write_csv(v2_equity, output_dir / "phase22c_v2_daily_equity.csv")
    _write_csv(v2_drawdowns, output_dir / "phase22c_v2_daily_drawdowns.csv")
    _write_csv(v2_weights, output_dir / "phase22c_v2_daily_weights.csv")
    _write_csv(v2_events, output_dir / "phase22c_v2_rebalance_event_log.csv")
    _write_csv(v2_costs, output_dir / "phase22c_v2_transaction_cost_sensitivity.csv")
    _write_csv(turnover, output_dir / "phase22c_v2_turnover_diagnostics.csv")
    _write_csv(latest_audit, output_dir / "phase22c_latest_allocation_audit.csv")
    _write_csv(comparison, output_dir / "phase22c_benchmark_comparison.csv")
    _write_csv(scorecard, output_dir / "phase22c_return_enhancement_scorecard.csv")
    _write_csv(common_equity, output_dir / "phase22c_common_period_daily_equity.csv")

    chart_paths = _write_charts(
        visuals_dir=visuals_dir,
        common_equity=common_equity,
        v2_equity=v2_equity,
        comparison=comparison,
        turnover=turnover,
        scorecard=scorecard,
        latest_audit=latest_audit,
    )

    any_return_gate = bool(
        not scorecard.empty
        and scorecard["return_enhancement_pass"].map(_bool_value).any()
    )
    any_all_research_gates = bool(
        not scorecard.empty
        and scorecard["all_research_gates_passed"].map(_bool_value).any()
    )
    if any_all_research_gates:
        decision = "phase22c_v2_candidate_passed_research_gates_not_promoted"
    elif any_return_gate:
        decision = "phase22c_v2_return_improved_but_risk_or_cost_gate_failed"
    else:
        decision = "phase22c_v2_no_return_enhancement_research_only"
    if v2_metrics.empty or comparison.empty:
        decision = "phase22c_completed_insufficient_comparison_data_research_only"

    summary_md_path = output_dir / "phase22c_research_summary.md"
    _write_research_summary(
        path=summary_md_path,
        decision=decision,
        metrics=v2_metrics,
        comparison=comparison,
        scorecard=scorecard,
        turnover=turnover,
        latest_audit=latest_audit,
    )

    gates = pd.DataFrame(
        [
            {"gate_id": "phase22a_inputs_available", "passed": True},
            {"gate_id": "phase22b_inputs_available", "passed": True},
            {"gate_id": "at_least_3_v2_strategies_evaluated", "passed": len(v2_metrics) >= 3},
            {"gate_id": "transaction_cost_sensitivity_written", "passed": not v2_costs.empty},
            {"gate_id": "return_enhancement_scorecard_written", "passed": not scorecard.empty},
            {"gate_id": "latest_allocation_audit_written", "passed": not latest_audit.empty},
            {"gate_id": "benchmark_comparison_written", "passed": not comparison.empty},
            {"gate_id": "charts_generated", "passed": all(path.exists() for path in chart_paths)},
            {"gate_id": "research_summary_written", "passed": summary_md_path.exists()},
            {"gate_id": "not_added_to_daily_paper_runner", "passed": True},
            {"gate_id": "promotion_disabled", "passed": True},
            {"gate_id": "live_trading_disabled", "passed": True},
            {"gate_id": "real_money_disabled", "passed": True},
            {"gate_id": "broker_api_integration_disabled", "passed": True},
        ]
    )
    all_gates_passed = bool(gates["passed"].map(_bool_value).all())
    best_strategy = (
        str(scorecard.iloc[0]["strategy_name"]) if not scorecard.empty else ""
    )
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 22C",
                "phase22c_decision": decision,
                "all_gates_passed": all_gates_passed,
                "v2_strategy_count": len(v2_metrics),
                "best_research_ranked_v2_strategy": best_strategy,
                "any_return_enhancement_pass": any_return_gate,
                "any_all_research_gates_passed": any_all_research_gates,
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 22C",
                "phase22c_decision": decision,
                "all_gates_passed": all_gates_passed,
                "diagnostic": "Constrained v2 return-enhancement test with conviction sizing, breadth risk budgets, caps, and cost-survival gates",
                "best_research_ranked_v2_strategy": best_strategy,
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Research only. Not added to daily paper runner or Phase21 paper shortlist.",
            }
        ]
    )
    dashboard = pd.DataFrame(
        [
            {
                "phase22c_decision": decision,
                "all_gates_passed": all_gates_passed,
                "v2_strategy_count": len(v2_metrics),
                "best_research_ranked_v2_strategy": best_strategy,
                "any_return_enhancement_pass": any_return_gate,
                "any_all_research_gates_passed": any_all_research_gates,
                "dashboard_status": "phase22c_dynamic_opportunity_return_enhancement_status_written",
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Research-only v2 candidates remain outside the daily paper runner.",
            }
        ]
    )
    _write_csv(summary, output_dir / "phase22c_summary.csv")
    _write_csv(gates, output_dir / "phase22c_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase22c_conclusion.csv")
    _write_csv(
        dashboard,
        dashboard_dir / "phase22c_dynamic_opportunity_return_enhancement_status.csv",
    )
    print("Wrote Phase 22C dynamic opportunity v2 return-enhancement reports.")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "v2_metrics": v2_metrics,
        "v2_equity": v2_equity,
        "v2_weights": v2_weights,
        "v2_events": v2_events,
        "transaction_cost_sensitivity": v2_costs,
        "turnover_diagnostics": turnover,
        "latest_allocation_audit": latest_audit,
        "comparison": comparison,
        "return_enhancement_scorecard": scorecard,
        "dashboard": dashboard,
    }
