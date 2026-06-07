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
from market_strats.analysis.regime_switch_overlay_stress_confirmation import (
    _create_stress_state_frame,
)
from market_strats.analysis.regime_switch_overlay_switch_effectiveness import (
    _create_switch_effectiveness_events,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _segment_definitions(config: dict) -> list[dict]:
    phase_config = config.get("phase6_offensive_relief_validation", {})

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


def _create_relief_condition(
    offensive_result: pd.DataFrame,
    config: dict,
    profile: dict,
) -> pd.Series:
    phase_config = config.get("phase6_offensive_relief_validation", {})
    overlay_config = config.get("regime_switch_overlay", {})

    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))
    volatility_window_days = int(phase_config.get("volatility_window_days", 20))

    state = _create_stress_state_frame(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
        volatility_window_days=volatility_window_days,
    )

    relief = (
        (
            state["realized_vol_annualized"]
            <= float(profile["relief_vol_annualized_threshold"])
        )
        & (state["return_20d"] >= float(profile["relief_20d_return_threshold"]))
        & (
            state["trend_distance"]
            >= float(profile["relief_trend_distance_threshold"])
        )
    ).fillna(False)

    relief.index = pd.to_datetime(state["date"])

    return relief.astype(bool)


def _create_deep_drawdown_guard(
    offensive_result: pd.DataFrame,
    config: dict,
) -> pd.Series:
    phase4_guard_config = config.get("phase4_guarded_switch_diagnostic", {})
    overlay_config = config.get("regime_switch_overlay", {})

    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))

    return _create_defensive_entry_guard_series(
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


def _create_overlay_for_variant(
    offensive_result: pd.DataFrame,
    defensive_result: pd.DataFrame,
    config: dict,
    variant_name: str,
    relief_profile: dict | None,
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

    deep_drawdown_guard = _create_deep_drawdown_guard(
        offensive_result=offensive_result,
        config=config,
    )

    if variant_name == "phase4_execution_candidate":
        offensive_entry_allowed = None
        offensive_guard_name = "none"
    else:
        if relief_profile is None:
            raise ValueError("relief_profile must be supplied for relief variants")

        offensive_entry_allowed = _create_relief_condition(
            offensive_result=offensive_result,
            config=config,
            profile=relief_profile,
        )
        offensive_guard_name = f"offensive_{variant_name}"

    return run_spy_trend_regime_switch_overlay(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        initial_capital=initial_capital,
        trend_sma_days=trend_sma_days,
        slippage_bps=baseline_slippage_bps,
        confirmation_days=confirmation_days,
        dynamic_slippage_bps=dynamic_slippage,
        defensive_entry_allowed=deep_drawdown_guard,
        defensive_entry_guard_name="deep_drawdown_guard",
        offensive_entry_allowed=offensive_entry_allowed,
        offensive_entry_guard_name=offensive_guard_name,
    )


def create_phase6b_loose_relief_final_candidate(
    *,
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    """Build the registered Phase 6B final-candidate daily frame.

    This exposes the existing loose-relief overlay construction for Phase 15WXYZ
    fresh-extension export. It does not add a new strategy variant or change the
    Phase 6B selection logic.
    """

    phase15_config = config.get("phase15wxyz_fresh_extension_pipeline", {}) or {}
    final_decision_config = config.get("phase6_final_candidate_decision", {}) or {}
    phase6_config = config.get("phase6_offensive_relief_validation", {}) or {}

    variant_name = str(
        phase15_config.get(
            "fresh_final_candidate_variant",
            final_decision_config.get("final_candidate_variant", "loose_relief"),
        )
    )

    relief_profile = None
    for profile in phase6_config.get("relief_profiles", []):
        if str(profile.get("name", "")) == variant_name:
            relief_profile = profile
            break

    if relief_profile is None:
        raise ValueError(f"Fresh final-candidate relief profile not found: {variant_name}")

    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    return _create_overlay_for_variant(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        config=config,
        variant_name=variant_name,
        relief_profile=relief_profile,
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


def _create_relief_summary(
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
        effectiveness_columns = [
            column
            for column in benchmark_effectiveness.columns
            if column.startswith("switch_value_added_")
            or column.startswith("switch_helped_")
            or column == "switch_key"
        ]
        removed = removed.merge(
            benchmark_effectiveness[effectiveness_columns],
            on="switch_key",
            how="left",
        )

    if not candidate_effectiveness.empty:
        candidate_effectiveness = candidate_effectiveness.copy()
        candidate_effectiveness["switch_key"] = _normalise_switch_key(
            candidate_effectiveness
        )
        effectiveness_columns = [
            column
            for column in candidate_effectiveness.columns
            if column.startswith("switch_value_added_")
            or column.startswith("switch_helped_")
            or column == "switch_key"
        ]
        added = added.merge(
            candidate_effectiveness[effectiveness_columns],
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


def _create_relief_gate_report(
    summary: pd.DataFrame,
    event_summary: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    phase_config = config.get("phase6_offensive_relief_validation", {})
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
        phase_config.get("min_full_cagr_improvement_pct_points", 0.30)
    )
    min_calmar_improvement = float(
        phase_config.get("min_full_calmar_improvement", 0.010)
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
    max_episode_cagr_damage = float(
        phase_config.get("max_allowed_episode_cagr_damage_pct_points", -0.50)
    )
    max_episode_calmar_damage = float(
        phase_config.get("max_allowed_episode_calmar_damage", -0.05)
    )
    max_switch_reduction = int(
        phase_config.get("max_allowed_switch_count_reduction", -10)
    )

    rows: list[dict] = []
    candidate_records: list[dict] = []

    benchmark_events = event_summary[
        event_summary["variant_name"] == benchmark_variant
    ]

    for _, candidate in candidates.iterrows():
        variant_name = str(candidate["variant_name"])

        full_cagr_delta = float(candidate["cagr_delta_pct_points"])
        full_calmar_delta = float(candidate["calmar_delta"])
        full_drawdown_delta = float(candidate["drawdown_delta_pct_points"])

        score = (
            full_cagr_delta
            + full_calmar_delta
            + (full_drawdown_delta / 10.0)
        )

        passes_materiality = (
            full_cagr_delta >= min_cagr_improvement
            and full_calmar_delta >= min_calmar_improvement
            and full_drawdown_delta >= max_drawdown_damage
        )

        candidate_holdout = holdout[holdout["variant_name"] == variant_name]

        holdout_damage = False
        holdout_interpretation = "Holdout comparison unavailable."

        if not candidate_holdout.empty:
            holdout_row = candidate_holdout.iloc[0]
            holdout_cagr_delta = float(holdout_row["cagr_delta_pct_points"])
            holdout_calmar_delta = float(holdout_row["calmar_delta"])
            holdout_drawdown_delta = float(
                holdout_row["drawdown_delta_pct_points"]
            )

            holdout_damage = (
                holdout_cagr_delta < max_holdout_cagr_damage
                or holdout_calmar_delta < max_holdout_calmar_damage
                or holdout_drawdown_delta < max_drawdown_damage
            )

            holdout_interpretation = (
                f"{variant_name} holdout CAGR delta was "
                f"{holdout_cagr_delta}, Calmar delta was "
                f"{holdout_calmar_delta}, and drawdown delta was "
                f"{holdout_drawdown_delta}."
            )

        candidate_episode = episode[episode["variant_name"] == variant_name].copy()

        damaged_episode_count = 0
        episode_interpretation = "No episode-level comparison available."

        if not candidate_episode.empty:
            damaged_episode = candidate_episode[
                (
                    candidate_episode["cagr_delta_pct_points"].astype(float)
                    < max_episode_cagr_damage
                )
                | (
                    candidate_episode["calmar_delta"].astype(float)
                    < max_episode_calmar_damage
                )
                | (
                    candidate_episode["drawdown_delta_pct_points"].astype(float)
                    < max_drawdown_damage
                )
            ].copy()

            damaged_episode_count = int(len(damaged_episode))

            if damaged_episode.empty:
                episode_interpretation = (
                    "No episode segment breached damage thresholds."
                )
            else:
                damaged_names = ", ".join(
                    damaged_episode["period"].astype(str).tolist()
                )
                episode_interpretation = (
                    f"{damaged_episode_count} episode segment(s) breached "
                    f"damage thresholds: {damaged_names}."
                )

        candidate_events = event_summary[
            event_summary["variant_name"] == variant_name
        ]

        switch_reduction_too_large = False
        switch_delta: int | None = None
        switch_interpretation = "Switch-count comparison unavailable."

        if not benchmark_events.empty and not candidate_events.empty:
            switch_delta = int(candidate_events.iloc[0]["switch_count"]) - int(
                benchmark_events.iloc[0]["switch_count"]
            )
            switch_reduction_too_large = switch_delta < max_switch_reduction
            switch_interpretation = (
                f"{variant_name} changed switch count by {switch_delta} "
                f"versus {benchmark_variant}. Allowed reduction is no worse "
                f"than {max_switch_reduction}."
            )

        passes_all_gates = (
            passes_materiality
            and not holdout_damage
            and damaged_episode_count == 0
            and not switch_reduction_too_large
        )

        candidate_records.append(
            {
                "candidate_variant": variant_name,
                "score": score,
                "passes_all_gates": passes_all_gates,
                "passes_materiality": passes_materiality,
                "holdout_damage": holdout_damage,
                "damaged_episode_count": damaged_episode_count,
                "switch_reduction_too_large": switch_reduction_too_large,
                "switch_delta": switch_delta,
                "full_cagr_delta": full_cagr_delta,
                "full_calmar_delta": full_calmar_delta,
                "full_drawdown_delta": full_drawdown_delta,
            }
        )

        rows.extend(
            [
                {
                    "candidate_variant": variant_name,
                    "gate": "Offensive relief variant passes materiality.",
                    "status": "Passed" if passes_materiality else "Failed",
                    "evidence_quality": (
                        "Required minimum full-period CAGR and Calmar "
                        "improvement"
                    ),
                    "interpretation": (
                        f"{variant_name} full-period CAGR delta was "
                        f"{full_cagr_delta}, Calmar delta was "
                        f"{full_calmar_delta}, and drawdown delta was "
                        f"{full_drawdown_delta}."
                    ),
                },
                {
                    "candidate_variant": variant_name,
                    "gate": "Offensive relief variant avoids holdout damage.",
                    "status": "Passed" if not holdout_damage else "Failed",
                    "evidence_quality": (
                        "Checked holdout CAGR, Calmar, and drawdown deltas"
                    ),
                    "interpretation": holdout_interpretation,
                },
                {
                    "candidate_variant": variant_name,
                    "gate": (
                        "Offensive relief variant avoids episode-level damage."
                    ),
                    "status": (
                        "Passed" if damaged_episode_count == 0 else "Failed"
                    ),
                    "evidence_quality": (
                        "Checked pre-declared episode segments"
                    ),
                    "interpretation": episode_interpretation,
                },
                {
                    "candidate_variant": variant_name,
                    "gate": (
                        "Offensive relief variant avoids excessive switch "
                        "reduction."
                    ),
                    "status": (
                        "Passed"
                        if not switch_reduction_too_large
                        else "Failed"
                    ),
                    "evidence_quality": (
                        "Compared switch count against Phase 4 execution "
                        "candidate"
                    ),
                    "interpretation": switch_interpretation,
                },
                {
                    "candidate_variant": variant_name,
                    "gate": (
                        "Offensive relief variant passes all validation gates."
                    ),
                    "status": "Passed" if passes_all_gates else "Failed",
                    "evidence_quality": (
                        "Requires materiality, holdout safety, episode safety, "
                        "and switch-count discipline"
                    ),
                    "interpretation": (
                        f"{variant_name} passed all validation gates."
                        if passes_all_gates
                        else f"{variant_name} did not pass all validation gates."
                    ),
                },
            ]
        )

    candidate_record_frame = pd.DataFrame(candidate_records)

    passing_candidates = candidate_record_frame[
        candidate_record_frame["passes_all_gates"]
    ].copy()

    if not passing_candidates.empty:
        selected = passing_candidates.sort_values(
            "score",
            ascending=False,
        ).iloc[0]
        selected_variant = str(selected["candidate_variant"])
        final_status = "Passed"
        final_interpretation = (
            f"{selected_variant} was the best passing offensive relief "
            "variant."
        )
    else:
        selected = candidate_record_frame.sort_values(
            "score",
            ascending=False,
        ).iloc[0]
        selected_variant = str(selected["candidate_variant"])
        final_status = "Not yet"
        final_interpretation = (
            "No offensive relief variant passed all validation gates. "
            f"The best headline-score variant was {selected_variant}."
        )

    rows.append(
        {
            "candidate_variant": selected_variant,
            "gate": "Offensive relief confirmation is validated for promotion.",
            "status": final_status,
            "evidence_quality": (
                "Selected the highest-scoring candidate among variants that "
                "passed every validation gate"
            ),
            "interpretation": final_interpretation,
        }
    )

    return pd.DataFrame(rows)


def _create_relief_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    if gate_report.empty:
        return pd.DataFrame()

    final_gate = gate_report[
        gate_report["gate"]
        == "Offensive relief confirmation is validated for promotion."
    ]

    final_status = final_gate.iloc[0]["status"] if not final_gate.empty else "Not yet"
    selected_variant = (
        str(final_gate.iloc[0]["candidate_variant"])
        if not final_gate.empty and "candidate_variant" in final_gate.columns
        else ""
    )

    return pd.DataFrame(
        [
            {
                "claim": (
                    "An offensive relief profile is validated for promotion "
                    "consideration."
                ),
                "status": "Survived" if final_status == "Passed" else "Failed",
                "evidence_quality": (
                    "Based on Phase 6B offensive-relief validation gates"
                ),
                "interpretation": (
                    f"{selected_variant} passed all validation gates."
                    if final_status == "Passed"
                    else "No offensive relief profile passed all validation gates."
                ),
            },
            {
                "claim": (
                    "Phase 6A's baseline offensive relief result was safe to "
                    "promote immediately."
                ),
                "status": "Failed",
                "evidence_quality": (
                    "Phase 6B checked relief threshold sensitivity, episode "
                    "damage, and switch-count reduction"
                ),
                "interpretation": (
                    "The highest-headline Phase 6A relief result was not enough "
                    "by itself. Promotion requires candidate-level gate validation."
                ),
            },
            {
                "claim": "The next step should be macro/sentiment/ML.",
                "status": "Not yet",
                "evidence_quality": (
                    "Only justified after documenting offensive-relief validation"
                ),
                "interpretation": (
                    "Do not add external data until this relief validation is "
                    "documented and either rejected or promoted."
                ),
            },
        ]
    )


def create_regime_switch_overlay_offensive_relief_validation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = config.get("phase6_offensive_relief_validation", {})

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
    segments = _segment_definitions(config)

    variant_specs: list[tuple[str, dict | None]] = [(benchmark_variant, None)]

    for profile in phase_config.get("relief_profiles", []):
        variant_specs.append((str(profile["name"]), profile))

    metric_frames: list[pd.DataFrame] = []
    variant_events: dict[str, pd.DataFrame] = {}
    variant_effectiveness: dict[str, pd.DataFrame] = {}

    for variant_name, relief_profile in variant_specs:
        overlay_result = _create_overlay_for_variant(
            offensive_result=offensive_result,
            defensive_result=defensive_result,
            config=config,
            variant_name=variant_name,
            relief_profile=relief_profile,
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
        variant_effectiveness[variant_name] = _create_switch_effectiveness_events(
            overlay_result=overlay_result,
            offensive_result=offensive_result,
            defensive_result=defensive_result,
            horizons=[5, 20, 60],
        )

    metrics = pd.concat(metric_frames, ignore_index=True)
    summary = _create_relief_summary(
        metrics=metrics,
        benchmark_variant=benchmark_variant,
    )
    event_summary = _create_event_summary(variant_events)

    changed_frames: list[pd.DataFrame] = []
    benchmark_events = variant_events[benchmark_variant]
    benchmark_effectiveness = variant_effectiveness[benchmark_variant]

    for variant_name, _profile in variant_specs:
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

    gate_report = _create_relief_gate_report(
        summary=summary,
        event_summary=event_summary,
        config=config,
    )
    conclusion = _create_relief_conclusion(gate_report)

    return {
        "metrics": metrics,
        "summary": summary,
        "event_summary": event_summary,
        "changed_switches": changed_switches,
        "changed_switch_summary": changed_switch_summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }


def write_regime_switch_overlay_offensive_relief_markdown(
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

    content = f"""# Regime Switch Overlay Offensive Relief Validation

This Phase 6B report validates whether offensive relief confirmation genuinely improves re-entry timing or merely over-filters switches.

It compares strict, baseline, and loose relief profiles against the Phase 4 execution-realistic candidate.

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


def save_regime_switch_overlay_offensive_relief_validation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_offensive_relief_validation(
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

    metrics_path = reports_dir / "regime_switch_overlay_offensive_relief_metrics.csv"
    summary_path = reports_dir / "regime_switch_overlay_offensive_relief_summary.csv"
    event_summary_path = (
        reports_dir / "regime_switch_overlay_offensive_relief_event_summary.csv"
    )
    changed_switches_path = (
        reports_dir / "regime_switch_overlay_offensive_relief_changed_switch_audit.csv"
    )
    changed_switch_summary_path = (
        reports_dir / "regime_switch_overlay_offensive_relief_changed_switch_summary.csv"
    )
    gate_path = reports_dir / "regime_switch_overlay_offensive_relief_gate_report.csv"
    conclusion_path = reports_dir / "phase6b_offensive_relief_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_offensive_relief.md"

    metrics.to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)
    event_summary.to_csv(event_summary_path, index=False)
    changed_switches.to_csv(changed_switches_path, index=False)
    changed_switch_summary.to_csv(changed_switch_summary_path, index=False)
    gate_report.to_csv(gate_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_offensive_relief_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay offensive-relief metrics:")
    print(metrics.to_string(index=False))

    print("\nRegime switch overlay offensive-relief summary:")
    print(summary.to_string(index=False))

    print("\nRegime switch overlay offensive-relief event summary:")
    print(event_summary.to_string(index=False))

    print("\nRegime switch overlay offensive-relief changed-switch summary:")
    print(changed_switch_summary.to_string(index=False))

    print("\nRegime switch overlay offensive-relief gate report:")
    print(gate_report.to_string(index=False))

    print("\nPhase 6B offensive-relief conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved offensive-relief metrics to: {metrics_path}")
    print(f"Saved offensive-relief summary to: {summary_path}")
    print(f"Saved offensive-relief event summary to: {event_summary_path}")
    print(f"Saved offensive-relief changed-switch audit to: {changed_switches_path}")
    print(f"Saved offensive-relief changed-switch summary to: {changed_switch_summary_path}")
    print(f"Saved offensive-relief gate report to: {gate_path}")
    print(f"Saved Phase 6B conclusion to: {conclusion_path}")
    print(f"Saved offensive-relief markdown to: {markdown_path}")

    return outputs
