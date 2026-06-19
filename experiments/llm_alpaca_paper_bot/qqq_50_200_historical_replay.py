from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "paper_bot_logs"
LOG_DIR.mkdir(exist_ok=True)

CLOSE_PATH = LOG_DIR / "robust_adjusted_close_prices.csv"

INITIAL_CASH = 100_000.0
SYMBOL = "QQQ"
BENCHMARKS = ["QQQ", "SPY"]

FAST_MA = 50
SLOW_MA = 200

TRANSACTION_COST_BPS = 2.0
SLIPPAGE_BPS = 3.0
TOTAL_TRADE_FRICTION = (TRANSACTION_COST_BPS + SLIPPAGE_BPS) / 10_000.0


def load_prices() -> pd.DataFrame:
    if not CLOSE_PATH.exists():
        raise RuntimeError(
            f"Missing {CLOSE_PATH}. Run robust_pattern_research.py first."
        )

    close = pd.read_csv(CLOSE_PATH, index_col=0, parse_dates=True)
    needed = [SYMBOL] + BENCHMARKS
    needed = sorted(set(needed))

    missing = [s for s in needed if s not in close.columns]
    if missing:
        raise RuntimeError(f"Missing required symbols in close file: {missing}")

    close = close[needed].sort_index().ffill().dropna()
    return close


def perf_metrics(name: str, equity: pd.Series, exposure: pd.Series | None = None, trades: pd.DataFrame | None = None) -> dict:
    equity = equity.dropna()
    daily_returns = equity.pct_change().fillna(0.0)
    dd = equity / equity.cummax() - 1.0

    years = len(equity) / 252.0
    final_equity = float(equity.iloc[-1])
    total_return = final_equity / float(equity.iloc[0]) - 1.0
    cagr = (final_equity / float(equity.iloc[0])) ** (1 / years) - 1 if years > 0 else np.nan
    ann_vol = float(daily_returns.std() * np.sqrt(252))
    sharpe = np.nan if ann_vol == 0 else float(daily_returns.mean() * 252 / ann_vol)

    return {
        "strategy": name,
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "days": int(len(equity)),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "ann_vol_pct": round(ann_vol * 100, 2),
        "sharpe_0rf": None if pd.isna(sharpe) else round(sharpe, 3),
        "max_drawdown_pct": round(float(dd.min()) * 100, 2),
        "avg_exposure": None if exposure is None else round(float(exposure.mean()), 3),
        "active_days": None if exposure is None else int((exposure > 0).sum()),
        "trade_count": 0 if trades is None else int(len(trades)),
    }


def run_buy_hold(close: pd.DataFrame, symbol: str) -> tuple[pd.Series, pd.Series]:
    px = close[symbol].dropna()
    first_price = float(px.iloc[0])

    shares = math.floor(INITIAL_CASH / (first_price * (1.0 + TOTAL_TRADE_FRICTION)))
    spent = shares * first_price * (1.0 + TOTAL_TRADE_FRICTION)
    cash = INITIAL_CASH - spent

    equity = cash + shares * px
    exposure = (shares * px) / equity

    return equity, exposure


def run_qqq_50_200_replay(close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = close[[SYMBOL]].copy()
    df["sma50"] = df[SYMBOL].rolling(FAST_MA).mean()
    df["sma200"] = df[SYMBOL].rolling(SLOW_MA).mean()

    cash = INITIAL_CASH
    shares = 0

    pending_target_fraction: float | None = None
    pending_signal_date = None

    rows = []
    trades = []

    for dt, row in df.iterrows():
        price = float(row[SYMBOL])

        executed_trade = False
        trade_qty = 0
        trade_side = "NONE"
        trade_reason = ""

        # Execute yesterday's signal today.
        if pending_target_fraction is not None:
            pre_trade_equity = cash + shares * price
            target_value = pre_trade_equity * pending_target_fraction
            target_shares = math.floor(target_value / (price * (1.0 + TOTAL_TRADE_FRICTION)))

            trade_qty = target_shares - shares

            if trade_qty > 0:
                max_affordable = math.floor(cash / (price * (1.0 + TOTAL_TRADE_FRICTION)))
                trade_qty = min(trade_qty, max_affordable)

                if trade_qty > 0:
                    cost = trade_qty * price * (1.0 + TOTAL_TRADE_FRICTION)
                    cash -= cost
                    shares += trade_qty
                    executed_trade = True
                    trade_side = "BUY"
                    trade_reason = "target_in_market"

            elif trade_qty < 0:
                sell_qty = abs(trade_qty)
                sell_qty = min(sell_qty, shares)

                if sell_qty > 0:
                    proceeds = sell_qty * price * (1.0 - TOTAL_TRADE_FRICTION)
                    cash += proceeds
                    shares -= sell_qty
                    executed_trade = True
                    trade_side = "SELL"
                    trade_qty = -sell_qty
                    trade_reason = "target_cash"

            if executed_trade:
                trades.append(
                    {
                        "execution_date": dt,
                        "signal_date": pending_signal_date,
                        "symbol": SYMBOL,
                        "side": trade_side,
                        "qty": int(abs(trade_qty)),
                        "signed_qty": int(trade_qty),
                        "price": round(price, 4),
                        "friction_bps_total": round(TOTAL_TRADE_FRICTION * 10_000, 2),
                        "cash_after": round(cash, 2),
                        "shares_after": int(shares),
                        "reason": trade_reason,
                    }
                )

        equity = cash + shares * price
        exposure = 0.0 if equity <= 0 else (shares * price) / equity

        signal_ready = not pd.isna(row["sma50"]) and not pd.isna(row["sma200"])
        signal_in_market = bool(row["sma50"] > row["sma200"]) if signal_ready else False

        # Today's signal becomes tomorrow's target.
        if signal_ready:
            pending_target_fraction = 1.0 if signal_in_market else 0.0
            pending_signal_date = dt
        else:
            pending_target_fraction = None
            pending_signal_date = None

        rows.append(
            {
                "date": dt,
                "price": price,
                "sma50": None if pd.isna(row["sma50"]) else float(row["sma50"]),
                "sma200": None if pd.isna(row["sma200"]) else float(row["sma200"]),
                "signal_ready": bool(signal_ready),
                "signal_in_market": bool(signal_in_market),
                "cash": round(cash, 2),
                "shares": int(shares),
                "equity": round(equity, 2),
                "exposure": round(exposure, 6),
                "pending_target_fraction_for_next_day": pending_target_fraction,
            }
        )

    equity_df = pd.DataFrame(rows).set_index("date")
    trades_df = pd.DataFrame(trades)

    return equity_df, trades_df


def subperiod_summary(equity_df: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    periods = [
        ("full", None, None),
        ("pre_2020", None, "2019-12-31"),
        ("covid_to_now", "2020-01-01", None),
        ("rate_hike_2022_2023", "2022-01-01", "2023-12-31"),
        ("recent_2024_now", "2024-01-01", None),
    ]

    rows = []

    replay_equity = equity_df["equity"]
    replay_exposure = equity_df["exposure"]

    for period_name, start, end in periods:
        replay_slice = replay_equity.copy()
        exposure_slice = replay_exposure.copy()

        if start:
            replay_slice = replay_slice.loc[pd.Timestamp(start):]
            exposure_slice = exposure_slice.loc[pd.Timestamp(start):]
        if end:
            replay_slice = replay_slice.loc[:pd.Timestamp(end)]
            exposure_slice = exposure_slice.loc[:pd.Timestamp(end)]

        if len(replay_slice) >= 252:
            m = perf_metrics(
                f"QQQ_50_200_historical_replay",
                replay_slice,
                exposure_slice,
                None,
            )
            m["period"] = period_name
            rows.append(m)

        for symbol in BENCHMARKS:
            bench_equity, bench_exposure = run_buy_hold(close, symbol)

            if start:
                bench_equity = bench_equity.loc[pd.Timestamp(start):]
                bench_exposure = bench_exposure.loc[pd.Timestamp(start):]
            if end:
                bench_equity = bench_equity.loc[:pd.Timestamp(end)]
                bench_exposure = bench_exposure.loc[:pd.Timestamp(end)]

            if len(bench_equity) >= 252:
                m = perf_metrics(f"{symbol}_buy_hold", bench_equity, bench_exposure, None)
                m["period"] = period_name
                rows.append(m)

    return pd.DataFrame(rows)


def main() -> None:
    close = load_prices()

    print("Running event-style historical replay.")
    print(f"Symbol: {SYMBOL}")
    print(f"Rule: {FAST_MA}DMA > {SLOW_MA}DMA")
    print(f"Execution proxy: next trading day adjusted close")
    print(f"Initial cash: ${INITIAL_CASH:,.2f}")
    print(f"Transaction cost: {TRANSACTION_COST_BPS} bps")
    print(f"Slippage: {SLIPPAGE_BPS} bps")
    print("No broker calls. No orders. Historical replay only.")

    replay_df, trades_df = run_qqq_50_200_replay(close)

    qqq_bh_equity, qqq_bh_exposure = run_buy_hold(close, "QQQ")
    spy_bh_equity, spy_bh_exposure = run_buy_hold(close, "SPY")

    summary_rows = []

    summary_rows.append(
        perf_metrics(
            "QQQ_50_200_historical_replay",
            replay_df["equity"],
            replay_df["exposure"],
            trades_df,
        )
    )

    summary_rows.append(perf_metrics("QQQ_buy_hold", qqq_bh_equity, qqq_bh_exposure, None))
    summary_rows.append(perf_metrics("SPY_buy_hold", spy_bh_equity, spy_bh_exposure, None))

    summary = pd.DataFrame(summary_rows).sort_values(["cagr_pct", "sharpe_0rf"], ascending=False)

    period_summary = subperiod_summary(replay_df, close)

    out_equity = LOG_DIR / "qqq_50_200_historical_replay_equity.csv"
    out_trades = LOG_DIR / "qqq_50_200_historical_replay_trades.csv"
    out_summary = LOG_DIR / "qqq_50_200_historical_replay_summary.csv"
    out_period = LOG_DIR / "qqq_50_200_historical_replay_period_summary.csv"

    replay_df.to_csv(out_equity)
    trades_df.to_csv(out_trades, index=False)
    summary.to_csv(out_summary, index=False)
    period_summary.to_csv(out_period, index=False)

    latest = replay_df.iloc[-1]

    print("")
    print("QQQ 50/200 HISTORICAL REPLAY COMPLETE")
    print("-------------------------------------")
    print("")
    print("Full-period comparison:")
    print(summary.to_string(index=False))
    print("")
    print("Subperiod comparison:")
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
    print("Latest replay state:")
    print(
        {
            "latest_date": str(replay_df.index[-1].date()),
            "price": round(float(latest["price"]), 4),
            "sma50": round(float(latest["sma50"]), 4) if pd.notna(latest["sma50"]) else None,
            "sma200": round(float(latest["sma200"]), 4) if pd.notna(latest["sma200"]) else None,
            "signal_in_market": bool(latest["signal_in_market"]),
            "shares": int(latest["shares"]),
            "equity": round(float(latest["equity"]), 2),
            "exposure": round(float(latest["exposure"]), 4),
        }
    )
    print("")
    print(f"Equity replay written to: {out_equity}")
    print(f"Trade ledger written to: {out_trades}")
    print(f"Summary written to: {out_summary}")
    print(f"Period summary written to: {out_period}")
    print("")
    print("No orders were submitted.")


if __name__ == "__main__":
    main()
