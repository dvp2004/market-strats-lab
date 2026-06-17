from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from market_strats.analysis.phase23l_operational_paper_bridge import (
    REQUIRED_MODEL_HASH,
    REQUIRED_MODEL_ID,
    build_mark_to_market_histories,
    build_order_packet,
    build_spy_benchmark,
    ingest_manual_fills,
    save_phase23l_operational_paper_bridge,
)


def _price_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _holdings() -> pd.DataFrame:
    return pd.DataFrame([
        {"portfolio_id": "ridge_top5_equal_weight", "ticker": "AAA", "shares": 10, "entry_price": 100.0},
        {"portfolio_id": "ridge_top5_equal_weight", "ticker": "BBB", "shares": 5, "entry_price": 200.0},
    ])


def _session(signal_date: str = "2026-06-12") -> dict:
    return {
        "session_id": "phase23k_existing",
        "signal_date": signal_date,
        "expected_execution_date": "2026-06-15",
        "observed_execution_date": "2026-06-15",
        "model_id": REQUIRED_MODEL_ID,
        "model_hash": REQUIRED_MODEL_HASH,
    }


def test_phase23l_entry_cost_basis_remains_unchanged_and_completed_bar_values() -> None:
    price_frames = {
        "AAA": _price_frame([
            {"date": "2026-06-16", "open": 101, "high": 112, "low": 100, "close": 110, "adj_close": 110, "volume": 1}
        ]),
        "BBB": _price_frame([
            {"date": "2026-06-16", "open": 201, "high": 215, "low": 200, "close": 210, "adj_close": 210, "volume": 1}
        ]),
        "SPY": _price_frame([
            {"date": "2026-06-16", "open": 100, "high": 105, "low": 99, "close": 104, "adj_close": 104, "volume": 1}
        ]),
    }
    position_history, portfolio_history, blockers = build_mark_to_market_histories(
        holdings=_holdings(),
        cash_balance=100.0,
        session=_session(),
        price_frames=price_frames,
        portfolio_id="ridge_top5_equal_weight",
    )
    assert blockers == []
    aaa = position_history[position_history["ticker"].eq("AAA")].iloc[0]
    assert aaa["entry_price"] == 100.0
    assert aaa["current_close"] == 110.0
    assert aaa["position_cost_basis"] == 1000.0
    assert aaa["unrealized_pnl"] == 100.0
    assert portfolio_history.iloc[0]["total_portfolio_value"] == 2250.0
    assert portfolio_history.iloc[0]["cumulative_portfolio_return"] == (2250 / 2100) - 1


def test_phase23l_incomplete_bar_does_not_create_valuation() -> None:
    price_frames = {
        "AAA": _price_frame([
            {"date": "2026-06-16", "open": 101, "high": 112, "low": 100, "close": np.nan, "adj_close": np.nan, "volume": 1}
        ]),
        "BBB": _price_frame([
            {"date": "2026-06-16", "open": 201, "high": 215, "low": 200, "close": 210, "adj_close": 210, "volume": 1}
        ]),
        "SPY": _price_frame([
            {"date": "2026-06-16", "open": 100, "high": 105, "low": 99, "close": 104, "adj_close": 104, "volume": 1}
        ]),
    }
    _position_history, portfolio_history, blockers = build_mark_to_market_histories(
        holdings=_holdings(),
        cash_balance=100.0,
        session=_session(),
        price_frames=price_frames,
        portfolio_id="ridge_top5_equal_weight",
    )
    assert portfolio_history.empty
    assert "2026-06-16:missing_completed_close:AAA" in blockers


def test_phase23l_missing_selected_ticker_blocks_valuation() -> None:
    price_frames = {
        "AAA": _price_frame([
            {"date": "2026-06-16", "open": 101, "high": 112, "low": 100, "close": 110, "adj_close": 110, "volume": 1}
        ]),
        "SPY": _price_frame([
            {"date": "2026-06-16", "open": 100, "high": 105, "low": 99, "close": 104, "adj_close": 104, "volume": 1}
        ]),
    }
    _position_history, portfolio_history, blockers = build_mark_to_market_histories(
        holdings=_holdings(),
        cash_balance=100.0,
        session=_session(),
        price_frames=price_frames,
        portfolio_id="ridge_top5_equal_weight",
    )
    assert portfolio_history.empty
    assert "missing_price_frame:BBB" in blockers


def test_phase23l_duplicate_rerun_does_not_duplicate_dates() -> None:
    price_frames = {
        "AAA": _price_frame([
            {"date": "2026-06-16", "open": 101, "high": 112, "low": 100, "close": 110, "adj_close": 110, "volume": 1}
        ]),
        "BBB": _price_frame([
            {"date": "2026-06-16", "open": 201, "high": 215, "low": 200, "close": 210, "adj_close": 210, "volume": 1}
        ]),
        "SPY": _price_frame([
            {"date": "2026-06-16", "open": 100, "high": 105, "low": 99, "close": 104, "adj_close": 104, "volume": 1}
        ]),
    }
    first_pos, first_port, _blockers = build_mark_to_market_histories(
        holdings=_holdings(),
        cash_balance=100.0,
        session=_session(),
        price_frames=price_frames,
        portfolio_id="ridge_top5_equal_weight",
    )
    second_pos, second_port, _blockers = build_mark_to_market_histories(
        holdings=_holdings(),
        cash_balance=100.0,
        session=_session(),
        price_frames=price_frames,
        portfolio_id="ridge_top5_equal_weight",
        existing_position_history=first_pos,
        existing_portfolio_history=first_port,
    )
    assert len(second_pos) == 2
    assert len(second_port) == 1


def test_phase23l_spy_baseline_uses_execution_open_and_completed_close() -> None:
    portfolio = pd.DataFrame([{
        "valuation_date": "2026-06-16",
        "total_portfolio_value": 2250.0,
        "cumulative_portfolio_return": (2250 / 2100) - 1,
        "drawdown": 0.0,
    }])
    spy = _price_frame([
        {"date": "2026-06-15", "open": 100, "high": 101, "low": 99, "close": np.nan, "adj_close": np.nan, "volume": 1},
        {"date": "2026-06-16", "open": 101, "high": 106, "low": 100, "close": 105, "adj_close": 105, "volume": 1},
    ])
    benchmark, relative, status = build_spy_benchmark(
        portfolio_history=portfolio,
        spy_frame=spy,
        execution_date="2026-06-15",
        starting_value=2100.0,
    )
    assert status == "calculated"
    assert benchmark.iloc[0]["spy_entry_price"] == 100.0
    assert benchmark.iloc[0]["spy_value"] == 2205.0
    assert relative.iloc[0]["relative_return"] == pytest.approx(((2250 / 2100) - 1) - 0.05)


def test_phase23l_existing_signal_is_not_reexported() -> None:
    target = pd.DataFrame([{
        "selected_signal_date": "2026-06-12",
        "ticker": "AAA",
        "execution_target_shares": 10,
        "target_weight": 0.2,
    }])
    registry = pd.DataFrame([{"signal_date": "2026-06-12"}])
    packet, _targets, status = build_order_packet(
        current_target=target,
        session_registry=registry,
        actual_shares={"AAA": 0},
    )
    assert packet.empty
    assert status == "waiting_next_signal"


def test_phase23l_next_signal_creates_packet_and_omits_zero_delta() -> None:
    target = pd.DataFrame([
        {
            "selected_signal_date": "2026-06-19",
            "expected_execution_date": "2026-06-22",
            "ticker": "AAA",
            "execution_target_shares": 10,
            "target_weight": 0.2,
            "reference_price": 100,
            "reference_price_date": "2026-06-19",
            "execution_open_price": 101,
        },
        {
            "selected_signal_date": "2026-06-19",
            "expected_execution_date": "2026-06-22",
            "ticker": "BBB",
            "execution_target_shares": 5,
            "target_weight": 0.2,
            "reference_price": 200,
            "reference_price_date": "2026-06-19",
            "execution_open_price": 201,
        },
    ])
    packet, _targets, status = build_order_packet(
        current_target=target,
        session_registry=pd.DataFrame([{"signal_date": "2026-06-12"}]),
        actual_shares={"AAA": 10, "BBB": 0},
    )
    assert status == "order_packet_available"
    assert set(packet["ticker"]) == {"BBB"}
    assert packet.iloc[0]["order_quantity"] == 5
    assert bool(packet.iloc[0]["paper_only"]) is True
    assert bool(packet.iloc[0]["live_trading_allowed"]) is False


def test_phase23l_unsubmitted_rejected_partial_and_filled_behaviour() -> None:
    packet = pd.DataFrame([
        {"order_packet_id": "p", "session_id": "s", "ticker": "AAA", "side": "BUY", "order_quantity": 10},
        {"order_packet_id": "p", "session_id": "s", "ticker": "BBB", "side": "SELL", "order_quantity": 5},
        {"order_packet_id": "p", "session_id": "s", "ticker": "CCC", "side": "BUY", "order_quantity": 4},
    ])
    fills = pd.DataFrame([
            {
                "order_packet_id": "p",
                "session_id": "s",
                "ticker": "AAA",
            "submitted_quantity": 10,
            "submitted_side": "BUY",
            "submitted_at": "",
            "fill_status": "not_submitted",
            "filled_quantity": "",
            "fill_price": "",
            "fill_timestamp": "",
            "rejection_reason": "",
            "partial_fill_reason": "",
            "notes": "",
        },
        {
            "order_packet_id": "p",
            "session_id": "s",
            "ticker": "BBB",
            "submitted_quantity": 5,
            "submitted_side": "SELL",
            "submitted_at": "",
            "fill_status": "rejected",
            "filled_quantity": "",
            "fill_price": "",
            "fill_timestamp": "",
            "rejection_reason": "paper_platform_rejected",
            "partial_fill_reason": "",
            "notes": "",
        },
        {
            "order_packet_id": "p",
            "session_id": "s",
            "ticker": "CCC",
            "submitted_quantity": 4,
            "submitted_side": "BUY",
            "submitted_at": "",
            "fill_status": "partially_filled",
            "filled_quantity": 2,
            "fill_price": 50,
            "fill_timestamp": "2026-06-22T14:30:00Z",
            "rejection_reason": "",
            "partial_fill_reason": "limited_liquidity",
            "notes": "",
        },
    ])
    ledger, shares, cash, blockers = ingest_manual_fills(
        fills=fills,
        packet=packet,
        starting_shares={"AAA": 1, "BBB": 5, "CCC": 0},
        cash_balance=1000.0,
    )
    assert blockers == []
    assert shares["AAA"] == 1
    assert shares["BBB"] == 5
    assert shares["CCC"] == 2
    assert cash == 900.0
    assert len(ledger) == 3


def test_phase23l_duplicate_fill_ingestion_is_rejected() -> None:
    packet = pd.DataFrame([{"order_packet_id": "p", "session_id": "s", "ticker": "AAA"}])
    fills = pd.DataFrame([
        {"order_packet_id": "p", "session_id": "s", "ticker": "AAA"},
        {"order_packet_id": "p", "session_id": "s", "ticker": "AAA"},
    ])
    _ledger, _shares, _cash, blockers = ingest_manual_fills(
        fills=fills,
        packet=packet,
        starting_shares={},
        cash_balance=0.0,
    )
    assert "missing_fill_columns:" in blockers[0] or blockers == ["duplicate_fill_rows"]


def test_phase23l_save_writes_outputs_and_safety_flags_false(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    shadow = reports / "individual_equity_shadow" / "phase23i_prospective_shadow"
    phase23j = reports / "individual_equity_decision_system" / "phase23j_post_endpoint_individual_equity_extension"
    phase23k = reports / "individual_equity_shadow" / "phase23k_prospective_monitoring"
    combined = tmp_path / "data" / "individual_equity_post_endpoint" / "combined"
    for path in [shadow, phase23j, phase23k, combined]:
        path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {
            "portfolio_id": "ridge_top5_equal_weight",
            "ticker": "AMZN",
            "shares": 10,
            "reference_price": 100.0,
            "market_value": 1000.0,
            "cash_balance": "",
            "position_status": "entered_shadow_position",
        },
        {
            "portfolio_id": "ridge_top5_equal_weight",
            "ticker": "CASH",
            "shares": 0,
            "reference_price": 1,
            "market_value": 100.0,
            "cash_balance": 100.0,
            "position_status": "shadow_cash_residual",
        },
    ]).to_csv(shadow / "positions.csv", index=False)
    pd.DataFrame([{
        "session_id": "phase23k_existing",
        "signal_date": "2026-06-12",
        "expected_execution_date": "2026-06-15",
        "observed_execution_date": "2026-06-15",
        "model_id": REQUIRED_MODEL_ID,
        "model_hash": REQUIRED_MODEL_HASH,
    }]).to_csv(phase23k / "phase23k_session_registry.csv", index=False)
    pd.DataFrame([{
        "selected_signal_date": "2026-06-12",
        "expected_execution_date": "2026-06-15",
        "ticker": "AAA",
        "execution_target_shares": 10,
        "target_weight": 0.2,
    }]).to_csv(phase23j / "phase23j_current_target_portfolio.csv", index=False)
    pd.DataFrame([
        {"date": "2026-06-16", "open": 100, "high": 111, "low": 99, "close": 110, "adj_close": 110, "volume": 1}
    ]).to_csv(combined / "AMZN.csv", index=False)
    pd.DataFrame([
        {"date": "2026-06-15", "open": 100, "high": 100, "low": 100, "close": np.nan, "adj_close": np.nan, "volume": 1},
        {"date": "2026-06-16", "open": 101, "high": 105, "low": 100, "close": 104, "adj_close": 104, "volume": 1},
    ]).to_csv(combined / "benchmark_SPY.csv", index=False)
    config = {
        "phase23l_operational_paper_bridge": {
            "enabled": True,
            "output_dir": "reports/individual_equity_shadow/phase23l_operational_paper_bridge",
            "dashboard_status_path": "reports/paper_trading/dashboard/phase23l_status.csv",
            "source_phase23i_shadow_dir": str(shadow),
            "source_phase23j_dir": str(phase23j),
            "source_phase23k_dir": str(phase23k),
            "combined_input_dir": str(combined),
            "post_endpoint_input_dir": str(combined),
            "pilot_input_dir": str(combined),
        }
    }
    outputs = save_phase23l_operational_paper_bridge(config=config, reports_dir=reports)
    assert not outputs["portfolio_valuation_history"].empty
    summary = outputs["summary"].iloc[0]
    assert not bool(summary["live_trading_allowed"])
    assert not bool(summary["real_money_allowed"])
    assert not bool(summary["broker_api_integration_allowed"])
    assert (reports / "individual_equity_shadow" / "phase23l_operational_paper_bridge" / "phase23l_operational_dashboard.md").exists()
