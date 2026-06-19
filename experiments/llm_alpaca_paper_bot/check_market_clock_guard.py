from __future__ import annotations

from pathlib import Path
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient


REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value


def main() -> None:
    base_url = require_env("APCA_API_BASE_URL")
    bot_mode = require_env("BOT_MODE")

    if base_url != "https://paper-api.alpaca.markets":
        raise RuntimeError(f"Unsafe endpoint: {base_url}")

    if bot_mode != "paper":
        raise RuntimeError(f"BOT_MODE must be paper, got {bot_mode}")

    client = TradingClient(
        api_key=require_env("APCA_API_KEY_ID"),
        secret_key=require_env("APCA_API_SECRET_KEY"),
        paper=True,
    )

    clock = client.get_clock()

    print("ALPACA MARKET CLOCK")
    print("-------------------")
    print("timestamp:", clock.timestamp)
    print("is_open:", clock.is_open)
    print("next_open:", clock.next_open)
    print("next_close:", clock.next_close)

    if not clock.is_open:
        print("")
        print("Guard decision: BLOCK_NEW_ORDERS")
    else:
        print("")
        print("Guard decision: MARKET_OPEN")


if __name__ == "__main__":
    main()
