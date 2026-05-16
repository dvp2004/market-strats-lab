from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.regime_switch_overlay_breadth_confirmation import (
    _align_breadth_to_dates,
    _create_risk_asset_breadth_frame,
)
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
from market_strats.analysis.regime_switch_overlay_switch_effectiveness import (
    _create_switch_effectiveness_events,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _segment_definitions(config: dict) -> list[dict]:
    phase_config = config.get("phase5_breadth_materiality_validation", {})

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


def _normalise_switch_key(events: pd.DataFrame) -> pd.Series:
    return (
        pd.to_datetime(events["switch_date"]).dt.strftime("%Y-%m-%d")
        + "|"
        + events["from_mode"].astype(str)
        + "|"
        + events["to_mode"].astype(str)
    )


def _create_base_guard_inputs(
    offensive_result: pd.DataFrame,
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.Series]:
    phase5_config = config.get("phase5_breadth_confirmation", {})
    phase4_guard_config = config.get("phase4_guarded_switch_diagnostic", {})
    overlay_config = config.get("regime_switch_overlay", {})

    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))
    breadth_sma_days = int(phase5_config.get("breadth_sma_days", 200))

    risk_assets = [str(ticker).upper() for ticker in phase5_config["risk_assets"]]

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
            phase4_guard_config.get("near_high_drawdown_threshold", -0.05)
        ),
        near_high_min_trend_distance=float(
            phase4_guard_config.get("near_high_min_trend_distance", -0.01)
        ),
        deep_drawdown_threshold=float(
            phase4_guard_config.get("deep_drawdown_threshold", -0.20)
        ),
    )

    breadth.index = pd.to_datetime(offensive["date"])

    return {
        "deep_drawdown_guard": deep_drawdown_guard.astype(bool),
        "risk_asset_breadth_pct": breadth.astype(float),
    }


def _variant_name_for_threshold(threshold: float) -> str:
    threshold_label = f"{threshold:.2f}".replace(".", "_")

    return f"defensive_breadth_threshold_{threshold_label}"


def _create_overlay_for_variant(
    offensive_result: pd.DataFrame,
    defensive_result: pd.DataFrame,
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    variant_name: str,
    defensive_breadth_threshold: float | None,
) -> pd.DataFrame:
    overlay_config = config.get("regime_switch_overlay", {})

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

    guard_inputs = _create_base_guard_inputs(
        offensive_result=offensive_result,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    deep_drawdown_guard = guard_inputs["deep_drawdown_guard"]

    if variant_name == "phase4_execution_candidate":
        defensive_entry_allowed = deep_drawdown_guard
        defensive_guard_name = "deep_drawdown_guard"

    elif defensive_breadth_threshold is not None:
        breadth_condition = (
            guard_inputs["risk_asset_breadth_pct"] <= defensive_breadth_threshold
        )
        defensive_entry_allowed = deep_drawdown_guard & breadth_condition
        defensive_guard_name = (
            f"deep_drawdown_guard_and_defensive_breadth_{defensive_breadth_threshold:.2f}"
        )

    else:
        raise ValueError(
            "defensive_breadth_threshold must be supplied for breadth variants"
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
        defensive_entry_guard_name=defensive_guard_name,
    )


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


def _create_materiality_summary(
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


def _create_changed_switch_audit(
    benchmark_events: pd.DataFrame,
    candidate_events: pd.DataFrame,
    benchmark_effectiveness: pd.DataFrame,
    candidate_effectiveness: pd.DataFrame,
    candidate_variant: str,
) -> pd.DataFrame:
    if benchmark_events.empty and candidate_events.empty:
        return pd.DataFrame()

    benchmark = benchmark_events.copy()
    candidate = candidate_events.copy()

    benchmark["switch_key"] = (
        _normalise_switch_key(benchmark) if not benchmark.empty else pd.Series()
    )
    candidate["switch_key"] = (
        _normalise_switch_key(candidate) if not candidate.empty else pd.Series()
    )

    benchmark_keys = set(benchmark["switch_key"]) if not benchmark.empty else set()
    candidate_keys = set(candidate["switch_key"]) if not candidate.empty else set()

    removed = benchmark[~benchmark["switch_key"].isin(candidate_keys)].copy()
    added = candidate[~candidate["switch_key"].isin(benchmark_keys)].copy()

    removed["change_type"] = "removed_from_benchmark"
    added["change_type"] = "added_by_candidate"

    if not benchmark_effectiveness.empty:
        benchmark_effectiveness = benchmark_effectiveness.copy()
        benchmark_effectiveness["switch_key"] = _normalise_switch_key(
            benchmark_effectiveness
        )
        removed = removed.merge(
            benchmark_effectiveness[
                [
                    column
                    for column in benchmark_effectiveness.columns
                    if column.startswith("switch_value_added_")
                    or column.startswith("switch_helped_")
                    or column == "switch_key"
                ]
            ],
            on="switch_key",
            how="left",
        )

    if not candidate_effectiveness.empty:
        candidate_effectiveness = candidate_effectiveness.copy()
        candidate_effectiveness["switch_key"] = _normalise_switch_key(
            candidate_effectiveness
        )
        added = added.merge(
            candidate_effectiveness[
                [
                    column
                    for column in candidate_effectiveness.columns
                    if column.startswith("switch_value_added_")
                    or column.startswith("switch_helped_")
                    or column == "switch_key"
                ]
            ],
            on="switch_key",
            how="left",
        )

    changed = pd.concat([removed, added], ignore_index=True)

    if changed.empty:
        return pd.DataFrame()

    changed["candidate_variant"] = candidate_variant

    columns = [
        "candidate_variant",
        "change_type",
        "switch_date",
        "from_mode",
        "to_mode",
        "spy_distance_from_trend_pct",
        "spy_drawdown_pct",
        "applied_overlay_slippage_bps",
        "overlay_slippage_cost_pct",
        "switch_value_added_5d_pct_points",
        "switch_helped_5d",
        "switch_value_added_20d_pct_points",
        "switch_helped_20d",
        "switch_value_added_60d_pct_points",
        "switch_helped_60d",
    ]

    existing_columns = [column for column in columns if column in changed.columns]

    return changed[existing_columns].reset_index(drop=True)


def _summarise_changed_switches(changed_switches: pd.DataFrame) -> pd.DataFrame:
    if changed_switches.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for (variant_name, change_type), group_df in changed_switches.groupby(
        ["candidate_variant", "change_type"]
    ):
        row: dict = {
            "candidate_variant": variant_name,
            "change_type": change_type,
            "switch_count": int(len(group_df)),
            "avg_applied_slippage_bps": round(
                float(pd.to_numeric(group_df["applied_overlay_slippage_bps"]).mean()),
                3,
            ),
            "avg_spy_drawdown_pct": round(
                float(pd.to_numeric(group_df["spy_drawdown_pct"]).mean()),
                3,
            ),
        }

        for horizon in [5, 20, 60]:
            value_column = f"switch_value_added_{horizon}d_pct_points"
            helped_column = f"switch_helped_{horizon}d"

            if value_column not in group_df.columns:
                row[f"avg_value_added_{horizon}d_pct_points"] = ""
                row[f"helped_{horizon}d_pct"] = ""
                continue

            values = pd.to_numeric(
                group_df[value_column].replace("", np.nan),
                errors="coerce",
            )
            helped = group_df[helped_column].astype(str).str.lower().eq("true")
            valid = values.notna()

            if not valid.any():
                row[f"avg_value_added_{horizon}d_pct_points"] = ""
                row[f"helped_{horizon}d_pct"] = ""
                continue

            row[f"avg_value_added_{horizon}d_pct_points"] = round(
                float(values[valid].mean()),
                3,
            )
            row[f"helped_{horizon}d_pct"] = round(
                float(helped[valid].mean()) * 100.0,
                3,
            )

        rows.append(row)

    return pd.DataFrame(rows)


def _create_materiality_gate_report(
    summary: pd.DataFrame,
    event_summary: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    phase_config = config.get("phase5_breadth_materiality_validation", {})
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

    candidates["materiality_score"] = (
        candidates["cagr_delta_pct_points"].astype(float)
        + candidates["calmar_delta"].astype(float)
        + candidates["drawdown_delta_pct_points"].astype(float) / 10.0
    )

    best_candidate = candidates.sort_values(
        "materiality_score",
        ascending=False,
    ).iloc[0]

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

    switch_interpretation = "Switch-count comparison unavailable."
    excessive_switch_change = False

    if not benchmark_events.empty and not candidate_events.empty:
        switch_delta = int(candidate_events.iloc[0]["switch_count"]) - int(
            benchmark_events.iloc[0]["switch_count"]
        )
        excessive_switch_change = abs(switch_delta) > 10
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
                "gate": "Best defensive breadth threshold passes materiality.",
                "status": "Passed" if passes_materiality else "Failed",
                "evidence_quality": "Required minimum full-period CAGR and Calmar improvement",
                "interpretation": (
                    f"Best threshold variant was {best_variant}. Full-period "
                    f"CAGR delta was {full_cagr_delta}, Calmar delta was "
                    f"{full_calmar_delta}, and drawdown delta was "
                    f"{full_drawdown_delta}. Required CAGR delta >= "
                    f"{min_cagr_improvement} and Calmar delta >= "
                    f"{min_calmar_improvement}."
                ),
            },
            {
                "gate": "Best defensive breadth threshold avoids holdout damage.",
                "status": "Passed" if not holdout_damage else "Failed",
                "evidence_quality": "Checked holdout CAGR, Calmar, and drawdown deltas",
                "interpretation": holdout_interpretation,
            },
            {
                "gate": "Best defensive breadth threshold avoids episode-level damage.",
                "status": "Passed" if damaged_episode_count == 0 else "Failed",
                "evidence_quality": "Checked pre-declared episode segments",
                "interpretation": episode_interpretation,
            },
            {
                "gate": "Best defensive breadth threshold avoids excessive switch changes.",
                "status": "Passed" if not excessive_switch_change else "Failed",
                "evidence_quality": "Compared switch count against Phase 4 execution candidate",
                "interpretation": switch_interpretation,
            },
            {
                "gate": "Defensive breadth confirmation is validated for promotion.",
                "status": "Passed" if promotion_ready else "Not yet",
                "evidence_quality": "Requires materiality, holdout safety, episode safety, and reasonable switch count",
                "interpretation": (
                    f"{best_variant} passed all materiality-validation gates."
                    if promotion_ready
                    else f"{best_variant} did not pass all materiality-validation gates."
                ),
            },
        ]
    )


def _create_materiality_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    if gate_report.empty:
        return pd.DataFrame()

    final_gate = gate_report[
        gate_report["gate"] == "Defensive breadth confirmation is validated for promotion."
    ]

    final_status = final_gate.iloc[0]["status"] if not final_gate.empty else "Not yet"

    return pd.DataFrame(
        [
            {
                "claim": "Defensive breadth confirmation is materially useful.",
                "status": "Survived" if final_status == "Passed" else "Failed",
                "evidence_quality": "Based on Phase 5B materiality-validation gates",
                "interpretation": (
                    "A defensive breadth threshold passed all materiality gates."
                    if final_status == "Passed"
                    else "Defensive breadth did not pass the stricter materiality gates."
                ),
            },
            {
                "claim": "Phase 5A's small improvement was enough for promotion.",
                "status": "Failed" if final_status != "Passed" else "Survived",
                "evidence_quality": "Checked stricter materiality and robustness conditions",
                "interpretation": (
                    "Small improvements must pass materiality and robustness checks "
                    "before promotion."
                ),
            },
            {
                "claim": "The next step should be macro/sentiment/ML.",
                "status": "Not yet",
                "evidence_quality": "Only justified after documenting whether breadth is rejected or promoted",
                "interpretation": (
                    "Do not add external complexity until the breadth materiality "
                    "result is documented."
                ),
            },
        ]
    )


def create_regime_switch_overlay_breadth_materiality_validation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = config.get("phase5_breadth_materiality_validation", {})

    if not phase_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "event_summary": pd.DataFrame(),
            "changed_switches": pd.DataFrame(),
            "changed_switch_summary": pd.DataFrame(),
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

    benchmark_variant = str(
        phase_config.get("benchmark_variant", "phase4_execution_candidate")
    )
    thresholds = [float(value) for value in phase_config["breadth_thresholds"]]
    segments = _segment_definitions(config)

    variant_specs: list[tuple[str, float | None]] = [
        (benchmark_variant, None),
    ]

    for threshold in thresholds:
        variant_specs.append((_variant_name_for_threshold(threshold), threshold))

    metric_frames: list[pd.DataFrame] = []
    variant_events: dict[str, pd.DataFrame] = {}
    variant_effectiveness: dict[str, pd.DataFrame] = {}
    overlay_results: dict[str, pd.DataFrame] = {}

    for variant_name, threshold in variant_specs:
        overlay_result = _create_overlay_for_variant(
            offensive_result=offensive_result,
            defensive_result=defensive_result,
            ticker_outputs=ticker_outputs,
            config=config,
            variant_name=variant_name,
            defensive_breadth_threshold=threshold,
        )

        overlay_results[variant_name] = overlay_result
        variant_events[variant_name] = _create_trade_event_audit(overlay_result)
        variant_effectiveness[variant_name] = _create_switch_effectiveness_events(
            overlay_result=overlay_result,
            offensive_result=offensive_result,
            defensive_result=defensive_result,
            horizons=[5, 20, 60],
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

    metrics = pd.concat(metric_frames, ignore_index=True)
    event_summary = _create_event_summary(variant_events)
    summary = _create_materiality_summary(
        metrics=metrics,
        benchmark_variant=benchmark_variant,
    )

    changed_frames: list[pd.DataFrame] = []
    benchmark_events = variant_events[benchmark_variant]
    benchmark_effectiveness = variant_effectiveness[benchmark_variant]

    for variant_name, _threshold in variant_specs:
        if variant_name == benchmark_variant:
            continue

        changed = _create_changed_switch_audit(
            benchmark_events=benchmark_events,
            candidate_events=variant_events[variant_name],
            benchmark_effectiveness=benchmark_effectiveness,
            candidate_effectiveness=variant_effectiveness[variant_name],
            candidate_variant=variant_name,
        )

        if not changed.empty:
            changed_frames.append(changed)

    changed_switches = (
        pd.concat(changed_frames, ignore_index=True)
        if changed_frames
        else pd.DataFrame()
    )
    changed_switch_summary = _summarise_changed_switches(changed_switches)

    gate_report = _create_materiality_gate_report(
        summary=summary,
        event_summary=event_summary,
        config=config,
    )
    conclusion = _create_materiality_conclusion(gate_report)

    return {
        "metrics": metrics,
        "summary": summary,
        "event_summary": event_summary,
        "changed_switches": changed_switches,
        "changed_switch_summary": changed_switch_summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }


def write_regime_switch_overlay_breadth_materiality_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = outputs.get("metrics", pd.DataFrame())
    summary = outputs.get("summary", pd.DataFrame())
    event_summary = outputs.get("event_summary", pd.DataFrame())
    changed_switch_summary = outputs.get("changed_switch_summary", pd.DataFrame())
    gate_report = outputs.get("gate_report", pd.DataFrame())
    conclusion = outputs.get("conclusion", pd.DataFrame())

    content = f"""# Regime Switch Overlay Breadth Materiality Validation

This Phase 5B report tests whether the small Phase 5A defensive-breadth improvement is material and robust.

It compares defensive breadth thresholds against the Phase 4 execution-realistic candidate.

## Metrics

{metrics.to_markdown(index=False) if not metrics.empty else "No metrics available."}

## Summary

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Event Summary

{event_summary.to_markdown(index=False) if not event_summary.empty else "No event summary available."}

## Changed Switch Summary

{changed_switch_summary.to_markdown(index=False) if not changed_switch_summary.empty else "No changed-switch summary available."}

## Gate Report

{gate_report.to_markdown(index=False) if not gate_report.empty else "No gate report available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_breadth_materiality_validation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_breadth_materiality_validation(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    metrics = outputs["metrics"]
    summary = outputs["summary"]
    event_summary = outputs["event_summary"]
    changed_switches = outputs["changed_switches"]
    changed_switch_summary = outputs["changed_switch_summary"]
    gate_report = outputs["gate_report"]
    conclusion = outputs["conclusion"]

    if metrics.empty:
        return outputs

    metrics_path = reports_dir / "regime_switch_overlay_breadth_materiality_metrics.csv"
    summary_path = reports_dir / "regime_switch_overlay_breadth_materiality_summary.csv"
    event_summary_path = (
        reports_dir / "regime_switch_overlay_breadth_materiality_event_summary.csv"
    )
    changed_switches_path = (
        reports_dir / "regime_switch_overlay_breadth_changed_switch_audit.csv"
    )
    changed_switch_summary_path = (
        reports_dir / "regime_switch_overlay_breadth_changed_switch_summary.csv"
    )
    gate_path = reports_dir / "regime_switch_overlay_breadth_materiality_gate_report.csv"
    conclusion_path = reports_dir / "phase5b_breadth_materiality_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_breadth_materiality.md"

    metrics.to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)
    event_summary.to_csv(event_summary_path, index=False)
    changed_switches.to_csv(changed_switches_path, index=False)
    changed_switch_summary.to_csv(changed_switch_summary_path, index=False)
    gate_report.to_csv(gate_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_breadth_materiality_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay breadth-materiality metrics:")
    print(metrics.to_string(index=False))

    print("\nRegime switch overlay breadth-materiality summary:")
    print(summary.to_string(index=False))

    print("\nRegime switch overlay breadth-materiality event summary:")
    print(event_summary.to_string(index=False))

    print("\nRegime switch overlay breadth changed-switch summary:")
    print(changed_switch_summary.to_string(index=False))

    print("\nRegime switch overlay breadth-materiality gate report:")
    print(gate_report.to_string(index=False))

    print("\nPhase 5B breadth-materiality conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved breadth-materiality metrics to: {metrics_path}")
    print(f"Saved breadth-materiality summary to: {summary_path}")
    print(f"Saved breadth-materiality event summary to: {event_summary_path}")
    print(f"Saved breadth changed-switch audit to: {changed_switches_path}")
    print(f"Saved breadth changed-switch summary to: {changed_switch_summary_path}")
    print(f"Saved breadth-materiality gate report to: {gate_path}")
    print(f"Saved Phase 5B conclusion to: {conclusion_path}")
    print(f"Saved breadth-materiality markdown to: {markdown_path}")

    return outputs