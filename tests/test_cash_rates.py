import pandas as pd
import pytest

from market_strats.data.cash_rates import (
    align_cash_returns_to_price_dates,
    convert_irx_discount_rate_to_investment_yield,
    normalise_cash_rates_schema,
)


def test_convert_irx_discount_rate_to_investment_yield():
    discount_rate = 0.04

    result = convert_irx_discount_rate_to_investment_yield(discount_rate)

    expected = 0.04 / (1.0 - 0.04 * 91 / 360)

    assert result == pytest.approx(expected)


def test_normalise_cash_rates_schema_accepts_annual_yield_for_non_irx():
    cash_rates = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "annual_yield": [0.01, 0.02, 0.03],
        }
    )

    result = normalise_cash_rates_schema(cash_rates, ticker="CASH")

    assert list(result.columns) == [
        "date",
        "annual_yield",
        "source_rate_pct",
        "rate_source_type",
    ]
    assert result["annual_yield"].iloc[-1] == 0.03


def test_normalise_cash_rates_schema_converts_legacy_irx_annual_yield():
    cash_rates = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "annual_yield": [0.04, 0.04, 0.04],
        }
    )

    result = normalise_cash_rates_schema(cash_rates, ticker="^IRX")

    expected = 0.04 / (1.0 - 0.04 * 91 / 360)

    assert result["annual_yield"].iloc[0] == pytest.approx(expected)
    assert (
        result["rate_source_type"].iloc[0]
        == "legacy_irx_discount_rate_converted_to_yield"
    )


def test_normalise_cash_rates_schema_accepts_legacy_daily_cash_return():
    cash_rates = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "daily_cash_return": [0.0001, 0.0001, 0.0001],
        }
    )

    result = normalise_cash_rates_schema(cash_rates)

    assert "annual_yield" in result.columns
    assert result["annual_yield"].iloc[0] > 0


def test_align_cash_returns_handles_legacy_cash_return_schema():
    cash_rates = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "cash_return": [0.0001, 0.0001, 0.0001],
        }
    )
    price_dates = pd.bdate_range("2020-01-01", periods=5)

    result = align_cash_returns_to_price_dates(cash_rates, price_dates)

    assert len(result) == len(price_dates)
    assert result.name == "cash_return"