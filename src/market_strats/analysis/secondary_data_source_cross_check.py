from __future__ import annotations

from pathlib import Path

import pandas as pd
from io import StringIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

STOOQ_BASE_URL = "https://stooq.com/q/d/l/"


def _normalise_stooq_symbol(ticker: str) -> str:
    ticker = ticker.lower().replace("-", ".")
    return f"{ticker}.us"


def _format_stooq_date(value: str | None) -> str | None:
    if value is None:
        return None

    return pd.to_datetime(value).strftime("%Y%m%d")


def fetch_stooq_daily_prices(
    ticker: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    symbol = _normalise_stooq_symbol(ticker)
    params = {
        "s": symbol,
        "i": "d",
    }

    formatted_start = _format_stooq_date(start_date)
    formatted_end = _format_stooq_date(end_date)

    if formatted_start is not None:
        params["d1"] = formatted_start

    if formatted_end is not None:
        params["d2"] = formatted_end

    query = "&".join(f"{key}={value}" for key, value in params.items())
    url = f"{STOOQ_BASE_URL}?{query}"

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "text/csv,text/plain,*/*",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            raw_text = response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        raise ValueError(
            f"Stooq HTTP error for {ticker} using symbol {symbol}: "
            f"{error.code} {error.reason}. URL: {url}"
        ) from error
    except URLError as error:
        raise ValueError(
            f"Stooq URL error for {ticker} using symbol {symbol}: "
            f"{error.reason}. URL: {url}"
        ) from error
    except TimeoutError as error:
        raise ValueError(
            f"Stooq request timed out for {ticker} using symbol {symbol}. URL: {url}"
        ) from error

    cleaned_text = raw_text.strip()

    if not cleaned_text:
        raise ValueError(
            f"Stooq returned an empty response for {ticker} using symbol {symbol}. "
            f"URL: {url}"
        )

    if "No data" in cleaned_text or "Brak danych" in cleaned_text:
        raise ValueError(
            f"Stooq returned no data for {ticker} using symbol {symbol}. URL: {url}. "
            f"Response preview: {cleaned_text[:200]}"
        )

    lines = cleaned_text.splitlines()

    header_index = None

    for index, line in enumerate(lines):
        normalised_line = line.strip().lower()
        if normalised_line.startswith("date,open,high,low,close"):
            header_index = index
            break

    if header_index is None:
        raise ValueError(
            f"Could not find Stooq CSV header for {ticker} using symbol {symbol}. "
            f"URL: {url}. Response preview: {cleaned_text[:500]}"
        )

    csv_text = "\n".join(lines[header_index:])

    try:
        prices = pd.read_csv(StringIO(csv_text), engine="python")
    except pd.errors.ParserError as error:
        raise ValueError(
            f"Could not parse Stooq CSV for {ticker} using symbol {symbol}. "
            f"URL: {url}. Response preview after header trim: {csv_text[:500]}"
        ) from error

    if prices.empty:
        raise ValueError(
            f"No Stooq rows parsed for {ticker} using symbol {symbol}. URL: {url}. "
            f"Response preview: {cleaned_text[:200]}"
        )

    if "Date" not in prices.columns or "Close" not in prices.columns:
        raise ValueError(
            f"Unexpected Stooq schema for {ticker} using symbol {symbol}. "
            f"Columns: {list(prices.columns)}. URL: {url}. "
            f"Response preview: {cleaned_text[:200]}"
        )

    output = prices.rename(
        columns={
            "Date": "date",
            "Open": "secondary_open",
            "High": "secondary_high",
            "Low": "secondary_low",
            "Close": "secondary_close",
            "Volume": "secondary_volume",
        }
    )

    output["date"] = pd.to_datetime(output["date"])
    output["secondary_close"] = output["secondary_close"].astype(float)

    return (
        output[
            [
                column
                for column in [
                    "date",
                    "secondary_open",
                    "secondary_high",
                    "secondary_low",
                    "secondary_close",
                    "secondary_volume",
                ]
                if column in output.columns
            ]
        ]
        .sort_values("date")
        .dropna(subset=["secondary_close"])
        .reset_index(drop=True)
    )


def _calculate_cagr(
    values: pd.Series,
    dates: pd.Series,
) -> float:
    values = values.astype(float)
    dates = pd.to_datetime(dates)

    if len(values) < 2:
        return float("nan")

    start_value = float(values.iloc[0])
    end_value = float(values.iloc[-1])

    if start_value <= 0:
        return float("nan")

    years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25

    if years <= 0:
        return float("nan")

    return ((end_value / start_value) ** (1.0 / years) - 1.0) * 100.0


def _calculate_max_drawdown(values: pd.Series) -> float:
    values = values.astype(float)

    if values.empty:
        return float("nan")

    running_high = values.cummax()
    drawdown = values / running_high - 1.0

    return float(drawdown.min() * 100.0)


def _prepare_primary_price_data(
    price_data: pd.DataFrame,
) -> pd.DataFrame:
    required_columns = {"date", "close"}

    missing_columns = required_columns - set(price_data.columns)

    if missing_columns:
        raise ValueError(
            f"Primary price data missing required columns: {sorted(missing_columns)}"
        )

    primary = price_data[["date", "close"]].copy()
    primary["date"] = pd.to_datetime(primary["date"])
    primary["primary_close"] = primary["close"].astype(float)

    return (
        primary[["date", "primary_close"]]
        .sort_values("date")
        .dropna(subset=["primary_close"])
        .reset_index(drop=True)
    )


def create_price_cross_check_for_ticker(
    ticker: str,
    primary_price_data: pd.DataFrame,
    secondary_price_data: pd.DataFrame,
) -> dict:
    primary = _prepare_primary_price_data(primary_price_data)
    secondary = secondary_price_data.copy()
    secondary["date"] = pd.to_datetime(secondary["date"])
    secondary["secondary_close"] = secondary["secondary_close"].astype(float)

    merged = primary.merge(
        secondary[["date", "secondary_close"]],
        on="date",
        how="inner",
    ).sort_values("date")

    if len(merged) < 2:
        return {
            "ticker": ticker,
            "available": False,
            "reason": "Insufficient overlapping dates between primary and secondary data.",
        }

    merged["primary_return"] = merged["primary_close"].pct_change()
    merged["secondary_return"] = merged["secondary_close"].pct_change()
    merged["return_diff"] = merged["primary_return"] - merged["secondary_return"]
    merged = merged.dropna(
        subset=["primary_return", "secondary_return", "return_diff"]
    )

    if merged.empty:
        return {
            "ticker": ticker,
            "available": False,
            "reason": "No overlapping daily returns after alignment.",
        }

    return_correlation = merged["primary_return"].corr(merged["secondary_return"])

    median_abs_daily_return_diff_bps = (
        merged["return_diff"].abs().median() * 10_000.0
    )
    mean_abs_daily_return_diff_bps = merged["return_diff"].abs().mean() * 10_000.0
    max_abs_daily_return_diff_bps = merged["return_diff"].abs().max() * 10_000.0

    primary_cagr = _calculate_cagr(merged["primary_close"], merged["date"])
    secondary_cagr = _calculate_cagr(merged["secondary_close"], merged["date"])

    primary_max_drawdown = _calculate_max_drawdown(merged["primary_close"])
    secondary_max_drawdown = _calculate_max_drawdown(merged["secondary_close"])

    first_primary = float(merged["primary_close"].iloc[0])
    first_secondary = float(merged["secondary_close"].iloc[0])

    normalised_primary = merged["primary_close"] / first_primary
    normalised_secondary = merged["secondary_close"] / first_secondary

    final_normalised_gap_pct = (
        float(normalised_primary.iloc[-1] - normalised_secondary.iloc[-1]) * 100.0
    )

    return {
        "ticker": ticker,
        "available": True,
        "reason": "",
        "start_date": merged["date"].iloc[0].date(),
        "end_date": merged["date"].iloc[-1].date(),
        "overlapping_days": int(len(merged)),
        "primary_cagr_pct": primary_cagr,
        "secondary_cagr_pct": secondary_cagr,
        "cagr_delta_primary_minus_secondary_pct_points": (
            primary_cagr - secondary_cagr
        ),
        "primary_max_drawdown_pct": primary_max_drawdown,
        "secondary_max_drawdown_pct": secondary_max_drawdown,
        "max_drawdown_delta_primary_minus_secondary_pct_points": (
            primary_max_drawdown - secondary_max_drawdown
        ),
        "daily_return_correlation": return_correlation,
        "median_abs_daily_return_diff_bps": median_abs_daily_return_diff_bps,
        "mean_abs_daily_return_diff_bps": mean_abs_daily_return_diff_bps,
        "max_abs_daily_return_diff_bps": max_abs_daily_return_diff_bps,
        "final_normalised_gap_pct": final_normalised_gap_pct,
    }


def _classify_cross_check(row: pd.Series) -> str:
    if not bool(row.get("available", False)):
        return "Unavailable"

    correlation = float(row.get("daily_return_correlation", 0.0))
    median_abs_diff = float(row.get("median_abs_daily_return_diff_bps", 9999.0))

    if correlation >= 0.999 and median_abs_diff <= 2.0:
        return "Clean match"

    if correlation >= 0.995 and median_abs_diff <= 10.0:
        return "Acceptable difference"

    if correlation >= 0.98:
        return "Review difference"

    return "Potential data issue"


def create_secondary_data_source_cross_check(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    cross_check_config = config.get("secondary_data_source_cross_check", {})

    if not cross_check_config.get("enabled", False):
        return pd.DataFrame()

    provider = str(cross_check_config.get("provider", "stooq")).lower()

    if provider != "stooq":
        raise ValueError(
            f"Unsupported secondary data provider: {provider}. "
            "Currently only 'stooq' is implemented."
        )

    tickers = [
        str(ticker).upper()
        for ticker in cross_check_config.get("tickers", ticker_outputs.keys())
    ]

    start_date = cross_check_config.get("start_date")
    end_date = cross_check_config.get("end_date")

    rows: list[dict] = []

    for ticker in tickers:
        if ticker not in ticker_outputs:
            rows.append(
                {
                    "ticker": ticker,
                    "available": False,
                    "reason": "Ticker missing from ticker_outputs.",
                }
            )
            continue

        primary_price_data = ticker_outputs[ticker].get("price_data")

        if primary_price_data is None or primary_price_data.empty:
            primary_price_data = ticker_outputs[ticker].get("data")

        if primary_price_data is None or primary_price_data.empty:
            rows.append(
                {
                    "ticker": ticker,
                    "available": False,
                    "reason": "No primary price_data/data frame available.",
                }
            )
            continue

        try:
            secondary_price_data = fetch_stooq_daily_prices(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
            )
            row = create_price_cross_check_for_ticker(
                ticker=ticker,
                primary_price_data=primary_price_data,
                secondary_price_data=secondary_price_data,
            )
        except Exception as error:  # noqa: BLE001 - report data-source failure clearly.
            row = {
                "ticker": ticker,
                "available": False,
                "reason": str(error),
            }

        rows.append(row)

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    if "available" in output.columns:
        output["classification"] = output.apply(_classify_cross_check, axis=1)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(6)

    return output.reset_index(drop=True)


def create_secondary_data_source_cross_check_summary(
    cross_check: pd.DataFrame,
) -> pd.DataFrame:
    if cross_check.empty:
        return pd.DataFrame()

    available = cross_check[cross_check["available"].astype(str).str.lower() == "true"]

    if available.empty:
        return pd.DataFrame(
            [
                {
                    "available_tickers": 0,
                    "clean_match_count": 0,
                    "acceptable_difference_count": 0,
                    "review_difference_count": 0,
                    "potential_data_issue_count": 0,
                    "unavailable_count": int(len(cross_check)),
                    "overall_status": "No secondary data available",
                }
            ]
        )

    classification_counts = available["classification"].value_counts().to_dict()

    potential_issue_count = int(
        classification_counts.get("Potential data issue", 0)
    )
    review_count = int(classification_counts.get("Review difference", 0))

    if potential_issue_count > 0:
        overall_status = "Needs investigation"
    elif review_count > 0:
        overall_status = "Mostly acceptable, review differences"
    else:
        overall_status = "Passed raw-close data-source sanity check"

    return pd.DataFrame(
        [
            {
                "available_tickers": int(len(available)),
                "clean_match_count": int(classification_counts.get("Clean match", 0)),
                "acceptable_difference_count": int(
                    classification_counts.get("Acceptable difference", 0)
                ),
                "review_difference_count": review_count,
                "potential_data_issue_count": potential_issue_count,
                "unavailable_count": int(len(cross_check) - len(available)),
                "min_daily_return_correlation": round(
                    float(available["daily_return_correlation"].min()),
                    6,
                ),
                "median_daily_return_correlation": round(
                    float(available["daily_return_correlation"].median()),
                    6,
                ),
                "max_median_abs_daily_return_diff_bps": round(
                    float(available["median_abs_daily_return_diff_bps"].max()),
                    6,
                ),
                "overall_status": overall_status,
            }
        ]
    )


def write_secondary_data_source_cross_check_markdown(
    cross_check: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if cross_check.empty:
        output_path.write_text(
            "# Secondary Data-Source Cross-Check\n\nNo cross-check data available.\n",
            encoding="utf-8",
        )
        return output_path

    cross_check_table = cross_check.to_markdown(index=False)
    summary_table = summary.to_markdown(index=False) if not summary.empty else ""

    content = f"""# Secondary Data-Source Cross-Check

This report compares the project's primary Yahoo/yfinance raw close data against a secondary Stooq raw close download.

## Important Scope Limitation

This is a raw-close sanity check.

It does **not** fully validate adjusted-close total-return series, dividend handling, or every strategy output.

Its purpose is to check whether the primary raw close series used for signal diagnostics is broadly consistent with an independent no-key public data source.

## Summary

{summary_table}

## Full Cross-Check Table

{cross_check_table}

## Interpretation Notes

- `primary_close` comes from the project's preserved yfinance raw close column.
- `secondary_close` comes from Stooq.
- The most important field is daily return correlation.
- Small level differences can occur because vendors may handle historical price adjustments differently.
- Large return differences or low correlation should be investigated before expanding the strategy universe.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_secondary_data_source_cross_check(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    cross_check = create_secondary_data_source_cross_check(
        ticker_outputs=ticker_outputs,
        config=config,
    )

    if cross_check.empty:
        return {
            "cross_check": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    summary = create_secondary_data_source_cross_check_summary(cross_check)

    cross_check_path = reports_dir / "secondary_data_source_cross_check.csv"
    summary_path = reports_dir / "secondary_data_source_cross_check_summary.csv"
    markdown_path = reports_dir / "secondary_data_source_cross_check.md"

    cross_check.to_csv(cross_check_path, index=False)
    summary.to_csv(summary_path, index=False)

    write_secondary_data_source_cross_check_markdown(
        cross_check=cross_check,
        summary=summary,
        output_path=markdown_path,
    )

    print("\nSecondary data-source cross-check:")
    print(cross_check.to_string(index=False))

    print("\nSecondary data-source cross-check summary:")
    print(summary.to_string(index=False))

    print(f"\nSaved secondary data-source cross-check to: {cross_check_path}")
    print(f"Saved secondary data-source cross-check summary to: {summary_path}")
    print(f"Saved secondary data-source cross-check markdown to: {markdown_path}")

    return {
        "cross_check": cross_check,
        "summary": summary,
    }