import pandas as pd

from market_strats.analysis.secondary_data_source_cross_check_v2 import (
    _classify_cross_check_row,
    _compare_primary_secondary_prices,
    _create_cross_check_summary,
)


def test_classify_cross_check_row_clean_match():
    config = {
        "phase7_secondary_data_source_cross_check_v2": {
            "min_overlapping_days": 1000,
            "clean_min_daily_return_correlation": 0.995,
            "clean_max_median_abs_daily_return_diff_bps": 5.0,
            "clean_max_cagr_delta_pct_points": 0.25,
        }
    }

    classification = _classify_cross_check_row(
        daily_return_correlation=0.999,
        median_abs_daily_return_diff_bps=1.0,
        cagr_delta_abs=0.05,
        overlapping_days=3000,
        config=config,
    )

    assert classification == "Clean match"


def test_classify_cross_check_row_potential_issue():
    config = {
        "phase7_secondary_data_source_cross_check_v2": {
            "min_overlapping_days": 1000,
            "review_min_daily_return_correlation": 0.970,
            "review_max_median_abs_daily_return_diff_bps": 25.0,
            "review_max_cagr_delta_pct_points": 1.50,
        }
    }

    classification = _classify_cross_check_row(
        daily_return_correlation=0.50,
        median_abs_daily_return_diff_bps=100.0,
        cagr_delta_abs=5.0,
        overlapping_days=3000,
        config=config,
    )

    assert classification == "Potential data issue"


def test_compare_primary_secondary_prices_clean_match():
    dates = pd.bdate_range("2020-01-01", periods=1500)

    primary = pd.DataFrame(
        {
            "date": dates,
            "primary_price": [100.0 + index for index in range(len(dates))],
        }
    )
    secondary = pd.DataFrame(
        {
            "date": dates,
            "secondary_price": [100.0 + index for index in range(len(dates))],
        }
    )

    config = {
        "phase7_secondary_data_source_cross_check_v2": {
            "min_overlapping_days": 1000,
            "clean_min_daily_return_correlation": 0.995,
            "clean_max_median_abs_daily_return_diff_bps": 5.0,
            "clean_max_cagr_delta_pct_points": 0.25,
        }
    }

    row = _compare_primary_secondary_prices(
        ticker="SPY",
        stooq_symbol="spy.us",
        primary_prices=primary,
        secondary_prices=secondary,
        config=config,
    )

    assert row["classification"] == "Clean match"
    assert row["daily_return_correlation"] == 1.0
    assert row["median_abs_daily_return_diff_bps"] == 0.0


def test_create_cross_check_summary_review_needed():
    cross_check = pd.DataFrame(
        {
            "ticker": ["SPY", "QQQ"],
            "available": [True, True],
            "classification": ["Clean match", "Review difference"],
        }
    )

    summary = _create_cross_check_summary(cross_check)

    assert summary.iloc[0]["available_tickers"] == 2
    assert summary.iloc[0]["review_difference_count"] == 1
    assert summary.iloc[0]["overall_status"] == "Review needed"