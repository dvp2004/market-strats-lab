from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.strategies.fixed_weight_portfolio import (
    run_independent_weighted_portfolio,
)


FINALIST_SPY_STRATEGIES = [
    {
        "ticker": "SPY",
        "strategy": "Buy and Hold",
        "final_label": "Passive benchmark",
    },
    {
        "ticker": "SPY",
        "strategy": "12-Month Absolute Momentum",
        "final_label": "Leading simple core strategy",
    },
    {
        "ticker": "SPY",
        "strategy": "60/40 Annual Rebalanced Core-Satellite SPY B&H + 12M Momentum",
        "final_label": "Highest gross terminal-wealth SPY architecture",
    },
]


def _get_strategy_result(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
    strategy: str,
) -> pd.DataFrame:
    ticker = ticker.upper()

    if ticker not in ticker_outputs:
        raise ValueError(f"Ticker {ticker} not found in ticker outputs")

    strategy_results = ticker_outputs[ticker].get("strategy_results")

    if strategy_results is None:
        raise ValueError(f"Ticker {ticker} output is missing strategy_results")

    if strategy not in strategy_results:
        available = sorted(strategy_results.keys())
        raise ValueError(
            f"Strategy '{strategy}' not found for {ticker}. Available: {available}"
        )

    return strategy_results[strategy]


def _slice_and_rebase_result(
    result: pd.DataFrame,
    start_date: str | pd.Timestamp | None,
    end_date: str | pd.Timestamp | None,
    initial_capital: float,
) -> pd.DataFrame:
    required_columns = {
        "date",
        "adj_close",
        "strategy_return",
        "equity",
        "position",
        "cash_position",
        "turnover",
    }

    missing_columns = required_columns - set(result.columns)

    if missing_columns:
        raise ValueError(f"result missing columns: {sorted(missing_columns)}")

    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    if start_date is not None:
        df = df[df["date"] >= pd.to_datetime(start_date)]

    if end_date is not None:
        df = df[df["date"] <= pd.to_datetime(end_date)]

    df = df.copy().reset_index(drop=True)

    if len(df) < 2:
        return pd.DataFrame()

    df["strategy_return"] = df["strategy_return"].astype(float)
    df.loc[df.index[0], "strategy_return"] = 0.0
    df["equity"] = initial_capital * (1.0 + df["strategy_return"]).cumprod()

    return df


def _build_candidate_portfolio_result(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    portfolio_config: dict,
    initial_capital: float,
) -> pd.DataFrame:
    component_results: dict[str, pd.DataFrame] = {}
    weights: dict[str, float] = {}

    for component in portfolio_config["components"]:
        ticker = str(component["ticker"]).upper()
        strategy = str(component["strategy"])
        weight = float(component["weight"])
        component_name = f"{ticker} {strategy}"

        component_results[component_name] = _get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=ticker,
            strategy=strategy,
        )
        weights[component_name] = weight

    return run_independent_weighted_portfolio(
        component_results=component_results,
        weights=weights,
        initial_capital=initial_capital,
        portfolio_name=str(portfolio_config["name"]),
    )


def _period_definitions(
    reference_end_date: str,
    holdout_start_date: str,
) -> list[dict]:
    return [
        {
            "period": "reference",
            "start_date": None,
            "end_date": reference_end_date,
        },
        {
            "period": "holdout",
            "start_date": holdout_start_date,
            "end_date": None,
        },
    ]


def create_finalist_holdout_validation_report(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    validation_config = config.get("finalist_holdout_validation", {})

    if not validation_config.get("enabled", False):
        return pd.DataFrame()

    initial_capital = float(config["initial_capital"])
    reference_end_date = str(validation_config["reference_end_date"])
    holdout_start_date = str(validation_config["holdout_start_date"])

    finalists: list[dict] = []

    for item in FINALIST_SPY_STRATEGIES:
        result = _get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=item["ticker"],
            strategy=item["strategy"],
        )

        finalists.append(
            {
                "strategy": item["strategy"],
                "final_label": item["final_label"],
                "result": result,
            }
        )

    for portfolio_config in validation_config.get("finalist_portfolios", []):
        result = _build_candidate_portfolio_result(
            ticker_outputs=ticker_outputs,
            portfolio_config=portfolio_config,
            initial_capital=initial_capital,
        )

        finalists.append(
            {
                "strategy": str(portfolio_config["name"]),
                "final_label": "Candidate portfolio",
                "result": result,
            }
        )

    rows: list[dict] = []

    for period in _period_definitions(reference_end_date, holdout_start_date):
        for finalist in finalists:
            sliced = _slice_and_rebase_result(
                result=finalist["result"],
                start_date=period["start_date"],
                end_date=period["end_date"],
                initial_capital=initial_capital,
            )

            if sliced.empty:
                continue

            metrics = calculate_metrics(
                sliced,
                finalist["strategy"],
            )

            rows.append(
                {
                    "period": period["period"],
                    "strategy": finalist["strategy"],
                    "final_label": finalist["final_label"],
                    "start_date": metrics["start_date"],
                    "end_date": metrics["end_date"],
                    "end_value": metrics["end_value"],
                    "cagr_pct": metrics["cagr_pct"],
                    "calmar": metrics["calmar"],
                    "volatility_pct": metrics["volatility_pct"],
                    "sharpe": metrics["sharpe"],
                    "sortino": metrics["sortino"],
                    "max_drawdown_pct": metrics["max_drawdown_pct"],
                    "worst_month_pct": metrics["worst_month_pct"],
                    "exposure_time_pct": metrics["exposure_time_pct"],
                    "trade_count": metrics["trade_count"],
                }
            )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.reset_index(drop=True)


def create_finalist_holdout_validation_summary(
    validation_report: pd.DataFrame,
) -> pd.DataFrame:
    if validation_report.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for period, period_df in validation_report.groupby("period"):
        best_cagr = period_df.sort_values("cagr_pct", ascending=False).iloc[0]
        best_calmar = period_df.sort_values("calmar", ascending=False).iloc[0]
        best_drawdown = period_df.sort_values(
            "max_drawdown_pct",
            ascending=False,
        ).iloc[0]

        spy_12m = period_df[
            period_df["strategy"] == "12-Month Absolute Momentum"
        ]

        if spy_12m.empty:
            spy_12m_cagr = float("nan")
            spy_12m_drawdown = float("nan")
            spy_12m_calmar = float("nan")
        else:
            spy_12m_row = spy_12m.iloc[0]
            spy_12m_cagr = float(spy_12m_row["cagr_pct"])
            spy_12m_drawdown = float(spy_12m_row["max_drawdown_pct"])
            spy_12m_calmar = float(spy_12m_row["calmar"])

        rows.append(
            {
                "period": period,
                "best_cagr_strategy": best_cagr["strategy"],
                "best_cagr_pct": best_cagr["cagr_pct"],
                "best_calmar_strategy": best_calmar["strategy"],
                "best_calmar": best_calmar["calmar"],
                "best_drawdown_strategy": best_drawdown["strategy"],
                "best_max_drawdown_pct": best_drawdown["max_drawdown_pct"],
                "spy_12m_cagr_pct": spy_12m_cagr,
                "spy_12m_max_drawdown_pct": spy_12m_drawdown,
                "spy_12m_calmar": spy_12m_calmar,
            }
        )

    return pd.DataFrame(rows)


def write_finalist_holdout_validation_markdown(
    validation_report: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if validation_report.empty:
        output_path.write_text(
            "# Finalist Holdout Validation\n\nNo validation data available.\n",
            encoding="utf-8",
        )
        return output_path

    display_columns = [
        "period",
        "strategy",
        "final_label",
        "start_date",
        "end_date",
        "end_value",
        "cagr_pct",
        "calmar",
        "max_drawdown_pct",
        "sharpe",
        "sortino",
        "exposure_time_pct",
        "trade_count",
    ]

    available_columns = [
        column for column in display_columns if column in validation_report.columns
    ]

    report_table = validation_report[available_columns].to_markdown(index=False)
    summary_table = summary.to_markdown(index=False) if not summary.empty else ""

    content = f"""# Finalist Holdout Validation

This report splits the final strategy candidates into reference and holdout periods.

It is not a full walk-forward optimisation. It is a first validation check to see whether the final conclusions remain directionally true outside the earlier reference period.

## Summary

{summary_table}

## Full Validation Table

{report_table}

## Interpretation Notes

- The holdout period is the more important section.
- SPY-only strategies have longer histories than multi-asset portfolios.
- Multi-asset portfolios naturally begin later because AGG and EFA have later inception dates.
- This report should not be used to tune parameters after the fact.
- If the conclusions reverse in the holdout period, the full-period conclusions need to be softened.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_finalist_holdout_validation_report(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    validation_report = create_finalist_holdout_validation_report(
        ticker_outputs=ticker_outputs,
        config=config,
    )

    if validation_report.empty:
        return {
            "validation_report": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    summary = create_finalist_holdout_validation_summary(validation_report)

    report_path = reports_dir / "finalist_holdout_validation.csv"
    summary_path = reports_dir / "finalist_holdout_validation_summary.csv"
    markdown_path = reports_dir / "finalist_holdout_validation.md"

    validation_report.to_csv(report_path, index=False)
    summary.to_csv(summary_path, index=False)

    write_finalist_holdout_validation_markdown(
        validation_report=validation_report,
        summary=summary,
        output_path=markdown_path,
    )

    print("\nFinalist holdout validation:")
    print(validation_report.to_string(index=False))

    print("\nFinalist holdout validation summary:")
    print(summary.to_string(index=False))

    print(f"\nSaved finalist holdout validation to: {report_path}")
    print(f"Saved finalist holdout validation summary to: {summary_path}")
    print(f"Saved finalist holdout validation markdown to: {markdown_path}")

    return {
        "validation_report": validation_report,
        "summary": summary,
    }