from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.strategies.fixed_weight_portfolio import (
    rebase_strategy_result_to_dates,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
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
            "period": "full",
            "start_date": None,
            "end_date": None,
        },
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


def _build_overlay_inputs(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    overlay_config = config.get("regime_switch_overlay", {})

    defensive_allocator_name = str(overlay_config["defensive_allocator_name"])

    if defensive_allocator_name not in relative_momentum_outputs:
        available = sorted(relative_momentum_outputs.keys())
        raise ValueError(
            f"Defensive allocator '{defensive_allocator_name}' not found. "
            f"Available: {available}"
        )

    defensive_result = relative_momentum_outputs[defensive_allocator_name][
        "allocator_result"
    ]

    common_dates = list(pd.to_datetime(defensive_result["date"]))

    offensive_result = rebase_strategy_result_to_dates(
        result=_get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=str(overlay_config.get("benchmark_ticker", "SPY")).upper(),
            strategy=str(overlay_config.get("offensive_strategy", "Buy and Hold")),
        ),
        dates=common_dates,
        initial_capital=float(config["initial_capital"]),
    )

    defensive_result = rebase_strategy_result_to_dates(
        result=defensive_result,
        dates=common_dates,
        initial_capital=float(config["initial_capital"]),
    )

    return offensive_result, defensive_result


def create_regime_switch_overlay_slippage_sensitivity(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    sensitivity_config = config.get("regime_switch_overlay_slippage_sensitivity", {})

    if not sensitivity_config.get("enabled", False):
        return pd.DataFrame()

    overlay_config = config.get("regime_switch_overlay", {})

    if not overlay_config.get("enabled", False):
        return pd.DataFrame()

    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    overlay_name = str(overlay_config.get("name", "Regime Switch Overlay"))
    initial_capital = float(config["initial_capital"])
    reference_end_date = str(sensitivity_config["reference_end_date"])
    holdout_start_date = str(sensitivity_config["holdout_start_date"])

    slippage_values = [
        float(value)
        for value in sensitivity_config.get("slippage_bps_values", [0, 5, 10, 25, 50])
    ]

    rows: list[dict] = []

    for slippage_bps in slippage_values:
        overlay_result = run_spy_trend_regime_switch_overlay(
            offensive_result=offensive_result,
            defensive_result=defensive_result,
            initial_capital=initial_capital,
            trend_sma_days=int(overlay_config.get("trend_sma_days", 200)),
            slippage_bps=slippage_bps,
            confirmation_days=int(overlay_config.get("confirmation_days", 1)),
        )

        strategy_name = f"{overlay_name} @ {slippage_bps:g} bps"

        for period in _period_definitions(reference_end_date, holdout_start_date):
            sliced = _slice_and_rebase_result(
                result=overlay_result,
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
                    "slippage_bps": slippage_bps,
                    "strategy": overlay_name,
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


def create_regime_switch_overlay_slippage_sensitivity_summary(
    sensitivity: pd.DataFrame,
    baseline_slippage_bps: float = 5.0,
) -> pd.DataFrame:
    if sensitivity.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for period, period_df in sensitivity.groupby("period"):
        period_df = period_df.copy()

        baseline = period_df[
            period_df["slippage_bps"].astype(float) == float(baseline_slippage_bps)
        ]

        if baseline.empty:
            baseline = period_df.sort_values("slippage_bps").iloc[[0]]

        baseline_row = baseline.iloc[0]
        worst_slippage_row = period_df.sort_values("slippage_bps").iloc[-1]

        rows.append(
            {
                "period": period,
                "baseline_slippage_bps": float(baseline_row["slippage_bps"]),
                "highest_tested_slippage_bps": float(
                    worst_slippage_row["slippage_bps"]
                ),
                "baseline_cagr_pct": baseline_row["cagr_pct"],
                "highest_slippage_cagr_pct": worst_slippage_row["cagr_pct"],
                "cagr_drag_pct_points": round(
                    float(worst_slippage_row["cagr_pct"])
                    - float(baseline_row["cagr_pct"]),
                    3,
                ),
                "baseline_calmar": baseline_row["calmar"],
                "highest_slippage_calmar": worst_slippage_row["calmar"],
                "calmar_delta": round(
                    float(worst_slippage_row["calmar"])
                    - float(baseline_row["calmar"]),
                    3,
                ),
                "baseline_max_drawdown_pct": baseline_row["max_drawdown_pct"],
                "highest_slippage_max_drawdown_pct": worst_slippage_row[
                    "max_drawdown_pct"
                ],
                "drawdown_delta_pct_points": round(
                    float(worst_slippage_row["max_drawdown_pct"])
                    - float(baseline_row["max_drawdown_pct"]),
                    3,
                ),
                "baseline_end_value": baseline_row["end_value"],
                "highest_slippage_end_value": worst_slippage_row["end_value"],
                "end_value_delta": round(
                    float(worst_slippage_row["end_value"])
                    - float(baseline_row["end_value"]),
                    2,
                ),
            }
        )

    summary = pd.DataFrame(rows)

    numeric_columns = summary.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        summary[column] = summary[column].round(3)

    return summary.reset_index(drop=True)


def write_regime_switch_overlay_slippage_sensitivity_markdown(
    sensitivity: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if sensitivity.empty:
        output_path.write_text(
            "# Regime Switch Overlay Slippage Sensitivity\n\nNo sensitivity data available.\n",
            encoding="utf-8",
        )
        return output_path

    sensitivity_table = sensitivity.to_markdown(index=False)
    summary_table = summary.to_markdown(index=False) if not summary.empty else ""

    content = f"""# Regime Switch Overlay Slippage Sensitivity

This report tests whether the 3D confirmed regime-switch overlay is robust to higher assumed execution friction.

The tested slippage values are applied directly inside the overlay switch logic.

## Summary

{summary_table}

## Full Sensitivity Table

{sensitivity_table}

## Interpretation Notes

- The default project assumption is 5 bps slippage.
- This report checks whether the 3D overlay remains robust at higher slippage assumptions.
- If 25 bps or 50 bps materially destroys the result, the overlay is more execution-sensitive than the headline metrics suggest.
- This is a robustness check, not a new strategy branch.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_slippage_sensitivity(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    sensitivity = create_regime_switch_overlay_slippage_sensitivity(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    if sensitivity.empty:
        return {
            "sensitivity": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    summary = create_regime_switch_overlay_slippage_sensitivity_summary(
        sensitivity=sensitivity,
        baseline_slippage_bps=float(config.get("slippage_bps", 5.0)),
    )

    sensitivity_path = reports_dir / "regime_switch_overlay_slippage_sensitivity.csv"
    summary_path = reports_dir / "regime_switch_overlay_slippage_sensitivity_summary.csv"
    markdown_path = reports_dir / "regime_switch_overlay_slippage_sensitivity.md"

    sensitivity.to_csv(sensitivity_path, index=False)
    summary.to_csv(summary_path, index=False)

    write_regime_switch_overlay_slippage_sensitivity_markdown(
        sensitivity=sensitivity,
        summary=summary,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay slippage sensitivity:")
    print(sensitivity.to_string(index=False))

    print("\nRegime switch overlay slippage sensitivity summary:")
    print(summary.to_string(index=False))

    print(f"\nSaved regime switch overlay slippage sensitivity to: {sensitivity_path}")
    print(f"Saved regime switch overlay slippage sensitivity summary to: {summary_path}")
    print(f"Saved regime switch overlay slippage sensitivity markdown to: {markdown_path}")

    return {
        "sensitivity": sensitivity,
        "summary": summary,
    }