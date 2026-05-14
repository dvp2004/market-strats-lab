import pandas as pd

from market_strats.analysis.secondary_data_source_cross_check import (
    create_price_cross_check_for_ticker,
    create_secondary_data_source_cross_check_summary,
)


def test_create_price_cross_check_for_ticker_clean_match():
    dates = pd.bdate_range("2020-01-01", periods=300)
    primary_close = pd.Series(range(100, 400), dtype=float)
    secondary_close = primary_close.copy()

    primary = pd.DataFrame(
        {
            "date": dates,
            "close": primary_close,
            "adj_close": primary_close,
        }
    )
    secondary = pd.DataFrame(
        {
            "date": dates,
            "secondary_close": secondary_close,
        }
    )

    result = create_price_cross_check_for_ticker(
        ticker="SPY",
        primary_price_data=primary,
        secondary_price_data=secondary,
    )

    assert result["available"]
    assert result["ticker"] == "SPY"
    assert result["daily_return_correlation"] > 0.999
    assert result["median_abs_daily_return_diff_bps"] == 0.0


def test_create_secondary_data_source_cross_check_summary_counts():
    cross_check = pd.DataFrame(
        {
            "ticker": ["SPY", "QQQ", "BAD"],
            "available": [True, True, False],
            "classification": [
                "Clean match",
                "Acceptable difference",
                "Unavailable",
            ],
            "daily_return_correlation": [1.0, 0.998, None],
            "median_abs_daily_return_diff_bps": [0.0, 3.0, None],
        }
    )

    summary = create_secondary_data_source_cross_check_summary(cross_check)

    assert not summary.empty

    row = summary.iloc[0]
    assert row["available_tickers"] == 2
    assert row["clean_match_count"] == 1
    assert row["acceptable_difference_count"] == 1
    assert row["unavailable_count"] == 1