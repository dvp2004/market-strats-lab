from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.fill_phase23i_shadow_session import build_filled_shadow_session


TICKERS = ["AMZN", "CAT", "META", "NVDA", "TSLA"]
EXECUTION_OPENS = {
    "AMZN": 245.16400146484372,
    "CAT": 935.0,
    "META": 579.9000244140625,
    "NVDA": 208.85499572753903,
    "TSLA": 412.0799865722656,
}
QUANTITIES = {"AMZN": 81, "CAT": 21, "META": 34, "NVDA": 95, "TSLA": 48}
REFERENCE_PRICES = {
    "AMZN": 238.5500030517578,
    "CAT": 910.5700073242188,
    "META": 566.97998046875,
    "NVDA": 205.19000244140625,
    "TSLA": 406.42999267578125,
}


def _valid_template() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "session_date": "2026-06-16",
                "selected_signal_date": "2026-06-12",
                "portfolio_id": "ridge_top5_equal_weight",
                "ticker": ticker,
                "target_weight": 0.2,
                "target_notional": 20000.0,
                "reference_price": REFERENCE_PRICES[ticker],
                "reference_price_date": "2026-06-12",
                "expected_execution_date": "2026-06-15",
                "observed_execution_date": "2026-06-15",
                "execution_open_price": EXECUTION_OPENS[ticker],
                "execution_price_available": True,
                "current_shares": 0,
                "target_shares": QUANTITIES[ticker],
                "signal_estimated_target_shares": QUANTITIES[ticker] + 1,
                "phase23j_execution_target_shares": QUANTITIES[ticker],
                "proposed_quantity": QUANTITIES[ticker],
                "order_side": "BUY",
                "estimated_order_notional": QUANTITIES[ticker] * EXECUTION_OPENS[ticker],
                "estimated_transaction_cost": QUANTITIES[ticker]
                * EXECUTION_OPENS[ticker]
                * 0.001,
                "estimated_post_trade_cash_after_all_orders": 1000.0,
                "cash_affordability_status": "cost_aware_quantity_ok",
                "noncanonical_label": "NONCANONICAL PILOT DIAGNOSTIC",
                "session_state": "proposed",
                "order_instruction": "manual_research_shadow_only",
                "paper_order_allowed": True,
                "order_blocking_reason": "",
                "target_status": "post_endpoint_delta_order_ready",
                "manual_decision": "pending",
                "simulated_fill_price": "",
                "simulated_fill_quantity": "",
                "override_reason": "",
                "notes": "",
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
            for ticker in TICKERS
        ]
    )


def _write_template(tmp_path: Path, template: pd.DataFrame) -> Path:
    shadow_dir = tmp_path / "shadow"
    shadow_dir.mkdir()
    template.to_csv(shadow_dir / "current_manual_session_template.csv", index=False)
    return shadow_dir


def _assert_blocks_without_output(tmp_path: Path, template: pd.DataFrame) -> None:
    shadow_dir = _write_template(tmp_path, template)
    output = shadow_dir / "shadow_manual_session_filled.csv"
    with pytest.raises(ValueError):
        build_filled_shadow_session(
            shadow_dir=shadow_dir,
            output_file=output.name,
            confirm_simulated_fill=True,
        )
    assert not output.exists()


def test_simulated_fill_uses_execution_open_not_reference_price(tmp_path: Path) -> None:
    shadow_dir = _write_template(tmp_path, _valid_template())

    output = build_filled_shadow_session(
        shadow_dir=shadow_dir,
        output_file="shadow_manual_session_filled.csv",
        confirm_simulated_fill=True,
    )

    filled = pd.read_csv(output)
    assert filled["selected_signal_date"].eq("2026-06-12").all()
    assert filled["expected_execution_date"].eq("2026-06-15").all()
    assert filled["observed_execution_date"].eq("2026-06-15").all()
    by_ticker = filled.set_index("ticker")
    for ticker in TICKERS:
        assert by_ticker.loc[ticker, "simulated_fill_price"] == pytest.approx(
            EXECUTION_OPENS[ticker]
        )
        assert by_ticker.loc[ticker, "simulated_fill_quantity"] == QUANTITIES[ticker]
        assert by_ticker.loc[ticker, "reference_price"] == pytest.approx(
            REFERENCE_PRICES[ticker]
        )
        assert by_ticker.loc[ticker, "reference_price"] != pytest.approx(
            by_ticker.loc[ticker, "execution_open_price"]
        )
    assert filled["session_state"].eq("entered").all()
    assert filled["live_trading_allowed"].eq(False).all()
    assert filled["real_money_allowed"].eq(False).all()
    assert filled["broker_api_integration_allowed"].eq(False).all()


def test_missing_execution_open_blocks_whole_fill_and_creates_no_output(
    tmp_path: Path,
) -> None:
    template = _valid_template()
    template.loc[template["ticker"].eq("AMZN"), "execution_open_price"] = np.nan
    _assert_blocks_without_output(tmp_path, template)


def test_missing_execution_column_blocks_fill(tmp_path: Path) -> None:
    template = _valid_template().drop(columns=["execution_open_price"])
    _assert_blocks_without_output(tmp_path, template)


def test_execution_price_available_false_blocks_fill(tmp_path: Path) -> None:
    template = _valid_template()
    template.loc[template["ticker"].eq("AMZN"), "execution_price_available"] = False
    _assert_blocks_without_output(tmp_path, template)


def test_blank_observed_execution_date_blocks_fill(tmp_path: Path) -> None:
    template = _valid_template()
    template.loc[template["ticker"].eq("AMZN"), "observed_execution_date"] = ""
    _assert_blocks_without_output(tmp_path, template)


def test_observed_execution_date_mismatch_blocks_fill(tmp_path: Path) -> None:
    template = _valid_template()
    template.loc[template["ticker"].eq("AMZN"), "observed_execution_date"] = (
        "2026-06-16"
    )
    _assert_blocks_without_output(tmp_path, template)


def test_blocked_order_blocks_fill(tmp_path: Path) -> None:
    template = _valid_template()
    template.loc[template["ticker"].eq("AMZN"), "paper_order_allowed"] = False
    template.loc[template["ticker"].eq("AMZN"), "order_blocking_reason"] = (
        "execution_open_price_pending"
    )
    _assert_blocks_without_output(tmp_path, template)


def test_unaffordable_order_plan_blocks_fill(tmp_path: Path) -> None:
    template = _valid_template()
    template.loc[template["ticker"].eq("AMZN"), "cash_affordability_status"] = (
        "insufficient_cash"
    )
    _assert_blocks_without_output(tmp_path, template)


def test_zero_quantity_blocks_fill(tmp_path: Path) -> None:
    template = _valid_template()
    template.loc[template["ticker"].eq("AMZN"), "proposed_quantity"] = 0
    _assert_blocks_without_output(tmp_path, template)


def test_four_of_five_orders_blocks_fill(tmp_path: Path) -> None:
    template = _valid_template().loc[lambda frame: frame["ticker"].ne("AMZN")]
    _assert_blocks_without_output(tmp_path, template)


def test_duplicate_invocation_cannot_overwrite_existing_fill(tmp_path: Path) -> None:
    shadow_dir = _write_template(tmp_path, _valid_template())
    output_name = "shadow_manual_session_filled.csv"
    build_filled_shadow_session(
        shadow_dir=shadow_dir,
        output_file=output_name,
        confirm_simulated_fill=True,
    )

    with pytest.raises(FileExistsError):
        build_filled_shadow_session(
            shadow_dir=shadow_dir,
            output_file=output_name,
            confirm_simulated_fill=True,
        )
    assert len(pd.read_csv(shadow_dir / output_name)) == len(TICKERS)
