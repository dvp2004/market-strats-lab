import pandas as pd

from market_strats.analysis.regime_switch_overlay_slippage_sensitivity import (
    create_regime_switch_overlay_slippage_sensitivity,
    create_regime_switch_overlay_slippage_sensitivity_summary,
)


def make_result(
    dates: pd.DatetimeIndex,
    daily_return: float,
) -> pd.DataFrame:
    returns = [0.0] + [daily_return] * (len(dates) - 1)
    equity = 10_000 * (1.0 + pd.Series(returns)).cumprod()

    return pd.DataFrame(
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


def test_create_regime_switch_overlay_slippage_sensitivity_runs():
    dates = pd.bdate_range("2010-01-01", "2020-12-31")

    allocator_result = make_result(dates, 0.0004)
    spy_result = make_result(dates, 0.0005)

    relative_momentum_outputs = {
        "Defensive Allocator": {
            "allocator_result": allocator_result,
        }
    }

    ticker_outputs = {
        "SPY": {
            "strategy_results": {
                "Buy and Hold": spy_result,
            }
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
        "regime_switch_overlay_slippage_sensitivity": {
            "enabled": True,
            "slippage_bps_values": [0, 5, 10],
            "reference_end_date": "2015-12-31",
            "holdout_start_date": "2016-01-01",
        },
    }

    sensitivity = create_regime_switch_overlay_slippage_sensitivity(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    assert not sensitivity.empty
    assert set(sensitivity["slippage_bps"]) == {0.0, 5.0, 10.0}
    assert {"full", "reference", "holdout"}.issubset(set(sensitivity["period"]))
    assert "cagr_pct" in sensitivity.columns
    assert "calmar" in sensitivity.columns


def test_create_regime_switch_overlay_slippage_sensitivity_summary_runs():
    sensitivity = pd.DataFrame(
        {
            "period": ["full", "full", "holdout", "holdout"],
            "slippage_bps": [5.0, 50.0, 5.0, 50.0],
            "cagr_pct": [10.0, 9.5, 12.0, 11.2],
            "calmar": [0.4, 0.35, 0.5, 0.45],
            "max_drawdown_pct": [-25.0, -27.0, -20.0, -22.0],
            "end_value": [70_000, 65_000, 32_000, 30_000],
        }
    )

    summary = create_regime_switch_overlay_slippage_sensitivity_summary(
        sensitivity=sensitivity,
        baseline_slippage_bps=5.0,
    )

    assert not summary.empty
    assert "cagr_drag_pct_points" in summary.columns
    assert "end_value_delta" in summary.columns

    full = summary[summary["period"] == "full"].iloc[0]
    assert full["cagr_drag_pct_points"] == -0.5
    assert full["end_value_delta"] == -5000