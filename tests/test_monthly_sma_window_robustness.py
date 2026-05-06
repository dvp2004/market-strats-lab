import pandas as pd

from market_strats.analysis.monthly_sma_window_robustness import (
    create_monthly_sma_window_robustness_summary,
    run_monthly_sma_window_robustness,
)
from market_strats.strategies.buy_and_hold import run_buy_and_hold


def test_run_monthly_sma_window_robustness_returns_one_row_per_window():
    dates = pd.bdate_range("2010-01-01", "2020-12-31")
    prices = pd.DataFrame(
        {
            "date": dates,
            "adj_close": [100 + index * 0.05 for index in range(len(dates))],
        }
    )

    buy_hold = run_buy_and_hold(prices=prices, initial_capital=10_000)

    result = run_monthly_sma_window_robustness(
        ticker="EFA",
        prices=prices,
        buy_hold_result=buy_hold,
        initial_capital=10_000,
        sma_months=[6, 8, 10],
        slippage_bps=0,
        cash_returns=None,
    )

    assert len(result) == 3
    assert set(result["sma_months"]) == {6, 8, 10}
    assert "cagr_delta_vs_buy_hold_pct_points" in result.columns
    assert "drawdown_improvement_vs_buy_hold_pct_points" in result.columns


def test_create_monthly_sma_window_robustness_summary_uses_anchor_and_neighbours():
    robustness = pd.DataFrame(
        {
            "sma_months": [6, 8, 10, 12, 14],
            "cagr_pct": [5.0, 6.0, 7.0, 6.5, 5.5],
            "cagr_delta_vs_buy_hold_pct_points": [-1.0, 0.0, 1.0, 0.5, -0.5],
            "max_drawdown_pct": [-40.0, -35.0, -30.0, -32.0, -38.0],
            "drawdown_improvement_vs_buy_hold_pct_points": [
                10.0,
                15.0,
                20.0,
                18.0,
                12.0,
            ],
        }
    )

    summary = create_monthly_sma_window_robustness_summary(
        robustness,
        anchor_sma_months=10,
    )

    assert len(summary) == 1
    assert summary.iloc[0]["anchor_sma_months"] == 10
    assert summary.iloc[0]["neighbour_count"] == 3
    assert summary.iloc[0]["windows_with_positive_cagr_delta"] == 2