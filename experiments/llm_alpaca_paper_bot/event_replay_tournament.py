from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "paper_bot_logs"
CLOSE_PATH = LOG_DIR / "robust_adjusted_close_prices.csv"

INITIAL_CASH = 100_000.0
TRANSACTION_COST_BPS = 2.0
SLIPPAGE_BPS = 3.0
FRICTION = (TRANSACTION_COST_BPS + SLIPPAGE_BPS) / 10_000.0

CORE = ["SPY", "QQQ", "IWM", "GLD", "TLT"]


def load_close() -> pd.DataFrame:
    close = pd.read_csv(CLOSE_PATH, index_col=0, parse_dates=True)
    close = close.sort_index().ffill().dropna(how="all")
    return close


def metrics(name: str, equity: pd.Series, exposure: pd.Series, trades: pd.DataFrame) -> dict:
    r = equity.pct_change().fillna(0.0)
    dd = equity / equity.cummax() - 1.0
    years = len(equity) / 252.0
    final = float(equity.iloc[-1])
    cagr = (final / float(equity.iloc[0])) ** (1 / years) - 1
    vol = float(r.std() * np.sqrt(252))
    sharpe = np.nan if vol == 0 else float(r.mean() * 252 / vol)

    return {
        "strategy": name,
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "days": int(len(equity)),
        "final_equity": round(final, 2),
        "total_return_pct": round((final / float(equity.iloc[0]) - 1) * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "ann_vol_pct": round(vol * 100, 2),
        "sharpe_0rf": None if pd.isna(sharpe) else round(sharpe, 3),
        "max_drawdown_pct": round(float(dd.min()) * 100, 2),
        "avg_exposure": round(float(exposure.mean()), 3),
        "active_days": int((exposure > 0).sum()),
        "trade_count": int(len(trades)),
    }


def weights_buy_hold(close: pd.DataFrame, symbol: str) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    w[symbol] = 1.0
    return w


def weights_above_ma_cash(close: pd.DataFrame, symbol: str, ma: int) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    px = close[symbol]
    signal = px > px.rolling(ma).mean()
    w.loc[signal, symbol] = 1.0
    return w


def weights_cross_cash(close: pd.DataFrame, symbol: str, fast: int, slow: int) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    px = close[symbol]
    signal = px.rolling(fast).mean() > px.rolling(slow).mean()
    w.loc[signal, symbol] = 1.0
    return w


def weights_above_ma_defensive(close: pd.DataFrame, symbol: str, ma: int, defensive: dict[str, float]) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    px = close[symbol]
    signal = (px > px.rolling(ma).mean()).fillna(False).astype(bool)

    w.loc[signal, symbol] = 1.0

    for dsym, weight in defensive.items():
        w.loc[~signal, dsym] = weight

    return w


def weights_inverse_vol_monthly(close: pd.DataFrame, universe: list[str], lookback: int) -> pd.DataFrame:
    universe = [s for s in universe if s in close.columns]
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
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


def replay_strategy(close: pd.DataFrame, raw_weights: pd.DataFrame, name: str) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    raw_weights = raw_weights.reindex(close.index).fillna(0.0).clip(lower=0.0)

    cash = INITIAL_CASH
    shares = pd.Series(0, index=close.columns, dtype=int)

    rows = []
    trades = []

    pending_weights = None
    pending_signal_date = None
    last_executed_weights = None

    for dt in close.index:
        prices = close.loc[dt]

        should_execute = False
        if pending_weights is not None:
            if last_executed_weights is None:
                should_execute = True
            else:
                weight_change = (pending_weights - last_executed_weights).abs().sum()
                should_execute = bool(weight_change > 0.001)

        if pending_weights is not None and should_execute:
            equity_before = cash + float((shares * prices).sum())
            target_values = pending_weights * equity_before

            for symbol in close.columns:
                price = float(prices[symbol])
                if pd.isna(price) or price <= 0:
                    continue

                target_shares = math.floor(float(target_values[symbol]) / (price * (1.0 + FRICTION)))
                diff = int(target_shares - shares[symbol])

                if diff > 0:
                    affordable = math.floor(cash / (price * (1.0 + FRICTION)))
                    qty = min(diff, affordable)

                    if qty > 0:
                        cash -= qty * price * (1.0 + FRICTION)
                        shares[symbol] += qty
                        trades.append({
                            "strategy": name,
                            "execution_date": dt,
                            "signal_date": pending_signal_date,
                            "symbol": symbol,
                            "side": "BUY",
                            "qty": qty,
                            "price": round(price, 4),
                            "cash_after": round(cash, 2),
                        })

                elif diff < 0:
                    qty = min(abs(diff), int(shares[symbol]))

                    if qty > 0:
                        cash += qty * price * (1.0 - FRICTION)
                        shares[symbol] -= qty
                        trades.append({
                            "strategy": name,
                            "execution_date": dt,
                            "signal_date": pending_signal_date,
                            "symbol": symbol,
                            "side": "SELL",
                            "qty": qty,
                            "price": round(price, 4),
                            "cash_after": round(cash, 2),
                        })

        equity = cash + float((shares * prices).sum())
        exposure = 0.0 if equity <= 0 else float((shares * prices).sum()) / equity

        rows.append({
            "date": dt,
            "cash": cash,
            "equity": equity,
            "exposure": exposure,
        })

        if pending_weights is not None and should_execute:
            last_executed_weights = pending_weights.copy()

        pending_weights = raw_weights.loc[dt]
        pending_signal_date = dt

    ledger = pd.DataFrame(rows).set_index("date")
    trade_df = pd.DataFrame(trades)

    return ledger["equity"], ledger["exposure"], trade_df


def period_check(close: pd.DataFrame, strategies: dict[str, pd.DataFrame]) -> pd.DataFrame:
    periods = [
        ("full", None, None),
        ("pre_2020", None, "2019-12-31"),
        ("covid_to_now", "2020-01-01", None),
        ("rate_hike_2022_2023", "2022-01-01", "2023-12-31"),
        ("recent_2024_now", "2024-01-01", None),
    ]

    rows = []

    for pname, start, end in periods:
        pclose = close.copy()
        if start:
            pclose = pclose.loc[pd.Timestamp(start):]
        if end:
            pclose = pclose.loc[:pd.Timestamp(end)]

        if len(pclose) < 252:
            continue

        for name, weights in strategies.items():
            pweights = weights.reindex(pclose.index).fillna(0.0)
            equity, exposure, trades = replay_strategy(pclose, pweights, name)
            m = metrics(name, equity, exposure, trades)
            m["period"] = pname
            rows.append(m)

    return pd.DataFrame(rows)


def main() -> None:
    close = load_close()

    required = ["SPY", "QQQ", "GLD", "TLT", "XLK"]
    missing = [s for s in required if s not in close.columns]
    if missing:
        raise RuntimeError(f"Missing symbols: {missing}")

    close = close.dropna(subset=["SPY", "QQQ", "GLD", "TLT", "XLK"])

    strategies = {
        "SPY_buy_hold": weights_buy_hold(close, "SPY"),
        "QQQ_buy_hold": weights_buy_hold(close, "QQQ"),
        "XLK_buy_hold": weights_buy_hold(close, "XLK"),

        "QQQ_50_200_cross": weights_cross_cash(close, "QQQ", 50, 200),
        "QQQ_above_150_cash": weights_above_ma_cash(close, "QQQ", 150),
        "QQQ_above_200_cash": weights_above_ma_cash(close, "QQQ", 200),
        "QQQ_200_or_GLD": weights_above_ma_defensive(close, "QQQ", 200, {"GLD": 1.0}),
        "QQQ_200_or_TLT_GLD": weights_above_ma_defensive(close, "QQQ", 200, {"TLT": 0.5, "GLD": 0.5}),

        "XLK_50_200_cross": weights_cross_cash(close, "XLK", 50, 200),
        "XLK_above_200_cash": weights_above_ma_cash(close, "XLK", 200),

        "core_inverse_vol_60d": weights_inverse_vol_monthly(close, CORE, 60),
        "core_inverse_vol_120d": weights_inverse_vol_monthly(close, CORE, 120),
    }

    rows = []
    curves = pd.DataFrame(index=close.index)
    all_trades = []

    for name, weights in strategies.items():
        equity, exposure, trades = replay_strategy(close, weights, name)
        rows.append(metrics(name, equity, exposure, trades))
        curves[name] = equity
        if not trades.empty:
            all_trades.append(trades)

    summary = pd.DataFrame(rows).sort_values(["cagr_pct", "sharpe_0rf"], ascending=False)
    period_summary = period_check(close, strategies)

    trades_all = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()

    summary_path = LOG_DIR / "event_replay_tournament_summary.csv"
    period_path = LOG_DIR / "event_replay_tournament_period_summary.csv"
    curves_path = LOG_DIR / "event_replay_tournament_equity_curves.csv"
    trades_path = LOG_DIR / "event_replay_tournament_trades.csv"

    summary.to_csv(summary_path, index=False)
    period_summary.to_csv(period_path, index=False)
    curves.to_csv(curves_path)
    trades_all.to_csv(trades_path, index=False)

    print("")
    print("EVENT REPLAY TOURNAMENT COMPLETE")
    print("--------------------------------")
    print("")
    print("Full-period ranking:")
    print(summary.to_string(index=False))
    print("")
    print("Subperiod ranking:")
    print(
        period_summary[
            [
                "period",
                "strategy",
                "cagr_pct",
                "sharpe_0rf",
                "max_drawdown_pct",
                "avg_exposure",
                "trade_count",
            ]
        ].sort_values(["period", "cagr_pct"], ascending=[True, False]).to_string(index=False)
    )
    print("")
    print(f"Summary written to: {summary_path}")
    print(f"Period summary written to: {period_path}")
    print(f"Curves written to: {curves_path}")
    print(f"Trades written to: {trades_path}")
    print("")
    print("No broker calls. No orders submitted.")


if __name__ == "__main__":
    main()

