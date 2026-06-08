from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


PHASE17C_SECTION = "phase17c_strategy_factory_watchlist_dashboard"
ROLLING_3Y_BEAT_REFERENCE_THRESHOLD = 60.0

ROLE_MAP = {
    "sf_spy_qqq_60_40_monthly_rebalanced": {
        "watchlist_role": "clean_growth_watchlist",
        "role_caveat": "Equity growth tilt, tech concentration, still drawdown-prone.",
    },
    "sf_spy_core_phase6_overlay_satellite_qqq": {
        "watchlist_role": "baseline_linked_growth_watchlist",
        "role_caveat": (
            "Currently matched 60/40 because Phase6 exposure was risk-on in the tested "
            "window; must prove differentiated value later."
        ),
    },
    "sf_spy_qqq_btc_capped_offensive": {
        "watchlist_role": "high_growth_high_caveat_watchlist",
        "role_caveat": (
            "BTC cap dependency, BTC weekend/gap risk, shorter BTC-driven test period, "
            "ETF-common-date limitation."
        ),
    },
}


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE17C_SECTION, {}) or {}


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_source(path: Path, name: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not path.exists():
        return pd.DataFrame(), {
            "source_name": name,
            "source_path": str(path),
            "source_available": False,
            "blocking_reason": "source_file_missing",
        }
    frame = pd.read_csv(path)
    return frame, {
        "source_name": name,
        "source_path": str(path),
        "source_available": True,
        "blocking_reason": "",
    }


def _scenario_row(metrics: pd.DataFrame, strategy: str, scenario: str) -> pd.Series:
    row = metrics.loc[
        (metrics["strategy"] == strategy) & (metrics["friction_scenario"] == scenario)
    ]
    if row.empty:
        return pd.Series(dtype=object)
    return row.iloc[0]


def _rolling_row(rolling: pd.DataFrame, strategy: str) -> pd.Series:
    if rolling.empty or "strategy" not in rolling.columns:
        return pd.Series(dtype=object)
    row = rolling.loc[rolling["strategy"] == strategy]
    if row.empty:
        return pd.Series(dtype=object)
    return row.iloc[0]


def _watchlist_source_rows(shortlist: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if shortlist.empty or "phase17b_classification" not in shortlist.columns:
        empty = pd.DataFrame()
        return empty, empty
    classification = shortlist["phase17b_classification"].astype(str)
    included = shortlist[classification.str.startswith("paper_watchlist")].copy()
    excluded = shortlist[~classification.str.startswith("paper_watchlist")].copy()
    return included, excluded


def _build_candidates(
    *,
    shortlist: pd.DataFrame,
    friction_metrics: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    btc_gap: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    included, excluded = _watchlist_source_rows(shortlist)
    btc_gap_row = btc_gap.iloc[0] if not btc_gap.empty else pd.Series(dtype=object)
    btc_gap_available = _bool_value(btc_gap_row.get("diagnostic_available", False))
    worst_btc_gap = _float_value(btc_gap_row.get("worst_friday_to_monday_return"), 0.0)

    candidate_rows = []
    role_rows = []
    caveat_rows = []
    stop_rows = []

    for row in included.to_dict(orient="records"):
        strategy = str(row["strategy"])
        role = ROLE_MAP.get(
            strategy,
            {
                "watchlist_role": "unmapped_watchlist_candidate",
                "role_caveat": "No explicit role mapping has been defined.",
            },
        )
        no_cost = _scenario_row(friction_metrics, strategy, "no_extra_cost")
        low = _scenario_row(friction_metrics, strategy, "low")
        realistic = _scenario_row(friction_metrics, strategy, "realistic_stress")
        rolling = _rolling_row(rolling_summary, strategy)

        rolling_3y = _float_value(
            rolling.get("rolling_3y_candidate_beats_spy_pct"),
            _float_value(row.get("rolling_3y_candidate_beats_spy_pct"), 0.0),
        )
        worst_3y = _float_value(rolling.get("worst_3y_active_cagr"), 0.0)
        latest_3y = _float_value(rolling.get("latest_3y_active_cagr"), 0.0)
        max_drawdown = _float_value(realistic.get("max_drawdown_pct"))
        drawdown_advantage = _float_value(
            realistic.get("candidate_max_drawdown_advantage_vs_spy_pct_points"),
            _float_value(row.get("low_drawdown_advantage_vs_spy_pct_points"), 0.0),
        )
        realistic_cagr_delta = _float_value(
            realistic.get("candidate_minus_spy_cagr_pct"),
            _float_value(row.get("realistic_stress_candidate_minus_spy_cagr_pct"), 0.0),
        )
        btc_dependency = _bool_value(row.get("btc_cap_dependency_flag", False))

        candidate_rows.append(
            {
                "candidate_id": strategy,
                "watchlist_role": role["watchlist_role"],
                "shortlist_classification": row["phase17b_classification"],
                "no_cost_cagr_pct": _float_value(no_cost.get("cagr_pct")),
                "low_friction_cagr_pct": _float_value(low.get("cagr_pct")),
                "realistic_stress_cagr_pct": _float_value(realistic.get("cagr_pct")),
                "max_drawdown_pct": max_drawdown,
                "calmar": _float_value(realistic.get("calmar")),
                "rolling_3y_beat_spy_pct": rolling_3y,
                "worst_3y_active_cagr": worst_3y,
                "latest_3y_active_cagr": latest_3y,
                "btc_cap_dependency_flag": btc_dependency,
                "btc_weekend_diagnostic_available": btc_gap_available,
                "promotion_allowed": False,
                "paper_watchlist_only": True,
                "paper_trading_ready": False,
                "final_candidate_replaced": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        )
        role_rows.append(
            {
                "candidate_id": strategy,
                "watchlist_role": role["watchlist_role"],
                "role_caveat": role["role_caveat"],
            }
        )
        caveat_rows.append(
            {
                "candidate_id": strategy,
                "watchlist_role": role["watchlist_role"],
                "primary_caveat": role["role_caveat"],
                "btc_cap_dependency_flag": btc_dependency,
                "btc_weekend_gap_diagnostic_available": btc_gap_available,
                "worst_btc_friday_to_monday_return_pct": worst_btc_gap
                if strategy == "sf_spy_qqq_btc_capped_offensive"
                else pd.NA,
            }
        )

        _append_stop_rows(
            stop_rows,
            strategy=strategy,
            realistic_cagr_delta=realistic_cagr_delta,
            rolling_3y=rolling_3y,
            drawdown_advantage=drawdown_advantage,
            btc_gap_available=btc_gap_available,
            btc_dependency=btc_dependency,
            worst_btc_gap=worst_btc_gap,
        )

    if not excluded.empty:
        excluded = excluded.rename(columns={"strategy": "candidate_id"})
    return (
        pd.DataFrame(candidate_rows),
        pd.DataFrame(role_rows),
        pd.DataFrame(caveat_rows),
        pd.DataFrame(stop_rows),
    )


def _append_stop_rows(
    rows: list[dict[str, Any]],
    *,
    strategy: str,
    realistic_cagr_delta: float,
    rolling_3y: float,
    drawdown_advantage: float,
    btc_gap_available: bool,
    btc_dependency: bool,
    worst_btc_gap: float,
) -> None:
    checks = [
        {
            "stop_condition": "realistic_stress_cagr_no_longer_beats_spy",
            "triggered": realistic_cagr_delta <= 0.0,
            "severity": "warning",
            "details": f"realistic_stress_candidate_minus_spy_cagr_pct={realistic_cagr_delta}",
        },
        {
            "stop_condition": "rolling_3y_beat_rate_below_60_pct",
            "triggered": rolling_3y < ROLLING_3Y_BEAT_REFERENCE_THRESHOLD,
            "severity": "warning",
            "details": f"rolling_3y_candidate_beats_spy_pct={rolling_3y}",
        },
        {
            "stop_condition": "max_drawdown_worse_than_spy_by_more_than_5pp",
            "triggered": drawdown_advantage < -5.0,
            "severity": "warning",
            "details": f"drawdown_advantage_vs_spy_pct_points={drawdown_advantage}",
        },
        {
            "stop_condition": "source_reports_missing_or_stale",
            "triggered": False,
            "severity": "fail_closed",
            "details": "source reports loaded; no timestamp staleness rule configured",
        },
    ]
    if strategy == "sf_spy_qqq_btc_capped_offensive":
        checks.extend(
            [
                {
                    "stop_condition": "btc_weekend_diagnostic_unavailable",
                    "triggered": not btc_gap_available,
                    "severity": "warning",
                    "details": f"btc_gap_available={btc_gap_available}",
                },
                {
                    "stop_condition": "btc_cap_dependency_flag_true",
                    "triggered": btc_dependency,
                    "severity": "warning",
                    "details": f"btc_cap_dependency_flag={btc_dependency}",
                },
                {
                    "stop_condition": "btc_worst_weekend_gap_worse_than_minus_10_pct",
                    "triggered": worst_btc_gap <= -10.0,
                    "severity": "warning",
                    "details": f"worst_btc_friday_to_monday_return_pct={worst_btc_gap}",
                },
                {
                    "stop_condition": "btc_allocation_logic_not_represented_in_paper_preview",
                    "triggered": True,
                    "severity": "warning",
                    "details": "Phase 16 paper preview is SPY baseline only; BTC watchlist remains research-only.",
                },
            ]
        )

    for check in checks:
        rows.append({"candidate_id": strategy, **check})


def _build_gate_report(
    *,
    source_status: list[dict[str, Any]],
    candidates: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    sources_available = all(bool(row["source_available"]) for row in source_status)
    safety_failed = any(
        _bool_value(section.get(flag, False))
        for flag in [
            "live_trading_allowed",
            "real_money_allowed",
            "broker_api_integration_allowed",
        ]
    )
    candidate_flags_failed = False
    if not candidates.empty:
        candidate_flags_failed = bool(
            candidates["promotion_allowed"].map(_bool_value).any()
            or (~candidates["paper_watchlist_only"].map(_bool_value)).any()
            or candidates["live_trading_allowed"].map(_bool_value).any()
            or candidates["real_money_allowed"].map(_bool_value).any()
            or candidates["broker_api_integration_allowed"].map(_bool_value).any()
        )
    rows = [
        {
            "gate": "source_reports_available",
            "gate_status": "passed" if sources_available else "failed",
            "details": "; ".join(
                f"{row['source_name']}={row['source_available']}" for row in source_status
            ),
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        },
        {
            "gate": "watchlist_candidates_present",
            "gate_status": "passed" if not candidates.empty else "failed",
            "details": f"candidate_count={len(candidates)}",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        },
        {
            "gate": "watchlist_flags_fail_closed",
            "gate_status": "failed" if candidate_flags_failed else "passed",
            "details": "promotion/live/real-money/broker flags must remain false; paper_watchlist_only must remain true",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        },
        {
            "gate": "phase17c_safety_config_false",
            "gate_status": "failed" if safety_failed else "passed",
            "details": "Phase 17C config safety flags must remain false",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        },
    ]
    return pd.DataFrame(rows)


def _summary(
    *,
    candidates: pd.DataFrame,
    excluded: pd.DataFrame,
    gate_report: pd.DataFrame,
) -> pd.DataFrame:
    all_gates_passed = bool((gate_report["gate_status"] == "passed").all())
    return pd.DataFrame(
        [
            {
                "phase": "Phase 17C",
                "diagnostic": "Strategy Factory Paper-Watchlist Dashboard",
                "decision": (
                    "strategy_factory_watchlist_dashboard_completed_no_promotion"
                    if all_gates_passed
                    else "strategy_factory_watchlist_dashboard_failed_closed"
                ),
                "watchlist_candidate_count": len(candidates),
                "excluded_candidate_count": len(excluded),
                "paper_trading_ready_candidate_count": 0,
                "phase6b_phase6c_operational_baseline_unchanged": True,
                "candidate_promotion_allowed": False,
                "final_candidate_replaced": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "all_gates_passed": all_gates_passed,
            }
        ]
    )


def _conclusion(summary: pd.DataFrame) -> pd.DataFrame:
    row = summary.iloc[0]
    return pd.DataFrame(
        [
            {
                "phase": "Phase 17C",
                "decision": row["decision"],
                "all_gates_passed": bool(row["all_gates_passed"]),
                "watchlist_only": True,
                "paper_trading_ready": False,
                "candidate_promotion_allowed": False,
                "final_candidate_replaced": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )


def _risk_flags(candidates: pd.DataFrame, caveats: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame(
            [
                {
                    "candidate_id": "none",
                    "risk_flag": "no_watchlist_candidates_available",
                    "risk_flag_triggered": True,
                    "details": "Phase 17C failed closed before candidate inclusion.",
                }
            ]
        )
    rows = []
    caveat_lookup = caveats.set_index("candidate_id") if not caveats.empty else pd.DataFrame()
    for row in candidates.to_dict(orient="records"):
        candidate = row["candidate_id"]
        caveat = (
            caveat_lookup.loc[candidate]["primary_caveat"]
            if not caveat_lookup.empty and candidate in caveat_lookup.index
            else ""
        )
        rows.append(
            {
                "candidate_id": candidate,
                "risk_flag": "watchlist_caveat_present",
                "risk_flag_triggered": True,
                "details": caveat,
            }
        )
        if _bool_value(row.get("btc_cap_dependency_flag", False)):
            rows.append(
                {
                    "candidate_id": candidate,
                    "risk_flag": "btc_cap_dependency",
                    "risk_flag_triggered": True,
                    "details": "Leadership depends materially on BTC cap sensitivity.",
                }
            )
    return pd.DataFrame(rows)


def _plot_metric_snapshot(snapshot: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    if snapshot.empty:
        ax.text(0.5, 0.5, "No watchlist candidates", ha="center", va="center")
        ax.set_axis_off()
    else:
        plot_frame = snapshot.set_index("candidate_id")[
            ["low_friction_cagr_pct", "realistic_stress_cagr_pct", "max_drawdown_pct"]
        ]
        plot_frame.plot(kind="bar", ax=ax)
        ax.set_title("Phase 17C Watchlist Metric Snapshot")
        ax.set_ylabel("Percent")
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_rolling_beat_rate(snapshot: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    if snapshot.empty:
        ax.text(0.5, 0.5, "No rolling watchlist data", ha="center", va="center")
        ax.set_axis_off()
    else:
        ax.bar(snapshot["candidate_id"], snapshot["rolling_3y_beat_spy_pct"])
        ax.axhline(ROLLING_3Y_BEAT_REFERENCE_THRESHOLD, color="black", linewidth=0.8)
        ax.set_title("Phase 17C Rolling 3Y Beat Rate vs SPY")
        ax.set_ylabel("3Y windows beating SPY %")
        ax.set_ylim(0, 105)
        ax.grid(True, axis="y", alpha=0.25)
        ax.tick_params(axis="x", labelrotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _write_dashboard_index(
    *,
    path: Path,
    candidates: pd.DataFrame,
    caveats: pd.DataFrame,
    conclusion: pd.DataFrame,
) -> None:
    decision = conclusion.iloc[0]["decision"] if not conclusion.empty else ""
    lines = [
        "# Strategy Factory Paper-Watchlist Dashboard",
        "",
        "Research and paper-watchlist only. No Strategy Factory candidate is promoted.",
        "",
        "- Live trading allowed: False",
        "- Real money allowed: False",
        "- Broker/API integration allowed: False",
        "- Candidate promotion allowed: False",
        "- Paper-trading-ready candidates: 0",
        "- Phase 6B/6C overlay remains the operational paper baseline.",
        "- Strategy Factory candidates are separate watchlist research candidates.",
        "",
        "## Dashboard Files",
        "",
        "- `watchlist_overview.csv`",
        "- `watchlist_roles.csv`",
        "- `watchlist_risk_flags.csv`",
        "- `watchlist_metric_snapshot.csv`",
        "- `watchlist_rolling_snapshot.csv`",
        "- `watchlist_stop_conditions.csv`",
        "- `watchlist_metric_snapshot.png`",
        "- `watchlist_rolling_3y_beat_rate.png`",
        "",
        "## Watchlist Candidates",
        "",
    ]
    for row in candidates.to_dict(orient="records"):
        lines.append(
            f"- {row['candidate_id']}: {row['watchlist_role']} "
            f"(classification: {row['shortlist_classification']})"
        )
    lines.extend(["", "## Caveats", ""])
    for row in caveats.to_dict(orient="records"):
        lines.append(f"- {row['candidate_id']}: {row['primary_caveat']}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No candidate is promoted.",
            "- No final candidate is replaced.",
            "- No live, real-money, or broker/API action is allowed.",
            f"- Phase 17C decision: {decision}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_outputs(
    *,
    output_dir: Path,
    dashboard_dir: Path,
    summary: pd.DataFrame,
    candidates: pd.DataFrame,
    caveats: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    roles: pd.DataFrame,
    risk_flags: pd.DataFrame,
    metric_snapshot: pd.DataFrame,
    rolling_snapshot: pd.DataFrame,
    stop_conditions: pd.DataFrame,
) -> None:
    summary.to_csv(output_dir / "phase17c_watchlist_summary.csv", index=False)
    candidates.to_csv(output_dir / "phase17c_watchlist_candidates.csv", index=False)
    caveats.to_csv(output_dir / "phase17c_watchlist_caveats.csv", index=False)
    gate_report.to_csv(output_dir / "phase17c_watchlist_gate_report.csv", index=False)
    conclusion.to_csv(output_dir / "phase17c_watchlist_conclusion.csv", index=False)
    summary.to_csv(dashboard_dir / "watchlist_overview.csv", index=False)
    roles.to_csv(dashboard_dir / "watchlist_roles.csv", index=False)
    risk_flags.to_csv(dashboard_dir / "watchlist_risk_flags.csv", index=False)
    metric_snapshot.to_csv(dashboard_dir / "watchlist_metric_snapshot.csv", index=False)
    rolling_snapshot.to_csv(dashboard_dir / "watchlist_rolling_snapshot.csv", index=False)
    stop_conditions.to_csv(dashboard_dir / "watchlist_stop_conditions.csv", index=False)
    _plot_metric_snapshot(metric_snapshot, dashboard_dir / "watchlist_metric_snapshot.png")
    _plot_rolling_beat_rate(
        rolling_snapshot,
        dashboard_dir / "watchlist_rolling_3y_beat_rate.png",
    )
    _write_dashboard_index(
        path=dashboard_dir / "index.md",
        candidates=candidates,
        caveats=caveats,
        conclusion=conclusion,
    )


def save_phase17c_strategy_factory_watchlist_dashboard(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _phase_config(config)
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "candidates": empty, "gate_report": empty}

    output_dir = Path(section.get("output_dir", "reports/strategy_factory/watchlist"))
    dashboard_dir = Path(
        section.get("dashboard_dir", output_dir / "dashboard")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    source_specs = [
        ("shortlist", Path(section.get("source_shortlist_file", ""))),
        ("metrics", Path(section.get("source_metrics_file", ""))),
        ("rolling", Path(section.get("source_rolling_file", ""))),
        ("btc_gap", Path(section.get("source_btc_gap_file", ""))),
    ]
    source_frames: dict[str, pd.DataFrame] = {}
    source_status = []
    for name, path in source_specs:
        frame, status = _read_source(path, name)
        source_frames[name] = frame
        source_status.append(status)

    sources_available = all(bool(row["source_available"]) for row in source_status)
    if sources_available:
        candidates, roles, caveats, stop_conditions = _build_candidates(
            shortlist=source_frames["shortlist"],
            friction_metrics=source_frames["metrics"],
            rolling_summary=source_frames["rolling"],
            btc_gap=source_frames["btc_gap"],
        )
        _included, excluded = _watchlist_source_rows(source_frames["shortlist"])
    else:
        candidates = pd.DataFrame()
        roles = pd.DataFrame()
        caveats = pd.DataFrame(
            [
                {
                    "candidate_id": "none",
                    "watchlist_role": "none",
                    "primary_caveat": "Phase 17C failed closed because source reports are missing.",
                    "btc_cap_dependency_flag": False,
                    "btc_weekend_gap_diagnostic_available": False,
                }
            ]
        )
        stop_conditions = pd.DataFrame(
            [
                {
                    "candidate_id": "all",
                    "stop_condition": "source_reports_missing_or_stale",
                    "triggered": True,
                    "severity": "fail_closed",
                    "details": "; ".join(
                        f"{row['source_name']}:{row['blocking_reason']}"
                        for row in source_status
                        if not row["source_available"]
                    ),
                }
            ]
        )
        excluded = pd.DataFrame()

    gate_report = _build_gate_report(
        source_status=source_status,
        candidates=candidates,
        section=section,
    )
    summary = _summary(candidates=candidates, excluded=excluded, gate_report=gate_report)
    conclusion = _conclusion(summary)
    risk_flags = _risk_flags(candidates, caveats)
    metric_snapshot = candidates[
        [
            "candidate_id",
            "low_friction_cagr_pct",
            "realistic_stress_cagr_pct",
            "max_drawdown_pct",
            "calmar",
        ]
    ].copy() if not candidates.empty else pd.DataFrame()
    rolling_snapshot = candidates[
        [
            "candidate_id",
            "rolling_3y_beat_spy_pct",
            "worst_3y_active_cagr",
            "latest_3y_active_cagr",
        ]
    ].copy() if not candidates.empty else pd.DataFrame()

    _write_outputs(
        output_dir=output_dir,
        dashboard_dir=dashboard_dir,
        summary=summary,
        candidates=candidates,
        caveats=caveats,
        gate_report=gate_report,
        conclusion=conclusion,
        roles=roles,
        risk_flags=risk_flags,
        metric_snapshot=metric_snapshot,
        rolling_snapshot=rolling_snapshot,
        stop_conditions=stop_conditions,
    )

    outputs = {
        "summary": summary,
        "candidates": candidates,
        "caveats": caveats,
        "gate_report": gate_report,
        "conclusion": conclusion,
        "roles": roles,
        "risk_flags": risk_flags,
        "metric_snapshot": metric_snapshot,
        "rolling_snapshot": rolling_snapshot,
        "stop_conditions": stop_conditions,
    }
    print("Wrote Phase 17C Strategy Factory watchlist dashboard reports.")
    return outputs
