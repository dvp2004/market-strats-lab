from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf


def _safe_cash_filename(ticker: str) -> str:
    return ticker.replace("^", "").replace("-", "_").upper()


def fetch_cash_yield_rates(
    ticker: str,
    start_date: str,
    end_date: str | None = None,
) -> pd.DataFrame:
    """
    Fetch annualised cash yield proxy data.

    For ^IRX, Yahoo reports the 13-week T-bill yield in percentage terms.
    We store the annualised yield as a decimal. Conversion into per-period
    cash returns happens later, when we know the asset's date frequency.
    """
    data = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        auto_adjust=False,
        progress=False,
    )

    if data.empty:
        raise ValueError(f"No cash yield data returned for {ticker}")

    data = data.reset_index()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [column[0].lower() for column in data.columns]
    else:
        data.columns = [str(column).lower().replace(" ", "_") for column in data.columns]

    if "date" not in data.columns:
        raise ValueError(f"Cash yield data for {ticker} does not contain date column")

    close_column = "adj_close" if "adj_close" in data.columns else "close"

    if close_column not in data.columns:
        raise ValueError(f"Cash yield data for {ticker} does not contain close column")

    cash_rates = data[["date", close_column]].copy()
    cash_rates = cash_rates.rename(columns={close_column: "annual_yield_pct"})
    cash_rates["date"] = pd.to_datetime(cash_rates["date"])
    cash_rates["annual_yield"] = cash_rates["annual_yield_pct"].astype(float) / 100.0

    return cash_rates[["date", "annual_yield"]].sort_values("date").reset_index(drop=True)


def save_cash_rates_to_parquet(
    cash_rates: pd.DataFrame,
    ticker: str,
    output_dir: str | Path = "data/processed",
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_ticker = _safe_cash_filename(ticker)
    output_path = output_dir / f"{safe_ticker}_cash_rates.parquet"

    cash_rates.to_parquet(output_path, index=False)

    return output_path

def normalise_cash_rates_schema(cash_rates: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise older cached cash-rate parquet files to the current schema.

    Current schema:
    - date
    - annual_yield

    Older cached files may contain:
    - annual_yield_pct
    - daily_cash_return
    - cash_return
    """
    df = cash_rates.copy()

    if "date" not in df.columns:
        raise ValueError("Cash rates data must contain a date column")

    df["date"] = pd.to_datetime(df["date"])

    if "annual_yield" in df.columns:
        df["annual_yield"] = df["annual_yield"].astype(float)
        return df[["date", "annual_yield"]].sort_values("date").reset_index(drop=True)

    if "annual_yield_pct" in df.columns:
        df["annual_yield"] = df["annual_yield_pct"].astype(float) / 100.0
        return df[["date", "annual_yield"]].sort_values("date").reset_index(drop=True)

    if "daily_cash_return" in df.columns:
        df["annual_yield"] = (1.0 + df["daily_cash_return"].astype(float)) ** 252 - 1.0
        return df[["date", "annual_yield"]].sort_values("date").reset_index(drop=True)

    if "cash_return" in df.columns:
        df["annual_yield"] = (1.0 + df["cash_return"].astype(float)) ** 252 - 1.0
        return df[["date", "annual_yield"]].sort_values("date").reset_index(drop=True)

    raise ValueError(
        "Cash rates data must contain one of: annual_yield, annual_yield_pct, "
        "daily_cash_return, cash_return"
    )


def load_cash_rates_from_parquet(
    ticker: str,
    input_dir: str | Path = "data/processed",
) -> pd.DataFrame:
    safe_ticker = _safe_cash_filename(ticker)
    input_path = Path(input_dir) / f"{safe_ticker}_cash_rates.parquet"

    if not input_path.exists():
        raise FileNotFoundError(f"Cash rates file not found: {input_path}")

    cash_rates = pd.read_parquet(input_path)

    return normalise_cash_rates_schema(cash_rates)


def _infer_periods_per_year_from_dates(dates: pd.Series) -> float:
    dates = pd.Series(pd.to_datetime(dates)).sort_values().reset_index(drop=True)

    if len(dates) < 2:
        return 252.0

    elapsed_years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25

    if elapsed_years <= 0:
        return 252.0

    periods_per_year = len(dates) / elapsed_years

    if periods_per_year <= 0:
        return 252.0

    return float(periods_per_year)


def align_cash_returns_to_price_dates(
    cash_rates: pd.DataFrame,
    price_dates: pd.Series,
) -> pd.Series:
    """
    Align annualised cash yields to asset dates and convert them into per-period returns.

    This matters because ETFs use trading-day dates while BTC-USD uses calendar-day dates.
    ETF cash returns should annualise around 252 observations per year.
    BTC cash returns should annualise closer to 365 observations per year.
    """
    if cash_rates.empty:
        return pd.Series(0.0, index=pd.to_datetime(price_dates), name="cash_return")

    cash_rates = normalise_cash_rates_schema(cash_rates)
    
    dates = pd.to_datetime(price_dates)
    periods_per_year = _infer_periods_per_year_from_dates(dates)

    cash = cash_rates.copy()
    cash["date"] = pd.to_datetime(cash["date"])
    cash = cash.sort_values("date").set_index("date")

    aligned = cash["annual_yield"].reindex(dates).ffill().fillna(0.0)

    per_period_cash_return = (1.0 + aligned) ** (1.0 / periods_per_year) - 1.0
    per_period_cash_return.name = "cash_return"
    per_period_cash_return.index = dates

    return per_period_cash_return