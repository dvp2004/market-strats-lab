from __future__ import annotations

from pathlib import Path

import pandas as pd


MAX_CAGR_LAG_PCT_POINTS = 1.50
MAX_CAGR_SACRIFICE_OF_BUY_HOLD = 0.20
RETURN_ENHANCING_MIN_CAGR_DELTA_PCT_POINTS = 0.20
WEALTH_EQUIVALENT_MIN_CAGR_DELTA_PCT_POINTS = -0.25
MATERIAL_DRAWDOWN_IMPROVEMENT_PCT_POINTS = 10.0
DEFENSIVE_DRAWDOWN_IMPROVEMENT_PCT_POINTS = 3.0
CORE_SATELLITE_MAX_CAGR_LAG_PCT_POINTS = 0.50
HIGH_TRADE_COUNT = 150

UNVALIDATED_LEADS = {
    ("EFA", "10-Month SMA"),
}


def _get_benchmark_row(metrics: pd.DataFrame, ticker: str | None) -> pd.Series:
    df = metrics.copy()

    if ticker is not None and "ticker" in df.columns:
        df = df[df["ticker"] == ticker]

    row = df[df["strategy"] == "Buy and Hold"]

    if row.empty:
        raise ValueError(f"Missing Buy and Hold benchmark for ticker={ticker}")

    return row.iloc[0]


def _get_rolling_value(
    rolling_summary: pd.DataFrame,
    ticker: str | None,
    strategy: str,
    window_years: int,
    column: str,
) -> float:
    if rolling_summary.empty:
        return float("nan")

    required_columns = {"strategy", "window_years", column}

    if not required_columns.issubset(set(rolling_summary.columns)):
        return float("nan")

    df = rolling_summary.copy()

    if ticker is not None and "ticker" in df.columns:
        df = df[df["ticker"] == ticker]

    row = df[
        (df["strategy"] == strategy)
        & (df["window_years"] == window_years)
    ]

    if row.empty:
        return float("nan")

    return float(row[column].iloc[0])


def _safe_float(value: object) -> float:
    if pd.isna(value):
        return float("nan")

    return float(value)


def _is_unvalidated_lead(ticker: str | None, strategy: str) -> bool:
    if ticker is None:
        return False

    return (ticker, strategy) in UNVALIDATED_LEADS


def _classify_base_strategy(
    strategy: str,
    cagr_delta_vs_buy_hold: float,
    cagr_sacrifice_pct_of_buy_hold: float,
    drawdown_improvement_vs_buy_hold: float,
    worst_5y_cagr_delta_vs_buy_hold: float,
    trade_count: int,
) -> tuple[str, bool, str]:
    """
    Classify non-BTC, non-core-satellite strategies.

    The classifier separates return improvement from risk reduction.
    It avoids calling tiny positive CAGR differences "wealth-building alpha".
    """
    wealth_test_pass = (
        cagr_delta_vs_buy_hold >= -MAX_CAGR_LAG_PCT_POINTS
        and cagr_sacrifice_pct_of_buy_hold <= MAX_CAGR_SACRIFICE_OF_BUY_HOLD
    )

    if not wealth_test_pass:
        if drawdown_improvement_vs_buy_hold >= MATERIAL_DRAWDOWN_IMPROVEMENT_PCT_POINTS:
            return (
                "Risk-control only",
                False,
                "Drawdown improved, but CAGR sacrifice is too large for wealth-building.",
            )

        return (
            "Rejected / weak",
            False,
            "Does not preserve enough compounding or improve drawdown enough versus buy-and-hold.",
        )

    if (
        cagr_delta_vs_buy_hold >= RETURN_ENHANCING_MIN_CAGR_DELTA_PCT_POINTS
        and drawdown_improvement_vs_buy_hold >= 0
    ):
        return (
            "Return-enhancing candidate",
            True,
            "Improves CAGR by a meaningful threshold and does not worsen drawdown versus buy-and-hold.",
        )

    if (
        cagr_delta_vs_buy_hold >= WEALTH_EQUIVALENT_MIN_CAGR_DELTA_PCT_POINTS
        and drawdown_improvement_vs_buy_hold
        >= MATERIAL_DRAWDOWN_IMPROVEMENT_PCT_POINTS
    ):
        return (
            "Wealth-equivalent risk reducer",
            True,
            "Keeps CAGR close to buy-and-hold while materially reducing drawdown.",
        )

    if (
        cagr_delta_vs_buy_hold >= WEALTH_EQUIVALENT_MIN_CAGR_DELTA_PCT_POINTS
        and drawdown_improvement_vs_buy_hold
        >= DEFENSIVE_DRAWDOWN_IMPROVEMENT_PCT_POINTS
    ):
        return (
            "Defensive sleeve candidate",
            True,
            "Keeps CAGR close to buy-and-hold while modestly reducing drawdown.",
        )

    if drawdown_improvement_vs_buy_hold >= MATERIAL_DRAWDOWN_IMPROVEMENT_PCT_POINTS:
        return (
            "Risk-control candidate",
            True,
            "Passes the wealth hurdle and materially improves drawdown, but gives up noticeable CAGR.",
        )

    if (
        worst_5y_cagr_delta_vs_buy_hold > 0
        and drawdown_improvement_vs_buy_hold > 0
    ):
        return (
            "Risk-control candidate",
            True,
            "Passes the wealth hurdle and improves bad-window behaviour, but needs manual review.",
        )

    if trade_count > HIGH_TRADE_COUNT and cagr_delta_vs_buy_hold < 0:
        return (
            "Rejected / weak",
            False,
            "Too trade-heavy without enough return improvement.",
        )

    return (
        "Rejected / weak",
        False,
        "Does not justify itself versus buy-and-hold.",
    )


def _classify_strategy(
    ticker: str | None,
    strategy: str,
    cagr_delta_vs_buy_hold: float,
    cagr_sacrifice_pct_of_buy_hold: float,
    drawdown_improvement_vs_buy_hold: float,
    worst_5y_cagr_delta_vs_buy_hold: float,
    trade_count: int,
) -> tuple[str, str, bool, bool, str]:
    """
    Return:
    - purpose classification
    - base classification
    - wealth test pass
    - pending validation
    - note
    """
    if ticker == "BTC-USD":
        return (
            "Quarantined / separate branch",
            "Quarantined / separate branch",
            False,
            True,
            "BTC history is short, extreme, and not comparable with mature ETF markets.",
        )

    if strategy == "Buy and Hold":
        return (
            "Benchmark",
            "Benchmark",
            True,
            False,
            "Passive benchmark for this ticker.",
        )

    if "Core-Satellite" in strategy:
        if (
            cagr_delta_vs_buy_hold >= -CORE_SATELLITE_MAX_CAGR_LAG_PCT_POINTS
            and drawdown_improvement_vs_buy_hold
            >= MATERIAL_DRAWDOWN_IMPROVEMENT_PCT_POINTS
        ):
            return (
                "Behavioural compromise",
                "Behavioural compromise",
                True,
                False,
                "Preserves most compounding while reducing drawdown versus buy-and-hold.",
            )

        return (
            "Rejected / weak",
            "Rejected / weak",
            False,
            False,
            "Core-satellite complexity is not justified by the return/drawdown trade-off.",
        )

    base_classification, wealth_test_pass, base_note = _classify_base_strategy(
        strategy=strategy,
        cagr_delta_vs_buy_hold=cagr_delta_vs_buy_hold,
        cagr_sacrifice_pct_of_buy_hold=cagr_sacrifice_pct_of_buy_hold,
        drawdown_improvement_vs_buy_hold=drawdown_improvement_vs_buy_hold,
        worst_5y_cagr_delta_vs_buy_hold=worst_5y_cagr_delta_vs_buy_hold,
        trade_count=trade_count,
    )

    if _is_unvalidated_lead(ticker, strategy):
        return (
            "Unvalidated lead",
            base_classification,
            wealth_test_pass,
            True,
            (
                f"Base classification is '{base_classification}', but this result "
                "emerged from a broad strategy scan and needs neighbouring-window robustness."
            ),
        )

    return (
        base_classification,
        base_classification,
        wealth_test_pass,
        False,
        base_note,
    )


def classify_strategy_purpose(
    metrics: pd.DataFrame,
    rolling_summary: pd.DataFrame,
) -> pd.DataFrame:
    """
    Classify each strategy by practical research purpose.

    This decision-support layer prevents low-CAGR defensive strategies from
    being mistaken for wealth-building strategies simply because drawdown or
    Sharpe looks better.
    """
    if metrics.empty:
        return pd.DataFrame()

    required_columns = {
        "strategy",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "trade_count",
    }

    missing_columns = required_columns - set(metrics.columns)

    if missing_columns:
        raise ValueError(f"Missing metric columns: {sorted(missing_columns)}")

    if "ticker" in metrics.columns:
        tickers: list[str | None] = sorted(metrics["ticker"].dropna().unique())
    else:
        tickers = [None]

    rows: list[dict] = []

    for ticker in tickers:
        benchmark = _get_benchmark_row(metrics, ticker)
        benchmark_cagr = _safe_float(benchmark["cagr_pct"])
        benchmark_drawdown = _safe_float(benchmark["max_drawdown_pct"])

        ticker_metrics = metrics.copy()

        if ticker is not None and "ticker" in ticker_metrics.columns:
            ticker_metrics = ticker_metrics[ticker_metrics["ticker"] == ticker]

        benchmark_worst_5y = _get_rolling_value(
            rolling_summary=rolling_summary,
            ticker=ticker,
            strategy="Buy and Hold",
            window_years=5,
            column="worst_cagr_pct",
        )

        for _, row in ticker_metrics.iterrows():
            strategy = str(row["strategy"])

            strategy_cagr = _safe_float(row["cagr_pct"])
            strategy_drawdown = _safe_float(row["max_drawdown_pct"])
            strategy_sharpe = _safe_float(row["sharpe"])
            trade_count = int(row["trade_count"])

            cagr_delta = strategy_cagr - benchmark_cagr
            cagr_sacrifice = max(0.0, benchmark_cagr - strategy_cagr)
            cagr_sacrifice_pct = (
                cagr_sacrifice / benchmark_cagr
                if benchmark_cagr > 0
                else 0.0
            )

            drawdown_improvement = strategy_drawdown - benchmark_drawdown

            strategy_worst_5y = _get_rolling_value(
                rolling_summary=rolling_summary,
                ticker=ticker,
                strategy=strategy,
                window_years=5,
                column="worst_cagr_pct",
            )
            worst_5y_delta = strategy_worst_5y - benchmark_worst_5y

            (
                classification,
                base_classification,
                wealth_test_pass,
                pending_validation,
                note,
            ) = _classify_strategy(
                ticker=ticker,
                strategy=strategy,
                cagr_delta_vs_buy_hold=cagr_delta,
                cagr_sacrifice_pct_of_buy_hold=cagr_sacrifice_pct,
                drawdown_improvement_vs_buy_hold=drawdown_improvement,
                worst_5y_cagr_delta_vs_buy_hold=worst_5y_delta,
                trade_count=trade_count,
            )

            rows.append(
                {
                    "ticker": ticker if ticker is not None else "",
                    "strategy": strategy,
                    "purpose_classification": classification,
                    "base_purpose_classification": base_classification,
                    "wealth_test_pass": wealth_test_pass,
                    "pending_validation": pending_validation,
                    "cagr_pct": strategy_cagr,
                    "buy_hold_cagr_pct": benchmark_cagr,
                    "cagr_delta_vs_buy_hold_pct_points": cagr_delta,
                    "cagr_sacrifice_pct_of_buy_hold": cagr_sacrifice_pct * 100.0,
                    "max_drawdown_pct": strategy_drawdown,
                    "buy_hold_max_drawdown_pct": benchmark_drawdown,
                    "drawdown_improvement_vs_buy_hold_pct_points": drawdown_improvement,
                    "sharpe": strategy_sharpe,
                    "trade_count": trade_count,
                    "worst_5y_cagr_pct": strategy_worst_5y,
                    "buy_hold_worst_5y_cagr_pct": benchmark_worst_5y,
                    "worst_5y_cagr_delta_vs_buy_hold_pct_points": worst_5y_delta,
                    "classification_note": note,
                }
            )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(2)

    classification_order = {
        "Return-enhancing candidate": 1,
        "Wealth-equivalent risk reducer": 2,
        "Defensive sleeve candidate": 3,
        "Behavioural compromise": 4,
        "Benchmark": 5,
        "Risk-control candidate": 6,
        "Risk-control only": 7,
        "Unvalidated lead": 8,
        "Quarantined / separate branch": 9,
        "Rejected / weak": 10,
    }

    output["classification_rank"] = output["purpose_classification"].map(
        classification_order
    ).fillna(99)

    sort_columns = ["classification_rank", "cagr_pct"]

    if "ticker" in output.columns:
        sort_columns = ["ticker", "classification_rank", "cagr_pct"]

    output = output.sort_values(sort_columns, ascending=[True, True, False]).reset_index(
        drop=True
    )

    output = output.drop(columns=["classification_rank"])

    return output


def write_strategy_purpose_markdown(
    classifications: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if classifications.empty:
        output_path.write_text(
            "# Strategy Purpose Classification\n\nNo data available.\n",
            encoding="utf-8",
        )
        return output_path

    display_columns = [
        "ticker",
        "strategy",
        "purpose_classification",
        "base_purpose_classification",
        "wealth_test_pass",
        "pending_validation",
        "cagr_pct",
        "buy_hold_cagr_pct",
        "cagr_delta_vs_buy_hold_pct_points",
        "cagr_sacrifice_pct_of_buy_hold",
        "max_drawdown_pct",
        "drawdown_improvement_vs_buy_hold_pct_points",
        "worst_5y_cagr_pct",
        "worst_5y_cagr_delta_vs_buy_hold_pct_points",
        "trade_count",
        "classification_note",
    ]

    available_columns = [
        column for column in display_columns if column in classifications.columns
    ]

    markdown_table = classifications[available_columns].to_markdown(index=False)

    content = f"""# Strategy Purpose Classification

This report classifies strategies by practical purpose rather than raw scorecard rank.

The purpose is to prevent defensive low-CAGR strategies from being mistaken for wealth-building strategies.

## Classification Table

{markdown_table}

## Classification Rules

- Return-enhancing candidate: meaningfully improves CAGR and does not worsen drawdown.
- Wealth-equivalent risk reducer: keeps CAGR close to buy-and-hold while materially reducing drawdown.
- Defensive sleeve candidate: keeps CAGR close to buy-and-hold while modestly improving drawdown.
- Behavioural compromise: improves liveability without necessarily being mathematically optimal.
- Risk-control candidate: passes the wealth hurdle and materially improves risk, but gives up noticeable CAGR.
- Risk-control only: improves drawdown but sacrifices too much CAGR.
- Unvalidated lead: promising result that emerged from a broad scan and needs robustness testing.
- Rejected / weak: does not justify itself versus buy-and-hold.
- Quarantined / separate branch: not comparable enough to the main ETF universe.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path