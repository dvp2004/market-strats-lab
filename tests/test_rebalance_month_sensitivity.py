import pandas as pd

from market_strats.analysis.rebalance_month_sensitivity import (
    run_rebalance_month_sensitivity,
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


def test_run_rebalance_month_sensitivity_returns_one_row_per_month():
    dates = pd.bdate_range("2015-01-01", "2022-12-31")

    core = make_result(
        dates=dates,
        equity=[10_000 + index for index in range(len(dates))],
        position=[1.0] * len(dates),
        turnover=[1.0] + [0.0] * (len(dates) - 1),
    )
    satellite = make_result(
        dates=dates,
        equity=[10_000] * len(dates),
        position=[0.0] * len(dates),
        turnover=[0.0] * len(dates),
    )

    result = run_rebalance_month_sensitivity(
        core_result=core,
        satellite_result=satellite,
        initial_capital=10_000,
        core_weight=0.60,
        satellite_weight=0.40,
        slippage_bps=0,
        rebalance_months=[3, 6, 9, 12],
    )

    assert len(result) == 4
    assert set(result["rebalance_month"]) == {3, 6, 9, 12}
    assert "end_value" in result.columns
    assert "worst_5y_cagr_pct" in result.columns