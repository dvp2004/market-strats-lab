from __future__ import annotations

import numpy as np
import pandas as pd


def _prepare_price_frame(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    required_columns = {"date", "adj_close"}
    missing_columns = required_columns - set(prices.columns)

    if missing_columns:
        raise ValueError(f"{ticker} prices missing columns: {sorted(missing_columns)}")

    df = prices.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df[["date", "adj_close"]].dropna()
    df = df.set_index("date")
    df["adj_close"] = df["adj_close"].astype(float)

    if df.empty:
        raise ValueError(f"{ticker} has no usable price rows")

    return df


def create_price_panel(
    price_data_by_ticker: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    if not price_data_by_ticker:
        raise ValueError("price_data_by_ticker cannot be empty")

    series_by_ticker = {}

    for ticker, prices in price_data_by_ticker.items():
        prepared = _prepare_price_frame(prices, ticker)
        series_by_ticker[ticker.upper()] = prepared["adj_close"]

    panel = pd.DataFrame(series_by_ticker)
    panel = panel.dropna(how="any")
    panel = panel.sort_index()

    if panel.empty:
        raise ValueError("No common price dates across relative momentum universe")

    return panel


def _align_cash_returns(
    cash_returns: pd.Series | None,
    index: pd.DatetimeIndex,
) -> pd.Series:
    if cash_returns is None:
        return pd.Series(0.0, index=index)

    aligned = cash_returns.copy()
    aligned.index = pd.to_datetime(aligned.index)
    aligned = aligned.sort_index()
    aligned = aligned.reindex(index).ffill().fillna(0.0)
    return aligned.astype(float)


def _safe_selected_assets(weights: pd.Series) -> str:
    selected = weights[weights > 0.000001].index.tolist()
    return ",".join(selected)


def _calculate_selected_weights(
    selected: list[str],
    top_n: int,
    weighting: str,
    volatility_row: pd.Series | None = None,
) -> dict[str, float]:
    if not selected:
        return {}

    risk_budget = len(selected) / top_n

    if weighting == "equal":
        equal_weight = risk_budget / len(selected)
        return {ticker: equal_weight for ticker in selected}

    if weighting != "inverse_volatility":
        raise ValueError(
            "weighting must be one of: 'equal', 'inverse_volatility'"
        )

    if volatility_row is None:
        equal_weight = risk_budget / len(selected)
        return {ticker: equal_weight for ticker in selected}

    selected_volatility = volatility_row[selected].astype(float)
    selected_volatility = selected_volatility.replace([np.inf, -np.inf], np.nan)

    if selected_volatility.isna().any() or (selected_volatility <= 0).any():
        equal_weight = risk_budget / len(selected)
        return {ticker: equal_weight for ticker in selected}

    inverse_volatility = 1.0 / selected_volatility
    weights = inverse_volatility / inverse_volatility.sum()
    weights = weights * risk_budget

    return weights.to_dict()

def run_relative_momentum_allocator(
    price_data_by_ticker: dict[str, pd.DataFrame],
    initial_capital: float,
    lookback_months: int,
    top_n: int,
    slippage_bps: float,
    min_momentum: float = 0.0,
    cash_returns: pd.Series | None = None,
    weighting: str = "equal",
    volatility_lookback_days: int = 63,
    trend_filter_enabled: bool = False,
    trend_sma_days: int = 200,
) -> pd.DataFrame:
    """
    Monthly top-N relative momentum allocator.

    Rule:
    - At each month-end, calculate trailing N-month return for each asset.
    - Keep assets with return greater than min_momentum.
    - Select the top-N eligible assets by return.
    - Each selected asset receives 1 / top_n weight.
    - If fewer than top_n assets qualify, unused capital remains in cash.
    - Execute on the next trading day.
    - Position affects returns from the day after execution.

    This is a tactical asset allocation baseline, not a prediction model.
    """
    if lookback_months <= 0:
        raise ValueError("lookback_months must be positive")

    if top_n <= 0:
        raise ValueError("top_n must be positive")

    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")

    close_panel = create_price_panel(price_data_by_ticker)

    if top_n > len(close_panel.columns):
        raise ValueError("top_n cannot exceed number of assets")

    asset_returns = close_panel.pct_change().fillna(0.0)

    if volatility_lookback_days <= 0:
        raise ValueError("volatility_lookback_days must be positive")

    rolling_volatility = asset_returns.rolling(volatility_lookback_days).std()

    if trend_sma_days <= 0:
        raise ValueError("trend_sma_days must be positive")

    if trend_filter_enabled:
        trend_sma = close_panel.rolling(trend_sma_days).mean()
    else:
        trend_sma = None

    monthly_last_dates = close_panel.groupby(close_panel.index.to_period("M")).tail(1)
    monthly_close = monthly_last_dates.copy()

    trailing_returns = (monthly_close / monthly_close.shift(lookback_months)) - 1.0

    target_weights = pd.DataFrame(
        np.nan,
        index=close_panel.index,
        columns=close_panel.columns,
    )
    target_weights.iloc[0] = 0.0

    for signal_date, momentum_row in trailing_returns.dropna(how="all").iterrows():
        execution_index = close_panel.index.searchsorted(signal_date, side="right")

        if execution_index >= len(close_panel.index):
            continue

        eligible = momentum_row.dropna()
        eligible = eligible[eligible > min_momentum]

        if trend_filter_enabled and trend_sma is not None:
            price_row = close_panel.loc[signal_date]
            sma_row = trend_sma.loc[signal_date]

            trend_confirmed = price_row > sma_row
            trend_confirmed = trend_confirmed.fillna(False)

            eligible = eligible[
                eligible.index.isin(
                    trend_confirmed[trend_confirmed].index
                )
            ]

        selected = eligible.sort_values(ascending=False).head(top_n).index.tolist()

        execution_date = close_panel.index[execution_index]
        target_weights.loc[execution_date] = 0.0

        selected_weights = _calculate_selected_weights(
            selected=selected,
            top_n=top_n,
            weighting=weighting,
            volatility_row=rolling_volatility.loc[signal_date],
        )

        for ticker, weight in selected_weights.items():
            target_weights.loc[execution_date, ticker] = weight

    target_weights = target_weights.ffill().fillna(0.0)

    held_weights = target_weights.shift(1).fillna(0.0)

    portfolio_asset_return = (held_weights * asset_returns).sum(axis=1)
    risky_weight = held_weights.sum(axis=1).clip(lower=0.0, upper=1.0)
    cash_weight = 1.0 - risky_weight

    aligned_cash_returns = _align_cash_returns(cash_returns, close_panel.index)

    turnover = target_weights.diff().abs().sum(axis=1)
    turnover = turnover.fillna(target_weights.abs().sum(axis=1))

    slippage_cost = turnover * (slippage_bps / 10_000.0)

    strategy_return = (
        portfolio_asset_return
        + cash_weight * aligned_cash_returns
        - slippage_cost
    )
    strategy_return.iloc[0] = 0.0

    equity = initial_capital * (1.0 + strategy_return).cumprod()

    result = pd.DataFrame(
        {
            "date": close_panel.index,
            "adj_close": equity.values,
            "strategy_return": strategy_return.values,
            "equity": equity.values,
            "position": risky_weight.values,
            "cash_position": cash_weight.values,
            "turnover": turnover.values,
            "selected_assets": [
                _safe_selected_assets(row) for _, row in held_weights.iterrows()
            ],
        }
    )

    for ticker in close_panel.columns:
        result[f"{ticker}_weight"] = held_weights[ticker].values
        result[f"{ticker}_target_weight"] = target_weights[ticker].values
        result[f"{ticker}_return"] = asset_returns[ticker].values

    result["cash_return"] = aligned_cash_returns.values
    result["portfolio_asset_return"] = portfolio_asset_return.values
    result["slippage_cost"] = slippage_cost.values
    result["weighting"] = weighting
    result["volatility_lookback_days"] = volatility_lookback_days
    result["trend_filter_enabled"] = trend_filter_enabled
    result["trend_sma_days"] = trend_sma_days

    numeric_columns = result.select_dtypes(include=[np.number]).columns

    for column in numeric_columns:
        result[column] = result[column].astype(float)

    return result.reset_index(drop=True)