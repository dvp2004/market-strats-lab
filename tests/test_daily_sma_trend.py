import pandas as pd

from market_strats.strategies.daily_sma_trend import run_daily_sma_trend_strategy


def test_daily_sma_strategy_eventually_enters_clear_uptrend():
    dates = pd.bdate_range("2020-01-01", periods=300)
    prices = pd.Series(range(100, 400), dtype=float)

    input_prices = pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "adj_close": prices,
            "volume": 1_000_000,
        }
    )

    result = run_daily_sma_trend_strategy(
        prices=input_prices,
        initial_capital=10_000,
        sma_days=200,
        slippage_bps=0,
    )

    assert result["position"].iloc[0] == 0.0
    assert result["position"].iloc[-1] == 1.0
    assert result["turnover"].sum() == 1.0


def test_daily_sma_strategy_stays_out_during_clear_downtrend():
    dates = pd.bdate_range("2020-01-01", periods=300)
    prices = pd.Series(range(400, 100, -1), dtype=float)

    input_prices = pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "adj_close": prices,
            "volume": 1_000_000,
        }
    )

    result = run_daily_sma_trend_strategy(
        prices=input_prices,
        initial_capital=10_000,
        sma_days=200,
        slippage_bps=0,
    )

    assert result["position"].iloc[-1] == 0.0
    assert result["turnover"].sum() == 0.0