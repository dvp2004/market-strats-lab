from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import os
import math

import pandas as pd
import yaml
from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce


REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = REPO_ROOT / "experiments" / "llm_alpaca_paper_bot"
LOG_DIR = REPO_ROOT / "paper_bot_logs"
ENV_PATH = REPO_ROOT / ".env"

CONFIG_PATH = Path(os.getenv("PAPER_BOT_CONFIG_PATH", str(EXP_DIR / "paper_bot_config.yaml")))
LOG_PATH = LOG_DIR / "config_driven_paper_signal.jsonl"

LOG_DIR.mkdir(exist_ok=True)
load_dotenv(ENV_PATH)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def enum_value(x) -> str:
    return str(getattr(x, "value", x))


def load_config() -> dict:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    if config.get("paper_only") is not True:
        raise RuntimeError("paper_only must be true")

    if int(config.get("max_shares", 0)) != 1:
        raise RuntimeError("max_shares must remain 1 for now")

    return config


def safety_env() -> dict:
    base_url = require_env("APCA_API_BASE_URL")
    bot_mode = require_env("BOT_MODE")
    dry_run = os.getenv("DRY_RUN", "true").strip().lower()
    enable_orders_env = os.getenv("ENABLE_PAPER_ORDERS", "false").strip().lower()

    if base_url != "https://paper-api.alpaca.markets":
        raise RuntimeError(f"Unsafe endpoint: {base_url}")

    if bot_mode != "paper":
        raise RuntimeError(f"BOT_MODE must be paper, got {bot_mode}")

    return {
        "base_url": base_url,
        "bot_mode": bot_mode,
        "dry_run": dry_run,
        "enable_orders_env": enable_orders_env,
    }


def data_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(
        api_key=require_env("APCA_API_KEY_ID"),
        secret_key=require_env("APCA_API_SECRET_KEY"),
    )


def trading_client() -> TradingClient:
    return TradingClient(
        api_key=require_env("APCA_API_KEY_ID"),
        secret_key=require_env("APCA_API_SECRET_KEY"),
        paper=True,
    )


def fetch_close(symbol: str, min_bars: int) -> pd.Series:
    client = data_client()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=max(800, min_bars * 4))

    req = StockBarsRequest(
        symbol_or_symbols=[symbol],
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )

    bars = client.get_stock_bars(req).df

    if bars.empty:
        raise RuntimeError("No bars returned")

    if isinstance(bars.index, pd.MultiIndex):
        df = bars.loc[symbol].sort_index()
    else:
        df = bars.sort_index()

    close = df["close"].dropna()

    if len(close) < min_bars:
        raise RuntimeError(f"Need {min_bars} bars, got {len(close)}")

    return close


def evaluate_signal(spec: dict) -> dict:
    symbol = spec["symbol"]
    rule_type = spec["rule_type"]
    slow = int(spec["slow"])
    fast = spec.get("fast")

    min_bars = slow + 5
    close = fetch_close(symbol, min_bars)

    latest_close = float(close.iloc[-1])
    slow_ma = float(close.rolling(slow).mean().iloc[-1])

    fast_ma = None

    if rule_type == "cross":
        fast = int(fast)
        fast_ma = float(close.rolling(fast).mean().iloc[-1])
        signal_in_market = bool(fast_ma > slow_ma)
    elif rule_type == "above_ma":
        signal_in_market = bool(latest_close > slow_ma)
    else:
        raise RuntimeError(f"Unsupported rule_type: {rule_type}")

    return {
        "strategy": spec["name"],
        "symbol": symbol,
        "rule_type": rule_type,
        "fast": fast,
        "slow": slow,
        "latest_bar_timestamp": str(close.index[-1]),
        "latest_close": round(latest_close, 4),
        "fast_ma": None if fast_ma is None else round(fast_ma, 4),
        "slow_ma": round(slow_ma, 4),
        "signal_in_market": signal_in_market,
    }


def get_position_qty(client: TradingClient, symbol: str) -> int:
    try:
        pos = client.get_open_position(symbol)
        return int(float(pos.qty))
    except Exception:
        return 0


def get_open_orders(client: TradingClient, symbol: str) -> list[dict]:
    orders = client.get_orders()
    terminal = {"filled", "canceled", "expired", "rejected", "replaced"}

    rows = []

    for o in orders:
        if getattr(o, "symbol", None) != symbol:
            continue

        status = enum_value(getattr(o, "status", "")).lower()

        if status in terminal:
            continue

        rows.append(
            {
                "id": str(getattr(o, "id", "")),
                "symbol": getattr(o, "symbol", ""),
                "side": enum_value(getattr(o, "side", "")),
                "qty": str(getattr(o, "qty", "")),
                "filled_qty": str(getattr(o, "filled_qty", "")),
                "status": enum_value(getattr(o, "status", "")),
                "submitted_at": str(getattr(o, "submitted_at", "")),
            }
        )

    return rows


def submit_order(client: TradingClient, symbol: str, side: str, qty: int):
    order_side = OrderSide.BUY if side == "BUY" else OrderSide.SELL

    req = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=order_side,
        time_in_force=TimeInForce.DAY,
    )

    return client.submit_order(req)


def main() -> None:
    config = load_config()
    env = safety_env()

    active = config["active_strategy"]
    symbol = active["symbol"]
    max_shares = int(config["max_shares"])

    signal = evaluate_signal(active)

    tclient = trading_client()
    account = tclient.get_account()
    clock = tclient.get_clock()

    current_qty = get_position_qty(tclient, symbol)
    target_qty = max_shares if signal["signal_in_market"] else 0

    if target_qty > current_qty:
        action = "BUY"
        order_qty = target_qty - current_qty
    elif target_qty < current_qty:
        action = "SELL"
        order_qty = current_qty - target_qty
    else:
        action = "HOLD"
        order_qty = 0

    open_orders = get_open_orders(tclient, symbol)

    config_orders_enabled = bool(config.get("orders_enabled", False))
    env_orders_enabled = env["enable_orders_env"] == "true"
    dry_run = env["dry_run"] == "true"

    execution = {
        "submitted": False,
        "reason": "",
    }

    if action == "HOLD":
        execution["reason"] = "Target already satisfied."

    elif open_orders:
        execution["reason"] = "Open order already exists. Refusing duplicate submission."

    elif not clock.is_open:
        execution["reason"] = "Market is closed. Refusing to queue new order."

    elif not config_orders_enabled:
        execution["reason"] = "Config orders_enabled=false."

    elif not env_orders_enabled:
        execution["reason"] = "ENABLE_PAPER_ORDERS is not true."

    elif dry_run:
        execution["reason"] = "DRY_RUN=true."

    else:
        order = submit_order(tclient, symbol, action, order_qty)
        execution = {
            "submitted": True,
            "order_id": str(order.id),
            "symbol": order.symbol,
            "side": enum_value(order.side),
            "qty": str(order.qty),
            "status": enum_value(order.status),
            "submitted_at": str(order.submitted_at),
        }

    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "config_driven_paper_signal",
        "config_path": str(CONFIG_PATH),
        "account_status": enum_value(account.status),
        "equity": str(account.equity),
        "buying_power": str(account.buying_power),
        "market_clock": {
            "timestamp": str(clock.timestamp),
            "is_open": bool(clock.is_open),
            "next_open": str(clock.next_open),
            "next_close": str(clock.next_close),
        },
        "signal": signal,
        "current_qty": current_qty,
        "target_qty": target_qty,
        "action": action,
        "order_qty": order_qty,
        "open_orders_before_execution": open_orders,
        "safety": {
            "config_orders_enabled": config_orders_enabled,
            "env_orders_enabled": env_orders_enabled,
            "dry_run": dry_run,
            "paper_only": config.get("paper_only"),
            "max_shares": max_shares,
        },
        "execution": execution,
    }

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")

    print("")
    print("CONFIG-DRIVEN PAPER SIGNAL COMPLETE")
    print("-----------------------------------")
    print(json.dumps(record, indent=2, sort_keys=True))
    print("")
    print(f"Log written to: {LOG_PATH}")


if __name__ == "__main__":
    main()
