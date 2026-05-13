from __future__ import annotations

import numpy as np
import pandas as pd


def _prepare_result(result: pd.DataFrame, name: str) -> pd.DataFrame:
    required_columns = {
        "date",
        "adj_close",
        "strategy_return",
        "equity",
        "position",
        "cash_position",
        "turnover",
    }

    missing_columns = required_columns - set(result.columns)

    if missing_columns:
        raise ValueError(f"{name} result missing columns: {sorted(missing_columns)}")

    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    for column in [
        "adj_close",
        "strategy_return",
        "equity",
        "position",
        "cash_position",
        "turnover",
    ]:
        df[column] = df[column].astype(float)

    return df

def _create_confirmed_defensive_signal(
    above_trend: pd.Series,
    trend_ready: pd.Series,
    confirmation_days: int,
) -> pd.Series:
    if confirmation_days <= 0:
        raise ValueError("confirmation_days must be positive")

    above_trend = above_trend.astype(bool)
    trend_ready = trend_ready.astype(bool)

    below_trend = trend_ready & (~above_trend)
    above_trend_confirmable = trend_ready & above_trend

    if confirmation_days == 1:
        return below_trend.fillna(False)

    below_confirmed = (
        below_trend.astype(int)
        .rolling(confirmation_days)
        .sum()
        .eq(confirmation_days)
    )

    above_confirmed = (
        above_trend_confirmable.astype(int)
        .rolling(confirmation_days)
        .sum()
        .eq(confirmation_days)
    )

    defensive_state = False
    states: list[bool] = []

    for below_signal, above_signal in zip(
        below_confirmed.fillna(False),
        above_confirmed.fillna(False),
        strict=True,
    ):
        if below_signal:
            defensive_state = True
        elif above_signal:
            defensive_state = False

        states.append(defensive_state)

    return pd.Series(states, index=above_trend.index)

def run_spy_trend_regime_switch_overlay(
    offensive_result: pd.DataFrame,
    defensive_result: pd.DataFrame,
    initial_capital: float,
    trend_sma_days: int,
    slippage_bps: float,
    confirmation_days: int = 1,
) -> pd.DataFrame:
    """
    Regime-switching overlay.

    Rule:
    - Use offensive strategy when SPY/offensive proxy is above its trend SMA.
    - Use defensive allocator when SPY/offensive proxy is below its trend SMA.
    - Signal is observed using current close.
    - Execution occurs on the next trading day.
    - Position affects returns from the day after execution.

    This intentionally uses one simple regime signal only.
    """
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")

    if trend_sma_days <= 0:
        raise ValueError("trend_sma_days must be positive")

    offensive = _prepare_result(offensive_result, "offensive")
    defensive = _prepare_result(defensive_result, "defensive")

    merged = offensive[
        [
            "date",
            "adj_close",
            "strategy_return",
            "position",
            "cash_position",
            "turnover",
        ]
    ].merge(
        defensive[
            [
                "date",
                "strategy_return",
                "position",
                "cash_position",
                "turnover",
            ]
        ],
        on="date",
        how="inner",
        suffixes=("_offensive", "_defensive"),
    )

    if merged.empty:
        raise ValueError("No common dates between offensive and defensive results")

    merged = merged.sort_values("date").reset_index(drop=True)

    if confirmation_days <= 0:
        raise ValueError("confirmation_days must be positive")

    merged["trend_sma"] = merged["adj_close"].rolling(trend_sma_days).mean()
    merged["trend_ready"] = merged["trend_sma"].notna()
    merged["offensive_above_trend"] = (
        merged["trend_ready"] & (merged["adj_close"] > merged["trend_sma"])
    )

    signal_use_defensive = _create_confirmed_defensive_signal(
        above_trend=merged["offensive_above_trend"],
        trend_ready=merged["trend_ready"],
        confirmation_days=confirmation_days,
    )

    target_use_defensive = signal_use_defensive.shift(1).fillna(False)
    held_use_defensive = target_use_defensive.shift(1).fillna(False)

    target_defensive_weight = target_use_defensive.astype(float)
    target_offensive_weight = 1.0 - target_defensive_weight

    held_defensive_weight = held_use_defensive.astype(float)
    held_offensive_weight = 1.0 - held_defensive_weight

    overlay_turnover = (
        target_defensive_weight.diff().abs().fillna(target_defensive_weight.abs())
        + target_offensive_weight.diff().abs().fillna(target_offensive_weight.abs())
    )

    overlay_slippage_cost = overlay_turnover * (slippage_bps / 10_000.0)

    strategy_return = np.where(
        held_use_defensive,
        merged["strategy_return_defensive"],
        merged["strategy_return_offensive"],
    )
    strategy_return = pd.Series(strategy_return, index=merged.index).astype(float)
    strategy_return = strategy_return - overlay_slippage_cost
    strategy_return.iloc[0] = 0.0

    equity = initial_capital * (1.0 + strategy_return).cumprod()

    position = np.where(
        held_use_defensive,
        merged["position_defensive"],
        merged["position_offensive"],
    )
    cash_position = np.where(
        held_use_defensive,
        merged["cash_position_defensive"],
        merged["cash_position_offensive"],
    )

    underlying_turnover = np.where(
        held_use_defensive,
        merged["turnover_defensive"],
        merged["turnover_offensive"],
    )

    total_turnover = overlay_turnover + pd.Series(
        underlying_turnover,
        index=merged.index,
    ).astype(float)

    result = pd.DataFrame(
        {
            "date": merged["date"],
            "adj_close": equity.values,
            "strategy_return": strategy_return.values,
            "equity": equity.values,
            "position": position,
            "cash_position": cash_position,
            "turnover": total_turnover.values,
            "offensive_weight": held_offensive_weight.values,
            "defensive_weight": held_defensive_weight.values,
            "target_offensive_weight": target_offensive_weight.values,
            "target_defensive_weight": target_defensive_weight.values,
            "offensive_above_trend": merged["offensive_above_trend"].fillna(False).values,
            "trend_sma": merged["trend_sma"].values,
            "trend_ready": merged["trend_ready"].values,
            "confirmation_days": confirmation_days,
            "overlay_turnover": overlay_turnover.values,
            "overlay_slippage_cost": overlay_slippage_cost.values,
            "selected_mode": np.where(
                held_use_defensive,
                "defensive_allocator",
                "offensive_spy",
            ),
        }
    )

    numeric_columns = result.select_dtypes(include=[np.number]).columns

    for column in numeric_columns:
        result[column] = result[column].astype(float)

    return result.reset_index(drop=True)