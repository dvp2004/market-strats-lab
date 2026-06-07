from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf


CACHE_DIR = Path("data/.yfinance_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
if hasattr(yf, "set_tz_cache_location"):
    yf.set_tz_cache_location(str(CACHE_DIR))


COLUMN_MAP = {
    "Date": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


def fetch_daily_prices(ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
    """
    Fetch daily OHLCV data from Yahoo Finance through yfinance.

    This is good enough for the first research MVP, but it is not institutional-grade data.
    Later, we should cross-check against a second source.
    """
    raw = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        auto_adjust=False,
        progress=False,
    )

    if raw.empty:
        raise ValueError(f"No data returned for ticker={ticker}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [col[0] for col in raw.columns]

    df = raw.reset_index()
    df = df.rename(columns=COLUMN_MAP)

    required = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(f"Missing required columns for {ticker}: {missing}")

    df = df[required].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values("date").reset_index(drop=True)

    return df


def save_prices_to_parquet(df: pd.DataFrame, ticker: str, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{ticker.upper()}.parquet"
    df.to_parquet(output_path, index=False)

    return output_path


def load_prices_from_parquet(ticker: str, input_dir: str | Path) -> pd.DataFrame:
    input_path = Path(input_dir) / f"{ticker.upper()}.parquet"

    if not input_path.exists():
        raise FileNotFoundError(f"Could not find data file: {input_path}")

    df = pd.read_parquet(input_path)
    df["date"] = pd.to_datetime(df["date"])

    return df.sort_values("date").reset_index(drop=True)
