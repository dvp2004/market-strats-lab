import pandas as pd

from market_strats.analysis.regime_switch_overlay_dynamic_slippage import (
    _create_dynamic_slippage_series,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _make_result(dates: pd.DatetimeIndex, prices: list[float]) -> pd.DataFrame:
    returns = pd.Series(prices, dtype=float).pct_change().fillna(0.0)

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": prices,
            "strategy_return": returns,
            "equity": prices,
            "position": 1.0,
            "cash_position": 0.0,
            "turnover": 0.0,
        }
    )


def test_dynamic_slippage_series_uses_stress_tiers():
    dates = pd.bdate_range("2020-01-01", periods=260)
    prices = [100.0] * 220 + [89.0] * 20 + [75.0] * 20

    result = _make_result(dates, prices)

    slippage = _create_dynamic_slippage_series(
        offensive_result=result,
        trend_sma_days=20,
        normal_bps=5.0,
        below_200d_bps=15.0,
        drawdown_10_bps=25.0,
        drawdown_20_bps=50.0,
    )

    assert slippage.max() == 50.0
    assert 25.0 in set(slippage)
    assert 15.0 in set(slippage)


def test_overlay_accepts_dynamic_slippage_series():
    dates = pd.bdate_range("2020-01-01", periods=260)
    offensive = _make_result(dates, [100.0] * 220 + [90.0] * 40)
    defensive = _make_result(dates, [100.0 + i * 0.01 for i in range(260)])

    dynamic_slippage = pd.Series(25.0, index=dates)

    result = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive,
        defensive_result=defensive,
        initial_capital=10_000.0,
        trend_sma_days=20,
        slippage_bps=5.0,
        confirmation_days=3,
        dynamic_slippage_bps=dynamic_slippage,
    )

    assert "applied_overlay_slippage_bps" in result.columns
    assert result["applied_overlay_slippage_bps"].max() == 25.0