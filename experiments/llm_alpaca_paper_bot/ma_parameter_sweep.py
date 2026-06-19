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

SYMBOLS = ["QQQ", "XLK"]
FAST_WINDOWS = [10, 20, 30, 40, 50, 75, 100]
SLOW_WINDOWS = [100, 125, 150, 175, 200, 225, 250, 300]


def load_close() -> pd.DataFrame:
    close = pd.read_csv(CLOSE_PATH, index_col=0, parse_dates=True)
    close = close.sort_index().ffill().dropna(how="all")
    missing = [s for s in SYMBOLS + ["SPY"] if s not in close.columns]
    if missing:
        raise RuntimeError(f"Missing symbols: {missing}")
    close = close.dropna(subset=SYMBOLS + ["SPY"])
    return close


def weights_cross(close: pd.DataFrame, symbol: str, fast: int, slow: int) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    px = close[symbol]
    signal = px.rolling(fast).mean() > px.rolling(slow).mean()
    w.loc[signal, symbol] = 1.0
    return w


def weights_above_ma(close: pd.DataFrame, symbol: str, slow: int) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    px = close[symbol]
    signal = px > px.rolling(slow).mean()
    w.loc[signal, symbol] = 1.0
    return w


def weights_buy_hold(close: pd.DataFrame, symbol: str) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    w[symbol] = 1.0
    return w


def replay(close: pd.DataFrame, raw_weights: pd.DataFrame) -> tuple[pd.Series, pd.Series, int]:
    raw_weights = raw_weights.reindex(close.index).fillna(0.0).clip(lower=0.0)

    cash = INITIAL_CASH
    shares = pd.Series(0, index=close.columns, dtype=int)

    equity_rows = []
    exposure_rows = []
    trade_count = 0

    pending_weights = None
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
                        trade_count += 1

                elif diff < 0:
                    qty = min(abs(diff), int(shares[symbol]))
                    if qty > 0:
                        cash += qty * price * (1.0 - FRICTION)
                        shares[symbol] -= qty
                        trade_count += 1

            last_executed_weights = pending_weights.copy()

        equity = cash + float((shares * prices).sum())
        exposure = 0.0 if equity <= 0 else float((shares * prices).sum()) / equity

        equity_rows.append((dt, equity))
        exposure_rows.append((dt, exposure))

        pending_weights = raw_weights.loc[dt]

    equity = pd.Series(dict(equity_rows)).sort_index()
    exposure = pd.Series(dict(exposure_rows)).sort_index()

    return equity, exposure, trade_count


def metrics(name: str, equity: pd.Series, exposure: pd.Series, trade_count: int, meta: dict) -> dict:
    r = equity.pct_change().fillna(0.0)
    dd = equity / equity.cummax() - 1.0

    years = len(equity) / 252.0
    final = float(equity.iloc[-1])
    cagr = (final / float(equity.iloc[0])) ** (1 / years) - 1
    vol = float(r.std() * np.sqrt(252))
    sharpe = np.nan if vol == 0 else float(r.mean() * 252 / vol)

    row = {
        "strategy": name,
        "symbol": meta.get("symbol"),
        "rule_type": meta.get("rule_type"),
        "fast": meta.get("fast"),
        "slow": meta.get("slow"),
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "final_equity": round(final, 2),
        "total_return_pct": round((final / float(equity.iloc[0]) - 1) * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "ann_vol_pct": round(vol * 100, 2),
        "sharpe_0rf": None if pd.isna(sharpe) else round(sharpe, 3),
        "max_drawdown_pct": round(float(dd.min()) * 100, 2),
        "avg_exposure": round(float(exposure.mean()), 3),
        "active_days": int((exposure > 0).sum()),
        "trade_count": int(trade_count),
    }
    return row


def main() -> None:
    close = load_close()

    rows = []
    curves = pd.DataFrame(index=close.index)

    for symbol in ["SPY", "QQQ", "XLK"]:
        w = weights_buy_hold(close, symbol)
        eq, ex, tc = replay(close, w)
        name = f"{symbol}_buy_hold"
        rows.append(metrics(name, eq, ex, tc, {"symbol": symbol, "rule_type": "buy_hold"}))
        curves[name] = eq

    for symbol in SYMBOLS:
        for slow in SLOW_WINDOWS:
            w = weights_above_ma(close, symbol, slow)
            eq, ex, tc = replay(close, w)
            name = f"{symbol}_above_{slow}_cash"
            rows.append(metrics(name, eq, ex, tc, {"symbol": symbol, "rule_type": "above_ma", "slow": slow}))
            curves[name] = eq

        for fast in FAST_WINDOWS:
            for slow in SLOW_WINDOWS:
                if fast >= slow:
                    continue

                w = weights_cross(close, symbol, fast, slow)
                eq, ex, tc = replay(close, w)
                name = f"{symbol}_{fast}_{slow}_cross"
                rows.append(metrics(name, eq, ex, tc, {"symbol": symbol, "rule_type": "cross", "fast": fast, "slow": slow}))
                curves[name] = eq

    summary = pd.DataFrame(rows).sort_values(["cagr_pct", "sharpe_0rf"], ascending=False)

    spy = summary[summary["strategy"] == "SPY_buy_hold"].iloc[0]

    viable = summary[
        (~summary["strategy"].isin(["SPY_buy_hold", "QQQ_buy_hold", "XLK_buy_hold"]))
        & (summary["cagr_pct"] > spy["cagr_pct"])
        & (summary["max_drawdown_pct"] > -35)
        & (summary["trade_count"] <= 150)
    ].copy()

    cluster = viable[
        (viable["symbol"] == "QQQ")
        & (viable["rule_type"] == "cross")
        & (viable["slow"].between(150, 250))
        & (viable["fast"].between(30, 75))
    ].copy()

    summary_path = LOG_DIR / "ma_parameter_sweep_summary.csv"
    viable_path = LOG_DIR / "ma_parameter_sweep_viable.csv"
    cluster_path = LOG_DIR / "ma_parameter_sweep_qcc_cluster.csv"
    curves_path = LOG_DIR / "ma_parameter_sweep_equity_curves.csv"

    summary.to_csv(summary_path, index=False)
    viable.to_csv(viable_path, index=False)
    cluster.to_csv(cluster_path, index=False)
    curves.to_csv(curves_path)

    print("")
    print("MA PARAMETER SWEEP COMPLETE")
    print("---------------------------")
    print("")
    print("Benchmarks:")
    print(summary[summary["strategy"].isin(["SPY_buy_hold", "QQQ_buy_hold", "XLK_buy_hold"])].to_string(index=False))
    print("")
    print("Top 25 overall:")
    print(summary.head(25).to_string(index=False))
    print("")
    print("Viable non-buy-hold candidates:")
    print(viable.head(30).to_string(index=False) if not viable.empty else "None")
    print("")
    print("QQQ cross cluster around 50/200:")
    print(cluster.sort_values(["cagr_pct", "sharpe_0rf"], ascending=False).to_string(index=False) if not cluster.empty else "None")
    print("")
    print(f"Summary written to: {summary_path}")
    print(f"Viable written to: {viable_path}")
    print(f"Cluster written to: {cluster_path}")
    print(f"Curves written to: {curves_path}")


if __name__ == "__main__":
    main()
