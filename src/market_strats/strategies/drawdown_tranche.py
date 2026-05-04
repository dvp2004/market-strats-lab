from __future__ import annotations

import pandas as pd


def run_drawdown_tranche_strategy(
    prices: pd.DataFrame,
    initial_capital: float,
    base_allocation: float,
    tranche_allocation: float,
    drawdown_levels: list[float],
    slippage_bps: float,
) -> pd.DataFrame:
    """
    Drawdown tranche dip-buying strategy.

    Rule:
    - Hold a base allocation to the asset.
    - Keep the remaining capital in cash.
    - When the asset falls from its all-time high by predefined drawdown levels,
      deploy additional tranches into the asset.
    - As the asset recovers above those drawdown thresholds, reduce exposure again.

    Example:
    - Base allocation = 70%
    - Drawdown levels = 10%, 20%, 30%
    - Tranche allocation = 10%

    Then:
    - Drawdown less than 10%: hold 70%
    - Drawdown >= 10%: hold 80%
    - Drawdown >= 20%: hold 90%
    - Drawdown >= 30%: hold 100%

    The signal is generated using today's close.
    The target allocation is executed at the next trading day's close.
    The position affects returns from the day after execution.
    """
    if not 0 <= base_allocation <= 1:
        raise ValueError("base_allocation must be between 0 and 1")

    if not 0 <= tranche_allocation <= 1:
        raise ValueError("tranche_allocation must be between 0 and 1")

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

    running_high = daily_close.cummax()
    drawdown = (daily_close / running_high) - 1.0

    signal_target_position = pd.Series(base_allocation, index=df.index, dtype=float)

    for level in sorted_levels:
        signal_target_position += (drawdown <= -level).astype(float) * tranche_allocation

    signal_target_position = signal_target_position.clip(lower=0.0, upper=1.0)

    # Signal from today's close is executed at the next trading day's close.
    target_position = signal_target_position.shift(1).fillna(base_allocation)

    # Actual position used for returns. This lag avoids lookahead bias.
    held_position = target_position.shift(1).fillna(base_allocation)

    turnover = target_position.diff().abs().fillna(target_position.abs())
    slippage_cost = turnover * (slippage_bps / 10_000.0)

    strategy_return = (held_position * asset_return) - slippage_cost
    equity = initial_capital * (1.0 + strategy_return).cumprod()

    result = pd.DataFrame(
        {
            "date": df.index,
            "adj_close": daily_close.values,
            "strategy_return": strategy_return.values,
            "equity": equity.values,
            "position": held_position.values,
            "target_position": target_position.values,
            "drawdown_from_high": drawdown.values,
            "turnover": turnover.values,
        }
    )

    return result.reset_index(drop=True)