from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import os
from typing import Dict

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"
OUT_DIR = REPO_ROOT / "paper_bot_logs"
OUT_DIR.mkdir(exist_ok=True)

load_dotenv(dotenv_path=ENV_PATH)


SYMBOLS = ["SPY", "QQQ", "IWM", "GLD", "TLT"]
START_DATE = os.getenv("BACKTEST_START", "2018-01-01")
END_DATE = os.getenv("BACKTEST_END", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

INITIAL_CAPITAL = 100_000.0
TRANSACTION_COST_BPS = 2.0


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def safety_checks() -> None:
    base_url = require_env("APCA_API_BASE_URL")
    bot_mode = require_env("BOT_MODE")

    if base_url != "https://paper-api.alpaca.markets":
        raise RuntimeError(f"Refusing to run: unsafe Alpaca endpoint: {base_url}")

    if bot_mode != "paper":
        raise RuntimeError(f"Refusing to run: BOT_MODE must be paper, got: {bot_mode}")

    print("Safety checks passed: paper config only. This script places zero orders.")


def fetch_close_prices() -> pd.DataFrame:
    client = StockHistoricalDataClient(
        api_key=require_env("APCA_API_KEY_ID"),
        secret_key=require_env("APCA_API_SECRET_KEY"),
    )

    request = StockBarsRequest(
        symbol_or_symbols=SYMBOLS,
        timeframe=TimeFrame.Day,
        start=pd.Timestamp(START_DATE, tz="UTC").to_pydatetime(),
        end=pd.Timestamp(END_DATE, tz="UTC").to_pydatetime(),
        feed=DataFeed.IEX,
    )

    bars = client.get_stock_bars(request).df

    if bars.empty:
        raise RuntimeError("No historical bars returned from Alpaca.")

    if not isinstance(bars.index, pd.MultiIndex):
        raise RuntimeError("Unexpected bars format. Expected MultiIndex with symbol/timestamp.")

    closes = {}

    for symbol in SYMBOLS:
        if symbol not in bars.index.get_level_values(0):
            print(f"Warning: missing symbol from Alpaca data: {symbol}")
            continue

        df = bars.loc[symbol].copy().sort_index()
        closes[symbol] = df["close"]

    close = pd.DataFrame(closes).sort_index()
    close.index = pd.to_datetime(close.index)
    close = close.dropna(how="all").ffill().dropna()

    missing = [s for s in SYMBOLS if s not in close.columns]
    if missing:
        raise RuntimeError(f"Missing required symbols after fetch: {missing}")

    return close


def empty_weights(close: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(0.0, index=close.index, columns=close.columns)


def strategy_spy_buy_hold(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)
    w["SPY"] = 1.0
    return w


def strategy_equal_weight(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)
    for symbol in SYMBOLS:
        w[symbol] = 1.0 / len(SYMBOLS)
    return w


def strategy_spy_200dma_risk_switch(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)

    spy = close["SPY"]
    sma200 = spy.rolling(200).mean()

    # yesterday's signal, today's return: avoids lookahead
    risk_on = (spy > sma200).shift(1).fillna(False).astype(bool)
    risk_off = ~risk_on

    w.loc[risk_on, "SPY"] = 0.70
    w.loc[risk_on, "QQQ"] = 0.30

    w.loc[risk_off, "TLT"] = 0.50
    w.loc[risk_off, "GLD"] = 0.50

    return w


def strategy_monthly_top2_momentum(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)

    ret60 = close.pct_change(60).shift(1)

    months = pd.Series(close.index.to_period("M"), index=close.index)
    rebalance_mask = months.ne(months.shift(1))
    rebalance_dates = set(close.index[rebalance_mask])

    current_weights = pd.Series(0.0, index=close.columns)

    for dt in close.index:
        if dt in rebalance_dates:
            scores = ret60.loc[dt].dropna().sort_values(ascending=False)
            positive = scores[scores > 0]

            current_weights[:] = 0.0

            if len(positive) >= 2:
                selected = list(positive.head(2).index)
                for symbol in selected:
                    current_weights[symbol] = 0.50
            elif len(positive) == 1:
                current_weights[positive.index[0]] = 0.50
                current_weights["TLT"] += 0.50
            else:
                current_weights["TLT"] = 0.50
                current_weights["GLD"] = 0.50

        w.loc[dt] = current_weights

    return w


def strategy_spy_trend_pullback(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)

    spy = close["SPY"]
    sma20 = spy.rolling(20).mean()
    sma200 = spy.rolling(200).mean()

    # Buy only if broad trend is up but SPY has pulled back more than 2% below 20DMA.
    signal = ((spy > sma200) & (spy < sma20 * 0.98)).shift(1).fillna(False)

    w.loc[signal, "SPY"] = 1.0

    return w


def backtest_strategy(name: str, close: pd.DataFrame, weights: pd.DataFrame) -> Dict[str, object]:
    returns = close.pct_change().fillna(0.0)

    weights = weights.reindex(close.index).fillna(0.0)
    weights = weights.clip(lower=0.0)

    gross_returns = (weights * returns).sum(axis=1)

    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    cost = turnover * (TRANSACTION_COST_BPS / 10_000.0)

    net_returns = gross_returns - cost
    equity = INITIAL_CAPITAL * (1.0 + net_returns).cumprod()

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0

    n_days = len(equity)
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (252 / max(n_days, 1)) - 1.0
    ann_vol = net_returns.std() * np.sqrt(252)
    sharpe = np.nan if ann_vol == 0 else (net_returns.mean() * 252) / ann_vol
    max_dd = drawdown.min()

    active_days = int((weights.sum(axis=1) > 0).sum())
    rebalance_days = int((turnover > 0.001).sum())
    avg_exposure = float(weights.sum(axis=1).mean())

    return {
        "strategy": name,
        "start": str(close.index[0].date()),
        "end": str(close.index[-1].date()),
        "days": int(n_days),
        "final_equity": round(float(equity.iloc[-1]), 2),
        "total_return_pct": round(float(total_return * 100), 2),
        "cagr_pct": round(float(cagr * 100), 2),
        "ann_vol_pct": round(float(ann_vol * 100), 2),
        "sharpe_0rf": None if pd.isna(sharpe) else round(float(sharpe), 3),
        "max_drawdown_pct": round(float(max_dd * 100), 2),
        "active_days": active_days,
        "rebalance_days": rebalance_days,
        "avg_exposure": round(avg_exposure, 3),
        "equity_curve": equity,
        "daily_returns": net_returns,
        "weights": weights,
    }


def main() -> None:
    safety_checks()

    print(f"Fetching historical bars for: {SYMBOLS}")
    print(f"Backtest window: {START_DATE} to {END_DATE}")
    print(f"Transaction cost assumption: {TRANSACTION_COST_BPS} bps per unit turnover")

    close = fetch_close_prices()

    strategies = {
        "SPY_buy_hold": strategy_spy_buy_hold(close),
        "equal_weight_5ETF": strategy_equal_weight(close),
        "spy_200dma_risk_switch": strategy_spy_200dma_risk_switch(close),
        "monthly_top2_60d_momentum": strategy_monthly_top2_momentum(close),
        "spy_trend_pullback": strategy_spy_trend_pullback(close),
    }

    results = []
    equity_curves = pd.DataFrame(index=close.index)

    for name, weights in strategies.items():
        result = backtest_strategy(name, close, weights)
        results.append({k: v for k, v in result.items() if k not in {"equity_curve", "daily_returns", "weights"}})
        equity_curves[name] = result["equity_curve"]

    summary = pd.DataFrame(results).sort_values("cagr_pct", ascending=False)

    summary_path = OUT_DIR / "historical_strategy_backtest_summary.csv"
    equity_path = OUT_DIR / "historical_strategy_equity_curves.csv"
    close_path = OUT_DIR / "historical_strategy_close_prices.csv"

    summary.to_csv(summary_path, index=False)
    equity_curves.to_csv(equity_path)
    close.to_csv(close_path)

    print("")
    print("HISTORICAL STRATEGY BACKTEST COMPLETE")
    print("-------------------------------------")
    print(summary.to_string(index=False))
    print("")
    print(f"Summary written to: {summary_path}")
    print(f"Equity curves written to: {equity_path}")
    print(f"Close prices written to: {close_path}")
    print("")
    print("No orders were submitted. This was historical testing only.")


if __name__ == "__main__":
    main()

