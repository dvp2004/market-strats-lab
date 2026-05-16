from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.regime_switch_overlay_dynamic_slippage import (
    _create_dynamic_slippage_series,
    _create_trade_event_audit,
)
from market_strats.analysis.regime_switch_overlay_slippage_sensitivity import (
    _build_overlay_inputs,
    _period_definitions,
    _slice_and_rebase_result,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _prepare_offensive_state_frame(
    offensive_result: pd.DataFrame,
    trend_sma_days: int,
) -> pd.DataFrame:
    offensive = offensive_result.copy()
    offensive["date"] = pd.to_datetime(offensive["date"])
    offensive = offensive.sort_values("date").reset_index(drop=True)

    if "adj_close" not in offensive.columns:
        raise ValueError("offensive_result must contain adj_close")

    offensive["signal_price"] = offensive["adj_close"].astype(float)
    offensive["trend_sma"] = offensive["signal_price"].rolling(
        trend_sma_days
    ).mean()
    offensive["trend_ready"] = offensive["trend_sma"].notna()
    offensive["trend_distance"] = (
        offensive["signal_price"] / offensive["trend_sma"]
    ) - 1.0

    rolling_high = offensive["signal_price"].cummax()
    offensive["drawdown"] = (offensive["signal_price"] / rolling_high) - 1.0

    return offensive


def _create_defensive_entry_guard_series(
    offensive_result: pd.DataFrame,
    trend_sma_days: int,
    guard_name: str,
    near_high_drawdown_threshold: float,
    near_high_min_trend_distance: float,
    deep_drawdown_threshold: float,
) -> pd.Series:
    state = _prepare_offensive_state_frame(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
    )

    if guard_name == "baseline_no_guard":
        allowed = pd.Series(True, index=state.index)

    elif guard_name == "deep_drawdown_guard":
        allowed = state["drawdown"] > float(deep_drawdown_threshold)

    elif guard_name == "near_high_whipsaw_guard":
        shallow_drawdown = state["drawdown"] > float(near_high_drawdown_threshold)
        meaningfully_below_trend = state["trend_distance"] <= float(
            near_high_min_trend_distance
        )
        allowed = (~shallow_drawdown) | meaningfully_below_trend

    elif guard_name == "combined_deep_and_near_high_guard":
        not_deep_drawdown = state["drawdown"] > float(deep_drawdown_threshold)
        shallow_drawdown = state["drawdown"] > float(near_high_drawdown_threshold)
        meaningfully_below_trend = state["trend_distance"] <= float(
            near_high_min_trend_distance
        )
        near_high_allowed = (~shallow_drawdown) | meaningfully_below_trend
        allowed = not_deep_drawdown & near_high_allowed

    else:
        raise ValueError(f"Unknown guard_name: {guard_name}")

    allowed = allowed.fillna(False)
    allowed.index = state["date"]

    return allowed.astype(bool)


def _calculate_guarded_period_metrics(
    result: pd.DataFrame,
    strategy_name: str,
    guard_name: str,
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


def _create_guarded_switch_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()

    baseline = metrics[metrics["guard_name"] == "baseline_no_guard"]

    if baseline.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for _, row in metrics.iterrows():
        period = row["period"]
        baseline_period = baseline[baseline["period"] == period]

        if baseline_period.empty:
            continue

        baseline_row = baseline_period.iloc[0]

        rows.append(
            {
                "period": period,
                "guard_name": row["guard_name"],
                "cagr_pct": row["cagr_pct"],
                "cagr_delta_vs_baseline_pct_points": round(
                    float(row["cagr_pct"]) - float(baseline_row["cagr_pct"]),
                    3,
                ),
                "calmar": row["calmar"],
                "calmar_delta_vs_baseline": round(
                    float(row["calmar"]) - float(baseline_row["calmar"]),
                    3,
                ),
                "max_drawdown_pct": row["max_drawdown_pct"],
                "drawdown_delta_vs_baseline_pct_points": round(
                    float(row["max_drawdown_pct"])
                    - float(baseline_row["max_drawdown_pct"]),
                    3,
                ),
                "end_value": row["end_value"],
                "end_value_delta_vs_baseline": round(
                    float(row["end_value"]) - float(baseline_row["end_value"]),
                    2,
                ),
                "trade_count": row["trade_count"],
                "trade_count_delta_vs_baseline": int(row["trade_count"])
                - int(baseline_row["trade_count"]),
            }
        )

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.reset_index(drop=True)


def _create_guarded_switch_event_summary(
    guard_events: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict] = []

    for guard_name, events in guard_events.items():
        if events.empty:
            rows.append(
                {
                    "guard_name": guard_name,
                    "switch_count": 0,
                    "avg_applied_slippage_bps": "",
                    "avg_overlay_slippage_cost_pct": "",
                }
            )
            continue

        rows.append(
            {
                "guard_name": guard_name,
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


def _create_guarded_switch_conclusion(
    summary: pd.DataFrame,
    event_summary: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    full = summary[summary["period"] == "full"].copy()
    holdout = summary[summary["period"] == "holdout"].copy()

    if full.empty:
        return pd.DataFrame()

    candidates = full[full["guard_name"] != "baseline_no_guard"].copy()

    if candidates.empty:
        return pd.DataFrame()

    candidates["score"] = (
        candidates["cagr_delta_vs_baseline_pct_points"].astype(float)
        + candidates["calmar_delta_vs_baseline"].astype(float)
        + candidates["drawdown_delta_vs_baseline_pct_points"].astype(float) / 10.0
    )

    best_full = candidates.sort_values("score", ascending=False).iloc[0]

    best_guard = str(best_full["guard_name"])
    best_holdout = holdout[holdout["guard_name"] == best_guard]

    full_cagr_delta = float(best_full["cagr_delta_vs_baseline_pct_points"])
    full_calmar_delta = float(best_full["calmar_delta_vs_baseline"])
    full_drawdown_delta = float(best_full["drawdown_delta_vs_baseline_pct_points"])

    holdout_cagr_delta = None
    holdout_calmar_delta = None

    if not best_holdout.empty:
        holdout_row = best_holdout.iloc[0]
        holdout_cagr_delta = float(holdout_row["cagr_delta_vs_baseline_pct_points"])
        holdout_calmar_delta = float(holdout_row["calmar_delta_vs_baseline"])

    improves_full_period = (
        full_cagr_delta > 0.0
        and full_calmar_delta >= 0.0
        and full_drawdown_delta >= -1.0
    )

    survives_holdout = (
        holdout_cagr_delta is not None
        and holdout_calmar_delta is not None
        and holdout_cagr_delta >= -0.25
        and holdout_calmar_delta >= -0.025
    )

    event_row = event_summary[event_summary["guard_name"] == best_guard]
    baseline_event_row = event_summary[
        event_summary["guard_name"] == "baseline_no_guard"
    ]

    switch_reduction_interpretation = "Switch-count comparison unavailable."

    if not event_row.empty and not baseline_event_row.empty:
        switch_delta = int(event_row.iloc[0]["switch_count"]) - int(
            baseline_event_row.iloc[0]["switch_count"]
        )
        switch_reduction_interpretation = (
            f"{best_guard} changed switch count by {switch_delta} versus baseline."
        )

    return pd.DataFrame(
        [
            {
                "claim": "A guarded switch rule improves the dynamic baseline.",
                "status": (
                    "Survived"
                    if improves_full_period and survives_holdout
                    else "Failed"
                ),
                "evidence_quality": "Compared guarded variants against dynamic stress-slippage baseline",
                "interpretation": (
                    f"Best full-period guard was {best_guard}. Full-period CAGR "
                    f"delta was {full_cagr_delta} percentage points, Calmar delta "
                    f"was {full_calmar_delta}, and drawdown delta was "
                    f"{full_drawdown_delta} percentage points."
                ),
            },
            {
                "claim": "The best guarded rule survives holdout damage control.",
                "status": "Survived" if survives_holdout else "Failed",
                "evidence_quality": "Checked holdout CAGR and Calmar deterioration versus baseline",
                "interpretation": (
                    f"Best guard holdout CAGR delta was {holdout_cagr_delta} "
                    f"percentage points and Calmar delta was {holdout_calmar_delta}."
                ),
            },
            {
                "claim": "Guarding reduces harmful switching without simply refusing protection.",
                "status": "Review",
                "evidence_quality": "Compared switch counts and performance deltas",
                "interpretation": switch_reduction_interpretation,
            },
            {
                "claim": "Guarded switch rules are ready for promotion.",
                "status": "Not yet",
                "evidence_quality": "Phase 4D is still a design-hypothesis diagnostic",
                "interpretation": (
                    "A guard can only be promoted after deeper event-level review and "
                    "additional validation. Do not replace the baseline overlay yet."
                ),
            },
        ]
    )


def create_regime_switch_overlay_guarded_switch_diagnostic(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    diagnostic_config = config.get("phase4_guarded_switch_diagnostic", {})

    if not diagnostic_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "event_summary": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    overlay_config = config.get("regime_switch_overlay", {})

    if not overlay_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "event_summary": pd.DataFrame(),
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

    reference_end_date = str(diagnostic_config["reference_end_date"])
    holdout_start_date = str(diagnostic_config["holdout_start_date"])

    dynamic_config = config.get("phase4_dynamic_slippage", {})
    dynamic_slippage = _create_dynamic_slippage_series(
        offensive_result=offensive_result,
        trend_sma_days=trend_sma_days,
        normal_bps=float(dynamic_config.get("normal_bps", 5.0)),
        below_200d_bps=float(dynamic_config.get("below_200d_bps", 15.0)),
        drawdown_10_bps=float(dynamic_config.get("drawdown_10_bps", 25.0)),
        drawdown_20_bps=float(dynamic_config.get("drawdown_20_bps", 50.0)),
    )

    guard_names = [
        "baseline_no_guard",
        "deep_drawdown_guard",
        "near_high_whipsaw_guard",
        "combined_deep_and_near_high_guard",
    ]

    metric_frames: list[pd.DataFrame] = []
    guard_events: dict[str, pd.DataFrame] = {}

    for guard_name in guard_names:
        guard_series = _create_defensive_entry_guard_series(
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

        if guard_name == "baseline_no_guard":
            defensive_entry_allowed = None
        else:
            defensive_entry_allowed = guard_series

        overlay_result = run_spy_trend_regime_switch_overlay(
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

        metric_frames.append(
            _calculate_guarded_period_metrics(
                result=overlay_result,
                strategy_name=overlay_name,
                guard_name=guard_name,
                initial_capital=initial_capital,
                reference_end_date=reference_end_date,
                holdout_start_date=holdout_start_date,
            )
        )

        guard_events[guard_name] = _create_trade_event_audit(overlay_result)

    metrics = pd.concat(metric_frames, ignore_index=True)
    summary = _create_guarded_switch_summary(metrics)
    event_summary = _create_guarded_switch_event_summary(guard_events)
    conclusion = _create_guarded_switch_conclusion(
        summary=summary,
        event_summary=event_summary,
    )

    return {
        "metrics": metrics,
        "summary": summary,
        "event_summary": event_summary,
        "conclusion": conclusion,
    }


def write_regime_switch_overlay_guarded_switch_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = outputs.get("metrics", pd.DataFrame())
    summary = outputs.get("summary", pd.DataFrame())
    event_summary = outputs.get("event_summary", pd.DataFrame())
    conclusion = outputs.get("conclusion", pd.DataFrame())

    content = f"""# Regime Switch Overlay Guarded Switch Diagnostic

This Phase 4D report tests targeted guarded switch rules derived from Phase 4C failure attribution.

The tested guards are:

- baseline_no_guard
- deep_drawdown_guard
- near_high_whipsaw_guard
- combined_deep_and_near_high_guard

These are design hypotheses, not promoted strategy replacements.

## Metrics

{metrics.to_markdown(index=False) if not metrics.empty else "No metrics available."}

## Summary Versus Baseline

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Event Summary

{event_summary.to_markdown(index=False) if not event_summary.empty else "No event summary available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_guarded_switch_diagnostic(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_guarded_switch_diagnostic(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    metrics = outputs["metrics"]
    summary = outputs["summary"]
    event_summary = outputs["event_summary"]
    conclusion = outputs["conclusion"]

    if metrics.empty:
        return outputs

    metrics_path = reports_dir / "regime_switch_overlay_guarded_switch_metrics.csv"
    summary_path = reports_dir / "regime_switch_overlay_guarded_switch_summary.csv"
    event_summary_path = (
        reports_dir / "regime_switch_overlay_guarded_switch_event_summary.csv"
    )
    conclusion_path = reports_dir / "phase4d_guarded_switch_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_guarded_switch.md"

    metrics.to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)
    event_summary.to_csv(event_summary_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_guarded_switch_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay guarded switch metrics:")
    print(metrics.to_string(index=False))

    print("\nRegime switch overlay guarded switch summary:")
    print(summary.to_string(index=False))

    print("\nRegime switch overlay guarded switch event summary:")
    print(event_summary.to_string(index=False))

    print("\nPhase 4D guarded switch conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved guarded switch metrics to: {metrics_path}")
    print(f"Saved guarded switch summary to: {summary_path}")
    print(f"Saved guarded switch event summary to: {event_summary_path}")
    print(f"Saved Phase 4D conclusion to: {conclusion_path}")
    print(f"Saved guarded switch markdown to: {markdown_path}")

    return outputs