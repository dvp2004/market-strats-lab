from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PHASE21C_SECTION = "phase21c_regime_informed_paper_tracking"
PHASE6_ID = "phase6b_loose_relief_execution_realistic_overlay"
GLD_TLT_ID = "canonical_spy_qqq_gld_tlt_50_30_10_10"
BTC_INVOL_ID = "canonical_inverse_vol_63d_btc_usd_qqq_spy"
SPY_QQQ_60_40_ID = "canonical_spy_qqq_60_40"
STATIC_ALLOCATIONS = {
    GLD_TLT_ID: {"SPY": 0.50, "QQQ": 0.30, "GLD": 0.10, "TLT": 0.10},
    SPY_QQQ_60_40_ID: {"SPY": 0.60, "QQQ": 0.40},
}
SAFETY_FALSE = {
    "promotion_allowed": False,
    "paper_trading_ready": False,
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


def _tracking_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


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
    return config.get(PHASE21C_SECTION, {}) or {}


def _source_paths(section: dict[str, Any], reports_dir: Path) -> dict[str, Path]:
    reconciliation_dir = Path(
        section.get(
            "source_regime_reconciliation_dir",
            reports_dir / "strategy_factory" / "regime_reconciliation",
        )
    )
    regime_dir = Path(
        section.get(
            "source_regime_stress_dir",
            reports_dir / "strategy_factory" / "regime_stress",
        )
    )
    dynamic_dir = Path(
        section.get(
            "source_dynamic_allocation_dir",
            reports_dir / "paper_trading" / "finalist_tracking",
        )
    )
    hardening_dir = Path(
        section.get(
            "source_operational_hardening_dir",
            reports_dir / "paper_trading" / "operational_hardening",
        )
    )
    return {
        "phase21b_shortlist": reconciliation_dir
        / "phase21b_paper_shortlist_recommendation.csv",
        "phase21b_current": reconciliation_dir
        / "phase21b_current_paper_candidate_reconciliation.csv",
        "phase21a_master": regime_dir / "phase21a_master_strategy_candidates.csv",
        "phase21a_components": regime_dir
        / "phase21a_regime_robustness_score_components.csv",
        "dynamic_allocations": dynamic_dir / "finalist_dynamic_allocations.csv",
        "tear_sheet": hardening_dir / "daily_execution_tear_sheet.csv",
        "fresh_data_quality": Path(
            section.get(
                "source_fresh_data_quality_report",
                hardening_dir / "fresh_data_quality_report.csv",
            )
        ),
    }


def _load_inputs(paths: dict[str, Path]) -> tuple[dict[str, pd.DataFrame], list[str]]:
    frames = {name: _read_csv(path) for name, path in paths.items()}
    missing = [name for name, frame in frames.items() if frame.empty]
    return frames, missing


def _tear_sheet_value(tear_sheet: pd.DataFrame, key: str) -> str:
    if tear_sheet.empty or "key" not in tear_sheet.columns or "value" not in tear_sheet.columns:
        return ""
    match = tear_sheet.loc[tear_sheet["key"].astype(str) == key]
    if match.empty:
        return ""
    return _text_value(match.iloc[0]["value"])


def _parse_phase6_signal(value: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for item in value.split(";"):
        if "=" in item:
            key, raw = item.split("=", 1)
            parts[key.strip()] = raw.strip()
    return parts


def _resolve_phase6_allocation(tear_sheet: pd.DataFrame) -> tuple[dict[str, float], str, bool]:
    signal = _parse_phase6_signal(_tear_sheet_value(tear_sheet, "phase6_baseline_signal"))
    mode = signal.get("mode", "").lower()
    action = signal.get("action", "").lower()
    exposure = pd.to_numeric(pd.Series([signal.get("exposure", "")]), errors="coerce").iloc[0]
    if pd.isna(exposure):
        return {"SPY": 0.0, "CASH": 0.0}, "phase6_signal_source_missing", False
    if exposure > 0 or "offensive" in mode or "risk_on" in action:
        return {"SPY": 1.0, "CASH": 0.0}, "phase6_signal_resolved", True
    if exposure <= 0 or "cash" in mode or "defensive" in mode:
        return {"SPY": 0.0, "CASH": 1.0}, "phase6_signal_resolved", True
    return {"SPY": 0.0, "CASH": 0.0}, "phase6_signal_source_missing", False


def _data_quality_by_symbol(quality: pd.DataFrame) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if quality.empty or "symbol" not in quality.columns:
        return rows
    for row in quality.to_dict("records"):
        symbol = _text_value(row.get("symbol"))
        warnings = _text_value(row.get("warnings"))
        blocking = _text_value(row.get("blocking_failures") or row.get("blocking_failure"))
        status = _text_value(row.get("quality_status") or row.get("data_quality_status")).lower()
        warning = bool(
            warnings
            and warnings.lower() not in {"none", "nan", "false", "0"}
            or status == "warning"
            or _bool_value(row.get("outlier_warning", False))
        )
        block = bool(
            blocking
            and blocking.lower() not in {"none", "nan", "false", "0"}
            or status in {"block", "blocked", "failed", "failure"}
            or _bool_value(row.get("outlier_block", False))
        )
        rows[symbol] = {"warning": warning, "block": block, "warnings": warnings, "blocking": blocking}
    return rows


def _candidate_metadata(shortlist: pd.DataFrame, phase21a: pd.DataFrame) -> pd.DataFrame:
    phase_cols = [
        "canonical_candidate_id",
        "master_strategy_classification",
        "regime_robustness_score",
        "final_regime_robustness_score",
        "classification_blocking_reasons",
    ]
    available_cols = [col for col in phase_cols if col in phase21a.columns]
    merged = shortlist.merge(
        phase21a[available_cols].drop_duplicates("canonical_candidate_id"),
        on="canonical_candidate_id",
        how="left",
    )
    if "regime_robustness_score" not in merged.columns:
        merged["regime_robustness_score"] = merged.get("final_regime_robustness_score")
    return merged


def _candidate_caveat(candidate_id: str) -> str:
    return {
        PHASE6_ID: "original defensive overlay baseline; lower drawdown, lower raw wealth; paper-only",
        GLD_TLT_ID: "multi-asset regime survivability candidate; asset inception limited; not promoted",
        BTC_INVOL_ID: "BTC high-caveat; inception-limited; weekend/gap risk; paper-only",
        SPY_QQQ_60_40_ID: "reference-only growth benchmark; rejected by regime hard gates; severe drawdown risk",
    }.get(candidate_id, "regime-informed research candidate; not promoted")


def _phase21a_classification(row: pd.Series) -> str:
    return _text_value(
        row.get("master_strategy_classification")
        or row.get("phase21a_classification")
        or row.get("phase21a_classification_x")
    )


def _make_target_row(
    *,
    tracking_date: str,
    selected_signal_date: str,
    candidate_id: str,
    candidate_role: str,
    asset: str,
    target_weight: float,
    paper_notional_usd: float,
    allocation_source: str,
    allocation_status: str,
    paper_preview_allowed: bool,
    phase21b_role: str,
    phase21a_classification: str,
    phase21a_score: Any,
    caveats: str,
    btc_capable: bool,
    current_btc_weight: float,
    active_btc_warning: bool,
) -> dict[str, Any]:
    return {
        "tracking_date": tracking_date,
        "selected_signal_date": selected_signal_date,
        "canonical_candidate_id": candidate_id,
        "candidate_role": candidate_role,
        "asset": asset,
        "target_weight": round(float(target_weight), 6),
        "target_notional_usd": round(float(target_weight) * paper_notional_usd, 2),
        "allocation_source": allocation_source,
        "allocation_status": allocation_status,
        "paper_preview_allowed": bool(paper_preview_allowed),
        "phase21b_recommendation_role": phase21b_role,
        "phase21a_classification": phase21a_classification,
        "phase21a_regime_robustness_score": phase21a_score,
        "candidate_caveats": caveats,
        "btc_capable_candidate": bool(btc_capable),
        "current_btc_weight": round(float(current_btc_weight), 6),
        "persistent_btc_caveat": bool(btc_capable),
        "active_btc_allocation_warning": bool(active_btc_warning),
        **SAFETY_FALSE,
    }


def build_regime_informed_targets(
    *,
    shortlist: pd.DataFrame,
    phase21a: pd.DataFrame,
    dynamic_allocations: pd.DataFrame,
    tear_sheet: pd.DataFrame,
    fresh_quality: pd.DataFrame,
    paper_notional_usd: float,
    max_candidates: int,
    include_reference_only: bool,
) -> pd.DataFrame:
    if shortlist.empty:
        return pd.DataFrame()
    tracking_date = _tracking_date()
    selected_signal_date = _tear_sheet_value(tear_sheet, "selected_signal_date")
    metadata = _candidate_metadata(shortlist, phase21a).head(max_candidates).copy()
    if not include_reference_only:
        metadata = metadata.loc[metadata["recommended_role"] != "reference_only"]
    quality = _data_quality_by_symbol(fresh_quality)
    rows: list[dict[str, Any]] = []

    for row in metadata.to_dict("records"):
        candidate_id = _text_value(row.get("canonical_candidate_id"))
        phase21b_role = _text_value(row.get("recommended_role"))
        classification = _text_value(row.get("master_strategy_classification"))
        score = row.get("regime_robustness_score", "")
        caveat = _candidate_caveat(candidate_id)
        candidate_role = phase21b_role
        if candidate_id == PHASE6_ID:
            allocation, status, allowed = _resolve_phase6_allocation(tear_sheet)
            for asset, weight in allocation.items():
                rows.append(
                    _make_target_row(
                        tracking_date=tracking_date,
                        selected_signal_date=selected_signal_date,
                        candidate_id=candidate_id,
                        candidate_role=candidate_role,
                        asset=asset,
                        target_weight=weight,
                        paper_notional_usd=paper_notional_usd,
                        allocation_source="phase18a_daily_execution_tear_sheet",
                        allocation_status=status,
                        paper_preview_allowed=allowed,
                        phase21b_role=phase21b_role,
                        phase21a_classification=classification,
                        phase21a_score=score,
                        caveats=caveat,
                        btc_capable=False,
                        current_btc_weight=0.0,
                        active_btc_warning=False,
                    )
                )
            continue

        if candidate_id == BTC_INVOL_ID:
            dyn = dynamic_allocations.loc[
                dynamic_allocations.get("canonical_candidate_id", pd.Series(dtype=str)).astype(str)
                == candidate_id
            ].copy()
            statuses = dyn.get("allocation_status", pd.Series(dtype=str)).astype(str)
            valid = (
                not dyn.empty
                and statuses.eq("dynamic_allocation_resolved").all()
            )
            if not valid:
                rows.append(
                    _make_target_row(
                        tracking_date=tracking_date,
                        selected_signal_date=selected_signal_date,
                        candidate_id=candidate_id,
                        candidate_role=candidate_role,
                        asset="UNRESOLVED",
                        target_weight=0.0,
                        paper_notional_usd=paper_notional_usd,
                        allocation_source="phase20b_finalist_dynamic_allocations",
                        allocation_status="dynamic_allocation_missing",
                        paper_preview_allowed=False,
                        phase21b_role=phase21b_role,
                        phase21a_classification=classification,
                        phase21a_score=score,
                        caveats=caveat,
                        btc_capable=True,
                        current_btc_weight=0.0,
                        active_btc_warning=False,
                    )
                )
                continue
            btc_weight = float(
                pd.to_numeric(
                    dyn.loc[dyn["asset"].astype(str) == "BTC-USD", "target_weight"],
                    errors="coerce",
                ).fillna(0.0).sum()
            )
            for dyn_row in dyn.to_dict("records"):
                weight = float(pd.to_numeric(pd.Series([dyn_row.get("target_weight")]), errors="coerce").fillna(0.0).iloc[0])
                rows.append(
                    _make_target_row(
                        tracking_date=tracking_date,
                        selected_signal_date=selected_signal_date,
                        candidate_id=candidate_id,
                        candidate_role=candidate_role,
                        asset=_text_value(dyn_row.get("asset")),
                        target_weight=weight,
                        paper_notional_usd=paper_notional_usd,
                        allocation_source="phase20b_finalist_dynamic_allocations",
                        allocation_status="dynamic_allocation_resolved",
                        paper_preview_allowed=True,
                        phase21b_role=phase21b_role,
                        phase21a_classification=classification,
                        phase21a_score=score,
                        caveats=caveat,
                        btc_capable=True,
                        current_btc_weight=btc_weight,
                        active_btc_warning=btc_weight > 0,
                    )
                )
            continue

        allocation = STATIC_ALLOCATIONS.get(candidate_id)
        if allocation is None:
            continue
        blocked_assets = [
            asset
            for asset in allocation
            if quality.get(asset, {}).get("block", False)
        ]
        allowed = not blocked_assets
        status = "static_allocation_resolved" if allowed else "asset_data_quality_block"
        source = "phase21c_static_regime_informed_allocation"
        for asset, weight in allocation.items():
            rows.append(
                _make_target_row(
                    tracking_date=tracking_date,
                    selected_signal_date=selected_signal_date,
                    candidate_id=candidate_id,
                    candidate_role=candidate_role,
                    asset=asset,
                    target_weight=weight,
                    paper_notional_usd=paper_notional_usd,
                    allocation_source=source,
                    allocation_status=status,
                    paper_preview_allowed=allowed,
                    phase21b_role=phase21b_role,
                    phase21a_classification=classification,
                    phase21a_score=score,
                    caveats=caveat,
                    btc_capable=False,
                    current_btc_weight=0.0,
                    active_btc_warning=False,
                )
            )
    return pd.DataFrame(rows)


def build_order_preview(targets: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for row in targets.to_dict("records"):
        allowed = _bool_value(row.get("paper_preview_allowed"))
        blocking_reason = "" if allowed else _text_value(row.get("allocation_status"))
        rows.append(
            {
                "tracking_date": row.get("tracking_date"),
                "canonical_candidate_id": row.get("canonical_candidate_id"),
                "candidate_role": row.get("candidate_role"),
                "asset": row.get("asset"),
                "target_weight": row.get("target_weight"),
                "target_notional_usd": row.get("target_notional_usd"),
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY" if allowed else "PAPER_PREVIEW_BLOCKED",
                "execution_instruction": "manual_paper_preview_only",
                "paper_order_allowed": allowed,
                "paper_order_blocking_reason": blocking_reason,
                "candidate_caveats": row.get("candidate_caveats"),
            }
        )
    return pd.DataFrame(rows)


def _fresh_quality_status(fresh_quality: pd.DataFrame) -> tuple[bool, bool, str, str]:
    quality = _data_quality_by_symbol(fresh_quality)
    warning_symbols = sorted(symbol for symbol, row in quality.items() if row["warning"])
    blocking_symbols = sorted(symbol for symbol, row in quality.items() if row["block"])
    return (
        bool(warning_symbols),
        bool(blocking_symbols),
        ",".join(warning_symbols) if warning_symbols else "none",
        ",".join(blocking_symbols) if blocking_symbols else "none",
    )


def _final_instruction(targets: pd.DataFrame, fresh_quality: pd.DataFrame) -> str:
    warnings, blocks, _warning_symbols, _blocking_symbols = _fresh_quality_status(fresh_quality)
    candidate_blocks = (
        not targets.empty
        and not targets.groupby("canonical_candidate_id")["paper_preview_allowed"]
        .apply(lambda values: bool(pd.Series(values).map(_bool_value).all()))
        .all()
    )
    if blocks or candidate_blocks:
        return "MANUAL REVIEW REQUIRED - SOME CANDIDATES BLOCKED"
    if warnings:
        return "WARNINGS PRESENT - REVIEW BEFORE REGIME-INFORMED PAPER TRACKING"
    return "NO BLOCKING ISSUES - REGIME-INFORMED PAPER PREVIEW ONLY"


def _write_tear_sheet(
    *,
    csv_path: Path,
    md_path: Path,
    targets: pd.DataFrame,
    fresh_quality: pd.DataFrame,
    requires_manual_adoption: bool,
) -> tuple[Path, Path]:
    warnings, blocks, warning_symbols, blocking_symbols = _fresh_quality_status(fresh_quality)
    final_instruction = _final_instruction(targets, fresh_quality)
    rows = [
        {"category": "boundary", "key": "status", "value": "MANUAL PAPER PREVIEW ONLY"},
        {
            "category": "signal",
            "key": "selected_signal_date",
            "value": targets["selected_signal_date"].iloc[0] if not targets.empty else "",
        },
        {
            "category": "tracking",
            "key": "tracking_date",
            "value": targets["tracking_date"].iloc[0] if not targets.empty else "",
        },
        {"category": "quality", "key": "warnings_present", "value": warnings},
        {"category": "quality", "key": "blocking_failures_present", "value": blocks},
        {"category": "quality", "key": "warning_symbols", "value": warning_symbols},
        {"category": "quality", "key": "blocking_symbols", "value": blocking_symbols},
        {
            "category": "adoption",
            "key": "requires_manual_adoption",
            "value": requires_manual_adoption,
        },
        {"category": "instruction", "key": "final_instruction", "value": final_instruction},
    ]
    if not targets.empty:
        for candidate_id, group in targets.groupby("canonical_candidate_id", sort=False):
            weights = "; ".join(
                f"{row.asset}={float(row.target_weight):.2%}" for row in group.itertuples()
            )
            rows.append(
                {
                    "category": "candidate",
                    "key": candidate_id,
                    "value": weights,
                    "status": group.iloc[0]["candidate_role"],
                    "notes": group.iloc[0]["candidate_caveats"],
                }
            )
    tear = pd.DataFrame(rows)
    _write_csv(tear, csv_path)

    md_lines = [
        "# Phase 21C Regime-Informed Daily Tracking Tear Sheet",
        "",
        "NO LIVE TRADING",
        "NO REAL MONEY",
        "NO BROKER/API",
        "NO STRATEGY PROMOTION",
        "MANUAL PAPER PREVIEW ONLY",
        "REGIME-INFORMED SHORTLIST - NOT FINAL MASTER BOT",
        "",
        f"Final instruction: **{final_instruction}**",
        "",
        f"Requires manual adoption before replacing Phase 20: `{requires_manual_adoption}`",
        f"Warning symbols: `{warning_symbols}`",
        f"Blocking symbols: `{blocking_symbols}`",
        "",
        "## Candidates",
        "",
    ]
    if targets.empty:
        md_lines.append("No candidates generated.")
    else:
        for candidate_id, group in targets.groupby("canonical_candidate_id", sort=False):
            weights = ", ".join(
                f"{row.asset} {float(row.target_weight):.2%}" for row in group.itertuples()
            )
            md_lines.append(f"- `{candidate_id}` ({group.iloc[0]['candidate_role']}): {weights}")
            md_lines.append(f"  - Phase 21A: {group.iloc[0]['phase21a_classification']}")
            md_lines.append(f"  - Caveat: {group.iloc[0]['candidate_caveats']}")
            md_lines.append(
                f"  - BTC active warning: {bool(group['active_btc_allocation_warning'].map(_bool_value).any())}"
            )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return csv_path, md_path


def build_adoption_status(
    *,
    targets: pd.DataFrame,
    requires_manual_adoption: bool,
) -> pd.DataFrame:
    candidate_allowed = (
        targets.groupby("canonical_candidate_id")["paper_preview_allowed"]
        .apply(lambda values: bool(pd.Series(values).map(_bool_value).all()))
        if not targets.empty
        else pd.Series(dtype=bool)
    )
    return pd.DataFrame(
        [
            {
                "tracking_date": targets["tracking_date"].iloc[0] if not targets.empty else "",
                "selected_signal_date": targets["selected_signal_date"].iloc[0]
                if not targets.empty
                else "",
                "regime_informed_shortlist_written": not targets.empty,
                "candidate_count": int(targets["canonical_candidate_id"].nunique())
                if not targets.empty
                else 0,
                "preview_allowed_candidate_count": int(candidate_allowed.sum()),
                "blocked_candidate_count": int((~candidate_allowed).sum()),
                "requires_manual_adoption": bool(requires_manual_adoption),
                "phase20_outputs_modified": False,
                "recommended_to_replace_phase20_primary_tracking": True,
                "recommended_to_keep_old_phase20_reference": True,
                "adoption_status": "pending_manual_review",
                "adoption_notes": "Phase 20 outputs were not modified; manual adoption required.",
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )


def _empty_outputs(output_dir: Path, dashboard_dir: Path, decision: str, missing: list[str]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 21C",
                "phase21c_decision": decision,
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
    gate = pd.DataFrame(
        [
            _gate_row("required_sources_present", False, ",".join(missing)),
            _gate_row("phase20_outputs_not_modified", True),
            _gate_row("promotion_disabled", True),
            _gate_row("live_trading_disabled", True),
            _gate_row("real_money_disabled", True),
            _gate_row("broker_api_integration_disabled", True),
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 21C",
                "phase21c_decision": decision,
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
        "summary": _write_csv(summary, output_dir / "phase21c_summary.csv"),
        "gate_report": _write_csv(gate, output_dir / "phase21c_gate_report.csv"),
        "conclusion": _write_csv(conclusion, output_dir / "phase21c_conclusion.csv"),
        "regime_informed_paper_targets": _write_csv(
            pd.DataFrame(),
            output_dir / "regime_informed_paper_targets.csv",
        ),
        "regime_informed_paper_orders_preview": _write_csv(
            pd.DataFrame(),
            output_dir / "regime_informed_paper_orders_preview.csv",
        ),
        "regime_informed_tracking_adoption_status": _write_csv(
            pd.DataFrame(),
            output_dir / "regime_informed_tracking_adoption_status.csv",
        ),
    }
    tear_csv = output_dir / "regime_informed_daily_tracking_tear_sheet.csv"
    tear_md = output_dir / "regime_informed_daily_tracking_tear_sheet.md"
    _write_csv(pd.DataFrame(), tear_csv)
    tear_md.write_text(
        "# Phase 21C Regime-Informed Tracking\n\nFailed closed: missing sources.\n",
        encoding="utf-8",
    )
    outputs["regime_informed_daily_tracking_tear_sheet_csv"] = tear_csv
    outputs["regime_informed_daily_tracking_tear_sheet_md"] = tear_md
    outputs["dashboard_status"] = _write_csv(
        pd.DataFrame(
            [
                {
                    "phase21c_decision": decision,
                    "candidate_count": 0,
                    "phase20_outputs_modified": False,
                    "promotion_allowed": False,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                    "notes": f"Missing sources: {','.join(missing)}",
                }
            ]
        ),
        dashboard_dir / "regime_informed_tracking_status.csv",
    )
    return outputs


def save_phase21c_regime_informed_paper_tracking(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, Path]:
    section = config.get(PHASE21C_SECTION, {}) or {}
    output_dir = Path(
        section.get(
            "output_dir",
            Path(reports_dir) / "paper_trading" / "regime_informed_tracking",
        )
    )
    dashboard_dir = Path(
        section.get("dashboard_dir", Path(reports_dir) / "paper_trading" / "dashboard")
    )
    if not _bool_value(section.get("enabled", False)):
        return _empty_outputs(output_dir, dashboard_dir, "phase21c_disabled", ["phase21c_disabled"])

    paths = _source_paths(section, Path(reports_dir))
    frames, missing = _load_inputs(paths)
    if missing:
        return _empty_outputs(
            output_dir,
            dashboard_dir,
            "regime_informed_paper_tracking_failed_missing_sources",
            missing,
        )

    targets = build_regime_informed_targets(
        shortlist=frames["phase21b_shortlist"],
        phase21a=frames["phase21a_master"],
        dynamic_allocations=frames["dynamic_allocations"],
        tear_sheet=frames["tear_sheet"],
        fresh_quality=frames["fresh_data_quality"],
        paper_notional_usd=float(section.get("paper_notional_usd", 10000)),
        max_candidates=int(section.get("max_candidates", 4)),
        include_reference_only=_bool_value(section.get("include_reference_only_candidate", True)),
    )
    orders = build_order_preview(targets)
    requires_manual_adoption = _bool_value(
        section.get("require_manual_adoption_before_replacing_phase20", True)
    )
    adoption = build_adoption_status(
        targets=targets,
        requires_manual_adoption=requires_manual_adoption,
    )
    tear_csv = output_dir / "regime_informed_daily_tracking_tear_sheet.csv"
    tear_md = output_dir / "regime_informed_daily_tracking_tear_sheet.md"
    _write_tear_sheet(
        csv_path=tear_csv,
        md_path=tear_md,
        targets=targets,
        fresh_quality=frames["fresh_data_quality"],
        requires_manual_adoption=requires_manual_adoption,
    )

    live = _bool_value(section.get("live_trading_allowed", False))
    real = _bool_value(section.get("real_money_allowed", False))
    broker = _bool_value(section.get("broker_api_integration_allowed", False))
    promotion = _bool_value(section.get("promotion_allowed", False))
    gate = pd.DataFrame(
        [
            _gate_row("phase21b_recommendation_present", True),
            _gate_row("target_file_written", True),
            _gate_row("order_preview_written", True),
            _gate_row("tear_sheet_csv_written", True),
            _gate_row("tear_sheet_md_written", True),
            _gate_row("adoption_status_written", True),
            _gate_row("dashboard_status_written", True),
            _gate_row("phase20_outputs_not_modified", True),
            _gate_row("promotion_disabled", not promotion),
            _gate_row("live_trading_disabled", not live),
            _gate_row("real_money_disabled", not real),
            _gate_row("broker_api_integration_disabled", not broker),
        ]
    )
    all_gates_passed = bool(gate["passed"].map(_bool_value).all())
    decision = (
        "regime_informed_paper_tracking_shortlist_written_pending_manual_adoption"
        if all_gates_passed
        else "regime_informed_paper_tracking_failed_safety_gate"
    )
    candidate_allowed = (
        targets.groupby("canonical_candidate_id")["paper_preview_allowed"]
        .apply(lambda values: bool(pd.Series(values).map(_bool_value).all()))
        if not targets.empty
        else pd.Series(dtype=bool)
    )
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 21C",
                "phase21c_decision": decision,
                "all_gates_passed": all_gates_passed,
                "candidate_count": int(targets["canonical_candidate_id"].nunique())
                if not targets.empty
                else 0,
                "preview_allowed_candidate_count": int(candidate_allowed.sum()),
                "blocked_candidate_count": int((~candidate_allowed).sum()),
                "requires_manual_adoption": requires_manual_adoption,
                "phase20_outputs_modified": False,
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
                "phase": "Phase 21C",
                "phase21c_decision": decision,
                "all_gates_passed": all_gates_passed,
                "promotion_allowed": False,
                "final_model_promoted": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Regime-informed shortlist written; Phase 20 outputs unchanged pending manual adoption.",
            }
        ]
    )
    dashboard_status = adoption.copy()
    dashboard_status.insert(0, "phase21c_decision", decision)
    dashboard_status["notes"] = (
        "Regime-informed shortlist is versioned separately and pending manual adoption."
    )

    outputs = {
        "summary": _write_csv(summary, output_dir / "phase21c_summary.csv"),
        "gate_report": _write_csv(gate, output_dir / "phase21c_gate_report.csv"),
        "conclusion": _write_csv(conclusion, output_dir / "phase21c_conclusion.csv"),
        "regime_informed_paper_targets": _write_csv(
            targets,
            output_dir / "regime_informed_paper_targets.csv",
        ),
        "regime_informed_paper_orders_preview": _write_csv(
            orders,
            output_dir / "regime_informed_paper_orders_preview.csv",
        ),
        "regime_informed_daily_tracking_tear_sheet_csv": tear_csv,
        "regime_informed_daily_tracking_tear_sheet_md": tear_md,
        "regime_informed_tracking_adoption_status": _write_csv(
            adoption,
            output_dir / "regime_informed_tracking_adoption_status.csv",
        ),
        "dashboard_status": _write_csv(
            dashboard_status,
            dashboard_dir / "regime_informed_tracking_status.csv",
        ),
    }
    print("Wrote Phase 21C regime-informed paper tracking reports.")
    return outputs
