import pandas as pd
import pytest

from market_strats.strategies.drawdown_tranche import run_drawdown_tranche_strategy


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


def test_drawdown_tranche_stays_at_base_allocation_when_no_drawdown():
    prices = make_price_frame([100, 101, 102, 103, 104, 105])

    result = run_drawdown_tranche_strategy(
        prices=prices,
        initial_capital=10_000,
        base_allocation=0.70,
        tranche_allocation=0.10,
        drawdown_levels=[0.10, 0.20, 0.30],
        slippage_bps=0,
    )

    assert result["target_position"].iloc[-1] == 0.70
    assert result["position"].iloc[-1] == 0.70


def test_drawdown_tranche_increases_exposure_after_large_drawdown():
    prices = make_price_frame([100, 98, 90, 80, 70, 68, 67])

    result = run_drawdown_tranche_strategy(
        prices=prices,
        initial_capital=10_000,
        base_allocation=0.70,
        tranche_allocation=0.10,
        drawdown_levels=[0.10, 0.20, 0.30],
        slippage_bps=0,
    )

    assert result["target_position"].iloc[-1] == pytest.approx(1.00)


def test_drawdown_tranche_reduces_exposure_after_recovery():
    prices = make_price_frame([100, 90, 80, 70, 90, 101, 102])

    result = run_drawdown_tranche_strategy(
        prices=prices,
        initial_capital=10_000,
        base_allocation=0.70,
        tranche_allocation=0.10,
        drawdown_levels=[0.10, 0.20, 0.30],
        slippage_bps=0,
    )

    assert result["target_position"].iloc[-1] == 0.70


def test_drawdown_tranche_rejects_overallocated_settings():
    prices = make_price_frame([100, 90, 80, 70])

    with pytest.raises(ValueError):
        run_drawdown_tranche_strategy(
            prices=prices,
            initial_capital=10_000,
            base_allocation=0.80,
            tranche_allocation=0.10,
            drawdown_levels=[0.10, 0.20, 0.30],
            slippage_bps=0,
        )