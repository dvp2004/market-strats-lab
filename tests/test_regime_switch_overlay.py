import pandas as pd

from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def make_result(
    dates: pd.DatetimeIndex,
    returns: list[float],
    start_price: float = 100.0,
) -> pd.DataFrame:
    prices = [start_price]

    for return_value in returns[1:]:
        prices.append(prices[-1] * (1.0 + return_value))

    equity = 10_000 * (1.0 + pd.Series(returns)).cumprod()

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": prices,
            "strategy_return": returns,
            "equity": equity,
            "position": [1.0] * len(dates),
            "cash_position": [0.0] * len(dates),
            "turnover": [1.0] + [0.0] * (len(dates) - 1),
        }
    )


def test_regime_switch_overlay_runs_and_switches_to_defensive():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")

    offensive_returns = [0.0]

    for index in range(1, len(dates)):
        if index < 550:
            offensive_returns.append(0.0005)
        else:
            offensive_returns.append(-0.0015)

    defensive_returns = [0.0] + [0.0002] * (len(dates) - 1)

    offensive = make_result(dates, offensive_returns)
    defensive = make_result(dates, defensive_returns)

    result = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive,
        defensive_result=defensive,
        initial_capital=10_000,
        trend_sma_days=200,
        slippage_bps=0.0,
    )

    assert not result.empty
    assert "selected_mode" in result.columns
    assert "defensive_allocator" in set(result["selected_mode"])
    assert "offensive_spy" in set(result["selected_mode"])
    assert result["equity"].iloc[-1] > 0


def test_regime_switch_overlay_rejects_invalid_trend_window():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")
    returns = [0.0] + [0.0002] * (len(dates) - 1)

    offensive = make_result(dates, returns)
    defensive = make_result(dates, returns)

    try:
        run_spy_trend_regime_switch_overlay(
            offensive_result=offensive,
            defensive_result=defensive,
            initial_capital=10_000,
            trend_sma_days=0,
            slippage_bps=0.0,
        )
    except ValueError as error:
        assert "trend_sma_days" in str(error)
    else:
        raise AssertionError("Expected ValueError for invalid trend_sma_days")
    
def test_regime_switch_overlay_with_confirmation_reduces_fast_switching():
    dates = pd.bdate_range("2018-01-01", periods=500)

    offensive_returns = [0.0]

    for index in range(1, len(dates)):
        if index < 250:
            offensive_returns.append(0.0004)
        elif index % 2 == 0:
            offensive_returns.append(-0.0100)
        else:
            offensive_returns.append(0.0105)

    defensive_returns = [0.0] + [0.0001] * (len(dates) - 1)

    offensive = make_result(dates, offensive_returns)
    defensive = make_result(dates, defensive_returns)

    raw_result = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive,
        defensive_result=defensive,
        initial_capital=10_000,
        trend_sma_days=50,
        slippage_bps=0.0,
        confirmation_days=1,
    )

    confirmed_result = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive,
        defensive_result=defensive,
        initial_capital=10_000,
        trend_sma_days=50,
        slippage_bps=0.0,
        confirmation_days=3,
    )

    raw_switches = (
        raw_result["selected_mode"] != raw_result["selected_mode"].shift(1)
    ).sum()

    confirmed_switches = (
        confirmed_result["selected_mode"]
        != confirmed_result["selected_mode"].shift(1)
    ).sum()

    assert confirmed_switches < raw_switches