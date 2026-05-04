import pandas as pd
import pytest

from market_strats.analysis.momentum_robustness import (
    classify_parameter_shape,
    run_momentum_window_robustness,
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


def test_run_momentum_window_robustness_rejects_empty_lookbacks():
    prices = make_price_frame(list(range(100, 500)))

    with pytest.raises(ValueError):
        run_momentum_window_robustness(
            prices=prices,
            initial_capital=10_000,
            lookback_months=[],
            slippage_bps=0,
            cash_returns=None,
        )


def test_run_momentum_window_robustness_outputs_one_row_per_lookback():
    prices = make_price_frame(list(range(100, 800)))
    lookbacks = [6, 12]

    result, rolling_summary, strategy_results = run_momentum_window_robustness(
        prices=prices,
        initial_capital=10_000,
        lookback_months=lookbacks,
        slippage_bps=0,
        cash_returns=None,
    )

    assert set(result["lookback_months"]) == set(lookbacks)
    assert not rolling_summary.empty
    assert len(strategy_results) == len(lookbacks)


def test_classify_parameter_shape_detects_reasonable_plateau():
    robustness_metrics = pd.DataFrame(
        {
            "lookback_months": [9, 10, 11, 12, 13],
            "cagr_pct": [10.1, 10.3, 10.5, 10.4, 10.0],
            "max_drawdown_pct": [-34.0, -33.0, -32.0, -33.5, -35.0],
        }
    )

    result = classify_parameter_shape(robustness_metrics)

    assert "plateau" in result.lower()


def test_classify_parameter_shape_flags_fragility():
    robustness_metrics = pd.DataFrame(
        {
            "lookback_months": [9, 10, 11, 12, 13],
            "cagr_pct": [7.0, 7.5, 8.0, 11.0, 6.0],
            "max_drawdown_pct": [-45.0, -44.0, -43.0, -30.0, -48.0],
        }
    )

    result = classify_parameter_shape(robustness_metrics)

    assert "fragility" in result.lower()