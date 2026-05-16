from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.regime_switch_overlay_dynamic_slippage import (
    _create_dynamic_slippage_series,
    _create_trade_event_audit,
)
from market_strats.analysis.regime_switch_overlay_guarded_switch_diagnostic import (
    _create_defensive_entry_guard_series,
)
from market_strats.analysis.regime_switch_overlay_slippage_sensitivity import (
    _build_overlay_inputs,
    _period_definitions,
    _slice_and_rebase_result,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _get_price_data(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
) -> pd.DataFrame:
    ticker = ticker.upper()

    if ticker not in ticker_outputs:
        raise ValueError(f"Ticker {ticker} not available in ticker_outputs")

    price_data = ticker_outputs[ticker].get("price_data")

    if price_data is None:
        price_data = ticker_outputs[ticker].get("data")

    if price_data is None:
        raise ValueError(f"Ticker {ticker} has no price_data/data frame")

    required_columns = {"date", "adj_close"}
    missing_columns = required_columns - set(price_data.columns)

    if missing_columns:
        raise ValueError(
            f"Ticker {ticker} price data missing columns: {sorted(missing_columns)}"
        )

    output = price_data[["date", "adj_close"]].copy()
    output["date"] = pd.to_datetime(output["date"])
    output["adj_close"] = output["adj_close"].astype(float)
    output = output.sort_values("date").reset_index(drop=True)

    return output


def _create_risk_asset_breadth_frame(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    risk_assets: list[str],
    breadth_sma_days: int,
) -> pd.DataFrame:
    if breadth_sma_days <= 0:
        raise ValueError("breadth_sma_days must be positive")

    frames: list[pd.DataFrame] = []

    for ticker in risk_assets:
        prices = _get_price_data(ticker_outputs=ticker_outputs, ticker=ticker)
        ticker_upper = ticker.upper()

        prices[f"{ticker_upper}_sma"] = prices["adj_close"].rolling(
            breadth_sma_days
        ).mean()
        prices[f"{ticker_upper}_above_sma"] = (
            prices[f"{ticker_upper}_sma"].notna()
            & (prices["adj_close"] > prices[f"{ticker_upper}_sma"])
        )

        frames.append(prices[["date", f"{ticker_upper}_above_sma"]])

    if not frames:
        raise ValueError("No risk assets supplied for breadth calculation")

    breadth = frames[0]

    for frame in frames[1:]:
        breadth = breadth.merge(frame, on="date", how="inner")

    if breadth.empty:
        raise ValueError("Risk asset breadth frame is empty")

    breadth = breadth.sort_values("date").reset_index(drop=True)

    above_columns = [column for column in breadth.columns if column.endswith("_above_sma")]

    breadth["risk_asset_count"] = len(above_columns)
    breadth["risk_assets_above_sma"] = breadth[above_columns].sum(axis=1)
    breadth["risk_asset_breadth_pct"] = (
        breadth["risk_assets_above_sma"] / breadth["risk_asset_count"]
    )

    return breadth


def _align_breadth_to_dates(
    breadth_frame: pd.DataFrame,
    dates: pd.Series,
) -> pd.Series:
    if breadth_frame.empty:
        raise ValueError("breadth_frame is empty")

    breadth = breadth_frame[["date", "risk_asset_breadth_pct"]].copy()
    breadth["date"] = pd.to_datetime(breadth["date"])
    breadth = breadth.sort_values("date").set_index("date")

    aligned = (
        breadth["risk_asset_breadth_pct"]
        .reindex(pd.to_datetime(dates))
        .ffill()
        .bfill()
        .reset_index(drop=True)
        .astype(float)
    )

    if aligned.isna().any():
        raise ValueError("Risk asset breadth could not be aligned to dates")

    aligned.index = pd.to_datetime(dates)

    return aligned


def _create_breadth_guard_series(
    offensive_result: pd.DataFrame,
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.Series]:
    phase_config = config.get("phase5_breadth_confirmation", {})
    overlay_config = config.get("regime_switch_overlay", {})
    guarded_config = config.get("phase4_guarded_switch_diagnostic", {})

    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))
    breadth_sma_days = int(phase_config.get("breadth_sma_days", 200))

    risk_assets = [str(ticker).upper() for ticker in phase_config["risk_assets"]]

    breadth_frame = _create_risk_asset_breadth_frame(
        ticker_outputs=ticker_outputs,
        risk_assets=risk_assets,
        breadth_sma_days=breadth_sma_days,
    )

    offensive = offensive_result.copy()
    offensive["date"] = pd.to_datetime(offensive["date"])
    offensive = offensive.sort_values("date").reset_index(drop=True)

    breadth = _align_breadth_to_dates(
        breadth_frame=breadth_frame,
        dates=offensive["date"],
    )

    deep_drawdown_guard = _create_defensive_entry_guard_series(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
        guard_name="deep_drawdown_guard",
        near_high_drawdown_threshold=float(
            guarded_config.get("near_high_drawdown_threshold", -0.05)
        ),
        near_high_min_trend_distance=float(
            guarded_config.get("near_high_min_trend_distance", -0.01)
        ),
        deep_drawdown_threshold=float(
            guarded_config.get("deep_drawdown_threshold", -0.20)
        ),
    )

    defensive_breadth_condition = breadth <= float(
        phase_config.get("defensive_breadth_max", 0.50)
    )
    offensive_breadth_condition = breadth >= float(
        phase_config.get("offensive_breadth_min", 0.50)
    )

    defensive_breadth_condition.index = offensive["date"]
    offensive_breadth_condition.index = offensive["date"]

    return {
        "deep_drawdown_guard": deep_drawdown_guard.astype(bool),
        "defensive_breadth_condition": defensive_breadth_condition.astype(bool),
        "offensive_breadth_condition": offensive_breadth_condition.astype(bool),
        "risk_asset_breadth_pct": breadth.astype(float),
    }


def _variant_guard_inputs(
    variant_name: str,
    guards: dict[str, pd.Series],
) -> tuple[pd.Series | None, pd.Series | None, str, str]:
    deep_guard = guards["deep_drawdown_guard"]
    defensive_breadth = guards["defensive_breadth_condition"]
    offensive_breadth = guards["offensive_breadth_condition"]

    if variant_name == "phase4_execution_candidate":
        return (
            deep_guard,
            None,
            "deep_drawdown_guard",
            "none",
        )

    if variant_name == "defensive_breadth_confirmation":
        return (
            deep_guard & defensive_breadth,
            None,
            "deep_drawdown_guard_and_defensive_breadth",
            "none",
        )

    if variant_name == "offensive_breadth_confirmation":
        return (
            deep_guard,
            offensive_breadth,
            "deep_drawdown_guard",
            "offensive_breadth_confirmation",
        )

    if variant_name == "combined_breadth_confirmation":
        return (
            deep_guard & defensive_breadth,
            offensive_breadth,
            "deep_drawdown_guard_and_defensive_breadth",
            "offensive_breadth_confirmation",
        )

    raise ValueError(f"Unknown breadth confirmation variant: {variant_name}")


def _calculate_variant_metrics(
    result: pd.DataFrame,
    variant_name: str,
    strategy_name: str,
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
                "variant_name": variant_name,
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


def _create_event_summary(
    variant_events: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict] = []

    for variant_name, events in variant_events.items():
        if events.empty:
            rows.append(
                {
                    "variant_name": variant_name,
                    "switch_count": 0,
                    "avg_applied_slippage_bps": "",
                    "avg_overlay_slippage_cost_pct": "",
                }
            )
            continue

        rows.append(
            {
                "variant_name": variant_name,
                "switch_count": int(len(events)),
                "avg_applied_slippage_bps": round(
                    float(events["applied_overlay_slippage_bps"].astype(float).mean()),
                    3,
                ),
                "avg_overlay_slippage_cost_pct": round(
                    float(events["overlay_slippage_cost_pct"].astype(float).mean()),
                    5,
                ),
            }
        )

    return pd.DataFrame(rows)


def _create_breadth_confirmation_summary(
    metrics: pd.DataFrame,
    benchmark_variant: str,
) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()

    benchmark = metrics[metrics["variant_name"] == benchmark_variant].copy()

    if benchmark.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for _, row in metrics.iterrows():
        period = row["period"]
        benchmark_period = benchmark[benchmark["period"] == period]

        if benchmark_period.empty:
            continue

        benchmark_row = benchmark_period.iloc[0]

        rows.append(
            {
                "period": period,
                "variant_name": row["variant_name"],
                "benchmark_variant": benchmark_variant,
                "cagr_pct": row["cagr_pct"],
                "cagr_delta_vs_benchmark_pct_points": round(
                    float(row["cagr_pct"]) - float(benchmark_row["cagr_pct"]),
                    3,
                ),
                "calmar": row["calmar"],
                "calmar_delta_vs_benchmark": round(
                    float(row["calmar"]) - float(benchmark_row["calmar"]),
                    3,
                ),
                "max_drawdown_pct": row["max_drawdown_pct"],
                "drawdown_delta_vs_benchmark_pct_points": round(
                    float(row["max_drawdown_pct"])
                    - float(benchmark_row["max_drawdown_pct"]),
                    3,
                ),
                "end_value": row["end_value"],
                "end_value_delta_vs_benchmark": round(
                    float(row["end_value"]) - float(benchmark_row["end_value"]),
                    2,
                ),
                "trade_count": row["trade_count"],
                "trade_count_delta_vs_benchmark": int(row["trade_count"])
                - int(benchmark_row["trade_count"]),
            }
        )

    return pd.DataFrame(rows)


def _create_breadth_confirmation_gate_report(
    summary: pd.DataFrame,
    event_summary: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    phase_config = config.get("phase5_breadth_confirmation", {})
    benchmark_variant = str(
        phase_config.get("benchmark_variant", "phase4_execution_candidate")
    )

    full = summary[summary["period"] == "full"].copy()
    holdout = summary[summary["period"] == "holdout"].copy()

    candidates = full[full["variant_name"] != benchmark_variant].copy()

    if candidates.empty:
        return pd.DataFrame()

    candidates["score"] = (
        candidates["cagr_delta_vs_benchmark_pct_points"].astype(float)
        + candidates["calmar_delta_vs_benchmark"].astype(float)
        + candidates["drawdown_delta_vs_benchmark_pct_points"].astype(float) / 10.0
    )

    best_full = candidates.sort_values("score", ascending=False).iloc[0]
    best_variant = str(best_full["variant_name"])

    best_holdout = holdout[holdout["variant_name"] == best_variant]

    full_cagr_delta = float(best_full["cagr_delta_vs_benchmark_pct_points"])
    full_calmar_delta = float(best_full["calmar_delta_vs_benchmark"])
    full_drawdown_delta = float(best_full["drawdown_delta_vs_benchmark_pct_points"])

    max_holdout_cagr_damage = float(
        phase_config.get("max_allowed_holdout_cagr_damage_pct_points", -0.50)
    )
    max_holdout_calmar_damage = float(
        phase_config.get("max_allowed_holdout_calmar_damage", -0.05)
    )
    max_drawdown_damage = float(
        phase_config.get("max_allowed_drawdown_damage_pct_points", -1.00)
    )

    improves_full = (
        full_cagr_delta > 0
        and full_calmar_delta > 0
        and full_drawdown_delta >= max_drawdown_damage
    )

    holdout_damage = False
    holdout_interpretation = "Holdout comparison unavailable."

    if not best_holdout.empty:
        holdout_row = best_holdout.iloc[0]
        holdout_cagr_delta = float(
            holdout_row["cagr_delta_vs_benchmark_pct_points"]
        )
        holdout_calmar_delta = float(holdout_row["calmar_delta_vs_benchmark"])
        holdout_drawdown_delta = float(
            holdout_row["drawdown_delta_vs_benchmark_pct_points"]
        )

        holdout_damage = (
            holdout_cagr_delta < max_holdout_cagr_damage
            or holdout_calmar_delta < max_holdout_calmar_damage
            or holdout_drawdown_delta < max_drawdown_damage
        )

        holdout_interpretation = (
            f"{best_variant} holdout CAGR delta was {holdout_cagr_delta}, "
            f"Calmar delta was {holdout_calmar_delta}, and drawdown delta was "
            f"{holdout_drawdown_delta} versus {benchmark_variant}."
        )

    benchmark_events = event_summary[
        event_summary["variant_name"] == benchmark_variant
    ]
    candidate_events = event_summary[event_summary["variant_name"] == best_variant]

    switch_interpretation = "Switch-count comparison unavailable."
    excessive_churn = False

    if not benchmark_events.empty and not candidate_events.empty:
        switch_delta = int(candidate_events.iloc[0]["switch_count"]) - int(
            benchmark_events.iloc[0]["switch_count"]
        )
        excessive_churn = switch_delta > 10
        switch_interpretation = (
            f"{best_variant} changed switch count by {switch_delta} versus "
            f"{benchmark_variant}."
        )

    candidate_passes = improves_full and not holdout_damage and not excessive_churn

    return pd.DataFrame(
        [
            {
                "gate": "Best breadth variant improves full-period execution-realistic benchmark.",
                "status": "Passed" if improves_full else "Failed",
                "evidence_quality": "Compared full-period variant metrics against Phase 4 execution-realistic candidate",
                "interpretation": (
                    f"Best variant was {best_variant}. Full-period CAGR delta was "
                    f"{full_cagr_delta}, Calmar delta was {full_calmar_delta}, "
                    f"and drawdown delta was {full_drawdown_delta}."
                ),
            },
            {
                "gate": "Best breadth variant avoids holdout damage.",
                "status": "Passed" if not holdout_damage else "Failed",
                "evidence_quality": "Checked holdout CAGR, Calmar, and drawdown deltas",
                "interpretation": holdout_interpretation,
            },
            {
                "gate": "Best breadth variant avoids excessive switching.",
                "status": "Passed" if not excessive_churn else "Failed",
                "evidence_quality": "Compared switch counts versus Phase 4 execution-realistic candidate",
                "interpretation": switch_interpretation,
            },
            {
                "gate": "Breadth confirmation is ready for promotion.",
                "status": "Passed" if candidate_passes else "Not yet",
                "evidence_quality": "Requires full-period improvement without holdout damage or excessive churn",
                "interpretation": (
                    f"{best_variant} passed all breadth-confirmation gates."
                    if candidate_passes
                    else f"{best_variant} did not pass all breadth-confirmation gates."
                ),
            },
        ]
    )


def _create_breadth_confirmation_conclusion(
    gate_report: pd.DataFrame,
) -> pd.DataFrame:
    if gate_report.empty:
        return pd.DataFrame()

    final_gate = gate_report[
        gate_report["gate"] == "Breadth confirmation is ready for promotion."
    ]

    final_status = final_gate.iloc[0]["status"] if not final_gate.empty else "Not yet"

    return pd.DataFrame(
        [
            {
                "claim": "Breadth confirmation improves the Phase 4 execution-realistic candidate.",
                "status": "Survived" if final_status == "Passed" else "Failed",
                "evidence_quality": "Based on Phase 5A breadth-confirmation gate report",
                "interpretation": (
                    "A breadth-confirmation variant passed all promotion gates."
                    if final_status == "Passed"
                    else "No breadth-confirmation variant passed all promotion gates."
                ),
            },
            {
                "claim": "Breadth confirmation should replace deep_drawdown_guard immediately.",
                "status": "Not yet",
                "evidence_quality": "Phase 5A is a diagnostic layer test",
                "interpretation": (
                    "Even if breadth improves results, it should be documented as a "
                    "candidate and validated further before replacing the Phase 4 "
                    "execution-realistic candidate."
                ),
            },
            {
                "claim": "The next step should be macro/sentiment/ML.",
                "status": "Not yet",
                "evidence_quality": "Breadth is the first external confirmation layer",
                "interpretation": (
                    "Only move to macro/sentiment/ML if breadth confirmation fails "
                    "cleanly or after any breadth candidate is documented."
                ),
            },
        ]
    )


def create_regime_switch_overlay_breadth_confirmation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = config.get("phase5_breadth_confirmation", {})

    if not phase_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "event_summary": pd.DataFrame(),
            "gate_report": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    overlay_config = config.get("regime_switch_overlay", {})

    if not overlay_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "event_summary": pd.DataFrame(),
            "gate_report": pd.DataFrame(),
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
    overlay_name = str(overlay_config.get("name", "Regime Switch Overlay"))

    reference_end_date = str(phase_config["reference_end_date"])
    holdout_start_date = str(phase_config["holdout_start_date"])

    dynamic_config = config.get("phase4_dynamic_slippage", {})
    dynamic_slippage = _create_dynamic_slippage_series(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
        normal_bps=float(dynamic_config.get("normal_bps", 5.0)),
        below_200d_bps=float(dynamic_config.get("below_200d_bps", 15.0)),
        drawdown_10_bps=float(dynamic_config.get("drawdown_10_bps", 25.0)),
        drawdown_20_bps=float(dynamic_config.get("drawdown_20_bps", 50.0)),
    )

    guards = _create_breadth_guard_series(
        offensive_result=offensive_result,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    variant_names = [
        "phase4_execution_candidate",
        "defensive_breadth_confirmation",
        "offensive_breadth_confirmation",
        "combined_breadth_confirmation",
    ]

    metric_frames: list[pd.DataFrame] = []
    variant_events: dict[str, pd.DataFrame] = {}

    for variant_name in variant_names:
        (
            defensive_entry_allowed,
            offensive_entry_allowed,
            defensive_guard_name,
            offensive_guard_name,
        ) = _variant_guard_inputs(variant_name=variant_name, guards=guards)

        overlay_result = run_spy_trend_regime_switch_overlay(
            offensive_result=offensive_result,
            defensive_result=defensive_result,
            initial_capital=initial_capital,
            trend_sma_days=trend_sma_days,
            slippage_bps=baseline_slippage_bps,
            confirmation_days=confirmation_days,
            dynamic_slippage_bps=dynamic_slippage,
            defensive_entry_allowed=defensive_entry_allowed,
            defensive_entry_guard_name=defensive_guard_name,
            offensive_entry_allowed=offensive_entry_allowed,
            offensive_entry_guard_name=offensive_guard_name,
        )

        metric_frames.append(
            _calculate_variant_metrics(
                result=overlay_result,
                variant_name=variant_name,
                strategy_name=overlay_name,
                initial_capital=initial_capital,
                reference_end_date=reference_end_date,
                holdout_start_date=holdout_start_date,
            )
        )

        variant_events[variant_name] = _create_trade_event_audit(overlay_result)

    metrics = pd.concat(metric_frames, ignore_index=True)
    event_summary = _create_event_summary(variant_events)
    summary = _create_breadth_confirmation_summary(
        metrics=metrics,
        benchmark_variant=str(
            phase_config.get("benchmark_variant", "phase4_execution_candidate")
        ),
    )
    gate_report = _create_breadth_confirmation_gate_report(
        summary=summary,
        event_summary=event_summary,
        config=config,
    )
    conclusion = _create_breadth_confirmation_conclusion(gate_report)

    return {
        "metrics": metrics,
        "summary": summary,
        "event_summary": event_summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }


def write_regime_switch_overlay_breadth_confirmation_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = outputs.get("metrics", pd.DataFrame())
    summary = outputs.get("summary", pd.DataFrame())
    event_summary = outputs.get("event_summary", pd.DataFrame())
    gate_report = outputs.get("gate_report", pd.DataFrame())
    conclusion = outputs.get("conclusion", pd.DataFrame())

    content = f"""# Regime Switch Overlay Breadth Confirmation Diagnostic

This Phase 5A report tests whether a simple risk-asset breadth confirmation layer improves the Phase 4 execution-realistic candidate.

The benchmark is:

- 3D confirmed overlay
- dynamic stress slippage
- deep_drawdown_guard

Breadth is calculated as the percentage of configured risk assets trading above their 200D SMA.

## Metrics

{metrics.to_markdown(index=False) if not metrics.empty else "No metrics available."}

## Summary Versus Benchmark

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Event Summary

{event_summary.to_markdown(index=False) if not event_summary.empty else "No event summary available."}

## Gate Report

{gate_report.to_markdown(index=False) if not gate_report.empty else "No gate report available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_breadth_confirmation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_breadth_confirmation(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    metrics = outputs["metrics"]
    summary = outputs["summary"]
    event_summary = outputs["event_summary"]
    gate_report = outputs["gate_report"]
    conclusion = outputs["conclusion"]

    if metrics.empty:
        return outputs

    metrics_path = reports_dir / "regime_switch_overlay_breadth_confirmation_metrics.csv"
    summary_path = reports_dir / "regime_switch_overlay_breadth_confirmation_summary.csv"
    event_summary_path = (
        reports_dir / "regime_switch_overlay_breadth_confirmation_event_summary.csv"
    )
    gate_path = reports_dir / "regime_switch_overlay_breadth_confirmation_gate_report.csv"
    conclusion_path = reports_dir / "phase5a_breadth_confirmation_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_breadth_confirmation.md"

    metrics.to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)
    event_summary.to_csv(event_summary_path, index=False)
    gate_report.to_csv(gate_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_breadth_confirmation_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay breadth-confirmation metrics:")
    print(metrics.to_string(index=False))

    print("\nRegime switch overlay breadth-confirmation summary:")
    print(summary.to_string(index=False))

    print("\nRegime switch overlay breadth-confirmation event summary:")
    print(event_summary.to_string(index=False))

    print("\nRegime switch overlay breadth-confirmation gate report:")
    print(gate_report.to_string(index=False))

    print("\nPhase 5A breadth-confirmation conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved breadth-confirmation metrics to: {metrics_path}")
    print(f"Saved breadth-confirmation summary to: {summary_path}")
    print(f"Saved breadth-confirmation event summary to: {event_summary_path}")
    print(f"Saved breadth-confirmation gate report to: {gate_path}")
    print(f"Saved Phase 5A conclusion to: {conclusion_path}")
    print(f"Saved breadth-confirmation markdown to: {markdown_path}")

    return outputs