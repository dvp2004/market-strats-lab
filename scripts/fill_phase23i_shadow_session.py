from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_SHADOW_DIR = Path("reports/individual_equity_shadow/phase23i_prospective_shadow")
REQUIRED_SIGNAL_DATE = "2026-06-12"
REQUIRED_EXECUTION_DATE = "2026-06-15"
REQUIRED_SELECTED_ORDER_COUNT = 5
ACCEPTABLE_CASH_STATUSES = {"cost_aware_quantity_ok"}


def _bool_false_columns(frame: pd.DataFrame) -> pd.DataFrame:
    for column in [
        "live_trading_allowed",
        "real_money_allowed",
        "broker_api_integration_allowed",
    ]:
        frame[column] = False
    return frame


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _blank(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    return str(value).strip() == ""


def _date_string(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return pd.Timestamp(parsed).date().isoformat()


def _positive_integer_series(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.notna() & numeric.gt(0) & np.isclose(numeric, np.floor(numeric))


def _validate_simulated_fill_template(template: pd.DataFrame) -> None:
    required = [
        "selected_signal_date",
        "ticker",
        "reference_price",
        "reference_price_date",
        "expected_execution_date",
        "observed_execution_date",
        "execution_open_price",
        "execution_price_available",
        "current_shares",
        "target_shares",
        "phase23j_execution_target_shares",
        "proposed_quantity",
        "order_side",
        "estimated_order_notional",
        "estimated_transaction_cost",
        "estimated_post_trade_cash_after_all_orders",
        "cash_affordability_status",
        "paper_order_allowed",
        "order_blocking_reason",
    ]
    missing = [column for column in required if column not in template.columns]
    if missing:
        raise ValueError(
            "Cannot simulate fills because Phase23I order plan is missing columns: "
            + ";".join(missing)
        )
    blockers: list[str] = []
    if len(template) != REQUIRED_SELECTED_ORDER_COUNT:
        blockers.append(
            f"expected_{REQUIRED_SELECTED_ORDER_COUNT}_proposed_orders_got_{len(template)}"
        )
    tickers = template["ticker"].astype(str).str.strip()
    if tickers.duplicated().any():
        blockers.append("duplicate_tickers")
    signal_dates = template["selected_signal_date"].map(_date_string)
    if not signal_dates.eq(REQUIRED_SIGNAL_DATE).all():
        blockers.append("selected_signal_date_not_current_phase23j_signal")
    expected_dates = template["expected_execution_date"].map(_date_string)
    observed_dates = template["observed_execution_date"].map(_date_string)
    if not expected_dates.eq(REQUIRED_EXECUTION_DATE).all():
        blockers.append("expected_execution_date_not_current_phase23j_execution_date")
    if observed_dates.eq("").any():
        blockers.append("observed_execution_date_missing")
    if not observed_dates.eq(expected_dates).all():
        blockers.append("observed_execution_date_mismatch")
    if not template["execution_price_available"].map(_bool_value).all():
        blockers.append("execution_price_not_available")
    execution_open = pd.to_numeric(template["execution_open_price"], errors="coerce")
    if execution_open.isna().any() or execution_open.le(0).any():
        blockers.append("execution_open_price_missing_or_nonpositive")
    reference_price = pd.to_numeric(template["reference_price"], errors="coerce")
    if reference_price.isna().any() or reference_price.le(0).any():
        blockers.append("reference_price_missing_or_nonpositive")
    if not template["paper_order_allowed"].map(_bool_value).all():
        blockers.append("paper_order_not_allowed")
    if not template["order_blocking_reason"].map(_blank).all():
        blockers.append("order_blocking_reason_present")
    statuses = template["cash_affordability_status"].astype(str).str.strip()
    if not statuses.isin(ACCEPTABLE_CASH_STATUSES).all():
        blockers.append("cash_affordability_status_not_acceptable")
    proposed_quantity = pd.to_numeric(template["proposed_quantity"], errors="coerce")
    if not _positive_integer_series(template["proposed_quantity"]).all():
        blockers.append("proposed_quantity_not_positive_integer")
    current_shares = pd.to_numeric(template["current_shares"], errors="coerce")
    target_shares = pd.to_numeric(template["target_shares"], errors="coerce")
    phase23j_target_shares = pd.to_numeric(
        template["phase23j_execution_target_shares"], errors="coerce"
    )
    if current_shares.isna().any() or target_shares.isna().any():
        blockers.append("current_or_target_shares_missing")
    else:
        approved_delta = (target_shares - current_shares).abs()
        if not np.isclose(proposed_quantity, approved_delta).all():
            blockers.append("proposed_quantity_does_not_match_approved_target_delta")
        side = template["order_side"].astype(str).str.upper().str.strip()
        if not side.isin({"BUY", "SELL"}).all():
            blockers.append("invalid_order_side")
        buy_mismatch = side.eq("BUY") & target_shares.le(current_shares)
        sell_mismatch = side.eq("SELL") & target_shares.ge(current_shares)
        if (buy_mismatch | sell_mismatch).any():
            blockers.append("order_side_does_not_match_target_delta")
    if phase23j_target_shares.isna().any():
        blockers.append("phase23j_execution_target_shares_missing")
    elif not np.isclose(target_shares, phase23j_target_shares).all():
        blockers.append("target_shares_do_not_match_phase23j_execution_target_shares")
    if blockers:
        raise ValueError(
            "Cannot simulate Phase23I fills: " + ";".join(sorted(set(blockers)))
        )


def _atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def build_filled_shadow_session(
    *,
    shadow_dir: Path,
    output_file: str,
    confirm_simulated_fill: bool,
) -> Path:
    template_path = shadow_dir / "current_manual_session_template.csv"
    if not template_path.exists():
        raise FileNotFoundError(f"Missing shadow template: {template_path}")
    template = pd.read_csv(template_path)
    filled = template.copy()
    if filled.empty:
        raise ValueError("Current shadow session template is empty.")
    output_path = shadow_dir / output_file
    if output_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing Phase23I filled session: {output_path}"
        )
    if confirm_simulated_fill:
        _validate_simulated_fill_template(filled)
        execution_price = pd.to_numeric(
            filled["execution_open_price"], errors="coerce"
        )
        proposed_quantity = pd.to_numeric(filled["proposed_quantity"], errors="coerce")
        filled["manual_decision"] = "enter_simulated_shadow_trade"
        filled["session_state"] = "entered"
        filled["simulated_fill_price"] = execution_price
        filled["simulated_fill_quantity"] = proposed_quantity.astype(int)
        filled["override_reason"] = "explicit_user_simulated_shadow_fill_command"
        filled["notes"] = (
            "SIMULATED PAPER SHADOW FILL ONLY - no broker, no live trading, "
            "no real money"
        )
    else:
        filled["manual_decision"] = "skip_user_choice"
        filled["session_state"] = "skipped"
        filled["override_reason"] = "explicit_user_skip_shadow_session_command"
        filled["notes"] = "Skipped by explicit helper command."
    filled = _bool_false_columns(filled)
    _atomic_write_csv(filled, output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fill the Phase23I individual-equity shadow session template. "
            "This writes a research-only CSV and never places orders."
        )
    )
    parser.add_argument("--shadow-dir", default=str(DEFAULT_SHADOW_DIR))
    parser.add_argument("--output-file", default="shadow_manual_session_filled.csv")
    parser.add_argument(
        "--confirm-simulated-fill",
        action="store_true",
        help=(
            "Mark rows as simulated entered fills using placeholder local-only "
            "fill values. This is not broker execution."
        ),
    )
    args = parser.parse_args()
    output_path = build_filled_shadow_session(
        shadow_dir=Path(args.shadow_dir),
        output_file=args.output_file,
        confirm_simulated_fill=bool(args.confirm_simulated_fill),
    )
    print(f"Wrote research-only Phase23I shadow filled session: {output_path}")


if __name__ == "__main__":
    main()
