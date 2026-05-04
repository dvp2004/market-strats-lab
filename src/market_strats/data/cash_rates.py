from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from market_strats.analysis.metrics import TRADING_DAYS_PER_YEAR


def fetch_cash_yield_rates(
    ticker: str,
    start_date: str,
    end_date: str | None = None,
) -> pd.DataFrame:
    """
    Fetch a cash yield proxy.

    For the first implementation, we use Yahoo Finance ^IRX as a proxy for
    short-term Treasury bill yield.

    Yahoo typically reports ^IRX as a percentage-like yield value, e.g. 5.25
    meaning approximately 5.25% annualised. We convert this to a decimal
    annual yield, then to an approximate daily return.
    """
    raw = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        auto_adjust=False,
        progress=False,
    )

    if raw.empty:
        raise ValueError(f"No cash yield data returned for ticker={ticker}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [col[0] for col in raw.columns]

    df = raw.reset_index()

    if "Date" not in df.columns or "Close" not in df.columns:
        raise ValueError(f"Cash yield data for {ticker} must contain Date and Close columns")

    result = pd.DataFrame(
        {
            "date": pd.to_datetime(df["Date"]).dt.tz_localize(None),
            "yield_pct": pd.to_numeric(df["Close"], errors="coerce"),
        }
    )

    result = result.dropna(subset=["yield_pct"])
    result = result.sort_values("date").reset_index(drop=True)

    result["annual_yield_decimal"] = result["yield_pct"] / 100.0
    result["daily_cash_return"] = (
        (1.0 + result["annual_yield_decimal"]) ** (1.0 / TRADING_DAYS_PER_YEAR)
    ) - 1.0

    return result[["date", "yield_pct", "annual_yield_decimal", "daily_cash_return"]]


def save_cash_rates_to_parquet(
    df: pd.DataFrame,
    ticker: str,
    output_dir: str | Path,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_ticker = ticker.replace("^", "")
    output_path = output_dir / f"{safe_ticker.upper()}_cash_rates.parquet"

    df.to_parquet(output_path, index=False)

    return output_path


def load_cash_rates_from_parquet(ticker: str, input_dir: str | Path) -> pd.DataFrame:
    safe_ticker = ticker.replace("^", "")
    input_path = Path(input_dir) / f"{safe_ticker.upper()}_cash_rates.parquet"

    if not input_path.exists():
        raise FileNotFoundError(f"Could not find cash rates file: {input_path}")

    df = pd.read_parquet(input_path)
    df["date"] = pd.to_datetime(df["date"])

    return df.sort_values("date").reset_index(drop=True)


def align_cash_returns_to_price_dates(
    cash_rates: pd.DataFrame,
    price_dates: pd.Series,
) -> pd.Series:
    """
    Align daily cash returns to the asset trading dates.

    Missing cash yield dates are forward-filled. If no cash rate is available
    at the beginning, cash return is set to 0 until data begins.
    """
    cash_df = cash_rates.copy()
    cash_df["date"] = pd.to_datetime(cash_df["date"])
    cash_df = cash_df.sort_values("date").set_index("date")

    target_dates = pd.to_datetime(price_dates)
    aligned = cash_df["daily_cash_return"].reindex(target_dates, method="ffill")
    aligned = aligned.fillna(0.0)

    return pd.Series(aligned.values, index=target_dates, name="cash_return")