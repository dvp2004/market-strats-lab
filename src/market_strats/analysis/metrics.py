from __future__ import annotations

import math

import numpy as np
import pandas as pd


def infer_periods_per_year(result: pd.DataFrame) -> float:
    """
    Infer observations per year from the date column.

    ETF data usually has roughly 252 observations per year.
    Crypto data can have roughly 365 observations per year.

    This avoids using ETF annualisation assumptions for BTC-USD.
    """
    if result.empty or "date" not in result.columns:
        return 252.0

    dates = pd.to_datetime(result["date"]).sort_values().reset_index(drop=True)

    if len(dates) < 2:
        return 252.0

    elapsed_years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25

    if elapsed_years <= 0:
        return 252.0

    periods_per_year = len(dates) / elapsed_years

    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        return 252.0

    return float(periods_per_year)


def calculate_drawdown(equity: pd.Series) -> pd.Series:
    equity = equity.astype(float)
    running_max = equity.cummax()

    return (equity / running_max) - 1.0


def _calculate_cagr(start_value: float, end_value: float, years: float) -> float:
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return 0.0

    return (end_value / start_value) ** (1.0 / years) - 1.0


def _calculate_sharpe(
    strategy_returns: pd.Series,
    periods_per_year: float,
) -> float:
    returns = strategy_returns.astype(float)

    if returns.empty:
        return 0.0

    volatility = returns.std(ddof=1) * math.sqrt(periods_per_year)

    if volatility == 0 or not np.isfinite(volatility):
        return 0.0

    annualised_return = returns.mean() * periods_per_year

    return float(annualised_return / volatility)


def _calculate_sortino(
    strategy_returns: pd.Series,
    periods_per_year: float,
) -> float:
    returns = strategy_returns.astype(float)

    if returns.empty:
        return 0.0

    downside_returns = returns[returns < 0]

    if downside_returns.empty:
        return 0.0

    downside_deviation = downside_returns.std(ddof=1) * math.sqrt(periods_per_year)

    if downside_deviation == 0 or not np.isfinite(downside_deviation):
        return 0.0

    annualised_return = returns.mean() * periods_per_year

    return float(annualised_return / downside_deviation)


def calculate_metrics(result: pd.DataFrame, strategy_name: str) -> dict:
    """
    Calculate performance metrics for a strategy result.

    The annualisation factor is inferred from the date frequency, which matters
    when comparing ETF data with 7-day crypto data.
    """
    if result.empty:
        raise ValueError("result cannot be empty")

    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    required_columns = {"date", "equity", "strategy_return", "position", "turnover"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    start_date = df["date"].iloc[0]
    end_date = df["date"].iloc[-1]

    start_value = float(df["equity"].iloc[0])
    end_value = float(df["equity"].iloc[-1])

    elapsed_years = (end_date - start_date).days / 365.25
    total_return = (end_value / start_value) - 1.0 if start_value != 0 else 0.0
    cagr = _calculate_cagr(start_value, end_value, elapsed_years)

    strategy_returns = df["strategy_return"].astype(float)
    periods_per_year = infer_periods_per_year(df)

    volatility = strategy_returns.std(ddof=1) * math.sqrt(periods_per_year)
    sharpe = _calculate_sharpe(strategy_returns, periods_per_year)
    sortino = _calculate_sortino(strategy_returns, periods_per_year)

    drawdown = calculate_drawdown(df["equity"])
    max_drawdown = float(drawdown.min())

    monthly_equity = df.set_index("date")["equity"].resample("ME").last()
    monthly_returns = monthly_equity.pct_change().dropna()

    best_month = float(monthly_returns.max()) if not monthly_returns.empty else 0.0
    worst_month = float(monthly_returns.min()) if not monthly_returns.empty else 0.0

    exposure_time = float(df["position"].astype(float).mean())
    total_turnover = float(df["turnover"].astype(float).sum())
    trade_count = int((df["turnover"].astype(float) > 0).sum())
    time_underwater = float((drawdown < 0).mean())

    return {
        "strategy": strategy_name,
        "start_date": start_date.date().isoformat(),
        "end_date": end_date.date().isoformat(),
        "start_value": round(start_value, 2),
        "end_value": round(end_value, 2),
        "total_return_pct": round(total_return * 100.0, 2),
        "cagr_pct": round(cagr * 100.0, 2),
        "volatility_pct": round(volatility * 100.0, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_drawdown_pct": round(max_drawdown * 100.0, 2),
        "best_month_pct": round(best_month * 100.0, 2),
        "worst_month_pct": round(worst_month * 100.0, 2),
        "exposure_time_pct": round(exposure_time * 100.0, 2),
        "total_turnover": round(total_turnover, 2),
        "trade_count": trade_count,
        "time_underwater_pct": round(time_underwater * 100.0, 2),
    }