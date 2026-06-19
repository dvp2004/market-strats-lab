from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import os
from decimal import Decimal

import pandas as pd
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"
LOG_DIR = REPO_ROOT / "paper_bot_logs"
LOG_DIR.mkdir(exist_ok=True)

load_dotenv(dotenv_path=ENV_PATH)

SYMBOL = "QQQ"
MAX_SHARES_FIRST_RUN = 1


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_bool_env(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default).strip().lower()
    if value not in {"true", "false"}:
        raise RuntimeError(f"{name} must be true or false, got: {value}")
    return value == "true"


def safety_checks() -> tuple[bool, str]:
    base_url = require_env("APCA_API_BASE_URL")
    bot_mode = require_env("BOT_MODE")
    dry_run = os.getenv("DRY_RUN", "true").strip().lower()

    if base_url != "https://paper-api.alpaca.markets":
        raise RuntimeError(f"Refusing to run: unsafe Alpaca endpoint: {base_url}")

    if bot_mode != "paper":
        raise RuntimeError(f"Refusing to run: BOT_MODE must be paper, got: {bot_mode}")

    if dry_run not in {"true", "false"}:
        raise RuntimeError(f"DRY_RUN must be true or false, got: {dry_run}")

    enable_orders = parse_bool_env("ENABLE_PAPER_ORDERS", "false")

    if enable_orders and dry_run == "true":
        raise RuntimeError("Contradiction: ENABLE_PAPER_ORDERS=true but DRY_RUN=true")

    mode = "PAPER_ORDER_ENABLED" if enable_orders else "SIGNAL_ONLY"
    print(f"Safety checks passed. Mode: {mode}")

    return enable_orders, mode


def get_clients() -> tuple[TradingClient, StockHistoricalDataClient]:
    api_key = require_env("APCA_API_KEY_ID")
    secret = require_env("APCA_API_SECRET_KEY")

    trading_client = TradingClient(
        api_key=api_key,
        secret_key=secret,
        paper=True,
    )

    data_client = StockHistoricalDataClient(
        api_key=api_key,
        secret_key=secret,
    )

    return trading_client, data_client


def fetch_signal_data(data_client: StockHistoricalDataClient) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=420)

    request = StockBarsRequest(
        symbol_or_symbols=[SYMBOL],
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )

    bars = data_client.get_stock_bars(request).df

    if bars.empty:
        raise RuntimeError("No bars returned from Alpaca.")

    if isinstance(bars.index, pd.MultiIndex):
        df = bars.loc[SYMBOL].copy()
    else:
        df = bars.copy()

    df = df.sort_index()

    if len(df) < 220:
        raise RuntimeError(f"Need at least 220 bars. Got {len(df)}.")

    df["sma50"] = df["close"].rolling(50).mean()
    df["sma200"] = df["close"].rolling(200).mean()

    return df


def get_current_position_qty(trading_client: TradingClient) -> int:
    try:
        position = trading_client.get_open_position(SYMBOL)
        return int(Decimal(str(position.qty)))
    except Exception:
        return 0


def get_open_orders_for_symbol(trading_client: TradingClient) -> list[dict]:
    orders = trading_client.get_orders()
    open_orders = []

    terminal_statuses = {
        "filled",
        "canceled",
        "cancelled",
        "expired",
        "rejected",
        "stopped",
        "suspended",
    }

    for order in orders:
        symbol = str(getattr(order, "symbol", ""))
        status_raw = getattr(order, "status", "")
        status = str(getattr(status_raw, "value", status_raw)).lower()

        if symbol == SYMBOL and status not in terminal_statuses:
            open_orders.append(
                {
                    "id": str(getattr(order, "id", "")),
                    "symbol": symbol,
                    "side": str(getattr(order, "side", "")),
                    "qty": str(getattr(order, "qty", "")),
                    "status": str(status_raw),
                    "submitted_at": str(getattr(order, "submitted_at", "")),
                }
            )

    return open_orders


def build_signal(df: pd.DataFrame, current_qty: int) -> dict:
    last = df.iloc[-1]

    close = float(last["close"])
    sma50 = float(last["sma50"])
    sma200 = float(last["sma200"])

    signal_in_market = sma50 > sma200
    target_qty = MAX_SHARES_FIRST_RUN if signal_in_market else 0

    if current_qty < target_qty:
        action = "BUY"
        order_qty = target_qty - current_qty
    elif current_qty > target_qty:
        action = "SELL"
        order_qty = current_qty - target_qty
    else:
        action = "HOLD"
        order_qty = 0

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": "QQQ_50_200_cross",
        "symbol": SYMBOL,
        "latest_bar_timestamp": str(df.index[-1]),
        "latest_close": round(close, 4),
        "sma50": round(sma50, 4),
        "sma200": round(sma200, 4),
        "signal_in_market": bool(signal_in_market),
        "current_qty": int(current_qty),
        "target_qty": int(target_qty),
        "action": action,
        "order_qty": int(order_qty),
        "max_shares_first_run": MAX_SHARES_FIRST_RUN,
    }


def submit_paper_order(trading_client: TradingClient, signal: dict) -> dict:
    if signal["action"] == "HOLD":
        return {
            "submitted": False,
            "reason": "HOLD signal. No order needed.",
        }

    side = OrderSide.BUY if signal["action"] == "BUY" else OrderSide.SELL

    order_request = MarketOrderRequest(
        symbol=signal["symbol"],
        qty=signal["order_qty"],
        side=side,
        time_in_force=TimeInForce.DAY,
    )

    order = trading_client.submit_order(order_data=order_request)

    return {
        "submitted": True,
        "order_id": str(order.id),
        "symbol": str(order.symbol),
        "qty": str(order.qty),
        "side": str(order.side),
        "status": str(order.status),
        "submitted_at": str(order.submitted_at),
    }


def append_log(record: dict) -> Path:
    path = LOG_DIR / "qqq_50_200_paper_signal.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def main() -> None:
    enable_orders, mode = safety_checks()

    trading_client, data_client = get_clients()

    account = trading_client.get_account()
    account_status_value = getattr(account.status, "value", str(account.status))
    if str(account_status_value).upper() != "ACTIVE":
        raise RuntimeError(f"Account is not ACTIVE. Status: {account.status}")

    df = fetch_signal_data(data_client)
    current_qty = get_current_position_qty(trading_client)
    open_orders = get_open_orders_for_symbol(trading_client)
    signal = build_signal(df, current_qty)

    execution = {
        "submitted": False,
        "reason": "Signal-only mode. ENABLE_PAPER_ORDERS is not true.",
    }

    if open_orders:
        execution = {
            "submitted": False,
            "reason": "Open QQQ order already exists. Refusing duplicate submission.",
            "open_orders": open_orders,
        }
    elif enable_orders:
        execution = submit_paper_order(trading_client, signal)

    record = {
        "mode": mode,
        "account_status": str(account.status),
        "account_equity": str(account.equity),
        "buying_power": str(account.buying_power),
        "signal": signal,
        "open_orders_before_execution": open_orders,
        "execution": execution,
    }

    log_path = append_log(record)

    print("")
    print("QQQ 50/200 PAPER SIGNAL COMPLETE")
    print("--------------------------------")
    print(json.dumps(record, indent=2))
    print("")
    print(f"Log written to: {log_path}")

    if not enable_orders:
        print("")
        print("No order was submitted. This was signal-only mode.")
    else:
        print("")
        print("Paper order mode was enabled. Check Alpaca paper dashboard.")


if __name__ == "__main__":
    main()



