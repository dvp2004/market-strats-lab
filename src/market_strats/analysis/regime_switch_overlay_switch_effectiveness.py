from __future__ import annotations

from pathlib import Path
import pandas as pd

from market_strats.analysis.regime_switch_overlay_dynamic_slippage import (
    _create_dynamic_slippage_series,
)
from market_strats.analysis.regime_switch_overlay_slippage_sensitivity import (
    _build_overlay_inputs,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _compound_return(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")

    return float((1.0 + returns.astype(float)).prod() - 1.0)


def _mode_to_return_column(mode: str) -> str:
    if mode == "offensive_spy":
        return "strategy_return_offensive"

    if mode == "defensive_allocator":
        return "strategy_return_defensive"

    raise ValueError(f"Unknown mode: {mode}")


def _create_component_return_frame(
    offensive_result: pd.DataFrame,
    defensive_result: pd.DataFrame,
) -> pd.DataFrame:
    offensive = offensive_result.copy()
    defensive = defensive_result.copy()

    offensive["date"] = pd.to_datetime(offensive["date"])
    defensive["date"] = pd.to_datetime(defensive["date"])

    offensive = offensive.sort_values("date").reset_index(drop=True)
    defensive = defensive.sort_values("date").reset_index(drop=True)

    required_columns = {"date", "strategy_return"}

    missing_offensive = required_columns - set(offensive.columns)
    missing_defensive = required_columns - set(defensive.columns)

    if missing_offensive:
        raise ValueError(
            f"offensive_result missing columns: {sorted(missing_offensive)}"
        )

    if missing_defensive:
        raise ValueError(
            f"defensive_result missing columns: {sorted(missing_defensive)}"
        )

    return offensive[["date", "strategy_return"]].merge(
        defensive[["date", "strategy_return"]],
        on="date",
        how="inner",
        suffixes=("_offensive", "_defensive"),
    )


def _create_switch_effectiveness_events(
    overlay_result: pd.DataFrame,
    offensive_result: pd.DataFrame,
    defensive_result: pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    overlay = overlay_result.copy()
    overlay["date"] = pd.to_datetime(overlay["date"])
    overlay = overlay.sort_values("date").reset_index(drop=True)

    required_columns = {
        "date",
        "equity",
        "target_defensive_weight",
        "signal_price",
        "trend_sma",
        "applied_overlay_slippage_bps",
        "overlay_slippage_cost",
    }
    missing_columns = required_columns - set(overlay.columns)

    if missing_columns:
        raise ValueError(
            "overlay_result missing columns for switch-effectiveness audit: "
            f"{sorted(missing_columns)}"
        )

    component_returns = _create_component_return_frame(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
    )

    merged = overlay.merge(component_returns, on="date", how="inner")

    if merged.empty:
        raise ValueError("No common dates for switch-effectiveness audit")

    target_defensive = merged["target_defensive_weight"].astype(float)
    previous_target_defensive = target_defensive.shift(1)

    switch_mask = (
        previous_target_defensive.notna()
        & target_defensive.ne(previous_target_defensive)
    )

    equity = merged["equity"].astype(float)
    signal_price = merged["signal_price"].astype(float)
    rolling_high = signal_price.cummax()
    drawdown = (signal_price / rolling_high) - 1.0

    rows: list[dict] = []

    for idx, row in merged.loc[switch_mask].iterrows():
        if idx <= 0:
            continue

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

        counterfactual_return_column = _mode_to_return_column(from_mode)

        event = {
            "switch_date": row["date"].date().isoformat(),
            "from_mode": from_mode,
            "to_mode": to_mode,
            "transition": f"{from_mode}_to_{to_mode}",
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
            "applied_overlay_slippage_bps": round(
                float(row["applied_overlay_slippage_bps"]),
                3,
            ),
            "overlay_slippage_cost_pct": round(
                float(row["overlay_slippage_cost"]) * 100.0,
                5,
            ),
        }

        start_idx = idx - 1

        for horizon in horizons:
            future_idx = idx + int(horizon)

            if future_idx >= len(merged):
                event[f"actual_next_{horizon}d_return_pct"] = ""
                event[f"stay_previous_next_{horizon}d_return_pct"] = ""
                event[f"switch_value_added_{horizon}d_pct_points"] = ""
                event[f"switch_helped_{horizon}d"] = ""
                continue

            actual_return = (equity.iloc[future_idx] / equity.iloc[start_idx]) - 1.0

            counterfactual_return = _compound_return(
                merged.loc[idx:future_idx, counterfactual_return_column]
            )

            value_added = actual_return - counterfactual_return

            event[f"actual_next_{horizon}d_return_pct"] = round(
                float(actual_return) * 100.0,
                3,
            )
            event[f"stay_previous_next_{horizon}d_return_pct"] = round(
                float(counterfactual_return) * 100.0,
                3,
            )
            event[f"switch_value_added_{horizon}d_pct_points"] = round(
                float(value_added) * 100.0,
                3,
            )
            event[f"switch_helped_{horizon}d"] = bool(value_added > 0)

        rows.append(event)

    return pd.DataFrame(rows)


def _summarise_switch_effectiveness(
    events: pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    groupings = {
        "all_switches": events,
    }

    for transition, transition_df in events.groupby("transition"):
        groupings[f"transition_{transition}"] = transition_df

    for slippage_bps, slippage_df in events.groupby("applied_overlay_slippage_bps"):
        groupings[f"slippage_{slippage_bps:g}_bps"] = slippage_df

    for group_name, group_df in groupings.items():
        row = {
            "group": group_name,
            "switch_count": int(len(group_df)),
            "avg_applied_slippage_bps": round(
                float(group_df["applied_overlay_slippage_bps"].mean()),
                3,
            ),
            "avg_overlay_slippage_cost_pct": round(
                float(group_df["overlay_slippage_cost_pct"].mean()),
                5,
            ),
        }

        for horizon in horizons:
            value_column = f"switch_value_added_{horizon}d_pct_points"
            helped_column = f"switch_helped_{horizon}d"

            valid = group_df[
                group_df[value_column].ne("")
                & group_df[helped_column].ne("")
            ].copy()

            if valid.empty:
                row[f"valid_{horizon}d_events"] = 0
                row[f"helped_{horizon}d_pct"] = ""
                row[f"avg_value_added_{horizon}d_pct_points"] = ""
                row[f"median_value_added_{horizon}d_pct_points"] = ""
                row[f"worst_value_added_{horizon}d_pct_points"] = ""
                row[f"best_value_added_{horizon}d_pct_points"] = ""
                continue

            value_added = valid[value_column].astype(float)
            helped = valid[helped_column].astype(str).str.lower().eq("true")

            row[f"valid_{horizon}d_events"] = int(len(valid))
            row[f"helped_{horizon}d_pct"] = round(float(helped.mean()) * 100.0, 3)
            row[f"avg_value_added_{horizon}d_pct_points"] = round(
                float(value_added.mean()),
                3,
            )
            row[f"median_value_added_{horizon}d_pct_points"] = round(
                float(value_added.median()),
                3,
            )
            row[f"worst_value_added_{horizon}d_pct_points"] = round(
                float(value_added.min()),
                3,
            )
            row[f"best_value_added_{horizon}d_pct_points"] = round(
                float(value_added.max()),
                3,
            )

        rows.append(row)

    return pd.DataFrame(rows)


def _create_switch_effectiveness_conclusion(
    summary: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    all_switches = summary[summary["group"] == "all_switches"]

    if all_switches.empty:
        return pd.DataFrame()

    row = all_switches.iloc[0]

    avg_20d_value_added = float(row["avg_value_added_20d_pct_points"])
    helped_20d_pct = float(row["helped_20d_pct"])
    avg_60d_value_added = float(row["avg_value_added_60d_pct_points"])
    helped_60d_pct = float(row["helped_60d_pct"])

    positive_20d_edge = avg_20d_value_added > 0 and helped_20d_pct > 50
    positive_60d_edge = avg_60d_value_added > 0 and helped_60d_pct > 50

    return pd.DataFrame(
        [
            {
                "claim": "Switches add positive short/intermediate-horizon value.",
                "status": "Survived" if positive_20d_edge else "Failed",
                "evidence_quality": "Compared actual switch outcome to staying in the previous mode",
                "interpretation": (
                    f"Across all switches, average 20D value added was "
                    f"{avg_20d_value_added} percentage points and switches helped "
                    f"{helped_20d_pct}% of valid 20D events."
                ),
            },
            {
                "claim": "Switches add positive medium-horizon value.",
                "status": "Survived" if positive_60d_edge else "Failed",
                "evidence_quality": "Compared actual switch outcome to staying in the previous mode",
                "interpretation": (
                    f"Across all switches, average 60D value added was "
                    f"{avg_60d_value_added} percentage points and switches helped "
                    f"{helped_60d_pct}% of valid 60D events."
                ),
            },
            {
                "claim": "Switch quality is good enough to justify adding more complexity immediately.",
                "status": "Not yet",
                "evidence_quality": "Phase 4B is diagnostic, not an optimisation branch",
                "interpretation": (
                    "This audit identifies whether switches are useful and where they fail. "
                    "It should inform the next validation step, not trigger immediate "
                    "macro/sentiment/ML expansion."
                ),
            },
        ]
    )


def create_regime_switch_overlay_switch_effectiveness(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    audit_config = config.get("phase4_switch_effectiveness", {})

    if not audit_config.get("enabled", False):
        return {
            "events": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    overlay_config = config.get("regime_switch_overlay", {})

    if not overlay_config.get("enabled", False):
        return {
            "events": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    horizons = [int(value) for value in audit_config.get("horizons", [5, 20, 60])]

    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    initial_capital = float(config["initial_capital"])
    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))
    confirmation_days = int(overlay_config.get("confirmation_days", 1))
    baseline_slippage_bps = float(config.get("slippage_bps", 5.0))

    use_dynamic_slippage = bool(audit_config.get("use_dynamic_slippage", True))
    dynamic_slippage = None

    if use_dynamic_slippage:
        dynamic_config = config.get("phase4_dynamic_slippage", {})
        dynamic_slippage = _create_dynamic_slippage_series(
            offensive_result=offensive_result,
            trend_sma_days=trend_sma_days,
            normal_bps=float(dynamic_config.get("normal_bps", 5.0)),
            below_200d_bps=float(dynamic_config.get("below_200d_bps", 15.0)),
            drawdown_10_bps=float(dynamic_config.get("drawdown_10_bps", 25.0)),
            drawdown_20_bps=float(dynamic_config.get("drawdown_20_bps", 50.0)),
        )

    overlay_result = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        initial_capital=initial_capital,
        trend_sma_days=trend_sma_days,
        slippage_bps=baseline_slippage_bps,
        confirmation_days=confirmation_days,
        dynamic_slippage_bps=dynamic_slippage,
    )

    events = _create_switch_effectiveness_events(
        overlay_result=overlay_result,
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        horizons=horizons,
    )
    summary = _summarise_switch_effectiveness(events, horizons)
    conclusion = _create_switch_effectiveness_conclusion(summary)

    return {
        "events": events,
        "summary": summary,
        "conclusion": conclusion,
    }


def write_regime_switch_overlay_switch_effectiveness_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    events = outputs.get("events", pd.DataFrame())
    summary = outputs.get("summary", pd.DataFrame())
    conclusion = outputs.get("conclusion", pd.DataFrame())

    content = f"""# Regime Switch Overlay Switch-Effectiveness Audit

This Phase 4B report tests whether the 3D confirmed regime-switch overlay's switches added value versus staying in the previous mode.

The audit uses the dynamic stress-slippage model when enabled.

## Summary

{summary.to_markdown(index=False) if not summary.empty else "No summary available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}

## Event-Level Audit

{events.to_markdown(index=False) if not events.empty else "No events available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_switch_effectiveness(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_switch_effectiveness(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    events = outputs["events"]
    summary = outputs["summary"]
    conclusion = outputs["conclusion"]

    if events.empty:
        return outputs

    events_path = reports_dir / "regime_switch_overlay_switch_effectiveness_events.csv"
    summary_path = reports_dir / "regime_switch_overlay_switch_effectiveness_summary.csv"
    conclusion_path = reports_dir / "phase4b_switch_effectiveness_conclusion.csv"
    markdown_path = reports_dir / "regime_switch_overlay_switch_effectiveness.md"

    events.to_csv(events_path, index=False)
    summary.to_csv(summary_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_regime_switch_overlay_switch_effectiveness_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay switch-effectiveness summary:")
    print(summary.to_string(index=False))

    print("\nPhase 4B switch-effectiveness conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved switch-effectiveness events to: {events_path}")
    print(f"Saved switch-effectiveness summary to: {summary_path}")
    print(f"Saved Phase 4B conclusion to: {conclusion_path}")
    print(f"Saved switch-effectiveness markdown to: {markdown_path}")

    return outputs