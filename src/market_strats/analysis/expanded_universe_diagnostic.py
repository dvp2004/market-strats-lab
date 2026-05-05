from __future__ import annotations

from pathlib import Path

import pandas as pd


ASSET_METADATA = {
    "SPY": {
        "asset_class": "US large-cap equities",
        "research_note": (
            "Cleanest current success case for 12M absolute momentum; "
            "buy-and-hold-like compounding with materially lower drawdown."
        ),
    },
    "QQQ": {
        "asset_class": "US growth / Nasdaq-100",
        "research_note": (
            "Momentum is useful as crash protection, but robustness is messier "
            "than SPY and not a clean CAGR improvement."
        ),
    },
    "IWM": {
        "asset_class": "US small caps",
        "research_note": (
            "Current timing rules reduce drawdown but sacrifice too much CAGR; "
            "small-cap cycles appear less friendly to slow momentum."
        ),
    },
    "EFA": {
        "asset_class": "Developed ex-US equities",
        "research_note": (
            "12M momentum failed, but 200D SMA beat buy-and-hold on both CAGR "
            "and drawdown; faster trend filters may fit this market better."
        ),
    },
    "EEM": {
        "asset_class": "Emerging markets",
        "research_note": (
            "12M momentum reduced drawdown but sacrificed too much return; "
            "international high-volatility markets need separate treatment."
        ),
    },
    "GLD": {
        "asset_class": "Gold",
        "research_note": (
            "12M momentum reduced drawdown but gave up too much CAGR; gold has "
            "different crisis/real-rate trend dynamics."
        ),
    },
    "TLT": {
        "asset_class": "Long-duration US Treasuries",
        "research_note": (
            "Useful mainly as risk-control evidence, not a compounding engine; "
            "rate-cycle risk makes interpretation different from equities."
        ),
    },
    "AGG": {
        "asset_class": "Aggregate US bonds",
        "research_note": (
            "Quietly strong defensive result for 12M momentum: small CAGR lift, "
            "lower drawdown, and better risk metrics."
        ),
    },
    "VNQ": {
        "asset_class": "US REITs",
        "research_note": (
            "12M momentum reduced drawdown but destroyed too much compounding; "
            "REITs behave like credit-sensitive equity hybrids."
        ),
    },
    "BTC-USD": {
        "asset_class": "Bitcoin",
        "research_note": (
            "Quarantined high-volatility result: short history, extreme regime "
            "dependence, and no direct comparison to ETF-era assets."
        ),
    },
}


def _get_row(metrics: pd.DataFrame, ticker: str, strategy: str) -> pd.Series | None:
    row = metrics[(metrics["ticker"] == ticker) & (metrics["strategy"] == strategy)]

    if row.empty:
        return None

    return row.iloc[0]


def _safe_float(value: object) -> float:
    if pd.isna(value):
        return float("nan")

    return float(value)


def _history_years(start_date: str, end_date: str) -> float:
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    return round((end - start).days / 365.25, 2)


def _classify_market(
    buy_hold: pd.Series,
    momentum: pd.Series | None,
    best_cagr_strategy: str,
    best_drawdown_strategy: str,
    best_scorecard_strategy: str,
) -> str:
    buy_hold_cagr = _safe_float(buy_hold["cagr_pct"])
    buy_hold_dd = _safe_float(buy_hold["max_drawdown_pct"])

    if momentum is None:
        return "Needs review: missing 12M momentum row."

    momentum_cagr = _safe_float(momentum["cagr_pct"])
    momentum_dd = _safe_float(momentum["max_drawdown_pct"])

    cagr_delta = momentum_cagr - buy_hold_cagr
    drawdown_improvement = momentum_dd - buy_hold_dd

    cagr_sacrifice = buy_hold_cagr - momentum_cagr
    cagr_sacrifice_pct_of_bh = (
        cagr_sacrifice / buy_hold_cagr if buy_hold_cagr > 0 else 0.0
    )

    if cagr_delta >= -0.25 and drawdown_improvement >= 10:
        return "12M momentum candidate."

    if cagr_sacrifice_pct_of_bh > 0.20 and drawdown_improvement > 10:
        return "Risk-control only; fails wealth test."

    if best_cagr_strategy == "Buy and Hold" and drawdown_improvement < 10:
        return "Buy-and-hold favoured."

    if best_scorecard_strategy != best_cagr_strategy:
        return "Scorecard conflict; needs objective classification."

    if best_drawdown_strategy != best_cagr_strategy:
        return "Return/drawdown trade-off; needs manual review."

    return "Needs manual review."


def create_expanded_universe_diagnostic(
    metrics: pd.DataFrame,
    scorecards: pd.DataFrame,
    momentum_strategy: str = "12-Month Absolute Momentum",
) -> pd.DataFrame:
    """
    Create one compact market map across all tested tickers.

    This is deliberately not a universal ranking table. It maps each market to
    the strategy behaviour observed inside that market.
    """
    if metrics.empty:
        return pd.DataFrame()

    required_metric_columns = {
        "ticker",
        "strategy",
        "start_date",
        "end_date",
        "end_value",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "trade_count",
    }

    missing_metric_columns = required_metric_columns - set(metrics.columns)

    if missing_metric_columns:
        raise ValueError(f"Missing metric columns: {sorted(missing_metric_columns)}")

    if not scorecards.empty:
        required_scorecard_columns = {"ticker", "strategy", "composite_rank"}
        missing_scorecard_columns = required_scorecard_columns - set(scorecards.columns)

        if missing_scorecard_columns:
            raise ValueError(
                f"Missing scorecard columns: {sorted(missing_scorecard_columns)}"
            )

    rows: list[dict] = []

    for ticker in sorted(metrics["ticker"].dropna().unique()):
        ticker_metrics = metrics[metrics["ticker"] == ticker].copy()

        buy_hold = _get_row(metrics, ticker, "Buy and Hold")

        if buy_hold is None:
            continue

        momentum = _get_row(metrics, ticker, momentum_strategy)

        best_cagr_row = ticker_metrics.sort_values(
            ["cagr_pct", "max_drawdown_pct"],
            ascending=[False, False],
        ).iloc[0]

        best_drawdown_row = ticker_metrics.sort_values(
            ["max_drawdown_pct", "cagr_pct"],
            ascending=[False, False],
        ).iloc[0]

        if scorecards.empty:
            best_scorecard_strategy = ""
        else:
            ticker_scorecard = scorecards[scorecards["ticker"] == ticker].copy()

            if ticker_scorecard.empty:
                best_scorecard_strategy = ""
            else:
                best_scorecard_strategy = str(
                    ticker_scorecard.sort_values("composite_rank").iloc[0]["strategy"]
                )

        start_date = str(buy_hold["start_date"])
        end_date = str(buy_hold["end_date"])

        metadata = ASSET_METADATA.get(
            ticker,
            {
                "asset_class": "Unclassified",
                "research_note": "No research note yet.",
            },
        )

        buy_hold_cagr = _safe_float(buy_hold["cagr_pct"])
        buy_hold_dd = _safe_float(buy_hold["max_drawdown_pct"])

        if momentum is None:
            momentum_end_value = float("nan")
            momentum_cagr = float("nan")
            momentum_dd = float("nan")
            momentum_sharpe = float("nan")
            momentum_trade_count = float("nan")
            momentum_cagr_delta = float("nan")
            momentum_dd_improvement = float("nan")
        else:
            momentum_end_value = _safe_float(momentum["end_value"])
            momentum_cagr = _safe_float(momentum["cagr_pct"])
            momentum_dd = _safe_float(momentum["max_drawdown_pct"])
            momentum_sharpe = _safe_float(momentum["sharpe"])
            momentum_trade_count = int(momentum["trade_count"])
            momentum_cagr_delta = momentum_cagr - buy_hold_cagr
            momentum_dd_improvement = momentum_dd - buy_hold_dd

        classification = _classify_market(
            buy_hold=buy_hold,
            momentum=momentum,
            best_cagr_strategy=str(best_cagr_row["strategy"]),
            best_drawdown_strategy=str(best_drawdown_row["strategy"]),
            best_scorecard_strategy=best_scorecard_strategy,
        )

        rows.append(
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "history_years": _history_years(start_date, end_date),
                "asset_class": metadata["asset_class"],
                "buy_hold_end_value": _safe_float(buy_hold["end_value"]),
                "buy_hold_cagr_pct": buy_hold_cagr,
                "buy_hold_max_drawdown_pct": buy_hold_dd,
                "buy_hold_sharpe": _safe_float(buy_hold["sharpe"]),
                "momentum_end_value": momentum_end_value,
                "momentum_cagr_pct": momentum_cagr,
                "momentum_max_drawdown_pct": momentum_dd,
                "momentum_sharpe": momentum_sharpe,
                "momentum_trade_count": momentum_trade_count,
                "momentum_cagr_delta_pct_points": momentum_cagr_delta,
                "momentum_drawdown_improvement_pct_points": momentum_dd_improvement,
                "best_cagr_strategy": str(best_cagr_row["strategy"]),
                "best_cagr_pct": _safe_float(best_cagr_row["cagr_pct"]),
                "best_drawdown_strategy": str(best_drawdown_row["strategy"]),
                "best_drawdown_pct": _safe_float(best_drawdown_row["max_drawdown_pct"]),
                "best_scorecard_strategy": best_scorecard_strategy,
                "practical_classification": classification,
                "research_note": metadata["research_note"],
            }
        )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(2)

    return output.reset_index(drop=True)


def write_expanded_universe_diagnostic_markdown(
    diagnostic: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if diagnostic.empty:
        output_path.write_text(
            "# Expanded Universe Diagnostic\n\nNo data available.\n",
            encoding="utf-8",
        )
        return output_path

    display_columns = [
        "ticker",
        "start_date",
        "history_years",
        "asset_class",
        "buy_hold_cagr_pct",
        "momentum_cagr_pct",
        "momentum_cagr_delta_pct_points",
        "buy_hold_max_drawdown_pct",
        "momentum_max_drawdown_pct",
        "momentum_drawdown_improvement_pct_points",
        "best_cagr_strategy",
        "best_drawdown_strategy",
        "best_scorecard_strategy",
        "practical_classification",
        "research_note",
    ]

    available_columns = [column for column in display_columns if column in diagnostic.columns]

    markdown_table = diagnostic[available_columns].to_markdown(index=False)

    content = f"""# Expanded Universe Diagnostic

This report maps how the tested strategies behaved across the expanded market universe.

This is not a universal ranking table. Each row should be interpreted within that asset's own history, start date, volatility profile, and return structure.

## Diagnostic Table

{markdown_table}

## Interpretation Notes

- Start date matters. BTC-USD, GLD, AGG, VNQ, EEM, and EFA do not share SPY's 1993 history.
- A high scorecard result is not automatically a wealth-building result.
- 12M absolute momentum should be treated as a candidate where it preserves CAGR while reducing drawdown.
- If a strategy sacrifices too much CAGR, it is risk-control only, not a wealth-builder.
- BTC-USD is quarantined because its history is short, extreme, and not comparable to mature ETF markets.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path