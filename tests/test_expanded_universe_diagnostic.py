import pandas as pd

from market_strats.analysis.expanded_universe_diagnostic import (
    create_expanded_universe_diagnostic,
)


def test_create_expanded_universe_diagnostic_maps_ticker_results():
    metrics = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY", "SPY"],
            "strategy": [
                "Buy and Hold",
                "12-Month Absolute Momentum",
                "200-Day SMA",
            ],
            "start_date": ["2000-01-01", "2000-01-01", "2000-01-01"],
            "end_date": ["2020-01-01", "2020-01-01", "2020-01-01"],
            "end_value": [100_000.0, 110_000.0, 90_000.0],
            "cagr_pct": [10.0, 10.5, 9.0],
            "max_drawdown_pct": [-55.0, -35.0, -25.0],
            "sharpe": [0.60, 0.75, 0.65],
            "trade_count": [1, 17, 100],
        }
    )

    scorecards = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY", "SPY"],
            "strategy": [
                "12-Month Absolute Momentum",
                "Buy and Hold",
                "200-Day SMA",
            ],
            "composite_rank": [1, 2, 3],
        }
    )

    result = create_expanded_universe_diagnostic(metrics, scorecards)

    assert len(result) == 1

    row = result.iloc[0]

    assert row["ticker"] == "SPY"
    assert row["start_date"] == "2000-01-01"
    assert row["best_cagr_strategy"] == "12-Month Absolute Momentum"
    assert row["best_drawdown_strategy"] == "200-Day SMA"
    assert row["best_scorecard_strategy"] == "12-Month Absolute Momentum"
    assert row["momentum_cagr_delta_pct_points"] == 0.5
    assert row["momentum_drawdown_improvement_pct_points"] == 20.0


def test_create_expanded_universe_diagnostic_returns_empty_for_empty_metrics():
    result = create_expanded_universe_diagnostic(
        metrics=pd.DataFrame(),
        scorecards=pd.DataFrame(),
    )

    assert result.empty