"""Report-only GMA TradingView manual fill validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.global_multi_asset.gma3a_config import GMA3AConfig
from market_strats.global_multi_asset.gma3a_paper_readiness import run_gma3a_paper_readiness


@dataclass(frozen=True)
class GMA3AManualFillValidationResult:
    session_valid: bool
    fills_path: Path
    output_root: Path
    summary_path: Path
    row_validation_path: Path
    reconciliation_path: Path
    accepted_rows: int
    rejected_rows: int
    blocking_reason: str


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _side(row: pd.Series) -> str:
    for column in ["submitted_side", "side"]:
        if column in row.index:
            return _text(row.get(column)).upper()
    return ""


def _account_name(row: pd.Series) -> str:
    for column in ["account_name", "account_id", "paper_account_name"]:
        if column in row.index and _text(row.get(column)):
            return _text(row.get(column))
    return ""


def _account_is_manual_paper(account_name: str) -> bool:
    lowered = account_name.lower()
    return ("tradingview" in lowered and "paper" in lowered) or "manual paper" in lowered


def _flag_true(row: pd.Series, columns: list[str]) -> bool:
    return any(column in row.index and _as_bool(row.get(column)) for column in columns)


def _duplicate_values(frame: pd.DataFrame, column: str) -> set[str]:
    if column not in frame.columns:
        return set()
    values = frame[column].map(_text)
    values = values[values != ""]
    return set(values[values.duplicated(keep=False)])


def _packet_lookup(packet: pd.DataFrame) -> dict[str, pd.Series]:
    if packet.empty or "order_packet_id" not in packet.columns:
        return {}
    return {_text(row.get("order_packet_id")): row for _, row in packet.iterrows()}


def _packet_safety_valid(packet_row: pd.Series) -> bool:
    return (
        _as_bool(packet_row.get("paper_only", False))
        and not _as_bool(packet_row.get("live_trading_allowed", False))
        and not _as_bool(packet_row.get("real_money_allowed", False))
        and not _text(packet_row.get("blocking_reason", ""))
    )


def _validate_fill_row(
    row: pd.Series,
    packet_by_id: dict[str, pd.Series],
    duplicate_fill_ids: set[str],
    duplicate_packet_ids: set[str],
    manual_entry_active: bool,
) -> tuple[bool, str, dict[str, Any]]:
    reasons: list[str] = []
    order_packet_id = _text(row.get("order_packet_id", ""))
    fill_id = _text(row.get("fill_id", ""))
    symbol = _text(row.get("symbol", "")).upper()
    submitted_side = _side(row)
    quantity = _as_float(row.get("filled_quantity", row.get("submitted_quantity", "")))
    fill_price = _as_float(row.get("fill_price", ""))
    fill_timestamp = _text(row.get("fill_timestamp", row.get("filled_at", "")))
    account_name = _account_name(row)

    if not manual_entry_active:
        reasons.append("manual_tradingview_entry_not_active")
    if not order_packet_id:
        reasons.append("order_packet_id_missing")
    if fill_id and fill_id in duplicate_fill_ids:
        reasons.append("duplicate_fill_id")
    if order_packet_id and order_packet_id in duplicate_packet_ids:
        reasons.append("duplicate_order_packet_id_partial_fill_not_supported")
    packet_row = packet_by_id.get(order_packet_id)
    if packet_row is None:
        reasons.append("unknown_order_packet_id")
    else:
        packet_symbol = _text(packet_row.get("symbol", "")).upper()
        packet_side = _text(packet_row.get("side", "")).upper()
        if symbol != packet_symbol:
            reasons.append("symbol_mismatch")
        if submitted_side != packet_side:
            reasons.append("side_mismatch")
        if not _packet_safety_valid(packet_row):
            reasons.append("packet_safety_flags_invalid_or_blocked")
    if not symbol:
        reasons.append("symbol_missing")
    if submitted_side not in {"BUY", "SELL"}:
        reasons.append("side_missing_or_invalid")
    if quantity is None or quantity <= 0:
        reasons.append("filled_quantity_missing_or_non_positive")
    if fill_price is None or fill_price <= 0:
        reasons.append("fill_price_missing_or_non_positive")
    if not fill_timestamp:
        reasons.append("fill_timestamp_missing")
    if not account_name:
        reasons.append("account_name_missing")
    elif not _account_is_manual_paper(account_name):
        reasons.append("account_not_tradingview_manual_paper")
    if _flag_true(row, ["live_trading_allowed", "live_trading", "live_order", "live_order_submitted"]):
        reasons.append("live_trading_flag_present")
    if _flag_true(row, ["real_money_allowed", "real_money", "real_money_order"]):
        reasons.append("real_money_flag_present")
    if _flag_true(
        row,
        [
            "broker_api_submission",
            "broker_api_order_submitted",
            "broker_api_integration_allowed",
            "alpaca_order_submitted",
        ],
    ):
        reasons.append("broker_api_submission_flag_present")

    actual_notional = (quantity or 0.0) * (fill_price or 0.0)
    signed_quantity = 0.0
    cash_impact = 0.0
    if submitted_side == "BUY":
        signed_quantity = quantity or 0.0
        cash_impact = -actual_notional
    elif submitted_side == "SELL":
        signed_quantity = -(quantity or 0.0)
        cash_impact = actual_notional

    values = {
        "order_packet_id": order_packet_id,
        "fill_id": fill_id,
        "symbol": symbol,
        "submitted_side": submitted_side,
        "filled_quantity": quantity if quantity is not None else "",
        "fill_price": fill_price if fill_price is not None else "",
        "fill_timestamp": fill_timestamp,
        "account_name": account_name,
        "actual_notional_usd": actual_notional,
        "signed_quantity": signed_quantity,
        "cash_impact_estimate": cash_impact,
    }
    return not reasons, ";".join(reasons), values


def _build_reconciliation(packet: pd.DataFrame, accepted: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if packet.empty:
        return pd.DataFrame(
            columns=[
                "order_packet_id",
                "symbol",
                "side",
                "current_confirmed_quantity",
                "target_quantity",
                "confirmed_fill_quantity",
                "confirmed_quantity_after_fill",
                "target_vs_confirmed_difference",
                "cash_impact_estimate",
                "manual_paper_only",
                "canonical_holdings_updated",
            ]
        )
    accepted_by_packet = (
        accepted.groupby("order_packet_id", dropna=False)
        .agg({"signed_quantity": "sum", "cash_impact_estimate": "sum"})
        .to_dict("index")
        if not accepted.empty
        else {}
    )
    for _, packet_row in packet.iterrows():
        order_packet_id = _text(packet_row.get("order_packet_id", ""))
        fill = accepted_by_packet.get(order_packet_id, {})
        current_quantity = _as_float(packet_row.get("current_confirmed_quantity", 0)) or 0.0
        target_quantity = _as_float(packet_row.get("target_quantity", 0)) or 0.0
        confirmed_fill_quantity = float(fill.get("signed_quantity", 0.0) or 0.0)
        confirmed_after = current_quantity + confirmed_fill_quantity
        rows.append(
            {
                "order_packet_id": order_packet_id,
                "symbol": _text(packet_row.get("symbol", "")),
                "side": _text(packet_row.get("side", "")),
                "current_confirmed_quantity": current_quantity,
                "target_quantity": target_quantity,
                "confirmed_fill_quantity": confirmed_fill_quantity,
                "confirmed_quantity_after_fill": confirmed_after,
                "target_vs_confirmed_difference": target_quantity - confirmed_after,
                "cash_impact_estimate": float(fill.get("cash_impact_estimate", 0.0) or 0.0),
                "manual_paper_only": True,
                "canonical_holdings_updated": False,
            }
        )
    return pd.DataFrame(rows)


def _write_markdown(path: Path, summary_row: dict[str, Any], reconciliation: pd.DataFrame) -> None:
    reconciliation_text = (
        reconciliation.to_markdown(index=False)
        if not reconciliation.empty
        else "No active packet rows are available for reconciliation."
    )
    lines = [
        "# GMA Manual Fill Validation",
        "",
        "MANUAL PAPER ONLY. NO LIVE TRADING. NO BROKER/API. USER-ENTERED FILLS ONLY.",
        "",
        f"- Session valid: `{summary_row['manual_paper_session_valid']}`",
        f"- Fill ingestion status: `{summary_row['fill_ingestion_status']}`",
        f"- Accepted fill rows: `{summary_row['accepted_fill_rows']}`",
        f"- Rejected fill rows: `{summary_row['rejected_fill_rows']}`",
        f"- Blocking reason: `{summary_row['blocking_reason']}`",
        f"- Canonical holdings updated: `{summary_row['canonical_holdings_updated']}`",
        "",
        "## Reconciliation",
        "",
        reconciliation_text,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def validate_gma3a_manual_fills(config: GMA3AConfig, fills_path: Path) -> GMA3AManualFillValidationResult:
    out = config.paths["output_root"]
    out.mkdir(parents=True, exist_ok=True)
    readiness = run_gma3a_paper_readiness(config)
    packet = _read_csv(out / "gma3a_tradingview_order_packet.csv")
    fills = _read_csv(fills_path)
    packet_by_id = _packet_lookup(packet)
    duplicate_fill_ids = _duplicate_values(fills, "fill_id")
    duplicate_packet_ids = _duplicate_values(fills, "order_packet_id")
    manual_entry_active = readiness.manual_tradingview_entry_active

    row_records: list[dict[str, Any]] = []
    if fills_path.exists() and not fills.empty:
        for index, row in fills.iterrows():
            valid, reasons, values = _validate_fill_row(
                row,
                packet_by_id,
                duplicate_fill_ids,
                duplicate_packet_ids,
                manual_entry_active,
            )
            row_records.append(
                {
                    "row_number": index + 2,
                    "row_valid": valid,
                    "row_blocking_reasons": reasons,
                    **values,
                }
            )
    row_validation = pd.DataFrame(row_records)
    accepted = row_validation[row_validation["row_valid"]].copy() if not row_validation.empty else pd.DataFrame()
    rejected = row_validation[~row_validation["row_valid"]].copy() if not row_validation.empty else pd.DataFrame()
    reconciliation = _build_reconciliation(packet, accepted)

    blocking_reasons: list[str] = []
    if not fills_path.exists():
        blocking_reasons.append("fills_file_missing")
    if not manual_entry_active:
        blocking_reasons.append("manual_tradingview_entry_not_active")
    if rejected.shape[0] > 0:
        blocking_reasons.append("one_or_more_fill_rows_rejected")
    if fills.empty:
        blocking_reasons.append("fills_file_empty")
    session_valid = fills_path.exists() and not fills.empty and manual_entry_active and rejected.empty and not accepted.empty
    status = "valid_manual_paper_fills" if session_valid else "manual_fill_validation_blocked"
    summary_row = {
        "fills_path": str(fills_path),
        "readiness_status": readiness.readiness_status,
        "execution_status": readiness.execution_status,
        "manual_tradingview_entry_active": readiness.manual_tradingview_entry_active,
        "order_packet_rows": readiness.order_packet_rows,
        "fill_ingestion_status": status,
        "manual_paper_session_valid": session_valid,
        "fill_rows_received": int(len(fills)),
        "accepted_fill_rows": int(len(accepted)),
        "rejected_fill_rows": int(len(rejected)),
        "cash_impact_estimate": float(accepted["cash_impact_estimate"].sum()) if not accepted.empty else 0.0,
        "blocking_reason": ";".join(dict.fromkeys(blocking_reasons)),
        "manual_paper_only": True,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
        "canonical_holdings_updated": False,
        "canonical_cash_updated": False,
    }

    summary_path = out / "gma3a_manual_fill_validation_summary.csv"
    row_validation_path = out / "gma3a_manual_fill_row_validation.csv"
    accepted_path = out / "gma3a_manual_fill_accepted.csv"
    rejected_path = out / "gma3a_manual_fill_rejected.csv"
    reconciliation_path = out / "gma3a_manual_fill_reconciliation.csv"
    markdown_path = out / "gma3a_manual_fill_validation.md"

    pd.DataFrame([summary_row]).to_csv(summary_path, index=False)
    row_validation.to_csv(row_validation_path, index=False)
    accepted.to_csv(accepted_path, index=False)
    rejected.to_csv(rejected_path, index=False)
    reconciliation.to_csv(reconciliation_path, index=False)
    _write_markdown(markdown_path, summary_row, reconciliation)

    return GMA3AManualFillValidationResult(
        session_valid=session_valid,
        fills_path=fills_path,
        output_root=out,
        summary_path=summary_path,
        row_validation_path=row_validation_path,
        reconciliation_path=reconciliation_path,
        accepted_rows=int(len(accepted)),
        rejected_rows=int(len(rejected)),
        blocking_reason=summary_row["blocking_reason"],
    )
