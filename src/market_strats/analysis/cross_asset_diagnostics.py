from __future__ import annotations

from pathlib import Path

import pandas as pd


def _get_strategy_row(metrics: pd.DataFrame, ticker: str, strategy: str) -> pd.Series:
    row = metrics[(metrics["ticker"] == ticker) & (metrics["strategy"] == strategy)]

    if row.empty:
        raise ValueError(f"Missing strategy row for ticker={ticker}, strategy={strategy}")

    return row.iloc[0]


def _get_rolling_value(
    rolling_summary: pd.DataFrame,
    ticker: str,
    strategy: str,
    window_years: int,
    column: str,
) -> float:
    if rolling_summary.empty:
        return float("nan")

    required_columns = {"ticker", "strategy", "window_years", column}

    if not required_columns.issubset(set(rolling_summary.columns)):
        return float("nan")

    row = rolling_summary[
        (rolling_summary["ticker"] == ticker)
        & (rolling_summary["strategy"] == strategy)
        & (rolling_summary["window_years"] == window_years)
    ]

    if row.empty:
        return float("nan")

    return float(row[column].iloc[0])


def _calculate_history_years(start_date: str, end_date: str) -> float:
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    return round((end - start).days / 365.25, 2)


def _create_diagnostic_verdict(row: dict) -> str:
    cagr_delta = row["cagr_delta_pct_points"]
    drawdown_improvement = row["drawdown_improvement_pct_points"]
    worst_5y_improvement = row["worst_5y_cagr_improvement_pct_points"]

    if cagr_delta >= 0 and drawdown_improvement >= 15:
        return "Strong: matched or beat buy-and-hold CAGR with materially lower drawdown."

    if cagr_delta >= -1.0 and drawdown_improvement >= 20:
        return "Good risk-control trade-off: small CAGR give-up for major drawdown reduction."

    if cagr_delta < -1.0 and drawdown_improvement >= 15 and worst_5y_improvement > 0:
        return "Mixed: improved downside behaviour, but return sacrifice is material."

    if drawdown_improvement < 10:
        return "Weak: drawdown improvement is not large enough to justify strategy complexity."

    return "Needs review: trade-off is not clearly strong or weak."


def create_buy_hold_vs_momentum_diagnostic(
    metrics: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    momentum_strategy: str = "12-Month Absolute Momentum",
) -> pd.DataFrame:
    """
    Create a cross-asset diagnostic comparing Buy and Hold with 12-month momentum.

    This table is designed for cross-asset interpretation. It does not compare
    scorecard values across tickers. Instead, it directly compares the same two
    strategies inside each ticker.
    """
    if metrics.empty:
        return pd.DataFrame()

    if "ticker" not in metrics.columns:
        raise ValueError("metrics must contain a ticker column")

    tickers = sorted(metrics["ticker"].dropna().unique())

    rows: list[dict] = []

    for ticker in tickers:
        buy_hold = _get_strategy_row(metrics, ticker, "Buy and Hold")
        momentum = _get_strategy_row(metrics, ticker, momentum_strategy)

        history_years = _calculate_history_years(
            start_date=str(buy_hold["start_date"]),
            end_date=str(buy_hold["end_date"]),
        )

        buy_hold_worst_3y = _get_rolling_value(
            rolling_summary,
            ticker,
            "Buy and Hold",
            3,
            "worst_cagr_pct",
        )
        momentum_worst_3y = _get_rolling_value(
            rolling_summary,
            ticker,
            momentum_strategy,
            3,
            "worst_cagr_pct",
        )
        buy_hold_worst_5y = _get_rolling_value(
            rolling_summary,
            ticker,
            "Buy and Hold",
            5,
            "worst_cagr_pct",
        )
        momentum_worst_5y = _get_rolling_value(
            rolling_summary,
            ticker,
            momentum_strategy,
            5,
            "worst_cagr_pct",
        )

        buy_hold_avg_3y = _get_rolling_value(
            rolling_summary,
            ticker,
            "Buy and Hold",
            3,
            "avg_cagr_pct",
        )
        momentum_avg_3y = _get_rolling_value(
            rolling_summary,
            ticker,
            momentum_strategy,
            3,
            "avg_cagr_pct",
        )
        buy_hold_avg_5y = _get_rolling_value(
            rolling_summary,
            ticker,
            "Buy and Hold",
            5,
            "avg_cagr_pct",
        )
        momentum_avg_5y = _get_rolling_value(
            rolling_summary,
            ticker,
            momentum_strategy,
            5,
            "avg_cagr_pct",
        )

        row = {
            "ticker": ticker,
            "asset_start_date": buy_hold["start_date"],
            "asset_end_date": buy_hold["end_date"],
            "history_years": history_years,
            "buy_hold_end_value": float(buy_hold["end_value"]),
            "momentum_end_value": float(momentum["end_value"]),
            "end_value_delta": float(momentum["end_value"] - buy_hold["end_value"]),
            "buy_hold_cagr_pct": float(buy_hold["cagr_pct"]),
            "momentum_cagr_pct": float(momentum["cagr_pct"]),
            "cagr_delta_pct_points": float(momentum["cagr_pct"] - buy_hold["cagr_pct"]),
            "buy_hold_volatility_pct": float(buy_hold["volatility_pct"]),
            "momentum_volatility_pct": float(momentum["volatility_pct"]),
            "volatility_delta_pct_points": float(
                momentum["volatility_pct"] - buy_hold["volatility_pct"]
            ),
            "buy_hold_sharpe": float(buy_hold["sharpe"]),
            "momentum_sharpe": float(momentum["sharpe"]),
            "sharpe_delta": float(momentum["sharpe"] - buy_hold["sharpe"]),
            "buy_hold_max_drawdown_pct": float(buy_hold["max_drawdown_pct"]),
            "momentum_max_drawdown_pct": float(momentum["max_drawdown_pct"]),
            "drawdown_improvement_pct_points": float(
                momentum["max_drawdown_pct"] - buy_hold["max_drawdown_pct"]
            ),
            "buy_hold_avg_3y_cagr_pct": buy_hold_avg_3y,
            "momentum_avg_3y_cagr_pct": momentum_avg_3y,
            "avg_3y_cagr_delta_pct_points": momentum_avg_3y - buy_hold_avg_3y,
            "buy_hold_worst_3y_cagr_pct": buy_hold_worst_3y,
            "momentum_worst_3y_cagr_pct": momentum_worst_3y,
            "worst_3y_cagr_improvement_pct_points": (
                momentum_worst_3y - buy_hold_worst_3y
            ),
            "buy_hold_avg_5y_cagr_pct": buy_hold_avg_5y,
            "momentum_avg_5y_cagr_pct": momentum_avg_5y,
            "avg_5y_cagr_delta_pct_points": momentum_avg_5y - buy_hold_avg_5y,
            "buy_hold_worst_5y_cagr_pct": buy_hold_worst_5y,
            "momentum_worst_5y_cagr_pct": momentum_worst_5y,
            "worst_5y_cagr_improvement_pct_points": (
                momentum_worst_5y - buy_hold_worst_5y
            ),
            "momentum_exposure_time_pct": float(momentum["exposure_time_pct"]),
            "momentum_trade_count": int(momentum["trade_count"]),
        }

        row["verdict"] = _create_diagnostic_verdict(row)

        rows.append(row)

    result = pd.DataFrame(rows)

    numeric_columns = result.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        result[column] = result[column].round(2)

    return result.sort_values("ticker").reset_index(drop=True)


def write_buy_hold_vs_momentum_markdown(
    diagnostic: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """
    Write a readable markdown report for the cross-asset diagnostic.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if diagnostic.empty:
        output_path.write_text(
            "# Cross-Asset Buy-and-Hold vs 12-Month Momentum Diagnostic\n\nNo data available.\n",
            encoding="utf-8",
        )
        return output_path

    display_columns = [
        "ticker",
        "history_years",
        "asset_start_date",
        "asset_end_date",
        "buy_hold_cagr_pct",
        "momentum_cagr_pct",
        "cagr_delta_pct_points",
        "buy_hold_max_drawdown_pct",
        "momentum_max_drawdown_pct",
        "drawdown_improvement_pct_points",
        "buy_hold_worst_5y_cagr_pct",
        "momentum_worst_5y_cagr_pct",
        "worst_5y_cagr_improvement_pct_points",
        "momentum_trade_count",
        "verdict",
    ]

    available_columns = [column for column in display_columns if column in diagnostic.columns]

    markdown_table = diagnostic[available_columns].to_markdown(index=False)

    content = f"""# Cross-Asset Buy-and-Hold vs 12-Month Momentum Diagnostic

This report compares buy-and-hold against 12-month absolute momentum within each ticker.

Do not compare raw scorecard values across tickers. Different assets have different histories, volatility profiles, return distributions, and drawdown structures.

## Diagnostic Table

{markdown_table}

## Interpretation Rules

- Positive CAGR delta means 12-month momentum beat buy-and-hold on CAGR.
- Positive drawdown improvement means 12-month momentum reduced max drawdown.
- Worst rolling CAGR improvement is often more important than tiny full-period CAGR differences.
- History length matters: shorter-history ETFs miss earlier regimes and should not be interpreted as equally complete tests.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path