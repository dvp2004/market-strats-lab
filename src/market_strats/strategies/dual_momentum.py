from __future__ import annotations

import numpy as np
import pandas as pd


def run_dual_momentum_strategy(
    asset_a_prices: pd.DataFrame,
    asset_b_prices: pd.DataFrame,
    asset_a_name: str,
    asset_b_name: str,
    initial_capital: float,
    momentum_months: int,
    slippage_bps: float,
    cash_returns: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Dual momentum strategy.

    Rule:
    - At each month-end, calculate trailing N-month return for both assets.
    - Select the asset with stronger relative momentum.
    - Compare the winner's trailing return against trailing cash return.
    - If winner beats cash, hold the winner.
    - If winner does not beat cash, hold cash.
    - Execute at the next trading day's close.
    - Position affects returns from the following day.

    This tests relative momentum plus an absolute/cash filter.
    """
    if momentum_months <= 0:
        raise ValueError("momentum_months must be positive")

    asset_a = asset_a_prices.copy()
    asset_b = asset_b_prices.copy()

    asset_a["date"] = pd.to_datetime(asset_a["date"])
    asset_b["date"] = pd.to_datetime(asset_b["date"])

    asset_a = asset_a.sort_values("date")
    asset_b = asset_b.sort_values("date")

    df = pd.merge(
        asset_a[["date", "adj_close"]],
        asset_b[["date", "adj_close"]],
        on="date",
        how="inner",
        suffixes=(f"_{asset_a_name}", f"_{asset_b_name}"),
    )

    if df.empty:
        raise ValueError(
            f"No overlapping dates for {asset_a_name} and {asset_b_name}"
        )

    df = df.sort_values("date").reset_index(drop=True)
    df = df.set_index("date")

    close_a = df[f"adj_close_{asset_a_name}"]
    close_b = df[f"adj_close_{asset_b_name}"]

    return_a = close_a.pct_change().fillna(0.0)
    return_b = close_b.pct_change().fillna(0.0)

    if cash_returns is None:
        aligned_cash_returns = pd.Series(0.0, index=df.index)
    else:
        aligned_cash_returns = cash_returns.copy()
        aligned_cash_returns = aligned_cash_returns.astype(float)
        aligned_cash_returns = aligned_cash_returns.reindex(df.index).ffill().fillna(0.0)

    cash_index = (1.0 + aligned_cash_returns).cumprod()

    monthly_last_rows = df.groupby(df.index.to_period("M")).tail(1)
    monthly_close_a = monthly_last_rows[f"adj_close_{asset_a_name}"]
    monthly_close_b = monthly_last_rows[f"adj_close_{asset_b_name}"]
    monthly_cash_index = cash_index.reindex(monthly_last_rows.index)

    trailing_return_a = (monthly_close_a / monthly_close_a.shift(momentum_months)) - 1.0
    trailing_return_b = (monthly_close_b / monthly_close_b.shift(momentum_months)) - 1.0
    trailing_cash_return = (
        monthly_cash_index / monthly_cash_index.shift(momentum_months)
    ) - 1.0

    target_weight_a = pd.Series(np.nan, index=df.index, dtype=float)
    target_weight_b = pd.Series(np.nan, index=df.index, dtype=float)
    target_weight_a.iloc[0] = 0.0
    target_weight_b.iloc[0] = 0.0

    signal_selected_asset = pd.Series(index=df.index, dtype="object")
    signal_selected_asset.iloc[0] = "CASH"

    signal_dates = trailing_return_a.dropna().index.intersection(
        trailing_return_b.dropna().index
    )
    signal_dates = signal_dates.intersection(trailing_cash_return.dropna().index)

    for signal_date in signal_dates:
        asset_a_momentum = float(trailing_return_a.loc[signal_date])
        asset_b_momentum = float(trailing_return_b.loc[signal_date])
        cash_momentum = float(trailing_cash_return.loc[signal_date])

        if asset_a_momentum >= asset_b_momentum:
            winning_asset = asset_a_name
            winning_return = asset_a_momentum
        else:
            winning_asset = asset_b_name
            winning_return = asset_b_momentum

        if winning_return > cash_momentum:
            next_weight_a = 1.0 if winning_asset == asset_a_name else 0.0
            next_weight_b = 1.0 if winning_asset == asset_b_name else 0.0
            selected_asset = winning_asset
        else:
            next_weight_a = 0.0
            next_weight_b = 0.0
            selected_asset = "CASH"

        execution_index = df.index.searchsorted(signal_date, side="right")

        if execution_index < len(df.index):
            execution_date = df.index[execution_index]
            target_weight_a.loc[execution_date] = next_weight_a
            target_weight_b.loc[execution_date] = next_weight_b
            signal_selected_asset.loc[execution_date] = selected_asset

    target_weight_a = target_weight_a.ffill().fillna(0.0)
    target_weight_b = target_weight_b.ffill().fillna(0.0)
    target_selected_asset = signal_selected_asset.ffill().fillna("CASH")

    held_weight_a = target_weight_a.shift(1).fillna(0.0)
    held_weight_b = target_weight_b.shift(1).fillna(0.0)

    cash_position = 1.0 - held_weight_a - held_weight_b

    turnover = (
        target_weight_a.diff().abs().fillna(0.0)
        + target_weight_b.diff().abs().fillna(0.0)
    )

    slippage_cost = turnover * (slippage_bps / 10_000.0)

    strategy_return = (
        held_weight_a * return_a
        + held_weight_b * return_b
        + cash_position * aligned_cash_returns
        - slippage_cost
    )

    if not strategy_return.empty:
        strategy_return.iloc[0] = 0.0

    equity = initial_capital * (1.0 + strategy_return).cumprod()

    held_selected_asset = target_selected_asset.shift(1).fillna("CASH")

    result = pd.DataFrame(
        {
            "date": df.index,
            f"adj_close_{asset_a_name}": close_a.values,
            f"adj_close_{asset_b_name}": close_b.values,
            "strategy_return": strategy_return.values,
            "equity": equity.values,
            "position": (held_weight_a + held_weight_b).values,
            "cash_position": cash_position.values,
            f"weight_{asset_a_name}": held_weight_a.values,
            f"weight_{asset_b_name}": held_weight_b.values,
            f"target_weight_{asset_a_name}": target_weight_a.values,
            f"target_weight_{asset_b_name}": target_weight_b.values,
            "selected_asset": held_selected_asset.values,
            "target_selected_asset": target_selected_asset.values,
            "turnover": turnover.values,
        }
    )

    # For compatibility with generic plotting/metrics tools.
    result["adj_close"] = np.where(
        result[f"weight_{asset_a_name}"] > 0,
        result[f"adj_close_{asset_a_name}"],
        result[f"adj_close_{asset_b_name}"],
    )

    return result.reset_index(drop=True)