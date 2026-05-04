from __future__ import annotations

import numpy as np
import pandas as pd
from market_strats.strategies.accounting import calculate_allocation_strategy_returns

def run_daily_sma_trend_strategy(
    prices: pd.DataFrame,
    initial_capital: float,
    sma_days: int,
    slippage_bps: float,
    cash_returns: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Daily SMA trend strategy.

    Rule:
    - Calculate the daily adjusted close against its N-day SMA.
    - If adjusted close is above the SMA, target position = 1.
    - If adjusted close is below or equal to the SMA, target position = 0.
    - Signal is generated using today's close.
    - Trade is executed at the next trading day's close.
    - Position affects returns from the day after execution.

    This is deliberately conservative to avoid lookahead bias.
    """
    df = prices.copy()
    df = df.sort_values("date").reset_index(drop=True)
    df = df.set_index("date")

    daily_close = df["adj_close"]
    sma = daily_close.rolling(sma_days).mean()

    daily_signal = pd.Series(np.nan, index=df.index, dtype=float)
    valid_signal_mask = sma.notna()
    daily_signal.loc[valid_signal_mask] = (
        daily_close.loc[valid_signal_mask] > sma.loc[valid_signal_mask]
    ).astype(float)

    target_position = pd.Series(np.nan, index=df.index, dtype=float)
    target_position.iloc[0] = 0.0

    for signal_date, signal_value in daily_signal.dropna().items():
        execution_index = df.index.searchsorted(signal_date, side="right")

        if execution_index < len(df.index):
            target_position.iloc[execution_index] = float(signal_value)

    target_position = target_position.ffill().fillna(0.0)

    asset_return = daily_close.pct_change().fillna(0.0)

    # Actual position used for returns. This lag avoids lookahead bias.
    held_position = target_position.shift(1).fillna(0.0)

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
            "turnover": turnover.values,
        }
    )

    return result.reset_index(drop=True)