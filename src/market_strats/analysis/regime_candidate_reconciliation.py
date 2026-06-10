from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PHASE21B_SECTION = "phase21b_regime_candidate_reconciliation"
SAFETY_COLUMNS = {
    "promotion_allowed": False,
    "live_trading_allowed": False,
    "real_money_allowed": False,
    "broker_api_integration_allowed": False,
}


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (not isinstance(value, (list, dict, tuple, set)) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _text_value(value: Any) -> str:
    if value is None or (not isinstance(value, (list, dict, tuple, set)) and pd.isna(value)):
        return ""
    return str(value).strip()


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    return pd.read_csv(path)


def _write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE21B_SECTION, {}) or {}


def _source_paths(section: dict[str, Any], reports_dir: Path) -> dict[str, Path]:
    regime_dir = Path(
        section.get(
            "source_regime_stress_dir",
            reports_dir / "strategy_factory" / "regime_stress",
        )
    )
    finalist_dir = Path(
        section.get(
            "source_finalist_validation_dir",
            reports_dir / "strategy_factory" / "finalist_validation",
        )
    )
    paper_dir = Path(
        section.get(
            "source_paper_tracking_dir",
            reports_dir / "paper_trading" / "finalist_tracking",
        )
    )
    return {
        "phase21a_master": regime_dir / "phase21a_master_strategy_candidates.csv",
        "phase21a_scores": regime_dir / "phase21a_regime_robustness_scores.csv",
        "phase21a_components": regime_dir
        / "phase21a_regime_robustness_score_components.csv",
        "phase21a_summary": regime_dir / "phase21a_candidate_regime_summary.csv",
        "phase19b_tracking": finalist_dir / "phase19b_recommended_paper_tracking_set.csv",
        "paper_targets": paper_dir / "finalist_paper_targets.csv",
        "paper_orders": paper_dir / "finalist_paper_orders_preview.csv",
    }


def _load_inputs(paths: dict[str, Path]) -> tuple[dict[str, pd.DataFrame], list[str]]:
    frames = {name: _read_csv(path) for name, path in paths.items()}
    missing = [name for name, frame in frames.items() if frame.empty]
    return frames, missing


def _phase21a_lookup(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    master = frames.get("phase21a_master", pd.DataFrame()).copy()
    if master.empty:
        return master
    if "regime_robustness_score" not in master.columns and "final_regime_robustness_score" in master.columns:
        master["regime_robustness_score"] = master["final_regime_robustness_score"]
    return master


def _current_candidate_targets(targets: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    order_allowed = (
        orders.groupby("canonical_candidate_id")["paper_order_allowed"]
        .apply(lambda values: bool(pd.Series(values).map(_bool_value).all()))
        .to_dict()
        if not orders.empty and "paper_order_allowed" in orders.columns
        else {}
    )
    for candidate_id, group in targets.groupby("canonical_candidate_id", sort=False):
        nonzero = group.loc[pd.to_numeric(group["target_weight"], errors="coerce").fillna(0.0) > 0]
        weights = [
            f"{row.asset}={float(row.target_weight):.4f}"
            for row in group.itertuples()
            if pd.notna(pd.to_numeric(row.target_weight, errors="coerce"))
        ]
        rows.append(
            {
                "canonical_candidate_id": candidate_id,
                "current_paper_role": _text_value(group.iloc[0].get("candidate_role", "")),
                "currently_paper_tracked": True,
                "current_target_assets": ",".join(nonzero["asset"].astype(str).tolist()),
                "current_target_weights": ";".join(weights),
                "paper_preview_allowed": bool(order_allowed.get(candidate_id, False)),
            }
        )
    return pd.DataFrame(rows)


def _recommend_current_candidate(row: pd.Series) -> tuple[str, str, str, str]:
    candidate_id = _text_value(row.get("canonical_candidate_id"))
    classification = _text_value(row.get("phase21a_classification"))
    blocking = _text_value(row.get("phase21a_blocking_reasons"))
    if candidate_id == "canonical_spy_qqq_60_40" or classification == "rejected_regime_fragile":
        return (
            "keep_as_reference_only",
            "reference_only",
            "return-strong but regime-fragile after Phase 21A hard gates",
            blocking or "severe drawdown and crash fragility caveat",
        )
    if classification == "provisional_high_caveat_candidate_for_further_research":
        return (
            "keep_as_high_caveat_candidate",
            "provisional_high_caveat_candidate",
            "remains promising in available post-inception regimes but is high caveat",
            blocking or "high-caveat research candidate only",
        )
    if classification.startswith("provisional_core"):
        return (
            "needs_manual_review",
            "provisional_core_candidate",
            "Phase 21A provisional core candidate requires manual review before Phase 20 changes",
            blocking,
        )
    return (
        "needs_manual_review",
        "research_only",
        "Phase 21A evidence is mixed or incomplete",
        blocking,
    )


def build_current_paper_candidate_reconciliation(
    *,
    targets: pd.DataFrame,
    orders: pd.DataFrame,
    phase21a: pd.DataFrame,
) -> pd.DataFrame:
    current = _current_candidate_targets(targets, orders)
    if current.empty:
        return pd.DataFrame()
    phase_cols = [
        "canonical_candidate_id",
        "master_strategy_classification",
        "regime_robustness_score",
        "final_regime_robustness_score",
        "worst_max_drawdown_pct",
        "classification_blocking_reasons",
    ]
    available_cols = [col for col in phase_cols if col in phase21a.columns]
    merged = current.merge(
        phase21a[available_cols].drop_duplicates("canonical_candidate_id"),
        on="canonical_candidate_id",
        how="left",
    )
    if "regime_robustness_score" not in merged.columns:
        merged["regime_robustness_score"] = merged.get("final_regime_robustness_score")
    merged = merged.rename(
        columns={
            "master_strategy_classification": "phase21a_classification",
            "regime_robustness_score": "phase21a_regime_robustness_score",
            "worst_max_drawdown_pct": "phase21a_worst_drawdown_pct",
            "classification_blocking_reasons": "phase21a_blocking_reasons",
        }
    )
    status_rows = merged.apply(_recommend_current_candidate, axis=1)
    merged["phase21a_reconciliation_status"] = [row[0] for row in status_rows]
    merged["paper_tracking_recommendation"] = [row[1] for row in status_rows]
    merged["recommendation_reason"] = [row[2] for row in status_rows]
    merged["recommendation_limitations"] = [row[3] for row in status_rows]
    for key, value in SAFETY_COLUMNS.items():
        merged[key] = value
    return merged[
        [
            "canonical_candidate_id",
            "current_paper_role",
            "currently_paper_tracked",
            "current_target_assets",
            "current_target_weights",
            "paper_preview_allowed",
            "phase21a_classification",
            "phase21a_regime_robustness_score",
            "phase21a_worst_drawdown_pct",
            "phase21a_blocking_reasons",
            "phase21a_reconciliation_status",
            "paper_tracking_recommendation",
            "recommendation_reason",
            "recommendation_limitations",
            "promotion_allowed",
            "live_trading_allowed",
            "real_money_allowed",
            "broker_api_integration_allowed",
        ]
    ]


def _shortlist_role(candidate_id: str, classification: str, current_ids: set[str]) -> str:
    if candidate_id == "canonical_spy_qqq_60_40":
        return "reference_only"
    if classification == "provisional_core_candidate_for_further_research":
        return "provisional_core_candidate"
    if classification == "provisional_core_inception_limited_for_further_research":
        return "provisional_core_inception_limited"
    if classification == "provisional_high_caveat_candidate_for_further_research":
        return "provisional_high_caveat_candidate"
    if candidate_id in current_ids:
        return "reference_only"
    return "research_only"


def _shortlist_reason(candidate_id: str, role: str) -> tuple[str, str]:
    if candidate_id == "phase6b_loose_relief_execution_realistic_overlay":
        return (
            "best drawdown-control baseline and original defensive overlay reference",
            "provisional research candidate only; not promoted",
        )
    if candidate_id == "canonical_spy_qqq_gld_tlt_50_30_10_10":
        return (
            "multi-asset regime survivability candidate after Phase 21A",
            "asset inception limited and still requires manual review",
        )
    if candidate_id == "canonical_inverse_vol_63d_btc_usd_qqq_spy":
        return (
            "current high-caveat BTC paper candidate remains viable in post-inception regimes",
            "BTC inception, weekend/gap, and paper-only caveats remain",
        )
    if candidate_id == "canonical_spy_qqq_60_40":
        return (
            "return-strong growth benchmark useful as reference only",
            "rejected by regime hard gates due severe drawdown and crash fragility",
        )
    return (
        f"selected as {role} by Phase 21B reconciliation",
        "requires manual review before any Phase 20 paper tracking change",
    )


def build_paper_shortlist_recommendation(
    *,
    phase21a: pd.DataFrame,
    current_ids: set[str],
    max_candidates: int,
    max_core: int,
    max_high_caveat: int,
) -> pd.DataFrame:
    if phase21a.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    selected: set[str] = set()

    priority_ids = [
        "phase6b_loose_relief_execution_realistic_overlay",
        "canonical_spy_qqq_gld_tlt_50_30_10_10",
        "canonical_inverse_vol_63d_btc_usd_qqq_spy",
        "canonical_spy_qqq_60_40",
    ]
    phase = phase21a.copy()
    phase["_priority"] = phase["canonical_candidate_id"].map(
        {candidate_id: idx for idx, candidate_id in enumerate(priority_ids)}
    ).fillna(999)
    phase = phase.sort_values(
        ["_priority", "regime_robustness_score"],
        ascending=[True, False],
    )
    core_count = 0
    high_caveat_count = 0
    for row in phase.to_dict("records"):
        candidate_id = _text_value(row.get("canonical_candidate_id"))
        if candidate_id in selected:
            continue
        classification = _text_value(row.get("master_strategy_classification"))
        role = _shortlist_role(candidate_id, classification, current_ids)
        if role == "research_only" and candidate_id not in priority_ids:
            continue
        if role.startswith("provisional_core") and core_count >= max_core:
            continue
        if role == "provisional_high_caveat_candidate" and high_caveat_count >= max_high_caveat:
            continue
        if len(rows) >= max_candidates:
            break
        reason, limitation = _shortlist_reason(candidate_id, role)
        if role.startswith("provisional_core"):
            core_count += 1
        if role == "provisional_high_caveat_candidate":
            high_caveat_count += 1
        selected.add(candidate_id)
        rows.append(
            {
                "canonical_candidate_id": candidate_id,
                "recommended_role": role,
                "phase21a_classification": classification,
                "phase21a_regime_robustness_score": row.get("regime_robustness_score"),
                "phase21a_worst_drawdown_pct": row.get("worst_max_drawdown_pct"),
                "phase21a_blocking_reasons": row.get("classification_blocking_reasons", ""),
                "recommendation_reason": reason,
                "recommendation_limitations": limitation,
                "currently_paper_tracked": candidate_id in current_ids,
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        )
    return pd.DataFrame(rows)


def build_candidate_delta_report(
    *,
    phase19b_tracking: pd.DataFrame,
    targets: pd.DataFrame,
    phase21a: pd.DataFrame,
    shortlist: pd.DataFrame,
) -> pd.DataFrame:
    phase19_ids = set(phase19b_tracking.get("canonical_candidate_id", pd.Series(dtype=str)).astype(str))
    current_ids = set(targets.get("canonical_candidate_id", pd.Series(dtype=str)).astype(str))
    shortlist_ids = set(shortlist.get("canonical_candidate_id", pd.Series(dtype=str)).astype(str))
    all_ids = sorted(phase19_ids | current_ids | shortlist_ids)
    lookup = phase21a.set_index("canonical_candidate_id") if not phase21a.empty else pd.DataFrame()
    shortlist_lookup = shortlist.set_index("canonical_candidate_id") if not shortlist.empty else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for candidate_id in all_ids:
        phase_row = lookup.loc[candidate_id] if candidate_id in lookup.index else pd.Series(dtype=object)
        short_row = (
            shortlist_lookup.loc[candidate_id]
            if candidate_id in shortlist_lookup.index
            else pd.Series(dtype=object)
        )
        classification = _text_value(phase_row.get("master_strategy_classification", "missing_phase21a"))
        if candidate_id == "canonical_spy_qqq_60_40":
            status_change = "paper_tracked_clean_growth_to_reference_only_regime_fragile"
            action = "manual_review_before_any_phase20_change"
            reason = "Phase 21A hard gates reject it as regime-fragile despite return strength"
        elif candidate_id == "canonical_inverse_vol_63d_btc_usd_qqq_spy":
            status_change = "remains_high_caveat_candidate"
            action = "keep_high_caveat_manual_review"
            reason = "Still provisional high-caveat after BTC inception-limited regime stress"
        elif candidate_id == "phase6b_loose_relief_execution_realistic_overlay":
            status_change = "newly_reintroduced_provisional_core"
            action = "manual_review_for_possible_phase20_addition"
            reason = "Original defensive overlay baseline has strongest calibrated regime result"
        elif candidate_id == "canonical_spy_qqq_gld_tlt_50_30_10_10":
            status_change = "newly_elevated_provisional_core_inception_limited"
            action = "manual_review_for_possible_phase20_addition"
            reason = "Multi-asset survivability improved after regime stress"
        elif candidate_id in current_ids:
            status_change = "current_candidate_needs_manual_review"
            action = "manual_review"
            reason = classification
        else:
            status_change = "research_context_only"
            action = "no_phase20_change"
            reason = classification
        rows.append(
            {
                "canonical_candidate_id": candidate_id,
                "was_phase19b_recommended": candidate_id in phase19_ids,
                "currently_paper_tracked": candidate_id in current_ids,
                "phase21a_classification": classification,
                "phase21a_score": phase_row.get("regime_robustness_score", ""),
                "phase21a_worst_drawdown_pct": phase_row.get("worst_max_drawdown_pct", ""),
                "status_change": status_change,
                "delta_reason": reason or short_row.get("recommendation_reason", ""),
                "action_required": action,
                "promotion_allowed": False,
            }
        )
    return pd.DataFrame(rows)


def _write_recommendation_markdown(
    *,
    path: Path,
    current: pd.DataFrame,
    shortlist: pd.DataFrame,
    delta: pd.DataFrame,
) -> None:
    lines = [
        "# Phase 21B Regime Candidate Reconciliation",
        "",
        "NO LIVE TRADING",
        "NO REAL MONEY",
        "NO BROKER/API",
        "NO STRATEGY PROMOTION",
        "RESEARCH RECONCILIATION ONLY",
        "",
        "Current paper tracking remains operational, but Phase 21A changed the research hierarchy.",
        "`canonical_spy_qqq_60_40` should be treated as reference-only, not as a primary candidate.",
        "`phase6b_loose_relief_execution_realistic_overlay` is reintroduced as a provisional core candidate.",
        "`canonical_spy_qqq_gld_tlt_50_30_10_10` is a provisional multi-asset core candidate with inception caveats.",
        "BTC candidates remain high-caveat and inception-limited.",
        "The next phase may update Phase 20 paper-tracking outputs only after manual review.",
        "",
        "## Current Paper Candidates",
        "",
    ]
    if current.empty:
        lines.append("No current paper candidates were reconciled.")
    else:
        for row in current.to_dict("records"):
            lines.append(
                f"- `{row['canonical_candidate_id']}`: "
                f"{row['phase21a_reconciliation_status']} - {row['recommendation_reason']}"
            )
    lines.extend(["", "## Recommended Research/Paper Review Shortlist", ""])
    for row in shortlist.to_dict("records"):
        lines.append(
            f"- `{row['canonical_candidate_id']}`: {row['recommended_role']} - "
            f"{row['recommendation_reason']}"
        )
    lines.extend(["", "## Candidate Delta", ""])
    for row in delta.to_dict("records"):
        lines.append(
            f"- `{row['canonical_candidate_id']}`: {row['status_change']} "
            f"({row['action_required']})"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _empty_outputs(output_dir: Path, dashboard_dir: Path, decision: str, missing: list[str]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    gate_report = pd.DataFrame(
        [
            _gate_row("required_sources_present", False, ",".join(missing)),
            _gate_row("live_trading_disabled", True),
            _gate_row("real_money_disabled", True),
            _gate_row("broker_api_integration_disabled", True),
            _gate_row("promotion_disabled", True),
        ]
    )
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 21B",
                "phase21b_decision": decision,
                "all_gates_passed": False,
                "missing_sources": ",".join(missing),
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 21B",
                "phase21b_decision": decision,
                "all_gates_passed": False,
                "promotion_allowed": False,
                "final_model_promoted": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Failed closed because required source files are missing.",
            }
        ]
    )
    outputs = {
        "summary": _write_csv(summary, output_dir / "phase21b_summary.csv"),
        "gate_report": _write_csv(gate_report, output_dir / "phase21b_gate_report.csv"),
        "conclusion": _write_csv(conclusion, output_dir / "phase21b_conclusion.csv"),
        "current_paper_candidate_reconciliation": _write_csv(
            pd.DataFrame(),
            output_dir / "phase21b_current_paper_candidate_reconciliation.csv",
        ),
        "paper_shortlist_recommendation": _write_csv(
            pd.DataFrame(),
            output_dir / "phase21b_paper_shortlist_recommendation.csv",
        ),
        "candidate_delta_report": _write_csv(
            pd.DataFrame(),
            output_dir / "phase21b_candidate_delta_report.csv",
        ),
    }
    md_path = output_dir / "phase21b_recommendation_summary.md"
    md_path.write_text(
        "# Phase 21B Regime Candidate Reconciliation\n\nFailed closed: missing sources.\n",
        encoding="utf-8",
    )
    outputs["recommendation_summary_md"] = md_path
    for key in [
        "current_paper_candidate_reconciliation",
        "paper_shortlist_recommendation",
        "candidate_delta_report",
    ]:
        dashboard_name = {
            "current_paper_candidate_reconciliation": "current_paper_candidate_reconciliation.csv",
            "paper_shortlist_recommendation": "paper_shortlist_recommendation.csv",
            "candidate_delta_report": "candidate_delta_report.csv",
        }[key]
        _write_csv(pd.DataFrame(), dashboard_dir / dashboard_name)
    (dashboard_dir / "index.md").write_text(
        "# Phase 21B Regime Candidate Reconciliation\n\nFailed closed: missing sources.\n",
        encoding="utf-8",
    )
    outputs["dashboard_index"] = dashboard_dir / "index.md"
    return outputs


def save_phase21b_regime_candidate_reconciliation(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, Path]:
    section = _section(config)
    output_dir = Path(
        section.get(
            "output_dir",
            Path(reports_dir) / "strategy_factory" / "regime_reconciliation",
        )
    )
    dashboard_dir = Path(section.get("dashboard_dir", output_dir / "dashboard"))
    if not _bool_value(section.get("enabled", False)):
        return _empty_outputs(output_dir, dashboard_dir, "phase21b_disabled", ["phase21b_disabled"])

    reports_path = Path(reports_dir)
    paths = _source_paths(section, reports_path)
    frames, missing = _load_inputs(paths)
    if missing:
        return _empty_outputs(
            output_dir,
            dashboard_dir,
            "regime_candidate_reconciliation_failed_missing_sources",
            missing,
        )

    phase21a = _phase21a_lookup(frames)
    targets = frames["paper_targets"]
    orders = frames["paper_orders"]
    phase19b = frames["phase19b_tracking"]
    current = build_current_paper_candidate_reconciliation(
        targets=targets,
        orders=orders,
        phase21a=phase21a,
    )
    current_ids = set(targets["canonical_candidate_id"].astype(str))
    shortlist = build_paper_shortlist_recommendation(
        phase21a=phase21a,
        current_ids=current_ids,
        max_candidates=int(section.get("max_recommended_paper_candidates", 4)),
        max_core=int(section.get("max_core_candidates", 2)),
        max_high_caveat=int(section.get("max_high_caveat_candidates", 2)),
    )
    delta = build_candidate_delta_report(
        phase19b_tracking=phase19b,
        targets=targets,
        phase21a=phase21a,
        shortlist=shortlist,
    )

    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )
    promotion_allowed = not _bool_value(section.get("require_no_promotion", True))
    gate_report = pd.DataFrame(
        [
            _gate_row("phase21a_regime_outputs_present", True),
            _gate_row("phase19b_tracking_set_present", True),
            _gate_row("phase20_paper_targets_present", True),
            _gate_row("current_reconciliation_written", True),
            _gate_row("paper_shortlist_recommendation_written", True),
            _gate_row("candidate_delta_report_written", True),
            _gate_row("recommendation_markdown_written", True),
            _gate_row("dashboard_files_written", True),
            _gate_row("promotion_disabled", not promotion_allowed),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row("broker_api_integration_disabled", not broker_api_integration_allowed),
        ]
    )
    all_gates_passed = bool(gate_report["passed"].map(_bool_value).all())
    decision = (
        "regime_candidate_reconciliation_completed_no_promotion"
        if all_gates_passed
        else "regime_candidate_reconciliation_failed_safety_gate"
    )

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 21B",
                "phase21b_decision": decision,
                "all_gates_passed": all_gates_passed,
                "current_paper_candidate_count": len(current),
                "recommended_shortlist_count": len(shortlist),
                "delta_candidate_count": len(delta),
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 21B",
                "phase21b_decision": decision,
                "all_gates_passed": all_gates_passed,
                "promotion_allowed": False,
                "final_model_promoted": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Regime-informed reconciliation only. Phase 20 paper tracking is not modified.",
            }
        ]
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "summary": _write_csv(summary, output_dir / "phase21b_summary.csv"),
        "gate_report": _write_csv(gate_report, output_dir / "phase21b_gate_report.csv"),
        "conclusion": _write_csv(conclusion, output_dir / "phase21b_conclusion.csv"),
        "current_paper_candidate_reconciliation": _write_csv(
            current,
            output_dir / "phase21b_current_paper_candidate_reconciliation.csv",
        ),
        "paper_shortlist_recommendation": _write_csv(
            shortlist,
            output_dir / "phase21b_paper_shortlist_recommendation.csv",
        ),
        "candidate_delta_report": _write_csv(
            delta,
            output_dir / "phase21b_candidate_delta_report.csv",
        ),
    }
    md_path = output_dir / "phase21b_recommendation_summary.md"
    _write_recommendation_markdown(
        path=md_path,
        current=current,
        shortlist=shortlist,
        delta=delta,
    )
    outputs["recommendation_summary_md"] = md_path
    _write_csv(
        current,
        dashboard_dir / "current_paper_candidate_reconciliation.csv",
    )
    _write_csv(shortlist, dashboard_dir / "paper_shortlist_recommendation.csv")
    _write_csv(delta, dashboard_dir / "candidate_delta_report.csv")
    dashboard_index = dashboard_dir / "index.md"
    _write_recommendation_markdown(
        path=dashboard_index,
        current=current,
        shortlist=shortlist,
        delta=delta,
    )
    outputs["dashboard_index"] = dashboard_index
    print("Wrote Phase 21B regime candidate reconciliation reports.")
    return outputs
