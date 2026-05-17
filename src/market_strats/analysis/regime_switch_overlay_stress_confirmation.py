from __future__ import annotations

from pathlib import Path

import numpy as np
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
    _slice_and_rebase_result,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _segment_definitions(config: dict) -> list[dict]:
    phase_config = config.get("phase6_stress_confirmation_validation", {})

    reference_end_date = str(phase_config["reference_end_date"])
    holdout_start_date = str(phase_config["holdout_start_date"])

    segments: list[dict] = [
        {
            "period": "full",
            "start_date": None,
            "end_date": None,
            "segment_type": "core",
        },
        {
            "period": "reference",
            "start_date": None,
            "end_date": reference_end_date,
            "segment_type": "core",
        },
        {
            "period": "holdout",
            "start_date": holdout_start_date,
            "end_date": None,
            "segment_type": "core",
        },
    ]

    for segment in phase_config.get("segments", []):
        segments.append(
            {
                "period": str(segment["name"]),
                "start_date": segment.get("start_date"),
                "end_date": segment.get("end_date"),
                "segment_type": "episode",
            }
        )

    return segments


def _create_stress_state_frame(
    offensive_result: pd.DataFrame,
    trend_sma_days: int,
    volatility_window_days: int,
) -> pd.DataFrame:
    offensive = offensive_result.copy()
    offensive["date"] = pd.to_datetime(offensive["date"])
    offensive = offensive.sort_values("date").reset_index(drop=True)

    if "adj_close" not in offensive.columns:
        raise ValueError("offensive_result must contain adj_close")

    price = offensive["adj_close"].astype(float)
    returns = price.pct_change().fillna(0.0)

    offensive["signal_price"] = price
    offensive["trend_sma"] = price.rolling(trend_sma_days).mean()
    offensive["trend_distance"] = (price / offensive["trend_sma"]) - 1.0
    offensive["return_20d"] = price.pct_change(20)
    offensive["realized_vol_annualized"] = (
        returns.rolling(volatility_window_days).std() * np.sqrt(252.0)
    )

    rolling_high = price.cummax()
    offensive["drawdown"] = (price / rolling_high) - 1.0

    return offensive


def _create_stress_guard_inputs(
    offensive_result: pd.DataFrame,
    config: dict,
) -> dict[str, pd.Series]:
    phase_config = config.get("phase6_stress_confirmation_validation", {})
    phase4_guard_config = config.get("phase4_guarded_switch_diagnostic", {})
    overlay_config = config.get("regime_switch_overlay", {})

    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))
    volatility_window_days = int(phase_config.get("volatility_window_days", 20))

    state = _create_stress_state_frame(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
        volatility_window_days=volatility_window_days,
    )

    deep_drawdown_guard = _create_defensive_entry_guard_series(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
        guard_name="deep_drawdown_guard",
        near_high_drawdown_threshold=float(
            phase4_guard_config.get("near_high_drawdown_threshold", -0.05)
        ),
        near_high_min_trend_distance=float(
            phase4_guard_config.get("near_high_min_trend_distance", -0.01)
        ),
        deep_drawdown_threshold=float(
            phase4_guard_config.get("deep_drawdown_threshold", -0.20)
        ),
    )

    vol_stress = state["realized_vol_annualized"] >= float(
        phase_config.get("stress_vol_annualized_threshold", 0.20)
    )
    return_shock_stress = state["return_20d"] <= float(
        phase_config.get("stress_20d_return_threshold", -0.05)
    )
    trend_distance_stress = state["trend_distance"] <= float(
        phase_config.get("stress_trend_distance_threshold", -0.01)
    )

    composite_stress = (
        vol_stress.fillna(False)
        | return_shock_stress.fillna(False)
        | trend_distance_stress.fillna(False)
    )

    relief_condition = (
        (
            state["realized_vol_annualized"]
            <= float(phase_config.get("relief_vol_annualized_threshold", 0.18))
        )
        & (
            state["return_20d"]
            >= float(phase_config.get("relief_20d_return_threshold", -0.02))
        )
        & (
            state["trend_distance"]
            >= float(phase_config.get("relief_trend_distance_threshold", 0.00))
        )
    ).fillna(False)

    date_index = pd.to_datetime(state["date"])

    outputs = {
        "deep_drawdown_guard": deep_drawdown_guard.astype(bool),
        "vol_stress": vol_stress.fillna(False).astype(bool),
        "return_shock_stress": return_shock_stress.fillna(False).astype(bool),
        "trend_distance_stress": trend_distance_stress.fillna(False).astype(bool),
        "composite_stress": composite_stress.astype(bool),
        "relief_condition": relief_condition.astype(bool),
    }

    for key, series in outputs.items():
        series.index = date_index
        outputs[key] = series

    return outputs


def _variant_guard_inputs(
    variant_name: str,
    guards: dict[str, pd.Series],
) -> tuple[pd.Series | None, pd.Series | None, str, str]:
    deep_guard = guards["deep_drawdown_guard"]
    vol_stress = guards["vol_stress"]
    return_shock = guards["return_shock_stress"]
    trend_stress = guards["trend_distance_stress"]
    composite_stress = guards["composite_stress"]
    relief = guards["relief_condition"]

    if variant_name == "phase4_execution_candidate":
        return deep_guard, None, "deep_drawdown_guard", "none"

    if variant_name == "defensive_vol_stress_confirmation":
        return (
            deep_guard & vol_stress,
            None,
            "deep_drawdown_guard_and_vol_stress",
            "none",
        )

    if variant_name == "defensive_return_shock_confirmation":
        return (
            deep_guard & return_shock,
            None,
            "deep_drawdown_guard_and_return_shock",
            "none",
        )

    if variant_name == "defensive_trend_distance_confirmation":
        return (
            deep_guard & trend_stress,
            None,
            "deep_drawdown_guard_and_trend_distance_stress",
            "none",
        )

    if variant_name == "defensive_composite_stress_confirmation":
        return (
            deep_guard & composite_stress,
            None,
            "deep_drawdown_guard_and_composite_stress",
            "none",
        )

    if variant_name == "offensive_relief_confirmation":
        return (
            deep_guard,
            relief,
            "deep_drawdown_guard",
            "offensive_relief_confirmation",
        )

    if variant_name == "combined_composite_stress_relief_confirmation":
        return (
            deep_guard & composite_stress,
            relief,
            "deep_drawdown_guard_and_composite_stress",
            "offensive_relief_confirmation",
        )

    raise ValueError(f"Unknown stress confirmation variant: {variant_name}")


def _calculate_segment_metrics(
    result: pd.DataFrame,
    variant_name: str,
    strategy_name: str,
    initial_capital: float,
    segments: list[dict],
) -> pd.DataFrame:
    rows: list[dict] = []

    for segment in segments:
        sliced = _slice_and_rebase_result(
            result=result,
            start_date=segment["start_date"],
            end_date=segment["end_date"],
            initial_capital=initial_capital,
        )

        if sliced.empty:
            continue

        metrics = calculate_metrics(sliced, strategy_name)

        rows.append(
            {
                "period": segment["period"],
                "segment_type": segment["segment_type"],
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


def _create_stress_confirmation_summary(
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
                "segment_type": row["segment_type"],
                "variant_name": row["variant_name"],
                "benchmark_variant": benchmark_variant,
                "benchmark_cagr_pct": benchmark_row["cagr_pct"],
                "candidate_cagr_pct": row["cagr_pct"],
                "cagr_delta_pct_points": round(
                    float(row["cagr_pct"]) - float(benchmark_row["cagr_pct"]),
                    3,
                ),
                "benchmark_calmar": benchmark_row["calmar"],
                "candidate_calmar": row["calmar"],
                "calmar_delta": round(
                    float(row["calmar"]) - float(benchmark_row["calmar"]),
                    3,
                ),
                "benchmark_max_drawdown_pct": benchmark_row["max_drawdown_pct"],
                "candidate_max_drawdown_pct": row["max_drawdown_pct"],
                "drawdown_delta_pct_points": round(
                    float(row["max_drawdown_pct"])
                    - float(benchmark_row["max_drawdown_pct"]),
                    3,
                ),
                "benchmark_end_value": benchmark_row["end_value"],
                "candidate_end_value": row["end_value"],
                "end_value_delta": round(
                    float(row["end_value"]) - float(benchmark_row["end_value"]),
                    2,
                ),
                "benchmark_trade_count": benchmark_row["trade_count"],
                "candidate_trade_count": row["trade_count"],
                "trade_count_delta": int(row["trade_count"])
                - int(benchmark_row["trade_count"]),
            }
        )

    return pd.DataFrame(rows)


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


def _create_stress_confirmation_gate_report(
    summary: pd.DataFrame,
    event_summary: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    phase_config = config.get("phase6_stress_confirmation_validation", {})
    benchmark_variant = str(
        phase_config.get("benchmark_variant", "phase4_execution_candidate")
    )

    full = summary[summary["period"] == "full"].copy()
    holdout = summary[summary["period"] == "holdout"].copy()
    episode = summary[summary["segment_type"] == "episode"].copy()

    candidates = full[full["variant_name"] != benchmark_variant].copy()

    if candidates.empty:
        return pd.DataFrame()

    min_cagr_improvement = float(
        phase_config.get("min_full_cagr_improvement_pct_points", 0.15)
    )
    min_calmar_improvement = float(
        phase_config.get("min_full_calmar_improvement", 0.005)
    )
    max_holdout_cagr_damage = float(
        phase_config.get("max_allowed_holdout_cagr_damage_pct_points", -0.50)
    )
    max_holdout_calmar_damage = float(
        phase_config.get("max_allowed_holdout_calmar_damage", -0.05)
    )
    max_drawdown_damage = float(
        phase_config.get("max_allowed_drawdown_damage_pct_points", -0.50)
    )
    max_switch_count_delta = int(
        phase_config.get("max_allowed_switch_count_delta", 10)
    )

    candidates["score"] = (
        candidates["cagr_delta_pct_points"].astype(float)
        + candidates["calmar_delta"].astype(float)
        + candidates["drawdown_delta_pct_points"].astype(float) / 10.0
    )

    best_candidate = candidates.sort_values("score", ascending=False).iloc[0]
    best_variant = str(best_candidate["variant_name"])

    full_cagr_delta = float(best_candidate["cagr_delta_pct_points"])
    full_calmar_delta = float(best_candidate["calmar_delta"])
    full_drawdown_delta = float(best_candidate["drawdown_delta_pct_points"])

    passes_materiality = (
        full_cagr_delta >= min_cagr_improvement
        and full_calmar_delta >= min_calmar_improvement
        and full_drawdown_delta >= max_drawdown_damage
    )

    best_holdout = holdout[holdout["variant_name"] == best_variant]

    holdout_damage = False
    holdout_interpretation = "Holdout comparison unavailable."

    if not best_holdout.empty:
        holdout_row = best_holdout.iloc[0]
        holdout_cagr_delta = float(holdout_row["cagr_delta_pct_points"])
        holdout_calmar_delta = float(holdout_row["calmar_delta"])
        holdout_drawdown_delta = float(holdout_row["drawdown_delta_pct_points"])

        holdout_damage = (
            holdout_cagr_delta < max_holdout_cagr_damage
            or holdout_calmar_delta < max_holdout_calmar_damage
            or holdout_drawdown_delta < max_drawdown_damage
        )

        holdout_interpretation = (
            f"{best_variant} holdout CAGR delta was {holdout_cagr_delta}, "
            f"Calmar delta was {holdout_calmar_delta}, and drawdown delta was "
            f"{holdout_drawdown_delta}."
        )

    damaged_episode_count = 0
    episode_interpretation = "No episode-level comparison available."

    if not episode.empty:
        best_episode = episode[episode["variant_name"] == best_variant].copy()

        damaged_episode = best_episode[
            (best_episode["cagr_delta_pct_points"].astype(float) < max_holdout_cagr_damage)
            | (best_episode["calmar_delta"].astype(float) < max_holdout_calmar_damage)
            | (best_episode["drawdown_delta_pct_points"].astype(float) < max_drawdown_damage)
        ]

        damaged_episode_count = int(len(damaged_episode))

        if damaged_episode.empty:
            episode_interpretation = "No episode segment breached damage thresholds."
        else:
            damaged_names = ", ".join(damaged_episode["period"].astype(str).tolist())
            episode_interpretation = (
                f"{damaged_episode_count} episode segment(s) breached damage "
                f"thresholds: {damaged_names}."
            )

    benchmark_events = event_summary[
        event_summary["variant_name"] == benchmark_variant
    ]
    candidate_events = event_summary[event_summary["variant_name"] == best_variant]

    excessive_switch_change = False
    switch_interpretation = "Switch-count comparison unavailable."

    if not benchmark_events.empty and not candidate_events.empty:
        switch_delta = int(candidate_events.iloc[0]["switch_count"]) - int(
            benchmark_events.iloc[0]["switch_count"]
        )
        excessive_switch_change = abs(switch_delta) > max_switch_count_delta
        switch_interpretation = (
            f"{best_variant} changed switch count by {switch_delta} versus "
            f"{benchmark_variant}."
        )

    promotion_ready = (
        passes_materiality
        and not holdout_damage
        and damaged_episode_count == 0
        and not excessive_switch_change
    )

    return pd.DataFrame(
        [
            {
                "gate": "Best stress-confirmation variant passes materiality.",
                "status": "Passed" if passes_materiality else "Failed",
                "evidence_quality": "Required minimum full-period CAGR and Calmar improvement",
                "interpretation": (
                    f"Best variant was {best_variant}. Full-period CAGR delta was "
                    f"{full_cagr_delta}, Calmar delta was {full_calmar_delta}, "
                    f"and drawdown delta was {full_drawdown_delta}."
                ),
            },
            {
                "gate": "Best stress-confirmation variant avoids holdout damage.",
                "status": "Passed" if not holdout_damage else "Failed",
                "evidence_quality": "Checked holdout CAGR, Calmar, and drawdown deltas",
                "interpretation": holdout_interpretation,
            },
            {
                "gate": "Best stress-confirmation variant avoids episode-level damage.",
                "status": "Passed" if damaged_episode_count == 0 else "Failed",
                "evidence_quality": "Checked pre-declared episode segments",
                "interpretation": episode_interpretation,
            },
            {
                "gate": "Best stress-confirmation variant avoids excessive switch changes.",
                "status": "Passed" if not excessive_switch_change else "Failed",
                "evidence_quality": "Compared switch count against Phase 4 execution candidate",
                "interpretation": switch_interpretation,
            },
            {
                "gate": "Stress confirmation is validated for promotion.",
                "status": "Passed" if promotion_ready else "Not yet",
                "evidence_quality": "Requires materiality, holdout safety, episode safety, and reasonable switch count",
                "interpretation": (
                    f"{best_variant} passed all validation gates."
                    if promotion_ready
                    else f"{best_variant} did not pass all validation gates."
                ),
            },
        ]
    )


def _create_stress_confirmation_conclusion(
    gate_report: pd.DataFrame,
) -> pd.DataFrame:
    if gate_report.empty:
        return pd.DataFrame()

    final_gate = gate_report[
        gate_report["gate"] == "Stress confirmation is validated for promotion."
    ]

    final_status = final_gate.iloc[0]["status"] if not final_gate.empty else "Not yet"

    return pd.DataFrame(
        [
            {
                "claim": "SPY stress confirmation materially improves the Phase 4 execution candidate.",
                "status": "Survived" if final_status == "Passed" else "Failed",
                "evidence_quality": "Based on Phase 6A stress-confirmation validation gates",
                "interpretation": (
                    "A stress-confirmation variant passed all validation gates."
                    if final_status == "Passed"
                    else "No stress-confirmation variant passed all validation gates."
                ),
            },
            {
                "claim": "Stress confirmation should replace the Phase 4 execution candidate immediately.",
                "status": "Not yet",
                "evidence_quality": "Phase 6A is a diagnostic layer test",
                "interpretation": (
                    "Even if a variant passes, it should be documented as a candidate "
                    "and reviewed before replacing the execution-realistic baseline."
                ),
            },
            {
                "claim": "The next step should be external macro/sentiment/ML.",
                "status": "Not yet",
                "evidence_quality": "Only justified after the price-derived stress layer is documented",
                "interpretation": (
                    "External data should not be added until simple price-derived "
                    "stress confirmation has either been rejected or checkpointed."
                ),
            },
        ]
    )


def create_regime_switch_overlay_stress_confirmation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = config.get("phase6_stress_confirmation_validation", {})

    if not phase_config.get("enabled", False):
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

    overlay_config = config.get("regime_switch_overlay", {})
    overlay_name = str(overlay_config.get("name", "Regime Switch Overlay"))
    initial_capital = float(config["initial_capital"])
    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))
    confirmation_days = int(overlay_config.get("confirmation_days", 1))
    baseline_slippage_bps = float(config.get("slippage_bps", 5.0))

    benchmark_variant = str(
        phase_config.get("benchmark_variant", "phase4_execution_candidate")
    )

    variant_names = [
        benchmark_variant,
        "defensive_vol_stress_confirmation",
        "defensive_return_shock_confirmation",
        "defensive_trend_distance_confirmation",
        "defensive_composite_stress_confirmation",
        "offensive_relief_confirmation",
        "combined_composite_stress_relief_confirmation",
    ]

    segments = _segment_definitions(config)

    dynamic_config = config.get("phase4_dynamic_slippage", {})
    dynamic_slippage = _create_dynamic_slippage_series(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
        normal_bps=float(dynamic_config.get("normal_bps", 5.0)),
        below_200d_bps=float(dynamic_config.get("below_200d_bps", 15.0)),
        drawdown_10_bps=float(dynamic_config.get("drawdown_10_bps", 25.0)),
        drawdown_20_bps=float(dynamic_config.get("drawdown_20_bps", 50.0)),
    )

    guards = _create_stress_guard_inputs(
        offensive_result=offensive_result,
        config=config,
    )

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
            _calculate_segment_metrics(
                result=overlay_result,
                variant_name=variant_name,
                strategy_name=overlay_name,
                initial_capital=initial_capital,
                segments=segments,
            )
        )

        variant_events[variant_name] = _create_trade_event_audit(overlay_result)

    metrics = pd.concat(metric_frames, ignore_index=True)
    event_summary = _create_event_summary(variant_events)
    summary = _create_stress_confirmation_summary(
        metrics=metrics,
        benchmark_variant=benchmark_variant,
    )
    gate_report = _create_stress_confirmation_gate_report(
        summary=summary,
        event_summary=event_summary,
        config=config,
    )
    conclusion = _create_stress_confirmation_conclusion(gate_report)

    return {
        "metrics": metrics,
        "summary": summary,
        "event_summary": event_summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }


def write_regime_switch_overlay_stress_confirmation_markdown(
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

    content = f"""# Regime Switch Overlay Stress Confirmation Diagnostic

This Phase 6A report tests whether SPY price-derived stress confirmation improves the Phase 4 execution-realistic candidate.

Stress inputs are:

- 20D realised volatility,
- 20D SPY return shock,
- SPY distance from 200D trend.

## Metrics

{metrics.to_markdown(index=False) if not metrics.empty else "No metrics available."}

## Summary

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


def save_regime_switch_overlay_stress_confirmation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_stress_confirmation(
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

    metrics_path = reports_dir / "regime_switch_overlay_stress_confirmation_metrics.csv"
    summary_path = reports_dir / "regime_switch_overlay_stress_confirmation_summary.csv"
    event_summary_path = (
        reports_dir / "regime_switch_overlay_stress_confirmation_event_summary.csv"
    )
    gate_path = reports_dir / "regime_switch_overlay_stress_confirmation_gate_report.csv"
    conclusion_path = reports_dir / "phase6a_stress_confirmation_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_stress_confirmation.md"

    metrics.to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)
    event_summary.to_csv(event_summary_path, index=False)
    gate_report.to_csv(gate_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_stress_confirmation_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay stress-confirmation metrics:")
    print(metrics.to_string(index=False))

    print("\nRegime switch overlay stress-confirmation summary:")
    print(summary.to_string(index=False))

    print("\nRegime switch overlay stress-confirmation event summary:")
    print(event_summary.to_string(index=False))

    print("\nRegime switch overlay stress-confirmation gate report:")
    print(gate_report.to_string(index=False))

    print("\nPhase 6A stress-confirmation conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved stress-confirmation metrics to: {metrics_path}")
    print(f"Saved stress-confirmation summary to: {summary_path}")
    print(f"Saved stress-confirmation event summary to: {event_summary_path}")
    print(f"Saved stress-confirmation gate report to: {gate_path}")
    print(f"Saved Phase 6A conclusion to: {conclusion_path}")
    print(f"Saved stress-confirmation markdown to: {markdown_path}")

    return outputs