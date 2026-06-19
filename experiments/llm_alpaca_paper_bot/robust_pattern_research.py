from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import warnings

import numpy as np
import pandas as pd
import yfinance as yf


warnings.filterwarnings("ignore", category=FutureWarning)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "paper_bot_logs"
OUT_DIR.mkdir(exist_ok=True)

INITIAL_CAPITAL = 100_000.0
TRANSACTION_COST_BPS = 2.0
START_DATE = "2006-01-01"
END_DATE = None

CORE = ["SPY", "QQQ", "IWM", "GLD", "TLT"]
SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "VNQ"]
ALL_SYMBOLS = sorted(set(CORE + SECTORS))


def fetch_adjusted_close(symbols: List[str]) -> pd.DataFrame:
    print(f"Fetching adjusted historical prices from yfinance: {symbols}")
    raw = yf.download(
        tickers=symbols,
        start=START_DATE,
        end=END_DATE,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )

    if raw.empty:
        raise RuntimeError("No data returned from yfinance.")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            raise RuntimeError(f"Could not find Close in columns: {raw.columns}")
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = symbols

    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = close.sort_index()
    close = close.dropna(how="all").ffill()

    available = [s for s in symbols if s in close.columns]
    close = close[available]

    missing = [s for s in symbols if s not in close.columns]
    if missing:
        print(f"Warning: missing symbols: {missing}")

    return close


def empty_weights(close: pd.DataFrame, universe: List[str]) -> pd.DataFrame:
    return pd.DataFrame(0.0, index=close.index, columns=close.columns)


def buy_hold(close: pd.DataFrame, symbol: str) -> pd.DataFrame:
    w = empty_weights(close, [symbol])
    if symbol in close.columns:
        w[symbol] = 1.0
    return w


def above_ma_else_cash(close: pd.DataFrame, symbol: str, ma: int) -> pd.DataFrame:
    w = empty_weights(close, [symbol])
    px = close[symbol]
    signal = px > px.rolling(ma).mean()
    w.loc[signal, symbol] = 1.0
    return w


def ma_cross_else_cash(close: pd.DataFrame, symbol: str, fast: int, slow: int) -> pd.DataFrame:
    w = empty_weights(close, [symbol])
    px = close[symbol]
    signal = px.rolling(fast).mean() > px.rolling(slow).mean()
    w.loc[signal, symbol] = 1.0
    return w


def above_ma_else_defensive(close: pd.DataFrame, symbol: str, ma: int, defensive: Dict[str, float]) -> pd.DataFrame:
    w = empty_weights(close, [symbol] + list(defensive.keys()))
    px = close[symbol]
    signal = (px > px.rolling(ma).mean()).fillna(False).astype(bool)

    w.loc[signal, symbol] = 1.0

    off = ~signal
    for d_symbol, weight in defensive.items():
        if d_symbol in close.columns:
            w.loc[off, d_symbol] = weight

    return w


def monthly_top_n_momentum(
    close: pd.DataFrame,
    universe: List[str],
    lookback: int,
    n: int,
    positive_only: bool,
    fallback: Dict[str, float] | None = None,
) -> pd.DataFrame:
    universe = [s for s in universe if s in close.columns]
    w = empty_weights(close, universe)
    scores = close[universe].pct_change(lookback)

    months = pd.Series(close.index.to_period("M"), index=close.index)
    rebalance_dates = set(close.index[months.ne(months.shift(1))])

    current = pd.Series(0.0, index=close.columns)

    for dt in close.index:
        if dt in rebalance_dates:
            row = scores.loc[dt].dropna().sort_values(ascending=False)

            if positive_only:
                row = row[row > 0]

            current[:] = 0.0

            if len(row) >= n:
                selected = list(row.head(n).index)
                for symbol in selected:
                    current[symbol] = 1.0 / n
            elif len(row) > 0:
                selected = list(row.index)
                for symbol in selected:
                    current[symbol] = 1.0 / n

                leftover = 1.0 - current.sum()
                if leftover > 0 and fallback:
                    for f_symbol, f_weight in fallback.items():
                        if f_symbol in current.index:
                            current[f_symbol] += leftover * f_weight
            else:
                if fallback:
                    for f_symbol, f_weight in fallback.items():
                        if f_symbol in current.index:
                            current[f_symbol] = f_weight

        w.loc[dt] = current

    return w


def monthly_dual_momentum_sector_plus_bond(close: pd.DataFrame, lookback: int, n: int) -> pd.DataFrame:
    universe = [s for s in SECTORS if s in close.columns]
    fallback = {"TLT": 0.50, "GLD": 0.50}
    return monthly_top_n_momentum(
        close=close,
        universe=universe,
        lookback=lookback,
        n=n,
        positive_only=True,
        fallback=fallback,
    )


def monthly_top_n_core(close: pd.DataFrame, lookback: int, n: int, positive_only: bool) -> pd.DataFrame:
    fallback = {"TLT": 0.50, "GLD": 0.50}
    return monthly_top_n_momentum(
        close=close,
        universe=CORE,
        lookback=lookback,
        n=n,
        positive_only=positive_only,
        fallback=fallback,
    )


def qqq_pullback_in_uptrend(close: pd.DataFrame, pullback: float) -> pd.DataFrame:
    w = empty_weights(close, ["QQQ"])
    qqq = close["QQQ"]
    sma20 = qqq.rolling(20).mean()
    sma200 = qqq.rolling(200).mean()
    signal = (qqq > sma200) & (qqq < sma20 * (1.0 - pullback))
    w.loc[signal, "QQQ"] = 1.0
    return w


def qqq_breakout_in_uptrend(close: pd.DataFrame, lookback: int) -> pd.DataFrame:
    w = empty_weights(close, ["QQQ"])
    qqq = close["QQQ"]
    high = qqq.rolling(lookback).max()
    sma200 = qqq.rolling(200).mean()
    signal = (qqq >= high) & (qqq > sma200)
    w.loc[signal, "QQQ"] = 1.0
    return w


def inverse_vol_monthly(close: pd.DataFrame, universe: List[str], lookback: int) -> pd.DataFrame:
    universe = [s for s in universe if s in close.columns]
    w = empty_weights(close, universe)
    vol = close[universe].pct_change().rolling(lookback).std()

    months = pd.Series(close.index.to_period("M"), index=close.index)
    rebalance_dates = set(close.index[months.ne(months.shift(1))])

    current = pd.Series(0.0, index=close.columns)

    for dt in close.index:
        if dt in rebalance_dates:
            row = vol.loc[dt].replace(0, np.nan).dropna()
            current[:] = 0.0

            if len(row) > 0:
                inv = 1.0 / row
                inv = inv / inv.sum()
                current.loc[inv.index] = inv

        w.loc[dt] = current

    return w


def backtest(name: str, close: pd.DataFrame, raw_weights: pd.DataFrame) -> dict:
    close = close.copy()
    raw_weights = raw_weights.reindex(close.index).fillna(0.0)

    returns = close.pct_change().fillna(0.0)

    # Execute tomorrow using today's signal. This is non-negotiable.
    weights = raw_weights.shift(1).fillna(0.0).clip(lower=0.0)

    gross = (weights * returns).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    costs = turnover * (TRANSACTION_COST_BPS / 10_000.0)
    net = gross - costs

    equity = INITIAL_CAPITAL * (1.0 + net).cumprod()
    dd = equity / equity.cummax() - 1.0

    years = len(equity) / 252.0
    final_equity = float(equity.iloc[-1])
    total_return = final_equity / INITIAL_CAPITAL - 1.0
    cagr = (final_equity / INITIAL_CAPITAL) ** (1.0 / years) - 1.0 if years > 0 else np.nan
    ann_vol = float(net.std() * np.sqrt(252))
    sharpe = np.nan if ann_vol == 0 else float((net.mean() * 252) / ann_vol)
    max_dd = float(dd.min())

    return {
        "strategy": name,
        "start": str(close.index[0].date()),
        "end": str(close.index[-1].date()),
        "days": int(len(close)),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "ann_vol_pct": round(ann_vol * 100, 2),
        "sharpe_0rf": None if pd.isna(sharpe) else round(sharpe, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "avg_exposure": round(float(weights.sum(axis=1).mean()), 3),
        "active_days": int((weights.sum(axis=1) > 0).sum()),
        "rebalance_days": int((turnover > 0.001).sum()),
        "equity_curve": equity,
        "daily_returns": net,
    }


def build_strategies(close: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    strategies: Dict[str, pd.DataFrame] = {}

    for symbol in ["SPY", "QQQ", "XLK"]:
        if symbol in close.columns:
            strategies[f"{symbol}_buy_hold"] = buy_hold(close, symbol)
            strategies[f"{symbol}_above_200_cash"] = above_ma_else_cash(close, symbol, 200)
            strategies[f"{symbol}_above_150_cash"] = above_ma_else_cash(close, symbol, 150)
            strategies[f"{symbol}_50_200_cross"] = ma_cross_else_cash(close, symbol, 50, 200)

    if "QQQ" in close.columns:
        strategies["QQQ_200_or_TLT"] = above_ma_else_defensive(close, "QQQ", 200, {"TLT": 1.0})
        strategies["QQQ_200_or_GLD"] = above_ma_else_defensive(close, "QQQ", 200, {"GLD": 1.0})
        strategies["QQQ_200_or_TLT_GLD"] = above_ma_else_defensive(close, "QQQ", 200, {"TLT": 0.50, "GLD": 0.50})
        strategies["QQQ_pullback_2pct_uptrend"] = qqq_pullback_in_uptrend(close, 0.02)
        strategies["QQQ_pullback_4pct_uptrend"] = qqq_pullback_in_uptrend(close, 0.04)
        strategies["QQQ_60d_breakout_uptrend"] = qqq_breakout_in_uptrend(close, 60)
        strategies["QQQ_120d_breakout_uptrend"] = qqq_breakout_in_uptrend(close, 120)

    for lookback in [63, 126, 252]:
        strategies[f"core_top1_{lookback}d_positive"] = monthly_top_n_core(close, lookback, 1, True)
        strategies[f"core_top2_{lookback}d_positive"] = monthly_top_n_core(close, lookback, 2, True)
        strategies[f"core_top1_{lookback}d_any"] = monthly_top_n_core(close, lookback, 1, False)
        strategies[f"core_top2_{lookback}d_any"] = monthly_top_n_core(close, lookback, 2, False)

        strategies[f"sector_top1_{lookback}d_positive"] = monthly_dual_momentum_sector_plus_bond(close, lookback, 1)
        strategies[f"sector_top2_{lookback}d_positive"] = monthly_dual_momentum_sector_plus_bond(close, lookback, 2)
        strategies[f"sector_top3_{lookback}d_positive"] = monthly_dual_momentum_sector_plus_bond(close, lookback, 3)

    strategies["core_inverse_vol_60d"] = inverse_vol_monthly(close, CORE, 60)
    strategies["core_inverse_vol_120d"] = inverse_vol_monthly(close, CORE, 120)
    strategies["sector_inverse_vol_60d"] = inverse_vol_monthly(close, SECTORS, 60)
    strategies["sector_inverse_vol_120d"] = inverse_vol_monthly(close, SECTORS, 120)

    return strategies


def period_slice(close: pd.DataFrame, start: str, end: str | None) -> pd.DataFrame:
    x = close.loc[pd.Timestamp(start):].copy()
    if end is not None:
        x = x.loc[:pd.Timestamp(end)].copy()
    return x


def run_period(name: str, close: pd.DataFrame, strategies: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []

    for sname, full_weights in strategies.items():
        period_close = close.loc[close.index.intersection(full_weights.index)].copy()
        period_close = period_close.loc[close.index].copy()

        weights = full_weights.reindex(period_close.index).fillna(0.0)
        result = backtest(sname, period_close, weights)
        result["period"] = name
        rows.append({k: v for k, v in result.items() if k not in {"equity_curve", "daily_returns"}})

    return pd.DataFrame(rows)


def main() -> None:
    close = fetch_adjusted_close(ALL_SYMBOLS)

    # Require the main ETFs to exist. Drop rows before all core ETFs are available.
    close = close.dropna(subset=[s for s in CORE if s in close.columns]).copy()

    close_path = OUT_DIR / "robust_adjusted_close_prices.csv"
    close.to_csv(close_path)

    print(f"Adjusted close window: {close.index[0].date()} to {close.index[-1].date()}")
    print(f"Available symbols: {list(close.columns)}")
    print(f"Transaction cost assumption: {TRANSACTION_COST_BPS} bps per unit turnover")
    print("No orders will be submitted.")

    strategies = build_strategies(close)

    full_rows = []
    curves = pd.DataFrame(index=close.index)

    for name, weights in strategies.items():
        result = backtest(name, close, weights)
        full_rows.append({k: v for k, v in result.items() if k not in {"equity_curve", "daily_returns"}})
        curves[name] = result["equity_curve"]

    full_summary = pd.DataFrame(full_rows).sort_values(["cagr_pct", "sharpe_0rf"], ascending=False)

    periods: List[Tuple[str, str, str | None]] = [
        ("full", str(close.index[0].date()), None),
        ("pre_2020", str(close.index[0].date()), "2019-12-31"),
        ("covid_to_now", "2020-01-01", None),
        ("rate_hike_2022_2023", "2022-01-01", "2023-12-31"),
        ("recent_2024_now", "2024-01-01", None),
    ]

    period_frames = []

    for pname, pstart, pend in periods:
        pclose = period_slice(close, pstart, pend)
        if len(pclose) < 252:
            continue

        pstrategies = {}
        for sname, w in strategies.items():
            pstrategies[sname] = w.reindex(pclose.index).fillna(0.0)

        psum = run_period(pname, pclose, pstrategies)
        period_frames.append(psum)

    period_summary = pd.concat(period_frames, ignore_index=True)

    spy = full_summary[full_summary["strategy"] == "SPY_buy_hold"].iloc[0]
    qqq = full_summary[full_summary["strategy"] == "QQQ_buy_hold"].iloc[0]

    survivors = full_summary[
        (
            (full_summary["cagr_pct"] > spy["cagr_pct"])
            | (
                (full_summary["sharpe_0rf"] > spy["sharpe_0rf"])
                & (full_summary["max_drawdown_pct"] > spy["max_drawdown_pct"])
            )
        )
        & (~full_summary["strategy"].isin(["SPY_buy_hold", "QQQ_buy_hold"]))
    ].copy()

    full_path = OUT_DIR / "robust_strategy_tournament_full_summary.csv"
    period_path = OUT_DIR / "robust_strategy_tournament_period_summary.csv"
    survivor_path = OUT_DIR / "robust_strategy_tournament_survivors.csv"
    curves_path = OUT_DIR / "robust_strategy_tournament_equity_curves.csv"

    full_summary.to_csv(full_path, index=False)
    period_summary.to_csv(period_path, index=False)
    survivors.to_csv(survivor_path, index=False)
    curves.to_csv(curves_path)

    print("")
    print("ROBUST STRATEGY TOURNAMENT COMPLETE")
    print("-----------------------------------")
    print("")
    print("Top 20 by full-period CAGR:")
    print(full_summary.head(20).to_string(index=False))
    print("")
    print("SPY benchmark:")
    print(spy.to_frame().T.to_string(index=False))
    print("")
    print("QQQ benchmark:")
    print(qqq.to_frame().T.to_string(index=False))
    print("")
    print("Survivors beating SPY on CAGR OR Sharpe+Drawdown:")
    if survivors.empty:
        print("None")
    else:
        print(survivors.to_string(index=False))
    print("")
    print("Subperiod check for likely candidates:")
    likely = [
        "QQQ_above_200_cash",
        "QQQ_50_200_cross",
        "QQQ_200_or_TLT",
        "QQQ_200_or_TLT_GLD",
        "sector_top1_126d_positive",
        "sector_top2_126d_positive",
        "sector_top1_252d_positive",
        "sector_top2_252d_positive",
        "core_top1_126d_positive",
        "core_top2_126d_positive",
        "SPY_buy_hold",
        "QQQ_buy_hold",
    ]

    sub = period_summary[period_summary["strategy"].isin(likely)].copy()
    sub = sub.sort_values(["period", "cagr_pct"], ascending=[True, False])
    print(sub[[
        "period",
        "strategy",
        "cagr_pct",
        "sharpe_0rf",
        "max_drawdown_pct",
        "avg_exposure",
        "rebalance_days",
    ]].to_string(index=False))

    print("")
    print(f"Full summary written to: {full_path}")
    print(f"Period summary written to: {period_path}")
    print(f"Survivors written to: {survivor_path}")
    print(f"Equity curves written to: {curves_path}")
    print("")
    print("No orders were submitted. Historical research only.")


if __name__ == "__main__":
    main()
