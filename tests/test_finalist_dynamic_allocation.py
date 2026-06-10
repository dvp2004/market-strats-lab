from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.finalist_dynamic_allocation import (
    compute_inverse_vol_allocation,
    save_phase20b_finalist_dynamic_allocation,
)


CANDIDATE_ID = "canonical_inverse_vol_63d_btc_usd_qqq_spy"


def _candidate_config(*, lookback_days: int = 63) -> dict:
    return {
        "lookback_days": lookback_days,
        "assets": ["SPY", "QQQ", "BTC-USD"],
        "max_asset_weight": 0.50,
        "btc_max_weight": 0.05,
        "require_all_assets": True,
    }


def _prices_from_returns(
    dates: pd.DatetimeIndex,
    returns: list[float],
    *,
    start: float = 100.0,
) -> pd.DataFrame:
    values = [start]
    for ret in returns:
        values.append(values[-1] * (1.0 + ret))
    return pd.DataFrame({"date": dates, "adj_close": values[: len(dates)]})


def _write_price(
    data_dir: Path,
    symbol: str,
    returns: list[float],
    *,
    periods: int = 80,
) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range("2026-01-01", periods=periods)
    frame = _prices_from_returns(dates, returns[: periods - 1], start=100.0)
    frame.to_parquet(data_dir / f"{symbol}.parquet", index=False)


def _write_valid_prices(data_dir: Path, *, periods: int = 80) -> None:
    spy_returns = [0.001 if i % 2 == 0 else -0.001 for i in range(periods - 1)]
    qqq_returns = [0.012 if i % 2 == 0 else -0.012 for i in range(periods - 1)]
    btc_returns = [0.0001 if i % 2 == 0 else -0.0001 for i in range(periods - 1)]
    _write_price(data_dir, "SPY", spy_returns, periods=periods)
    _write_price(data_dir, "QQQ", qqq_returns, periods=periods)
    _write_price(data_dir, "BTC-USD", btc_returns, periods=periods)


def test_inverse_vol_weights_sum_to_one_and_caps_are_enforced(tmp_path):
    data_dir = tmp_path / "data"
    _write_valid_prices(data_dir)

    allocations, diagnostics = compute_inverse_vol_allocation(
        data_dir=data_dir,
        candidate_id=CANDIDATE_ID,
        candidate_config=_candidate_config(),
        selected_signal_date="2026-06-08",
        paper_notional_usd=10000,
        generated_at_utc="2026-06-10T00:00:00+00:00",
    )

    assert diagnostics.loc[0, "allocation_status"] == "dynamic_allocation_resolved"
    assert abs(float(allocations["final_weight"].sum()) - 1.0) < 1e-8
    weights = dict(zip(allocations["asset"], allocations["final_weight"], strict=False))
    assert weights["BTC-USD"] <= 0.05 + 1e-8
    assert max(weights.values()) <= 0.50 + 1e-8
    assert diagnostics.loc[0, "btc_weight"] <= 0.05 + 1e-8
    assert "BTC-USD" in str(diagnostics.loc[0, "cap_binding_assets"])
    assert "SPY" in str(diagnostics.loc[0, "cap_binding_assets"])


def test_missing_asset_file_fails_closed(tmp_path):
    data_dir = tmp_path / "data"
    _write_valid_prices(data_dir)
    (data_dir / "QQQ.parquet").unlink()

    allocations, diagnostics = compute_inverse_vol_allocation(
        data_dir=data_dir,
        candidate_id=CANDIDATE_ID,
        candidate_config=_candidate_config(),
        selected_signal_date="2026-06-08",
        paper_notional_usd=10000,
    )

    assert diagnostics.loc[0, "allocation_status"] == "dynamic_allocation_blocked"
    assert "QQQ:file_missing" in diagnostics.loc[0, "blocking_reason"]
    assert not allocations["paper_preview_allowed"].any()


def test_insufficient_lookback_fails_closed(tmp_path):
    data_dir = tmp_path / "data"
    _write_valid_prices(data_dir, periods=20)

    _allocations, diagnostics = compute_inverse_vol_allocation(
        data_dir=data_dir,
        candidate_id=CANDIDATE_ID,
        candidate_config=_candidate_config(lookback_days=63),
        selected_signal_date="2026-06-08",
        paper_notional_usd=10000,
    )

    assert diagnostics.loc[0, "allocation_status"] == "dynamic_allocation_blocked"
    assert diagnostics.loc[0, "blocking_reason"] == "insufficient_lookback_rows"


def test_zero_or_negative_price_fails_closed(tmp_path):
    data_dir = tmp_path / "data"
    _write_valid_prices(data_dir)
    frame = pd.read_parquet(data_dir / "SPY.parquet")
    frame.loc[0, "adj_close"] = -1.0
    frame.to_parquet(data_dir / "SPY.parquet", index=False)

    _allocations, diagnostics = compute_inverse_vol_allocation(
        data_dir=data_dir,
        candidate_id=CANDIDATE_ID,
        candidate_config=_candidate_config(),
        selected_signal_date="2026-06-08",
        paper_notional_usd=10000,
    )

    assert diagnostics.loc[0, "allocation_status"] == "dynamic_allocation_blocked"
    assert "SPY:non_positive_price_present" in diagnostics.loc[0, "blocking_reason"]


def test_duplicate_dates_fail_closed(tmp_path):
    data_dir = tmp_path / "data"
    _write_valid_prices(data_dir)
    frame = pd.read_parquet(data_dir / "SPY.parquet")
    frame.loc[1, "date"] = frame.loc[0, "date"]
    frame.to_parquet(data_dir / "SPY.parquet", index=False)

    _allocations, diagnostics = compute_inverse_vol_allocation(
        data_dir=data_dir,
        candidate_id=CANDIDATE_ID,
        candidate_config=_candidate_config(),
        selected_signal_date="2026-06-08",
        paper_notional_usd=10000,
    )

    assert diagnostics.loc[0, "allocation_status"] == "dynamic_allocation_blocked"
    assert "SPY:duplicate_dates_present" in diagnostics.loc[0, "blocking_reason"]


def test_save_writes_diagnostics_and_safety_flags_false(tmp_path):
    data_dir = tmp_path / "data"
    _write_valid_prices(data_dir)
    hardening_dir = tmp_path / "reports" / "paper_trading" / "operational_hardening"
    hardening_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"category": "signal", "key": "selected_signal_date", "value": "2026-06-08"}]
    ).to_csv(hardening_dir / "daily_execution_tear_sheet.csv", index=False)

    config = {
        "phase20b_finalist_dynamic_allocation": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "paper_trading" / "finalist_tracking"),
            "dashboard_dir": str(tmp_path / "reports" / "paper_trading" / "dashboard"),
            "source_fresh_processed_dir": str(data_dir),
            "source_daily_execution_tear_sheet": str(
                hardening_dir / "daily_execution_tear_sheet.csv"
            ),
            "paper_notional_usd": 10000,
            "inverse_vol_candidates": {CANDIDATE_ID: _candidate_config()},
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        }
    }

    outputs = save_phase20b_finalist_dynamic_allocation(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    out_dir = tmp_path / "reports" / "paper_trading" / "finalist_tracking"

    assert (out_dir / "finalist_dynamic_allocations.csv").exists()
    assert (out_dir / "finalist_dynamic_allocation_diagnostics.csv").exists()
    assert outputs["summary"].loc[0, "phase20b_decision"] == (
        "finalist_dynamic_allocation_completed_manual_preview_only"
    )
    assert not outputs["summary"].loc[0, "live_trading_allowed"]
    assert not outputs["summary"].loc[0, "real_money_allowed"]
    assert not outputs["summary"].loc[0, "broker_api_integration_allowed"]
    assert np.isclose(
        outputs["finalist_dynamic_allocations"]["final_weight"].astype(float).sum(),
        1.0,
    )
