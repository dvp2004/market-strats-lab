from __future__ import annotations

from pathlib import Path
import os
import json
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH)

SYMBOL = "QQQ"


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


def main() -> None:
    safety_checks()

    client = TradingClient(
        api_key=require_env("APCA_API_KEY_ID"),
        secret_key=require_env("APCA_API_SECRET_KEY"),
        paper=True,
    )

    account = client.get_account()

    orders = client.get_orders()
    qqq_orders = []

    for order in orders:
        if str(getattr(order, "symbol", "")) == SYMBOL:
            qqq_orders.append(
                {
                    "id": str(getattr(order, "id", "")),
                    "symbol": str(getattr(order, "symbol", "")),
                    "side": str(getattr(order, "side", "")),
                    "qty": str(getattr(order, "qty", "")),
                    "filled_qty": str(getattr(order, "filled_qty", "")),
                    "status": str(getattr(order, "status", "")),
                    "submitted_at": str(getattr(order, "submitted_at", "")),
                    "filled_at": str(getattr(order, "filled_at", "")),
                }
            )

    try:
        position = client.get_open_position(SYMBOL)
        qqq_position = {
            "symbol": position.symbol,
            "qty": str(position.qty),
            "market_value": str(position.market_value),
            "avg_entry_price": str(position.avg_entry_price),
            "current_price": str(position.current_price),
            "unrealized_pl": str(position.unrealized_pl),
            "unrealized_plpc": str(position.unrealized_plpc),
        }
    except Exception:
        qqq_position = None

    output = {
        "account_status": str(account.status),
        "account_equity": str(account.equity),
        "buying_power": str(account.buying_power),
        "qqq_open_or_recent_orders": qqq_orders,
        "qqq_position": qqq_position,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
