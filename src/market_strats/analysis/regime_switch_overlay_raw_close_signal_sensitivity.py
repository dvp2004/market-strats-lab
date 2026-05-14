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


def _find_raw_close_frame(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
    column_candidates: list[str],
) -> pd.DataFrame:
    ticker = ticker.upper()

    if ticker not in ticker_outputs:
        raise ValueError(f"Ticker {ticker} not found in ticker outputs")

    ticker_output = ticker_outputs[ticker]

    candidate_frames: list[pd.DataFrame] = []

    for value in ticker_output.values():
        if isinstance(value, pd.DataFrame):
            candidate_frames.append(value)

    strategy_results = ticker_output.get("strategy_results", {})

    if isinstance(strategy_results, dict):
        for value in strategy_results.values():
            if isinstance(value, pd.DataFrame):
                candidate_frames.append(value)

    for frame in candidate_frames:
        if "date" not in frame.columns:
            continue

        for column in column_candidates:
            if column in frame.columns:
                output = frame[["date", column]].copy()
                output["date"] = pd.to_datetime(output["date"])
                output = output.sort_values("date").drop_duplicates("date")
                output = output.rename(columns={column: "raw_signal_close"})
                output["raw_signal_close"] = output["raw_signal_close"].astype(float)
                return output.reset_index(drop=True)

    searched_columns = sorted(
        {
            column
            for frame in candidate_frames
            for column in getattr(frame, "columns", [])
        }
    )

    raise ValueError(
        f"Could not find a raw close column for {ticker}. Tried: "
        f"{column_candidates}. Available dataframe columns seen: {searched_columns}. "
        f"If raw close is not preserved in ticker_outputs, update the data/strategy "
        f"pipeline to retain a raw close column named 'close' or 'raw_close'."
    )


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


def _attach_raw_signal_close(
    offensive_result: pd.DataFrame,
    raw_close_frame: pd.DataFrame,
) -> pd.DataFrame:
    offensive = offensive_result.copy()
    offensive["date"] = pd.to_datetime(offensive["date"])

    merged = offensive.merge(raw_close_frame, on="date", how="left")

    missing_count = int(merged["raw_signal_close"].isna().sum())

    if missing_count:
        raise ValueError(
            f"raw_signal_close missing for {missing_count} offensive dates. "
            f"Check whether raw close data and strategy dates are aligned."
        )

    return merged.reset_index(drop=True)


def _create_raw_close_unavailable_report(
    config: dict,
    reason: str,
) -> pd.DataFrame:
    sensitivity_config = config.get(
        "regime_switch_overlay_raw_close_signal_sensitivity",
        {},
    )
    overlay_config = config.get("regime_switch_overlay", {})

    overlay_name = str(overlay_config.get("name", "Regime Switch Overlay"))
    reference_end_date = str(sensitivity_config.get("reference_end_date", ""))
    holdout_start_date = str(sensitivity_config.get("holdout_start_date", ""))

    rows = [
        {
            "period": "full",
            "signal_type": "raw_close_signal_unavailable",
            "strategy": overlay_name,
            "available": False,
            "reason": reason,
            "start_date": "",
            "end_date": "",
            "end_value": "",
            "cagr_pct": "",
            "calmar": "",
            "volatility_pct": "",
            "sharpe": "",
            "sortino": "",
            "max_drawdown_pct": "",
            "worst_month_pct": "",
            "exposure_time_pct": "",
            "trade_count": "",
        },
        {
            "period": "reference",
            "signal_type": "raw_close_signal_unavailable",
            "strategy": overlay_name,
            "available": False,
            "reason": (
                f"Raw close unavailable. Reference end date was {reference_end_date}. "
                f"{reason}"
            ),
            "start_date": "",
            "end_date": "",
            "end_value": "",
            "cagr_pct": "",
            "calmar": "",
            "volatility_pct": "",
            "sharpe": "",
            "sortino": "",
            "max_drawdown_pct": "",
            "worst_month_pct": "",
            "exposure_time_pct": "",
            "trade_count": "",
        },
        {
            "period": "holdout",
            "signal_type": "raw_close_signal_unavailable",
            "strategy": overlay_name,
            "available": False,
            "reason": (
                f"Raw close unavailable. Holdout start date was {holdout_start_date}. "
                f"{reason}"
            ),
            "start_date": "",
            "end_date": "",
            "end_value": "",
            "cagr_pct": "",
            "calmar": "",
            "volatility_pct": "",
            "sharpe": "",
            "sortino": "",
            "max_drawdown_pct": "",
            "worst_month_pct": "",
            "exposure_time_pct": "",
            "trade_count": "",
        },
    ]

    return pd.DataFrame(rows)

def create_regime_switch_overlay_raw_close_signal_sensitivity(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    sensitivity_config = config.get(
        "regime_switch_overlay_raw_close_signal_sensitivity",
        {},
    )

    if not sensitivity_config.get("enabled", False):
        return pd.DataFrame()

    overlay_config = config.get("regime_switch_overlay", {})

    if not overlay_config.get("enabled", False):
        return pd.DataFrame()

    benchmark_ticker = str(
        sensitivity_config.get(
            "benchmark_ticker",
            overlay_config.get("benchmark_ticker", "SPY"),
        )
    ).upper()

    column_candidates = [
        str(column)
        for column in sensitivity_config.get(
            "raw_close_column_candidates",
            ["raw_close", "close", "Close"],
        )
    ]

    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    try:
        raw_close_frame = _find_raw_close_frame(
            ticker_outputs=ticker_outputs,
            ticker=benchmark_ticker,
            column_candidates=column_candidates,
        )
    except ValueError as error:
        return _create_raw_close_unavailable_report(
            config=config,
            reason=str(error),
        )

    offensive_raw_signal = _attach_raw_signal_close(
        offensive_result=offensive_result,
        raw_close_frame=raw_close_frame,
    )

    overlay_name = str(overlay_config.get("name", "Regime Switch Overlay"))
    initial_capital = float(config["initial_capital"])
    reference_end_date = str(sensitivity_config["reference_end_date"])
    holdout_start_date = str(sensitivity_config["holdout_start_date"])

    scenarios = [
        {
            "signal_type": "adjusted_close_signal",
            "offensive_result": offensive_result,
            "signal_price_column": "adj_close",
        },
        {
            "signal_type": "raw_close_signal",
            "offensive_result": offensive_raw_signal,
            "signal_price_column": "raw_signal_close",
        },
    ]

    rows: list[dict] = []

    for scenario in scenarios:
        overlay_result = run_spy_trend_regime_switch_overlay(
            offensive_result=scenario["offensive_result"],
            defensive_result=defensive_result,
            initial_capital=initial_capital,
            trend_sma_days=int(overlay_config.get("trend_sma_days", 200)),
            slippage_bps=float(config.get("slippage_bps", 0.0)),
            confirmation_days=int(overlay_config.get("confirmation_days", 1)),
            signal_price_column=str(scenario["signal_price_column"]),
        )

        strategy_name = f"{overlay_name} - {scenario['signal_type']}"

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
                    "signal_type": scenario["signal_type"],
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


def create_regime_switch_overlay_raw_close_signal_sensitivity_summary(
    sensitivity: pd.DataFrame,
) -> pd.DataFrame:
    if sensitivity.empty:
        return pd.DataFrame()

    if "available" in sensitivity.columns:
        available_values = sensitivity["available"].astype(str).str.lower()
        if (available_values == "false").all():
            return pd.DataFrame(
                [
                    {
                        "status": "unavailable",
                        "reason": sensitivity["reason"].iloc[0]
                        if "reason" in sensitivity.columns
                        else "Raw close data unavailable.",
                    }
                ]
            )

    rows: list[dict] = []

    for period, period_df in sensitivity.groupby("period"):
        adjusted = period_df[
            period_df["signal_type"] == "adjusted_close_signal"
        ]
        raw = period_df[period_df["signal_type"] == "raw_close_signal"]

        if adjusted.empty or raw.empty:
            continue

        adjusted_row = adjusted.iloc[0]
        raw_row = raw.iloc[0]

        rows.append(
            {
                "period": period,
                "adjusted_signal_cagr_pct": adjusted_row["cagr_pct"],
                "raw_signal_cagr_pct": raw_row["cagr_pct"],
                "raw_minus_adjusted_cagr_pct_points": round(
                    float(raw_row["cagr_pct"]) - float(adjusted_row["cagr_pct"]),
                    3,
                ),
                "adjusted_signal_calmar": adjusted_row["calmar"],
                "raw_signal_calmar": raw_row["calmar"],
                "raw_minus_adjusted_calmar": round(
                    float(raw_row["calmar"]) - float(adjusted_row["calmar"]),
                    3,
                ),
                "adjusted_signal_max_drawdown_pct": adjusted_row[
                    "max_drawdown_pct"
                ],
                "raw_signal_max_drawdown_pct": raw_row["max_drawdown_pct"],
                "raw_minus_adjusted_drawdown_pct_points": round(
                    float(raw_row["max_drawdown_pct"])
                    - float(adjusted_row["max_drawdown_pct"]),
                    3,
                ),
                "adjusted_signal_end_value": adjusted_row["end_value"],
                "raw_signal_end_value": raw_row["end_value"],
                "raw_minus_adjusted_end_value": round(
                    float(raw_row["end_value"]) - float(adjusted_row["end_value"]),
                    2,
                ),
                "adjusted_signal_trade_count": adjusted_row["trade_count"],
                "raw_signal_trade_count": raw_row["trade_count"],
            }
        )

    summary = pd.DataFrame(rows)

    numeric_columns = summary.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        summary[column] = summary[column].round(3)

    return summary.reset_index(drop=True)


def write_regime_switch_overlay_raw_close_signal_sensitivity_markdown(
    sensitivity: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if sensitivity.empty:
        output_path.write_text(
            "# Regime Switch Overlay Raw-Close Signal Sensitivity\n\nNo sensitivity data available.\n",
            encoding="utf-8",
        )
        return output_path

    sensitivity_table = sensitivity.to_markdown(index=False)
    summary_table = summary.to_markdown(index=False) if not summary.empty else ""

    content = f"""# Regime Switch Overlay Raw-Close Signal Sensitivity

This report tests whether the 3D confirmed regime-switch overlay depends on using adjusted close for the SPY trend signal.

## Tested Signal Types

| Signal Type | Meaning |
|---|---|
| adjusted_close_signal | Existing baseline. SPY trend signal uses adjusted close. |
| raw_close_signal | Robustness test. SPY trend signal uses raw close while returns remain adjusted. |

## Summary

{summary_table}

## Full Sensitivity Table

{sensitivity_table}

## Interpretation Notes

- This is a robustness check, not a new strategy.
- Returns are still calculated from the normal strategy return stream.
- Only the SPY trend signal price is changed.
- If raw-close signal results are close to adjusted-close signal results, the 3D overlay is less likely to depend on adjusted-close artefacts.
- If raw-close signal performance collapses, the adjusted-close signal may be overstating robustness.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_raw_close_signal_sensitivity(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    sensitivity = create_regime_switch_overlay_raw_close_signal_sensitivity(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    if sensitivity.empty:
        return {
            "sensitivity": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    summary = create_regime_switch_overlay_raw_close_signal_sensitivity_summary(
        sensitivity
    )

    sensitivity_path = (
        reports_dir / "regime_switch_overlay_raw_close_signal_sensitivity.csv"
    )
    summary_path = (
        reports_dir
        / "regime_switch_overlay_raw_close_signal_sensitivity_summary.csv"
    )
    markdown_path = (
        reports_dir / "regime_switch_overlay_raw_close_signal_sensitivity.md"
    )

    sensitivity.to_csv(sensitivity_path, index=False)
    summary.to_csv(summary_path, index=False)

    write_regime_switch_overlay_raw_close_signal_sensitivity_markdown(
        sensitivity=sensitivity,
        summary=summary,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay raw-close signal sensitivity:")
    print(sensitivity.to_string(index=False))

    print("\nRegime switch overlay raw-close signal sensitivity summary:")
    print(summary.to_string(index=False))

    print(
        "\nSaved regime switch overlay raw-close signal sensitivity to: "
        f"{sensitivity_path}"
    )
    print(
        "Saved regime switch overlay raw-close signal sensitivity summary to: "
        f"{summary_path}"
    )
    print(
        "Saved regime switch overlay raw-close signal sensitivity markdown to: "
        f"{markdown_path}"
    )

    return {
        "sensitivity": sensitivity,
        "summary": summary,
    }