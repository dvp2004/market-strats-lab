import pandas as pd

from market_strats.analysis.cross_asset_diagnostics import (
    create_buy_hold_vs_momentum_diagnostic,
)


def test_create_buy_hold_vs_momentum_diagnostic_compares_strategies_by_ticker():
    metrics = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY", "QQQ", "QQQ"],
            "strategy": [
                "Buy and Hold",
                "12-Month Absolute Momentum",
                "Buy and Hold",
                "12-Month Absolute Momentum",
            ],
            "start_date": ["2000-01-01", "2000-01-01", "2000-01-01", "2000-01-01"],
            "end_date": ["2020-01-01", "2020-01-01", "2020-01-01", "2020-01-01"],
            "end_value": [100_000.0, 120_000.0, 200_000.0, 180_000.0],
            "cagr_pct": [10.0, 11.0, 12.0, 11.0],
            "volatility_pct": [18.0, 14.0, 28.0, 20.0],
            "sharpe": [0.6, 0.8, 0.5, 0.7],
            "max_drawdown_pct": [-50.0, -30.0, -80.0, -40.0],
            "exposure_time_pct": [100.0, 80.0, 100.0, 75.0],
            "trade_count": [1, 20, 1, 25],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": [
                "SPY",
                "SPY",
                "SPY",
                "SPY",
                "QQQ",
                "QQQ",
                "QQQ",
                "QQQ",
            ],
            "window_years": [3, 3, 5, 5, 3, 3, 5, 5],
            "strategy": [
                "Buy and Hold",
                "12-Month Absolute Momentum",
                "Buy and Hold",
                "12-Month Absolute Momentum",
                "Buy and Hold",
                "12-Month Absolute Momentum",
                "Buy and Hold",
                "12-Month Absolute Momentum",
            ],
            "avg_cagr_pct": [9.0, 10.0, 8.0, 9.0, 12.0, 11.0, 10.0, 9.0],
            "worst_cagr_pct": [-10.0, -2.0, -8.0, -1.0, -30.0, -8.0, -20.0, -5.0],
        }
    )

    result = create_buy_hold_vs_momentum_diagnostic(metrics, rolling_summary)

    assert set(result["ticker"]) == {"SPY", "QQQ"}

    spy = result[result["ticker"] == "SPY"].iloc[0]
    qqq = result[result["ticker"] == "QQQ"].iloc[0]

    assert spy["cagr_delta_pct_points"] == 1.0
    assert spy["drawdown_improvement_pct_points"] == 20.0
    assert spy["worst_5y_cagr_improvement_pct_points"] == 7.0

    assert qqq["cagr_delta_pct_points"] == -1.0
    assert qqq["drawdown_improvement_pct_points"] == 40.0


def test_create_buy_hold_vs_momentum_diagnostic_returns_empty_for_empty_metrics():
    result = create_buy_hold_vs_momentum_diagnostic(
        metrics=pd.DataFrame(),
        rolling_summary=pd.DataFrame(),
    )

    assert result.empty