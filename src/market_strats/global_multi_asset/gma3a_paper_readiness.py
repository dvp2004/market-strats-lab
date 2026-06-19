"""GMA paper-readiness reporting for manual TradingView packets."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.global_multi_asset.gma3a_config import GMA3AConfig


TARGET_ASSETS = ["SPY", "QQQ", "IEF", "GLD", "DBC"]


@dataclass(frozen=True)
class GMA3APaperReadinessResult:
    readiness_status: str
    execution_status: str
    output_root: Path
    summary_path: Path
    markdown_path: Path
    order_packet_rows: int
    manual_tradingview_entry_active: bool
    blocking_reason: str


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _latest_post_endpoint_dates(data_root: Path) -> dict[str, str]:
    root = data_root / "post_endpoint_market"
    latest: dict[str, str] = {}
    for symbol in TARGET_ASSETS:
        path = root / f"{symbol}_post_endpoint.csv"
        frame = _read_csv(path)
        latest[symbol] = "" if frame.empty or "date" not in frame.columns else str(frame["date"].iloc[-1])
    return latest


def _packet_row_count(packet: pd.DataFrame) -> int:
    if packet.empty:
        return 0
    return int(len(packet))


def _execution_status(blocking_reason: str, expected_execution_date: str, order_packet_rows: int) -> str:
    if blocking_reason.startswith("non_retroactive_execution_block"):
        return "retroactive_blocked"
    if "next_execution_unavailable" in blocking_reason:
        return "data_blocked"
    if blocking_reason:
        return "blocked"
    if order_packet_rows > 0 and expected_execution_date:
        return "valid"
    return "waiting_or_no_packet"


def _readiness_status(execution_status: str, order_packet_rows: int) -> str:
    if execution_status == "valid" and order_packet_rows > 0:
        return "valid"
    return "blocked"


def _write_markdown(path: Path, row: dict[str, Any], packet_preview: pd.DataFrame) -> None:
    packet_table = (
        packet_preview.to_markdown(index=False)
        if not packet_preview.empty
        else "No TradingView manual order packet rows are currently active."
    )
    lines = [
        "# GMA Paper-Readiness Report",
        "",
        "Read-only report. No broker/API calls. No orders submitted.",
        "",
        "## Decision",
        "",
        f"- Readiness status: `{row['readiness_status']}`",
        f"- Execution status: `{row['execution_status']}`",
        f"- Manual TradingView entry active: `{row['manual_tradingview_entry_active']}`",
        f"- Blocking reason: `{row['target_blocking_reason']}`",
        "",
        "## Dates",
        "",
        f"- GMA decision date: `{row['decision_date']}`",
        f"- Expected execution date: `{row['expected_execution_date']}`",
        f"- SPY latest finalized date: `{row['SPY_latest_finalized_date']}`",
        f"- QQQ latest finalized date: `{row['QQQ_latest_finalized_date']}`",
        f"- IEF latest finalized date: `{row['IEF_latest_finalized_date']}`",
        f"- GLD latest finalized date: `{row['GLD_latest_finalized_date']}`",
        f"- DBC latest finalized date: `{row['DBC_latest_finalized_date']}`",
        "",
        "## Safety Flags",
        "",
        f"- paper_only: `{row['paper_only']}`",
        f"- live_trading_allowed: `{row['live_trading_allowed']}`",
        f"- real_money_allowed: `{row['real_money_allowed']}`",
        f"- broker_api_integration_allowed: `{row['broker_api_integration_allowed']}`",
        f"- ml_portfolio_influence: `{row['ml_portfolio_influence']}`",
        "",
        "## Order Packet Preview",
        "",
        packet_table,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_gma3a_paper_readiness(config: GMA3AConfig) -> GMA3APaperReadinessResult:
    out = config.paths["output_root"]
    data_root = config.paths["data_root"]
    out.mkdir(parents=True, exist_ok=True)

    summary = _read_csv(out / "gma3a_summary.csv")
    targets = _read_csv(out / "gma3a_current_strategy_targets.csv")
    packet = _read_csv(out / "gma3a_tradingview_order_packet.csv")
    latest_dates = _latest_post_endpoint_dates(data_root)

    if summary.empty:
        raise FileNotFoundError(out / "gma3a_summary.csv")
    summary_row = summary.iloc[0]
    if targets.empty:
        decision_date = ""
        expected_execution_date = ""
    else:
        decision_date = str(targets.iloc[0].get("decision_date", ""))
        expected_execution_date = str(targets.iloc[0].get("expected_execution_date", ""))

    target_blocking_reason = str(summary_row.get("target_blocking_reason", ""))
    order_packet_rows = _packet_row_count(packet)
    execution_status = _execution_status(
        target_blocking_reason,
        expected_execution_date,
        order_packet_rows,
    )
    readiness_status = _readiness_status(execution_status, order_packet_rows)
    paper_only = _bool_value(summary_row.get("paper_only", False))
    live_trading_allowed = _bool_value(summary_row.get("live_trading_allowed", True))
    real_money_allowed = _bool_value(summary_row.get("real_money_allowed", True))
    broker_api_allowed = _bool_value(summary_row.get("broker_api_integration_allowed", True))
    ml_influence = float(summary_row.get("ml_portfolio_influence", 0) or 0)
    safety_flags_valid = (
        paper_only
        and not live_trading_allowed
        and not real_money_allowed
        and not broker_api_allowed
        and ml_influence == 0
    )
    manual_active = bool(readiness_status == "valid" and order_packet_rows > 0 and safety_flags_valid)

    row: dict[str, Any] = {
        "readiness_status": readiness_status,
        "execution_status": execution_status,
        "manual_tradingview_entry_active": manual_active,
        "decision": summary_row.get("decision", ""),
        "decision_date": decision_date,
        "expected_execution_date": expected_execution_date,
        "target_blocking_reason": target_blocking_reason,
        "order_packet_rows": order_packet_rows,
        "paper_only": paper_only,
        "live_trading_allowed": live_trading_allowed,
        "real_money_allowed": real_money_allowed,
        "broker_api_integration_allowed": broker_api_allowed,
        "ml_portfolio_influence": ml_influence,
        "safety_flags_valid": safety_flags_valid,
    }
    for symbol, latest in latest_dates.items():
        row[f"{symbol}_latest_finalized_date"] = latest

    summary_path = out / "gma3a_paper_readiness_summary.csv"
    markdown_path = out / "gma3a_paper_readiness.md"
    pd.DataFrame([row]).to_csv(summary_path, index=False)
    packet_preview = packet.head(10) if not packet.empty else packet
    _write_markdown(markdown_path, row, packet_preview)

    return GMA3APaperReadinessResult(
        readiness_status=readiness_status,
        execution_status=execution_status,
        output_root=out,
        summary_path=summary_path,
        markdown_path=markdown_path,
        order_packet_rows=order_packet_rows,
        manual_tradingview_entry_active=manual_active,
        blocking_reason=target_blocking_reason,
    )
