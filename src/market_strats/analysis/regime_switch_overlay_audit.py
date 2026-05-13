from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.strategies.fixed_weight_portfolio import (
    rebase_strategy_result_to_dates,
)


def _prepare_result(result: pd.DataFrame, name: str) -> pd.DataFrame:
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
        raise ValueError(f"{name} result missing columns: {sorted(missing_columns)}")

    df = result.copy()
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


def _future_return(
    equity: pd.Series,
    start_index: int,
    horizon_days: int,
) -> float:
    if horizon_days <= 0:
        raise ValueError("future return horizon must be positive")

    end_index = min(start_index + horizon_days, len(equity) - 1)

    if end_index <= start_index:
        return np.nan

    start_value = float(equity.iloc[start_index])
    end_value = float(equity.iloc[end_index])

    if start_value <= 0:
        return np.nan

    return (end_value / start_value - 1.0) * 100.0


def _create_merged_audit_frame(
    overlay_result: pd.DataFrame,
    offensive_result: pd.DataFrame,
    defensive_result: pd.DataFrame,
) -> pd.DataFrame:
    overlay = _prepare_result(overlay_result, "overlay")

    if "selected_mode" not in overlay.columns:
        raise ValueError("overlay result missing selected_mode column")

    if "trend_sma" not in overlay.columns:
        raise ValueError("overlay result missing trend_sma column")

    if "overlay_turnover" not in overlay.columns:
        raise ValueError("overlay result missing overlay_turnover column")

    offensive = _prepare_result(offensive_result, "offensive")
    defensive = _prepare_result(defensive_result, "defensive")

    merged = overlay[
        [
            "date",
            "equity",
            "strategy_return",
            "position",
            "cash_position",
            "turnover",
            "selected_mode",
            "trend_sma",
            "overlay_turnover",
            "offensive_weight",
            "defensive_weight",
        ]
    ].merge(
        offensive[
            [
                "date",
                "adj_close",
                "equity",
                "strategy_return",
                "position",
                "cash_position",
            ]
        ],
        on="date",
        how="inner",
        suffixes=("_overlay", "_offensive"),
    ).merge(
        defensive[
            [
                "date",
                "equity",
                "strategy_return",
                "position",
                "cash_position",
            ]
        ],
        on="date",
        how="inner",
    )

    merged = merged.rename(
        columns={
            "equity": "equity_defensive",
            "strategy_return": "strategy_return_defensive",
            "position": "position_defensive",
            "cash_position": "cash_position_defensive",
            "adj_close": "spy_adj_close",
            "position_overlay": "position",
            "cash_position_overlay": "cash_position",
        }
    )

    merged = merged.sort_values("date").reset_index(drop=True)

    merged["overlay_peak"] = merged["equity_overlay"].cummax()
    merged["overlay_drawdown_pct"] = (
        merged["equity_overlay"] / merged["overlay_peak"] - 1.0
    ) * 100.0

    merged["spy_peak"] = merged["spy_adj_close"].cummax()
    merged["spy_drawdown_pct"] = (
        merged["spy_adj_close"] / merged["spy_peak"] - 1.0
    ) * 100.0

    merged["spy_distance_from_200d_pct"] = (
        merged["spy_adj_close"] / merged["trend_sma"] - 1.0
    ) * 100.0

    return merged


def create_regime_switch_overlay_audit(
    overlay_result: pd.DataFrame,
    offensive_result: pd.DataFrame,
    defensive_result: pd.DataFrame,
    whipsaw_days: int = 30,
    future_return_horizons: list[int] | None = None,
) -> pd.DataFrame:
    if whipsaw_days <= 0:
        raise ValueError("whipsaw_days must be positive")

    if future_return_horizons is None:
        future_return_horizons = [21, 63, 126, 252]

    merged = _create_merged_audit_frame(
        overlay_result=overlay_result,
        offensive_result=offensive_result,
        defensive_result=defensive_result,
    )

    merged["previous_mode"] = merged["selected_mode"].shift(1)
    switch_mask = (
        merged["previous_mode"].notna()
        & (merged["selected_mode"] != merged["previous_mode"])
    )

    switch_indices = merged.index[switch_mask].tolist()

    rows: list[dict] = []

    for switch_number, switch_index in enumerate(switch_indices, start=1):
        row = merged.iloc[switch_index]

        if switch_number < len(switch_indices):
            next_switch_index = switch_indices[switch_number]
            days_until_next_switch = next_switch_index - switch_index
            next_switch_date = merged.iloc[next_switch_index]["date"]
        else:
            days_until_next_switch = np.nan
            next_switch_date = pd.NaT

        if switch_number > 1:
            previous_switch_index = switch_indices[switch_number - 2]
            days_since_previous_switch = switch_index - previous_switch_index
        else:
            days_since_previous_switch = np.nan

        audit_row = {
            "switch_number": switch_number,
            "switch_date": row["date"].date().isoformat(),
            "switch_year": int(row["date"].year),
            "from_mode": row["previous_mode"],
            "to_mode": row["selected_mode"],
            "next_switch_date": (
                ""
                if pd.isna(next_switch_date)
                else pd.Timestamp(next_switch_date).date().isoformat()
            ),
            "days_since_previous_switch": days_since_previous_switch,
            "days_until_next_switch": days_until_next_switch,
            "whipsaw_flag": (
                False
                if pd.isna(days_until_next_switch)
                else days_until_next_switch <= whipsaw_days
            ),
            "overlay_equity_at_switch": row["equity_overlay"],
            "overlay_drawdown_at_switch_pct": row["overlay_drawdown_pct"],
            "spy_drawdown_at_switch_pct": row["spy_drawdown_pct"],
            "spy_adj_close_at_switch": row["spy_adj_close"],
            "spy_200d_sma_at_switch": row["trend_sma"],
            "spy_distance_from_200d_pct": row["spy_distance_from_200d_pct"],
            "overlay_turnover_at_switch_pct": row["overlay_turnover"] * 100.0,
            "portfolio_position_at_switch_pct": row["position"] * 100.0,
            "portfolio_cash_at_switch_pct": row["cash_position"] * 100.0,
            "defensive_allocator_position_at_switch_pct": (
                row["position_defensive"] * 100.0
            ),
            "defensive_allocator_cash_at_switch_pct": (
                row["cash_position_defensive"] * 100.0
            ),
        }

        for horizon in future_return_horizons:
            audit_row[f"overlay_next_{horizon}d_return_pct"] = _future_return(
                equity=merged["equity_overlay"],
                start_index=switch_index,
                horizon_days=int(horizon),
            )
            audit_row[f"spy_next_{horizon}d_return_pct"] = _future_return(
                equity=merged["equity_offensive"],
                start_index=switch_index,
                horizon_days=int(horizon),
            )
            audit_row[f"defensive_next_{horizon}d_return_pct"] = _future_return(
                equity=merged["equity_defensive"],
                start_index=switch_index,
                horizon_days=int(horizon),
            )

        rows.append(audit_row)

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.reset_index(drop=True)


def create_regime_switch_overlay_audit_summary(
    audit: pd.DataFrame,
    focus_years: list[int] | None = None,
) -> pd.DataFrame:
    if audit.empty:
        return pd.DataFrame()

    if focus_years is None:
        focus_years = []

    total_switches = len(audit)
    whipsaw_count = int(audit["whipsaw_flag"].sum())
    defensive_switches = int((audit["to_mode"] == "defensive_allocator").sum())
    offensive_switches = int((audit["to_mode"] == "offensive_spy").sum())

    switches_by_year = (
        audit.groupby("switch_year")
        .size()
        .sort_index()
        .rename("switch_count")
        .reset_index()
    )

    focus_year_switches = audit[audit["switch_year"].isin(focus_years)]

    rows = [
        {
            "metric": "total_switches",
            "value": total_switches,
        },
        {
            "metric": "whipsaw_count",
            "value": whipsaw_count,
        },
        {
            "metric": "whipsaw_pct",
            "value": whipsaw_count / total_switches * 100.0
            if total_switches
            else np.nan,
        },
        {
            "metric": "switches_to_defensive",
            "value": defensive_switches,
        },
        {
            "metric": "switches_to_offensive",
            "value": offensive_switches,
        },
        {
            "metric": "avg_days_until_next_switch",
            "value": audit["days_until_next_switch"].dropna().astype(float).mean(),
        },
        {
            "metric": "median_days_until_next_switch",
            "value": audit["days_until_next_switch"].dropna().astype(float).median(),
        },
        {
            "metric": "avg_overlay_drawdown_at_switch_pct",
            "value": audit["overlay_drawdown_at_switch_pct"].astype(float).mean(),
        },
        {
            "metric": "avg_spy_drawdown_at_switch_pct",
            "value": audit["spy_drawdown_at_switch_pct"].astype(float).mean(),
        },
        {
            "metric": "avg_spy_distance_from_200d_pct",
            "value": audit["spy_distance_from_200d_pct"].astype(float).mean(),
        },
        {
            "metric": "avg_defensive_allocator_cash_at_switch_pct",
            "value": audit["defensive_allocator_cash_at_switch_pct"].astype(float).mean(),
        },
        {
            "metric": "focus_year_switches",
            "value": len(focus_year_switches),
        },
        {
            "metric": "switches_by_year",
            "value": "; ".join(
                f"{int(row.switch_year)}:{int(row.switch_count)}"
                for row in switches_by_year.itertuples(index=False)
            ),
        },
    ]

    summary = pd.DataFrame(rows)

    numeric_mask = pd.to_numeric(summary["value"], errors="coerce").notna()
    summary.loc[numeric_mask, "value"] = (
        pd.to_numeric(summary.loc[numeric_mask, "value"], errors="coerce")
        .round(3)
        .astype(object)
    )

    return summary


def write_regime_switch_overlay_audit_markdown(
    audit: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if audit.empty:
        output_path.write_text(
            "# Regime Switch Overlay Audit\n\nNo switches found.\n",
            encoding="utf-8",
        )
        return output_path

    summary_table = summary.to_markdown(index=False) if not summary.empty else ""
    audit_table = audit.to_markdown(index=False)

    content = f"""# Regime Switch Overlay Audit

This report audits the raw SPY 200D regime-switch overlay.

The goal is to diagnose why the overlay failed to become a new leader.

## Summary

{summary_table}

## Switch Audit

{audit_table}

## Interpretation Notes

- A whipsaw is defined as a switch that reverses within the configured whipsaw window.
- The current default whipsaw window is 30 trading days.
- The key question is whether the overlay lost performance through frequent boundary crossings around the 200D SMA.
- If whipsaws are the main problem, one pre-declared buffered switch may be justified.
- If whipsaws are not the main problem, the defensive allocator may simply be too low-return as a substitute for SPY.
- Do not use this report to optimise many thresholds after the fact.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_audit(
    overlay_outputs: dict[str, pd.DataFrame],
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    audit_config = config.get("regime_switch_overlay_audit", {})

    if not audit_config.get("enabled", False):
        return {
            "audit": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    overlay_config = config.get("regime_switch_overlay", {})

    if not overlay_config.get("enabled", False):
        return {
            "audit": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    overlay_result = overlay_outputs.get("overlay_result")

    if overlay_result is None or overlay_result.empty:
        return {
            "audit": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

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

    overlay_dates = list(pd.to_datetime(overlay_result["date"]))

    offensive_result = rebase_strategy_result_to_dates(
        result=_get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=str(overlay_config.get("benchmark_ticker", "SPY")).upper(),
            strategy=str(overlay_config.get("offensive_strategy", "Buy and Hold")),
        ),
        dates=overlay_dates,
        initial_capital=float(config["initial_capital"]),
    )

    defensive_result = rebase_strategy_result_to_dates(
        result=defensive_result,
        dates=overlay_dates,
        initial_capital=float(config["initial_capital"]),
    )

    audit = create_regime_switch_overlay_audit(
        overlay_result=overlay_result,
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        whipsaw_days=int(audit_config.get("whipsaw_days", 30)),
        future_return_horizons=[
            int(horizon)
            for horizon in audit_config.get("future_return_horizons", [21, 63, 126, 252])
        ],
    )

    summary = create_regime_switch_overlay_audit_summary(
        audit=audit,
        focus_years=[int(year) for year in audit_config.get("focus_years", [])],
    )

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    audit_path = reports_dir / "regime_switch_overlay_audit.csv"
    summary_path = reports_dir / "regime_switch_overlay_audit_summary.csv"
    markdown_path = reports_dir / "regime_switch_overlay_audit.md"

    audit.to_csv(audit_path, index=False)
    summary.to_csv(summary_path, index=False)

    write_regime_switch_overlay_audit_markdown(
        audit=audit,
        summary=summary,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay audit:")
    print(audit.to_string(index=False))

    print("\nRegime switch overlay audit summary:")
    print(summary.to_string(index=False))

    print(f"\nSaved regime switch overlay audit to: {audit_path}")
    print(f"Saved regime switch overlay audit summary to: {summary_path}")
    print(f"Saved regime switch overlay audit markdown to: {markdown_path}")

    return {
        "audit": audit,
        "summary": summary,
    }