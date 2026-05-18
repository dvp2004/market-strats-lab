from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.secondary_data_source_cross_check_v2 import (
    _calculate_price_result_metrics,
    _download_stooq_prices,
    _find_primary_price_data,
    _get_stooq_api_key,
    _normalise_ticker,
)


def _phase7c2_config(config: dict) -> dict:
    return config.get("phase7_secondary_data_source_difference_attribution", {})


def _find_raw_close_column(price_data: pd.DataFrame) -> str | None:
    candidates = [
        "close",
        "raw_close",
        "unadjusted_close",
        "Close",
        "close_price",
    ]

    for column in candidates:
        if column in price_data.columns:
            return column

    return None


def _normalise_primary_basis_prices(
    price_data: pd.DataFrame,
    price_column: str,
    output_column: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    output = price_data.copy()

    if "date" not in output.columns:
        raise ValueError("primary price data missing date column")

    if price_column not in output.columns:
        return pd.DataFrame(columns=["date", output_column])

    output["date"] = pd.to_datetime(output["date"])
    output[output_column] = pd.to_numeric(output[price_column], errors="coerce")

    output = output[
        (output["date"] >= pd.Timestamp(start_date))
        & (output["date"] <= pd.Timestamp(end_date))
    ].copy()

    return output[["date", output_column]].dropna().sort_values("date").reset_index(
        drop=True
    )


def _compare_price_basis_to_secondary(
    ticker: str,
    basis_name: str,
    primary_basis_prices: pd.DataFrame,
    secondary_prices: pd.DataFrame,
) -> dict:
    primary_column = [
        column for column in primary_basis_prices.columns if column != "date"
    ][0]

    merged = primary_basis_prices.merge(
        secondary_prices,
        on="date",
        how="inner",
    ).sort_values("date")

    if len(merged) < 3:
        return {
            "ticker": ticker,
            "basis_name": basis_name,
            "available": False,
            "start_date": "",
            "end_date": "",
            "overlapping_days": int(len(merged)),
            "daily_return_correlation": "",
            "median_abs_daily_return_diff_bps": "",
            "mean_abs_daily_return_diff_bps": "",
            "primary_basis_cagr_pct": "",
            "secondary_cagr_pct": "",
            "cagr_delta_primary_minus_secondary_pct_points": "",
            "primary_basis_max_drawdown_pct": "",
            "secondary_max_drawdown_pct": "",
            "reason": "Fewer than 3 overlapping rows.",
        }

    merged["primary_return"] = merged[primary_column].pct_change()
    merged["secondary_return"] = merged["secondary_price"].pct_change()

    returns = merged.dropna(subset=["primary_return", "secondary_return"]).copy()

    if returns.empty:
        return {
            "ticker": ticker,
            "basis_name": basis_name,
            "available": False,
            "start_date": merged["date"].min().date().isoformat(),
            "end_date": merged["date"].max().date().isoformat(),
            "overlapping_days": int(len(merged)),
            "daily_return_correlation": "",
            "median_abs_daily_return_diff_bps": "",
            "mean_abs_daily_return_diff_bps": "",
            "primary_basis_cagr_pct": "",
            "secondary_cagr_pct": "",
            "cagr_delta_primary_minus_secondary_pct_points": "",
            "primary_basis_max_drawdown_pct": "",
            "secondary_max_drawdown_pct": "",
            "reason": "No comparable daily return rows.",
        }

    returns["abs_return_diff_bps"] = (
        returns["primary_return"] - returns["secondary_return"]
    ).abs() * 10000.0

    primary_metrics = _calculate_price_result_metrics(
        data=merged,
        price_column=primary_column,
        strategy_name=f"{ticker} {basis_name} buy hold",
    )
    secondary_metrics = _calculate_price_result_metrics(
        data=merged,
        price_column="secondary_price",
        strategy_name=f"{ticker} secondary buy hold",
    )

    primary_cagr = float(primary_metrics["cagr_pct"])
    secondary_cagr = float(secondary_metrics["cagr_pct"])
    cagr_delta = primary_cagr - secondary_cagr

    primary_drawdown = float(primary_metrics["max_drawdown_pct"])
    secondary_drawdown = float(secondary_metrics["max_drawdown_pct"])
    drawdown_delta = primary_drawdown - secondary_drawdown

    return {
        "ticker": ticker,
        "basis_name": basis_name,
        "available": True,
        "start_date": merged["date"].min().date().isoformat(),
        "end_date": merged["date"].max().date().isoformat(),
        "overlapping_days": int(len(returns)),
        "daily_return_correlation": round(
            float(returns["primary_return"].corr(returns["secondary_return"])),
            6,
        ),
        "median_abs_daily_return_diff_bps": round(
            float(returns["abs_return_diff_bps"].median()),
            3,
        ),
        "mean_abs_daily_return_diff_bps": round(
            float(returns["abs_return_diff_bps"].mean()),
            3,
        ),
        "primary_basis_cagr_pct": round(primary_cagr, 3),
        "secondary_cagr_pct": round(secondary_cagr, 3),
        "cagr_delta_primary_minus_secondary_pct_points": round(cagr_delta, 3),
        "primary_basis_max_drawdown_pct": round(primary_drawdown, 3),
        "secondary_max_drawdown_pct": round(secondary_drawdown, 3),
        "drawdown_delta_primary_minus_secondary_pct_points": round(drawdown_delta, 3),
        "reason": "",
    }


def _classify_attribution(
    ticker: str,
    adjusted_row: dict,
    raw_row: dict | None,
    prior_classification: str,
    config: dict,
) -> str:
    phase_config = _phase7c2_config(config)

    distribution_sensitive = {
        _normalise_ticker(value)
        for value in phase_config.get("distribution_sensitive_tickers", [])
    }

    raw_corr_threshold = float(
        phase_config.get("raw_close_match_min_correlation", 0.995)
    )
    raw_cagr_delta_threshold = float(
        phase_config.get("raw_close_match_max_cagr_delta_pct_points", 0.75)
    )
    large_adjusted_cagr_delta_threshold = float(
        phase_config.get("adjusted_vs_secondary_large_cagr_delta_pct_points", 0.75)
    )
    potential_issue_cagr_threshold = float(
        phase_config.get("potential_issue_min_cagr_delta_pct_points", 1.50)
    )
    potential_issue_drawdown_threshold = float(
        phase_config.get("potential_issue_min_drawdown_delta_pct_points", 5.00)
    )

    adjusted_cagr_delta = abs(
        float(adjusted_row["cagr_delta_primary_minus_secondary_pct_points"])
    )
    adjusted_drawdown_delta = abs(
        float(adjusted_row["drawdown_delta_primary_minus_secondary_pct_points"])
    )

    raw_available = raw_row is not None and bool(raw_row.get("available", False))

    if raw_available:
        raw_corr = float(raw_row["daily_return_correlation"])
        raw_cagr_delta = abs(
            float(raw_row["cagr_delta_primary_minus_secondary_pct_points"])
        )

        if (
            raw_corr >= raw_corr_threshold
            and raw_cagr_delta <= raw_cagr_delta_threshold
            and adjusted_cagr_delta >= large_adjusted_cagr_delta_threshold
        ):
            return "Likely adjusted-vs-unadjusted distribution difference"

    if (
        _normalise_ticker(ticker) in distribution_sensitive
        and adjusted_cagr_delta >= large_adjusted_cagr_delta_threshold
    ):
        return "Likely distribution/price-basis difference; raw close unavailable or inconclusive"

    if prior_classification in {"Clean match", "Acceptable difference"}:
        return "No material data-source concern"

    if (
        adjusted_cagr_delta >= potential_issue_cagr_threshold
        or adjusted_drawdown_delta >= potential_issue_drawdown_threshold
    ):
        return "Unresolved potential data issue"

    return "Review difference; not enough evidence for unresolved issue"


def _safe_float(value: object) -> float | None:
    try:
        if value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _create_attribution_summary(attribution: pd.DataFrame) -> pd.DataFrame:
    if attribution.empty:
        return pd.DataFrame()

    counts = attribution["attribution"].value_counts().to_dict()

    unresolved_count = int(counts.get("Unresolved potential data issue", 0))
    distribution_count = int(
        counts.get("Likely adjusted-vs-unadjusted distribution difference", 0)
        + counts.get(
            "Likely distribution/price-basis difference; raw close unavailable or inconclusive",
            0,
        )
    )

    if unresolved_count > 0:
        overall_status = "Unresolved data issues remain"
    elif distribution_count > 0:
        overall_status = "Differences mostly attributable to price-basis/distributions"
    else:
        overall_status = "Passed"

    return pd.DataFrame(
        [
            {
                "ticker_count": int(len(attribution)),
                "no_material_concern_count": int(
                    counts.get("No material data-source concern", 0)
                ),
                "distribution_or_price_basis_count": distribution_count,
                "review_difference_count": int(
                    counts.get(
                        "Review difference; not enough evidence for unresolved issue",
                        0,
                    )
                ),
                "unresolved_potential_data_issue_count": unresolved_count,
                "overall_status": overall_status,
            }
        ]
    )


def _create_attribution_conclusion(
    attribution_summary: pd.DataFrame,
    attribution: pd.DataFrame,
) -> pd.DataFrame:
    if attribution_summary.empty:
        return pd.DataFrame()

    row = attribution_summary.iloc[0]
    unresolved_count = int(row["unresolved_potential_data_issue_count"])
    distribution_count = int(row["distribution_or_price_basis_count"])

    unresolved = attribution[
        attribution["attribution"] == "Unresolved potential data issue"
    ]

    return pd.DataFrame(
        [
            {
                "claim": "Secondary-source differences were attributed rather than ignored.",
                "status": "Survived",
                "evidence_quality": "Compared adjusted close and raw close, where available, against Stooq close",
                "interpretation": (
                    "The report separates clean matches, likely price-basis differences, and unresolved issues."
                ),
            },
            {
                "claim": "Distribution-heavy ETF differences are likely explained by price basis.",
                "status": "Survived" if distribution_count > 0 else "Not applicable",
                "evidence_quality": "Checked distribution-sensitive tickers and adjusted-vs-secondary CAGR gaps",
                "interpretation": (
                    f"{distribution_count} ticker(s) were classified as likely distribution/price-basis differences."
                ),
            },
            {
                "claim": "No unresolved secondary-source data issues remain.",
                "status": "Survived" if unresolved_count == 0 else "Failed",
                "evidence_quality": "Attribution classification",
                "interpretation": (
                    "No unresolved potential data issues remain."
                    if unresolved_count == 0
                    else "Unresolved potential data issues remain for: "
                    + ", ".join(unresolved["ticker"].astype(str).tolist())
                ),
            },
            {
                "claim": "Stooq close can fully validate yfinance adjusted-close total-return data.",
                "status": "Failed",
                "evidence_quality": "Stooq close appears to differ from adjusted-close total-return series for some distribution-heavy ETFs",
                "interpretation": (
                    "A close-price source cannot fully validate adjusted-close total-return data without matching adjustment methodology."
                ),
            },
            {
                "claim": "The next step should be more strategy optimisation.",
                "status": "Not yet",
                "evidence_quality": "Data reliability and statistical robustness remain higher-priority than new signals",
                "interpretation": "Continue audit/statistical robustness work before adding more strategy features.",
            },
        ]
    )


def write_secondary_data_source_difference_attribution_markdown(
    basis_comparison: pd.DataFrame,
    attribution: pd.DataFrame,
    summary: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Secondary Data-Source Difference Attribution

This Phase 7C.2 report investigates whether Stooq/yfinance differences are true data issues or expected price-basis differences.

The main suspicion is that Stooq close data may not match yfinance adjusted-close total-return data for distribution-heavy ETFs.

## Price-Basis Comparison

{basis_comparison.to_markdown(index=False) if not basis_comparison.empty else "No basis comparison available."}

## Attribution

{attribution.to_markdown(index=False) if not attribution.empty else "No attribution available."}

## Summary

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_secondary_data_source_difference_attribution(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase7c2_config(config)

    if not phase_config.get("enabled", False):
        return {
            "basis_comparison": pd.DataFrame(),
            "attribution": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    reports_dir = Path(reports_dir)

    start_date = str(phase_config.get("pinned_start_date", "2006-04-28"))
    end_date = str(phase_config.get("pinned_end_date", "2026-05-01"))
    stooq_api_key = _get_stooq_api_key(config)

    cross_check_path = reports_dir / str(
        phase_config.get(
            "source_cross_check_report",
            "secondary_data_source_cross_check_v2.csv",
        )
    )

    if cross_check_path.exists():
        cross_check = pd.read_csv(cross_check_path)
    else:
        cross_check = pd.DataFrame()

    ticker_map = {
        _normalise_ticker(ticker): str(symbol)
        for ticker, symbol in phase_config.get("tickers", {}).items()
    }

    basis_rows: list[dict] = []
    attribution_rows: list[dict] = []

    for ticker, stooq_symbol in ticker_map.items():
        try:
            primary_raw = _find_primary_price_data(
                ticker_outputs=ticker_outputs,
                ticker=ticker,
            )
            raw_close_column = _find_raw_close_column(primary_raw)

            adjusted_prices = _normalise_primary_basis_prices(
                price_data=primary_raw,
                price_column="adj_close",
                output_column="primary_adjusted_price",
                start_date=start_date,
                end_date=end_date,
            )

            secondary_prices = _download_stooq_prices(
                stooq_symbol=stooq_symbol,
                start_date=start_date,
                end_date=end_date,
                api_key=stooq_api_key,
            )

            adjusted_row = _compare_price_basis_to_secondary(
                ticker=ticker,
                basis_name="primary_adjusted_close",
                primary_basis_prices=adjusted_prices,
                secondary_prices=secondary_prices,
            )
            basis_rows.append(adjusted_row)

            raw_row = None

            if raw_close_column:
                raw_prices = _normalise_primary_basis_prices(
                    price_data=primary_raw,
                    price_column=raw_close_column,
                    output_column="primary_raw_close",
                    start_date=start_date,
                    end_date=end_date,
                )

                if not raw_prices.empty:
                    raw_row = _compare_price_basis_to_secondary(
                        ticker=ticker,
                        basis_name=f"primary_raw_close:{raw_close_column}",
                        primary_basis_prices=raw_prices,
                        secondary_prices=secondary_prices,
                    )
                    basis_rows.append(raw_row)

            prior_classification = ""

            if not cross_check.empty and "ticker" in cross_check.columns:
                prior_rows = cross_check[
                    cross_check["ticker"].astype(str).str.upper() == ticker
                ]

                if not prior_rows.empty:
                    prior_classification = str(prior_rows.iloc[0]["classification"])

            attribution = _classify_attribution(
                ticker=ticker,
                adjusted_row=adjusted_row,
                raw_row=raw_row,
                prior_classification=prior_classification,
                config=config,
            )

            adjusted_cagr_delta = _safe_float(
                adjusted_row["cagr_delta_primary_minus_secondary_pct_points"]
            )
            raw_cagr_delta = (
                _safe_float(raw_row["cagr_delta_primary_minus_secondary_pct_points"])
                if raw_row
                else None
            )

            attribution_rows.append(
                {
                    "ticker": ticker,
                    "prior_cross_check_classification": prior_classification,
                    "raw_close_column": raw_close_column or "",
                    "adjusted_vs_secondary_cagr_delta_pct_points": adjusted_cagr_delta,
                    "raw_vs_secondary_cagr_delta_pct_points": raw_cagr_delta
                    if raw_cagr_delta is not None
                    else "",
                    "adjusted_vs_secondary_return_correlation": adjusted_row[
                        "daily_return_correlation"
                    ],
                    "raw_vs_secondary_return_correlation": raw_row[
                        "daily_return_correlation"
                    ]
                    if raw_row
                    else "",
                    "attribution": attribution,
                    "reason": "",
                }
            )
        except Exception as exc:  # noqa: BLE001
            attribution_rows.append(
                {
                    "ticker": ticker,
                    "prior_cross_check_classification": "",
                    "raw_close_column": "",
                    "adjusted_vs_secondary_cagr_delta_pct_points": "",
                    "raw_vs_secondary_cagr_delta_pct_points": "",
                    "adjusted_vs_secondary_return_correlation": "",
                    "raw_vs_secondary_return_correlation": "",
                    "attribution": "Attribution failed",
                    "reason": str(exc),
                }
            )

    basis_comparison = pd.DataFrame(basis_rows)
    attribution = pd.DataFrame(attribution_rows)
    summary = _create_attribution_summary(attribution)
    conclusion = _create_attribution_conclusion(
        attribution_summary=summary,
        attribution=attribution,
    )

    return {
        "basis_comparison": basis_comparison,
        "attribution": attribution,
        "summary": summary,
        "conclusion": conclusion,
    }


def save_secondary_data_source_difference_attribution(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_secondary_data_source_difference_attribution(
        ticker_outputs=ticker_outputs,
        config=config,
        reports_dir=reports_dir,
    )

    basis_comparison = outputs["basis_comparison"]
    attribution = outputs["attribution"]
    summary = outputs["summary"]
    conclusion = outputs["conclusion"]

    if attribution.empty:
        return outputs

    basis_path = reports_dir / "secondary_data_source_difference_basis_comparison.csv"
    attribution_path = reports_dir / "secondary_data_source_difference_attribution.csv"
    summary_path = reports_dir / "secondary_data_source_difference_attribution_summary.csv"
    conclusion_path = (
        reports_dir / "secondary_data_source_difference_attribution_conclusion.csv"
    )
    markdown_path = reports_dir / "secondary_data_source_difference_attribution.md"

    basis_comparison.to_csv(basis_path, index=False)
    attribution.to_csv(attribution_path, index=False)
    summary.to_csv(summary_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_secondary_data_source_difference_attribution_markdown(
        basis_comparison=basis_comparison,
        attribution=attribution,
        summary=summary,
        conclusion=conclusion,
        output_path=markdown_path,
    )

    print("\nSecondary data-source difference basis comparison:")
    print(basis_comparison.to_string(index=False))

    print("\nSecondary data-source difference attribution:")
    print(attribution.to_string(index=False))

    print("\nSecondary data-source difference attribution summary:")
    print(summary.to_string(index=False))

    print("\nSecondary data-source difference attribution conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved basis comparison to: {basis_path}")
    print(f"Saved attribution to: {attribution_path}")
    print(f"Saved attribution summary to: {summary_path}")
    print(f"Saved attribution conclusion to: {conclusion_path}")
    print(f"Saved attribution markdown to: {markdown_path}")

    return outputs