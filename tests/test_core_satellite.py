import pandas as pd
import pytest

from market_strats.strategies.core_satellite import (
    run_annual_rebalanced_core_satellite_strategy,
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

def test_annual_rebalanced_core_satellite_starts_at_initial_capital():
    dates = pd.bdate_range("2020-01-01", periods=260)

    core = make_result(
        dates=dates,
        equity=[10_000 + index for index in range(260)],
        position=[1.0] * 260,
        turnover=[1.0] + [0.0] * 259,
    )
    satellite = make_result(
        dates=dates,
        equity=[10_000] * 260,
        position=[0.0] * 260,
        turnover=[0.0] * 260,
    )

    result = run_annual_rebalanced_core_satellite_strategy(
        core_result=core,
        satellite_result=satellite,
        initial_capital=10_000,
        core_weight=0.60,
        satellite_weight=0.40,
        strategy_name="Annual Rebalanced Test",
        slippage_bps=0,
    )

    assert result["equity"].iloc[0] == 10_000
    assert result["strategy_return"].iloc[0] == 0.0


def test_annual_rebalanced_core_satellite_creates_rebalance_days():
    dates = pd.bdate_range("2020-01-01", "2022-01-10")

    core = make_result(
        dates=dates,
        equity=list(range(10_000, 10_000 + len(dates))),
        position=[1.0] * len(dates),
        turnover=[1.0] + [0.0] * (len(dates) - 1),
    )
    satellite = make_result(
        dates=dates,
        equity=[10_000] * len(dates),
        position=[0.0] * len(dates),
        turnover=[0.0] * len(dates),
    )

    result = run_annual_rebalanced_core_satellite_strategy(
        core_result=core,
        satellite_result=satellite,
        initial_capital=10_000,
        core_weight=0.60,
        satellite_weight=0.40,
        strategy_name="Annual Rebalanced Test",
        slippage_bps=0,
    )

    assert result["is_rebalance_day"].sum() >= 1
    assert "rebalance_turnover" in result.columns

def test_annual_rebalanced_core_satellite_supports_custom_rebalance_month():
    dates = pd.bdate_range("2020-01-01", "2021-12-31")

    core = make_result(
        dates=dates,
        equity=list(range(10_000, 10_000 + len(dates))),
        position=[1.0] * len(dates),
        turnover=[1.0] + [0.0] * (len(dates) - 1),
    )
    satellite = make_result(
        dates=dates,
        equity=[10_000] * len(dates),
        position=[0.0] * len(dates),
        turnover=[0.0] * len(dates),
    )

    result = run_annual_rebalanced_core_satellite_strategy(
        core_result=core,
        satellite_result=satellite,
        initial_capital=10_000,
        core_weight=0.60,
        satellite_weight=0.40,
        strategy_name="Annual Rebalanced Test",
        slippage_bps=0,
        rebalance_month=6,
    )

    rebalance_dates = result.loc[result["is_rebalance_day"], "date"]

    assert not rebalance_dates.empty
    assert set(pd.to_datetime(rebalance_dates).dt.month) == {6}

def test_annual_rebalanced_core_satellite_rejects_invalid_rebalance_month():
    dates = pd.bdate_range("2020-01-01", periods=260)

    core = make_result(
        dates=dates,
        equity=[10_000 + index for index in range(260)],
        position=[1.0] * 260,
        turnover=[1.0] + [0.0] * 259,
    )
    satellite = make_result(
        dates=dates,
        equity=[10_000] * 260,
        position=[0.0] * 260,
        turnover=[0.0] * 260,
    )

    with pytest.raises(ValueError):
        run_annual_rebalanced_core_satellite_strategy(
            core_result=core,
            satellite_result=satellite,
            initial_capital=10_000,
            core_weight=0.60,
            satellite_weight=0.40,
            strategy_name="Annual Rebalanced Test",
            slippage_bps=0,
            rebalance_month=13,
        )