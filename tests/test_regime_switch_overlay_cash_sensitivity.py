import pandas as pd

from market_strats.analysis.regime_switch_overlay_cash_sensitivity import (
    create_regime_switch_overlay_cash_sensitivity,
    create_regime_switch_overlay_cash_sensitivity_summary,
)


def make_overlay_result(
    dates: pd.DatetimeIndex,
    daily_return: float,
    cash_position: float,
) -> pd.DataFrame:
    returns = [0.0] + [daily_return] * (len(dates) - 1)
    equity = 10_000 * (1.0 + pd.Series(returns)).cumprod()

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": equity,
            "strategy_return": returns,
            "equity": equity,
            "position": [1.0 - cash_position] * len(dates),
            "cash_position": [cash_position] * len(dates),
            "turnover": [1.0] + [0.0] * (len(dates) - 1),
        }
    )


def test_create_regime_switch_overlay_cash_sensitivity_runs():
    dates = pd.bdate_range("2010-01-01", "2020-12-31")

    overlay_result = make_overlay_result(
        dates=dates,
        daily_return=0.0004,
        cash_position=0.25,
    )

    overlay_outputs = {
        "overlay_result": overlay_result,
    }

    config = {
        "initial_capital": 10_000,
        "regime_switch_overlay": {
            "enabled": True,
            "name": "Test Overlay",
        },
        "regime_switch_overlay_cash_sensitivity": {
            "enabled": True,
            "baseline_cash_annual_yield_pct": 4.0,
            "cash_yield_multipliers": [0.0, 0.5, 1.0],
            "reference_end_date": "2015-12-31",
            "holdout_start_date": "2016-01-01",
        },
    }

    sensitivity = create_regime_switch_overlay_cash_sensitivity(
        overlay_outputs=overlay_outputs,
        config=config,
    )

    assert not sensitivity.empty
    assert set(sensitivity["cash_yield_multiplier"]) == {0.0, 0.5, 1.0}
    assert {"full", "reference", "holdout"}.issubset(set(sensitivity["period"]))
    assert "cagr_pct" in sensitivity.columns
    assert "avg_cash_position_pct" in sensitivity.columns


def test_create_regime_switch_overlay_cash_sensitivity_summary_runs():
    sensitivity = pd.DataFrame(
        {
            "period": ["full", "full", "holdout", "holdout"],
            "cash_yield_multiplier": [1.0, 0.0, 1.0, 0.0],
            "scenario_cash_annual_yield_pct": [4.0, 0.0, 4.0, 0.0],
            "cagr_pct": [10.0, 9.0, 12.0, 11.0],
            "calmar": [0.4, 0.35, 0.5, 0.45],
            "max_drawdown_pct": [-25.0, -27.0, -20.0, -22.0],
            "end_value": [70_000, 65_000, 32_000, 30_000],
            "avg_cash_position_pct": [20.0, 20.0, 25.0, 25.0],
        }
    )

    summary = create_regime_switch_overlay_cash_sensitivity_summary(
        sensitivity=sensitivity,
        baseline_multiplier=1.0,
    )

    assert not summary.empty
    assert "zero_cash_cagr_drag_pct_points" in summary.columns
    assert "zero_cash_end_value_delta" in summary.columns

    full = summary[summary["period"] == "full"].iloc[0]
    assert full["zero_cash_cagr_drag_pct_points"] == -1.0
    assert full["zero_cash_end_value_delta"] == -5000