from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "paper_bot_logs"
CLOSE_PATH = OUT_DIR / "historical_strategy_close_prices.csv"

INITIAL_CAPITAL = 100_000.0
TRANSACTION_COST_BPS = 2.0
SYMBOLS = ["SPY", "QQQ", "IWM", "GLD", "TLT"]


def load_close() -> pd.DataFrame:
    if not CLOSE_PATH.exists():
        raise RuntimeError(f"Missing close-price file: {CLOSE_PATH}")

    close = pd.read_csv(CLOSE_PATH, index_col=0, parse_dates=True)
    close = close[SYMBOLS].sort_index().ffill().dropna()
    return close


def empty_weights(close: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(0.0, index=close.index, columns=close.columns)


def buy_hold(close: pd.DataFrame, symbol: str) -> pd.DataFrame:
    w = empty_weights(close)
    w[symbol] = 1.0
    return w


def equal_weight(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)
    w.loc[:, SYMBOLS] = 1.0 / len(SYMBOLS)
    return w


def spy_above_200_else_cash(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)
    spy = close["SPY"]
    signal = spy > spy.rolling(200).mean()
    w.loc[signal, "SPY"] = 1.0
    return w


def qqq_above_200_else_cash(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)
    qqq = close["QQQ"]
    signal = qqq > qqq.rolling(200).mean()
    w.loc[signal, "QQQ"] = 1.0
    return w


def spy_50_200_cross(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)
    spy = close["SPY"]
    signal = spy.rolling(50).mean() > spy.rolling(200).mean()
    w.loc[signal, "SPY"] = 1.0
    return w


def qqq_50_200_cross(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)
    qqq = close["QQQ"]
    signal = qqq.rolling(50).mean() > qqq.rolling(200).mean()
    w.loc[signal, "QQQ"] = 1.0
    return w


def risk_on_off_spy_tlt(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)
    spy = close["SPY"]
    risk_on = spy > spy.rolling(200).mean()
    w.loc[risk_on, "SPY"] = 1.0
    w.loc[~risk_on.fillna(False).astype(bool), "TLT"] = 1.0
    return w


def risk_on_off_qqq_tlt(close: pd.DataFrame) -> pd.DataFrame:
    w = empty_weights(close)
    qqq = close["QQQ"]
    risk_on = qqq > qqq.rolling(200).mean()
    w.loc[risk_on, "QQQ"] = 1.0
    w.loc[~risk_on.fillna(False).astype(bool), "TLT"] = 1.0
    return w


def monthly_top_n_momentum(close: pd.DataFrame, lookback: int, n: int, defensive: bool) -> pd.DataFrame:
    w = empty_weights(close)
    scores = close.pct_change(lookback)

    months = pd.Series(close.index.tz_localize(None).to_period("M"), index=close.index)
    rebalance_mask = months.ne(months.shift(1))
    rebalance_dates = set(close.index[rebalance_mask])

    current = pd.Series(0.0, index=close.columns)

    for dt in close.index:
        if dt in rebalance_dates:
            row = scores.loc[dt].dropna().sort_values(ascending=False)
            current[:] = 0.0

            if defensive:
                row = row[row > 0]

            if len(row) >= n:
                selected = list(row.head(n).index)
                for symbol in selected:
                    current[symbol] = 1.0 / n
            elif len(row) > 0:
                selected = list(row.index)
                for symbol in selected:
                    current[symbol] = 1.0 / max(n, 1)

                leftover = 1.0 - current.sum()
                if leftover > 0:
                    current["TLT"] += leftover
            else:
                current["TLT"] = 0.5
                current["GLD"] = 0.5

        w.loc[dt] = current

    return w


def monthly_inverse_vol(close: pd.DataFrame, lookback: int) -> pd.DataFrame:
    w = empty_weights(close)
    vol = close.pct_change().rolling(lookback).std()

    months = pd.Series(close.index.tz_localize(None).to_period("M"), index=close.index)
    rebalance_mask = months.ne(months.shift(1))
    rebalance_dates = set(close.index[rebalance_mask])

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


def monthly_top1_vol_target(close: pd.DataFrame, lookback: int, target_vol: float) -> pd.DataFrame:
    w = empty_weights(close)
    scores = close.pct_change(lookback)
    realized_vol = close.pct_change().rolling(20).std() * np.sqrt(252)

    months = pd.Series(close.index.tz_localize(None).to_period("M"), index=close.index)
    rebalance_mask = months.ne(months.shift(1))
    rebalance_dates = set(close.index[rebalance_mask])

    current = pd.Series(0.0, index=close.columns)

    for dt in close.index:
        if dt in rebalance_dates:
            score_row = scores.loc[dt].dropna().sort_values(ascending=False)
            vol_row = realized_vol.loc[dt].dropna()

            current[:] = 0.0

            positive = score_row[score_row > 0]
            if len(positive) > 0:
                symbol = positive.index[0]
                vol = vol_row.get(symbol, np.nan)
                exposure = 1.0 if pd.isna(vol) or vol <= 0 else min(1.0, target_vol / vol)
                current[symbol] = exposure

        w.loc[dt] = current

    return w


def spy_bull_pullback(close: pd.DataFrame, pullback_pct: float) -> pd.DataFrame:
    w = empty_weights(close)
    spy = close["SPY"]
    sma20 = spy.rolling(20).mean()
    sma200 = spy.rolling(200).mean()

    signal = (spy > sma200) & (spy < sma20 * (1.0 - pullback_pct))
    w.loc[signal, "SPY"] = 1.0
    return w


def qqq_bull_pullback(close: pd.DataFrame, pullback_pct: float) -> pd.DataFrame:
    w = empty_weights(close)
    qqq = close["QQQ"]
    sma20 = qqq.rolling(20).mean()
    sma200 = qqq.rolling(200).mean()

    signal = (qqq > sma200) & (qqq < sma20 * (1.0 - pullback_pct))
    w.loc[signal, "QQQ"] = 1.0
    return w


def spy_breakout(close: pd.DataFrame, lookback: int) -> pd.DataFrame:
    w = empty_weights(close)
    spy = close["SPY"]
    high = spy.rolling(lookback).max()
    trend = spy > spy.rolling(200).mean()

    signal = (spy >= high) & trend
    w.loc[signal, "SPY"] = 1.0
    return w


def qqq_breakout(close: pd.DataFrame, lookback: int) -> pd.DataFrame:
    w = empty_weights(close)
    qqq = close["QQQ"]
    high = qqq.rolling(lookback).max()
    trend = qqq > qqq.rolling(200).mean()

    signal = (qqq >= high) & trend
    w.loc[signal, "QQQ"] = 1.0
    return w


def backtest(name: str, close: pd.DataFrame, raw_weights: pd.DataFrame) -> dict:
    returns = close.pct_change().fillna(0.0)

    # Critical: execute next day to reduce lookahead.
    weights = raw_weights.reindex(close.index).fillna(0.0).clip(lower=0.0).shift(1).fillna(0.0)

    gross = (weights * returns).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    costs = turnover * (TRANSACTION_COST_BPS / 10_000.0)

    net = gross - costs
    equity = INITIAL_CAPITAL * (1.0 + net).cumprod()
    dd = equity / equity.cummax() - 1.0

    years = len(equity) / 252
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0 if years > 0 else np.nan
    ann_vol = net.std() * np.sqrt(252)
    sharpe = np.nan if ann_vol == 0 else (net.mean() * 252) / ann_vol

    return {
        "strategy": name,
        "start": str(close.index[0].date()),
        "end": str(close.index[-1].date()),
        "days": int(len(close)),
        "final_equity": round(float(equity.iloc[-1]), 2),
        "total_return_pct": round(float(total_return * 100), 2),
        "cagr_pct": round(float(cagr * 100), 2),
        "ann_vol_pct": round(float(ann_vol * 100), 2),
        "sharpe_0rf": None if pd.isna(sharpe) else round(float(sharpe), 3),
        "max_drawdown_pct": round(float(dd.min() * 100), 2),
        "avg_exposure": round(float(weights.sum(axis=1).mean()), 3),
        "active_days": int((weights.sum(axis=1) > 0).sum()),
        "rebalance_days": int((turnover > 0.001).sum()),
        "equity_curve": equity,
    }


def main() -> None:
    close = load_close()

    strategies = {
        "SPY_buy_hold": buy_hold(close, "SPY"),
        "QQQ_buy_hold": buy_hold(close, "QQQ"),
        "equal_weight_5ETF": equal_weight(close),

        "SPY_above_200_else_cash": spy_above_200_else_cash(close),
        "QQQ_above_200_else_cash": qqq_above_200_else_cash(close),
        "SPY_50_200_cross": spy_50_200_cross(close),
        "QQQ_50_200_cross": qqq_50_200_cross(close),

        "risk_on_off_SPY_TLT": risk_on_off_spy_tlt(close),
        "risk_on_off_QQQ_TLT": risk_on_off_qqq_tlt(close),

        "monthly_top1_63d_mom": monthly_top_n_momentum(close, 63, 1, defensive=False),
        "monthly_top2_63d_mom": monthly_top_n_momentum(close, 63, 2, defensive=False),
        "monthly_top1_126d_mom": monthly_top_n_momentum(close, 126, 1, defensive=False),
        "monthly_top2_126d_mom": monthly_top_n_momentum(close, 126, 2, defensive=False),
        "monthly_top1_252d_mom": monthly_top_n_momentum(close, 252, 1, defensive=False),
        "monthly_top2_252d_mom": monthly_top_n_momentum(close, 252, 2, defensive=False),

        "defensive_top1_63d_mom": monthly_top_n_momentum(close, 63, 1, defensive=True),
        "defensive_top2_63d_mom": monthly_top_n_momentum(close, 63, 2, defensive=True),
        "defensive_top1_126d_mom": monthly_top_n_momentum(close, 126, 1, defensive=True),
        "defensive_top2_126d_mom": monthly_top_n_momentum(close, 126, 2, defensive=True),
        "defensive_top1_252d_mom": monthly_top_n_momentum(close, 252, 1, defensive=True),
        "defensive_top2_252d_mom": monthly_top_n_momentum(close, 252, 2, defensive=True),

        "monthly_inverse_vol_60d": monthly_inverse_vol(close, 60),
        "monthly_inverse_vol_120d": monthly_inverse_vol(close, 120),

        "monthly_top1_126d_vol10": monthly_top1_vol_target(close, 126, 0.10),
        "monthly_top1_126d_vol15": monthly_top1_vol_target(close, 126, 0.15),

        "SPY_bull_pullback_2pct": spy_bull_pullback(close, 0.02),
        "SPY_bull_pullback_4pct": spy_bull_pullback(close, 0.04),
        "QQQ_bull_pullback_2pct": qqq_bull_pullback(close, 0.02),
        "QQQ_bull_pullback_4pct": qqq_bull_pullback(close, 0.04),

        "SPY_60d_breakout": spy_breakout(close, 60),
        "SPY_120d_breakout": spy_breakout(close, 120),
        "QQQ_60d_breakout": qqq_breakout(close, 60),
        "QQQ_120d_breakout": qqq_breakout(close, 120),
    }

    rows = []
    curves = pd.DataFrame(index=close.index)

    for name, weights in strategies.items():
        result = backtest(name, close, weights)
        rows.append({k: v for k, v in result.items() if k != "equity_curve"})
        curves[name] = result["equity_curve"]

    summary = pd.DataFrame(rows).sort_values(["cagr_pct", "sharpe_0rf"], ascending=False)

    spy = summary[summary["strategy"] == "SPY_buy_hold"].iloc[0]
    survivors = summary[
        (
            (summary["cagr_pct"] > spy["cagr_pct"]) |
            (
                (summary["sharpe_0rf"] > spy["sharpe_0rf"]) &
                (summary["max_drawdown_pct"] > spy["max_drawdown_pct"])
            )
        )
        & (summary["strategy"] != "SPY_buy_hold")
    ].copy()

    summary_path = OUT_DIR / "strategy_tournament_summary.csv"
    survivor_path = OUT_DIR / "strategy_tournament_survivors.csv"
    curves_path = OUT_DIR / "strategy_tournament_equity_curves.csv"

    summary.to_csv(summary_path, index=False)
    survivors.to_csv(survivor_path, index=False)
    curves.to_csv(curves_path)

    print("")
    print("STRATEGY TOURNAMENT COMPLETE")
    print("----------------------------")
    print("")
    print("Top 15 by CAGR:")
    print(summary.head(15).to_string(index=False))
    print("")
    print("SPY benchmark:")
    print(spy.to_frame().T.to_string(index=False))
    print("")
    print("Survivors beating SPY on CAGR OR Sharpe+Drawdown:")
    if survivors.empty:
        print("None")
    else:
        print(survivors.to_string(index=False))
    print("")
    print(f"Summary written to: {summary_path}")
    print(f"Survivors written to: {survivor_path}")
    print(f"Equity curves written to: {curves_path}")
    print("")
    print("No orders were submitted. Historical test only.")


if __name__ == "__main__":
    main()
