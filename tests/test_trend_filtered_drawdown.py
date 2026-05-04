import pandas as pd
import pytest

from market_strats.strategies.trend_filtered_drawdown import (
    run_trend_filtered_drawdown_strategy,
)


def make_price_frame(prices: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(prices))

    return pd.DataFrame(
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


def test_trend_filtered_drawdown_rejects_overallocated_settings():
    prices = make_price_frame([100] * 400)

    with pytest.raises(ValueError):
        run_trend_filtered_drawdown_strategy(
            prices=prices,
            initial_capital=10_000,
            base_allocation=0.80,
            tranche_allocation=0.10,
            drawdown_levels=[0.10, 0.20, 0.30],
            momentum_months=12,
            trend_off_allocation=0.0,
            slippage_bps=0,
        )


def test_trend_filtered_drawdown_stays_off_without_enough_momentum_history():
    prices = make_price_frame([100, 99, 98, 97, 96, 95])

    result = run_trend_filtered_drawdown_strategy(
        prices=prices,
        initial_capital=10_000,
        base_allocation=0.70,
        tranche_allocation=0.10,
        drawdown_levels=[0.10, 0.20, 0.30],
        momentum_months=12,
        trend_off_allocation=0.0,
        slippage_bps=0,
    )

    assert result["target_position"].iloc[-1] == 0.0
    assert result["position"].iloc[-1] == 0.0


def test_trend_filtered_drawdown_enters_when_momentum_is_positive():
    prices = make_price_frame(list(range(100, 500)))

    result = run_trend_filtered_drawdown_strategy(
        prices=prices,
        initial_capital=10_000,
        base_allocation=0.70,
        tranche_allocation=0.10,
        drawdown_levels=[0.10, 0.20, 0.30],
        momentum_months=12,
        trend_off_allocation=0.0,
        slippage_bps=0,
    )

    assert result["target_position"].iloc[-1] == pytest.approx(0.70)
    assert result["position"].iloc[-1] == pytest.approx(0.70)


def test_trend_filtered_drawdown_adds_tranches_during_positive_momentum_pullback():
    uptrend = list(range(100, 500))
    pullback = [450, 430, 400, 370, 350]
    prices = make_price_frame(uptrend + pullback)

    result = run_trend_filtered_drawdown_strategy(
        prices=prices,
        initial_capital=10_000,
        base_allocation=0.70,
        tranche_allocation=0.10,
        drawdown_levels=[0.10, 0.20, 0.30],
        momentum_months=12,
        trend_off_allocation=0.0,
        slippage_bps=0,
    )

    assert result["target_position"].iloc[-1] >= 0.80