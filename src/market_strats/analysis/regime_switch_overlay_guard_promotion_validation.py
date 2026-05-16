from __future__ import annotations

from pathlib import Path
import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.regime_switch_overlay_guard_validation import (
    _create_overlay_for_guard,
)
from market_strats.analysis.regime_switch_overlay_slippage_sensitivity import (
    _build_overlay_inputs,
    _slice_and_rebase_result,
)


def _segment_definitions(config: dict) -> list[dict]:
    promotion_config = config.get("phase4_guard_promotion_validation", {})

    reference_end_date = str(promotion_config["reference_end_date"])
    holdout_start_date = str(promotion_config["holdout_start_date"])

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

    for segment in promotion_config.get("segments", []):
        segments.append(
            {
                "period": str(segment["name"]),
                "start_date": segment.get("start_date"),
                "end_date": segment.get("end_date"),
                "segment_type": "episode",
            }
        )

    return segments


def _calculate_segment_metrics(
    result: pd.DataFrame,
    guard_name: str,
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


def _create_guard_promotion_summary(
    metrics: pd.DataFrame,
    benchmark_guard: str,
    candidate_guard: str,
) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()

    benchmark = metrics[metrics["guard_name"] == benchmark_guard].copy()
    candidate = metrics[metrics["guard_name"] == candidate_guard].copy()

    if benchmark.empty or candidate.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    common_periods = sorted(set(benchmark["period"]).intersection(candidate["period"]))

    for period in common_periods:
        benchmark_row = benchmark[benchmark["period"] == period].iloc[0]
        candidate_row = candidate[candidate["period"] == period].iloc[0]

        rows.append(
            {
                "period": period,
                "segment_type": candidate_row["segment_type"],
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


def _create_guard_promotion_gate_report(
    summary: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    promotion_config = config.get("phase4_guard_promotion_validation", {})

    spy_12m_cagr_gate = float(promotion_config.get("spy_12m_cagr_gate", 9.68))
    spy_12m_calmar_gate = float(promotion_config.get("spy_12m_calmar_gate", 0.287))
    spy_12m_drawdown_gate = float(
        promotion_config.get("spy_12m_max_drawdown_gate", -33.72)
    )

    max_cagr_damage = float(
        promotion_config.get("max_allowed_segment_cagr_damage_pct_points", -0.50)
    )
    max_calmar_damage = float(
        promotion_config.get("max_allowed_segment_calmar_damage", -0.05)
    )
    max_drawdown_damage = float(
        promotion_config.get("max_allowed_segment_drawdown_damage_pct_points", -1.00)
    )

    full = summary[summary["period"] == "full"]
    holdout = summary[summary["period"] == "holdout"]
    episode = summary[summary["segment_type"] == "episode"].copy()

    if full.empty:
        return pd.DataFrame()

    full_row = full.iloc[0]
    holdout_row = holdout.iloc[0] if not holdout.empty else None

    full_cagr_delta = float(full_row["cagr_delta_pct_points"])
    full_calmar_delta = float(full_row["calmar_delta"])
    full_drawdown_delta = float(full_row["drawdown_delta_pct_points"])

    candidate_full_cagr = float(full_row["candidate_cagr_pct"])
    candidate_full_calmar = float(full_row["candidate_calmar"])
    candidate_full_drawdown = float(full_row["candidate_max_drawdown_pct"])

    beats_spy_12m_triple_gate = (
        candidate_full_cagr > spy_12m_cagr_gate
        and candidate_full_calmar > spy_12m_calmar_gate
        and candidate_full_drawdown > spy_12m_drawdown_gate
    )

    improves_dynamic_baseline = (
        full_cagr_delta > 0
        and full_calmar_delta > 0
        and full_drawdown_delta >= max_drawdown_damage
    )

    holdout_damage = False
    holdout_interpretation = "Holdout comparison unavailable."

    if holdout_row is not None:
        holdout_cagr_delta = float(holdout_row["cagr_delta_pct_points"])
        holdout_calmar_delta = float(holdout_row["calmar_delta"])
        holdout_drawdown_delta = float(holdout_row["drawdown_delta_pct_points"])

        holdout_damage = (
            holdout_cagr_delta < max_cagr_damage
            or holdout_calmar_delta < max_calmar_damage
            or holdout_drawdown_delta < max_drawdown_damage
        )

        holdout_interpretation = (
            f"Holdout CAGR delta was {holdout_cagr_delta}, Calmar delta was "
            f"{holdout_calmar_delta}, and drawdown delta was "
            f"{holdout_drawdown_delta}."
        )

    damaged_episode_count = 0
    episode_interpretation = "No episode-level segments available."

    if not episode.empty:
        damaged = episode[
            (episode["cagr_delta_pct_points"].astype(float) < max_cagr_damage)
            | (episode["calmar_delta"].astype(float) < max_calmar_damage)
            | (
                episode["drawdown_delta_pct_points"].astype(float)
                < max_drawdown_damage
            )
        ].copy()

        damaged_episode_count = int(len(damaged))

        if damaged.empty:
            episode_interpretation = (
                f"No episode segments breached damage thresholds "
                f"({max_cagr_damage} CAGR pts, {max_calmar_damage} Calmar, "
                f"{max_drawdown_damage} drawdown pts)."
            )
        else:
            damaged_names = ", ".join(damaged["period"].astype(str).tolist())
            episode_interpretation = (
                f"{damaged_episode_count} episode segment(s) breached damage "
                f"thresholds: {damaged_names}."
            )

    passes_segment_robustness = damaged_episode_count == 0

    promotion_candidate = (
        beats_spy_12m_triple_gate
        and improves_dynamic_baseline
        and not holdout_damage
        and passes_segment_robustness
    )

    return pd.DataFrame(
        [
            {
                "gate": "Candidate beats pinned SPY 12M strict full-period triple gate.",
                "status": "Passed" if beats_spy_12m_triple_gate else "Failed",
                "evidence_quality": "Compared candidate full-period CAGR, Calmar, and drawdown against pinned SPY 12M gates",
                "interpretation": (
                    f"Candidate full-period result was {candidate_full_cagr}% CAGR, "
                    f"{candidate_full_calmar} Calmar, and "
                    f"{candidate_full_drawdown}% max drawdown. Gates were "
                    f"{spy_12m_cagr_gate}% CAGR, {spy_12m_calmar_gate} Calmar, "
                    f"and {spy_12m_drawdown_gate}% max drawdown."
                ),
            },
            {
                "gate": "Candidate improves dynamic no-guard baseline.",
                "status": "Passed" if improves_dynamic_baseline else "Failed",
                "evidence_quality": "Compared full-period candidate guard versus dynamic no-guard baseline",
                "interpretation": (
                    f"Full-period CAGR delta was {full_cagr_delta}, Calmar delta "
                    f"was {full_calmar_delta}, and drawdown delta was "
                    f"{full_drawdown_delta}."
                ),
            },
            {
                "gate": "Candidate avoids holdout damage.",
                "status": "Passed" if not holdout_damage else "Failed",
                "evidence_quality": "Checked holdout CAGR, Calmar, and drawdown deltas",
                "interpretation": holdout_interpretation,
            },
            {
                "gate": "Candidate avoids material episode-level damage.",
                "status": "Passed" if passes_segment_robustness else "Failed",
                "evidence_quality": "Checked pre-declared market episode segments",
                "interpretation": episode_interpretation,
            },
            {
                "gate": "Candidate can be promoted to execution-realistic overlay candidate.",
                "status": "Passed" if promotion_candidate else "Not yet",
                "evidence_quality": "Requires all Phase 4F gates to pass",
                "interpretation": (
                    "The candidate passed all promotion-validation gates."
                    if promotion_candidate
                    else "The candidate did not pass all promotion-validation gates."
                ),
            },
        ]
    )


def _create_guard_promotion_conclusion(
    gate_report: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    if gate_report.empty:
        return pd.DataFrame()

    final_gate = gate_report[
        gate_report["gate"]
        == "Candidate can be promoted to execution-realistic overlay candidate."
    ]

    full = summary[summary["period"] == "full"]
    holdout = summary[summary["period"] == "holdout"]

    final_status = final_gate.iloc[0]["status"] if not final_gate.empty else "Not yet"

    full_interpretation = "Full-period comparison unavailable."
    holdout_interpretation = "Holdout comparison unavailable."

    if not full.empty:
        row = full.iloc[0]
        full_interpretation = (
            f"Full-period candidate improved CAGR by "
            f"{row['cagr_delta_pct_points']} percentage points, Calmar by "
            f"{row['calmar_delta']}, and drawdown by "
            f"{row['drawdown_delta_pct_points']} percentage points."
        )

    if not holdout.empty:
        row = holdout.iloc[0]
        holdout_interpretation = (
            f"Holdout candidate changed CAGR by {row['cagr_delta_pct_points']} "
            f"percentage points, Calmar by {row['calmar_delta']}, and drawdown "
            f"by {row['drawdown_delta_pct_points']} percentage points."
        )

    return pd.DataFrame(
        [
            {
                "claim": "deep_drawdown_guard is validated as the execution-realistic overlay candidate.",
                "status": "Survived" if final_status == "Passed" else "Not yet",
                "evidence_quality": "Based on Phase 4F promotion gate report",
                "interpretation": (
                    f"{full_interpretation} {holdout_interpretation}"
                ),
            },
            {
                "claim": "The original flat 5 bps 3D overlay should be replaced silently.",
                "status": "Failed",
                "evidence_quality": "Flat-cost and stress-cost systems answer different assumptions",
                "interpretation": (
                    "The flat 5 bps 3D overlay remains the original canonical "
                    "Phase 3 system. The guarded dynamic-slippage version should "
                    "be documented separately as an execution-realistic candidate."
                ),
            },
            {
                "claim": "The next step should be macro/sentiment/ML expansion.",
                "status": "Not yet",
                "evidence_quality": "Switch mechanics still require final documentation and checkpointing",
                "interpretation": (
                    "First document the Phase 4 execution-realism branch and decide "
                    "whether deep_drawdown_guard becomes the realistic candidate. "
                    "Only then consider external data."
                ),
            },
        ]
    )


def create_regime_switch_overlay_guard_promotion_validation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    promotion_config = config.get("phase4_guard_promotion_validation", {})

    if not promotion_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "gate_report": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    benchmark_guard = str(promotion_config.get("benchmark_guard", "baseline_no_guard"))
    candidate_guard = str(promotion_config.get("candidate_guard", "deep_drawdown_guard"))

    overlay_config = config.get("regime_switch_overlay", {})
    overlay_name = str(overlay_config.get("name", "Regime Switch Overlay"))
    initial_capital = float(config["initial_capital"])

    segments = _segment_definitions(config)

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

    benchmark_metrics = _calculate_segment_metrics(
        result=benchmark_overlay,
        guard_name=benchmark_guard,
        strategy_name=overlay_name,
        initial_capital=initial_capital,
        segments=segments,
    )
    candidate_metrics = _calculate_segment_metrics(
        result=candidate_overlay,
        guard_name=candidate_guard,
        strategy_name=overlay_name,
        initial_capital=initial_capital,
        segments=segments,
    )

    metrics = pd.concat([benchmark_metrics, candidate_metrics], ignore_index=True)
    summary = _create_guard_promotion_summary(
        metrics=metrics,
        benchmark_guard=benchmark_guard,
        candidate_guard=candidate_guard,
    )
    gate_report = _create_guard_promotion_gate_report(
        summary=summary,
        config=config,
    )
    conclusion = _create_guard_promotion_conclusion(
        gate_report=gate_report,
        summary=summary,
    )

    return {
        "metrics": metrics,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }


def write_regime_switch_overlay_guard_promotion_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = outputs.get("metrics", pd.DataFrame())
    summary = outputs.get("summary", pd.DataFrame())
    gate_report = outputs.get("gate_report", pd.DataFrame())
    conclusion = outputs.get("conclusion", pd.DataFrame())

    content = f"""# Regime Switch Overlay Guard Promotion Validation

This Phase 4F report tests whether the deep-drawdown guarded overlay is robust enough to become the execution-realistic overlay candidate.

It compares:

- baseline_no_guard
- deep_drawdown_guard

The validation checks full-period improvement, holdout damage control, SPY 12M gate survival, and pre-declared market-episode robustness.

## Metrics

{metrics.to_markdown(index=False) if not metrics.empty else "No metrics available."}

## Summary

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Gate Report

{gate_report.to_markdown(index=False) if not gate_report.empty else "No gate report available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_guard_promotion_validation(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_guard_promotion_validation(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    metrics = outputs["metrics"]
    summary = outputs["summary"]
    gate_report = outputs["gate_report"]
    conclusion = outputs["conclusion"]

    if metrics.empty:
        return outputs

    metrics_path = reports_dir / "regime_switch_overlay_guard_promotion_metrics.csv"
    summary_path = reports_dir / "regime_switch_overlay_guard_promotion_summary.csv"
    gate_path = reports_dir / "regime_switch_overlay_guard_promotion_gate_report.csv"
    conclusion_path = reports_dir / "phase4f_guard_promotion_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_guard_promotion.md"

    metrics.to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)
    gate_report.to_csv(gate_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_guard_promotion_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay guard-promotion summary:")
    print(summary.to_string(index=False))

    print("\nRegime switch overlay guard-promotion gate report:")
    print(gate_report.to_string(index=False))

    print("\nPhase 4F guard-promotion conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved guard-promotion metrics to: {metrics_path}")
    print(f"Saved guard-promotion summary to: {summary_path}")
    print(f"Saved guard-promotion gate report to: {gate_path}")
    print(f"Saved Phase 4F conclusion to: {conclusion_path}")
    print(f"Saved guard-promotion markdown to: {markdown_path}")

    return outputs