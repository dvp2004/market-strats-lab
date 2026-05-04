from __future__ import annotations

import pandas as pd


def calculate_allocation_strategy_returns(
    asset_return: pd.Series,
    held_position: pd.Series,
    turnover: pd.Series,
    slippage_bps: float,
    cash_returns: pd.Series | None = None,
) -> pd.Series:
    """
    Calculate strategy returns for long-only allocation strategies.

    position = percentage allocated to the risky asset
    1 - position = percentage allocated to cash

    If cash_returns is None, cash return is assumed to be 0.

    The first return is forced to 0 so every backtest starts exactly at
    initial_capital. This avoids first-row cash yield or initial slippage
    distorting the reported start value.
    """
    asset_return = asset_return.astype(float)
    index = asset_return.index

    held_position = held_position.reindex(index).astype(float).fillna(0.0)
    turnover = turnover.reindex(index).astype(float).fillna(0.0)

    if cash_returns is None:
        aligned_cash_returns = pd.Series(0.0, index=index)
    else:
        aligned_cash_returns = cash_returns.copy()
        aligned_cash_returns = aligned_cash_returns.astype(float)
        aligned_cash_returns = aligned_cash_returns.reindex(index).ffill().fillna(0.0)

    cash_position = 1.0 - held_position
    slippage_cost = turnover * (slippage_bps / 10_000.0)

    strategy_return = (
        held_position * asset_return
        + cash_position * aligned_cash_returns
        - slippage_cost
    )

    if not strategy_return.empty:
        strategy_return.iloc[0] = 0.0

    return strategy_return