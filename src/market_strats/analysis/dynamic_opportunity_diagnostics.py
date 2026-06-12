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
    COMMODITY_ASSETS,
    DEFAULT_UNIVERSE,
    _bool_value,
    _cap_and_redistribute,
    _daily_drawdowns,
    _drawdown,
    _plot_bar,
    _plot_lines,
    _read_csv,
    _returns_with_cash,
    _write_csv,
    build_feature_store,
    compute_opportunity_scores,
    load_asset_prices,
)


PHASE22B_SECTION = "phase22b_dynamic_opportunity_diagnostics"
PHASE22A_SECTION = "phase22a_dynamic_multi_asset_opportunity_engine"
V0_STRATEGIES = [
    "dynamic_top3_technical_opportunity_v0",
    "dynamic_top5_technical_opportunity_v0",
    "dynamic_defensive_opportunity_v0",
]
V1_STRATEGIES = [
    "dynamic_top5_opportunity_v1_sticky",
    "dynamic_top5_opportunity_v1_balanced",
    "dynamic_top3_opportunity_v1_growth_guarded",
    "dynamic_adaptive_core_satellite_v1",
]
CURRENT_COMPARISON_STRATEGIES = [
    "SPY Buy & Hold Benchmark",
    "phase6b_loose_relief_execution_realistic_overlay",
    "canonical_spy_qqq_gld_tlt_50_30_10_10",
    "canonical_inverse_vol_63d_btc_usd_qqq_spy",
    "canonical_spy_qqq_60_40",
]
DEFENSIVE_ASSETS = ["CASH", "GLD", "TLT", "AGG"]


@dataclass(frozen=True)
class V1StrategySpec:
    strategy_name: str
    top_n: int
    max_single_asset_weight: float
    max_btc_weight: float
    max_oil_weight: float
    max_commodity_weight: float
    mode: str
    min_score_improvement: float = 0.35
    min_weight_change: float = 0.10


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE22B_SECTION, {}) or {}


def _resolve_path(value: object, default: Path) -> Path:
    return Path(value) if value else default


def _parse_target_weights(text: object) -> pd.Series:
    weights: dict[str, float] = {}
    for part in str(text or "").split(";"):
        if ":" not in part:
            continue
        asset, value = part.split(":", 1)
        try:
            weights[asset] = float(value)
        except ValueError:
            continue
    return pd.Series(weights, dtype=float)


def _strategy_specs(section: dict[str, Any]) -> list[V1StrategySpec]:
    max_btc = float(section.get("max_btc_weight", 0.05))
    max_oil = float(section.get("max_oil_weight", 0.10))
    max_commodity = float(section.get("max_commodity_weight", 0.20))
    return [
        V1StrategySpec(
            strategy_name="dynamic_top5_opportunity_v1_sticky",
            top_n=5,
            max_single_asset_weight=0.35,
            max_btc_weight=max_btc,
            max_oil_weight=max_oil,
            max_commodity_weight=max_commodity,
            mode="sticky",
        ),
        V1StrategySpec(
            strategy_name="dynamic_top5_opportunity_v1_balanced",
            top_n=5,
            max_single_asset_weight=0.35,
            max_btc_weight=max_btc,
            max_oil_weight=max_oil,
            max_commodity_weight=max_commodity,
            mode="balanced",
        ),
        V1StrategySpec(
            strategy_name="dynamic_top3_opportunity_v1_growth_guarded",
            top_n=3,
            max_single_asset_weight=0.50,
            max_btc_weight=max_btc,
            max_oil_weight=max_oil,
            max_commodity_weight=max_commodity,
            mode="growth_guarded",
        ),
        V1StrategySpec(
            strategy_name="dynamic_adaptive_core_satellite_v1",
            top_n=3,
            max_single_asset_weight=0.50,
            max_btc_weight=max_btc,
            max_oil_weight=max_oil,
            max_commodity_weight=max_commodity,
            mode="core_satellite",
        ),
    ]


def _rebalance_execution_dates(index: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if len(index) < 2:
        return []
    series = pd.Series(index, index=index)
    signal_dates = pd.DatetimeIndex(series.groupby(index.to_period("M")).last().values)
    pairs: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for signal_date in signal_dates:
        future = index[index > signal_date]
        if len(future) == 0:
            continue
        pairs.append((pd.Timestamp(signal_date), pd.Timestamp(future[0])))
    return pairs


def _asset_filter_frame(scores_for_signal: pd.DataFrame) -> pd.DataFrame:
    frame = scores_for_signal.loc[scores_for_signal["symbol"] != "CASH"].copy()
    frame["raw_score"] = pd.to_numeric(frame["opportunity_score"], errors="coerce")
    frame["rank"] = frame["raw_score"].rank(method="first", ascending=False)
    frame["eligible_before_filters"] = frame["raw_score"].notna()
    frame["blocked_by_missing_data"] = (
        frame["raw_score"].isna()
        | pd.to_numeric(frame["volatility_63d"], errors="coerce").isna()
    )
    frame["blocked_by_negative_score"] = frame["raw_score"] <= 0
    vol = pd.to_numeric(frame["volatility_63d"], errors="coerce")
    vol_cutoff = vol.quantile(0.90) if vol.notna().any() else np.nan
    frame["blocked_by_volatility_filter"] = (
        vol > vol_cutoff
    ) & frame["symbol"].ne("BTC-USD")
    frame["blocked_by_drawdown_filter"] = (
        pd.to_numeric(frame["drawdown_from_252d_high"], errors="coerce") < -0.35
    )
    frame["eligible_after_filters"] = (
        frame["eligible_before_filters"]
        & ~frame["blocked_by_missing_data"]
        & ~frame["blocked_by_negative_score"]
        & ~frame["blocked_by_drawdown_filter"]
    )
    return frame


def _market_risk_on(scores_for_signal: pd.DataFrame) -> bool:
    if scores_for_signal.empty or "market_risk_on_flag" not in scores_for_signal.columns:
        return True
    return bool(scores_for_signal["market_risk_on_flag"].fillna(1.0).median() >= 0.5)


def _defensive_basket(scores_for_signal: pd.DataFrame, weight: float) -> pd.Series:
    if weight <= 0:
        return pd.Series(dtype=float)
    available = [asset for asset in DEFENSIVE_ASSETS if asset == "CASH" or asset in set(scores_for_signal["symbol"])]
    if not available:
        return pd.Series({"CASH": weight})
    risk_assets = [asset for asset in available if asset != "CASH"]
    if not risk_assets:
        return pd.Series({"CASH": weight})
    rows = scores_for_signal.set_index("symbol").reindex(risk_assets)
    inv_vol = 1.0 / pd.to_numeric(rows["volatility_63d"], errors="coerce").clip(lower=1e-6)
    inv_vol = inv_vol.replace([np.inf, -np.inf], np.nan).dropna()
    if inv_vol.empty:
        return pd.Series({"CASH": weight})
    inv_vol = inv_vol / inv_vol.sum() * min(weight, weight * 0.75)
    cash_weight = weight - float(inv_vol.sum())
    result = inv_vol.copy()
    if cash_weight > 1e-9:
        result.loc["CASH"] = cash_weight
    return result


def _cap_weights(raw: pd.Series, spec: V1StrategySpec) -> pd.Series:
    capped = _cap_and_redistribute(
        raw,
        max_single_asset_weight=spec.max_single_asset_weight,
        max_btc_weight=spec.max_btc_weight,
        max_oil_weight=spec.max_oil_weight,
        max_commodity_weight=spec.max_commodity_weight,
    )
    if capped.empty:
        return capped
    released = 0.0
    for asset, cap in {
        "BTC-USD": spec.max_btc_weight,
        "USO": spec.max_oil_weight,
    }.items():
        if asset in capped.index and capped.loc[asset] > cap:
            released += float(capped.loc[asset] - cap)
            capped.loc[asset] = cap
    for asset in list(capped.index):
        if asset != "CASH" and capped.loc[asset] > spec.max_single_asset_weight:
            released += float(capped.loc[asset] - spec.max_single_asset_weight)
            capped.loc[asset] = spec.max_single_asset_weight
    commodity_assets = [asset for asset in capped.index if asset in COMMODITY_ASSETS]
    commodity_weight = float(capped.loc[commodity_assets].sum()) if commodity_assets else 0.0
    if commodity_weight > spec.max_commodity_weight and commodity_weight > 0:
        scale = spec.max_commodity_weight / commodity_weight
        released += commodity_weight - spec.max_commodity_weight
        capped.loc[commodity_assets] *= scale
    if released > 0:
        capped.loc["CASH"] = capped.get("CASH", 0.0) + released
    total = float(capped.sum())
    if total <= 0:
        return pd.Series({"CASH": 1.0})
    if total < 1.0:
        capped.loc["CASH"] = capped.get("CASH", 0.0) + (1.0 - total)
    elif total > 1.0:
        non_cash = [asset for asset in capped.index if asset != "CASH"]
        excess = total - 1.0
        if "CASH" in capped.index and capped.loc["CASH"] >= excess:
            capped.loc["CASH"] -= excess
        elif non_cash:
            capped.loc[non_cash] *= (1.0 - capped.get("CASH", 0.0)) / capped.loc[non_cash].sum()
    return capped.sort_index()


def _base_opportunity_weights(
    scores_for_signal: pd.DataFrame,
    spec: V1StrategySpec,
    *,
    top_n: int | None = None,
    allow_negative: bool = False,
) -> pd.Series:
    filter_frame = _asset_filter_frame(scores_for_signal)
    eligible = filter_frame.loc[filter_frame["eligible_before_filters"]].copy()
    if not allow_negative:
        eligible = eligible.loc[~eligible["blocked_by_negative_score"]]
    eligible = eligible.loc[~eligible["blocked_by_missing_data"]]
    eligible = eligible.sort_values("raw_score", ascending=False).head(top_n or spec.top_n)
    if eligible.empty:
        return pd.Series(dtype=float)
    inv_vol = 1.0 / pd.to_numeric(
        eligible.set_index("symbol")["volatility_63d"],
        errors="coerce",
    ).clip(lower=1e-6)
    inv_vol = inv_vol.replace([np.inf, -np.inf], np.nan).dropna()
    return inv_vol / inv_vol.sum() if not inv_vol.empty else pd.Series(dtype=float)


def _apply_sticky_overlay(
    *,
    desired: pd.Series,
    previous: pd.Series,
    scores_for_signal: pd.DataFrame,
    min_score_improvement: float,
    min_weight_change: float,
) -> pd.Series:
    if previous.empty or previous.get("CASH", 0.0) > 0.95:
        return desired
    previous_assets = [asset for asset, weight in previous.items() if asset != "CASH" and weight > 1e-6]
    desired_assets = [asset for asset, weight in desired.items() if asset != "CASH" and weight > 1e-6]
    score_lookup = scores_for_signal.set_index("symbol")["opportunity_score"].to_dict()
    held_scores = [float(score_lookup.get(asset, -np.inf)) for asset in previous_assets]
    weakest_held = min(held_scores) if held_scores else -np.inf
    changed = False
    for asset in desired_assets:
        if asset not in previous_assets and float(score_lookup.get(asset, -np.inf)) > weakest_held + min_score_improvement:
            changed = True
            break
    if not changed:
        blended = previous.reindex(sorted(set(previous.index) | set(desired.index))).fillna(0.0)
        small_delta = (
            desired.reindex(blended.index).fillna(0.0) - blended
        ).abs() < min_weight_change
        adjusted = desired.reindex(blended.index).fillna(0.0)
        adjusted.loc[small_delta] = blended.loc[small_delta]
        if adjusted.sum() > 0:
            return adjusted / adjusted.sum()
        return previous
    combined_index = sorted(set(previous.index) | set(desired.index))
    blended = (
        0.65 * previous.reindex(combined_index).fillna(0.0)
        + 0.35 * desired.reindex(combined_index).fillna(0.0)
    )
    return blended / blended.sum() if blended.sum() > 0 else desired


def _weights_for_signal_v1(
    *,
    scores_for_signal: pd.DataFrame,
    spec: V1StrategySpec,
    previous_weights: pd.Series,
) -> pd.Series:
    risk_on = _market_risk_on(scores_for_signal)
    ranked = scores_for_signal.loc[scores_for_signal["symbol"] != "CASH"].copy()
    top_score = pd.to_numeric(ranked["opportunity_score"], errors="coerce").max()
    spy_row = ranked.loc[ranked["symbol"] == "SPY"]
    spy_below_200 = bool(
        not spy_row.empty
        and pd.to_numeric(spy_row["price_above_200d_ma"], errors="coerce").fillna(1.0).iloc[0] < 0.5
    )
    severe_risk_off = (not risk_on) and (pd.isna(top_score) or top_score <= 0 or spy_below_200)

    if spec.mode == "core_satellite":
        core_raw = pd.Series({"SPY": 0.30, "QQQ": 0.18, "GLD": 0.06, "TLT": 0.06})
        sleeve = _base_opportunity_weights(scores_for_signal, spec, top_n=3, allow_negative=False)
        raw = core_raw.copy()
        if not sleeve.empty:
            raw = raw.add(sleeve * 0.40, fill_value=0.0)
        else:
            raw.loc["CASH"] = raw.get("CASH", 0.0) + 0.40
        return _cap_weights(raw, spec)

    opportunity = _base_opportunity_weights(scores_for_signal, spec, allow_negative=spec.mode == "balanced")
    if opportunity.empty:
        return pd.Series({"CASH": 1.0})

    if spec.mode == "balanced":
        if risk_on:
            raw = opportunity
        else:
            raw = opportunity * 0.60
            raw = raw.add(_defensive_basket(scores_for_signal, 0.40), fill_value=0.0)
        return _cap_weights(raw, spec)

    if spec.mode == "growth_guarded":
        if severe_risk_off:
            raw = opportunity * 0.35
            raw = raw.add(_defensive_basket(scores_for_signal, 0.65), fill_value=0.0)
        elif not risk_on:
            raw = opportunity * 0.70
            raw = raw.add(_defensive_basket(scores_for_signal, 0.30), fill_value=0.0)
        else:
            raw = opportunity
        return _cap_weights(raw, spec)

    if spec.mode == "sticky":
        if severe_risk_off:
            raw = opportunity * 0.50
            raw = raw.add(_defensive_basket(scores_for_signal, 0.50), fill_value=0.0)
        elif not risk_on:
            raw = opportunity * 0.70
            raw = raw.add(_defensive_basket(scores_for_signal, 0.30), fill_value=0.0)
        else:
            raw = opportunity
        capped = _cap_weights(raw, spec)
        sticky = _apply_sticky_overlay(
            desired=capped,
            previous=previous_weights,
            scores_for_signal=scores_for_signal,
            min_score_improvement=spec.min_score_improvement,
            min_weight_change=spec.min_weight_change,
        )
        return _cap_weights(sticky, spec)

    return _cap_weights(opportunity, spec)


def simulate_v1_strategy(
    *,
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    spec: V1StrategySpec,
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
    current_value = starting_cash
    equity_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for index, (signal_date, execution_date) in enumerate(pairs):
        signal_scores = score_by_date.get(pd.Timestamp(signal_date), pd.DataFrame())
        if signal_scores.empty:
            continue
        target_weights = _weights_for_signal_v1(
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
        cost = current_value * turnover * transaction_cost_bps / 10_000.0
        current_value -= cost
        event_rows.append(
            {
                "strategy_name": spec.strategy_name,
                "signal_date": signal_date.date().isoformat(),
                "execution_date": execution_date.date().isoformat(),
                "selected_assets": ",".join([asset for asset in target_weights.index if asset != "CASH" and target_weights.loc[asset] > 1e-6]),
                "target_weights": ";".join(f"{asset}:{weight:.6f}" for asset, weight in target_weights.items()),
                "asset_turnover": ";".join(f"{asset}:{value:.6f}" for asset, value in asset_turnover.items() if value > 1e-9),
                "turnover": turnover,
                "transaction_cost_bps": transaction_cost_bps,
                "transaction_cost_usd": cost,
                "market_risk_on_flag": _market_risk_on(signal_scores),
                "v1_mode": spec.mode,
            }
        )
        current_weights = target_weights
        next_execution = pairs[index + 1][1] if index + 1 < len(pairs) else returns.index[-1]
        period_dates = returns.index[(returns.index >= execution_date) & (returns.index < next_execution)]
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
                        "weight": weight,
                        "transaction_cost_bps": transaction_cost_bps,
                    }
                )
    return pd.DataFrame(equity_rows), pd.DataFrame(weight_rows), pd.DataFrame(event_rows)


def _metrics(equity: pd.DataFrame, events: pd.DataFrame, weights: pd.DataFrame) -> dict[str, Any]:
    if equity.empty:
        return {}
    frame = equity.sort_values("date").drop_duplicates("date")
    series = frame.set_index(pd.to_datetime(frame["date"]))["portfolio_value"].astype(float)
    returns = series.pct_change().dropna()
    years = max((series.index.max() - series.index.min()).days / 365.25, 1 / 365.25)
    final_value = float(series.iloc[-1])
    cagr = (final_value / float(series.iloc[0])) ** (1 / years) - 1
    max_dd = float(_drawdown(series).min())
    annualized_vol = float(returns.std() * np.sqrt(252)) if not returns.empty else 0.0
    sharpe = float(returns.mean() / returns.std() * np.sqrt(252)) if returns.std() else np.nan
    turnover_value = pd.to_numeric(events.get("turnover", pd.Series(dtype=float)), errors="coerce").mean()
    turnover = float(turnover_value) if pd.notna(turnover_value) else 0.0
    btc_max = _max_weight(weights, "BTC-USD")
    oil_max = _max_weight(weights, "USO")
    commodity_max = _max_group_weight(weights, COMMODITY_ASSETS)
    return {
        "start_date": series.index.min().date().isoformat(),
        "end_date": series.index.max().date().isoformat(),
        "initial_value": float(series.iloc[0]),
        "final_value": final_value,
        "total_return_pct": (final_value / float(series.iloc[0]) - 1) * 100,
        "CAGR": cagr * 100,
        "max_drawdown": max_dd * 100,
        "Calmar": cagr / abs(max_dd) if max_dd else np.nan,
        "Sharpe": sharpe,
        "annualized_volatility": annualized_vol * 100,
        "turnover": turnover,
        "number_of_rebalances": len(events),
        "BTC_max_actual_weight": btc_max,
        "oil_max_actual_weight": oil_max,
        "commodity_max_actual_weight": commodity_max,
    }


def _max_weight(weights: pd.DataFrame, asset: str) -> float:
    if weights.empty or "asset" not in weights.columns:
        return 0.0
    values = pd.to_numeric(weights.loc[weights["asset"] == asset, "weight"], errors="coerce")
    max_value = values.max()
    return float(max_value) if pd.notna(max_value) else 0.0


def _max_group_weight(weights: pd.DataFrame, assets: set[str]) -> float:
    if weights.empty or "asset" not in weights.columns:
        return 0.0
    frame = weights.loc[weights["asset"].isin(assets)].copy()
    if frame.empty:
        return 0.0
    grouped = frame.groupby(["date", "strategy_name"])["weight"].sum()
    value = pd.to_numeric(grouped, errors="coerce").max()
    return float(value) if pd.notna(value) else 0.0


def _build_score_to_weight_audit(
    *,
    scores: pd.DataFrame,
    v0_events: pd.DataFrame,
    v1_events: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    event_frames = []
    if not v0_events.empty:
        event_frames.append(v0_events)
    if not v1_events.empty:
        event_frames.append(v1_events)
    events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    if scores.empty or events.empty:
        return pd.DataFrame()
    score_by_date = {pd.Timestamp(date): group.copy() for date, group in scores.groupby(pd.to_datetime(scores["date"]))}
    latest_score_date = pd.to_datetime(scores["date"]).max()
    score_counts = scores.groupby(pd.to_datetime(scores["date"]))["symbol"].nunique()
    latest_multi_asset_score_date = (
        score_counts.loc[score_counts >= 3].index.max()
        if not score_counts.loc[score_counts >= 3].empty
        else latest_score_date
    )
    latest_top3_weights = pd.Series(dtype=float)
    top3_events = events.loc[events["strategy_name"] == "dynamic_top3_technical_opportunity_v0"]
    if not top3_events.empty:
        latest_top3_weights = _parse_target_weights(top3_events.sort_values("signal_date").iloc[-1].get("target_weights", ""))
    sample_events = []
    for strategy, group in events.groupby("strategy_name"):
        group = group.sort_values("signal_date")
        sample_events.extend(group.tail(3).to_dict("records"))
    for event in sample_events:
        signal_date = pd.Timestamp(event["signal_date"])
        signal_scores = score_by_date.get(signal_date, pd.DataFrame())
        if signal_scores.empty:
            continue
        target_weights = _parse_target_weights(event.get("target_weights", ""))
        filter_frame = _asset_filter_frame(signal_scores)
        risk_on = _market_risk_on(signal_scores)
        chosen = set(target_weights[target_weights > 1e-8].index)
        top_n = 5 if "top5" in str(event["strategy_name"]) else 3
        for row in filter_frame.sort_values("raw_score", ascending=False).itertuples(index=False):
            asset = str(row.symbol)
            final_weight = float(target_weights.get(asset, 0.0))
            cash_weight = float(target_weights.get("CASH", 0.0))
            rank = int(row.rank) if pd.notna(row.rank) else 999
            blocked_by_market = (not risk_on) and asset not in set(DEFENSIVE_ASSETS) and final_weight == 0
            blocked_by_cap = bool(asset in chosen and final_weight < 1.0 / max(top_n, 1) * 0.75)
            if final_weight > 0:
                explanation = "selected; final weight reflects inverse-vol sizing and caps"
            elif blocked_by_market:
                explanation = "blocked by market risk-off filter; allocation moved toward defensive assets or cash"
            elif bool(row.blocked_by_negative_score):
                explanation = "not selected because opportunity score was non-positive"
            elif bool(row.blocked_by_drawdown_filter):
                explanation = "not selected because drawdown filter flagged asset"
            elif bool(row.blocked_by_volatility_filter):
                explanation = "not selected because volatility filter flagged asset"
            elif rank > top_n:
                explanation = "not selected because asset ranked outside strategy top-N set"
            else:
                explanation = "not selected after sizing/cap logic"
            if signal_date != latest_score_date and event == sample_events[-1]:
                explanation += "; latest score panel can differ from latest held weights because weights update only at scheduled rebalance"
            rows.append(
                {
                    "rebalance_date": signal_date.date().isoformat(),
                    "strategy": event["strategy_name"],
                    "asset": asset,
                    "raw_score": row.raw_score,
                    "rank": rank,
                    "eligible_before_filters": bool(row.eligible_before_filters),
                    "eligible_after_filters": bool(row.eligible_after_filters) and not blocked_by_market,
                    "blocked_by_market_risk_filter": blocked_by_market,
                    "blocked_by_asset_cap": blocked_by_cap,
                    "blocked_by_missing_data": bool(row.blocked_by_missing_data),
                    "blocked_by_negative_score": bool(row.blocked_by_negative_score),
                    "blocked_by_volatility_filter": bool(row.blocked_by_volatility_filter),
                    "blocked_by_drawdown_filter": bool(row.blocked_by_drawdown_filter),
                    "pre_cap_weight": np.nan,
                    "post_cap_weight": final_weight,
                    "final_weight": final_weight,
                    "cash_weight_after_filters": cash_weight,
                    "allocation_explanation": explanation,
                }
            )
        if "CASH" in target_weights.index:
            rows.append(
                {
                    "rebalance_date": signal_date.date().isoformat(),
                    "strategy": event["strategy_name"],
                    "asset": "CASH",
                    "raw_score": np.nan,
                    "rank": np.nan,
                    "eligible_before_filters": True,
                    "eligible_after_filters": True,
                    "blocked_by_market_risk_filter": False,
                    "blocked_by_asset_cap": False,
                    "blocked_by_missing_data": False,
                    "blocked_by_negative_score": False,
                    "blocked_by_volatility_filter": False,
                    "blocked_by_drawdown_filter": False,
                    "pre_cap_weight": target_weights.get("CASH", 0.0),
                    "post_cap_weight": target_weights.get("CASH", 0.0),
                    "final_weight": target_weights.get("CASH", 0.0),
                    "cash_weight_after_filters": target_weights.get("CASH", 0.0),
                    "allocation_explanation": "cash residual from risk filter, missing eligible assets, and/or cap redistribution",
                }
            )
    if latest_multi_asset_score_date in score_by_date:
        signal_scores = score_by_date[latest_multi_asset_score_date]
        filter_frame = _asset_filter_frame(signal_scores)
        for row in filter_frame.sort_values("raw_score", ascending=False).head(15).itertuples(index=False):
            asset = str(row.symbol)
            held_weight = float(latest_top3_weights.get(asset, 0.0)) if not latest_top3_weights.empty else 0.0
            rows.append(
                {
                    "rebalance_date": pd.Timestamp(latest_multi_asset_score_date).date().isoformat(),
                    "strategy": "latest_multi_asset_score_panel_no_rebalance",
                    "asset": asset,
                    "raw_score": row.raw_score,
                    "rank": int(row.rank) if pd.notna(row.rank) else np.nan,
                    "eligible_before_filters": bool(row.eligible_before_filters),
                    "eligible_after_filters": bool(row.eligible_after_filters),
                    "blocked_by_market_risk_filter": False,
                    "blocked_by_asset_cap": False,
                    "blocked_by_missing_data": bool(row.blocked_by_missing_data),
                    "blocked_by_negative_score": bool(row.blocked_by_negative_score),
                    "blocked_by_volatility_filter": bool(row.blocked_by_volatility_filter),
                    "blocked_by_drawdown_filter": bool(row.blocked_by_drawdown_filter),
                    "pre_cap_weight": np.nan,
                    "post_cap_weight": held_weight,
                    "final_weight": held_weight,
                    "cash_weight_after_filters": float(latest_top3_weights.get("CASH", 0.0)) if not latest_top3_weights.empty else np.nan,
                    "allocation_explanation": (
                        "latest multi-asset score panel; not itself a rebalance event. "
                        "Held v0 weights came from the latest scheduled signal date, which may differ because signals update monthly."
                    ),
                }
            )
    return pd.DataFrame(rows)


def _cash_audit(weights: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame()
    rows = []
    cash = weights.loc[weights["asset"] == "CASH"].copy()
    for strategy, group in weights.groupby("strategy_name"):
        cash_group = cash.loc[cash["strategy_name"] == strategy].copy()
        if cash_group.empty:
            avg_cash = 0.0
            latest_cash = 0.0
            over_50 = 0
            examples = ""
        else:
            cash_group["date"] = pd.to_datetime(cash_group["date"])
            cash_group["weight"] = pd.to_numeric(cash_group["weight"], errors="coerce").fillna(0.0)
            avg_cash = float(cash_group["weight"].mean())
            latest_cash = float(cash_group.sort_values("date")["weight"].iloc[-1])
            over = cash_group.loc[cash_group["weight"] > 0.50]
            over_50 = len(over)
            examples = ",".join(over["date"].dt.date.astype(str).tail(5).tolist())
        event_group = events.loc[events["strategy_name"] == strategy] if not events.empty else pd.DataFrame()
        risk_off_count = (
            int((~event_group.get("market_risk_on_flag", pd.Series(dtype=bool)).map(_bool_value)).sum())
            if not event_group.empty
            else 0
        )
        reason = (
            "cash-heavy dates mostly coincide with risk-off events and cap residuals"
            if risk_off_count
            else "cash is residual after caps or unavailable eligible assets"
        )
        rows.append(
            {
                "strategy": strategy,
                "average_cash_weight": avg_cash,
                "latest_cash_weight": latest_cash,
                "cash_over_50_day_count": over_50,
                "cash_over_50_latest_dates": examples,
                "risk_off_rebalance_count": risk_off_count,
                "cash_heavy_reason": reason,
            }
        )
    return pd.DataFrame(rows)


def _asset_turnover_counts(events: pd.DataFrame) -> dict[str, str]:
    result: dict[str, str] = {}
    if events.empty or "asset_turnover" not in events.columns:
        return result
    for strategy, group in events.groupby("strategy_name"):
        totals: dict[str, float] = {}
        for text in group["asset_turnover"].dropna().astype(str):
            for part in text.split(";"):
                if ":" not in part:
                    continue
                asset, value = part.split(":", 1)
                try:
                    totals[asset] = totals.get(asset, 0.0) + float(value)
                except ValueError:
                    continue
        ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:5]
        result[strategy] = ",".join(asset for asset, _value in ordered)
    return result


def _turnover_diagnostics(
    *,
    events: pd.DataFrame,
    tc: pd.DataFrame,
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    most_traded = _asset_turnover_counts(events)
    rows = []
    for strategy, group in events.groupby("strategy_name"):
        group = group.sort_values("execution_date")
        start = pd.to_datetime(group["execution_date"]).min()
        end = pd.to_datetime(group["execution_date"]).max()
        years = max((end - start).days / 365.25, 1 / 365.25)
        turnover = pd.to_numeric(group["turnover"], errors="coerce").dropna()
        tc_group = tc.loc[tc["strategy_name"] == strategy].copy() if not tc.empty else pd.DataFrame()
        final_by_cost = {
            int(row.transaction_cost_bps): float(row.final_value)
            for row in tc_group.itertuples(index=False)
            if pd.notna(row.final_value)
        }
        zero = final_by_cost.get(0, np.nan)
        ten = final_by_cost.get(10, np.nan)
        twentyfive = final_by_cost.get(25, np.nan)
        drag10 = (zero - ten) / zero * 100 if zero and pd.notna(ten) else np.nan
        drag25 = (zero - twentyfive) / zero * 100 if zero and pd.notna(twentyfive) else np.nan
        annualized = float(turnover.mean() * len(group) / years) if not turnover.empty else 0.0
        warnings = []
        if annualized > 4.0:
            warnings.append("annualized_turnover_above_4x")
        if pd.notna(drag25) and drag25 > 25:
            warnings.append("cost_drag_25bps_above_25pct")
        rows.append(
            {
                "strategy": strategy,
                "period_start": start.date().isoformat(),
                "period_end": end.date().isoformat(),
                "rebalance_count": len(group),
                "average_turnover": float(turnover.mean()) if not turnover.empty else 0.0,
                "median_turnover": float(turnover.median()) if not turnover.empty else 0.0,
                "max_turnover": float(turnover.max()) if not turnover.empty else 0.0,
                "annualized_turnover": annualized,
                "zero_cost_final_value": zero,
                "ten_bps_final_value": ten,
                "twentyfive_bps_final_value": twentyfive,
                "cost_drag_10bps_pct": drag10,
                "cost_drag_25bps_pct": drag25,
                "most_traded_assets": most_traded.get(strategy, ""),
                "turnover_warning": ";".join(warnings) if warnings else "none",
            }
        )
    return pd.DataFrame(rows)


def _asset_contribution_summary(
    *,
    weights: pd.DataFrame,
    prices: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    if weights.empty or prices.empty:
        return pd.DataFrame()
    returns = _returns_with_cash(prices)
    weights_frame = weights.copy()
    weights_frame["date"] = pd.to_datetime(weights_frame["date"])
    rows = []
    for strategy, group in weights_frame.groupby("strategy_name"):
        pivot = group.pivot_table(index="date", columns="asset", values="weight", aggfunc="last").sort_index()
        aligned_returns = returns.reindex(pivot.index).fillna(0.0)
        event_group = events.loc[events["strategy_name"] == strategy] if not events.empty else pd.DataFrame()
        for asset in sorted(set(pivot.columns)):
            asset_weight = pd.to_numeric(pivot[asset], errors="coerce").fillna(0.0)
            asset_return = aligned_returns[asset] if asset in aligned_returns.columns else pd.Series(0.0, index=pivot.index)
            contribution = asset_weight.shift(1).fillna(asset_weight) * asset_return.fillna(0.0)
            event_count = (
                event_group["selected_assets"].fillna("").astype(str).str.contains(asset, regex=False).sum()
                if not event_group.empty and "selected_assets" in event_group.columns
                else 0
            )
            rows.append(
                {
                    "strategy": strategy,
                    "asset": asset,
                    "average_weight": float(asset_weight.mean()),
                    "max_weight": float(asset_weight.max()),
                    "days_held": int((asset_weight > 1e-6).sum()),
                    "rebalance_count_in_asset": int(event_count),
                    "approx_return_contribution": float(contribution.sum() * 100),
                    "approx_drawdown_contribution": float(contribution.loc[contribution < 0].sum() * 100),
                    "notes": "approximate daily weight times asset-return contribution; not broker-level attribution",
                }
            )
    return pd.DataFrame(rows)


def _cost_sensitivity(
    *,
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    specs: list[V1StrategySpec],
    starting_cash: float,
    transaction_cost_cases: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    all_equity = []
    all_weights = []
    all_events = []
    metrics_rows = []
    tc_rows = []
    for spec in specs:
        for cost in transaction_cost_cases:
            equity, weights, events = simulate_v1_strategy(
                prices=prices,
                scores=scores,
                spec=spec,
                starting_cash=starting_cash,
                transaction_cost_bps=float(cost),
            )
            if equity.empty:
                continue
            metric = _metrics(equity, events, weights)
            metric.update(
                {
                    "strategy_name": spec.strategy_name,
                    "transaction_cost_bps": cost,
                    "paper_only": True,
                    "promotion_allowed": False,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                }
            )
            tc_rows.append(
                {
                    "strategy_name": spec.strategy_name,
                    "transaction_cost_bps": cost,
                    "strategy_cost_case": f"{spec.strategy_name}_{cost}bps",
                    "final_value": metric["final_value"],
                    "CAGR": metric["CAGR"],
                    "max_drawdown": metric["max_drawdown"],
                }
            )
            if cost == 0:
                metrics_rows.append(metric)
                all_equity.append(equity)
                all_weights.append(weights)
                all_events.append(events)
    return (
        pd.concat(all_equity, ignore_index=True) if all_equity else pd.DataFrame(),
        pd.concat(all_weights, ignore_index=True) if all_weights else pd.DataFrame(),
        pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame(),
        pd.DataFrame(metrics_rows),
        pd.DataFrame(tc_rows),
    )


def _common_comparison_extended(
    *,
    benchmark_equity_path: Path,
    equity_frames: list[pd.DataFrame],
    starting_cash: float,
    turnover_diagnostics: pd.DataFrame,
    tc: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    benchmark = _read_csv(benchmark_equity_path)
    if not benchmark.empty and {"date", "canonical_candidate_id", "portfolio_value"}.issubset(benchmark.columns):
        bench = benchmark.rename(columns={"canonical_candidate_id": "strategy_name"})
        frames.append(bench[["date", "strategy_name", "portfolio_value"]])
    for frame in equity_frames:
        if not frame.empty and {"date", "strategy_name", "portfolio_value"}.issubset(frame.columns):
            frames.append(frame[["date", "strategy_name", "portfolio_value"]])
    if not frames:
        return pd.DataFrame(), pd.DataFrame()
    all_equity = pd.concat(frames, ignore_index=True)
    all_equity["date"] = pd.to_datetime(all_equity["date"])
    date_sets = [set(group["date"]) for _name, group in all_equity.groupby("strategy_name") if not group.empty]
    common_dates = sorted(set.intersection(*date_sets)) if date_sets else []
    if len(common_dates) < 2:
        return pd.DataFrame(), all_equity
    turnover_lookup = {}
    if not turnover_diagnostics.empty:
        turnover_lookup = turnover_diagnostics.set_index("strategy")["average_turnover"].to_dict()
    cost_drag_lookup = {}
    if not tc.empty:
        pivot = tc.pivot_table(index="strategy_name", columns="transaction_cost_bps", values="final_value", aggfunc="last")
        for strategy, row in pivot.iterrows():
            if 0 in row.index and 25 in row.index and row[0]:
                cost_drag_lookup[strategy] = (row[0] - row[25]) / row[0] * 100
    common_frames = []
    rows = []
    spy_normalized = pd.Series(dtype=float)
    for strategy, group in all_equity.groupby("strategy_name"):
        series = (
            group.sort_values("date")
            .drop_duplicates("date")
            .set_index("date")["portfolio_value"]
            .astype(float)
            .reindex(common_dates)
            .dropna()
        )
        normalized = series / float(series.iloc[0]) * starting_cash
        if strategy == "SPY Buy & Hold Benchmark":
            spy_normalized = normalized.copy()
        common_frames.append(
            pd.DataFrame(
                {
                    "date": normalized.index.date.astype(str),
                    "strategy_name": strategy,
                    "portfolio_value": normalized.values,
                }
            )
        )
    common_equity = pd.concat(common_frames, ignore_index=True)
    for strategy, group in common_equity.groupby("strategy_name"):
        series = group.sort_values("date").set_index(pd.to_datetime(group["date"]))["portfolio_value"].astype(float)
        returns = series.pct_change().dropna()
        years = max((series.index.max() - series.index.min()).days / 365.25, 1 / 365.25)
        final_value = float(series.iloc[-1])
        cagr = (final_value / starting_cash) ** (1 / years) - 1
        max_dd = float(_drawdown(series).min())
        annual_vol = float(returns.std() * np.sqrt(252)) if not returns.empty else 0.0
        sharpe = float(returns.mean() / returns.std() * np.sqrt(252)) if returns.std() else np.nan
        worst_12m = float((series / series.shift(252) - 1.0).min() * 100) if len(series) > 252 else np.nan
        rolling_win = _rolling_3y_win_rate(series, spy_normalized)
        rows.append(
            {
                "strategy_name": strategy,
                "common_start_date": series.index.min().date().isoformat(),
                "common_end_date": series.index.max().date().isoformat(),
                "restriction_reason": "common overlap across current table, Phase22A v0, and Phase22B v1 candidates",
                "final_value": final_value,
                "CAGR": cagr * 100,
                "max_drawdown": max_dd * 100,
                "Calmar": cagr / abs(max_dd) if max_dd else np.nan,
                "Sharpe": sharpe,
                "annualized_volatility": annual_vol * 100,
                "turnover": turnover_lookup.get(strategy, np.nan),
                "transaction_cost_drag": cost_drag_lookup.get(strategy, np.nan),
                "worst_12m_return": worst_12m,
                "rolling_3y_win_rate_vs_SPY": rolling_win,
            }
        )
    return pd.DataFrame(rows), common_equity


def _rolling_3y_win_rate(series: pd.Series, spy: pd.Series) -> float:
    if series.empty or spy.empty:
        return np.nan
    aligned = pd.concat([series.rename("candidate"), spy.rename("spy")], axis=1).dropna()
    if len(aligned) <= 756:
        return np.nan
    candidate = aligned["candidate"] / aligned["candidate"].shift(756) - 1.0
    benchmark = aligned["spy"] / aligned["spy"].shift(756) - 1.0
    valid = pd.concat([candidate, benchmark], axis=1).dropna()
    if valid.empty:
        return np.nan
    return float((valid.iloc[:, 0] > valid.iloc[:, 1]).mean() * 100)


def _v0_failure_modes(
    *,
    cash_audit: pd.DataFrame,
    turnover: pd.DataFrame,
    comparison: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for strategy in V0_STRATEGIES:
        cash_row = cash_audit.loc[cash_audit["strategy"] == strategy]
        turn_row = turnover.loc[turnover["strategy"] == strategy]
        comp_row = comparison.loc[comparison["strategy_name"] == strategy]
        failure_modes = []
        if not cash_row.empty and float(cash_row["average_cash_weight"].iloc[0]) > 0.35:
            failure_modes.append("cash_drag")
        if not turn_row.empty and str(turn_row["turnover_warning"].iloc[0]) != "none":
            failure_modes.append(str(turn_row["turnover_warning"].iloc[0]))
        if not comp_row.empty and float(comp_row["CAGR"].iloc[0]) < 10:
            failure_modes.append("under_earned_vs_current_candidates")
        rows.append(
            {
                "strategy": strategy,
                "failure_modes": ";".join(failure_modes) if failure_modes else "none",
                "diagnostic_note": "v0 is research-only; failure modes are used only to guide transparent v1 variants",
            }
        )
    return pd.DataFrame(rows)


def _plot_scatter(frame: pd.DataFrame, path: Path) -> None:
    if frame.empty or not {"max_drawdown", "CAGR", "strategy_name"}.issubset(frame.columns):
        _placeholder(path, "Risk/Return Scatter", "Missing comparison data")
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(frame["max_drawdown"], frame["CAGR"])
    for row in frame.itertuples(index=False):
        ax.annotate(str(row.strategy_name)[:24], (row.max_drawdown, row.CAGR), fontsize=8)
    ax.set_title("Phase22B Risk/Return")
    ax.set_xlabel("Max drawdown (%)")
    ax.set_ylabel("CAGR (%)")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _placeholder(path: Path, title: str, message: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _write_charts(
    *,
    visuals_dir: Path,
    common_equity: pd.DataFrame,
    drawdowns: pd.DataFrame,
    comparison: pd.DataFrame,
    turnover: pd.DataFrame,
    latest_audit: pd.DataFrame,
    cash_audit: pd.DataFrame,
    contribution: pd.DataFrame,
    latest_weights: pd.DataFrame,
) -> list[Path]:
    visuals_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        visuals_dir / "phase22b_v1_equity_curves.png",
        visuals_dir / "phase22b_v1_drawdowns.png",
        visuals_dir / "phase22b_v1_final_value_bar.png",
        visuals_dir / "phase22b_v1_risk_return_scatter.png",
        visuals_dir / "phase22b_turnover_bar.png",
        visuals_dir / "phase22b_cost_drag_bar.png",
        visuals_dir / "phase22b_latest_score_to_weight.png",
        visuals_dir / "phase22b_cash_weight_over_time.png",
        visuals_dir / "phase22b_asset_contribution_bar.png",
        visuals_dir / "phase22b_v1_latest_weights_bar.png",
    ]
    _plot_lines(common_equity, "portfolio_value", paths[0], "Phase22B Equity Curves", "Portfolio value")
    _plot_lines(drawdowns, "drawdown_pct", paths[1], "Phase22B Drawdowns", "Drawdown (%)")
    _plot_bar(comparison, "strategy_name", "final_value", paths[2], "Phase22B Final Value")
    _plot_scatter(comparison, paths[3])
    _plot_bar(turnover, "strategy", "annualized_turnover", paths[4], "Annualized Turnover")
    _plot_bar(turnover, "strategy", "cost_drag_25bps_pct", paths[5], "25 bps Cost Drag (%)")
    latest_plot = latest_audit.loc[latest_audit["strategy"].astype(str).str.contains("top", case=False, na=False)].head(15)
    _plot_bar(latest_plot, "asset", "final_weight", paths[6], "Latest Score-to-Weight")
    _plot_bar(cash_audit, "strategy", "latest_cash_weight", paths[7], "Latest Cash Weight")
    positive_contrib = contribution.sort_values("approx_return_contribution", ascending=False).head(15)
    _plot_bar(positive_contrib, "asset", "approx_return_contribution", paths[8], "Approx Return Contribution")
    _plot_bar(latest_weights, "asset", "weight", paths[9], "Latest V1 Weights")
    return paths


def _write_research_summary(
    *,
    path: Path,
    decision: str,
    score_audit: pd.DataFrame,
    cash_audit: pd.DataFrame,
    turnover: pd.DataFrame,
    contribution: pd.DataFrame,
    metrics: pd.DataFrame,
    comparison: pd.DataFrame,
) -> None:
    lines = [
        "# Phase 22B Dynamic Opportunity Diagnostics and v1 Improvements",
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
        "Score-to-weight audit:",
        score_audit.head(25).to_markdown(index=False) if not score_audit.empty else "No score-to-weight audit available.",
        "",
        "Cash allocation audit:",
        cash_audit.to_markdown(index=False) if not cash_audit.empty else "No cash audit available.",
        "",
        "Turnover diagnostics:",
        turnover.to_markdown(index=False) if not turnover.empty else "No turnover diagnostics available.",
        "",
        "Approximate asset contribution summary:",
        contribution.sort_values("approx_return_contribution", ascending=False).head(20).to_markdown(index=False)
        if not contribution.empty
        else "No contribution summary available.",
        "",
        "v1 strategy metrics:",
        metrics.to_markdown(index=False) if not metrics.empty else "No v1 metrics available.",
        "",
        "Comparison vs current table:",
        comparison.to_markdown(index=False) if not comparison.empty else "No benchmark comparison available.",
        "",
        "Interpretation: Phase22B remains a technical/risk-only research prototype. It is not an adoption, promotion, or paper-tracking change.",
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
    decision = "phase22b_failed_missing_phase22a_inputs"
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 22B",
                "phase22b_decision": decision,
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
            {"gate_id": "phase22a_inputs_available", "passed": False, "notes": ";".join(missing)},
            {"gate_id": "safety_flags_false", "passed": True, "notes": "research only"},
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 22B",
                "phase22b_decision": decision,
                "all_gates_passed": False,
                "notes": "Phase22B failed closed because required Phase22A inputs were missing.",
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
                "phase22b_decision": decision,
                "all_gates_passed": False,
                "v1_strategy_count": 0,
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Missing Phase22A inputs: " + ";".join(missing),
            }
        ]
    )
    _write_csv(summary, output_dir / "phase22b_summary.csv")
    _write_csv(gates, output_dir / "phase22b_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase22b_conclusion.csv")
    _write_csv(dashboard, dashboard_dir / "phase22b_dynamic_opportunity_diagnostics_status.csv")
    (output_dir / "phase22b_research_summary.md").write_text(
        "# Phase 22B Dynamic Opportunity Diagnostics\n\n"
        "NO LIVE TRADING\nNO REAL MONEY\nNO BROKER/API\nNO STRATEGY PROMOTION\n"
        "RESEARCH ONLY\nNOT ADDED TO DAILY PAPER RUNNER\n\n"
        f"Decision: `{decision}`\n\nMissing sources: {', '.join(missing)}\n",
        encoding="utf-8",
    )
    return {"summary": summary, "gate_report": gates, "conclusion": conclusion, "dashboard": dashboard}


def save_phase22b_dynamic_opportunity_diagnostics(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config)
    if not _bool_value(section.get("enabled", False)):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}
    reports_path = Path(reports_dir)
    root = reports_path.parent if reports_path.name == "reports" else Path.cwd()
    phase22a_section = config.get(PHASE22A_SECTION, {}) or {}
    input_dir = _resolve_path(
        section.get("input_dir"),
        _resolve_path(
            phase22a_section.get("output_dir"),
            reports_path / "strategy_factory" / "dynamic_opportunity_engine",
        ),
    )
    output_dir = _resolve_path(
        section.get("output_dir"),
        reports_path / "strategy_factory" / "dynamic_opportunity_engine_diagnostics",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        reports_path / "paper_trading" / "dashboard",
    )
    visuals_dir = output_dir / "visuals"
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    visuals_dir.mkdir(parents=True, exist_ok=True)

    required_inputs = [
        input_dir / "phase22a_opportunity_scores.csv",
        input_dir / "phase22a_dynamic_strategy_daily_equity.csv",
        input_dir / "phase22a_dynamic_strategy_daily_weights.csv",
        input_dir / "phase22a_rebalance_event_log.csv",
        input_dir / "phase22a_transaction_cost_sensitivity.csv",
    ]
    missing = [str(path) for path in required_inputs if not path.exists()]
    if missing:
        return _write_missing_sources(output_dir=output_dir, dashboard_dir=dashboard_dir, missing=missing)

    starting_cash = float(section.get("starting_cash", 10_000))
    transaction_cost_cases = [int(value) for value in section.get("transaction_cost_bps_cases", [0, 10, 25])]
    if 0 not in transaction_cost_cases:
        transaction_cost_cases.insert(0, 0)

    prices, _availability = load_asset_prices(root, DEFAULT_UNIVERSE)
    feature_store = build_feature_store(prices)
    scores = compute_opportunity_scores(feature_store)
    if scores.empty:
        scores = _read_csv(input_dir / "phase22a_opportunity_scores.csv")

    v0_equity = _read_csv(input_dir / "phase22a_dynamic_strategy_daily_equity.csv")
    v0_weights = _read_csv(input_dir / "phase22a_dynamic_strategy_daily_weights.csv")
    v0_events = _read_csv(input_dir / "phase22a_rebalance_event_log.csv")
    v0_tc = _read_csv(input_dir / "phase22a_transaction_cost_sensitivity.csv")
    v1_specs = _strategy_specs(section)
    v1_equity, v1_weights, v1_events, v1_metrics, v1_tc = _cost_sensitivity(
        prices=prices,
        scores=scores,
        specs=v1_specs,
        starting_cash=starting_cash,
        transaction_cost_cases=transaction_cost_cases,
    )
    v1_drawdowns = _daily_drawdowns(v1_equity) if not v1_equity.empty else pd.DataFrame()
    combined_equity = pd.concat([v0_equity, v1_equity], ignore_index=True) if not v0_equity.empty else v1_equity
    combined_weights = pd.concat([v0_weights, v1_weights], ignore_index=True) if not v0_weights.empty else v1_weights
    combined_events = pd.concat([v0_events, v1_events], ignore_index=True) if not v0_events.empty else v1_events
    combined_tc = pd.concat([v0_tc, v1_tc], ignore_index=True) if not v0_tc.empty else v1_tc

    score_audit = _build_score_to_weight_audit(scores=scores, v0_events=v0_events, v1_events=v1_events)
    filter_audit = score_audit.copy()
    cash_audit = _cash_audit(combined_weights, combined_events)
    turnover = _turnover_diagnostics(events=combined_events, tc=combined_tc)
    contribution = _asset_contribution_summary(weights=combined_weights, prices=prices, events=combined_events)
    rebalance_diagnostics = combined_events.copy()
    if not rebalance_diagnostics.empty:
        rebalance_diagnostics["rebalance_explanation"] = (
            "signal_date uses month-end feature data; execution_date is the next available trading date"
        )
    benchmark_path = root / "reports" / "paper_trading" / "regime_informed_tracking" / "performance" / "regime_informed_historical_daily_equity.csv"
    comparison, common_equity = _common_comparison_extended(
        benchmark_equity_path=benchmark_path,
        equity_frames=[v0_equity, v1_equity],
        starting_cash=starting_cash,
        turnover_diagnostics=turnover,
        tc=combined_tc,
    )
    candidate_comparison = comparison.copy()
    failure_modes = _v0_failure_modes(
        cash_audit=cash_audit,
        turnover=turnover,
        comparison=comparison,
    )
    latest_weights = (
        v1_weights.loc[v1_weights["date"] == v1_weights["date"].max()].copy()
        if not v1_weights.empty
        else pd.DataFrame()
    )
    if not latest_weights.empty:
        latest_weights = latest_weights.loc[
            latest_weights["strategy_name"] == "dynamic_top5_opportunity_v1_balanced"
        ]
    latest_score_audit = (
        score_audit.loc[score_audit["rebalance_date"] == score_audit["rebalance_date"].max()].copy()
        if not score_audit.empty
        else pd.DataFrame()
    )

    _write_csv(score_audit, output_dir / "phase22b_latest_score_to_weight_audit.csv")
    _write_csv(filter_audit, output_dir / "phase22b_filter_block_audit.csv")
    _write_csv(cash_audit, output_dir / "phase22b_cash_allocation_audit.csv")
    _write_csv(turnover, output_dir / "phase22b_turnover_diagnostics.csv")
    _write_csv(contribution, output_dir / "phase22b_asset_contribution_summary.csv")
    _write_csv(rebalance_diagnostics, output_dir / "phase22b_rebalance_diagnostics.csv")
    _write_csv(failure_modes, output_dir / "phase22b_v0_failure_modes.csv")
    _write_csv(v1_metrics, output_dir / "phase22b_v1_strategy_metrics.csv")
    _write_csv(v1_equity, output_dir / "phase22b_v1_daily_equity.csv")
    _write_csv(v1_drawdowns, output_dir / "phase22b_v1_daily_drawdowns.csv")
    _write_csv(v1_weights, output_dir / "phase22b_v1_daily_weights.csv")
    _write_csv(v1_events, output_dir / "phase22b_v1_rebalance_event_log.csv")
    _write_csv(v1_tc, output_dir / "phase22b_v1_transaction_cost_sensitivity.csv")
    _write_csv(comparison, output_dir / "phase22b_v1_benchmark_comparison.csv")
    _write_csv(candidate_comparison, output_dir / "phase22b_v1_candidate_comparison_vs_current_table.csv")

    chart_paths = _write_charts(
        visuals_dir=visuals_dir,
        common_equity=common_equity,
        drawdowns=_daily_drawdowns(combined_equity) if not combined_equity.empty else pd.DataFrame(),
        comparison=comparison,
        turnover=turnover,
        latest_audit=latest_score_audit,
        cash_audit=cash_audit,
        contribution=contribution,
        latest_weights=latest_weights,
    )

    best_v0 = comparison.loc[comparison["strategy_name"].isin(V0_STRATEGIES), "final_value"].max() if not comparison.empty else np.nan
    best_v1 = comparison.loc[comparison["strategy_name"].isin(V1_STRATEGIES), "final_value"].max() if not comparison.empty else np.nan
    decision = (
        "phase22b_v1_candidates_improved_but_not_promoted"
        if pd.notna(best_v0) and pd.notna(best_v1) and best_v1 > best_v0
        else "phase22b_v1_no_improvement_research_only"
    )
    if v1_metrics.empty or comparison.empty:
        decision = "phase22b_dynamic_opportunity_diagnostics_completed_research_only"

    summary_md_path = output_dir / "phase22b_research_summary.md"
    _write_research_summary(
        path=summary_md_path,
        decision=decision,
        score_audit=score_audit,
        cash_audit=cash_audit,
        turnover=turnover,
        contribution=contribution,
        metrics=v1_metrics,
        comparison=comparison,
    )
    gates = pd.DataFrame(
        [
            {"gate_id": "score_to_weight_audit_written", "passed": not score_audit.empty},
            {"gate_id": "cash_allocation_audit_written", "passed": not cash_audit.empty},
            {"gate_id": "turnover_diagnostics_written", "passed": not turnover.empty},
            {"gate_id": "asset_contribution_summary_written", "passed": not contribution.empty},
            {"gate_id": "at_least_3_v1_strategies_evaluated", "passed": len(v1_metrics) >= 3},
            {"gate_id": "benchmark_comparison_written", "passed": not comparison.empty},
            {"gate_id": "transaction_cost_sensitivity_written", "passed": not v1_tc.empty},
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
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 22B",
                "phase22b_decision": decision,
                "all_gates_passed": all_gates_passed,
                "v1_strategy_count": len(v1_metrics),
                "score_to_weight_audit_rows": len(score_audit),
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
                "phase": "Phase 22B",
                "phase22b_decision": decision,
                "all_gates_passed": all_gates_passed,
                "diagnostic": "Dynamic opportunity v0 diagnostics and transparent v1 research variants",
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Research only. Not added to daily paper runner.",
            }
        ]
    )
    dashboard = pd.DataFrame(
        [
            {
                "phase22b_decision": decision,
                "all_gates_passed": all_gates_passed,
                "v1_strategy_count": len(v1_metrics),
                "dashboard_status": "phase22b_dynamic_opportunity_diagnostics_status_written",
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Research-only diagnostics not connected to daily paper runner.",
            }
        ]
    )
    _write_csv(summary, output_dir / "phase22b_summary.csv")
    _write_csv(gates, output_dir / "phase22b_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase22b_conclusion.csv")
    _write_csv(dashboard, dashboard_dir / "phase22b_dynamic_opportunity_diagnostics_status.csv")
    print("Wrote Phase 22B dynamic opportunity diagnostics and v1 reports.")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "score_to_weight_audit": score_audit,
        "cash_audit": cash_audit,
        "turnover_diagnostics": turnover,
        "asset_contribution_summary": contribution,
        "v1_metrics": v1_metrics,
        "comparison": comparison,
        "transaction_cost_sensitivity": v1_tc,
        "dashboard": dashboard,
    }
