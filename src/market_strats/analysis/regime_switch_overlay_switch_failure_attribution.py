from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.regime_switch_overlay_switch_effectiveness import (
    create_regime_switch_overlay_switch_effectiveness,
)


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace("", np.nan), errors="coerce")


def _bucket_slippage(value: float) -> str:
    if pd.isna(value):
        return "unknown"

    return f"{value:g}_bps"


def _bucket_spy_drawdown(drawdown_pct: float) -> str:
    if pd.isna(drawdown_pct):
        return "unknown"

    if drawdown_pct > -5.0:
        return "near_highs_0_to_-5"

    if drawdown_pct > -10.0:
        return "mild_drawdown_-5_to_-10"

    if drawdown_pct > -20.0:
        return "correction_-10_to_-20"

    return "deep_drawdown_below_-20"


def _bucket_trend_distance(distance_pct: float) -> str:
    if pd.isna(distance_pct):
        return "unknown"

    if distance_pct >= 2.0:
        return "well_above_trend_2_plus"

    if distance_pct >= 0.0:
        return "near_above_trend_0_to_2"

    if distance_pct >= -2.0:
        return "near_below_trend_0_to_-2"

    if distance_pct >= -5.0:
        return "below_trend_-2_to_-5"

    return "deep_below_trend_below_-5"


def _add_failure_attribution_buckets(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    output = events.copy()

    required_columns = {
        "transition",
        "spy_drawdown_pct",
        "spy_distance_from_trend_pct",
        "applied_overlay_slippage_bps",
    }
    missing_columns = required_columns - set(output.columns)

    if missing_columns:
        raise ValueError(
            "switch-effectiveness events missing attribution columns: "
            f"{sorted(missing_columns)}"
        )

    output["spy_drawdown_pct_numeric"] = _to_numeric(output["spy_drawdown_pct"])
    output["spy_distance_from_trend_pct_numeric"] = _to_numeric(
        output["spy_distance_from_trend_pct"]
    )
    output["applied_overlay_slippage_bps_numeric"] = _to_numeric(
        output["applied_overlay_slippage_bps"]
    )

    output["slippage_bucket"] = output["applied_overlay_slippage_bps_numeric"].map(
        _bucket_slippage
    )
    output["spy_drawdown_bucket"] = output["spy_drawdown_pct_numeric"].map(
        _bucket_spy_drawdown
    )
    output["trend_distance_bucket"] = output[
        "spy_distance_from_trend_pct_numeric"
    ].map(_bucket_trend_distance)

    return output


def _summarise_group(
    group_name: str,
    group_dimension: str,
    group_df: pd.DataFrame,
    horizons: list[int],
) -> dict:
    row: dict = {
        "group_dimension": group_dimension,
        "group": group_name,
        "switch_count": int(len(group_df)),
        "avg_applied_slippage_bps": round(
            float(group_df["applied_overlay_slippage_bps_numeric"].mean()),
            3,
        )
        if "applied_overlay_slippage_bps_numeric" in group_df
        else "",
        "avg_spy_drawdown_pct": round(
            float(group_df["spy_drawdown_pct_numeric"].mean()),
            3,
        )
        if "spy_drawdown_pct_numeric" in group_df
        else "",
        "avg_spy_distance_from_trend_pct": round(
            float(group_df["spy_distance_from_trend_pct_numeric"].mean()),
            3,
        )
        if "spy_distance_from_trend_pct_numeric" in group_df
        else "",
    }

    for horizon in horizons:
        value_column = f"switch_value_added_{horizon}d_pct_points"
        helped_column = f"switch_helped_{horizon}d"

        if value_column not in group_df.columns or helped_column not in group_df.columns:
            row[f"valid_{horizon}d_events"] = 0
            row[f"helped_{horizon}d_pct"] = ""
            row[f"avg_value_added_{horizon}d_pct_points"] = ""
            row[f"median_value_added_{horizon}d_pct_points"] = ""
            row[f"worst_value_added_{horizon}d_pct_points"] = ""
            row[f"best_value_added_{horizon}d_pct_points"] = ""
            row[f"negative_{horizon}d_event_pct"] = ""
            continue

        value_added = _to_numeric(group_df[value_column])
        helped = group_df[helped_column].astype(str).str.lower().eq("true")

        valid_mask = value_added.notna() & group_df[helped_column].ne("")
        valid_values = value_added[valid_mask]
        valid_helped = helped[valid_mask]

        if valid_values.empty:
            row[f"valid_{horizon}d_events"] = 0
            row[f"helped_{horizon}d_pct"] = ""
            row[f"avg_value_added_{horizon}d_pct_points"] = ""
            row[f"median_value_added_{horizon}d_pct_points"] = ""
            row[f"worst_value_added_{horizon}d_pct_points"] = ""
            row[f"best_value_added_{horizon}d_pct_points"] = ""
            row[f"negative_{horizon}d_event_pct"] = ""
            continue

        row[f"valid_{horizon}d_events"] = int(len(valid_values))
        row[f"helped_{horizon}d_pct"] = round(float(valid_helped.mean()) * 100.0, 3)
        row[f"avg_value_added_{horizon}d_pct_points"] = round(
            float(valid_values.mean()),
            3,
        )
        row[f"median_value_added_{horizon}d_pct_points"] = round(
            float(valid_values.median()),
            3,
        )
        row[f"worst_value_added_{horizon}d_pct_points"] = round(
            float(valid_values.min()),
            3,
        )
        row[f"best_value_added_{horizon}d_pct_points"] = round(
            float(valid_values.max()),
            3,
        )
        row[f"negative_{horizon}d_event_pct"] = round(
            float((valid_values < 0).mean()) * 100.0,
            3,
        )

    return row


def _create_failure_attribution_summary(
    attributed_events: pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    if attributed_events.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    rows.append(
        _summarise_group(
            group_name="all_switches",
            group_dimension="all",
            group_df=attributed_events,
            horizons=horizons,
        )
    )

    grouping_columns = [
        "transition",
        "slippage_bucket",
        "spy_drawdown_bucket",
        "trend_distance_bucket",
    ]

    for column in grouping_columns:
        for group_name, group_df in attributed_events.groupby(column, dropna=False):
            rows.append(
                _summarise_group(
                    group_name=str(group_name),
                    group_dimension=column,
                    group_df=group_df,
                    horizons=horizons,
                )
            )

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    return output.reset_index(drop=True)


def _find_worst_group(
    summary: pd.DataFrame,
    horizon: int,
) -> pd.Series | None:
    value_column = f"avg_value_added_{horizon}d_pct_points"
    valid_column = f"valid_{horizon}d_events"

    if value_column not in summary.columns or valid_column not in summary.columns:
        return None

    candidates = summary[
        (summary["group_dimension"] != "all")
        & (_to_numeric(summary[valid_column]) >= 3)
    ].copy()

    if candidates.empty:
        return None

    candidates[value_column] = _to_numeric(candidates[value_column])

    candidates = candidates[candidates[value_column].notna()]

    if candidates.empty:
        return None

    return candidates.sort_values(value_column).iloc[0]


def _get_group_row(
    summary: pd.DataFrame,
    group_dimension: str,
    group: str,
) -> pd.Series | None:
    rows = summary[
        (summary["group_dimension"] == group_dimension)
        & (summary["group"] == group)
    ]

    if rows.empty:
        return None

    return rows.iloc[0]


def _create_failure_attribution_conclusion(
    summary: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    all_switches = _get_group_row(summary, "all", "all_switches")

    if all_switches is None:
        return pd.DataFrame()

    all_20d_value = float(all_switches["avg_value_added_20d_pct_points"])
    all_20d_helped = float(all_switches["helped_20d_pct"])
    all_60d_value = float(all_switches["avg_value_added_60d_pct_points"])
    all_60d_helped = float(all_switches["helped_60d_pct"])

    worst_20d = _find_worst_group(summary, horizon=20)
    worst_60d = _find_worst_group(summary, horizon=60)

    high_slippage = _get_group_row(summary, "slippage_bucket", "50_bps")

    high_slippage_hurts = False
    high_slippage_interpretation = "No 50 bps switch bucket was available."

    if high_slippage is not None:
        high_slippage_20d = float(high_slippage["avg_value_added_20d_pct_points"])
        high_slippage_helped_20d = float(high_slippage["helped_20d_pct"])
        high_slippage_hurts = high_slippage_20d < 0 and high_slippage_helped_20d < 50
        high_slippage_interpretation = (
            f"50 bps switches had average 20D value added of "
            f"{high_slippage_20d} percentage points and helped "
            f"{high_slippage_helped_20d}% of valid 20D events."
        )

    rows = [
        {
            "claim": "Switch failures are concentrated enough to diagnose.",
            "status": "Survived" if worst_20d is not None else "Failed",
            "evidence_quality": "Grouped switch value added by transition, slippage, drawdown, and trend-distance buckets",
            "interpretation": (
                "Worst 20D group was "
                f"{worst_20d['group_dimension']}={worst_20d['group']} with "
                f"{worst_20d['avg_value_added_20d_pct_points']} percentage "
                "points average value added."
            )
            if worst_20d is not None
            else "No reliable failure group had enough valid events.",
        },
        {
            "claim": "High-friction switches are a major failure cluster.",
            "status": "Survived" if high_slippage_hurts else "Failed",
            "evidence_quality": "Reviewed the 50 bps dynamic-slippage switch bucket",
            "interpretation": high_slippage_interpretation,
        },
        {
            "claim": "Overall switch timing has a reliable positive 20D edge.",
            "status": "Survived" if all_20d_value > 0 and all_20d_helped > 50 else "Failed",
            "evidence_quality": "Compared actual switch outcome to staying in the previous mode",
            "interpretation": (
                f"Across all switches, average 20D value added was {all_20d_value} "
                f"percentage points and switches helped {all_20d_helped}% of "
                "valid 20D events."
            ),
        },
        {
            "claim": "Overall switch timing has a reliable positive 60D edge.",
            "status": "Survived" if all_60d_value > 0 and all_60d_helped > 50 else "Failed",
            "evidence_quality": "Compared actual switch outcome to staying in the previous mode",
            "interpretation": (
                f"Across all switches, average 60D value added was {all_60d_value} "
                f"percentage points and switches helped {all_60d_helped}% of "
                "valid 60D events."
            ),
        },
        {
            "claim": "The next step should be parameter optimisation.",
            "status": "Not yet",
            "evidence_quality": "Attribution must guide whether a design change is justified",
            "interpretation": (
                "Do not tune confirmation windows yet. First use the identified "
                "failure clusters to decide whether a rule change is economically "
                "sensible rather than curve-fitted."
            ),
        },
    ]

    if worst_60d is not None:
        rows.append(
            {
                "claim": "Medium-horizon failures have identifiable clusters.",
                "status": "Survived",
                "evidence_quality": "Grouped 60D switch value added by failure buckets",
                "interpretation": (
                    "Worst 60D group was "
                    f"{worst_60d['group_dimension']}={worst_60d['group']} with "
                    f"{worst_60d['avg_value_added_60d_pct_points']} percentage "
                    "points average value added."
                ),
            }
        )

    return pd.DataFrame(rows)


def create_regime_switch_overlay_switch_failure_attribution(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    attribution_config = config.get("phase4_switch_failure_attribution", {})

    if not attribution_config.get("enabled", False):
        return {
            "events": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    horizons = [int(value) for value in attribution_config.get("horizons", [5, 20, 60])]

    switch_outputs = create_regime_switch_overlay_switch_effectiveness(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    events = switch_outputs.get("events", pd.DataFrame())

    if events.empty:
        return {
            "events": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    attributed_events = _add_failure_attribution_buckets(events)
    summary = _create_failure_attribution_summary(attributed_events, horizons)
    conclusion = _create_failure_attribution_conclusion(summary)

    return {
        "events": attributed_events,
        "summary": summary,
        "conclusion": conclusion,
    }


def write_regime_switch_overlay_switch_failure_attribution_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    events = outputs.get("events", pd.DataFrame())
    summary = outputs.get("summary", pd.DataFrame())
    conclusion = outputs.get("conclusion", pd.DataFrame())

    content = f"""# Regime Switch Overlay Switch-Failure Attribution

This Phase 4C report diagnoses where the 3D confirmed regime-switch overlay's switches helped or hurt.

It groups switch value added by:

- transition direction,
- dynamic slippage bucket,
- SPY drawdown bucket,
- SPY distance from trend bucket.

## Summary

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}

## Attributed Events

{events.to_markdown(index=False) if not events.empty else "No attributed events available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_switch_failure_attribution(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_switch_failure_attribution(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    events = outputs["events"]
    summary = outputs["summary"]
    conclusion = outputs["conclusion"]

    if events.empty:
        return outputs

    events_path = reports_dir / "regime_switch_overlay_switch_failure_attribution.csv"
    summary_path = (
        reports_dir / "regime_switch_overlay_switch_failure_attribution_summary.csv"
    )
    conclusion_path = reports_dir / "phase4c_switch_failure_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_switch_failure_attribution.md"

    events.to_csv(events_path, index=False)
    summary.to_csv(summary_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_switch_failure_attribution_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay switch-failure attribution summary:")
    print(summary.to_string(index=False))

    print("\nPhase 4C switch-failure conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved switch-failure attribution events to: {events_path}")
    print(f"Saved switch-failure attribution summary to: {summary_path}")
    print(f"Saved Phase 4C conclusion to: {conclusion_path}")
    print(f"Saved switch-failure attribution markdown to: {markdown_path}")

    return outputs