from __future__ import annotations

import pandas as pd


def validate_price_data(df: pd.DataFrame, ticker: str) -> None:
    required = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(f"{ticker}: missing columns: {missing}")

    if df.empty:
        raise ValueError(f"{ticker}: dataframe is empty")

    if df["date"].duplicated().any():
        raise ValueError(f"{ticker}: duplicate dates found")

    if not df["date"].is_monotonic_increasing:
        raise ValueError(f"{ticker}: dates are not sorted")

    price_cols = ["open", "high", "low", "close", "adj_close"]

    for col in price_cols:
        if df[col].isna().any():
            raise ValueError(f"{ticker}: missing values in {col}")

        if (df[col] <= 0).any():
            raise ValueError(f"{ticker}: non-positive values in {col}")

    if df["volume"].isna().any():
        raise ValueError(f"{ticker}: missing volume values")

    if (df["volume"] < 0).any():
        raise ValueError(f"{ticker}: negative volume values")

    if len(df) < 252:
        raise ValueError(f"{ticker}: less than one year of daily data")