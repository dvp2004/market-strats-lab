import pandas as pd

from market_strats.analysis.regime_switch_overlay_raw_close_signal_sensitivity import (
    create_regime_switch_overlay_raw_close_signal_sensitivity,
    create_regime_switch_overlay_raw_close_signal_sensitivity_summary,
)


def make_result(
    dates: pd.DatetimeIndex,
    daily_return: float,
    include_close: bool = False,
) -> pd.DataFrame:
    returns = [0.0] + [daily_return] * (len(dates) - 1)
    equity = 10_000 * (1.0 + pd.Series(returns)).cumprod()

    frame = pd.DataFrame(
        {
            "date": dates,
            "adj_close": equity,
            "strategy_return": returns,
            "equity": equity,
            "position": [1.0] * len(dates),
            "cash_position": [0.0] * len(dates),
            "turnover": [1.0] + [0.0] * (len(dates) - 1),
        }
    )

    if include_close:
        frame["close"] = frame["adj_close"] * 1.01

    return frame


def test_create_regime_switch_overlay_raw_close_signal_sensitivity_runs():
    dates = pd.bdate_range("2010-01-01", "2020-12-31")

    allocator_result = make_result(dates, 0.0004)
    spy_result = make_result(dates, 0.0005, include_close=True)

    relative_momentum_outputs = {
        "Defensive Allocator": {
            "allocator_result": allocator_result,
        }
    }

    ticker_outputs = {
        "SPY": {
            "data": spy_result,
            "strategy_results": {
                "Buy and Hold": spy_result,
            },
        }
    }

    config = {
        "initial_capital": 10_000,
        "slippage_bps": 5.0,
        "regime_switch_overlay": {
            "enabled": True,
            "name": "Test Overlay",
            "benchmark_ticker": "SPY",
            "offensive_strategy": "Buy and Hold",
            "defensive_allocator_name": "Defensive Allocator",
            "trend_sma_days": 200,
            "confirmation_days": 3,
        },
        "regime_switch_overlay_raw_close_signal_sensitivity": {
            "enabled": True,
            "benchmark_ticker": "SPY",
            "raw_close_column_candidates": ["close"],
            "reference_end_date": "2015-12-31",
            "holdout_start_date": "2016-01-01",
        },
    }

    sensitivity = create_regime_switch_overlay_raw_close_signal_sensitivity(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    assert not sensitivity.empty
    assert {"adjusted_close_signal", "raw_close_signal"}.issubset(
        set(sensitivity["signal_type"])
    )
    assert {"full", "reference", "holdout"}.issubset(set(sensitivity["period"]))
    assert "cagr_pct" in sensitivity.columns
    assert "calmar" in sensitivity.columns


def test_create_regime_switch_overlay_raw_close_signal_sensitivity_summary_runs():
    sensitivity = pd.DataFrame(
        {
            "period": ["full", "full", "holdout", "holdout"],
            "signal_type": [
                "adjusted_close_signal",
                "raw_close_signal",
                "adjusted_close_signal",
                "raw_close_signal",
            ],
            "cagr_pct": [10.0, 9.8, 12.0, 11.7],
            "calmar": [0.4, 0.39, 0.5, 0.48],
            "max_drawdown_pct": [-25.0, -25.5, -20.0, -21.0],
            "end_value": [70_000, 68_000, 32_000, 31_000],
            "trade_count": [50, 52, 20, 22],
        }
    )

    summary = create_regime_switch_overlay_raw_close_signal_sensitivity_summary(
        sensitivity
    )

    assert not summary.empty
    assert "raw_minus_adjusted_cagr_pct_points" in summary.columns
    assert "raw_minus_adjusted_end_value" in summary.columns

    full = summary[summary["period"] == "full"].iloc[0]
    assert full["raw_minus_adjusted_cagr_pct_points"] == -0.2
    assert full["raw_minus_adjusted_end_value"] == -2000