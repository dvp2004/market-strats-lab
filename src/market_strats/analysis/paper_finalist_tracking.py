from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PHASE20A_SECTION = "phase20a_paper_finalist_tracking"
STATIC_60_40_CANDIDATE = "canonical_spy_qqq_60_40"
DYNAMIC_BTC_CANDIDATE = "canonical_inverse_vol_63d_btc_usd_qqq_spy"
REQUIRED_INPUTS = {
    "recommended_tracking_set": "phase19b_recommended_paper_tracking_set.csv",
    "paper_candidate_shortlist": "phase19b_paper_candidate_shortlist.csv",
    "entity_roster_recommendation": "phase19b_entity_roster_recommendation.csv",
    "daily_execution_tear_sheet": "daily_execution_tear_sheet.csv",
    "daily_execution_tear_sheet_md": "daily_execution_tear_sheet.md",
    "fresh_data_quality_report": "fresh_data_quality_report.csv",
    "paper_cycle_latest": "paper_cycle_latest.csv",
}
TARGET_COLUMNS = [
    "tracking_date",
    "selected_signal_date",
    "canonical_candidate_id",
    "candidate_role",
    "asset",
    "target_weight",
    "target_notional_usd",
    "allocation_source",
    "allocation_status",
    "paper_preview_allowed",
    "promotion_allowed",
    "paper_trading_ready",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
    "btc_capable_candidate",
    "current_btc_weight",
    "persistent_btc_caveat",
    "active_btc_allocation_warning",
    "candidate_caveats",
]
ORDER_COLUMNS = [
    "tracking_date",
    "canonical_candidate_id",
    "candidate_role",
    "asset",
    "target_weight",
    "target_notional_usd",
    "preview_action",
    "execution_instruction",
    "paper_order_allowed",
    "paper_order_blocking_reason",
    "btc_capable_candidate",
    "current_btc_weight",
    "persistent_btc_caveat",
    "active_btc_allocation_warning",
    "candidate_caveats",
]
JOURNAL_COLUMNS = [
    "journal_date",
    "selected_signal_date",
    "canonical_candidate_id",
    "candidate_role",
    "asset",
    "target_weight",
    "target_notional_usd",
    "manual_execution_status",
    "paper_account_value",
    "paper_fill_price",
    "paper_fill_quantity",
    "deviation_from_preview",
    "notes",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
]


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE20A_SECTION, {}) or {}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict | list | tuple | set):
        return False
    return bool(pd.isna(value))


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if _is_missing(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _text_value(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(value).strip()


def _resolve_path(path_value: str | Path | None, fallback: Path) -> Path:
    if path_value is None or str(path_value).strip() == "":
        return fallback
    return Path(path_value)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    return pd.read_csv(path)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generated_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _split_values(value: Any) -> list[str]:
    text = _text_value(value)
    if text == "" or text.lower() in {"none", "nan", "not_available"}:
        return []
    values: list[str] = []
    for chunk in text.replace(";", ",").split(","):
        stripped = chunk.strip()
        if stripped and stripped.lower() not in {"none", "nan", "not_available"}:
            values.append(stripped)
    return values


def _join_values(values: list[str]) -> str:
    unique = sorted({value for value in values if value})
    return ", ".join(unique) if unique else "none"


def _tear_sheet_values(tear_sheet: pd.DataFrame) -> dict[str, str]:
    if tear_sheet.empty or not {"key", "value"}.issubset(tear_sheet.columns):
        return {}
    return {
        _text_value(row["key"]): _text_value(row["value"])
        for row in tear_sheet.to_dict(orient="records")
    }


def _symbols_with_text(data_quality: pd.DataFrame, column: str) -> list[str]:
    if data_quality.empty or column not in data_quality.columns or "symbol" not in data_quality:
        return []
    rows = data_quality[data_quality[column].map(_text_value).str.len() > 0]
    return rows["symbol"].astype(str).tolist()


def _candidate_caveats(row: pd.Series) -> str:
    caveats = [
        _text_value(row.get("major_caveats", "")),
        _text_value(row.get("selection_limitations", "")),
    ]
    canonical_id = _text_value(row.get("canonical_candidate_id", ""))
    active_assets = _text_value(row.get("active_assets", ""))
    uses_btc = _bool_value(row.get("uses_btc", False)) or "BTC-USD" in active_assets
    if uses_btc or "btc" in canonical_id.lower():
        caveats.append("BTC weekend/gap risk; BTC allocation caveat")
    return "; ".join(dict.fromkeys(item for item in caveats if item))


def _selected_candidates(
    recommended_tracking_set: pd.DataFrame,
    include_candidates: list[str],
) -> pd.DataFrame:
    if recommended_tracking_set.empty:
        return pd.DataFrame()
    out = recommended_tracking_set.copy()
    if include_candidates:
        out = out[
            out["canonical_candidate_id"].astype(str).isin([str(item) for item in include_candidates])
        ]
    return out.reset_index(drop=True)


def _dynamic_allocation_source(
    *,
    dynamic_allocations: pd.DataFrame,
    candidate: pd.Series,
) -> pd.DataFrame:
    if dynamic_allocations.empty:
        return pd.DataFrame()
    frame = dynamic_allocations.copy()
    id_columns = [
        column
        for column in [
            "canonical_candidate_id",
            "candidate_id",
            "representative_candidate_id",
            "strategy_id",
        ]
        if column in frame.columns
    ]
    if "weight" not in frame.columns:
        if "final_weight" in frame.columns:
            frame["weight"] = frame["final_weight"]
        elif "target_weight" in frame.columns:
            frame["weight"] = frame["target_weight"]
    if not id_columns or not {"asset", "weight"}.issubset(frame.columns):
        return pd.DataFrame()
    candidate_ids = {
        _text_value(candidate.get("canonical_candidate_id", "")),
        _text_value(candidate.get("representative_candidate_id", "")),
    }
    mask = pd.Series(False, index=frame.index)
    for column in id_columns:
        mask = mask | frame[column].astype(str).isin(candidate_ids)
    frame = frame[mask].copy()
    if frame.empty:
        return frame
    if "allocation_status" in frame.columns:
        frame = frame[
            frame["allocation_status"].astype(str).eq("dynamic_allocation_resolved")
        ].copy()
    if "paper_preview_allowed" in frame.columns:
        frame = frame[frame["paper_preview_allowed"].map(_bool_value)].copy()
    if frame.empty:
        return frame
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame[frame["date"] == frame["date"].max()].copy()
    elif "allocation_date" in frame.columns:
        frame["allocation_date"] = pd.to_datetime(frame["allocation_date"], errors="coerce")
        frame = frame[frame["allocation_date"] == frame["allocation_date"].max()].copy()
    frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce")
    return frame.dropna(subset=["weight"])


def _is_btc_capable(row: pd.Series) -> bool:
    canonical_id = _text_value(row.get("canonical_candidate_id", ""))
    active_assets = _text_value(row.get("active_assets", ""))
    return _bool_value(row.get("uses_btc", False)) or "BTC-USD" in active_assets or "btc" in canonical_id.lower()


def _candidate_btc_weight(frame: pd.DataFrame) -> Any:
    if frame.empty or "asset" not in frame.columns or "weight" not in frame.columns:
        return pd.NA
    btc = frame.loc[frame["asset"].astype(str) == "BTC-USD", "weight"]
    if btc.empty:
        return 0.0
    value = pd.to_numeric(btc, errors="coerce").dropna()
    if value.empty:
        return pd.NA
    return float(value.iloc[0])


def build_finalist_paper_targets(
    *,
    recommended_tracking_set: pd.DataFrame,
    include_candidates: list[str],
    dynamic_allocations: pd.DataFrame | None,
    selected_signal_date: str,
    tracking_date: str,
    paper_notional_usd: float,
    data_quality_blocked: bool,
) -> pd.DataFrame:
    candidates = _selected_candidates(recommended_tracking_set, include_candidates)
    rows: list[dict[str, Any]] = []
    dynamic_frame = dynamic_allocations if dynamic_allocations is not None else pd.DataFrame()

    for candidate in candidates.to_dict(orient="records"):
        row = pd.Series(candidate)
        canonical_id = _text_value(row.get("canonical_candidate_id", ""))
        role = _text_value(row.get("paper_candidate_role", "paper_tracking_candidate"))
        caveats = _candidate_caveats(row)
        btc_capable = _is_btc_capable(row)

        if canonical_id == STATIC_60_40_CANDIDATE:
            static_weights = [("SPY", 0.60), ("QQQ", 0.40), ("BTC-USD", 0.0)]
            for asset, weight in static_weights:
                rows.append(
                    _target_row(
                        tracking_date=tracking_date,
                        selected_signal_date=selected_signal_date,
                        canonical_candidate_id=canonical_id,
                        candidate_role=role,
                        asset=asset,
                        target_weight=weight,
                        target_notional_usd=round(paper_notional_usd * weight, 2),
                        allocation_source="phase20a_static_rule_canonical_spy_qqq_60_40",
                        allocation_status="static_allocation_resolved",
                        paper_preview_allowed=not data_quality_blocked,
                        btc_capable_candidate=False,
                        current_btc_weight=0.0,
                        candidate_caveats=caveats,
                    )
                )
            continue

        dynamic_source = _dynamic_allocation_source(
            dynamic_allocations=dynamic_frame,
            candidate=row,
        )
        if not dynamic_source.empty:
            current_btc_weight = _candidate_btc_weight(dynamic_source)
            for alloc in dynamic_source.to_dict(orient="records"):
                weight = float(alloc["weight"])
                rows.append(
                    _target_row(
                        tracking_date=tracking_date,
                        selected_signal_date=selected_signal_date,
                        canonical_candidate_id=canonical_id,
                        candidate_role=role,
                        asset=_text_value(alloc.get("asset", "")),
                        target_weight=weight,
                        target_notional_usd=round(paper_notional_usd * weight, 2),
                        allocation_source=_text_value(
                            alloc.get(
                                "allocation_source",
                                "phase20b_inverse_vol_dynamic_allocation",
                            )
                        )
                        or "phase20b_inverse_vol_dynamic_allocation",
                        allocation_status=_text_value(
                            alloc.get("allocation_status", "dynamic_allocation_resolved")
                        )
                        or "dynamic_allocation_resolved",
                        paper_preview_allowed=not data_quality_blocked,
                        btc_capable_candidate=btc_capable,
                        current_btc_weight=current_btc_weight,
                        candidate_caveats=caveats,
                    )
                )
            continue

        active_assets = _split_values(row.get("active_assets", ""))
        if not active_assets:
            active_assets = ["BTC-USD", "QQQ", "SPY"] if "btc" in canonical_id.lower() else [""]
        for asset in active_assets:
            rows.append(
                _target_row(
                    tracking_date=tracking_date,
                    selected_signal_date=selected_signal_date,
                    canonical_candidate_id=canonical_id,
                    candidate_role=role,
                    asset=asset,
                    target_weight=pd.NA,
                    target_notional_usd=pd.NA,
                    allocation_source="none_available",
                    allocation_status="dynamic_weight_source_missing",
                    paper_preview_allowed=False,
                    btc_capable_candidate=btc_capable,
                    current_btc_weight=pd.NA,
                    candidate_caveats=(
                        f"{caveats}; dynamic allocation source missing"
                        if caveats
                        else "dynamic allocation source missing"
                    ),
                )
            )

    return pd.DataFrame(rows, columns=TARGET_COLUMNS)


def _target_row(
    *,
    tracking_date: str,
    selected_signal_date: str,
    canonical_candidate_id: str,
    candidate_role: str,
    asset: str,
    target_weight: Any,
    target_notional_usd: Any,
    allocation_source: str,
    allocation_status: str,
    paper_preview_allowed: bool,
    candidate_caveats: str,
    btc_capable_candidate: bool,
    current_btc_weight: Any,
) -> dict[str, Any]:
    numeric_btc_weight = pd.to_numeric(pd.Series([current_btc_weight]), errors="coerce").iloc[0]
    active_btc_warning = bool(pd.notna(numeric_btc_weight) and numeric_btc_weight > 0)
    return {
        "tracking_date": tracking_date,
        "selected_signal_date": selected_signal_date,
        "canonical_candidate_id": canonical_candidate_id,
        "candidate_role": candidate_role,
        "asset": asset,
        "target_weight": target_weight,
        "target_notional_usd": target_notional_usd,
        "allocation_source": allocation_source,
        "allocation_status": allocation_status,
        "paper_preview_allowed": bool(paper_preview_allowed),
        "promotion_allowed": False,
        "paper_trading_ready": False,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
        "btc_capable_candidate": bool(btc_capable_candidate),
        "current_btc_weight": current_btc_weight,
        "persistent_btc_caveat": bool(btc_capable_candidate),
        "active_btc_allocation_warning": active_btc_warning,
        "candidate_caveats": candidate_caveats,
    }


def build_finalist_paper_orders_preview(
    *,
    targets: pd.DataFrame,
    data_quality_blocked: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target in targets.to_dict(orient="records"):
        blocking_reasons: list[str] = []
        allocation_status = _text_value(target.get("allocation_status", ""))
        if data_quality_blocked:
            blocking_reasons.append("fresh_data_quality_blocking_failure")
        if allocation_status == "dynamic_weight_source_missing":
            blocking_reasons.append("dynamic_weight_source_missing")
        if _bool_value(target.get("live_trading_allowed", False)):
            blocking_reasons.append("live_trading_flag_true")
        if _bool_value(target.get("real_money_allowed", False)):
            blocking_reasons.append("real_money_flag_true")
        if _bool_value(target.get("broker_api_integration_allowed", False)):
            blocking_reasons.append("broker_api_flag_true")

        allowed = bool(not blocking_reasons and _bool_value(target.get("paper_preview_allowed", False)))
        rows.append(
            {
                "tracking_date": target.get("tracking_date", ""),
                "canonical_candidate_id": target.get("canonical_candidate_id", ""),
                "candidate_role": target.get("candidate_role", ""),
                "asset": target.get("asset", ""),
                "target_weight": target.get("target_weight", pd.NA),
                "target_notional_usd": target.get("target_notional_usd", pd.NA),
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY"
                if allowed
                else "BLOCKED_NO_PAPER_ORDER_PREVIEW",
                "execution_instruction": "manual_paper_preview_only",
                "paper_order_allowed": allowed,
                "paper_order_blocking_reason": ";".join(blocking_reasons),
                "btc_capable_candidate": target.get("btc_capable_candidate", False),
                "current_btc_weight": target.get("current_btc_weight", pd.NA),
                "persistent_btc_caveat": target.get("persistent_btc_caveat", False),
                "active_btc_allocation_warning": target.get(
                    "active_btc_allocation_warning",
                    False,
                ),
                "candidate_caveats": target.get("candidate_caveats", ""),
            }
        )
    return pd.DataFrame(rows, columns=ORDER_COLUMNS)


def build_finalist_manual_journal_template(
    *,
    targets: pd.DataFrame,
    selected_signal_date: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target in targets.to_dict(orient="records"):
        rows.append(
            {
                "journal_date": target.get("tracking_date", ""),
                "selected_signal_date": selected_signal_date,
                "canonical_candidate_id": target.get("canonical_candidate_id", ""),
                "candidate_role": target.get("candidate_role", ""),
                "asset": target.get("asset", ""),
                "target_weight": target.get("target_weight", pd.NA),
                "target_notional_usd": target.get("target_notional_usd", pd.NA),
                "manual_execution_status": "not_entered",
                "paper_account_value": "",
                "paper_fill_price": "",
                "paper_fill_quantity": "",
                "deviation_from_preview": "",
                "notes": "",
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        )
    return pd.DataFrame(rows, columns=JOURNAL_COLUMNS)


def _format_allocations(targets: pd.DataFrame) -> str:
    if targets.empty:
        return "none"
    parts: list[str] = []
    for candidate_id, group in targets.groupby("canonical_candidate_id", sort=False):
        asset_parts: list[str] = []
        for row in group.to_dict(orient="records"):
            weight = row.get("target_weight", pd.NA)
            if _is_missing(weight):
                asset_parts.append(f"{row.get('asset', '')}=unresolved")
            else:
                asset_parts.append(f"{row.get('asset', '')}={float(weight):.4f}")
        parts.append(f"{candidate_id}: " + ", ".join(asset_parts))
    return " | ".join(parts)


def _format_preview_orders(orders: pd.DataFrame) -> str:
    if orders.empty:
        return "none"
    nonzero = orders.copy()
    nonzero["target_weight_num"] = pd.to_numeric(nonzero["target_weight"], errors="coerce")
    nonzero = nonzero[nonzero["target_weight_num"].abs() > 1e-10]
    if nonzero.empty:
        return "none"
    return " | ".join(
        f"{row['canonical_candidate_id']}:{row['asset']}="
        f"{float(row['target_weight_num']):.4f}"
        f" allowed={_bool_value(row['paper_order_allowed'])}"
        for row in nonzero.to_dict(orient="records")
    )


def _quality_status(warning_symbols: list[str], blocking_symbols: list[str]) -> str:
    if blocking_symbols:
        return "blocked"
    if warning_symbols:
        return "warning"
    return "passed"


def _final_instruction(warning_symbols: list[str], blocking_symbols: list[str]) -> str:
    if blocking_symbols:
        return "MANUAL REVIEW REQUIRED — HOLD CURRENT STATE"
    if warning_symbols:
        return "WARNINGS PRESENT — REVIEW BEFORE PAPER TRACKING"
    return "NO BLOCKING ISSUES — MANUAL PAPER TRACKING PREVIEW ONLY"


def build_finalist_daily_tracking_tear_sheet(
    *,
    targets: pd.DataFrame,
    orders: pd.DataFrame,
    tear_values: dict[str, str],
    cycle_latest: pd.DataFrame,
    warning_symbols: list[str],
    blocking_symbols: list[str],
) -> tuple[pd.DataFrame, str]:
    cycle_row = cycle_latest.iloc[0] if not cycle_latest.empty else pd.Series(dtype=object)
    selected_signal_date = tear_values.get(
        "selected_signal_date",
        _text_value(cycle_row.get("selected_signal_date", "")),
    )
    cycle_date = _text_value(cycle_row.get("cycle_date", _generated_date()))
    final_instruction = _final_instruction(warning_symbols, blocking_symbols)
    data_quality_status = _quality_status(warning_symbols, blocking_symbols)
    candidates = sorted(targets["canonical_candidate_id"].astype(str).unique().tolist()) if not targets.empty else []
    blocked_candidates = sorted(
        orders.loc[~orders["paper_order_allowed"].map(_bool_value), "canonical_candidate_id"]
        .astype(str)
        .unique()
        .tolist()
    )
    btc_caveats = "; ".join(
        sorted(
            {
                _text_value(row.get("candidate_caveats", ""))
                for row in targets.to_dict(orient="records")
                if "BTC-USD" == _text_value(row.get("asset", ""))
                or "btc" in _text_value(row.get("canonical_candidate_id", "")).lower()
            }
        )
    )

    rows = [
        _tear_row("execution_boundary", "execution_status", "MANUAL PAPER TRACKING ONLY"),
        _tear_row("execution_boundary", "no_live_trading", "True"),
        _tear_row("execution_boundary", "no_real_money", "True"),
        _tear_row("execution_boundary", "no_broker_api", "True"),
        _tear_row("execution_boundary", "no_strategy_promotion", "True"),
        _tear_row("signal", "selected_signal_date", selected_signal_date),
        _tear_row("signal", "cycle_date", cycle_date),
        _tear_row("fresh_data_quality", "data_quality_status", data_quality_status),
        _tear_row("fresh_data_quality", "warning_symbols", _join_values(warning_symbols)),
        _tear_row("fresh_data_quality", "blocking_symbols", _join_values(blocking_symbols)),
        _tear_row(
            "phase18",
            "phase18_final_manual_action",
            tear_values.get("final_recommended_manual_action", ""),
        ),
        _tear_row("finalists", "selected_finalists", _join_values(candidates)),
        _tear_row("finalists", "target_allocations", _format_allocations(targets)),
        _tear_row("finalists", "preview_orders", _format_preview_orders(orders)),
        _tear_row("finalists", "blocked_candidates", _join_values(blocked_candidates)),
        _tear_row("finalists", "candidate_caveats", _join_values(_split_values(";".join(targets.get("candidate_caveats", pd.Series(dtype=str)).astype(str).tolist())))),
        _tear_row("finalists", "btc_specific_caveats", btc_caveats or "none"),
        _tear_row("final_action", "final_instruction", final_instruction),
    ]
    tear_sheet = pd.DataFrame(rows)

    candidate_lines = []
    for candidate_id, group in targets.groupby("canonical_candidate_id", sort=False):
        role = _text_value(group.iloc[0].get("candidate_role", ""))
        allowed = bool(
            orders.loc[
                orders["canonical_candidate_id"].astype(str) == str(candidate_id),
                "paper_order_allowed",
            ].map(_bool_value).all()
        )
        candidate_lines.append(f"- `{candidate_id}` ({role}): preview_allowed={allowed}")
        for row in group.to_dict(orient="records"):
            weight = row.get("target_weight", pd.NA)
            weight_text = "unresolved" if _is_missing(weight) else f"{float(weight):.4f}"
            candidate_lines.append(
                f"  - {row.get('asset', '')}: target_weight={weight_text}, "
                f"status={row.get('allocation_status', '')}"
            )

    markdown = "\n".join(
        [
            "# Phase 20A Finalist Daily Tracking Tear Sheet",
            "",
            "**NO LIVE TRADING**",
            "",
            "**NO REAL MONEY**",
            "",
            "**NO BROKER/API**",
            "",
            "**MANUAL PAPER TRACKING ONLY**",
            "",
            "**NO STRATEGY PROMOTION**",
            "",
            "## Final Instruction",
            "",
            f"**{final_instruction}**",
            "",
            "## Cycle Context",
            "",
            f"- Selected signal date: {selected_signal_date}",
            f"- Cycle date: {cycle_date}",
            f"- Data quality status: {data_quality_status}",
            f"- Warning symbols: {_join_values(warning_symbols)}",
            f"- Blocking symbols: {_join_values(blocking_symbols)}",
            f"- Phase 18 final manual action: {tear_values.get('final_recommended_manual_action', '')}",
            "",
            "## Selected Finalists",
            "",
            *candidate_lines,
            "",
            "## Preview Orders",
            "",
            f"- Nonzero preview orders: {_format_preview_orders(orders)}",
            f"- Blocked candidates: {_join_values(blocked_candidates)}",
            "",
            "## Candidate Caveats",
            "",
            f"- BTC caveats: {btc_caveats or 'none'}",
            "- All candidates remain paper-tracking candidates only.",
            "- This file does not place orders or provide broker instructions.",
            "",
        ]
    )
    return tear_sheet, markdown


def _tear_row(category: str, key: str, value: Any, status: str = "", notes: str = "") -> dict[str, Any]:
    return {
        "category": category,
        "key": key,
        "value": value,
        "status": status,
        "notes": notes,
    }


def build_dashboard_status(
    *,
    decision: str,
    tracking_date: str,
    selected_signal_date: str,
    targets: pd.DataFrame,
    orders: pd.DataFrame,
    warning_symbols: list[str],
    blocking_symbols: list[str],
    live_trading_allowed: bool,
    real_money_allowed: bool,
    broker_api_integration_allowed: bool,
    notes: str,
) -> pd.DataFrame:
    candidates = sorted(targets["canonical_candidate_id"].astype(str).unique().tolist()) if not targets.empty else []
    allowed_candidates = sorted(
        orders.groupby("canonical_candidate_id")["paper_order_allowed"]
        .apply(lambda values: bool(values.map(_bool_value).all()))
        .loc[lambda values: values]
        .index.astype(str)
        .tolist()
    ) if not orders.empty else []
    blocked_candidate_count = max(0, len(candidates) - len(allowed_candidates))
    safety_flags_clear = not any(
        [live_trading_allowed, real_money_allowed, broker_api_integration_allowed]
    )
    paper_tracking_ready = bool(
        candidates
        and len(allowed_candidates) == len(candidates)
        and not blocking_symbols
        and safety_flags_clear
    )
    return pd.DataFrame(
        [
            {
                "phase20a_decision": decision,
                "tracking_date": tracking_date,
                "selected_signal_date": selected_signal_date,
                "candidates_tracked": _join_values(candidates),
                "candidate_count": len(candidates),
                "paper_preview_allowed_count": len(allowed_candidates),
                "blocked_candidate_count": blocked_candidate_count,
                "data_quality_status": _quality_status(warning_symbols, blocking_symbols),
                "warning_symbols": _join_values(warning_symbols),
                "blocking_symbols": _join_values(blocking_symbols),
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "paper_tracking_ready": paper_tracking_ready,
                "promotion_allowed": False,
                "notes": notes,
            }
        ]
    )


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def save_phase20a_paper_finalist_tracking(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config)
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    output_dir = _resolve_path(
        section.get("output_dir"),
        reports_path / "paper_trading" / "finalist_tracking",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        reports_path / "paper_trading" / "dashboard",
    )
    finalist_dir = _resolve_path(
        section.get("source_finalist_validation_dir"),
        reports_path / "strategy_factory" / "finalist_validation",
    )
    hardening_dir = _resolve_path(
        section.get("source_operational_hardening_dir"),
        reports_path / "paper_trading" / "operational_hardening",
    )
    cycle_dir = _resolve_path(
        section.get("source_cycle_tracker_dir"),
        reports_path / "paper_trading" / "cycle_tracker",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    source_paths = {
        "recommended_tracking_set": finalist_dir / REQUIRED_INPUTS["recommended_tracking_set"],
        "paper_candidate_shortlist": finalist_dir / REQUIRED_INPUTS["paper_candidate_shortlist"],
        "entity_roster_recommendation": finalist_dir / REQUIRED_INPUTS["entity_roster_recommendation"],
        "daily_execution_tear_sheet": hardening_dir / REQUIRED_INPUTS["daily_execution_tear_sheet"],
        "daily_execution_tear_sheet_md": hardening_dir / REQUIRED_INPUTS["daily_execution_tear_sheet_md"],
        "fresh_data_quality_report": hardening_dir / REQUIRED_INPUTS["fresh_data_quality_report"],
        "paper_cycle_latest": cycle_dir / REQUIRED_INPUTS["paper_cycle_latest"],
    }
    missing_sources = [
        str(path) for key, path in source_paths.items() if key.endswith("_md") and not path.exists()
    ]
    missing_sources.extend(
        str(path)
        for key, path in source_paths.items()
        if not key.endswith("_md") and (not path.exists() or path.is_dir())
    )

    recommended = _read_csv(source_paths["recommended_tracking_set"])
    tear_sheet = _read_csv(source_paths["daily_execution_tear_sheet"])
    data_quality = _read_csv(source_paths["fresh_data_quality_report"])
    cycle_latest = _read_csv(source_paths["paper_cycle_latest"])
    dynamic_allocations = _read_csv(
        _resolve_path(
            section.get("source_dynamic_allocations_file"),
            output_dir / "finalist_dynamic_allocations.csv",
        )
    )

    tear_values = _tear_sheet_values(tear_sheet)
    selected_signal_date = tear_values.get("selected_signal_date", "")
    if selected_signal_date == "" and not cycle_latest.empty:
        selected_signal_date = _text_value(cycle_latest.iloc[0].get("selected_signal_date", ""))
    tracking_date = (
        _text_value(cycle_latest.iloc[0].get("cycle_date", ""))
        if not cycle_latest.empty
        else _generated_date()
    )
    warning_symbols = _symbols_with_text(data_quality, "warnings")
    if not warning_symbols:
        warning_symbols = _split_values(tear_values.get("symbols_with_warnings", ""))
    blocking_symbols = _symbols_with_text(data_quality, "blocking_failures")
    if not blocking_symbols:
        blocking_symbols = _split_values(tear_values.get("symbols_with_blocking_failures", ""))
    data_quality_blocked = bool(blocking_symbols)

    include_candidates = [str(item) for item in section.get("include_candidates", [])]
    paper_notional_usd = float(section.get("paper_notional_usd", 10000))
    targets = build_finalist_paper_targets(
        recommended_tracking_set=recommended,
        include_candidates=include_candidates,
        dynamic_allocations=dynamic_allocations,
        selected_signal_date=selected_signal_date,
        tracking_date=tracking_date,
        paper_notional_usd=paper_notional_usd,
        data_quality_blocked=data_quality_blocked,
    )
    orders = build_finalist_paper_orders_preview(
        targets=targets,
        data_quality_blocked=data_quality_blocked,
    )
    tear_sheet_out, tear_sheet_markdown = build_finalist_daily_tracking_tear_sheet(
        targets=targets,
        orders=orders,
        tear_values=tear_values,
        cycle_latest=cycle_latest,
        warning_symbols=warning_symbols,
        blocking_symbols=blocking_symbols,
    )
    journal_template = build_finalist_manual_journal_template(
        targets=targets,
        selected_signal_date=selected_signal_date,
    )

    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )
    safety_flags_clear = not any(
        [live_trading_allowed, real_money_allowed, broker_api_integration_allowed]
    )

    target_path = output_dir / "finalist_paper_targets.csv"
    orders_path = output_dir / "finalist_paper_orders_preview.csv"
    tear_path = output_dir / "finalist_daily_tracking_tear_sheet.csv"
    tear_md_path = output_dir / "finalist_daily_tracking_tear_sheet.md"
    journal_path = output_dir / "finalist_manual_paper_journal_template.csv"
    dashboard_path = dashboard_dir / "finalist_tracking_status.csv"

    _write_csv(targets, target_path)
    _write_csv(orders, orders_path)
    _write_csv(tear_sheet_out, tear_path)
    _write_text(tear_sheet_markdown, tear_md_path)
    _write_csv(journal_template, journal_path)

    gates = pd.DataFrame(
        [
            _gate_row("phase19b_recommended_tracking_set_exists", source_paths["recommended_tracking_set"].exists()),
            _gate_row("phase19b_paper_candidate_shortlist_exists", source_paths["paper_candidate_shortlist"].exists()),
            _gate_row("phase19b_entity_roster_recommendation_exists", source_paths["entity_roster_recommendation"].exists()),
            _gate_row("phase18a_tear_sheet_csv_exists", source_paths["daily_execution_tear_sheet"].exists()),
            _gate_row("phase18a_tear_sheet_md_exists", source_paths["daily_execution_tear_sheet_md"].exists()),
            _gate_row("fresh_data_quality_report_exists", source_paths["fresh_data_quality_report"].exists()),
            _gate_row("phase18b_latest_cycle_exists", source_paths["paper_cycle_latest"].exists()),
            _gate_row("finalist_target_file_written", target_path.exists() and not targets.empty),
            _gate_row("finalist_order_preview_file_written", orders_path.exists() and not orders.empty),
            _gate_row("finalist_tear_sheet_csv_written", tear_path.exists() and not tear_sheet_out.empty),
            _gate_row("finalist_tear_sheet_md_written", tear_md_path.exists() and tear_md_path.stat().st_size > 0),
            _gate_row("finalist_journal_template_written", journal_path.exists() and not journal_template.empty),
            _gate_row("dashboard_status_written", dashboard_path.parent.exists()),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row("broker_api_integration_disabled", not broker_api_integration_allowed),
            _gate_row("promotion_allowed_false", True),
            _gate_row("no_safety_flags_true", safety_flags_clear),
        ]
    )
    all_gates_passed = bool(gates["passed"].all())
    decision = (
        "paper_finalist_tracking_written_manual_preview_only"
        if all_gates_passed
        else "paper_finalist_tracking_failed_closed"
    )
    failed_gates = ";".join(gates.loc[~gates["passed"], "gate_id"].astype(str).tolist())
    blocked_candidates = (
        sorted(
            orders.loc[~orders["paper_order_allowed"].map(_bool_value), "canonical_candidate_id"]
            .astype(str)
            .unique()
            .tolist()
        )
        if not orders.empty
        else []
    )
    final_instruction = _final_instruction(warning_symbols, blocking_symbols)
    dashboard_status = build_dashboard_status(
        decision=decision,
        tracking_date=tracking_date,
        selected_signal_date=selected_signal_date,
        targets=targets,
        orders=orders,
        warning_symbols=warning_symbols,
        blocking_symbols=blocking_symbols,
        live_trading_allowed=live_trading_allowed,
        real_money_allowed=real_money_allowed,
        broker_api_integration_allowed=broker_api_integration_allowed,
        notes=(
            "manual paper tracking only; no strategy promotion; "
            f"blocked_candidates={_join_values(blocked_candidates)}"
        ),
    )
    _write_csv(dashboard_status, dashboard_path)

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 20A",
                "phase20a_decision": decision,
                "all_gates_passed": all_gates_passed,
                "tracking_date": tracking_date,
                "selected_signal_date": selected_signal_date,
                "candidate_count": int(targets["canonical_candidate_id"].nunique())
                if not targets.empty
                else 0,
                "paper_preview_allowed_count": int(
                    dashboard_status.iloc[0].get("paper_preview_allowed_count", 0)
                ),
                "blocked_candidate_count": int(
                    dashboard_status.iloc[0].get("blocked_candidate_count", 0)
                ),
                "data_quality_status": _quality_status(warning_symbols, blocking_symbols),
                "warning_symbols": _join_values(warning_symbols),
                "blocking_symbols": _join_values(blocking_symbols),
                "final_instruction": final_instruction,
                "paper_tracking_ready": _bool_value(
                    dashboard_status.iloc[0].get("paper_tracking_ready", False)
                ),
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
                "missing_sources": ";".join(missing_sources),
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 20A",
                "diagnostic": "Finalist candidate manual paper-tracking integration",
                "phase20a_decision": decision,
                "all_gates_passed": all_gates_passed,
                "paper_tracking_ready": _bool_value(
                    dashboard_status.iloc[0].get("paper_tracking_ready", False)
                ),
                "final_instruction": final_instruction,
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": (
                    "Manual paper tracking preview only. No order placement, live trading, "
                    "real money, broker/API, or strategy promotion."
                ),
                "failure_reason": failed_gates,
            }
        ]
    )

    _write_csv(summary, output_dir / "phase20a_summary.csv")
    _write_csv(gates, output_dir / "phase20a_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase20a_conclusion.csv")

    outputs = {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "finalist_paper_targets": targets,
        "finalist_paper_orders_preview": orders,
        "finalist_daily_tracking_tear_sheet": tear_sheet_out,
        "finalist_manual_paper_journal_template": journal_template,
        "finalist_tracking_status": dashboard_status,
    }
    print("Wrote Phase 20A finalist paper-tracking reports.")
    return outputs
