from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import os

import pandas as pd
import yaml
from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed


REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = REPO_ROOT / "experiments" / "llm_alpaca_paper_bot"
ENV_PATH = REPO_ROOT / ".env"
CONFIG_PATH = Path(os.getenv("PAPER_BOT_CONFIG_PATH", str(EXP_DIR / "paper_bot_config.yaml")))
LOG_DIR = REPO_ROOT / "paper_bot_logs"
LOG_DIR.mkdir(exist_ok=True)

load_dotenv(dotenv_path=ENV_PATH)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Missing config file: {CONFIG_PATH}")

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    if not isinstance(config, dict):
        raise RuntimeError("Config file did not parse as a dictionary.")

    required = ["paper_only", "orders_enabled", "max_shares", "active_strategy", "preview_strategies"]
    missing = [k for k in required if k not in config]
    if missing:
        raise RuntimeError(f"Config missing required keys: {missing}")

    return config


def safety_checks(config: dict) -> None:
    base_url = require_env("APCA_API_BASE_URL")
    bot_mode = require_env("BOT_MODE")

    if base_url != "https://paper-api.alpaca.markets":
        raise RuntimeError(f"Refusing to run: unsafe Alpaca endpoint: {base_url}")

    if bot_mode != "paper":
        raise RuntimeError(f"Refusing to run: BOT_MODE must be paper, got: {bot_mode}")

    if config.get("paper_only") is not True:
        raise RuntimeError("Refusing to run: config paper_only must be true.")

    if config.get("orders_enabled") is not False:
        raise RuntimeError("Refusing to run preview: config orders_enabled must be false.")

    enable_orders_env = os.getenv("ENABLE_PAPER_ORDERS", "false").strip().lower()
    if enable_orders_env == "true":
        raise RuntimeError("Refusing to run preview while ENABLE_PAPER_ORDERS=true.")

    if int(config.get("max_shares", 0)) != 1:
        raise RuntimeError("For now, config max_shares must remain 1.")

    print("Safety checks passed. Config-driven preview-only mode. No orders can be submitted.")


def collect_strategy_specs(config: dict) -> list[dict]:
    active = dict(config["active_strategy"])
    active["role"] = "active_default"

    previews = []
    for item in config.get("preview_strategies", []):
        spec = dict(item)
        spec["role"] = "preview_candidate"
        previews.append(spec)

    specs = [active] + previews

    seen_names = set()
    for spec in specs:
        for key in ["name", "symbol", "rule_type", "slow"]:
            if key not in spec:
                raise RuntimeError(f"Strategy spec missing key {key}: {spec}")

        if spec["name"] in seen_names:
            raise RuntimeError(f"Duplicate strategy name in config: {spec['name']}")
        seen_names.add(spec["name"])

        if spec["rule_type"] == "cross" and spec.get("fast") is None:
            raise RuntimeError(f"Cross strategy missing fast MA: {spec}")

        if spec["rule_type"] not in {"cross", "above_ma"}:
            raise RuntimeError(f"Unsupported rule_type: {spec}")

    return specs


def fetch_bars(symbols: list[str], max_slow: int) -> pd.DataFrame:
    client = StockHistoricalDataClient(
        api_key=require_env("APCA_API_KEY_ID"),
        secret_key=require_env("APCA_API_SECRET_KEY"),
    )

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=max(800, int(max_slow * 4)))

    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )

    bars = client.get_stock_bars(request).df

    if bars.empty:
        raise RuntimeError("No market bars returned.")

    if not isinstance(bars.index, pd.MultiIndex):
        raise RuntimeError("Expected Alpaca bars to return a MultiIndex dataframe.")

    close_by_symbol = {}

    for symbol in symbols:
        if symbol not in bars.index.get_level_values(0):
            raise RuntimeError(f"No bars returned for symbol: {symbol}")

        df = bars.loc[symbol].sort_index().copy()

        if len(df) < max_slow + 5:
            raise RuntimeError(f"Need at least {max_slow + 5} daily bars for {symbol}. Got {len(df)}.")

        close_by_symbol[symbol] = df["close"]

    close = pd.DataFrame(close_by_symbol).sort_index().ffill().dropna(how="all")

    return close


def evaluate_strategy(close: pd.DataFrame, spec: dict) -> dict:
    symbol = spec["symbol"]
    series = close[symbol].dropna()

    slow = int(spec["slow"])
    slow_ma = series.rolling(slow).mean().iloc[-1]
    latest_close = series.iloc[-1]
    latest_bar_timestamp = series.index[-1]

    fast_ma = None

    if pd.isna(slow_ma):
        raise RuntimeError(f"Slow MA unavailable for {spec['name']}")

    if spec["rule_type"] == "cross":
        fast = int(spec["fast"])
        fast_ma = series.rolling(fast).mean().iloc[-1]

        if pd.isna(fast_ma):
            raise RuntimeError(f"Fast MA unavailable for {spec['name']}")

        signal_in_market = bool(fast_ma > slow_ma)

    elif spec["rule_type"] == "above_ma":
        signal_in_market = bool(latest_close > slow_ma)

    else:
        raise RuntimeError(f"Unsupported rule_type: {spec['rule_type']}")

    return {
        "role": spec["role"],
        "strategy": spec["name"],
        "symbol": symbol,
        "rule_type": spec["rule_type"],
        "fast": spec.get("fast"),
        "slow": spec.get("slow"),
        "latest_bar_timestamp": str(latest_bar_timestamp),
        "latest_close": round(float(latest_close), 4),
        "fast_ma": None if fast_ma is None else round(float(fast_ma), 4),
        "slow_ma": round(float(slow_ma), 4),
        "signal_in_market": signal_in_market,
        "preview_action": "TARGET_QQQ" if signal_in_market else "TARGET_CASH",
    }


def append_jsonl(record: dict) -> Path:
    path = LOG_DIR / "ma_parallel_signal_preview.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def main() -> None:
    config = load_config()
    safety_checks(config)

    specs = collect_strategy_specs(config)
    symbols = sorted(set(spec["symbol"] for spec in specs))
    max_slow = max(int(spec["slow"]) for spec in specs)

    close = fetch_bars(symbols=symbols, max_slow=max_slow)
    results = [evaluate_strategy(close, spec) for spec in specs]

    active = [r for r in results if r["role"] == "active_default"][0]
    previews = [r for r in results if r["role"] == "preview_candidate"]

    all_agree = all(p["preview_action"] == active["preview_action"] for p in previews)

    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "config_driven_preview_only_no_orders",
        "config_path": str(CONFIG_PATH),
        "active_strategy": active["strategy"],
        "active_action": active["preview_action"],
        "all_preview_strategies_agree_with_active": bool(all_agree),
        "results": results,
    }

    jsonl_path = append_jsonl(record)

    out_csv = LOG_DIR / "latest_ma_parallel_signal_preview.csv"
    pd.DataFrame(results).to_csv(out_csv, index=False)

    print("")
    print("CONFIG-DRIVEN MA PARALLEL SIGNAL PREVIEW COMPLETE")
    print("-------------------------------------------------")
    print(pd.DataFrame(results).to_string(index=False))
    print("")
    print("Active strategy:", active["strategy"])
    print("Active action:", active["preview_action"])
    print("All previews agree with active:", bool(all_agree))
    print("")
    print(f"JSONL log written to: {jsonl_path}")
    print(f"Latest CSV written to: {out_csv}")
    print("")
    print("No orders were submitted.")


if __name__ == "__main__":
    main()

