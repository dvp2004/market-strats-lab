from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "experiments" / "llm_alpaca_paper_bot" / "paper_bot_config.yaml"

config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

required_top = ["paper_only", "orders_enabled", "max_shares", "active_strategy", "preview_strategies"]

missing = [k for k in required_top if k not in config]
if missing:
    raise RuntimeError(f"Missing config keys: {missing}")

if config["paper_only"] is not True:
    raise RuntimeError("paper_only must be true")

if config["orders_enabled"] is not False:
    raise RuntimeError("orders_enabled must remain false for now")

if int(config["max_shares"]) != 1:
    raise RuntimeError("max_shares must remain 1 for now")

active = config["active_strategy"]
for key in ["name", "symbol", "rule_type", "slow"]:
    if key not in active:
        raise RuntimeError(f"active_strategy missing key: {key}")

for s in config["preview_strategies"]:
    for key in ["name", "symbol", "rule_type", "slow"]:
        if key not in s:
            raise RuntimeError(f"preview strategy missing key {key}: {s}")

print("Config check passed.")
print("Active strategy:", active["name"])
print("Preview strategies:", ", ".join(s["name"] for s in config["preview_strategies"]))
