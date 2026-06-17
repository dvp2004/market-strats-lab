from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.pilot_individual_equity_feature_calculation import (
    normalize_price_frame,
)
from market_strats.analysis.prospective_shadow_monitoring import (
    PILOT_UNIVERSE,
    REQUIRED_MODEL_HASH,
    REQUIRED_MODEL_ID,
)


PHASE23L_SECTION = "phase23l_operational_paper_bridge"

DEFAULT_PHASE23L_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": "reports/individual_equity_shadow/phase23l_operational_paper_bridge",
    "dashboard_status_path": "reports/paper_trading/dashboard/phase23l_operational_paper_bridge_status.csv",
    "source_phase23i_shadow_dir": "reports/individual_equity_shadow/phase23i_prospective_shadow",
    "source_phase23j_dir": (
        "reports/individual_equity_decision_system/"
        "phase23j_post_endpoint_individual_equity_extension"
    ),
    "source_phase23k_dir": "reports/individual_equity_shadow/phase23k_prospective_monitoring",
    "combined_input_dir": "data/individual_equity_post_endpoint/combined",
    "post_endpoint_input_dir": "data/individual_equity_post_endpoint",
    "pilot_input_dir": "data/individual_equity_pilot",
    "portfolio_id": "ridge_top5_equal_weight",
    "manual_fill_filename": "phase23l_tradingview_manual_fills.csv",
    "paper_only": True,
    "live_trading_allowed": False,
    "real_money_allowed": False,
    "broker_api_integration_allowed": False,
    "promotion_allowed": False,
}

POSITION_VALUATION_COLUMNS = [
    "valuation_date",
    "session_id",
    "portfolio_id",
    "ticker",
    "shares",
    "entry_price",
    "current_close",
    "position_cost_basis",
    "current_market_value",
    "unrealized_pnl",
    "unrealized_return",
    "cash_balance",
    "total_portfolio_value",
    "daily_portfolio_return",
    "cumulative_portfolio_return",
    "running_peak_value",
    "drawdown",
    "price_date",
    "price_complete",
    "valuation_status",
]

PORTFOLIO_VALUATION_COLUMNS = [
    "valuation_date",
    "session_id",
    "portfolio_id",
    "market_value",
    "cash_balance",
    "total_portfolio_value",
    "daily_portfolio_return",
    "cumulative_portfolio_return",
    "running_peak_value",
    "drawdown",
    "valuation_status",
]

ORDER_PACKET_COLUMNS = [
    "order_packet_id",
    "session_id",
    "model_id",
    "model_hash",
    "signal_date",
    "expected_execution_date",
    "ticker",
    "side",
    "current_confirmed_shares",
    "target_shares",
    "order_quantity",
    "target_weight",
    "reference_price",
    "reference_price_date",
    "expected_execution_price",
    "order_status",
    "paper_only",
    "live_trading_allowed",
    "real_money_allowed",
    "blocking_reason",
]

FILL_TEMPLATE_COLUMNS = [
    "order_packet_id",
    "session_id",
    "ticker",
    "submitted_quantity",
    "submitted_side",
    "submitted_at",
    "fill_status",
    "filled_quantity",
    "fill_price",
    "fill_timestamp",
    "rejection_reason",
    "partial_fill_reason",
    "notes",
]

ALLOWED_FILL_STATUSES = {
    "not_submitted",
    "submitted",
    "filled",
    "partially_filled",
    "rejected",
    "cancelled",
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(DEFAULT_PHASE23L_CONFIG, config.get(PHASE23L_SECTION, {}))


def _resolve_reports_path(*, configured_path: str | Path, reports_dir: str | Path) -> Path:
    reports_root = Path(reports_dir)
    path = Path(configured_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == "reports":
        return reports_root.joinpath(*path.parts[1:])
    return reports_root / path


def _resolve_project_path(*, configured_path: str | Path, reports_dir: str | Path) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path
    return Path(reports_dir).parent / path


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(frame: pd.DataFrame, path: Path, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    working = frame.copy()
    if columns is not None:
        for column in columns:
            if column not in working.columns:
                working[column] = pd.Series(dtype="object")
        working = working[columns]
    temporary = path.with_suffix(path.suffix + ".tmp")
    working.to_csv(temporary, index=False)
    temporary.replace(path)


def _write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = np.nan) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(parsed) if pd.notna(parsed) else default


def _safe_int(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return default
    return int(float(parsed))


def _date_string(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return pd.Timestamp(parsed).date().isoformat()


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _price_filename(ticker: str) -> str:
    return "benchmark_SPY.csv" if ticker == "SPY" else f"{ticker}.csv"


def _load_price_frames(*, combined_dir: Path, post_dir: Path, pilot_dir: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for ticker in [*PILOT_UNIVERSE, "SPY"]:
        for directory in [combined_dir, post_dir, pilot_dir]:
            path = directory / _price_filename(ticker)
            if path.exists():
                frame = _read_csv(path)
                if not frame.empty:
                    frames[ticker] = normalize_price_frame(frame)
                    break
    return frames


def _completed_close_on(frame: pd.DataFrame, date: str) -> tuple[bool, float]:
    if frame.empty:
        return False, np.nan
    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce").dt.date.astype(str)
    rows = working[working["date"].eq(date)]
    if rows.empty:
        return False, np.nan
    row = rows.iloc[0]
    close = _safe_float(row.get("close"))
    adj_close = _safe_float(row.get("adj_close", close))
    if not np.isfinite(close) or close <= 0 or not np.isfinite(adj_close) or adj_close <= 0:
        return False, np.nan
    return True, adj_close


def _open_on(frame: pd.DataFrame, date: str) -> float:
    if frame.empty:
        return np.nan
    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce").dt.date.astype(str)
    rows = working[working["date"].eq(date)]
    if rows.empty:
        return np.nan
    return _safe_float(rows.iloc[0].get("open"))


def _available_dates(frame: pd.DataFrame) -> set[str]:
    if frame.empty or "date" not in frame.columns:
        return set()
    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce").dt.date.astype(str)
    return set(working["date"])


def _load_authoritative_state(
    *,
    shadow_dir: Path,
    phase23k_dir: Path,
    portfolio_id: str,
) -> tuple[pd.DataFrame, float, dict[str, Any]]:
    positions = _read_csv(shadow_dir / "positions.csv")
    session_registry = _read_csv(phase23k_dir / "phase23k_session_registry.csv")
    if positions.empty:
        return pd.DataFrame(), np.nan, {}
    holdings = positions[
        positions["portfolio_id"].astype(str).eq(portfolio_id)
        & ~positions["ticker"].astype(str).eq("CASH")
    ].copy()
    cash_rows = positions[positions["ticker"].astype(str).eq("CASH")]
    cash = _safe_float(cash_rows.iloc[-1].get("cash_balance")) if not cash_rows.empty else np.nan
    session = session_registry.iloc[-1].to_dict() if not session_registry.empty else {}
    holdings["shares"] = pd.to_numeric(holdings["shares"], errors="coerce").fillna(0).astype(int)
    holdings["entry_price"] = pd.to_numeric(holdings["reference_price"], errors="coerce")
    return holdings, cash, session


def _starting_value(holdings: pd.DataFrame, cash: float) -> float:
    if holdings.empty or not np.isfinite(cash):
        return np.nan
    return float((holdings["shares"] * holdings["entry_price"]).sum() + cash)


def build_mark_to_market_histories(
    *,
    holdings: pd.DataFrame,
    cash_balance: float,
    session: dict[str, Any],
    price_frames: dict[str, pd.DataFrame],
    portfolio_id: str,
    existing_position_history: pd.DataFrame | None = None,
    existing_portfolio_history: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    if holdings.empty:
        return (
            pd.DataFrame(columns=POSITION_VALUATION_COLUMNS),
            pd.DataFrame(columns=PORTFOLIO_VALUATION_COLUMNS),
            ["missing_authoritative_positions"],
        )
    execution_date = _date_string(session.get("observed_execution_date") or session.get("expected_execution_date"))
    if not execution_date:
        return (
            pd.DataFrame(columns=POSITION_VALUATION_COLUMNS),
            pd.DataFrame(columns=PORTFOLIO_VALUATION_COLUMNS),
            ["missing_execution_date"],
        )
    tickers = list(holdings["ticker"].astype(str))
    required = [*tickers, "SPY"]
    missing_frames = [ticker for ticker in required if ticker not in price_frames or price_frames[ticker].empty]
    if missing_frames:
        return (
            pd.DataFrame(columns=POSITION_VALUATION_COLUMNS),
            pd.DataFrame(columns=PORTFOLIO_VALUATION_COLUMNS),
            [f"missing_price_frame:{';'.join(missing_frames)}"],
        )
    candidate_dates: set[str] = set()
    for ticker in required:
        candidate_dates |= {date for date in _available_dates(price_frames[ticker]) if date > execution_date}
    complete_dates: list[str] = []
    blockers: list[str] = []
    for date in sorted(candidate_dates):
        missing = [ticker for ticker in required if not _completed_close_on(price_frames[ticker], date)[0]]
        if missing:
            blockers.append(f"{date}:missing_completed_close:{';'.join(missing)}")
            continue
        complete_dates.append(date)

    position_rows: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    start_value = _starting_value(holdings, cash_balance)
    previous_value = start_value
    running_peak = start_value
    for date in complete_dates:
        values: dict[str, float] = {}
        for ticker in tickers:
            _complete, close = _completed_close_on(price_frames[ticker], date)
            values[ticker] = close
        market_value = float(
            sum(
                _safe_int(row["shares"]) * values[str(row["ticker"])]
                for _, row in holdings.iterrows()
            )
        )
        total_value = market_value + cash_balance
        daily_return = total_value / previous_value - 1.0 if previous_value else np.nan
        cumulative_return = total_value / start_value - 1.0 if start_value else np.nan
        running_peak = max(running_peak, total_value)
        drawdown = total_value / running_peak - 1.0 if running_peak else np.nan
        for _, row in holdings.iterrows():
            ticker = str(row["ticker"])
            shares = _safe_int(row["shares"])
            entry_price = _safe_float(row["entry_price"])
            cost_basis = shares * entry_price
            current_value = shares * values[ticker]
            pnl = current_value - cost_basis
            position_rows.append({
                "valuation_date": date,
                "session_id": session.get("session_id", ""),
                "portfolio_id": portfolio_id,
                "ticker": ticker,
                "shares": shares,
                "entry_price": entry_price,
                "current_close": values[ticker],
                "position_cost_basis": cost_basis,
                "current_market_value": current_value,
                "unrealized_pnl": pnl,
                "unrealized_return": pnl / cost_basis if cost_basis else np.nan,
                "cash_balance": cash_balance,
                "total_portfolio_value": total_value,
                "daily_portfolio_return": daily_return,
                "cumulative_portfolio_return": cumulative_return,
                "running_peak_value": running_peak,
                "drawdown": drawdown,
                "price_date": date,
                "price_complete": True,
                "valuation_status": "completed_daily_bar_valued",
            })
        portfolio_rows.append({
            "valuation_date": date,
            "session_id": session.get("session_id", ""),
            "portfolio_id": portfolio_id,
            "market_value": market_value,
            "cash_balance": cash_balance,
            "total_portfolio_value": total_value,
            "daily_portfolio_return": daily_return,
            "cumulative_portfolio_return": cumulative_return,
            "running_peak_value": running_peak,
            "drawdown": drawdown,
            "valuation_status": "completed_daily_bar_valued",
        })
        previous_value = total_value

    position_history = pd.DataFrame(position_rows, columns=POSITION_VALUATION_COLUMNS)
    portfolio_history = pd.DataFrame(portfolio_rows, columns=PORTFOLIO_VALUATION_COLUMNS)
    if existing_position_history is not None and not existing_position_history.empty:
        position_history = pd.concat([existing_position_history, position_history], ignore_index=True)
        position_history = position_history.drop_duplicates(
            ["valuation_date", "session_id", "portfolio_id", "ticker"], keep="last"
        )
    if existing_portfolio_history is not None and not existing_portfolio_history.empty:
        portfolio_history = pd.concat([existing_portfolio_history, portfolio_history], ignore_index=True)
        portfolio_history = portfolio_history.drop_duplicates(
            ["valuation_date", "session_id", "portfolio_id"], keep="last"
        )
    return position_history, portfolio_history, blockers


def build_spy_benchmark(
    *,
    portfolio_history: pd.DataFrame,
    spy_frame: pd.DataFrame,
    execution_date: str,
    starting_value: float,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    columns = [
        "valuation_date",
        "spy_entry_price",
        "spy_value",
        "spy_return",
        "spy_drawdown",
        "benchmark_basis",
    ]
    if portfolio_history.empty:
        return pd.DataFrame(columns=columns), pd.DataFrame(columns=[
            "valuation_date",
            "portfolio_value",
            "spy_value",
            "portfolio_return",
            "spy_return",
            "relative_return",
            "portfolio_drawdown",
            "spy_drawdown",
        ]), "no_completed_portfolio_valuations"
    spy_entry = _open_on(spy_frame, execution_date)
    if not np.isfinite(spy_entry) or spy_entry <= 0:
        return pd.DataFrame(columns=columns), pd.DataFrame(), "spy_execution_open_missing"
    spy_shares = starting_value / spy_entry
    rows = []
    peak = starting_value
    for date in portfolio_history["valuation_date"].astype(str):
        complete, close = _completed_close_on(spy_frame, date)
        if not complete:
            continue
        value = spy_shares * close
        peak = max(peak, value)
        rows.append({
            "valuation_date": date,
            "spy_entry_price": spy_entry,
            "spy_value": value,
            "spy_return": value / starting_value - 1.0,
            "spy_drawdown": value / peak - 1.0,
            "benchmark_basis": "execution_date_open_entry_completed_adjusted_close_valuation_no_cash_dividend_reinvestment_claim",
        })
    benchmark = pd.DataFrame(rows, columns=columns)
    relative = portfolio_history.merge(benchmark, on="valuation_date", how="inner")
    if relative.empty:
        relative_out = pd.DataFrame(columns=[
            "valuation_date",
            "portfolio_value",
            "spy_value",
            "portfolio_return",
            "spy_return",
            "relative_return",
            "portfolio_drawdown",
            "spy_drawdown",
        ])
    else:
        relative_out = pd.DataFrame({
            "valuation_date": relative["valuation_date"],
            "portfolio_value": relative["total_portfolio_value"],
            "spy_value": relative["spy_value"],
            "portfolio_return": relative["cumulative_portfolio_return"],
            "spy_return": relative["spy_return"],
            "relative_return": relative["cumulative_portfolio_return"] - relative["spy_return"],
            "portfolio_drawdown": relative["drawdown"],
            "spy_drawdown": relative["spy_drawdown"],
        })
    return benchmark, relative_out, "calculated"


def _existing_signal_dates(session_registry: pd.DataFrame) -> set[str]:
    if session_registry.empty or "signal_date" not in session_registry.columns:
        return set()
    return set(session_registry["signal_date"].map(_date_string))


def _current_actual_holdings(holdings: pd.DataFrame) -> dict[str, int]:
    if holdings.empty:
        return {}
    return {
        str(row["ticker"]): _safe_int(row["shares"])
        for _, row in holdings.iterrows()
        if str(row.get("ticker", "")) != "CASH"
    }


def build_order_packet(
    *,
    current_target: pd.DataFrame,
    session_registry: pd.DataFrame,
    actual_shares: dict[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    if current_target.empty:
        return (
            pd.DataFrame(columns=ORDER_PACKET_COLUMNS),
            pd.DataFrame(columns=["ticker", "target_shares", "target_weight"]),
            "current_target_missing",
        )
    signal_date = _date_string(current_target.iloc[0].get("selected_signal_date"))
    if not signal_date or signal_date in _existing_signal_dates(session_registry):
        targets = current_target.copy()
        targets["target_shares"] = targets.get("execution_target_shares", 0)
        return (
            pd.DataFrame(columns=ORDER_PACKET_COLUMNS),
            targets,
            "waiting_next_signal",
        )
    packet_id = f"phase23l_tv_{signal_date.replace('-', '')}"
    session_id = f"phase23l_{signal_date.replace('-', '')}"
    rows = []
    for _, row in current_target.iterrows():
        ticker = str(row["ticker"])
        target_shares = _safe_int(row.get("execution_target_shares", row.get("estimated_target_shares", 0)))
        current_shares = int(actual_shares.get(ticker, 0))
        delta = target_shares - current_shares
        if delta == 0:
            continue
        rows.append({
            "order_packet_id": packet_id,
            "session_id": session_id,
            "model_id": REQUIRED_MODEL_ID,
            "model_hash": REQUIRED_MODEL_HASH,
            "signal_date": signal_date,
            "expected_execution_date": _date_string(row.get("expected_execution_date")),
            "ticker": ticker,
            "side": "BUY" if delta > 0 else "SELL",
            "current_confirmed_shares": current_shares,
            "target_shares": target_shares,
            "order_quantity": abs(delta),
            "target_weight": _safe_float(row.get("target_weight")),
            "reference_price": _safe_float(row.get("reference_price")),
            "reference_price_date": _date_string(row.get("reference_price_date")),
            "expected_execution_price": _safe_float(row.get("execution_open_price")),
            "order_status": "manual_tradingview_packet_only_not_submitted",
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "blocking_reason": "",
        })
    packet = pd.DataFrame(rows, columns=ORDER_PACKET_COLUMNS)
    targets = current_target.copy()
    targets["target_shares"] = targets.get("execution_target_shares", targets.get("estimated_target_shares", 0))
    return packet, targets, "order_packet_available" if not packet.empty else "zero_delta_no_packet"


def build_fill_template(packet: pd.DataFrame) -> pd.DataFrame:
    if packet.empty:
        return pd.DataFrame(columns=FILL_TEMPLATE_COLUMNS)
    return pd.DataFrame([
        {
            "order_packet_id": row["order_packet_id"],
            "session_id": row["session_id"],
            "ticker": row["ticker"],
            "submitted_quantity": row["order_quantity"],
            "submitted_side": row["side"],
            "submitted_at": "",
            "fill_status": "not_submitted",
            "filled_quantity": "",
            "fill_price": "",
            "fill_timestamp": "",
            "rejection_reason": "",
            "partial_fill_reason": "",
            "notes": "",
        }
        for _, row in packet.iterrows()
    ], columns=FILL_TEMPLATE_COLUMNS)


def ingest_manual_fills(
    *,
    fills: pd.DataFrame,
    packet: pd.DataFrame,
    starting_shares: dict[str, int],
    cash_balance: float,
) -> tuple[pd.DataFrame, dict[str, int], float, list[str]]:
    if fills.empty:
        return pd.DataFrame(columns=[
            "order_packet_id",
            "session_id",
            "ticker",
            "side",
            "fill_status",
            "filled_quantity",
            "fill_price",
            "cash_change",
            "ledger_status",
        ]), dict(starting_shares), cash_balance, []
    required = set(FILL_TEMPLATE_COLUMNS)
    missing = sorted(required - set(fills.columns))
    if missing:
        return pd.DataFrame(), dict(starting_shares), cash_balance, [f"missing_fill_columns:{';'.join(missing)}"]
    key_cols = ["order_packet_id", "session_id", "ticker"]
    if fills[key_cols].astype(str).duplicated().any():
        return pd.DataFrame(), dict(starting_shares), cash_balance, ["duplicate_fill_rows"]
    packet_keys = set(map(tuple, packet[key_cols].astype(str).to_numpy())) if not packet.empty else set()
    ledger_rows = []
    shares = dict(starting_shares)
    cash = float(cash_balance)
    blockers: list[str] = []
    for _, row in fills.iterrows():
        key = tuple(str(row[col]) for col in key_cols)
        if key not in packet_keys:
            blockers.append(f"unknown_order:{'|'.join(key)}")
            continue
        status = str(row["fill_status"]).strip()
        if status not in ALLOWED_FILL_STATUSES:
            blockers.append(f"{key[2]}:invalid_fill_status")
            continue
        side = str(row["submitted_side"]).upper().strip()
        quantity = _safe_int(row["filled_quantity"])
        price = _safe_float(row["fill_price"])
        cash_change = 0.0
        if status in {"filled", "partially_filled"}:
            if quantity <= 0 or not np.isfinite(price) or price <= 0:
                blockers.append(f"{key[2]}:filled_quantity_or_price_invalid")
                continue
            signed = quantity if side == "BUY" else -quantity
            shares[key[2]] = int(shares.get(key[2], 0) + signed)
            cash_change = -quantity * price if side == "BUY" else quantity * price
            cash += cash_change
        elif status == "rejected" and not str(row.get("rejection_reason", "")).strip():
            blockers.append(f"{key[2]}:rejection_reason_required")
            continue
        ledger_rows.append({
            "order_packet_id": key[0],
            "session_id": key[1],
            "ticker": key[2],
            "side": side,
            "fill_status": status,
            "filled_quantity": quantity,
            "fill_price": price,
            "cash_change": cash_change,
            "ledger_status": "accepted_manual_tradingview_fill" if status in {"filled", "partially_filled"} else status,
        })
    return pd.DataFrame(ledger_rows), shares, cash, blockers


def _target_holdings_from_targets(targets: pd.DataFrame, actual_shares: dict[str, int]) -> pd.DataFrame:
    if targets.empty:
        rows = [
            {
                "ticker": ticker,
                "target_shares": shares,
                "target_weight": np.nan,
                "target_status": "actual_holdings_reference_no_new_signal",
            }
            for ticker, shares in sorted(actual_shares.items())
        ]
        return pd.DataFrame(rows)
    rows = []
    for _, row in targets.iterrows():
        rows.append({
            "ticker": str(row["ticker"]),
            "target_shares": _safe_int(row.get("target_shares", row.get("execution_target_shares", 0))),
            "target_weight": _safe_float(row.get("target_weight")),
            "target_status": str(row.get("target_status", "prospective_frozen_model_target")),
        })
    return pd.DataFrame(rows)


def _actual_holdings_frame(actual_shares: dict[str, int], holdings: pd.DataFrame) -> pd.DataFrame:
    entry_prices = {
        str(row["ticker"]): _safe_float(row.get("entry_price", row.get("reference_price")))
        for _, row in holdings.iterrows()
    }
    return pd.DataFrame([
        {
            "ticker": ticker,
            "actual_confirmed_shares": int(shares),
            "entry_price": entry_prices.get(ticker, np.nan),
            "holding_source": "confirmed_entered_fills",
        }
        for ticker, shares in sorted(actual_shares.items())
        if shares != 0
    ])


def _tracking_reconciliation(
    *,
    targets: pd.DataFrame,
    actual_shares: dict[str, int],
    packet: pd.DataFrame,
    price_frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    tickers = sorted(set(targets["ticker"].astype(str)) | set(actual_shares) | set(packet["ticker"].astype(str)))
    rows = []
    packet_delta = {
        str(row["ticker"]): (_safe_int(row["order_quantity"]) if row["side"] == "BUY" else -_safe_int(row["order_quantity"]))
        for _, row in packet.iterrows()
    } if not packet.empty else {}
    target_map = {
        str(row["ticker"]): _safe_int(row["target_shares"])
        for _, row in targets.iterrows()
    } if not targets.empty else {}
    for ticker in tickers:
        target = int(target_map.get(ticker, actual_shares.get(ticker, 0)))
        actual = int(actual_shares.get(ticker, 0))
        open_order = int(packet_delta.get(ticker, 0))
        diff = target - actual
        latest_price = np.nan
        frame = price_frames.get(ticker, pd.DataFrame())
        if not frame.empty:
            complete_dates = []
            for date in sorted(_available_dates(frame)):
                complete, close = _completed_close_on(frame, date)
                if complete:
                    complete_dates.append((date, close))
            if complete_dates:
                latest_price = complete_dates[-1][1]
        rows.append({
            "ticker": ticker,
            "target_shares": target,
            "actual_confirmed_shares": actual,
            "open_order_quantity": open_order,
            "tracking_difference_shares": diff,
            "tracking_difference_notional": diff * latest_price if np.isfinite(latest_price) else np.nan,
            "reconciliation_status": "in_sync" if diff == 0 else "tracking_difference_open",
            "corrective_order_required": bool(diff != 0),
        })
    return pd.DataFrame(rows)


def _dashboard_markdown(
    *,
    decision: str,
    portfolio_history: pd.DataFrame,
    holdings: pd.DataFrame,
    relative: pd.DataFrame,
    packet: pd.DataFrame,
    reconciliation: pd.DataFrame,
    blockers: list[str],
) -> str:
    latest_value = ""
    latest_drawdown = ""
    if not portfolio_history.empty:
        latest = portfolio_history.sort_values("valuation_date").iloc[-1]
        latest_value = f"{_safe_float(latest['total_portfolio_value']):.2f}"
        latest_drawdown = f"{_safe_float(latest['drawdown']):.4f}"
    relative_return = ""
    if not relative.empty:
        relative_return = f"{_safe_float(relative.iloc[-1]['relative_return']):.4f}"
    return "\n".join([
        "# Phase 23L Operational Paper Bridge",
        "",
        "PAPER ONLY. NO LIVE TRADING. NO REAL MONEY. NO BROKER API. NO TRADINGVIEW ORDER SUBMISSION.",
        "",
        f"- Decision: `{decision}`",
        f"- Current portfolio value: `{latest_value or 'no_new_completed_valuation'}`",
        f"- Current drawdown: `{latest_drawdown or 'not_available'}`",
        f"- SPY-relative return: `{relative_return or 'not_available'}`",
        f"- Current holdings: `{'; '.join(holdings['ticker'].astype(str)) if not holdings.empty else 'none'}`",
        f"- Pending order rows: `{len(packet)}`",
        f"- Tracking differences: `{int(reconciliation['corrective_order_required'].sum()) if not reconciliation.empty else 0}`",
        f"- Blocking incidents: `{'; '.join(blockers) if blockers else ''}`",
        "",
        "TradingView packet rows are manual paper instructions only and are not submitted.",
    ])


def save_phase23l_operational_paper_bridge(
    *,
    config: dict,
    reports_dir: str | Path = "reports",
) -> dict[str, pd.DataFrame]:
    section = _phase_config(config)
    reports_path = Path(reports_dir)
    output_dir = _resolve_reports_path(configured_path=section["output_dir"], reports_dir=reports_path)
    dashboard_path = _resolve_reports_path(
        configured_path=section["dashboard_status_path"], reports_dir=reports_path
    )
    shadow_dir = _resolve_reports_path(
        configured_path=section["source_phase23i_shadow_dir"], reports_dir=reports_path
    )
    phase23j_dir = _resolve_reports_path(
        configured_path=section["source_phase23j_dir"], reports_dir=reports_path
    )
    phase23k_dir = _resolve_reports_path(
        configured_path=section["source_phase23k_dir"], reports_dir=reports_path
    )
    combined_dir = _resolve_project_path(
        configured_path=section["combined_input_dir"], reports_dir=reports_path
    )
    post_dir = _resolve_project_path(
        configured_path=section["post_endpoint_input_dir"], reports_dir=reports_path
    )
    pilot_dir = _resolve_project_path(
        configured_path=section["pilot_input_dir"], reports_dir=reports_path
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    portfolio_id = str(section["portfolio_id"])
    holdings, cash_balance, session = _load_authoritative_state(
        shadow_dir=shadow_dir,
        phase23k_dir=phase23k_dir,
        portfolio_id=portfolio_id,
    )
    price_frames = _load_price_frames(
        combined_dir=combined_dir,
        post_dir=post_dir,
        pilot_dir=pilot_dir,
    )
    existing_position = _read_csv(output_dir / "phase23l_position_valuation_history.csv")
    existing_portfolio = _read_csv(output_dir / "phase23l_portfolio_valuation_history.csv")
    position_history, portfolio_history, valuation_blockers = build_mark_to_market_histories(
        holdings=holdings,
        cash_balance=cash_balance,
        session=session,
        price_frames=price_frames,
        portfolio_id=portfolio_id,
        existing_position_history=existing_position,
        existing_portfolio_history=existing_portfolio,
    )
    starting_value = _starting_value(holdings, cash_balance)
    execution_date = _date_string(session.get("observed_execution_date") or session.get("expected_execution_date"))
    spy_history, relative, spy_status = build_spy_benchmark(
        portfolio_history=portfolio_history,
        spy_frame=price_frames.get("SPY", pd.DataFrame()),
        execution_date=execution_date,
        starting_value=starting_value,
    )

    session_registry = _read_csv(phase23k_dir / "phase23k_session_registry.csv")
    current_target = _read_csv(phase23j_dir / "phase23j_current_target_portfolio.csv")
    actual_shares = _current_actual_holdings(holdings)
    packet, targets_raw, packet_status = build_order_packet(
        current_target=current_target,
        session_registry=session_registry,
        actual_shares=actual_shares,
    )
    fill_template = build_fill_template(packet)
    manual_fill_path = output_dir / str(section["manual_fill_filename"])
    manual_fills = _read_csv(manual_fill_path)
    execution_ledger, updated_shares, updated_cash, fill_blockers = ingest_manual_fills(
        fills=manual_fills,
        packet=packet,
        starting_shares=actual_shares,
        cash_balance=cash_balance,
    )
    target_holdings = _target_holdings_from_targets(targets_raw, updated_shares)
    actual_holdings = _actual_holdings_frame(updated_shares, holdings)
    reconciliation = _tracking_reconciliation(
        targets=target_holdings,
        actual_shares=updated_shares,
        packet=packet,
        price_frames=price_frames,
    )

    blockers = [*valuation_blockers, *fill_blockers]
    if fill_blockers:
        decision = "phase23l_blocked_manual_fill_integrity"
    elif valuation_blockers and any("missing_completed_close" in item for item in valuation_blockers):
        decision = "phase23l_blocked_missing_completed_prices"
    elif packet_status == "order_packet_available" and not blockers:
        decision = "phase23l_paper_bridge_ready_order_packet_available"
    else:
        decision = "phase23l_paper_bridge_ready_waiting_next_signal"

    dashboard = pd.DataFrame([{
        "phase": "Phase 23L",
        "phase23l_decision": decision,
        "session_id": session.get("session_id", ""),
        "signal_date": session.get("signal_date", ""),
        "observed_execution_date": execution_date,
        "portfolio_id": portfolio_id,
        "position_count": len(holdings),
        "cash_balance": updated_cash,
        "initial_post_cost_portfolio_value": starting_value,
        "valuation_rows": len(portfolio_history),
        "spy_benchmark_status": spy_status,
        "order_packet_rows": len(packet),
        "manual_fill_rows": len(manual_fills),
        "blocking_incidents": ";".join(blockers),
        "paper_only": bool(section["paper_only"]),
        "live_trading_allowed": bool(section["live_trading_allowed"]),
        "real_money_allowed": bool(section["real_money_allowed"]),
        "broker_api_integration_allowed": bool(section["broker_api_integration_allowed"]),
        "promotion_allowed": bool(section["promotion_allowed"]),
        "generated_at_utc": _generated_at(),
    }])
    gates = pd.DataFrame([
        {
            "gate": "model_hash_frozen",
            "passed": session.get("model_hash", REQUIRED_MODEL_HASH) == REQUIRED_MODEL_HASH,
            "detail": REQUIRED_MODEL_HASH,
        },
        {
            "gate": "no_live_real_broker",
            "passed": not bool(section["live_trading_allowed"])
            and not bool(section["real_money_allowed"])
            and not bool(section["broker_api_integration_allowed"]),
            "detail": "safety flags false",
        },
        {
            "gate": "authoritative_positions_loaded",
            "passed": not holdings.empty and np.isfinite(cash_balance),
            "detail": str(shadow_dir / "positions.csv"),
        },
    ])
    conclusion = pd.DataFrame([{
        "phase23l_decision": decision,
        "paper_only": True,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
        "notes": "Operational mark-to-market and TradingView manual-paper bridge only.",
    }])

    _write_csv(position_history, output_dir / "phase23l_position_valuation_history.csv", POSITION_VALUATION_COLUMNS)
    _write_csv(portfolio_history, output_dir / "phase23l_portfolio_valuation_history.csv", PORTFOLIO_VALUATION_COLUMNS)
    _write_csv(spy_history, output_dir / "phase23l_spy_benchmark_history.csv")
    _write_csv(relative, output_dir / "phase23l_relative_performance.csv")
    _write_csv(packet, output_dir / "phase23l_tradingview_order_packet.csv", ORDER_PACKET_COLUMNS)
    _write_csv(fill_template, output_dir / "phase23l_tradingview_manual_fill_template.csv", FILL_TEMPLATE_COLUMNS)
    _write_csv(target_holdings, output_dir / "phase23l_target_holdings.csv")
    _write_csv(actual_holdings, output_dir / "phase23l_actual_holdings.csv")
    _write_csv(execution_ledger, output_dir / "phase23l_execution_ledger.csv")
    _write_csv(reconciliation, output_dir / "phase23l_tracking_reconciliation.csv")
    _write_csv(dashboard, output_dir / "phase23l_operational_dashboard.csv")
    _write_text(
        _dashboard_markdown(
            decision=decision,
            portfolio_history=portfolio_history,
            holdings=holdings,
            relative=relative,
            packet=packet,
            reconciliation=reconciliation,
            blockers=blockers,
        ),
        output_dir / "phase23l_operational_dashboard.md",
    )
    _write_csv(dashboard, output_dir / "phase23l_summary.csv")
    _write_csv(gates, output_dir / "phase23l_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase23l_conclusion.csv")
    _write_csv(dashboard, dashboard_path)

    return {
        "summary": dashboard,
        "gate_report": gates,
        "conclusion": conclusion,
        "position_valuation_history": position_history,
        "portfolio_valuation_history": portfolio_history,
        "spy_benchmark_history": spy_history,
        "relative_performance": relative,
        "tradingview_order_packet": packet,
        "manual_fill_template": fill_template,
        "target_holdings": target_holdings,
        "actual_holdings": actual_holdings,
        "execution_ledger": execution_ledger,
        "tracking_reconciliation": reconciliation,
    }
