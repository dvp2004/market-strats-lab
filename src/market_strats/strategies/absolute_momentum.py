from __future__ import annotations

import numpy as np
import pandas as pd
from market_strats.strategies.accounting import calculate_allocation_strategy_returns

def run_absolute_momentum_strategy(
    prices: pd.DataFrame,
    initial_capital: float,
    momentum_months: int,
    slippage_bps: float,
    cash_returns: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Monthly absolute momentum strategy.

    Rule:
    - At each month-end, calculate trailing N-month return.
    - If trailing return is positive, target position = 1.
    - If trailing return is zero or negative, target position = 0.
    - Execute at the next trading day's close.
    - Position affects returns from the following day.

    This tests whether positive medium-term momentum is useful as a simple market-timing signal.
    """
    df = prices.copy()
    df = df.sort_values("date").reset_index(drop=True)
    df = df.set_index("date")

    daily_close = df["adj_close"]

    monthly_last_rows = df.groupby(df.index.to_period("M")).tail(1)
    monthly_close = monthly_last_rows["adj_close"]

    trailing_return = (monthly_close / monthly_close.shift(momentum_months)) - 1.0
    monthly_signal = (trailing_return > 0).astype(float)
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