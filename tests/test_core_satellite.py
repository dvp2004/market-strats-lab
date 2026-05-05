import pandas as pd
import pytest

from market_strats.strategies.core_satellite import (
    run_independent_core_satellite_strategy,
)


def make_result(
    dates: pd.DatetimeIndex,
    equity: list[float],
    position: list[float],
    turnover: list[float],
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": equity,
            "strategy_return": pd.Series(equity).pct_change().fillna(0.0),
            "equity": equity,
            "position": position,
            "cash_position": [1.0 - value for value in position],
            "turnover": turnover,
        }
    )


def test_independent_core_satellite_starts_at_initial_capital():
    dates = pd.bdate_range("2020-01-01", periods=3)

    core = make_result(
        dates=dates,
        equity=[10_000, 11_000, 12_000],
        position=[1.0, 1.0, 1.0],
        turnover=[1.0, 0.0, 0.0],
    )
    satellite = make_result(
        dates=dates,
        equity=[10_000, 10_500, 10_000],
        position=[1.0, 1.0, 0.0],
        turnover=[1.0, 0.0, 1.0],
    )

    result = run_independent_core_satellite_strategy(
        core_result=core,
        satellite_result=satellite,
        initial_capital=10_000,
        core_weight=0.60,
        satellite_weight=0.40,
        strategy_name="Test Core Satellite",
    )

    assert result["equity"].iloc[0] == 10_000
    assert result["strategy_return"].iloc[0] == 0.0


def test_independent_core_satellite_combines_sleeve_equity_without_rebalancing():
    dates = pd.bdate_range("2020-01-01", periods=3)

    core = make_result(
        dates=dates,
        equity=[10_000, 12_000, 14_000],
        position=[1.0, 1.0, 1.0],
        turnover=[1.0, 0.0, 0.0],
    )
    satellite = make_result(
        dates=dates,
        equity=[10_000, 10_000, 10_000],
        position=[0.0, 0.0, 0.0],
        turnover=[0.0, 0.0, 0.0],
    )

    result = run_independent_core_satellite_strategy(
        core_result=core,
        satellite_result=satellite,
        initial_capital=10_000,
        core_weight=0.60,
        satellite_weight=0.40,
        strategy_name="Test Core Satellite",
    )

    expected_final_equity = (0.60 * 10_000 * 1.40) + (0.40 * 10_000 * 1.00)

    assert result["equity"].iloc[-1] == expected_final_equity


def test_independent_core_satellite_rejects_invalid_weights():
    dates = pd.bdate_range("2020-01-01", periods=3)

    core = make_result(
        dates=dates,
        equity=[10_000, 11_000, 12_000],
        position=[1.0, 1.0, 1.0],
        turnover=[1.0, 0.0, 0.0],
    )
    satellite = make_result(
        dates=dates,
        equity=[10_000, 10_500, 10_000],
        position=[1.0, 1.0, 0.0],
        turnover=[1.0, 0.0, 1.0],
    )

    with pytest.raises(ValueError):
        run_independent_core_satellite_strategy(
            core_result=core,
            satellite_result=satellite,
            initial_capital=10_000,
            core_weight=0.70,
            satellite_weight=0.40,
            strategy_name="Invalid",
        )