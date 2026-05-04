from __future__ import annotations

import pandas as pd


def run_buy_and_hold(
    prices: pd.DataFrame,
    initial_capital: float,
    cash_returns: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Buy SPY at the start and hold until the end.

    Uses adjusted close returns. Cash returns do not affect this strategy
    because it is fully invested.
    """
    df = prices.copy()
    df["asset_return"] = df["adj_close"].pct_change().fillna(0.0)
    df["strategy_return"] = df["asset_return"]
    df["equity"] = initial_capital * (1.0 + df["strategy_return"]).cumprod()
    df["position"] = 1.0
    df["cash_position"] = 0.0
    df["turnover"] = 0.0
    df.loc[df.index[0], "turnover"] = 1.0

    return df[
        [
            "date",
            "adj_close",
            "strategy_return",
            "equity",
            "position",
            "cash_position",
            "turnover",
        ]
    ]