from __future__ import annotations

import numpy as np
import pandas as pd
from market_strats.strategies.accounting import calculate_allocation_strategy_returns

def run_trend_filtered_drawdown_strategy(
    prices: pd.DataFrame,
    initial_capital: float,
    base_allocation: float,
    tranche_allocation: float,
    drawdown_levels: list[float],
    momentum_months: int,
    trend_off_allocation: float,
    slippage_bps: float,
    cash_returns: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Trend-filtered drawdown tranche strategy.

    Rule:
    - Calculate 12-month absolute momentum at each month-end.
    - If momentum is positive, the strategy is allowed to hold SPY.
    - If momentum is negative or unavailable, the strategy moves to the defensive/off allocation.
    - While trend is positive:
        - hold base allocation;
        - add tranches when SPY falls from its all-time high by defined drawdown levels.
    - While trend is negative:
        - do not add drawdown tranches;
        - hold trend_off_allocation.

    Example:
    - base_allocation = 70%
    - drawdown levels = 10%, 20%, 30%
    - tranche_allocation = 10%
    - trend_off_allocation = 0%

    Then, if 12-month momentum is positive:
    - drawdown < 10%: hold 70%
    - drawdown >= 10%: hold 80%
    - drawdown >= 20%: hold 90%
    - drawdown >= 30%: hold 100%

    If 12-month momentum is negative:
    - hold 0%, regardless of drawdown.

    Signal uses today's close.
    Trade executes at the next trading day's close.
    Position affects returns from the day after execution.
    """
    if not 0 <= base_allocation <= 1:
        raise ValueError("base_allocation must be between 0 and 1")

    if not 0 <= tranche_allocation <= 1:
        raise ValueError("tranche_allocation must be between 0 and 1")

    if not 0 <= trend_off_allocation <= 1:
        raise ValueError("trend_off_allocation must be between 0 and 1")

    if momentum_months <= 0:
        raise ValueError("momentum_months must be positive")

    if not drawdown_levels:
        raise ValueError("drawdown_levels cannot be empty")

    sorted_levels = sorted(drawdown_levels)

    if any(level <= 0 or level >= 1 for level in sorted_levels):
        raise ValueError("drawdown_levels must be between 0 and 1")

    max_possible_allocation = base_allocation + (len(sorted_levels) * tranche_allocation)

    if max_possible_allocation > 1.0000001:
        raise ValueError(
            "base_allocation + number of tranches * tranche_allocation cannot exceed 1"
        )

    df = prices.copy()
    df = df.sort_values("date").reset_index(drop=True)
    df = df.set_index("date")

    daily_close = df["adj_close"]
    asset_return = daily_close.pct_change().fillna(0.0)

    # 1. Monthly absolute momentum filter.
    monthly_last_rows = df.groupby(df.index.to_period("M")).tail(1)
    monthly_close = monthly_last_rows["adj_close"]

    trailing_return = (monthly_close / monthly_close.shift(momentum_months)) - 1.0
    monthly_trend_signal = (trailing_return > 0).astype(float).dropna()

    trend_signal_daily = pd.Series(np.nan, index=df.index, dtype=float)
    trend_signal_daily.iloc[0] = 0.0

    for signal_date, signal_value in monthly_trend_signal.items():
        trend_signal_daily.loc[signal_date] = float(signal_value)

    trend_signal_daily = trend_signal_daily.ffill().fillna(0.0)

    # 2. Drawdown tranche exposure, only used when trend is positive.
    running_high = daily_close.cummax()
    drawdown = (daily_close / running_high) - 1.0

    risk_on_position = pd.Series(base_allocation, index=df.index, dtype=float)

    for level in sorted_levels:
        risk_on_position += (drawdown <= -level).astype(float) * tranche_allocation

    risk_on_position = risk_on_position.clip(lower=0.0, upper=1.0)

    signal_target_position = pd.Series(
        np.where(trend_signal_daily > 0, risk_on_position, trend_off_allocation),
        index=df.index,
        dtype=float,
    )

    # Signal from today's close is executed at the next trading day's close.
    target_position = signal_target_position.shift(1).fillna(trend_off_allocation)

    # Actual held exposure affects returns from the day after execution.
    held_position = target_position.shift(1).fillna(trend_off_allocation)

    turnover = target_position.diff().abs().fillna(target_position.abs())
    strategy_return = calculate_allocation_strategy_returns(
        asset_return=asset_return,
        held_position=held_position,
        turnover=turnover,
        slippage_bps=slippage_bps,
        cash_returns=cash_returns,
    )
    equity = initial_capital * (1.0 + strategy_return).cumprod()

    result = pd.DataFrame(
        {
            "date": df.index,
            "adj_close": daily_close.values,
            "strategy_return": strategy_return.values,
            "equity": equity.values,
            "position": held_position.values,
            "cash_position": (1.0 - held_position).values,
            "target_position": target_position.values,
            "trend_signal": trend_signal_daily.values,
            "drawdown_from_high": drawdown.values,
            "turnover": turnover.values,
        }
    )

    return result.reset_index(drop=True)