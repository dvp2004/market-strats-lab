from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.regime_switch_overlay_slippage_sensitivity import (
    _build_overlay_inputs,
    _period_definitions,
    _slice_and_rebase_result,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _create_dynamic_slippage_series(
    offensive_result: pd.DataFrame,
    trend_sma_days: int,
    normal_bps: float,
    below_200d_bps: float,
    drawdown_10_bps: float,
    drawdown_20_bps: float,
) -> pd.Series:
    offensive = offensive_result.copy()
    offensive["date"] = pd.to_datetime(offensive["date"])
    offensive = offensive.sort_values("date").reset_index(drop=True)

    if "adj_close" not in offensive.columns:
        raise ValueError("offensive_result must contain adj_close")

    price = offensive["adj_close"].astype(float)
    trend_sma = price.rolling(trend_sma_days).mean()
    trend_ready = trend_sma.notna()
    below_200d = trend_ready & (price <= trend_sma)

    rolling_high = price.cummax()
    drawdown = (price / rolling_high) - 1.0

    slippage = pd.Series(float(normal_bps), index=offensive.index)

    slippage.loc[below_200d] = slippage.loc[below_200d].clip(
        lower=float(below_200d_bps)
    )
    slippage.loc[drawdown <= -0.10] = slippage.loc[drawdown <= -0.10].clip(
        lower=float(drawdown_10_bps)
    )
    slippage.loc[drawdown <= -0.20] = slippage.loc[drawdown <= -0.20].clip(
        lower=float(drawdown_20_bps)
    )

    slippage.index = offensive["date"]

    return slippage.astype(float)


def _calculate_period_metrics(
    result: pd.DataFrame,
    strategy_name: str,
    scenario: str,
    initial_capital: float,
    reference_end_date: str,
    holdout_start_date: str,
) -> pd.DataFrame:
    rows: list[dict] = []

    for period in _period_definitions(reference_end_date, holdout_start_date):
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
                "scenario": scenario,
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


def _create_trade_event_audit(
    overlay_result: pd.DataFrame,
) -> pd.DataFrame:
    result = overlay_result.copy()
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date").reset_index(drop=True)

    required_columns = {
        "date",
        "equity",
        "target_defensive_weight",
        "overlay_turnover",
        "overlay_slippage_cost",
        "applied_overlay_slippage_bps",
        "signal_price",
        "trend_sma",
    }
    missing_columns = required_columns - set(result.columns)

    if missing_columns:
        raise ValueError(
            "overlay result missing columns for trade-event audit: "
            f"{sorted(missing_columns)}"
        )

    target_defensive = result["target_defensive_weight"].astype(float)
    previous_target_defensive = target_defensive.shift(1)

    switch_mask = (
        previous_target_defensive.notna()
        & target_defensive.ne(previous_target_defensive)
    )

    event_rows: list[dict] = []

    equity = result["equity"].astype(float)
    signal_price = result["signal_price"].astype(float)
    rolling_high = signal_price.cummax()
    drawdown = (signal_price / rolling_high) - 1.0

    for idx, row in result.loc[switch_mask].iterrows():
        from_mode = (
            "defensive_allocator"
            if previous_target_defensive.loc[idx] >= 0.5
            else "offensive_spy"
        )

        to_mode = (
            "defensive_allocator"
            if target_defensive.loc[idx] >= 0.5
            else "offensive_spy"
        )

        event = {
            "switch_date": row["date"].date().isoformat(),
            "from_mode": from_mode,
            "to_mode": to_mode,
            "signal_price": round(float(row["signal_price"]), 4),
            "trend_sma": round(float(row["trend_sma"]), 4)
            if pd.notna(row["trend_sma"])
            else "",
            "spy_distance_from_trend_pct": round(
                (
                    (float(row["signal_price"]) / float(row["trend_sma"])) - 1.0
                )
                * 100.0,
                3,
            )
            if pd.notna(row["trend_sma"]) and float(row["trend_sma"]) != 0
            else "",
            "spy_drawdown_pct": round(float(drawdown.loc[idx]) * 100.0, 3),
            "overlay_turnover": round(float(row["overlay_turnover"]), 3),
            "applied_overlay_slippage_bps": round(
                float(row["applied_overlay_slippage_bps"]),
                3,
            ),
            "overlay_slippage_cost_pct": round(
                float(row["overlay_slippage_cost"]) * 100.0,
                5,
            ),
        }

        for horizon in [5, 20, 60]:
            future_idx = idx + horizon

            if future_idx < len(result):
                future_return = (equity.iloc[future_idx] / equity.iloc[idx]) - 1.0
                event[f"next_{horizon}d_return_pct"] = round(
                    float(future_return) * 100.0,
                    3,
                )
            else:
                event[f"next_{horizon}d_return_pct"] = ""

        event_rows.append(event)

    return pd.DataFrame(event_rows)


def create_regime_switch_overlay_dynamic_slippage(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    dynamic_config = config.get("phase4_dynamic_slippage", {})

    if not dynamic_config.get("enabled", False):
        return {
            "sensitivity": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "trade_event_audit": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    overlay_config = config.get("regime_switch_overlay", {})

    if not overlay_config.get("enabled", False):
        return {
            "sensitivity": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "trade_event_audit": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    initial_capital = float(config["initial_capital"])
    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))
    confirmation_days = int(overlay_config.get("confirmation_days", 1))
    baseline_slippage_bps = float(config.get("slippage_bps", 5.0))

    reference_end_date = str(dynamic_config["reference_end_date"])
    holdout_start_date = str(dynamic_config["holdout_start_date"])

    overlay_name = str(overlay_config.get("name", "Regime Switch Overlay"))

    flat_overlay = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        initial_capital=initial_capital,
        trend_sma_days=trend_sma_days,
        slippage_bps=baseline_slippage_bps,
        confirmation_days=confirmation_days,
    )

    dynamic_slippage = _create_dynamic_slippage_series(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
        normal_bps=float(dynamic_config.get("normal_bps", 5.0)),
        below_200d_bps=float(dynamic_config.get("below_200d_bps", 15.0)),
        drawdown_10_bps=float(dynamic_config.get("drawdown_10_bps", 25.0)),
        drawdown_20_bps=float(dynamic_config.get("drawdown_20_bps", 50.0)),
    )

    dynamic_overlay = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        initial_capital=initial_capital,
        trend_sma_days=trend_sma_days,
        slippage_bps=baseline_slippage_bps,
        confirmation_days=confirmation_days,
        dynamic_slippage_bps=dynamic_slippage,
    )

    flat_metrics = _calculate_period_metrics(
        result=flat_overlay,
        strategy_name=overlay_name,
        scenario="flat_5bps_baseline",
        initial_capital=initial_capital,
        reference_end_date=reference_end_date,
        holdout_start_date=holdout_start_date,
    )
    dynamic_metrics = _calculate_period_metrics(
        result=dynamic_overlay,
        strategy_name=overlay_name,
        scenario="dynamic_stress_slippage",
        initial_capital=initial_capital,
        reference_end_date=reference_end_date,
        holdout_start_date=holdout_start_date,
    )

    sensitivity = pd.concat(
        [flat_metrics, dynamic_metrics],
        ignore_index=True,
    )

    summary = create_regime_switch_overlay_dynamic_slippage_summary(sensitivity)
    trade_event_audit = _create_trade_event_audit(dynamic_overlay)
    conclusion = create_phase4_execution_realism_conclusion(sensitivity, summary)

    return {
        "sensitivity": sensitivity,
        "summary": summary,
        "trade_event_audit": trade_event_audit,
        "conclusion": conclusion,
    }


def create_regime_switch_overlay_dynamic_slippage_summary(
    sensitivity: pd.DataFrame,
) -> pd.DataFrame:
    if sensitivity.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for period, period_df in sensitivity.groupby("period"):
        baseline = period_df[period_df["scenario"] == "flat_5bps_baseline"]
        dynamic = period_df[period_df["scenario"] == "dynamic_stress_slippage"]

        if baseline.empty or dynamic.empty:
            continue

        baseline_row = baseline.iloc[0]
        dynamic_row = dynamic.iloc[0]

        rows.append(
            {
                "period": period,
                "baseline_cagr_pct": baseline_row["cagr_pct"],
                "dynamic_cagr_pct": dynamic_row["cagr_pct"],
                "cagr_delta_pct_points": round(
                    float(dynamic_row["cagr_pct"]) - float(baseline_row["cagr_pct"]),
                    3,
                ),
                "baseline_calmar": baseline_row["calmar"],
                "dynamic_calmar": dynamic_row["calmar"],
                "calmar_delta": round(
                    float(dynamic_row["calmar"]) - float(baseline_row["calmar"]),
                    3,
                ),
                "baseline_max_drawdown_pct": baseline_row["max_drawdown_pct"],
                "dynamic_max_drawdown_pct": dynamic_row["max_drawdown_pct"],
                "drawdown_delta_pct_points": round(
                    float(dynamic_row["max_drawdown_pct"])
                    - float(baseline_row["max_drawdown_pct"]),
                    3,
                ),
                "baseline_end_value": baseline_row["end_value"],
                "dynamic_end_value": dynamic_row["end_value"],
                "end_value_delta": round(
                    float(dynamic_row["end_value"]) - float(baseline_row["end_value"]),
                    2,
                ),
            }
        )

    return pd.DataFrame(rows)


def create_phase4_execution_realism_conclusion(
    sensitivity: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    if sensitivity.empty or summary.empty:
        return pd.DataFrame()

    full_dynamic = sensitivity[
        (sensitivity["period"] == "full")
        & (sensitivity["scenario"] == "dynamic_stress_slippage")
    ]

    full_summary = summary[summary["period"] == "full"]

    if full_dynamic.empty or full_summary.empty:
        return pd.DataFrame()

    dynamic_row = full_dynamic.iloc[0]
    summary_row = full_summary.iloc[0]

    dynamic_cagr = float(dynamic_row["cagr_pct"])
    dynamic_calmar = float(dynamic_row["calmar"])
    dynamic_drawdown = float(dynamic_row["max_drawdown_pct"])
    cagr_delta = float(summary_row["cagr_delta_pct_points"])
    calmar_delta = float(summary_row["calmar_delta"])
    drawdown_delta = float(summary_row["drawdown_delta_pct_points"])

    spy_12m_cagr_gate = 9.68
    spy_12m_calmar_gate = 0.287
    spy_12m_drawdown_gate = -33.72

    preserves_defensive_profile = (
        dynamic_calmar > spy_12m_calmar_gate
        and dynamic_drawdown > spy_12m_drawdown_gate
    )

    survives_spy_12m_triple_gate = (
        dynamic_cagr > spy_12m_cagr_gate
        and dynamic_calmar > spy_12m_calmar_gate
        and dynamic_drawdown > spy_12m_drawdown_gate
    )

    limited_impact = cagr_delta >= -0.5 and calmar_delta >= -0.05

    return pd.DataFrame(
        [
            {
                "claim": (
                    "The 3D overlay preserves its defensive profile under "
                    "dynamic stress slippage."
                ),
                "status": (
                    "Survived" if preserves_defensive_profile else "Failed"
                ),
                "evidence_quality": (
                    "Compared dynamic stress result against pinned SPY 12M "
                    "Calmar and drawdown gates"
                ),
                "interpretation": (
                    f"Dynamic stress slippage produced {dynamic_calmar} Calmar "
                    f"and {dynamic_drawdown}% max drawdown, versus SPY 12M gates "
                    f"of {spy_12m_calmar_gate} Calmar and "
                    f"{spy_12m_drawdown_gate}% max drawdown."
                ),
            },
            {
                "claim": (
                    "The 3D overlay still beats SPY 12M on the strict "
                    "full-period triple gate under dynamic stress slippage."
                ),
                "status": (
                    "Survived" if survives_spy_12m_triple_gate else "Failed"
                ),
                "evidence_quality": (
                    "Compared dynamic stress result against pinned SPY 12M "
                    "CAGR, Calmar, and drawdown gates"
                ),
                "interpretation": (
                    f"Dynamic stress slippage produced {dynamic_cagr}% CAGR, "
                    f"{dynamic_calmar} Calmar, and {dynamic_drawdown}% max "
                    f"drawdown. The pinned SPY 12M gates are "
                    f"{spy_12m_cagr_gate}% CAGR, {spy_12m_calmar_gate} Calmar, "
                    f"and {spy_12m_drawdown_gate}% max drawdown."
                ),
            },
            {
                "claim": "Dynamic stress slippage has limited impact.",
                "status": "Survived" if limited_impact else "Failed",
                "evidence_quality": (
                    "Compared dynamic stress slippage to flat 5 bps baseline"
                ),
                "interpretation": (
                    f"Dynamic slippage changed CAGR by {cagr_delta} percentage "
                    f"points, Calmar by {calmar_delta}, and max drawdown by "
                    f"{drawdown_delta} percentage points versus the flat 5 bps "
                    f"baseline."
                ),
            },
            {
                "claim": "Execution realism is no longer a major concern.",
                "status": "Failed",
                "evidence_quality": (
                    "Execution costs still require stress-aware modelling"
                ),
                "interpretation": (
                    "This test improves realism, but still does not model actual "
                    "bid-ask spreads, market impact, taxes, fund-level liquidity, "
                    "or execution delays during crises."
                ),
            },
        ]
    )


def write_regime_switch_overlay_dynamic_slippage_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sensitivity = outputs.get("sensitivity", pd.DataFrame())
    summary = outputs.get("summary", pd.DataFrame())
    trade_event_audit = outputs.get("trade_event_audit", pd.DataFrame())
    conclusion = outputs.get("conclusion", pd.DataFrame())

    content = f"""# Regime Switch Overlay Dynamic Slippage Sensitivity

This Phase 4 report tests whether the 3D confirmed regime-switch overlay survives a stress-aware execution-cost model.

## Dynamic Slippage Model

- Normal regime: 5 bps
- SPY below 200D: 15 bps
- SPY drawdown below -10%: 25 bps
- SPY drawdown below -20%: 50 bps

Costs only matter on switch days because they are multiplied by overlay turnover.

## Summary

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Sensitivity Table

{sensitivity.to_markdown(index=False) if not sensitivity.empty else "No sensitivity data available."}

## Trade Event Audit

{trade_event_audit.to_markdown(index=False) if not trade_event_audit.empty else "No trade-event audit available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_dynamic_slippage(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_dynamic_slippage(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    sensitivity = outputs["sensitivity"]
    summary = outputs["summary"]
    trade_event_audit = outputs["trade_event_audit"]
    conclusion = outputs["conclusion"]

    if sensitivity.empty:
        return outputs

    sensitivity_path = reports_dir / "regime_switch_overlay_dynamic_slippage_sensitivity.csv"
    summary_path = reports_dir / "regime_switch_overlay_dynamic_slippage_summary.csv"
    trade_event_path = reports_dir / "regime_switch_overlay_trade_event_audit.csv"
    conclusion_path = reports_dir / "phase4_execution_realism_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_dynamic_slippage.md"

    sensitivity.to_csv(sensitivity_path, index=False)
    summary.to_csv(summary_path, index=False)
    trade_event_audit.to_csv(trade_event_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_dynamic_slippage_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay dynamic slippage sensitivity:")
    print(sensitivity.to_string(index=False))

    print("\nRegime switch overlay dynamic slippage summary:")
    print(summary.to_string(index=False))

    print("\nPhase 4 execution realism conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved dynamic slippage sensitivity to: {sensitivity_path}")
    print(f"Saved dynamic slippage summary to: {summary_path}")
    print(f"Saved trade-event audit to: {trade_event_path}")
    print(f"Saved Phase 4 execution conclusion to: {conclusion_path}")
    print(f"Saved dynamic slippage markdown to: {markdown_path}")

    return outputs