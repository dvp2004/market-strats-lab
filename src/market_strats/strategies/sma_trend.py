from __future__ import annotations

import numpy as np
import pandas as pd
from market_strats.strategies.accounting import calculate_allocation_strategy_returns

def run_sma_trend_strategy(
    prices: pd.DataFrame,
    initial_capital: float,
    sma_months: int,
    slippage_bps: float,
    cash_returns: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Monthly SMA trend strategy.

    Rule:
    - At each month-end, calculate whether adjusted close is above its SMA.
    - If above, target position = 1.
    - If below, target position = 0.
    - Execute at the next trading day's close.
    - Position affects returns from the following day.

    This is intentionally conservative to avoid lookahead bias.
    """
    df = prices.copy()
    df = df.sort_values("date").reset_index(drop=True)
    df = df.set_index("date")

    daily_close = df["adj_close"]

    monthly_last_rows = df.groupby(df.index.to_period("M")).tail(1)
    monthly_close = monthly_last_rows["adj_close"]

    sma = monthly_close.rolling(sma_months).mean()
    monthly_signal = (monthly_close > sma).astype(float)
    monthly_signal = monthly_signal.dropna()

    target_position = pd.Series(np.nan, index=df.index, dtype=float)
    target_position.iloc[0] = 0.0

    for signal_date, signal_value in monthly_signal.items():
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