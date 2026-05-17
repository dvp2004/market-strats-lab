import pandas as pd

from market_strats.analysis.regime_switch_overlay_stress_confirmation import (
    _create_stress_state_frame,
    _variant_guard_inputs,
)


def test_create_stress_state_frame():
    dates = pd.bdate_range("2020-01-01", periods=260)
    prices = [100.0] * 220 + [95.0] * 20 + [85.0] * 20

    offensive = pd.DataFrame(
        {
            "date": dates,
            "adj_close": prices,
            "strategy_return": pd.Series(prices).pct_change().fillna(0.0),
        }
    )

    state = _create_stress_state_frame(
        offensive_result=offensive,
        trend_sma_days=20,
        volatility_window_days=20,
    )

    assert "realized_vol_annualized" in state.columns
    assert "return_20d" in state.columns
    assert "trend_distance" in state.columns
    assert state["drawdown"].min() < -0.10


def test_variant_guard_inputs_composite():
    dates = pd.bdate_range("2020-01-01", periods=5)

    guards = {
        "deep_drawdown_guard": pd.Series([True, True, False, True, True], index=dates),
        "vol_stress": pd.Series([True, False, False, True, False], index=dates),
        "return_shock_stress": pd.Series([False, True, False, False, False], index=dates),
        "trend_distance_stress": pd.Series([False, False, True, False, False], index=dates),
        "composite_stress": pd.Series([True, True, True, True, False], index=dates),
        "relief_condition": pd.Series([False, True, True, False, True], index=dates),
    }

    defensive_allowed, offensive_allowed, defensive_name, offensive_name = (
        _variant_guard_inputs(
            variant_name="combined_composite_stress_relief_confirmation",
            guards=guards,
        )
    )

    assert defensive_allowed.tolist() == [True, True, False, True, False]
    assert offensive_allowed.tolist() == [False, True, True, False, True]
    assert defensive_name == "deep_drawdown_guard_and_composite_stress"
    assert offensive_name == "offensive_relief_confirmation"