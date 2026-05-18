import pandas as pd

from market_strats.analysis.secondary_data_source_difference_attribution import (
    _classify_attribution,
    _compare_price_basis_to_secondary,
    _create_attribution_summary,
    _find_raw_close_column,
)


def test_find_raw_close_column_prefers_close():
    data = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-01-01", periods=3),
            "adj_close": [100, 101, 102],
            "close": [99, 100, 101],
        }
    )

    assert _find_raw_close_column(data) == "close"


def test_compare_price_basis_to_secondary_identical_series_clean():
    dates = pd.bdate_range("2020-01-01", periods=1500)

    primary = pd.DataFrame(
        {
            "date": dates,
            "primary_raw_close": [100.0 + index for index in range(len(dates))],
        }
    )
    secondary = pd.DataFrame(
        {
            "date": dates,
            "secondary_price": [100.0 + index for index in range(len(dates))],
        }
    )

    row = _compare_price_basis_to_secondary(
        ticker="SPY",
        basis_name="primary_raw_close",
        primary_basis_prices=primary,
        secondary_prices=secondary,
    )

    assert row["available"] is True
    assert row["daily_return_correlation"] == 1.0
    assert row["cagr_delta_primary_minus_secondary_pct_points"] == 0.0


def test_classify_attribution_distribution_difference_when_raw_matches():
    adjusted_row = {
        "cagr_delta_primary_minus_secondary_pct_points": 2.0,
        "drawdown_delta_primary_minus_secondary_pct_points": 1.0,
    }
    raw_row = {
        "available": True,
        "daily_return_correlation": 0.999,
        "cagr_delta_primary_minus_secondary_pct_points": 0.1,
    }
    config = {
        "phase7_secondary_data_source_difference_attribution": {
            "distribution_sensitive_tickers": ["AGG"],
            "raw_close_match_min_correlation": 0.995,
            "raw_close_match_max_cagr_delta_pct_points": 0.75,
            "adjusted_vs_secondary_large_cagr_delta_pct_points": 0.75,
            "potential_issue_min_cagr_delta_pct_points": 1.5,
            "potential_issue_min_drawdown_delta_pct_points": 5.0,
        }
    }

    attribution = _classify_attribution(
        ticker="AGG",
        adjusted_row=adjusted_row,
        raw_row=raw_row,
        prior_classification="Potential data issue",
        config=config,
    )

    assert attribution == "Likely adjusted-vs-unadjusted distribution difference"


def test_classify_attribution_unresolved_potential_issue():
    adjusted_row = {
        "cagr_delta_primary_minus_secondary_pct_points": 2.0,
        "drawdown_delta_primary_minus_secondary_pct_points": 6.0,
    }
    config = {
        "phase7_secondary_data_source_difference_attribution": {
            "distribution_sensitive_tickers": [],
            "potential_issue_min_cagr_delta_pct_points": 1.5,
            "potential_issue_min_drawdown_delta_pct_points": 5.0,
        }
    }

    attribution = _classify_attribution(
        ticker="XYZ",
        adjusted_row=adjusted_row,
        raw_row=None,
        prior_classification="Potential data issue",
        config=config,
    )

    assert attribution == "Unresolved potential data issue"


def test_create_attribution_summary_flags_unresolved():
    attribution = pd.DataFrame(
        {
            "ticker": ["AGG", "VNQ"],
            "attribution": [
                "Likely adjusted-vs-unadjusted distribution difference",
                "Unresolved potential data issue",
            ],
        }
    )

    summary = _create_attribution_summary(attribution)

    assert summary.iloc[0]["distribution_or_price_basis_count"] == 1
    assert summary.iloc[0]["unresolved_potential_data_issue_count"] == 1
    assert summary.iloc[0]["overall_status"] == "Unresolved data issues remain"