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
    _period_definitions,
    _slice_and_rebase_result,
)
from market_strats.analysis.regime_switch_overlay_switch_effectiveness import (
    _create_switch_effectiveness_events,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _normalise_switch_key(events: pd.DataFrame) -> pd.Series:
    return (
        pd.to_datetime(events["switch_date"]).dt.strftime("%Y-%m-%d")
        + "|"
        + events["from_mode"].astype(str)
        + "|"
        + events["to_mode"].astype(str)
    )


def _create_overlay_for_guard(
    offensive_result: pd.DataFrame,
    defensive_result: pd.DataFrame,
    config: dict,
    guard_name: str,
) -> pd.DataFrame:
    overlay_config = config.get("regime_switch_overlay", {})
    diagnostic_config = config.get("phase4_guarded_switch_diagnostic", {})

    initial_capital = float(config["initial_capital"])
    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))
    confirmation_days = int(overlay_config.get("confirmation_days", 1))
    baseline_slippage_bps = float(config.get("slippage_bps", 5.0))

    dynamic_config = config.get("phase4_dynamic_slippage", {})
    dynamic_slippage = _create_dynamic_slippage_series(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
        normal_bps=float(dynamic_config.get("normal_bps", 5.0)),
        below_200d_bps=float(dynamic_config.get("below_200d_bps", 15.0)),
        drawdown_10_bps=float(dynamic_config.get("drawdown_10_bps", 25.0)),
        drawdown_20_bps=float(dynamic_config.get("drawdown_20_bps", 50.0)),
    )

    if guard_name == "baseline_no_guard":
        defensive_entry_allowed = None
    else:
        defensive_entry_allowed = _create_defensive_entry_guard_series(
            offensive_result=offensive_result,
            trend_sma_days=trend_sma_days,
            guard_name=guard_name,
            near_high_drawdown_threshold=float(
                diagnostic_config.get("near_high_drawdown_threshold", -0.05)
            ),
            near_high_min_trend_distance=float(
                diagnostic_config.get("near_high_min_trend_distance", -0.01)
            ),
            deep_drawdown_threshold=float(
                diagnostic_config.get("deep_drawdown_threshold", -0.20)
            ),
        )

    return run_spy_trend_regime_switch_overlay(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        initial_capital=initial_capital,
        trend_sma_days=trend_sma_days,
        slippage_bps=baseline_slippage_bps,
        confirmation_days=confirmation_days,
        dynamic_slippage_bps=dynamic_slippage,
        defensive_entry_allowed=defensive_entry_allowed,
        defensive_entry_guard_name=guard_name,
    )


def _calculate_guard_validation_metrics(
    overlay_result: pd.DataFrame,
    guard_name: str,
    strategy_name: str,
    initial_capital: float,
    reference_end_date: str,
    holdout_start_date: str,
) -> pd.DataFrame:
    rows: list[dict] = []

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
                "guard_name": guard_name,
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


def _create_guard_validation_summary(
    metrics: pd.DataFrame,
    benchmark_guard: str,
    candidate_guard: str,
) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()

    benchmark = metrics[metrics["guard_name"] == benchmark_guard]
    candidate = metrics[metrics["guard_name"] == candidate_guard]

    if benchmark.empty or candidate.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for period in sorted(set(benchmark["period"]).intersection(candidate["period"])):
        benchmark_row = benchmark[benchmark["period"] == period].iloc[0]
        candidate_row = candidate[candidate["period"] == period].iloc[0]

        rows.append(
            {
                "period": period,
                "benchmark_guard": benchmark_guard,
                "candidate_guard": candidate_guard,
                "benchmark_cagr_pct": benchmark_row["cagr_pct"],
                "candidate_cagr_pct": candidate_row["cagr_pct"],
                "cagr_delta_pct_points": round(
                    float(candidate_row["cagr_pct"])
                    - float(benchmark_row["cagr_pct"]),
                    3,
                ),
                "benchmark_calmar": benchmark_row["calmar"],
                "candidate_calmar": candidate_row["calmar"],
                "calmar_delta": round(
                    float(candidate_row["calmar"]) - float(benchmark_row["calmar"]),
                    3,
                ),
                "benchmark_max_drawdown_pct": benchmark_row["max_drawdown_pct"],
                "candidate_max_drawdown_pct": candidate_row["max_drawdown_pct"],
                "drawdown_delta_pct_points": round(
                    float(candidate_row["max_drawdown_pct"])
                    - float(benchmark_row["max_drawdown_pct"]),
                    3,
                ),
                "benchmark_end_value": benchmark_row["end_value"],
                "candidate_end_value": candidate_row["end_value"],
                "end_value_delta": round(
                    float(candidate_row["end_value"])
                    - float(benchmark_row["end_value"]),
                    2,
                ),
                "benchmark_trade_count": benchmark_row["trade_count"],
                "candidate_trade_count": candidate_row["trade_count"],
                "trade_count_delta": int(candidate_row["trade_count"])
                - int(benchmark_row["trade_count"]),
            }
        )

    return pd.DataFrame(rows)


def _create_removed_switch_audit(
    benchmark_events: pd.DataFrame,
    candidate_events: pd.DataFrame,
    benchmark_effectiveness_events: pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    if benchmark_events.empty:
        return pd.DataFrame()

    benchmark = benchmark_events.copy()
    candidate = candidate_events.copy()
    effectiveness = benchmark_effectiveness_events.copy()

    benchmark["switch_key"] = _normalise_switch_key(benchmark)
    candidate["switch_key"] = _normalise_switch_key(candidate) if not candidate.empty else ""

    removed = benchmark[~benchmark["switch_key"].isin(set(candidate["switch_key"]))].copy()

    if removed.empty:
        return pd.DataFrame()

    if not effectiveness.empty:
        effectiveness["switch_key"] = _normalise_switch_key(effectiveness)

        columns_to_merge = [
            "switch_key",
            "transition",
            "applied_overlay_slippage_bps",
            "overlay_slippage_cost_pct",
        ]

        for horizon in horizons:
            columns_to_merge.extend(
                [
                    f"actual_next_{horizon}d_return_pct",
                    f"stay_previous_next_{horizon}d_return_pct",
                    f"switch_value_added_{horizon}d_pct_points",
                    f"switch_helped_{horizon}d",
                ]
            )

        merge_columns = [column for column in columns_to_merge if column in effectiveness.columns]

        removed = removed.merge(
            effectiveness[merge_columns],
            on="switch_key",
            how="left",
            suffixes=("", "_effectiveness"),
        )

    output_columns = [
        "switch_date",
        "from_mode",
        "to_mode",
        "spy_distance_from_trend_pct",
        "spy_drawdown_pct",
        "applied_overlay_slippage_bps",
        "overlay_slippage_cost_pct",
    ]

    for horizon in horizons:
        output_columns.extend(
            [
                f"switch_value_added_{horizon}d_pct_points",
                f"switch_helped_{horizon}d",
            ]
        )

    existing_columns = [column for column in output_columns if column in removed.columns]
    output = removed[existing_columns].copy()

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.reset_index(drop=True)


def _summarise_removed_switches(
    removed_switches: pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    if removed_switches.empty:
        return pd.DataFrame(
            [
                {
                    "removed_switch_count": 0,
                    "avg_removed_slippage_bps": "",
                    "avg_removed_drawdown_pct": "",
                }
            ]
        )

    row: dict = {
        "removed_switch_count": int(len(removed_switches)),
        "avg_removed_slippage_bps": round(
            float(pd.to_numeric(removed_switches["applied_overlay_slippage_bps"]).mean()),
            3,
        ),
        "avg_removed_drawdown_pct": round(
            float(pd.to_numeric(removed_switches["spy_drawdown_pct"]).mean()),
            3,
        ),
    }

    for horizon in horizons:
        value_column = f"switch_value_added_{horizon}d_pct_points"
        helped_column = f"switch_helped_{horizon}d"

        if value_column not in removed_switches.columns:
            row[f"avg_removed_value_added_{horizon}d_pct_points"] = ""
            row[f"removed_helped_{horizon}d_pct"] = ""
            continue

        values = pd.to_numeric(
            removed_switches[value_column].replace("", np.nan),
            errors="coerce",
        )
        helped = removed_switches[helped_column].astype(str).str.lower().eq("true")

        valid = values.notna()

        if not valid.any():
            row[f"avg_removed_value_added_{horizon}d_pct_points"] = ""
            row[f"removed_helped_{horizon}d_pct"] = ""
            continue

        row[f"avg_removed_value_added_{horizon}d_pct_points"] = round(
            float(values[valid].mean()),
            3,
        )
        row[f"removed_helped_{horizon}d_pct"] = round(
            float(helped[valid].mean()) * 100.0,
            3,
        )

    return pd.DataFrame([row])


def _create_guard_validation_conclusion(
    summary: pd.DataFrame,
    removed_summary: pd.DataFrame,
    candidate_guard: str,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    full = summary[summary["period"] == "full"]
    holdout = summary[summary["period"] == "holdout"]

    if full.empty:
        return pd.DataFrame()

    full_row = full.iloc[0]
    holdout_row = holdout.iloc[0] if not holdout.empty else None

    full_cagr_delta = float(full_row["cagr_delta_pct_points"])
    full_calmar_delta = float(full_row["calmar_delta"])
    full_drawdown_delta = float(full_row["drawdown_delta_pct_points"])

    holdout_cagr_delta = (
        float(holdout_row["cagr_delta_pct_points"]) if holdout_row is not None else np.nan
    )
    holdout_calmar_delta = (
        float(holdout_row["calmar_delta"]) if holdout_row is not None else np.nan
    )
    holdout_drawdown_delta = (
        float(holdout_row["drawdown_delta_pct_points"])
        if holdout_row is not None
        else np.nan
    )

    improves_full = (
        full_cagr_delta > 0
        and full_calmar_delta > 0
        and full_drawdown_delta >= -0.5
    )

    damages_holdout = (
        pd.notna(holdout_cagr_delta)
        and (
            holdout_cagr_delta < -0.25
            or holdout_calmar_delta < -0.025
            or holdout_drawdown_delta < -1.0
        )
    )

    removed_switches_bad = False
    removed_interpretation = "No removed switch summary available."

    if not removed_summary.empty:
        removed_row = removed_summary.iloc[0]
        removed_count = int(removed_row["removed_switch_count"])
        avg_removed_20d = removed_row.get("avg_removed_value_added_20d_pct_points", "")
        helped_removed_20d = removed_row.get("removed_helped_20d_pct", "")

        if avg_removed_20d != "" and helped_removed_20d != "":
            avg_removed_20d_float = float(avg_removed_20d)
            helped_removed_20d_float = float(helped_removed_20d)
            removed_switches_bad = (
                removed_count > 0
                and avg_removed_20d_float < 0
                and helped_removed_20d_float < 50
            )
            removed_interpretation = (
                f"{candidate_guard} removed {removed_count} switches. Removed "
                f"switches had average 20D value added of {avg_removed_20d_float} "
                f"percentage points and helped {helped_removed_20d_float}% of "
                "valid 20D events."
            )
        else:
            removed_interpretation = (
                f"{candidate_guard} removed {removed_count} switches, but valid "
                "20D switch-effectiveness data was unavailable."
            )

    return pd.DataFrame(
        [
            {
                "claim": "Candidate guard improves full-period dynamic baseline.",
                "status": "Survived" if improves_full else "Failed",
                "evidence_quality": "Compared candidate guard against no-guard dynamic baseline",
                "interpretation": (
                    f"{candidate_guard} changed full-period CAGR by "
                    f"{full_cagr_delta} percentage points, Calmar by "
                    f"{full_calmar_delta}, and max drawdown by "
                    f"{full_drawdown_delta} percentage points."
                ),
            },
            {
                "claim": "Candidate guard avoids damaging holdout performance.",
                "status": "Survived" if not damages_holdout else "Failed",
                "evidence_quality": "Checked holdout CAGR, Calmar, and drawdown deltas",
                "interpretation": (
                    f"Holdout CAGR delta was {holdout_cagr_delta}, Calmar delta "
                    f"was {holdout_calmar_delta}, and drawdown delta was "
                    f"{holdout_drawdown_delta}."
                ),
            },
            {
                "claim": "Removed switches were genuinely harmful.",
                "status": "Survived" if removed_switches_bad else "Failed",
                "evidence_quality": "Reviewed switches present in baseline but removed by candidate guard",
                "interpretation": removed_interpretation,
            },
            {
                "claim": "Candidate guard is ready to replace the baseline overlay.",
                "status": "Not yet",
                "evidence_quality": "Phase 4E validates the candidate but does not complete promotion",
                "interpretation": (
                    "A promotion decision still needs segment robustness and updated "
                    "README/checkpoint documentation. Do not silently replace the "
                    "canonical 3D overlay yet."
                ),
            },
        ]
    )


def create_regime_switch_overlay_guard_validation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    validation_config = config.get("phase4_guard_validation", {})

    if not validation_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "removed_switches": pd.DataFrame(),
            "removed_summary": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    candidate_guard = str(validation_config.get("candidate_guard", "deep_drawdown_guard"))
    benchmark_guard = str(validation_config.get("benchmark_guard", "baseline_no_guard"))
    horizons = [int(value) for value in validation_config.get("horizons", [5, 20, 60])]

    overlay_config = config.get("regime_switch_overlay", {})
    overlay_name = str(overlay_config.get("name", "Regime Switch Overlay"))
    initial_capital = float(config["initial_capital"])
    reference_end_date = str(validation_config["reference_end_date"])
    holdout_start_date = str(validation_config["holdout_start_date"])

    benchmark_overlay = _create_overlay_for_guard(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        config=config,
        guard_name=benchmark_guard,
    )
    candidate_overlay = _create_overlay_for_guard(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        config=config,
        guard_name=candidate_guard,
    )

    benchmark_metrics = _calculate_guard_validation_metrics(
        overlay_result=benchmark_overlay,
        guard_name=benchmark_guard,
        strategy_name=overlay_name,
        initial_capital=initial_capital,
        reference_end_date=reference_end_date,
        holdout_start_date=holdout_start_date,
    )
    candidate_metrics = _calculate_guard_validation_metrics(
        overlay_result=candidate_overlay,
        guard_name=candidate_guard,
        strategy_name=overlay_name,
        initial_capital=initial_capital,
        reference_end_date=reference_end_date,
        holdout_start_date=holdout_start_date,
    )

    metrics = pd.concat([benchmark_metrics, candidate_metrics], ignore_index=True)
    summary = _create_guard_validation_summary(
        metrics=metrics,
        benchmark_guard=benchmark_guard,
        candidate_guard=candidate_guard,
    )

    benchmark_events = _create_trade_event_audit(benchmark_overlay)
    candidate_events = _create_trade_event_audit(candidate_overlay)
    benchmark_effectiveness_events = _create_switch_effectiveness_events(
        overlay_result=benchmark_overlay,
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        horizons=horizons,
    )

    removed_switches = _create_removed_switch_audit(
        benchmark_events=benchmark_events,
        candidate_events=candidate_events,
        benchmark_effectiveness_events=benchmark_effectiveness_events,
        horizons=horizons,
    )
    removed_summary = _summarise_removed_switches(
        removed_switches=removed_switches,
        horizons=horizons,
    )
    conclusion = _create_guard_validation_conclusion(
        summary=summary,
        removed_summary=removed_summary,
        candidate_guard=candidate_guard,
    )

    return {
        "metrics": metrics,
        "summary": summary,
        "removed_switches": removed_switches,
        "removed_summary": removed_summary,
        "conclusion": conclusion,
    }


def write_regime_switch_overlay_guard_validation_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = outputs.get("metrics", pd.DataFrame())
    summary = outputs.get("summary", pd.DataFrame())
    removed_switches = outputs.get("removed_switches", pd.DataFrame())
    removed_summary = outputs.get("removed_summary", pd.DataFrame())
    conclusion = outputs.get("conclusion", pd.DataFrame())

    content = f"""# Regime Switch Overlay Guard Validation

This Phase 4E report validates whether the candidate guarded switch rule improved the dynamic stress-slippage baseline for the right reason.

It compares:

- baseline_no_guard
- candidate guard

It also audits the switches removed by the candidate guard.

## Metrics

{metrics.to_markdown(index=False) if not metrics.empty else "No metrics available."}

## Summary

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Removed Switch Summary

{removed_summary.to_markdown(index=False) if not removed_summary.empty else "No removed-switch summary available."}

## Removed Switches

{removed_switches.to_markdown(index=False) if not removed_switches.empty else "No removed switches."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_guard_validation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_guard_validation(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    metrics = outputs["metrics"]
    summary = outputs["summary"]
    removed_switches = outputs["removed_switches"]
    removed_summary = outputs["removed_summary"]
    conclusion = outputs["conclusion"]

    if metrics.empty:
        return outputs

    metrics_path = reports_dir / "regime_switch_overlay_guard_validation_metrics.csv"
    summary_path = reports_dir / "regime_switch_overlay_guard_validation_summary.csv"
    removed_path = reports_dir / "regime_switch_overlay_removed_switch_audit.csv"
    removed_summary_path = (
        reports_dir / "regime_switch_overlay_removed_switch_summary.csv"
    )
    conclusion_path = reports_dir / "phase4e_guard_validation_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_guard_validation.md"

    metrics.to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)
    removed_switches.to_csv(removed_path, index=False)
    removed_summary.to_csv(removed_summary_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_guard_validation_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay guard-validation summary:")
    print(summary.to_string(index=False))

    print("\nRemoved switch summary:")
    print(removed_summary.to_string(index=False))

    print("\nPhase 4E guard-validation conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved guard-validation metrics to: {metrics_path}")
    print(f"Saved guard-validation summary to: {summary_path}")
    print(f"Saved removed-switch audit to: {removed_path}")
    print(f"Saved removed-switch summary to: {removed_summary_path}")
    print(f"Saved Phase 4E conclusion to: {conclusion_path}")
    print(f"Saved guard-validation markdown to: {markdown_path}")

    return outputs