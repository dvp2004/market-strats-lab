from pathlib import Path
import os
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"

if not ENV_PATH.exists():
    raise RuntimeError(f"Missing .env file at: {ENV_PATH}")

load_dotenv(dotenv_path=ENV_PATH)

required = [
    "OPENAI_API_KEY",
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "APCA_API_BASE_URL",
    "BOT_MODE",
    "DRY_RUN",
]

missing = [k for k in required if not os.getenv(k)]
if missing:
    raise RuntimeError(f"Missing environment variables: {missing}")

placeholders = []
for key in required:
    value = os.getenv(key, "")
    lowered = value.lower()
    if "your_" in lowered or "xxxx" in lowered or "placeholder" in lowered:
        placeholders.append(key)

if placeholders:
    raise RuntimeError(f"Still using placeholder values for: {placeholders}")

base_url = os.getenv("APCA_API_BASE_URL", "")
bot_mode = os.getenv("BOT_MODE", "")
dry_run = os.getenv("DRY_RUN", "")

if base_url != "https://paper-api.alpaca.markets":
    raise RuntimeError(f"Refusing to run: unsafe Alpaca endpoint: {base_url}")

if bot_mode != "paper":
    raise RuntimeError(f"Refusing to run: BOT_MODE must be paper, got: {bot_mode}")

if dry_run.lower() not in {"true", "false"}:
    raise RuntimeError(f"DRY_RUN must be true or false, got: {dry_run}")

def mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]

print("Environment safety check passed.")
print("OpenAI key:", mask(os.getenv("OPENAI_API_KEY", "")))
print("Alpaca key ID:", mask(os.getenv("APCA_API_KEY_ID", "")))
print("Alpaca endpoint:", base_url)
print("Bot mode:", bot_mode)
print("Dry run:", dry_run)
