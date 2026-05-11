from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.strategies.fixed_weight_portfolio import (
    rebase_strategy_result_to_dates,
)


TRADING_DAYS_PER_YEAR = 252


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


def _prepare_result(result: pd.DataFrame) -> pd.DataFrame:
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
    df["strategy_return"] = df["strategy_return"].astype(float)

    return df


def _create_spy_regime_frame(
    spy_result: pd.DataFrame,
    trend_sma_days: int,
    momentum_lookback_days: int,
) -> pd.DataFrame:
    if trend_sma_days <= 0:
        raise ValueError("trend_sma_days must be positive")

    if momentum_lookback_days <= 0:
        raise ValueError("momentum_lookback_days must be positive")

    spy = _prepare_result(spy_result)
    spy = spy[["date", "adj_close", "strategy_return"]].copy()
    spy["adj_close"] = spy["adj_close"].astype(float)

    spy["spy_sma"] = spy["adj_close"].rolling(trend_sma_days).mean()
    spy["spy_above_sma"] = spy["adj_close"] > spy["spy_sma"]

    spy["spy_trailing_return"] = (
        spy["adj_close"] / spy["adj_close"].shift(momentum_lookback_days)
    ) - 1.0
    spy["spy_positive_momentum"] = spy["spy_trailing_return"] > 0.0

    spy["spy_peak"] = spy["adj_close"].cummax()
    spy["spy_drawdown_pct"] = (spy["adj_close"] / spy["spy_peak"] - 1.0) * 100.0

    spy["trend_regime"] = np.where(
        spy["spy_above_sma"],
        "SPY above 200D trend",
        "SPY below 200D trend",
    )

    spy["momentum_regime"] = np.where(
        spy["spy_positive_momentum"],
        "SPY positive 12M momentum",
        "SPY negative 12M momentum",
    )

    spy["drawdown_regime"] = pd.cut(
        spy["spy_drawdown_pct"],
        bins=[-np.inf, -20.0, -10.0, 0.0],
        labels=[
            "SPY bear drawdown below -20%",
            "SPY correction -10% to -20%",
            "SPY near highs 0% to -10%",
        ],
        include_lowest=True,
    ).astype(str)

    spy.loc[spy["spy_sma"].isna(), "trend_regime"] = "SPY trend warmup"
    spy.loc[
        spy["spy_trailing_return"].isna(),
        "momentum_regime",
    ] = "SPY momentum warmup"

    return spy[
        [
            "date",
            "strategy_return",
            "trend_regime",
            "momentum_regime",
            "drawdown_regime",
            "spy_drawdown_pct",
        ]
    ].rename(columns={"strategy_return": "spy_daily_return"})


def _calculate_conditional_metrics(
    strategy_name: str,
    strategy_result: pd.DataFrame,
    regime_frame: pd.DataFrame,
    regime_dimension: str,
    regime_value: str,
) -> dict:
    result = _prepare_result(strategy_result)

    merged = result.merge(
        regime_frame[["date", regime_dimension]],
        on="date",
        how="inner",
    )

    subset = merged[merged[regime_dimension] == regime_value].copy()

    if subset.empty:
        return {
            "regime_dimension": regime_dimension,
            "regime_value": regime_value,
            "strategy": strategy_name,
            "days": 0,
            "pct_days": 0.0,
            "conditional_total_return_pct": np.nan,
            "conditional_annualized_return_pct": np.nan,
            "conditional_volatility_pct": np.nan,
            "conditional_sharpe": np.nan,
            "avg_daily_return_pct": np.nan,
            "worst_daily_return_pct": np.nan,
            "avg_exposure_pct": np.nan,
            "avg_cash_pct": np.nan,
            "avg_turnover_pct": np.nan,
        }

    returns = subset["strategy_return"].astype(float)
    days = len(subset)
    total_days = len(merged)

    total_return = (1.0 + returns).prod() - 1.0

    if days > 0:
        annualized_return = ((1.0 + total_return) ** (TRADING_DAYS_PER_YEAR / days)) - 1.0
    else:
        annualized_return = np.nan

    volatility = returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR)

    if volatility == 0 or np.isnan(volatility):
        sharpe = np.nan
    else:
        sharpe = (returns.mean() * TRADING_DAYS_PER_YEAR) / volatility

    return {
        "regime_dimension": regime_dimension,
        "regime_value": regime_value,
        "strategy": strategy_name,
        "days": days,
        "pct_days": (days / total_days) * 100.0 if total_days else 0.0,
        "conditional_total_return_pct": total_return * 100.0,
        "conditional_annualized_return_pct": annualized_return * 100.0,
        "conditional_volatility_pct": volatility * 100.0,
        "conditional_sharpe": sharpe,
        "avg_daily_return_pct": returns.mean() * 100.0,
        "worst_daily_return_pct": returns.min() * 100.0,
        "avg_exposure_pct": subset["position"].astype(float).mean() * 100.0,
        "avg_cash_pct": subset["cash_position"].astype(float).mean() * 100.0,
        "avg_turnover_pct": subset["turnover"].astype(float).mean() * 100.0,
    }


def create_relative_momentum_regime_diagnostic(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    diagnostic_config = config.get("relative_momentum_regime_diagnostic", {})

    if not diagnostic_config.get("enabled", False):
        return pd.DataFrame()

    if not relative_momentum_outputs:
        return pd.DataFrame()

    benchmark_ticker = str(diagnostic_config.get("benchmark_ticker", "SPY")).upper()
    benchmark_strategy = str(diagnostic_config.get("benchmark_strategy", "Buy and Hold"))
    benchmark_momentum_strategy = str(
        diagnostic_config.get(
            "benchmark_momentum_strategy",
            "12-Month Absolute Momentum",
        )
    )

    trend_sma_days = int(diagnostic_config.get("trend_sma_days", 200))
    momentum_lookback_days = int(diagnostic_config.get("momentum_lookback_days", 252))

    first_allocator = next(iter(relative_momentum_outputs.values()))[
        "allocator_result"
    ]
    common_dates = list(pd.to_datetime(first_allocator["date"]))

    spy_buy_hold = rebase_strategy_result_to_dates(
        result=_get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=benchmark_ticker,
            strategy=benchmark_strategy,
        ),
        dates=common_dates,
        initial_capital=float(config["initial_capital"]),
    )

    spy_momentum = rebase_strategy_result_to_dates(
        result=_get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=benchmark_ticker,
            strategy=benchmark_momentum_strategy,
        ),
        dates=common_dates,
        initial_capital=float(config["initial_capital"]),
    )

    regime_frame = _create_spy_regime_frame(
        spy_result=spy_buy_hold,
        trend_sma_days=trend_sma_days,
        momentum_lookback_days=momentum_lookback_days,
    )

    comparison_results: dict[str, pd.DataFrame] = {}

    for strategy_name, output in relative_momentum_outputs.items():
        result = output.get("allocator_result")

        if result is None or result.empty:
            continue

        comparison_results[strategy_name] = result

    comparison_results["SPY Buy and Hold"] = spy_buy_hold
    comparison_results["SPY 12-Month Absolute Momentum"] = spy_momentum

    rows: list[dict] = []

    regime_dimensions = [
        "trend_regime",
        "momentum_regime",
        "drawdown_regime",
    ]

    for regime_dimension in regime_dimensions:
        regime_values = sorted(regime_frame[regime_dimension].dropna().unique())

        for regime_value in regime_values:
            for strategy_name, result in comparison_results.items():
                rows.append(
                    _calculate_conditional_metrics(
                        strategy_name=strategy_name,
                        strategy_result=result,
                        regime_frame=regime_frame,
                        regime_dimension=regime_dimension,
                        regime_value=regime_value,
                    )
                )

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.reset_index(drop=True)


def create_relative_momentum_regime_summary(
    regime_diagnostic: pd.DataFrame,
) -> pd.DataFrame:
    if regime_diagnostic.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for (regime_dimension, regime_value), group in regime_diagnostic.groupby(
        ["regime_dimension", "regime_value"]
    ):
        valid = group[group["days"] > 0].copy()

        if valid.empty:
            continue

        best_return = valid.sort_values(
            "conditional_annualized_return_pct",
            ascending=False,
        ).iloc[0]
        best_sharpe = valid.sort_values(
            "conditional_sharpe",
            ascending=False,
        ).iloc[0]
        lowest_vol = valid.sort_values(
            "conditional_volatility_pct",
            ascending=True,
        ).iloc[0]
        highest_exposure = valid.sort_values(
            "avg_exposure_pct",
            ascending=False,
        ).iloc[0]

        spy_12m = valid[valid["strategy"] == "SPY 12-Month Absolute Momentum"]

        if spy_12m.empty:
            spy_12m_return = np.nan
            spy_12m_sharpe = np.nan
        else:
            spy_12m_row = spy_12m.iloc[0]
            spy_12m_return = spy_12m_row["conditional_annualized_return_pct"]
            spy_12m_sharpe = spy_12m_row["conditional_sharpe"]

        rows.append(
            {
                "regime_dimension": regime_dimension,
                "regime_value": regime_value,
                "days": int(valid["days"].iloc[0]),
                "best_return_strategy": best_return["strategy"],
                "best_return_pct": best_return["conditional_annualized_return_pct"],
                "best_sharpe_strategy": best_sharpe["strategy"],
                "best_sharpe": best_sharpe["conditional_sharpe"],
                "lowest_volatility_strategy": lowest_vol["strategy"],
                "lowest_volatility_pct": lowest_vol["conditional_volatility_pct"],
                "highest_exposure_strategy": highest_exposure["strategy"],
                "highest_exposure_pct": highest_exposure["avg_exposure_pct"],
                "spy_12m_return_pct": spy_12m_return,
                "spy_12m_sharpe": spy_12m_sharpe,
            }
        )

    summary = pd.DataFrame(rows)

    numeric_columns = summary.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        summary[column] = summary[column].round(3)

    return summary.reset_index(drop=True)


def write_relative_momentum_regime_diagnostic_markdown(
    regime_diagnostic: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if regime_diagnostic.empty:
        output_path.write_text(
            "# Relative Momentum Regime Diagnostic\n\nNo diagnostic data available.\n",
            encoding="utf-8",
        )
        return output_path

    diagnostic_table = regime_diagnostic.to_markdown(index=False)
    summary_table = summary.to_markdown(index=False) if not summary.empty else ""

    content = f"""# Relative Momentum Regime Diagnostic

This report analyses when the Phase 2 relative momentum allocators work and when they fail.

The regimes are defined using SPY behaviour:

- SPY above/below 200D trend.
- SPY positive/negative 12M momentum.
- SPY drawdown buckets.

## Summary

{summary_table}

## Full Diagnostic Table

{diagnostic_table}

## Interpretation Notes

- Conditional annualised returns are computed over non-contiguous regime days.
- These are diagnostic statistics, not standalone investable backtests.
- The purpose is to identify where allocators beat or lag SPY benchmarks.
- If the allocator mainly wins when SPY is weak and loses when SPY is strong, the next research question is regime selection.
- Do not use this report to optimise regime definitions after the fact.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_relative_momentum_regime_diagnostic(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    diagnostic = create_relative_momentum_regime_diagnostic(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    if diagnostic.empty:
        return {
            "diagnostic": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    summary = create_relative_momentum_regime_summary(diagnostic)

    diagnostic_path = reports_dir / "relative_momentum_regime_diagnostic.csv"
    summary_path = reports_dir / "relative_momentum_regime_summary.csv"
    markdown_path = reports_dir / "relative_momentum_regime_diagnostic.md"

    diagnostic.to_csv(diagnostic_path, index=False)
    summary.to_csv(summary_path, index=False)

    write_relative_momentum_regime_diagnostic_markdown(
        regime_diagnostic=diagnostic,
        summary=summary,
        output_path=markdown_path,
    )

    print("\nRelative momentum regime diagnostic:")
    print(diagnostic.to_string(index=False))

    print("\nRelative momentum regime summary:")
    print(summary.to_string(index=False))

    print(f"\nSaved relative momentum regime diagnostic to: {diagnostic_path}")
    print(f"Saved relative momentum regime summary to: {summary_path}")
    print(f"Saved relative momentum regime markdown to: {markdown_path}")

    return {
        "diagnostic": diagnostic,
        "summary": summary,
    }