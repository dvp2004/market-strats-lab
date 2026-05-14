from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.metrics import calculate_metrics


TRADING_DAYS_PER_YEAR = 252


def _annual_yield_to_daily_return(annual_yield_pct: float) -> float:
    annual_rate = annual_yield_pct / 100.0
    return (1.0 + annual_rate) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0


def _prepare_overlay_result(overlay_result: pd.DataFrame) -> pd.DataFrame:
    required_columns = {
        "date",
        "adj_close",
        "strategy_return",
        "equity",
        "position",
        "cash_position",
        "turnover",
    }

    missing_columns = required_columns - set(overlay_result.columns)

    if missing_columns:
        raise ValueError(f"overlay result missing columns: {sorted(missing_columns)}")

    df = overlay_result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    for column in [
        "adj_close",
        "strategy_return",
        "equity",
        "position",
        "cash_position",
        "turnover",
    ]:
        df[column] = df[column].astype(float)

    return df


def _slice_and_rebase_result(
    result: pd.DataFrame,
    start_date: str | pd.Timestamp | None,
    end_date: str | pd.Timestamp | None,
    initial_capital: float,
) -> pd.DataFrame:
    df = _prepare_overlay_result(result)

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


def _apply_cash_yield_scenario(
    overlay_result: pd.DataFrame,
    initial_capital: float,
    baseline_cash_annual_yield_pct: float,
    scenario_cash_annual_yield_pct: float,
) -> pd.DataFrame:
    df = _prepare_overlay_result(overlay_result)

    baseline_daily_cash_return = _annual_yield_to_daily_return(
        baseline_cash_annual_yield_pct
    )
    scenario_daily_cash_return = _annual_yield_to_daily_return(
        scenario_cash_annual_yield_pct
    )

    cash_return_delta = scenario_daily_cash_return - baseline_daily_cash_return

    df["cash_return_delta"] = cash_return_delta
    df["cash_return_adjustment"] = df["cash_position"] * cash_return_delta

    df["strategy_return"] = (
        df["strategy_return"].astype(float) + df["cash_return_adjustment"]
    )

    df.loc[df.index[0], "strategy_return"] = 0.0
    df["equity"] = initial_capital * (1.0 + df["strategy_return"]).cumprod()
    df["adj_close"] = df["equity"]

    df["scenario_cash_annual_yield_pct"] = scenario_cash_annual_yield_pct
    df["baseline_cash_annual_yield_pct"] = baseline_cash_annual_yield_pct

    return df.reset_index(drop=True)


def create_regime_switch_overlay_cash_sensitivity(
    overlay_outputs: dict[str, pd.DataFrame],
    config: dict,
) -> pd.DataFrame:
    sensitivity_config = config.get("regime_switch_overlay_cash_sensitivity", {})

    if not sensitivity_config.get("enabled", False):
        return pd.DataFrame()

    overlay_config = config.get("regime_switch_overlay", {})

    if not overlay_config.get("enabled", False):
        return pd.DataFrame()

    overlay_result = overlay_outputs.get("overlay_result")

    if overlay_result is None or overlay_result.empty:
        return pd.DataFrame()

    initial_capital = float(config["initial_capital"])
    overlay_name = str(overlay_config.get("name", "Regime Switch Overlay"))

    baseline_cash_annual_yield_pct = float(
        sensitivity_config.get("baseline_cash_annual_yield_pct", 4.0)
    )

    cash_yield_multipliers = [
        float(value)
        for value in sensitivity_config.get("cash_yield_multipliers", [0.0, 0.5, 1.0])
    ]

    reference_end_date = str(sensitivity_config["reference_end_date"])
    holdout_start_date = str(sensitivity_config["holdout_start_date"])

    rows: list[dict] = []

    for multiplier in cash_yield_multipliers:
        scenario_cash_annual_yield_pct = baseline_cash_annual_yield_pct * multiplier

        scenario_result = _apply_cash_yield_scenario(
            overlay_result=overlay_result,
            initial_capital=initial_capital,
            baseline_cash_annual_yield_pct=baseline_cash_annual_yield_pct,
            scenario_cash_annual_yield_pct=scenario_cash_annual_yield_pct,
        )

        strategy_name = (
            f"{overlay_name} @ {scenario_cash_annual_yield_pct:g}% cash yield"
        )

        for period in _period_definitions(reference_end_date, holdout_start_date):
            sliced = _slice_and_rebase_result(
                result=scenario_result,
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
                    "cash_yield_multiplier": multiplier,
                    "scenario_cash_annual_yield_pct": scenario_cash_annual_yield_pct,
                    "baseline_cash_annual_yield_pct": baseline_cash_annual_yield_pct,
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
                    "avg_cash_position_pct": (
                        sliced["cash_position"].astype(float).mean() * 100.0
                    ),
                }
            )

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.reset_index(drop=True)


def create_regime_switch_overlay_cash_sensitivity_summary(
    sensitivity: pd.DataFrame,
    baseline_multiplier: float = 1.0,
) -> pd.DataFrame:
    if sensitivity.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for period, period_df in sensitivity.groupby("period"):
        period_df = period_df.copy()

        baseline = period_df[
            np.isclose(
                period_df["cash_yield_multiplier"].astype(float),
                float(baseline_multiplier),
            )
        ]

        if baseline.empty:
            baseline = period_df.sort_values("cash_yield_multiplier").iloc[[0]]

        zero_cash = period_df[
            np.isclose(period_df["cash_yield_multiplier"].astype(float), 0.0)
        ]

        if zero_cash.empty:
            zero_cash = period_df.sort_values("cash_yield_multiplier").iloc[[0]]

        baseline_row = baseline.iloc[0]
        zero_cash_row = zero_cash.iloc[0]

        rows.append(
            {
                "period": period,
                "baseline_cash_yield_pct": baseline_row[
                    "scenario_cash_annual_yield_pct"
                ],
                "zero_cash_yield_pct": zero_cash_row[
                    "scenario_cash_annual_yield_pct"
                ],
                "baseline_cagr_pct": baseline_row["cagr_pct"],
                "zero_cash_cagr_pct": zero_cash_row["cagr_pct"],
                "zero_cash_cagr_drag_pct_points": round(
                    float(zero_cash_row["cagr_pct"])
                    - float(baseline_row["cagr_pct"]),
                    3,
                ),
                "baseline_calmar": baseline_row["calmar"],
                "zero_cash_calmar": zero_cash_row["calmar"],
                "zero_cash_calmar_delta": round(
                    float(zero_cash_row["calmar"]) - float(baseline_row["calmar"]),
                    3,
                ),
                "baseline_max_drawdown_pct": baseline_row["max_drawdown_pct"],
                "zero_cash_max_drawdown_pct": zero_cash_row["max_drawdown_pct"],
                "zero_cash_drawdown_delta_pct_points": round(
                    float(zero_cash_row["max_drawdown_pct"])
                    - float(baseline_row["max_drawdown_pct"]),
                    3,
                ),
                "baseline_end_value": baseline_row["end_value"],
                "zero_cash_end_value": zero_cash_row["end_value"],
                "zero_cash_end_value_delta": round(
                    float(zero_cash_row["end_value"])
                    - float(baseline_row["end_value"]),
                    2,
                ),
                "avg_cash_position_pct": baseline_row["avg_cash_position_pct"],
            }
        )

    summary = pd.DataFrame(rows)

    numeric_columns = summary.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        summary[column] = summary[column].round(3)

    return summary.reset_index(drop=True)


def write_regime_switch_overlay_cash_sensitivity_markdown(
    sensitivity: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if sensitivity.empty:
        output_path.write_text(
            "# Regime Switch Overlay Cash Sensitivity\n\nNo sensitivity data available.\n",
            encoding="utf-8",
        )
        return output_path

    sensitivity_table = sensitivity.to_markdown(index=False)
    summary_table = summary.to_markdown(index=False) if not summary.empty else ""

    content = f"""# Regime Switch Overlay Cash Sensitivity

This report tests whether the 3D confirmed regime-switch overlay is dependent on the assumed cash yield.

## Summary

{summary_table}

## Full Sensitivity Table

{sensitivity_table}

## Interpretation Notes

- The baseline cash annual yield is configured in `configs/spy_sma10.yaml`.
- The test applies cash-yield scenarios using the strategy's observed cash position.
- This is a robustness stress test, not a new strategy.
- If zero-cash performance collapses, the strategy depends heavily on cash yield.
- If zero-cash performance remains competitive, the regime logic is more important than the cash yield assumption.

## Caveat

If exact daily cash-return columns are not stored in the underlying strategy outputs, this report uses a cash-position-based approximation. It is still useful as a directional stress test, but it should not be described as a perfect cash-return reconstruction.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_cash_sensitivity(
    overlay_outputs: dict[str, pd.DataFrame],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    sensitivity = create_regime_switch_overlay_cash_sensitivity(
        overlay_outputs=overlay_outputs,
        config=config,
    )

    if sensitivity.empty:
        return {
            "sensitivity": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    summary = create_regime_switch_overlay_cash_sensitivity_summary(
        sensitivity=sensitivity,
        baseline_multiplier=1.0,
    )

    sensitivity_path = reports_dir / "regime_switch_overlay_cash_sensitivity.csv"
    summary_path = reports_dir / "regime_switch_overlay_cash_sensitivity_summary.csv"
    markdown_path = reports_dir / "regime_switch_overlay_cash_sensitivity.md"

    sensitivity.to_csv(sensitivity_path, index=False)
    summary.to_csv(summary_path, index=False)

    write_regime_switch_overlay_cash_sensitivity_markdown(
        sensitivity=sensitivity,
        summary=summary,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay cash sensitivity:")
    print(sensitivity.to_string(index=False))

    print("\nRegime switch overlay cash sensitivity summary:")
    print(summary.to_string(index=False))

    print(f"\nSaved regime switch overlay cash sensitivity to: {sensitivity_path}")
    print(f"Saved regime switch overlay cash sensitivity summary to: {summary_path}")
    print(f"Saved regime switch overlay cash sensitivity markdown to: {markdown_path}")

    return {
        "sensitivity": sensitivity,
        "summary": summary,
    }