from __future__ import annotations

import math

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def calculate_drawdown(equity: pd.Series) -> pd.Series:
    running_max = equity.cummax()
    return (equity / running_max) - 1.0


def calculate_metrics(result: pd.DataFrame, strategy_name: str) -> dict[str, float | str]:
    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    equity = df["equity"]
    returns = df["strategy_return"]

    start_value = float(equity.iloc[0])
    end_value = float(equity.iloc[-1])
    total_return = (end_value / start_value) - 1.0

    start_date = df["date"].iloc[0]
    end_date = df["date"].iloc[-1]
    years = max((end_date - start_date).days / 365.25, 1 / 365.25)

    cagr = (end_value / start_value) ** (1.0 / years) - 1.0

    volatility = returns.std(ddof=0) * math.sqrt(TRADING_DAYS_PER_YEAR)

    if returns.std(ddof=0) == 0:
        sharpe = np.nan
    else:
        sharpe = (returns.mean() / returns.std(ddof=0)) * math.sqrt(TRADING_DAYS_PER_YEAR)

    downside_returns = returns[returns < 0]

    if downside_returns.std(ddof=0) == 0:
        sortino = np.nan
    else:
        sortino = (returns.mean() / downside_returns.std(ddof=0)) * math.sqrt(TRADING_DAYS_PER_YEAR)

    drawdown = calculate_drawdown(equity)
    max_drawdown = float(drawdown.min())

    monthly_equity = df.set_index("date")["equity"].resample("ME").last()
    monthly_returns = monthly_equity.pct_change().dropna()

    worst_month = float(monthly_returns.min()) if not monthly_returns.empty else np.nan
    best_month = float(monthly_returns.max()) if not monthly_returns.empty else np.nan

    exposure_time = float(df["position"].mean()) if "position" in df.columns else np.nan
    total_turnover = float(df["turnover"].sum()) if "turnover" in df.columns else np.nan
    trade_count = int((df["turnover"] > 0).sum()) if "turnover" in df.columns else 0

    time_underwater = float((drawdown < 0).mean())

    return {
        "strategy": strategy_name,
        "start_date": str(start_date.date()),
        "end_date": str(end_date.date()),
        "start_value": round(start_value, 2),
        "end_value": round(end_value, 2),
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "volatility_pct": round(volatility * 100, 2),
        "sharpe": round(float(sharpe), 3) if not np.isnan(sharpe) else np.nan,
        "sortino": round(float(sortino), 3) if not np.isnan(sortino) else np.nan,
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "best_month_pct": round(best_month * 100, 2) if not np.isnan(best_month) else np.nan,
        "worst_month_pct": round(worst_month * 100, 2) if not np.isnan(worst_month) else np.nan,
        "exposure_time_pct": round(exposure_time * 100, 2),
        "total_turnover": round(total_turnover, 2),
        "trade_count": trade_count,
        "time_underwater_pct": round(time_underwater * 100, 2),
    }