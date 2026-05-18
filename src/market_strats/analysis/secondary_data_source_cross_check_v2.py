from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode
import os
import pandas as pd
from io import StringIO
from urllib.request import Request, urlopen
from market_strats.analysis.metrics import calculate_metrics


def _phase7c_config(config: dict) -> dict:
    return config.get("phase7_secondary_data_source_cross_check_v2", {})


def _normalise_ticker(ticker: str) -> str:
    return str(ticker).upper()

class ProviderAuthenticationRequiredError(RuntimeError):
    """Raised when the secondary provider requires authentication."""   

def _find_primary_price_data(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
) -> pd.DataFrame:
    ticker = _normalise_ticker(ticker)

    if ticker not in ticker_outputs:
        raise ValueError(f"{ticker} not found in ticker_outputs")

    ticker_output = ticker_outputs[ticker]

    candidate_keys = [
        "price_data",
        "data",
        "prices",
        "raw_price_data",
    ]

    for key in candidate_keys:
        candidate = ticker_output.get(key)

        if isinstance(candidate, pd.DataFrame) and {"date", "adj_close"}.issubset(
            candidate.columns
        ):
            return candidate.copy()

    for value in ticker_output.values():
        if isinstance(value, pd.DataFrame) and {"date", "adj_close"}.issubset(
            value.columns
        ):
            return value.copy()

    raise ValueError(
        f"Could not find primary price data for {ticker}. "
        "Expected a DataFrame with columns date and adj_close."
    )


def _normalise_primary_prices(
    price_data: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    output = price_data.copy()

    output["date"] = pd.to_datetime(output["date"])
    output = output.sort_values("date").reset_index(drop=True)

    output = output[
        (output["date"] >= pd.Timestamp(start_date))
        & (output["date"] <= pd.Timestamp(end_date))
    ].copy()

    if output.empty:
        return pd.DataFrame(columns=["date", "primary_price"])

    output["primary_price"] = output["adj_close"].astype(float)

    return output[["date", "primary_price"]].dropna().reset_index(drop=True)


def _build_stooq_url(
    stooq_symbol: str,
    start_date: str,
    end_date: str,
    api_key: str | None = None,
) -> str:
    params = {
        "s": stooq_symbol,
        "d1": pd.Timestamp(start_date).strftime("%Y%m%d"),
        "d2": pd.Timestamp(end_date).strftime("%Y%m%d"),
        "i": "d",
    }

    if api_key:
        params["apikey"] = api_key

    return f"https://stooq.com/q/d/l/?{urlencode(params)}"

def _get_stooq_api_key(config: dict) -> str | None:
    phase_config = _phase7c_config(config)

    explicit_key = phase_config.get("stooq_api_key")

    if explicit_key:
        return str(explicit_key)

    env_var = str(phase_config.get("stooq_api_key_env_var", "STOOQ_API_KEY"))

    return os.environ.get(env_var)

def _download_stooq_prices(
    stooq_symbol: str,
    start_date: str,
    end_date: str,
    api_key: str | None = None,
) -> pd.DataFrame:
    url = _build_stooq_url(
        stooq_symbol=stooq_symbol,
        start_date=start_date,
        end_date=end_date,
        api_key=api_key,
    )

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

    with urlopen(request, timeout=30) as response:  # noqa: S310
        status_code = getattr(response, "status", "")
        raw_bytes = response.read()

    text = raw_bytes.decode("utf-8", errors="replace").strip()

    if not text:
        raise ValueError(
            f"Empty response from Stooq for {stooq_symbol}. "
            f"URL={url}, status={status_code}"
        )

    first_lines = text.splitlines()[:8]
    first_line = first_lines[0].strip() if first_lines else ""
    preview = " | ".join(first_lines)

    response_lower = text.lower()

    if "get your apikey" in response_lower or "apikey" in response_lower:
        raise ProviderAuthenticationRequiredError(
            f"Stooq requires API-key authentication for {stooq_symbol}. "
            f"URL={url}, status={status_code}, first_lines={preview}"
        )

    looks_like_stooq_csv = (
        first_line.lower().replace(" ", "")
        == "date,open,high,low,close,volume"
    )

    if not looks_like_stooq_csv:
        raise ValueError(
            f"Non-CSV or unexpected Stooq response for {stooq_symbol}. "
            f"URL={url}, status={status_code}, first_lines={preview}"
        )

    try:
        data = pd.read_csv(StringIO(text))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"Could not parse Stooq CSV for {stooq_symbol}. "
            f"URL={url}, status={status_code}, first_lines={preview}, error={exc}"
        ) from exc

    required_columns = {"Date", "Close"}

    if not required_columns.issubset(data.columns):
        raise ValueError(
            f"Stooq response for {stooq_symbol} missing columns "
            f"{sorted(required_columns - set(data.columns))}. "
            f"Columns={list(data.columns)}"
        )

    output = data.rename(
        columns={
            "Date": "date",
            "Close": "secondary_price",
        }
    ).copy()

    output["date"] = pd.to_datetime(output["date"], errors="coerce")
    output["secondary_price"] = pd.to_numeric(
        output["secondary_price"],
        errors="coerce",
    )

    output = output.dropna(subset=["date", "secondary_price"]).copy()

    output = output[
        (output["date"] >= pd.Timestamp(start_date))
        & (output["date"] <= pd.Timestamp(end_date))
    ].copy()

    return output[["date", "secondary_price"]].reset_index(drop=True)


def _calculate_price_result_metrics(
    data: pd.DataFrame,
    price_column: str,
    strategy_name: str,
) -> dict:
    if data.empty:
        return {
            "start_date": "",
            "end_date": "",
            "cagr_pct": "",
            "max_drawdown_pct": "",
        }

    result = data[["date", price_column]].rename(columns={price_column: "price"}).copy()
    result["strategy_return"] = result["price"].pct_change().fillna(0.0)
    result["equity"] = 10000.0 * (1.0 + result["strategy_return"]).cumprod()

    # Synthetic buy-and-hold comparison series.
    # calculate_metrics requires position and turnover columns.
    # This is not a strategy execution audit, so keep it simple:
    # fully invested throughout, no rebalance turnover.
    result["position"] = 1.0
    result["turnover"] = 0.0

    return calculate_metrics(
        result=result[
            [
                "date",
                "strategy_return",
                "equity",
                "position",
                "turnover",
            ]
        ],
        strategy_name=strategy_name,
    )


def _classify_cross_check_row(
    daily_return_correlation: float,
    median_abs_daily_return_diff_bps: float,
    cagr_delta_abs: float,
    overlapping_days: int,
    config: dict,
) -> str:
    phase_config = _phase7c_config(config)

    min_overlapping_days = int(phase_config.get("min_overlapping_days", 1000))

    if overlapping_days < min_overlapping_days:
        return "Insufficient overlap"

    clean_corr = float(phase_config.get("clean_min_daily_return_correlation", 0.995))
    acceptable_corr = float(
        phase_config.get("acceptable_min_daily_return_correlation", 0.990)
    )
    review_corr = float(phase_config.get("review_min_daily_return_correlation", 0.970))

    clean_median_diff = float(
        phase_config.get("clean_max_median_abs_daily_return_diff_bps", 5.0)
    )
    acceptable_median_diff = float(
        phase_config.get("acceptable_max_median_abs_daily_return_diff_bps", 10.0)
    )
    review_median_diff = float(
        phase_config.get("review_max_median_abs_daily_return_diff_bps", 25.0)
    )

    clean_cagr_delta = float(phase_config.get("clean_max_cagr_delta_pct_points", 0.25))
    acceptable_cagr_delta = float(
        phase_config.get("acceptable_max_cagr_delta_pct_points", 0.75)
    )
    review_cagr_delta = float(
        phase_config.get("review_max_cagr_delta_pct_points", 1.50)
    )

    if (
        daily_return_correlation >= clean_corr
        and median_abs_daily_return_diff_bps <= clean_median_diff
        and cagr_delta_abs <= clean_cagr_delta
    ):
        return "Clean match"

    if (
        daily_return_correlation >= acceptable_corr
        and median_abs_daily_return_diff_bps <= acceptable_median_diff
        and cagr_delta_abs <= acceptable_cagr_delta
    ):
        return "Acceptable difference"

    if (
        daily_return_correlation >= review_corr
        and median_abs_daily_return_diff_bps <= review_median_diff
        and cagr_delta_abs <= review_cagr_delta
    ):
        return "Review difference"

    return "Potential data issue"


def _compare_primary_secondary_prices(
    ticker: str,
    stooq_symbol: str,
    primary_prices: pd.DataFrame,
    secondary_prices: pd.DataFrame,
    config: dict,
) -> dict:
    merged = primary_prices.merge(
        secondary_prices,
        on="date",
        how="inner",
    ).sort_values("date")

    if len(merged) < 3:
        return {
            "ticker": ticker,
            "secondary_symbol": stooq_symbol,
            "available": True,
            "classification": "Insufficient overlap",
            "start_date": "",
            "end_date": "",
            "overlapping_days": int(len(merged)),
            "daily_return_correlation": "",
            "median_abs_daily_return_diff_bps": "",
            "mean_abs_daily_return_diff_bps": "",
            "primary_cagr_pct": "",
            "secondary_cagr_pct": "",
            "cagr_delta_primary_minus_secondary_pct_points": "",
            "primary_max_drawdown_pct": "",
            "secondary_max_drawdown_pct": "",
            "reason": "Fewer than 3 overlapping rows.",
        }

    merged["primary_return"] = merged["primary_price"].pct_change()
    merged["secondary_return"] = merged["secondary_price"].pct_change()
    returns = merged.dropna(subset=["primary_return", "secondary_return"]).copy()

    if returns.empty:
        return {
            "ticker": ticker,
            "secondary_symbol": stooq_symbol,
            "available": True,
            "classification": "Insufficient overlap",
            "start_date": merged["date"].min().date().isoformat(),
            "end_date": merged["date"].max().date().isoformat(),
            "overlapping_days": int(len(merged)),
            "daily_return_correlation": "",
            "median_abs_daily_return_diff_bps": "",
            "mean_abs_daily_return_diff_bps": "",
            "primary_cagr_pct": "",
            "secondary_cagr_pct": "",
            "cagr_delta_primary_minus_secondary_pct_points": "",
            "primary_max_drawdown_pct": "",
            "secondary_max_drawdown_pct": "",
            "reason": "No comparable daily return rows.",
        }

    returns["abs_return_diff_bps"] = (
        returns["primary_return"] - returns["secondary_return"]
    ).abs() * 10000.0

    daily_return_correlation = float(
        returns["primary_return"].corr(returns["secondary_return"])
    )
    median_abs_diff = float(returns["abs_return_diff_bps"].median())
    mean_abs_diff = float(returns["abs_return_diff_bps"].mean())

    primary_metrics = _calculate_price_result_metrics(
        data=merged,
        price_column="primary_price",
        strategy_name=f"{ticker} primary buy hold",
    )
    secondary_metrics = _calculate_price_result_metrics(
        data=merged,
        price_column="secondary_price",
        strategy_name=f"{ticker} secondary buy hold",
    )

    primary_cagr = float(primary_metrics["cagr_pct"])
    secondary_cagr = float(secondary_metrics["cagr_pct"])
    cagr_delta = primary_cagr - secondary_cagr

    classification = _classify_cross_check_row(
        daily_return_correlation=daily_return_correlation,
        median_abs_daily_return_diff_bps=median_abs_diff,
        cagr_delta_abs=abs(cagr_delta),
        overlapping_days=int(len(returns)),
        config=config,
    )

    return {
        "ticker": ticker,
        "secondary_symbol": stooq_symbol,
        "available": True,
        "classification": classification,
        "start_date": merged["date"].min().date().isoformat(),
        "end_date": merged["date"].max().date().isoformat(),
        "overlapping_days": int(len(returns)),
        "daily_return_correlation": round(daily_return_correlation, 6),
        "median_abs_daily_return_diff_bps": round(median_abs_diff, 3),
        "mean_abs_daily_return_diff_bps": round(mean_abs_diff, 3),
        "primary_cagr_pct": round(primary_cagr, 3),
        "secondary_cagr_pct": round(secondary_cagr, 3),
        "cagr_delta_primary_minus_secondary_pct_points": round(cagr_delta, 3),
        "primary_max_drawdown_pct": primary_metrics["max_drawdown_pct"],
        "secondary_max_drawdown_pct": secondary_metrics["max_drawdown_pct"],
        "reason": "",
    }


def _create_cross_check_summary(cross_check: pd.DataFrame) -> pd.DataFrame:
    if cross_check.empty:
        return pd.DataFrame()

    classification_counts = cross_check["classification"].value_counts().to_dict()

    available_count = int(cross_check["available"].astype(bool).sum())
    unavailable_count = int((~cross_check["available"].astype(bool)).sum())

    provider_auth_required_count = int(
        classification_counts.get("Provider authentication required", 0)
    )
    potential_issue_count = int(
        classification_counts.get("Potential data issue", 0)
    )
    review_count = int(classification_counts.get("Review difference", 0))
    insufficient_count = int(classification_counts.get("Insufficient overlap", 0))

    if available_count == 0 and provider_auth_required_count > 0:
        overall_status = "Provider authentication required"
    elif available_count == 0:
        overall_status = "No secondary data available"
    elif potential_issue_count > 0:
        overall_status = "Potential data issues found"
    elif review_count > 0 or insufficient_count > 0:
        overall_status = "Review needed"
    else:
        overall_status = "Passed"

    return pd.DataFrame(
        [
            {
                "source_name": "stooq",
                "available_tickers": available_count,
                "unavailable_count": unavailable_count,
                "provider_auth_required_count": provider_auth_required_count,
                "clean_match_count": int(classification_counts.get("Clean match", 0)),
                "acceptable_difference_count": int(
                    classification_counts.get("Acceptable difference", 0)
                ),
                "review_difference_count": review_count,
                "potential_data_issue_count": potential_issue_count,
                "insufficient_overlap_count": insufficient_count,
                "overall_status": overall_status,
            }
        ]
    )


def _create_cross_check_conclusion(
    summary: pd.DataFrame,
    cross_check: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    summary_row = summary.iloc[0]
    overall_status = str(summary_row["overall_status"])

    available_count = int(summary_row["available_tickers"])
    auth_required_count = int(summary_row.get("provider_auth_required_count", 0))
    potential_issue_count = int(summary_row["potential_data_issue_count"])

    some_available = available_count > 0
    auth_blocked = available_count == 0 and auth_required_count > 0
    all_available_clean_enough = overall_status == "Passed"
    has_potential_issues = potential_issue_count > 0

    if auth_blocked:
        usable_status = "Deferred"
        usable_interpretation = (
            "Stooq did not provide unauthenticated CSV data. "
            "The provider requires API-key/captcha authentication before this "
            "cross-check can validate prices."
        )
    elif some_available:
        usable_status = "Survived"
        usable_interpretation = (
            f"{available_count} ticker(s) had usable secondary data."
        )
    else:
        usable_status = "Failed"
        usable_interpretation = "No ticker had usable secondary data."

    if auth_blocked:
        agreement_status = "Deferred"
        agreement_interpretation = (
            "Primary/secondary agreement was not tested because the secondary "
            "provider required authentication."
        )
    elif all_available_clean_enough:
        agreement_status = "Survived"
        agreement_interpretation = "Overall status: Passed."
    elif some_available and not has_potential_issues:
        agreement_status = "Review needed"
        agreement_interpretation = f"Overall status: {overall_status}."
    else:
        agreement_status = "Failed"
        agreement_interpretation = f"Overall status: {overall_status}."

    return pd.DataFrame(
        [
            {
                "claim": "A usable secondary data-source cross-check was completed.",
                "status": usable_status,
                "evidence_quality": "Compared primary prices against Stooq daily close data when provider data was available",
                "interpretation": usable_interpretation,
            },
            {
                "claim": "Primary daily returns broadly agree with the secondary source.",
                "status": agreement_status,
                "evidence_quality": "Classification based on daily return correlation, median return difference, and CAGR delta",
                "interpretation": agreement_interpretation,
            },
            {
                "claim": "Stooq unauthenticated CSV access is available for this audit.",
                "status": "Failed" if auth_blocked else "Survived",
                "evidence_quality": "Provider response inspection",
                "interpretation": (
                    "Stooq returned an API-key/captcha requirement instead of CSV data."
                    if auth_blocked
                    else "Stooq provided usable CSV data for at least one ticker."
                ),
            },
            {
                "claim": "The final strategy checkpoint can ignore data-source reliability risk.",
                "status": "Failed",
                "evidence_quality": "Secondary-source checks reduce but do not eliminate data-quality risk",
                "interpretation": (
                    "Data-source reliability remains unresolved until a usable "
                    "secondary source or Stooq API key is added."
                    if auth_blocked
                    else "Even a clean secondary-source comparison does not prove production-grade data reliability."
                ),
            },
            {
                "claim": "The next step should be more strategy optimisation.",
                "status": "Not yet",
                "evidence_quality": "Data reliability and statistical robustness remain higher-priority than new signals",
                "interpretation": (
                    "Do not add new strategy features before completing reliability/statistical audits."
                ),
            },
        ]
    )


def write_secondary_data_source_cross_check_markdown(
    cross_check: pd.DataFrame,
    summary: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Secondary Data-Source Cross-Check v2

This Phase 7C report compares primary cached price data against Stooq daily close data.

The purpose is not to prove production-grade data quality. It is to catch obvious source-level disagreements.

## Cross-Check Results

{cross_check.to_markdown(index=False) if not cross_check.empty else "No cross-check results available."}

## Summary

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_secondary_data_source_cross_check_v2(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase7c_config(config)

    if not phase_config.get("enabled", False):
        return {
            "cross_check": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    start_date = str(phase_config.get("pinned_start_date", "2006-04-28"))
    end_date = str(phase_config.get("pinned_end_date", "2026-05-01"))
    stooq_api_key = _get_stooq_api_key(config)
    ticker_map = {
        _normalise_ticker(ticker): str(symbol)
        for ticker, symbol in phase_config.get("tickers", {}).items()
    }

    rows: list[dict] = []

    for ticker, stooq_symbol in ticker_map.items():
        try:
            primary_raw = _find_primary_price_data(
                ticker_outputs=ticker_outputs,
                ticker=ticker,
            )
            primary_prices = _normalise_primary_prices(
                price_data=primary_raw,
                start_date=start_date,
                end_date=end_date,
            )
            secondary_prices = _download_stooq_prices(
                stooq_symbol=stooq_symbol,
                start_date=start_date,
                end_date=end_date,
                api_key=stooq_api_key,
            )

            rows.append(
                _compare_primary_secondary_prices(
                    ticker=ticker,
                    stooq_symbol=stooq_symbol,
                    primary_prices=primary_prices,
                    secondary_prices=secondary_prices,
                    config=config,
                )
            )

        except ProviderAuthenticationRequiredError as exc:
            rows.append(
                {
                    "ticker": ticker,
                    "secondary_symbol": stooq_symbol,
                    "available": False,
                    "classification": "Provider authentication required",
                    "start_date": "",
                    "end_date": "",
                    "overlapping_days": "",
                    "daily_return_correlation": "",
                    "median_abs_daily_return_diff_bps": "",
                    "mean_abs_daily_return_diff_bps": "",
                    "primary_cagr_pct": "",
                    "secondary_cagr_pct": "",
                    "cagr_delta_primary_minus_secondary_pct_points": "",
                    "primary_max_drawdown_pct": "",
                    "secondary_max_drawdown_pct": "",
                    "reason": str(exc),
                }
            )
            
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "ticker": ticker,
                    "secondary_symbol": stooq_symbol,
                    "available": False,
                    "classification": "Unavailable",
                    "start_date": "",
                    "end_date": "",
                    "overlapping_days": "",
                    "daily_return_correlation": "",
                    "median_abs_daily_return_diff_bps": "",
                    "mean_abs_daily_return_diff_bps": "",
                    "primary_cagr_pct": "",
                    "secondary_cagr_pct": "",
                    "cagr_delta_primary_minus_secondary_pct_points": "",
                    "primary_max_drawdown_pct": "",
                    "secondary_max_drawdown_pct": "",
                    "reason": str(exc),
                }
            )

    cross_check = pd.DataFrame(rows)
    summary = _create_cross_check_summary(cross_check)
    conclusion = _create_cross_check_conclusion(
        summary=summary,
        cross_check=cross_check,
    )

    return {
        "cross_check": cross_check,
        "summary": summary,
        "conclusion": conclusion,
    }


def save_secondary_data_source_cross_check_v2(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_secondary_data_source_cross_check_v2(
        ticker_outputs=ticker_outputs,
        config=config,
    )

    cross_check = outputs["cross_check"]
    summary = outputs["summary"]
    conclusion = outputs["conclusion"]

    if cross_check.empty:
        return outputs

    cross_check_path = reports_dir / "secondary_data_source_cross_check_v2.csv"
    summary_path = reports_dir / "secondary_data_source_cross_check_v2_summary.csv"
    conclusion_path = reports_dir / "secondary_data_source_cross_check_v2_conclusion.csv"
    markdown_path = reports_dir / "secondary_data_source_cross_check_v2.md"

    cross_check.to_csv(cross_check_path, index=False)
    summary.to_csv(summary_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_secondary_data_source_cross_check_markdown(
        cross_check=cross_check,
        summary=summary,
        conclusion=conclusion,
        output_path=markdown_path,
    )

    print("\nSecondary data-source cross-check v2:")
    print(cross_check.to_string(index=False))

    print("\nSecondary data-source cross-check v2 summary:")
    print(summary.to_string(index=False))

    print("\nSecondary data-source cross-check v2 conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved secondary data-source cross-check v2 to: {cross_check_path}")
    print(f"Saved secondary data-source cross-check v2 summary to: {summary_path}")
    print(f"Saved secondary data-source cross-check v2 conclusion to: {conclusion_path}")
    print(f"Saved secondary data-source cross-check v2 markdown to: {markdown_path}")

    return outputs