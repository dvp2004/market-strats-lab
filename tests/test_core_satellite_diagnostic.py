import pandas as pd

from market_strats.analysis.core_satellite_diagnostic import (
    create_core_satellite_diagnostic,
)


def test_create_core_satellite_diagnostic_compares_three_strategies():
    metrics = pd.DataFrame(
        {
            "strategy": [
                "Buy and Hold",
                "12-Month Absolute Momentum",
                "60/40 Core-Satellite SPY B&H + 12M Momentum",
            ],
            "end_value": [100_000.0, 110_000.0, 108_000.0],
            "cagr_pct": [10.0, 10.5, 10.4],
            "volatility_pct": [18.0, 14.0, 15.0],
            "sharpe": [0.6, 0.8, 0.75],
            "sortino": [0.8, 0.9, 0.95],
            "max_drawdown_pct": [-55.0, -34.0, -35.0],
            "exposure_time_pct": [100.0, 80.0, 90.0],
            "trade_count": [1, 17, 18],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "strategy": [
                "Buy and Hold",
                "12-Month Absolute Momentum",
                "60/40 Core-Satellite SPY B&H + 12M Momentum",
                "Buy and Hold",
                "12-Month Absolute Momentum",
                "60/40 Core-Satellite SPY B&H + 12M Momentum",
            ],
            "window_years": [3, 3, 3, 5, 5, 5],
            "avg_cagr_pct": [10.0, 10.2, 10.1, 9.8, 10.0, 9.9],
            "worst_cagr_pct": [-15.0, -2.0, -8.0, -7.0, -0.5, -1.0],
            "avg_max_drawdown_pct": [-25.0, -16.0, -20.0, -30.0, -19.0, -24.0],
        }
    )

    result = create_core_satellite_diagnostic(
        metrics=metrics,
        rolling_summary=rolling_summary,
        core_satellite_strategy="60/40 Core-Satellite SPY B&H + 12M Momentum",
    )

    assert len(result) == 3
    assert set(result["strategy"]) == {
        "Buy and Hold",
        "12-Month Absolute Momentum",
        "60/40 Core-Satellite SPY B&H + 12M Momentum",
    }

    core_satellite = result[
        result["strategy"] == "60/40 Core-Satellite SPY B&H + 12M Momentum"
    ].iloc[0]

    assert core_satellite["cagr_delta_vs_buy_hold_pct_points"] == 0.4
    assert core_satellite["drawdown_improvement_vs_buy_hold_pct_points"] == 20.0
    assert core_satellite["cagr_delta_vs_12m_momentum_pct_points"] == -0.1


def test_create_core_satellite_diagnostic_returns_empty_for_empty_metrics():
    result = create_core_satellite_diagnostic(
        metrics=pd.DataFrame(),
        rolling_summary=pd.DataFrame(),
        core_satellite_strategy="60/40 Core-Satellite SPY B&H + 12M Momentum",
    )

    assert result.empty