from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
import os

import pandas as pd
import yaml
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient


REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = REPO_ROOT / "experiments" / "llm_alpaca_paper_bot"
LOG_DIR = REPO_ROOT / "paper_bot_logs"

ENV_PATH = REPO_ROOT / ".env"
CONFIG_PATH = EXP_DIR / "paper_bot_config.yaml"

PREVIEW_CSV = LOG_DIR / "latest_ma_parallel_signal_preview.csv"
CANDIDATE_SUMMARY = LOG_DIR / "paper_candidate_selection_summary.csv"
CANDIDATE_REPORT = LOG_DIR / "paper_candidate_selection_report.md"

OUT_MD = LOG_DIR / "daily_paper_status_report.md"
OUT_JSON = LOG_DIR / "daily_paper_status_snapshot.json"
OUT_JSONL = LOG_DIR / "daily_paper_status_history.jsonl"

load_dotenv(dotenv_path=ENV_PATH)


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def enum_value(x) -> str:
    if x is None:
        return ""
    return str(getattr(x, "value", x))


def safety_checks(config: dict) -> None:
    base_url = env_required("APCA_API_BASE_URL")
    bot_mode = env_required("BOT_MODE")

    if base_url != "https://paper-api.alpaca.markets":
        raise RuntimeError(f"Refusing to run: unsafe endpoint {base_url}")

    if bot_mode != "paper":
        raise RuntimeError(f"Refusing to run: BOT_MODE must be paper, got {bot_mode}")

    if config.get("paper_only") is not True:
        raise RuntimeError("Config paper_only must be true.")

    if config.get("orders_enabled") is not False:
        raise RuntimeError("Config orders_enabled must be false for now.")

    if os.getenv("ENABLE_PAPER_ORDERS", "false").strip().lower() == "true":
        raise RuntimeError("Refusing status report while ENABLE_PAPER_ORDERS=true.")

    if int(config.get("max_shares", 0)) != 1:
        raise RuntimeError("max_shares must remain 1 for now.")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Missing config: {CONFIG_PATH}")
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def get_trading_client() -> TradingClient:
    return TradingClient(
        api_key=env_required("APCA_API_KEY_ID"),
        secret_key=env_required("APCA_API_SECRET_KEY"),
        paper=True,
    )


def get_account_snapshot(client: TradingClient) -> dict:
    account = client.get_account()
    return {
        "status": enum_value(getattr(account, "status", None)),
        "equity": str(getattr(account, "equity", "")),
        "cash": str(getattr(account, "cash", "")),
        "buying_power": str(getattr(account, "buying_power", "")),
        "portfolio_value": str(getattr(account, "portfolio_value", "")),
    }


def get_position_snapshot(client: TradingClient, symbol: str) -> dict | None:
    try:
        pos = client.get_open_position(symbol)
    except Exception:
        return None

    return {
        "symbol": getattr(pos, "symbol", symbol),
        "qty": str(getattr(pos, "qty", "")),
        "market_value": str(getattr(pos, "market_value", "")),
        "avg_entry_price": str(getattr(pos, "avg_entry_price", "")),
        "current_price": str(getattr(pos, "current_price", "")),
        "unrealized_pl": str(getattr(pos, "unrealized_pl", "")),
        "unrealized_plpc": str(getattr(pos, "unrealized_plpc", "")),
    }


def get_relevant_orders(client: TradingClient, symbol: str) -> list[dict]:
    try:
        orders = client.get_orders()
    except Exception as e:
        return [{"error": f"Could not fetch orders: {e}"}]

    rows = []
    terminal = {"filled", "canceled", "expired", "rejected", "replaced"}

    for o in orders:
        if getattr(o, "symbol", None) != symbol:
            continue

        status = enum_value(getattr(o, "status", None)).lower()

        rows.append(
            {
                "id": str(getattr(o, "id", "")),
                "symbol": getattr(o, "symbol", ""),
                "side": enum_value(getattr(o, "side", "")),
                "qty": str(getattr(o, "qty", "")),
                "filled_qty": str(getattr(o, "filled_qty", "")),
                "status": enum_value(getattr(o, "status", "")),
                "submitted_at": str(getattr(o, "submitted_at", "")),
                "filled_at": str(getattr(o, "filled_at", "")),
                "is_terminal": status in terminal,
            }
        )

    return rows


def read_latest_preview() -> list[dict]:
    if not PREVIEW_CSV.exists():
        return []

    df = pd.read_csv(PREVIEW_CSV)
    return df.to_dict(orient="records")


def read_candidate_summary_top() -> list[dict]:
    if not CANDIDATE_SUMMARY.exists():
        return []

    df = pd.read_csv(CANDIDATE_SUMMARY)
    return df.head(10).to_dict(orient="records")


def md_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "_No data available._"

    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"

    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")

    return "\n".join([header, sep] + body)


def write_report(snapshot: dict) -> None:
    preview_rows = snapshot["latest_signal_preview"]
    order_rows = snapshot["qqq_orders"]
    position = snapshot["qqq_position"]
    account = snapshot["account"]
    config = snapshot["config"]

    active = config["active_strategy"]
    previews = config.get("preview_strategies", [])

    active_preview = [r for r in preview_rows if r.get("role") == "active_default"]
    preview_candidates = [r for r in preview_rows if r.get("role") == "preview_candidate"]

    active_action = active_preview[0].get("preview_action", "") if active_preview else ""
    all_agree = bool(preview_candidates) and all(r.get("preview_action") == active_action for r in preview_candidates)

    md = f"""# Daily Paper Status Report

Generated UTC: `{snapshot["timestamp_utc"]}`

## Safety

- Paper only: `{config.get("paper_only")}`
- Orders enabled in config: `{config.get("orders_enabled")}`
- Max shares: `{config.get("max_shares")}`
- No order submission performed by this report.

## Active / Preview Strategy Config

| Role | Strategy | Symbol | Rule | Fast | Slow |
|---|---|---|---|---|---|
| Active | `{active.get("name")}` | `{active.get("symbol")}` | `{active.get("rule_type")}` | `{active.get("fast")}` | `{active.get("slow")}` |
"""

    for p in previews:
        md += f"| Preview | `{p.get('name')}` | `{p.get('symbol')}` | `{p.get('rule_type')}` | `{p.get('fast')}` | `{p.get('slow')}` |\n"

    md += f"""

## Latest Signal Preview

{md_table(preview_rows, ["role", "strategy", "symbol", "rule_type", "fast", "slow", "latest_close", "fast_ma", "slow_ma", "signal_in_market", "preview_action"])}

Signal agreement with active: `{all_agree}`

## Alpaca Paper Account

| Field | Value |
|---|---|
| Status | `{account.get("status")}` |
| Equity | `{account.get("equity")}` |
| Cash | `{account.get("cash")}` |
| Buying power | `{account.get("buying_power")}` |
| Portfolio value | `{account.get("portfolio_value")}` |

## QQQ Position

"""

    if position:
        md += md_table([position], ["symbol", "qty", "market_value", "avg_entry_price", "current_price", "unrealized_pl", "unrealized_plpc"])
    else:
        md += "_No open QQQ position found._"

    md += f"""

## QQQ Orders

{md_table(order_rows, ["id", "symbol", "side", "qty", "filled_qty", "status", "submitted_at", "filled_at", "is_terminal"])}

## Current Decision

- Keep active default as `QQQ_50_200_cross`.
- Keep `QQQ_75_250_cross` as no-order preview candidate.
- Do not submit more orders.
- Do not scale above 1 share.
- Next research step: walk-forward validation for QQQ MA candidates.
"""

    OUT_MD.write_text(md, encoding="utf-8")


def main() -> None:
    config = load_config()
    safety_checks(config)

    symbol = config["active_strategy"]["symbol"]

    client = get_trading_client()

    snapshot = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(CONFIG_PATH),
        "config": config,
        "account": get_account_snapshot(client),
        "qqq_position": get_position_snapshot(client, symbol),
        "qqq_orders": get_relevant_orders(client, symbol),
        "latest_signal_preview": read_latest_preview(),
        "candidate_summary_top": read_candidate_summary_top(),
        "candidate_report_exists": CANDIDATE_REPORT.exists(),
    }

    OUT_JSON.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    with OUT_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, sort_keys=True) + "\n")

    write_report(snapshot)

    print("")
    print("DAILY PAPER STATUS REPORT COMPLETE")
    print("----------------------------------")
    print("Account:", snapshot["account"])
    print("QQQ position:", snapshot["qqq_position"])
    print("QQQ orders:", snapshot["qqq_orders"])
    print("")
    print(f"Markdown report: {OUT_MD}")
    print(f"JSON snapshot:   {OUT_JSON}")
    print(f"JSONL history:   {OUT_JSONL}")
    print("")
    print("No orders were submitted.")


if __name__ == "__main__":
    main()
