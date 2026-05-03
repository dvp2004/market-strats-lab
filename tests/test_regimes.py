import pandas as pd

from market_strats.analysis.regimes import slice_result_by_period


def test_slice_result_by_period_filters_dates_and_recalculates_returns():
    result = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2020-01-01",
                    "2020-01-02",
                    "2020-01-03",
                    "2020-01-04",
                ]
            ),
            "adj_close": [100, 101, 102, 103],
            "strategy_return": [0.0, 0.01, 0.0099, 0.0098],
            "equity": [100, 110, 121, 133.1],
            "position": [1, 1, 1, 1],
            "turnover": [1, 0, 0, 0],
        }
    )

    sliced = slice_result_by_period(
        result=result,
        start_date="2020-01-02",
        end_date="2020-01-04",
    )

    assert len(sliced) == 3
    assert sliced["date"].iloc[0] == pd.Timestamp("2020-01-02")
    assert sliced["date"].iloc[-1] == pd.Timestamp("2020-01-04")
    assert sliced["strategy_return"].iloc[0] == 0.0
    assert round(sliced["strategy_return"].iloc[1], 4) == 0.1