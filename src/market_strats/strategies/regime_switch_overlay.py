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

def _apply_defensive_entry_guard(
    signal_use_defensive: pd.Series,
    defensive_entry_allowed: pd.Series | None,
) -> pd.Series:
    if defensive_entry_allowed is None:
        return signal_use_defensive.astype(bool)

    desired_state = signal_use_defensive.astype(bool).reset_index(drop=True)
    entry_allowed = defensive_entry_allowed.astype(bool).reset_index(drop=True)

    if len(desired_state) != len(entry_allowed):
        raise ValueError(
            "defensive_entry_allowed must have the same length as signal_use_defensive"
        )

    guarded_states: list[bool] = []
    current_defensive_state = False

    for desired_defensive, allowed in zip(
        desired_state,
        entry_allowed,
        strict=True,
    ):
        if not current_defensive_state and desired_defensive:
            current_defensive_state = bool(allowed)
        elif current_defensive_state and not desired_defensive:
            current_defensive_state = False

        guarded_states.append(current_defensive_state)

    return pd.Series(guarded_states, index=signal_use_defensive.index)

def _align_optional_guard_series(
    guard: pd.Series | None,
    dates: pd.Series,
    default_value: bool,
    guard_name: str,
) -> pd.Series:
    if guard is None:
        return pd.Series(default_value, index=range(len(dates)))

    aligned = guard.copy()
    aligned.index = pd.to_datetime(aligned.index)

    aligned = (
        aligned.reindex(pd.to_datetime(dates))
        .ffill()
        .bfill()
        .reset_index(drop=True)
        .astype(bool)
    )

    if aligned.isna().any():
        raise ValueError(f"{guard_name} could not be aligned to overlay dates")

    return aligned


def _apply_switch_guards(
    signal_use_defensive: pd.Series,
    defensive_entry_allowed: pd.Series | None = None,
    offensive_entry_allowed: pd.Series | None = None,
) -> pd.Series:
    desired_state = signal_use_defensive.astype(bool).reset_index(drop=True)

    defensive_allowed = (
        defensive_entry_allowed.astype(bool).reset_index(drop=True)
        if defensive_entry_allowed is not None
        else pd.Series(True, index=desired_state.index)
    )
    offensive_allowed = (
        offensive_entry_allowed.astype(bool).reset_index(drop=True)
        if offensive_entry_allowed is not None
        else pd.Series(True, index=desired_state.index)
    )

    if len(desired_state) != len(defensive_allowed):
        raise ValueError(
            "defensive_entry_allowed must have the same length as signal_use_defensive"
        )

    if len(desired_state) != len(offensive_allowed):
        raise ValueError(
            "offensive_entry_allowed must have the same length as signal_use_defensive"
        )

    guarded_states: list[bool] = []
    current_defensive_state = False

    for desired_defensive, defensive_ok, offensive_ok in zip(
        desired_state,
        defensive_allowed,
        offensive_allowed,
        strict=True,
    ):
        if not current_defensive_state and desired_defensive:
            current_defensive_state = bool(defensive_ok)
        elif current_defensive_state and not desired_defensive:
            current_defensive_state = not bool(offensive_ok)

        guarded_states.append(current_defensive_state)

    return pd.Series(guarded_states, index=signal_use_defensive.index)

def run_spy_trend_regime_switch_overlay(
    offensive_result: pd.DataFrame,
    defensive_result: pd.DataFrame,
    initial_capital: float,
    trend_sma_days: int,
    slippage_bps: float,
    confirmation_days: int = 1,
    signal_price_column: str = "adj_close",
    dynamic_slippage_bps: pd.Series | None = None,
    defensive_entry_allowed: pd.Series | None = None,
    defensive_entry_guard_name: str = "none",
    offensive_entry_allowed: pd.Series | None = None,
    offensive_entry_guard_name: str = "none",
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

    if signal_price_column not in offensive.columns:
        raise ValueError(
            f"signal_price_column '{signal_price_column}' not found in offensive "
            f"result. Available columns: {sorted(offensive.columns)}"
        )

    offensive["signal_price"] = offensive[signal_price_column].astype(float)

    merged = offensive[
        [
            "date",
            "adj_close",
            "signal_price",
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

    merged["trend_sma"] = merged["signal_price"].rolling(trend_sma_days).mean()
    merged["trend_ready"] = merged["trend_sma"].notna()
    merged["offensive_above_trend"] = (
        merged["trend_ready"] & (merged["signal_price"] > merged["trend_sma"])
    )

    raw_signal_use_defensive = _create_confirmed_defensive_signal(
        above_trend=merged["offensive_above_trend"],
        trend_ready=merged["trend_ready"],
        confirmation_days=confirmation_days,
    )

    aligned_defensive_entry_allowed = _align_optional_guard_series(
        guard=defensive_entry_allowed,
        dates=merged["date"],
        default_value=True,
        guard_name="defensive_entry_allowed",
    )

    aligned_offensive_entry_allowed = _align_optional_guard_series(
        guard=offensive_entry_allowed,
        dates=merged["date"],
        default_value=True,
        guard_name="offensive_entry_allowed",
    )

    signal_use_defensive = _apply_switch_guards(
        signal_use_defensive=raw_signal_use_defensive,
        defensive_entry_allowed=aligned_defensive_entry_allowed,
        offensive_entry_allowed=aligned_offensive_entry_allowed,
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

    if dynamic_slippage_bps is None:
        applied_overlay_slippage_bps = pd.Series(
            float(slippage_bps),
            index=merged.index,
        )
    else:
        applied_overlay_slippage_bps = dynamic_slippage_bps.copy()
        applied_overlay_slippage_bps.index = pd.to_datetime(
            applied_overlay_slippage_bps.index
        )
        applied_overlay_slippage_bps = (
            applied_overlay_slippage_bps.reindex(pd.to_datetime(merged["date"]))
            .ffill()
            .bfill()
            .reset_index(drop=True)
            .astype(float)
        )

        if applied_overlay_slippage_bps.isna().any():
            raise ValueError("dynamic_slippage_bps could not be aligned to overlay dates")

    overlay_slippage_cost = overlay_turnover * (
        applied_overlay_slippage_bps / 10_000.0
    )

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
            "raw_signal_use_defensive": raw_signal_use_defensive.values,
            "guarded_signal_use_defensive": signal_use_defensive.values,
            "defensive_entry_allowed": aligned_defensive_entry_allowed.values,
            "defensive_entry_guard_name": defensive_entry_guard_name,
            "offensive_entry_allowed": aligned_offensive_entry_allowed.values,
            "offensive_entry_guard_name": offensive_entry_guard_name,
            "signal_price": merged["signal_price"].values,
            "signal_price_column": signal_price_column,
            "trend_sma": merged["trend_sma"].values,
            "trend_ready": merged["trend_ready"].values,
            "confirmation_days": confirmation_days,
            "overlay_turnover": overlay_turnover.values,
            "overlay_slippage_cost": overlay_slippage_cost.values,
            "applied_overlay_slippage_bps": applied_overlay_slippage_bps.values,
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