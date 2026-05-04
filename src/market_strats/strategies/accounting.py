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
    """
    asset_return = asset_return.astype(float)
    held_position = held_position.astype(float)
    turnover = turnover.astype(float)

    if cash_returns is None:
        aligned_cash_returns = pd.Series(0.0, index=asset_return.index)
    else:
        aligned_cash_returns = cash_returns.copy()
        aligned_cash_returns.index = asset_return.index
        aligned_cash_returns = aligned_cash_returns.astype(float).fillna(0.0)

    cash_position = 1.0 - held_position
    slippage_cost = turnover * (slippage_bps / 10_000.0)

    return (
        held_position * asset_return
        + cash_position * aligned_cash_returns
        - slippage_cost
    )