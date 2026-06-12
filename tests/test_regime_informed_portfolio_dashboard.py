import json
from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.regime_informed_portfolio_dashboard import (
    HISTORICAL_CHARTS,
    NOTEBOOK_SECTIONS,
    build_regime_informed_portfolio_dashboard,
)


def _write_price(root: Path, symbol: str, dates: pd.DatetimeIndex, start: float, drift: float) -> None:
    price = start * (1.0 + drift + np.sin(np.arange(len(dates)) / 15) * 0.002).cumprod()
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": price,
            "high": price * 1.01,
            "low": price * 0.99,
            "close": price,
            "adj_close": price,
            "volume": 1000,
        }
    )
    output_dir = root / "data" / "fresh" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_dir / f"{symbol}.parquet", index=False)


def _write_sources(root: Path, include_prices: bool = True) -> None:
    dates = pd.bdate_range("2020-01-01", periods=170)
    if include_prices:
        _write_price(root, "SPY", dates, 100.0, 0.0004)
        _write_price(root, "QQQ", dates, 120.0, 0.0006)
        _write_price(root, "GLD", dates, 90.0, 0.0002)
        _write_price(root, "TLT", dates, 80.0, 0.0001)
        _write_price(root, "BTC-USD", dates, 9000.0, 0.0010)
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    phase6_value = 10_000 * (1.0 + pd.Series(np.full(len(dates), 0.0003))).cumprod()
    pd.DataFrame(
        {
            "source_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "decision_date": dates,
            "strategy_return": 0.0003,
            "SPY_return": 0.0004,
            "candidate_equity": phase6_value,
            "benchmark_equity": phase6_value,
            "exposure": 1.0,
            "mode": "offensive_spy",
        }
    ).to_csv(
        reports_dir / "phase6b_loose_relief_execution_realistic_overlay_daily.csv",
        index=False,
    )
    tracking_dir = reports_dir / "paper_trading" / "regime_informed_tracking"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    candidates = {
        "phase6b_loose_relief_execution_realistic_overlay": [("SPY", 1.0), ("CASH", 0.0)],
        "canonical_spy_qqq_gld_tlt_50_30_10_10": [
            ("SPY", 0.5),
            ("QQQ", 0.3),
            ("GLD", 0.1),
            ("TLT", 0.1),
        ],
        "canonical_inverse_vol_63d_btc_usd_qqq_spy": [
            ("SPY", 0.5),
            ("QQQ", 0.45),
            ("BTC-USD", 0.05),
        ],
        "canonical_spy_qqq_60_40": [("SPY", 0.6), ("QQQ", 0.4)],
    }
    for candidate_id, assets in candidates.items():
        for asset, weight in assets:
            rows.append(
                {
                    "session_date": "2026-06-11",
                    "selected_signal_date": "2026-06-08",
                    "canonical_candidate_id": candidate_id,
                    "candidate_role": "reference_only" if "60_40" in candidate_id else "candidate",
                    "asset": asset,
                    "target_weight": weight,
                    "target_notional_usd": weight * 10_000,
                    "manual_decision": "skip_due_warning",
                    "manual_execution_status": "skipped",
                    "paper_account_value": 10_000,
                    "paper_fill_price": "",
                    "paper_fill_quantity": "",
                    "actual_notional_usd": "",
                    "deviation_from_preview_usd": "",
                    "deviation_from_preview_pct": "",
                    "override_reason": "first_regime_informed_workflow_validation_cycle",
                    "notes": "Latest valid session was skipped due warning.",
                    "candidate_caveats": "paper-only",
                    "promotion_allowed": False,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                }
            )
    pd.DataFrame(rows).to_csv(
        tracking_dir / "regime_informed_manual_session_ledger.csv",
        index=False,
    )


def test_portfolio_dashboard_writes_performance_csvs_and_notebook(tmp_path):
    _write_sources(tmp_path)
    outputs = build_regime_informed_portfolio_dashboard(
        root=tmp_path,
        performance_dir=tmp_path / "performance",
        visuals_dir=tmp_path / "visuals",
        notebook_path=tmp_path / "notebook.ipynb",
    )

    required_csvs = [
        "csv_native_summary",
        "csv_common_summary",
        "csv_daily_equity",
        "csv_daily_drawdowns",
        "csv_daily_weights",
        "csv_trade_blotter",
        "csv_cash_ledger",
        "csv_holdings",
        "csv_status",
    ]
    for key in required_csvs:
        assert outputs[key].exists()
    assert outputs["notebook"].exists()
    for key in HISTORICAL_CHARTS:
        assert outputs[f"chart_{key}"].exists()


def test_skipped_only_ledger_keeps_cash_and_no_positions(tmp_path):
    _write_sources(tmp_path)
    outputs = build_regime_informed_portfolio_dashboard(
        root=tmp_path,
        performance_dir=tmp_path / "performance",
        visuals_dir=tmp_path / "visuals",
        notebook_path=tmp_path / "notebook.ipynb",
    )

    cash = pd.read_csv(outputs["csv_cash_ledger"])
    blotter = pd.read_csv(outputs["csv_trade_blotter"])
    holdings = pd.read_csv(outputs["csv_holdings"])
    status = pd.read_csv(outputs["csv_status"])

    assert cash["entered_notional"].sum() == 0
    assert set(cash["cash_remaining"]) == {10_000.0}
    assert not status.loc[0, "paper_positions_exist"]
    assert holdings.empty
    assert set(blotter["action"]) == {"SKIPPED"}
    assert set(blotter["fill_timestamp_status"]) == {"not_recorded_date_only"}


def test_spy_buy_hold_benchmark_is_historical_only(tmp_path):
    _write_sources(tmp_path)
    outputs = build_regime_informed_portfolio_dashboard(
        root=tmp_path,
        performance_dir=tmp_path / "performance",
        visuals_dir=tmp_path / "visuals",
        notebook_path=tmp_path / "notebook.ipynb",
    )

    native = pd.read_csv(outputs["csv_native_summary"])
    common = pd.read_csv(outputs["csv_common_summary"])
    equity = pd.read_csv(outputs["csv_daily_equity"])
    cash = pd.read_csv(outputs["csv_cash_ledger"])
    benchmark = "SPY Buy & Hold Benchmark"
    assert benchmark in set(native["candidate_id"])
    assert benchmark in set(common["candidate_id"])
    assert benchmark in set(equity["canonical_candidate_id"])
    assert set(native.loc[native["candidate_id"] == benchmark, "candidate_role"]) == {
        "benchmark_only"
    }
    assert benchmark not in set(cash["canonical_candidate_id"])


def test_native_and_common_summaries_contain_dates(tmp_path):
    _write_sources(tmp_path)
    outputs = build_regime_informed_portfolio_dashboard(
        root=tmp_path,
        performance_dir=tmp_path / "performance",
        visuals_dir=tmp_path / "visuals",
        notebook_path=tmp_path / "notebook.ipynb",
    )

    native = pd.read_csv(outputs["csv_native_summary"])
    common = pd.read_csv(outputs["csv_common_summary"])
    assert native["start_date"].astype(str).str.len().min() >= 10
    assert native["end_date"].astype(str).str.len().min() >= 10
    assert common["common_start_date"].astype(str).str.len().min() >= 10
    assert common["common_end_date"].astype(str).str.len().min() >= 10


def test_notebook_has_required_sections_and_safety_language(tmp_path):
    _write_sources(tmp_path)
    outputs = build_regime_informed_portfolio_dashboard(
        root=tmp_path,
        performance_dir=tmp_path / "performance",
        visuals_dir=tmp_path
        / "reports"
        / "paper_trading"
        / "regime_informed_tracking"
        / "performance_visuals",
        notebook_path=tmp_path / "notebooks" / "notebook.ipynb",
    )

    notebook = json.loads(outputs["notebook"].read_text(encoding="utf-8"))
    text = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    for heading in NOTEBOOK_SECTIONS:
        assert heading in text
    assert "No entered paper trades yet" in text
    assert "NO LIVE TRADING" in text
    assert "NO REAL MONEY" in text
    assert "NO BROKER/API" in text
    assert "NO STRATEGY PROMOTION" in text
    assert "../reports/" in text
    assert "Missing image" in text


def test_missing_data_writes_placeholder_outputs_without_crashing(tmp_path):
    _write_sources(tmp_path, include_prices=False)
    outputs = build_regime_informed_portfolio_dashboard(
        root=tmp_path,
        performance_dir=tmp_path / "performance",
        visuals_dir=tmp_path / "visuals",
        notebook_path=tmp_path / "notebook.ipynb",
    )

    native = pd.read_csv(outputs["csv_native_summary"])
    assert outputs["notebook"].exists()
    assert "historical data missing" in " ".join(native["notes"].astype(str))


def test_safety_flags_are_false(tmp_path):
    _write_sources(tmp_path)
    outputs = build_regime_informed_portfolio_dashboard(
        root=tmp_path,
        performance_dir=tmp_path / "performance",
        visuals_dir=tmp_path / "visuals",
        notebook_path=tmp_path / "notebook.ipynb",
    )

    status = pd.read_csv(outputs["csv_status"])
    assert not status.loc[0, "promotion_allowed"]
    assert not status.loc[0, "live_trading_allowed"]
    assert not status.loc[0, "real_money_allowed"]
    assert not status.loc[0, "broker_api_integration_allowed"]
