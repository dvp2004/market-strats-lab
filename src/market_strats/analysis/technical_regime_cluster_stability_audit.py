from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.technical_indicator_expansion_diagnostic import (
    _get_phase_config as _get_phase9a_config,
)
from market_strats.analysis.technical_indicator_expansion_diagnostic import (
    _resolve_phase9a_input_frames,
    build_phase9a_analysis_frame,
    build_phase9a_indicator_frame,
    build_phase9a_regime_frame,
)


DEFAULT_PHASE9B_CONFIG: dict[str, Any] = {
    "enabled": False,
    "ticker": "SPY",
    "episode_definitions": {
        "crisis_2006_2010": {
            "start_date": "2006-04-28",
            "end_date": "2010-12-31",
        },
        "post_crisis_2011_2015": {
            "start_date": "2011-01-01",
            "end_date": "2015-12-31",
        },
        "bull_covid_2016_2020": {
            "start_date": "2016-01-01",
            "end_date": "2020-12-31",
        },
        "inflation_2021_2026": {
            "start_date": "2021-01-01",
            "end_date": "2026-05-01",
        },
    },
    "regime_columns": [
        "trend_state",
        "drawdown_bucket",
        "trend_distance_bucket",
        "rsi_bucket",
        "volatility_bucket",
        "long_momentum_state",
        "technical_risk_state",
    ],
    "gates": {
        "min_full_period_cluster_rows": 60,
        "min_episode_cluster_rows": 20,
        "min_episode_coverage_count": 3,
        "min_stability_rows": 8,
        "min_direction_consistency_rate": 0.60,
        "require_instability_report": True,
        "require_no_strategy_promotion": True,
        "max_allowed_diagnostic_role": "Diagnostic only",
    },
}


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


def _get_phase_config(config: dict[str, Any]) -> dict[str, Any]:
    user_config = config.get("phase9b_technical_regime_cluster_stability_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE9B_CONFIG, user_config)


def _direction(value: float) -> str:
    if pd.isna(value):
        return "unknown"
    if value > 0:
        return "helps"
    if value < 0:
        return "lags"
    return "flat"


def _slice_episode(
    analysis_frame: pd.DataFrame,
    *,
    episode_name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    out = analysis_frame[
        (analysis_frame["date"] >= start) & (analysis_frame["date"] <= end)
    ].copy()
    out["episode"] = episode_name

    return out


def build_phase9b_episode_frame(
    analysis_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    episode_definitions = phase_config.get("episode_definitions", {})

    if not episode_definitions:
        raise ValueError("Phase 9B requires episode_definitions.")

    frames = []

    for episode_name, episode_config in episode_definitions.items():
        frames.append(
            _slice_episode(
                analysis_frame,
                episode_name=str(episode_name),
                start_date=str(episode_config["start_date"]),
                end_date=str(episode_config["end_date"]),
            )
        )

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def _cluster_metric_row(
    group: pd.DataFrame,
    *,
    regime_column: str,
    regime_value: str,
    episode: str,
) -> dict[str, Any]:
    candidate_minus_buy_hold = group["candidate_minus_buy_hold"]
    candidate_minus_spy_12m = group["candidate_minus_spy_12m"]

    avg_vs_buy_hold = float(candidate_minus_buy_hold.mean())
    avg_vs_spy_12m = float(candidate_minus_spy_12m.mean())

    return {
        "episode": episode,
        "regime_column": regime_column,
        "regime_value": str(regime_value),
        "rows": int(len(group)),
        "coverage_rate": float(group["indicator_row_complete"].mean()),
        "candidate_minus_buy_hold_avg_daily": avg_vs_buy_hold,
        "candidate_minus_spy_12m_avg_daily": avg_vs_spy_12m,
        "direction_vs_buy_hold": _direction(avg_vs_buy_hold),
        "direction_vs_spy_12m": _direction(avg_vs_spy_12m),
        "underperform_buy_hold_rate": float(
            group["candidate_underperforms_buy_hold"].mean()
        ),
        "underperform_spy_12m_rate": float(
            group["candidate_underperforms_spy_12m"].mean()
        ),
        "worst_candidate_minus_buy_hold_daily": float(candidate_minus_buy_hold.min()),
        "worst_candidate_minus_spy_12m_daily": float(candidate_minus_spy_12m.min()),
    }


def build_phase9b_cluster_episode_metrics(
    analysis_frame: pd.DataFrame,
    episode_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    regime_columns = [str(value) for value in phase_config.get("regime_columns", [])]
    gates = phase_config.get("gates", {})
    min_full_rows = int(gates.get("min_full_period_cluster_rows", 60))
    min_episode_rows = int(gates.get("min_episode_cluster_rows", 20))

    rows: list[dict[str, Any]] = []

    for regime_column in regime_columns:
        if regime_column not in analysis_frame.columns:
            continue

        for regime_value, full_group in analysis_frame.groupby(regime_column, dropna=False):
            if len(full_group) < min_full_rows:
                continue

            rows.append(
                _cluster_metric_row(
                    full_group,
                    regime_column=regime_column,
                    regime_value=str(regime_value),
                    episode="full_period",
                )
            )

            episode_groups = episode_frame[
                episode_frame[regime_column].astype(str) == str(regime_value)
            ].groupby("episode", dropna=False)

            for episode, episode_group in episode_groups:
                if len(episode_group) < min_episode_rows:
                    continue

                rows.append(
                    _cluster_metric_row(
                        episode_group,
                        regime_column=regime_column,
                        regime_value=str(regime_value),
                        episode=str(episode),
                    )
                )

    return pd.DataFrame(rows)


def _consistency_rate(values: list[str], target: str) -> float:
    if not values:
        return 0.0

    return float(sum(value == target for value in values) / len(values))


def build_phase9b_stability_summary(
    cluster_episode_metrics: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if cluster_episode_metrics.empty:
        return pd.DataFrame()

    gates = phase_config.get("gates", {})
    min_episode_coverage = int(gates.get("min_episode_coverage_count", 3))
    min_consistency = float(gates.get("min_direction_consistency_rate", 0.60))

    full_period = cluster_episode_metrics[
        cluster_episode_metrics["episode"] == "full_period"
    ].copy()
    episode_rows = cluster_episode_metrics[
        cluster_episode_metrics["episode"] != "full_period"
    ].copy()

    rows: list[dict[str, Any]] = []

    for _, full_row in full_period.iterrows():
        regime_column = str(full_row["regime_column"])
        regime_value = str(full_row["regime_value"])

        matching = episode_rows[
            (episode_rows["regime_column"] == regime_column)
            & (episode_rows["regime_value"] == regime_value)
        ].copy()

        episode_count = int(len(matching))

        buy_hold_directions = matching["direction_vs_buy_hold"].astype(str).tolist()
        spy12m_directions = matching["direction_vs_spy_12m"].astype(str).tolist()

        full_buy_hold_direction = str(full_row["direction_vs_buy_hold"])
        full_spy12m_direction = str(full_row["direction_vs_spy_12m"])

        buy_hold_consistency = _consistency_rate(
            buy_hold_directions,
            full_buy_hold_direction,
        )
        spy12m_consistency = _consistency_rate(
            spy12m_directions,
            full_spy12m_direction,
        )

        stable_vs_buy_hold = (
            episode_count >= min_episode_coverage
            and buy_hold_consistency >= min_consistency
        )
        stable_vs_spy12m = (
            episode_count >= min_episode_coverage
            and spy12m_consistency >= min_consistency
        )

        rows.append(
            {
                "regime_column": regime_column,
                "regime_value": regime_value,
                "full_period_rows": int(full_row["rows"]),
                "episode_coverage_count": episode_count,
                "full_direction_vs_buy_hold": full_buy_hold_direction,
                "full_direction_vs_spy_12m": full_spy12m_direction,
                "buy_hold_direction_consistency_rate": buy_hold_consistency,
                "spy_12m_direction_consistency_rate": spy12m_consistency,
                "stable_vs_buy_hold": stable_vs_buy_hold,
                "stable_vs_spy_12m": stable_vs_spy12m,
                "stable_both_benchmarks": stable_vs_buy_hold and stable_vs_spy12m,
                "full_candidate_minus_buy_hold_avg_daily": float(
                    full_row["candidate_minus_buy_hold_avg_daily"]
                ),
                "full_candidate_minus_spy_12m_avg_daily": float(
                    full_row["candidate_minus_spy_12m_avg_daily"]
                ),
                "mean_episode_candidate_minus_buy_hold_avg_daily": float(
                    matching["candidate_minus_buy_hold_avg_daily"].mean()
                )
                if not matching.empty
                else np.nan,
                "mean_episode_candidate_minus_spy_12m_avg_daily": float(
                    matching["candidate_minus_spy_12m_avg_daily"].mean()
                )
                if not matching.empty
                else np.nan,
            }
        )

    return pd.DataFrame(rows)


def build_phase9b_instability_report(stability_summary: pd.DataFrame) -> pd.DataFrame:
    if stability_summary.empty:
        return pd.DataFrame()

    out = stability_summary.copy()
    out["instability_score"] = (
        (1.0 - out["buy_hold_direction_consistency_rate"])
        + (1.0 - out["spy_12m_direction_consistency_rate"])
        + (~out["stable_both_benchmarks"].astype(bool)).astype(float)
    )

    out = out.sort_values(
        ["instability_score", "full_period_rows"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return out.head(15)


def build_phase9b_helpful_stability_report(stability_summary: pd.DataFrame) -> pd.DataFrame:
    if stability_summary.empty:
        return pd.DataFrame()

    out = stability_summary[
        (stability_summary["full_direction_vs_buy_hold"] == "helps")
        | (stability_summary["full_direction_vs_spy_12m"] == "helps")
    ].copy()

    if out.empty:
        return pd.DataFrame()

    out["helpfulness_score"] = (
        out["full_candidate_minus_buy_hold_avg_daily"].clip(lower=0.0)
        + out["full_candidate_minus_spy_12m_avg_daily"].clip(lower=0.0)
        + out["stable_both_benchmarks"].astype(float) * 0.001
    )

    out = out.sort_values(
        ["helpfulness_score", "full_period_rows"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return out.head(15)


def build_phase9b_summary(
    cluster_episode_metrics: pd.DataFrame,
    stability_summary: pd.DataFrame,
    instability_report: pd.DataFrame,
    helpful_stability_report: pd.DataFrame,
) -> pd.DataFrame:
    if stability_summary.empty:
        return pd.DataFrame(
            [
                {
                    "stability_rows": 0,
                    "stable_both_benchmarks_rows": 0,
                    "unstable_rows": 0,
                    "instability_report_rows": int(len(instability_report)),
                    "helpful_stability_rows": int(len(helpful_stability_report)),
                    "mean_buy_hold_direction_consistency_rate": 0.0,
                    "mean_spy_12m_direction_consistency_rate": 0.0,
                    "diagnostic_role": "Diagnostic only",
                    "strategy_promotion": False,
                }
            ]
        )

    stable_both = stability_summary["stable_both_benchmarks"].astype(bool)

    return pd.DataFrame(
        [
            {
                "cluster_episode_metric_rows": int(len(cluster_episode_metrics)),
                "stability_rows": int(len(stability_summary)),
                "stable_both_benchmarks_rows": int(stable_both.sum()),
                "unstable_rows": int((~stable_both).sum()),
                "instability_report_rows": int(len(instability_report)),
                "helpful_stability_rows": int(len(helpful_stability_report)),
                "mean_buy_hold_direction_consistency_rate": float(
                    stability_summary["buy_hold_direction_consistency_rate"].mean()
                ),
                "mean_spy_12m_direction_consistency_rate": float(
                    stability_summary["spy_12m_direction_consistency_rate"].mean()
                ),
                "diagnostic_role": "Diagnostic only",
                "strategy_promotion": False,
            }
        ]
    )


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase9b_gate_report(
    summary: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 9B summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    min_stability_rows = int(gates.get("min_stability_rows", 8))
    require_instability = bool(gates.get("require_instability_report", True))
    require_no_promotion = bool(gates.get("require_no_strategy_promotion", True))
    max_role = str(gates.get("max_allowed_diagnostic_role", "Diagnostic only"))

    rows = [
        _gate_row(
            "Cluster stability rows were generated",
            int(row["stability_rows"]) >= min_stability_rows,
            f"{int(row['stability_rows'])} rows; required >= {min_stability_rows}",
        ),
        _gate_row(
            "Instability report was produced",
            (not require_instability) or int(row["instability_report_rows"]) > 0,
            f"{int(row['instability_report_rows'])} rows",
        ),
        _gate_row(
            "Helpful stability report was produced",
            int(row["helpful_stability_rows"]) > 0,
            f"{int(row['helpful_stability_rows'])} rows",
        ),
        _gate_row(
            "Diagnostic does not promote a new strategy",
            (not require_no_promotion) or not bool(row["strategy_promotion"]),
            f"strategy_promotion={bool(row['strategy_promotion'])}",
        ),
        _gate_row(
            "Diagnostic role remains bounded",
            str(row["diagnostic_role"]) == max_role,
            f"diagnostic_role={row['diagnostic_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase9b_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — diagnostic only"
        interpretation = (
            "Phase 9B documented whether Phase 9A technical clusters were stable "
            "across episodes. This does not promote a new rule and does not change "
            "the final candidate hierarchy."
        )
    else:
        verdict = "Failed diagnostic discipline"
        interpretation = (
            "Phase 9B did not satisfy every diagnostic gate. Do not use cluster "
            "evidence for rule design until the issue is corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 9B",
                "diagnostic": "Technical regime cluster stability audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase9b_markdown(
    *,
    summary: pd.DataFrame,
    stability_summary: pd.DataFrame,
    instability_report: pd.DataFrame,
    helpful_stability_report: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 9B — Technical Regime Cluster Stability Audit",
        "",
        "## Purpose",
        "",
        (
            "This diagnostic tests whether Phase 9A technical-regime clusters are "
            "stable across subperiods and episodes."
        ),
        "",
        "It is not a new strategy and it does not promote a trading rule.",
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Stability Summary",
        "",
        stability_summary.to_markdown(index=False),
        "",
        "## Instability Report",
        "",
        instability_report.to_markdown(index=False),
        "",
        "## Helpful Stability Report",
        "",
        helpful_stability_report.to_markdown(index=False),
        "",
        "## Gate Report",
        "",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        conclusion.to_markdown(index=False),
        "",
        "## Limitations",
        "",
        "- This is diagnostic only.",
        "- Cluster stability is not a validated trading rule.",
        "- Episode definitions are research choices and can still introduce bias.",
        "- Any future rule must be pre-defined and separately validated.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase9b_technical_regime_cluster_stability_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
    final_candidate: pd.DataFrame | None = None,
    spy_buy_hold: pd.DataFrame | None = None,
    spy_12m_momentum: pd.DataFrame | None = None,
    price_data: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "analysis_frame": empty,
            "episode_frame": empty,
            "cluster_episode_metrics": empty,
            "stability_summary": empty,
            "instability_report": empty,
            "helpful_stability_report": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    phase9a_config = _get_phase9a_config(config)

    final_candidate, spy_buy_hold, spy_12m_momentum, prices = (
        _resolve_phase9a_input_frames(
            config=config,
            phase_config=phase9a_config,
            final_candidate=final_candidate,
            spy_buy_hold=spy_buy_hold,
            spy_12m_momentum=spy_12m_momentum,
            price_data=price_data,
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
        )
    )

    indicator_frame = build_phase9a_indicator_frame(prices, phase9a_config)
    regime_frame = build_phase9a_regime_frame(indicator_frame, phase9a_config)
    analysis_frame = build_phase9a_analysis_frame(
        final_candidate=final_candidate,
        spy_buy_hold=spy_buy_hold,
        spy_12m_momentum=spy_12m_momentum,
        regime_frame=regime_frame,
    )
    episode_frame = build_phase9b_episode_frame(analysis_frame, phase_config)
    cluster_episode_metrics = build_phase9b_cluster_episode_metrics(
        analysis_frame,
        episode_frame,
        phase_config,
    )
    stability_summary = build_phase9b_stability_summary(
        cluster_episode_metrics,
        phase_config,
    )
    instability_report = build_phase9b_instability_report(stability_summary)
    helpful_stability_report = build_phase9b_helpful_stability_report(
        stability_summary
    )
    summary = build_phase9b_summary(
        cluster_episode_metrics,
        stability_summary,
        instability_report,
        helpful_stability_report,
    )
    gate_report = build_phase9b_gate_report(summary, phase_config)
    conclusion = build_phase9b_conclusion(gate_report)

    analysis_frame.to_csv(
        reports_path / "phase9b_technical_cluster_analysis_frame.csv",
        index=False,
    )
    episode_frame.to_csv(
        reports_path / "phase9b_technical_cluster_episode_frame.csv",
        index=False,
    )
    cluster_episode_metrics.to_csv(
        reports_path / "phase9b_technical_cluster_episode_metrics.csv",
        index=False,
    )
    stability_summary.to_csv(
        reports_path / "phase9b_technical_cluster_stability_summary.csv",
        index=False,
    )
    instability_report.to_csv(
        reports_path / "phase9b_technical_cluster_instability_report.csv",
        index=False,
    )
    helpful_stability_report.to_csv(
        reports_path / "phase9b_technical_cluster_helpful_stability_report.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase9b_technical_cluster_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase9b_technical_cluster_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase9b_technical_cluster_conclusion.csv",
        index=False,
    )

    write_phase9b_markdown(
        summary=summary,
        stability_summary=stability_summary,
        instability_report=instability_report,
        helpful_stability_report=helpful_stability_report,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase9b_technical_regime_cluster_stability_audit.md",
    )

    print("Wrote Phase 9B technical regime cluster stability audit reports.")

    return {
        "analysis_frame": analysis_frame,
        "episode_frame": episode_frame,
        "cluster_episode_metrics": cluster_episode_metrics,
        "stability_summary": stability_summary,
        "instability_report": instability_report,
        "helpful_stability_report": helpful_stability_report,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }