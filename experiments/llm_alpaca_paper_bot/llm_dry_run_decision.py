from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import os
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"
LOG_DIR = REPO_ROOT / "paper_bot_logs"
LOG_DIR.mkdir(exist_ok=True)

load_dotenv(dotenv_path=ENV_PATH)


SYMBOLS = ["SPY", "QQQ", "IWM", "GLD", "TLT"]


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def safety_checks() -> None:
    base_url = require_env("APCA_API_BASE_URL")
    bot_mode = require_env("BOT_MODE")
    dry_run = require_env("DRY_RUN")

    if base_url != "https://paper-api.alpaca.markets":
        raise RuntimeError(f"Refusing to run: unsafe Alpaca endpoint: {base_url}")

    if bot_mode != "paper":
        raise RuntimeError(f"Refusing to run: BOT_MODE must be paper, got: {bot_mode}")

    if dry_run.lower() != "true":
        raise RuntimeError("Refusing to run this script unless DRY_RUN=true")

    print("Safety checks passed: paper endpoint + dry-run only.")


def get_account_snapshot() -> dict[str, Any]:
    trading_client = TradingClient(
        api_key=require_env("APCA_API_KEY_ID"),
        secret_key=require_env("APCA_API_SECRET_KEY"),
        paper=True,
    )

    account = trading_client.get_account()
    positions = trading_client.get_all_positions()

    return {
        "status": str(account.status),
        "currency": str(account.currency),
        "equity": float(account.equity),
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "positions": [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "current_price": float(p.current_price),
            }
            for p in positions
        ],
    }


def get_market_features() -> list[dict[str, Any]]:
    data_client = StockHistoricalDataClient(
        api_key=require_env("APCA_API_KEY_ID"),
        secret_key=require_env("APCA_API_SECRET_KEY"),
    )

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=320)

    request = StockBarsRequest(
        symbol_or_symbols=SYMBOLS,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
    )

    bars = data_client.get_stock_bars(request).df

    if bars.empty:
        raise RuntimeError("No market data returned from Alpaca.")

    if not isinstance(bars.index, pd.MultiIndex):
        raise RuntimeError("Unexpected Alpaca bars format.")

    features = []

    for symbol in SYMBOLS:
        if symbol not in bars.index.get_level_values(0):
            print(f"Warning: no bars for {symbol}; skipping.")
            continue

        df = bars.loc[symbol].copy().sort_index()

        if len(df) < 220:
            print(f"Warning: not enough bars for {symbol}; got {len(df)}; skipping.")
            continue

        close = df["close"]

        last_close = float(close.iloc[-1])
        ret_20d = float(close.iloc[-1] / close.iloc[-21] - 1)
        ret_60d = float(close.iloc[-1] / close.iloc[-61] - 1)
        sma_50 = float(close.rolling(50).mean().iloc[-1])
        sma_200 = float(close.rolling(200).mean().iloc[-1])
        vol_20d = float(close.pct_change().rolling(20).std().iloc[-1] * (252 ** 0.5))

        features.append(
            {
                "symbol": symbol,
                "last_close": round(last_close, 4),
                "ret_20d": round(ret_20d, 6),
                "ret_60d": round(ret_60d, 6),
                "vol_20d_annualized": round(vol_20d, 6),
                "above_sma_50": bool(last_close > sma_50),
                "above_sma_200": bool(last_close > sma_200),
                "sma_50": round(sma_50, 4),
                "sma_200": round(sma_200, 4),
            }
        )

    if not features:
        raise RuntimeError("No valid market features created.")

    return features


def ask_llm(account_snapshot: dict[str, Any], market_features: list[dict[str, Any]]) -> dict[str, Any]:
    client = OpenAI(api_key=require_env("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "paper_dry_run_no_orders",
        "allowed_symbols": SYMBOLS,
        "account": account_snapshot,
        "market_features": market_features,
        "rules": {
            "allowed_actions": ["BUY", "SELL", "HOLD"],
            "max_target_weight": 0.20,
            "min_confidence_for_trade": 0.65,
            "no_shorting": True,
            "no_options": True,
            "no_crypto": True,
            "paper_only": True,
            "dry_run": True,
        },
    }

    schema = {
        "type": "json_schema",
        "name": "paper_trade_decision",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string", "enum": SYMBOLS},
                "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                "target_weight": {"type": "number", "minimum": 0, "maximum": 0.20},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reason": {"type": "string"},
                "risk_notes": {"type": "string"},
            },
            "required": [
                "symbol",
                "action",
                "target_weight",
                "confidence",
                "reason",
                "risk_notes",
            ],
        },
    }

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a paper-trading decision engine. "
                    "Use only the supplied market/account data. "
                    "Return one conservative decision. "
                    "If uncertain, choose HOLD. "
                    "Never invent news, prices, positions, or account details."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, indent=2),
            },
        ],
        text={"format": schema},
    )

    return json.loads(response.output_text)


def risk_gate(decision: dict[str, Any], account_snapshot: dict[str, Any]) -> dict[str, Any]:
    accepted = True
    rejection_reasons = []

    if decision["action"] not in {"BUY", "SELL", "HOLD"}:
        accepted = False
        rejection_reasons.append("invalid_action")

    if decision["symbol"] not in SYMBOLS:
        accepted = False
        rejection_reasons.append("symbol_not_allowed")

    if decision["target_weight"] > 0.20:
        accepted = False
        rejection_reasons.append("target_weight_above_limit")

    if decision["confidence"] < 0.65 and decision["action"] != "HOLD":
        accepted = False
        rejection_reasons.append("confidence_below_trade_threshold")

    if account_snapshot["status"] != "ACTIVE":
        accepted = False
        rejection_reasons.append("account_not_active")

    if decision["action"] == "HOLD":
        accepted = True
        rejection_reasons = []

    return {
        "accepted_for_paper_order": False,
        "dry_run": True,
        "would_pass_risk_gate": accepted,
        "rejection_reasons": rejection_reasons,
        "important": "No order was submitted. This is dry-run only.",
    }


def append_log(record: dict[str, Any]) -> Path:
    log_path = LOG_DIR / "llm_alpaca_dry_run_decisions.jsonl"

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")

    return log_path


def main() -> None:
    safety_checks()

    account_snapshot = get_account_snapshot()
    market_features = get_market_features()
    decision = ask_llm(account_snapshot, market_features)
    gate = risk_gate(decision, account_snapshot)

    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "account_snapshot": account_snapshot,
        "market_features": market_features,
        "llm_decision": decision,
        "risk_gate": gate,
    }

    log_path = append_log(record)

    print("")
    print("DRY-RUN DECISION COMPLETE")
    print("-------------------------")
    print("Decision:", json.dumps(decision, indent=2))
    print("Risk gate:", json.dumps(gate, indent=2))
    print("Log written to:", log_path)
    print("")
    print("No order was submitted.")


if __name__ == "__main__":
    main()
