import pandas as pd

from market_strats.data.cash_rates import (
    align_cash_returns_to_price_dates,
    normalise_cash_rates_schema,
)


def test_normalise_cash_rates_schema_accepts_annual_yield():
    cash_rates = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "annual_yield": [0.01, 0.02, 0.03],
        }
    )

    result = normalise_cash_rates_schema(cash_rates)

    assert list(result.columns) == ["date", "annual_yield"]
    assert result["annual_yield"].iloc[-1] == 0.03


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