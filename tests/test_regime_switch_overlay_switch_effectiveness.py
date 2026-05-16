import pandas as pd

from market_strats.analysis.regime_switch_overlay_switch_effectiveness import (
    _compound_return,
    _create_switch_effectiveness_events,
    _mode_to_return_column,
)


def test_compound_return():
    returns = pd.Series([0.01, 0.02, -0.01])
    expected = (1.01 * 1.02 * 0.99) - 1.0

    assert round(_compound_return(returns), 8) == round(expected, 8)


def test_mode_to_return_column():
    assert _mode_to_return_column("offensive_spy") == "strategy_return_offensive"
    assert (
        _mode_to_return_column("defensive_allocator")
        == "strategy_return_defensive"
    )


def test_create_switch_effectiveness_events():
    dates = pd.bdate_range("2020-01-01", periods=10)

    overlay = pd.DataFrame(
        {
            "date": dates,
            "equity": [
                100.0,
                101.0,
                102.0,
                103.0,
                104.0,
                105.0,
                106.0,
                107.0,
                108.0,
                109.0,
            ],
            "target_defensive_weight": [
                0.0,
                0.0,
                1.0,
                1.0,
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
            "signal_price": [100.0, 99.0, 98.0, 97.0, 96.0, 98.0, 99.0, 100.0, 101.0, 102.0],
            "trend_sma": [100.0] * 10,
            "applied_overlay_slippage_bps": [5.0] * 10,
            "overlay_slippage_cost": [0.0, 0.0, 0.001, 0.0, 0.0, 0.001, 0.0, 0.0, 0.0, 0.0],
        }
    )

    offensive = pd.DataFrame(
        {
            "date": dates,
            "strategy_return": [0.0, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
        }
    )
    defensive = pd.DataFrame(
        {
            "date": dates,
            "strategy_return": [0.0, 0.0, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005, 0.005],
        }
    )

    events = _create_switch_effectiveness_events(
        overlay_result=overlay,
        offensive_result=offensive,
        defensive_result=defensive,
        horizons=[2],
    )

    assert len(events) == 2
    assert events.iloc[0]["from_mode"] == "offensive_spy"
    assert events.iloc[0]["to_mode"] == "defensive_allocator"
    assert "switch_value_added_2d_pct_points" in events.columns