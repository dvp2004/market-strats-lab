from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.strategies.fixed_weight_portfolio import (
    rebase_strategy_result_to_dates,
)


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
    df["adj_close"] = df["equity"]

    return df


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


def _build_benchmark_results(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    benchmark_configs: list[dict],
    common_dates: list[pd.Timestamp],
    initial_capital: float,
) -> dict[str, pd.DataFrame]:
    benchmark_results: dict[str, pd.DataFrame] = {}

    for benchmark in benchmark_configs:
        ticker = str(benchmark["ticker"]).upper()
        strategy = str(benchmark["strategy"])
        benchmark_name = f"{ticker} {strategy}"

        result = _get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=ticker,
            strategy=strategy,
        )

        benchmark_results[benchmark_name] = rebase_strategy_result_to_dates(
            result=result,
            dates=common_dates,
            initial_capital=initial_capital,
        )

    return benchmark_results


def create_relative_momentum_holdout_validation_report(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    validation_config = config.get("relative_momentum_holdout_validation", {})

    if not validation_config.get("enabled", False):
        return pd.DataFrame()

    if not relative_momentum_outputs:
        return pd.DataFrame()

    initial_capital = float(config["initial_capital"])
    reference_end_date = str(validation_config["reference_end_date"])
    holdout_start_date = str(validation_config["holdout_start_date"])

    allocator_config = config.get("relative_momentum_allocator", {})
    benchmark_configs = allocator_config.get("benchmarks", [])

    allocator_results: dict[str, pd.DataFrame] = {}

    for strategy_name, output in relative_momentum_outputs.items():
        allocator_result = output.get("allocator_result")

        if allocator_result is None or allocator_result.empty:
            continue

        allocator_results[strategy_name] = allocator_result

    if not allocator_results:
        return pd.DataFrame()

    first_allocator = next(iter(allocator_results.values()))
    common_dates = list(pd.to_datetime(first_allocator["date"]))

    comparison_results = dict(allocator_results)
    comparison_results.update(
        _build_benchmark_results(
            ticker_outputs=ticker_outputs,
            benchmark_configs=benchmark_configs,
            common_dates=common_dates,
            initial_capital=initial_capital,
        )
    )

    rows: list[dict] = []

    for period in _period_definitions(reference_end_date, holdout_start_date):
        for strategy_name, result in comparison_results.items():
            sliced = _slice_and_rebase_result(
                result=result,
                start_date=period["start_date"],
                end_date=period["end_date"],
                initial_capital=initial_capital,
            )

            if sliced.empty:
                continue

            metrics = calculate_metrics(sliced, strategy_name)

            rows.append(
                {
                    "period": period["period"],
                    "strategy": strategy_name,
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

    if output.empty:
        return output

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.reset_index(drop=True)


def create_relative_momentum_holdout_validation_summary(
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
        best_volatility = period_df.sort_values(
            "volatility_pct",
            ascending=True,
        ).iloc[0]

        spy_12m = period_df[
            period_df["strategy"] == "SPY 12-Month Absolute Momentum"
        ]

        if spy_12m.empty:
            spy_12m_cagr = float("nan")
            spy_12m_calmar = float("nan")
            spy_12m_drawdown = float("nan")
        else:
            spy_12m_row = spy_12m.iloc[0]
            spy_12m_cagr = float(spy_12m_row["cagr_pct"])
            spy_12m_calmar = float(spy_12m_row["calmar"])
            spy_12m_drawdown = float(spy_12m_row["max_drawdown_pct"])

        rows.append(
            {
                "period": period,
                "best_cagr_strategy": best_cagr["strategy"],
                "best_cagr_pct": best_cagr["cagr_pct"],
                "best_calmar_strategy": best_calmar["strategy"],
                "best_calmar": best_calmar["calmar"],
                "best_drawdown_strategy": best_drawdown["strategy"],
                "best_max_drawdown_pct": best_drawdown["max_drawdown_pct"],
                "lowest_volatility_strategy": best_volatility["strategy"],
                "lowest_volatility_pct": best_volatility["volatility_pct"],
                "spy_12m_cagr_pct": spy_12m_cagr,
                "spy_12m_calmar": spy_12m_calmar,
                "spy_12m_max_drawdown_pct": spy_12m_drawdown,
            }
        )

    summary = pd.DataFrame(rows)

    numeric_columns = summary.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        summary[column] = summary[column].round(3)

    return summary.reset_index(drop=True)


def write_relative_momentum_holdout_validation_markdown(
    validation_report: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if validation_report.empty:
        output_path.write_text(
            "# Relative Momentum Holdout Validation\n\nNo validation data available.\n",
            encoding="utf-8",
        )
        return output_path

    display_columns = [
        "period",
        "strategy",
        "start_date",
        "end_date",
        "end_value",
        "cagr_pct",
        "calmar",
        "volatility_pct",
        "sharpe",
        "sortino",
        "max_drawdown_pct",
        "worst_month_pct",
        "exposure_time_pct",
        "trade_count",
    ]

    available_columns = [
        column for column in display_columns if column in validation_report.columns
    ]

    report_table = validation_report[available_columns].to_markdown(index=False)
    summary_table = summary.to_markdown(index=False) if not summary.empty else ""

    content = f"""# Relative Momentum Holdout Validation

This report validates the Phase 2 relative momentum allocator variants across reference and holdout periods.

It is designed to answer whether the current Phase 2 allocator conclusions are stable across regimes, or whether they are full-period artefacts.

## Summary

{summary_table}

## Full Validation Table

{report_table}

## Interpretation Notes

- The holdout period is the more important section.
- The key candidates are the trend-confirmed allocators.
- The constrained allocator should be judged primarily as a defensive/liveability variant.
- SPY 12M remains the Phase 1 benchmark to beat.
- If a Phase 2 allocator only wins in one period, the claim must be softened.
- This report should not be used to tune parameters after the fact.

## Questions This Report Should Answer

1. Does trend confirmation improve allocator quality in both periods?
2. Does the constrained allocator reduce drawdown in both periods?
3. Does the unconstrained trend-confirmed allocator remain the best balanced Phase 2 candidate?
4. Does any Phase 2 allocator beat SPY 12M on both return and risk?
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_relative_momentum_holdout_validation_report(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    validation_report = create_relative_momentum_holdout_validation_report(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    if validation_report.empty:
        return {
            "validation_report": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    summary = create_relative_momentum_holdout_validation_summary(validation_report)

    report_path = reports_dir / "relative_momentum_holdout_validation.csv"
    summary_path = reports_dir / "relative_momentum_holdout_validation_summary.csv"
    markdown_path = reports_dir / "relative_momentum_holdout_validation.md"

    validation_report.to_csv(report_path, index=False)
    summary.to_csv(summary_path, index=False)

    write_relative_momentum_holdout_validation_markdown(
        validation_report=validation_report,
        summary=summary,
        output_path=markdown_path,
    )

    print("\nRelative momentum holdout validation:")
    print(validation_report.to_string(index=False))

    print("\nRelative momentum holdout validation summary:")
    print(summary.to_string(index=False))

    print(f"\nSaved relative momentum holdout validation to: {report_path}")
    print(f"Saved relative momentum holdout validation summary to: {summary_path}")
    print(f"Saved relative momentum holdout validation markdown to: {markdown_path}")

    return {
        "validation_report": validation_report,
        "summary": summary,
    }