from pathlib import Path
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

api_key = os.getenv("APCA_API_KEY_ID")
secret_key = os.getenv("APCA_API_SECRET_KEY")
base_url = os.getenv("APCA_API_BASE_URL")
bot_mode = os.getenv("BOT_MODE")

if base_url != "https://paper-api.alpaca.markets":
    raise RuntimeError(f"Refusing to run: unsafe Alpaca endpoint: {base_url}")

if bot_mode != "paper":
    raise RuntimeError(f"Refusing to run: BOT_MODE must be paper, got: {bot_mode}")

client = TradingClient(
    api_key=api_key,
    secret_key=secret_key,
    paper=True,
)

account = client.get_account()

print("Alpaca paper connection passed.")
print("Account status:", account.status)
print("Currency:", account.currency)
print("Paper equity:", account.equity)
print("Buying power:", account.buying_power)
print("Pattern day trader:", account.pattern_day_trader)
