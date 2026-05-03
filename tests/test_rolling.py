import pandas as pd

from market_strats.analysis.rolling import (
    create_rolling_summary,
    slice_result_by_rolling_window,
)


def test_slice_result_by_rolling_window_recalculates_returns():
    dates = pd.date_range("2020-01-01", periods=600, freq="B")
    equity = pd.Series(range(1000, 1600), dtype=float)

    result = pd.DataFrame(
        {
            "date": dates,
            "adj_close": equity.values,
            "strategy_return": 0.0,
            "equity": equity.values,
            "position": 1.0,
            "turnover": 0.0,
        }
    )

    sliced = slice_result_by_rolling_window(
        result=result,
        end_date=pd.Timestamp("2022-01-03"),
        years=1,
    )

    assert not sliced.empty
    assert sliced["strategy_return"].iloc[0] == 0.0
    assert sliced["date"].min() >= pd.Timestamp("2021-01-03")
    assert sliced["date"].max() <= pd.Timestamp("2022-01-03")


def test_create_rolling_summary_groups_by_window_and_strategy():
    rolling_metrics = pd.DataFrame(
        {
            "window_years": [3, 3, 3, 3],
            "strategy": ["A", "A", "B", "B"],
            "cagr_pct": [10.0, -5.0, 8.0, 4.0],
            "max_drawdown_pct": [-20.0, -30.0, -10.0, -15.0],
            "sharpe": [0.5, -0.2, 0.7, 0.4],
            "exposure_time_pct": [100.0, 100.0, 80.0, 80.0],
        }
    )

    summary = create_rolling_summary(rolling_metrics)

    assert len(summary) == 2

    strategy_a = summary[summary["strategy"] == "A"].iloc[0]
    strategy_b = summary[summary["strategy"] == "B"].iloc[0]

    assert strategy_a["windows_count"] == 2
    assert strategy_a["positive_windows_pct"] == 50.0
    assert strategy_b["positive_windows_pct"] == 100.0