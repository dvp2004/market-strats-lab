from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PHASE20C_SECTION = "phase20c_manual_paper_session"
ALLOWED_MANUAL_DECISIONS = {
    "enter_paper_trade",
    "skip_due_warning",
    "skip_due_block",
    "skip_user_choice",
    "pending",
}
ALLOWED_EXECUTION_STATUSES = {"not_entered", "entered", "skipped", "blocked"}
REQUIRED_SOURCE_FILES = {
    "finalist_paper_targets": "finalist_paper_targets.csv",
    "finalist_paper_orders_preview": "finalist_paper_orders_preview.csv",
    "finalist_daily_tracking_tear_sheet": "finalist_daily_tracking_tear_sheet.csv",
    "finalist_daily_tracking_tear_sheet_md": "finalist_daily_tracking_tear_sheet.md",
    "finalist_manual_paper_journal_template": "finalist_manual_paper_journal_template.csv",
    "finalist_tracking_status": "finalist_tracking_status.csv",
    "paper_cycle_latest": "paper_cycle_latest.csv",
}
SESSION_TEMPLATE_COLUMNS = [
    "session_date",
    "selected_signal_date",
    "canonical_candidate_id",
    "candidate_role",
    "asset",
    "target_weight",
    "target_notional_usd",
    "preview_action",
    "paper_order_allowed",
    "candidate_caveats",
    "tear_sheet_reviewed",
    "warnings_acknowledged",
    "btc_caveat_acknowledged",
    "manual_decision",
    "manual_execution_status",
    "paper_account_value",
    "paper_fill_price",
    "paper_fill_quantity",
    "actual_notional_usd",
    "deviation_from_preview_usd",
    "deviation_from_preview_pct",
    "override_reason",
    "notes",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
]


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE20C_SECTION, {}) or {}


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


def _numeric(value: Any) -> float:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(converted) if pd.notna(converted) else np.nan


def _source_paths(
    *,
    finalist_tracking_dir: Path,
    cycle_tracker_dir: Path,
    dashboard_dir: Path,
) -> dict[str, Path]:
    return {
        "finalist_paper_targets": finalist_tracking_dir / REQUIRED_SOURCE_FILES["finalist_paper_targets"],
        "finalist_paper_orders_preview": finalist_tracking_dir
        / REQUIRED_SOURCE_FILES["finalist_paper_orders_preview"],
        "finalist_daily_tracking_tear_sheet": finalist_tracking_dir
        / REQUIRED_SOURCE_FILES["finalist_daily_tracking_tear_sheet"],
        "finalist_daily_tracking_tear_sheet_md": finalist_tracking_dir
        / REQUIRED_SOURCE_FILES["finalist_daily_tracking_tear_sheet_md"],
        "finalist_manual_paper_journal_template": finalist_tracking_dir
        / REQUIRED_SOURCE_FILES["finalist_manual_paper_journal_template"],
        "finalist_tracking_status": dashboard_dir / REQUIRED_SOURCE_FILES["finalist_tracking_status"],
        "paper_cycle_latest": cycle_tracker_dir / REQUIRED_SOURCE_FILES["paper_cycle_latest"],
    }


def _missing_source_paths(source_paths: dict[str, Path]) -> list[str]:
    return [
        str(path)
        for path in source_paths.values()
        if not path.exists() or path.is_dir()
    ]


def _selected_signal_date(
    *,
    orders: pd.DataFrame,
    cycle_latest: pd.DataFrame,
    tracking_status: pd.DataFrame,
) -> str:
    if not tracking_status.empty and "selected_signal_date" in tracking_status.columns:
        value = _text_value(tracking_status.iloc[0].get("selected_signal_date", ""))
        if value:
            return value
    if not cycle_latest.empty and "selected_signal_date" in cycle_latest.columns:
        value = _text_value(cycle_latest.iloc[0].get("selected_signal_date", ""))
        if value:
            return value
    if not orders.empty and "selected_signal_date" in orders.columns:
        value = _text_value(orders.iloc[0].get("selected_signal_date", ""))
        if value:
            return value
    return ""


def _session_date(*, cycle_latest: pd.DataFrame, tracking_status: pd.DataFrame) -> str:
    if not tracking_status.empty and "tracking_date" in tracking_status.columns:
        value = _text_value(tracking_status.iloc[0].get("tracking_date", ""))
        if value:
            return value
    if not cycle_latest.empty and "cycle_date" in cycle_latest.columns:
        value = _text_value(cycle_latest.iloc[0].get("cycle_date", ""))
        if value:
            return value
    return _generated_date()


def _warnings_present(tracking_status: pd.DataFrame, tear_sheet: pd.DataFrame) -> bool:
    if not tracking_status.empty:
        warning_symbols = _text_value(tracking_status.iloc[0].get("warning_symbols", ""))
        status = _text_value(tracking_status.iloc[0].get("data_quality_status", ""))
        if warning_symbols.lower() not in {"", "none", "nan"}:
            return True
        if status.lower() == "warning":
            return True
    if not tear_sheet.empty and {"key", "value"}.issubset(tear_sheet.columns):
        rows = tear_sheet.loc[tear_sheet["key"].astype(str) == "warning_symbols", "value"]
        if not rows.empty and _split_values(rows.iloc[0]):
            return True
    return False


def _btc_positive_weight_present(orders: pd.DataFrame, targets: pd.DataFrame) -> bool:
    for frame in [orders, targets]:
        if frame.empty or "asset" not in frame.columns:
            continue
        weight_col = "target_weight" if "target_weight" in frame.columns else ""
        if not weight_col:
            continue
        btc = frame.loc[frame["asset"].astype(str) == "BTC-USD", weight_col]
        if pd.to_numeric(btc, errors="coerce").fillna(0.0).gt(0.0).any():
            return True
        if "current_btc_weight" in frame.columns:
            current_btc_weight = pd.to_numeric(
                frame["current_btc_weight"],
                errors="coerce",
            ).fillna(0.0)
            if current_btc_weight.gt(0.0).any():
                return True
    return False


def build_manual_session_template(
    *,
    orders: pd.DataFrame,
    session_date: str,
    selected_signal_date: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for order in orders.to_dict(orient="records"):
        rows.append(
            {
                "session_date": session_date,
                "selected_signal_date": selected_signal_date,
                "canonical_candidate_id": order.get("canonical_candidate_id", ""),
                "candidate_role": order.get("candidate_role", ""),
                "asset": order.get("asset", ""),
                "target_weight": order.get("target_weight", pd.NA),
                "target_notional_usd": order.get("target_notional_usd", pd.NA),
                "preview_action": order.get("preview_action", ""),
                "paper_order_allowed": order.get("paper_order_allowed", False),
                "candidate_caveats": order.get("candidate_caveats", ""),
                "tear_sheet_reviewed": False,
                "warnings_acknowledged": False,
                "btc_caveat_acknowledged": False,
                "manual_decision": "pending",
                "manual_execution_status": "not_entered",
                "paper_account_value": "",
                "paper_fill_price": "",
                "paper_fill_quantity": "",
                "actual_notional_usd": "",
                "deviation_from_preview_usd": "",
                "deviation_from_preview_pct": "",
                "override_reason": "",
                "notes": "",
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        )
    return pd.DataFrame(rows, columns=SESSION_TEMPLATE_COLUMNS)


def build_manual_session_checklist() -> str:
    return "\n".join(
        [
            "# Phase 20C Manual Paper Session Checklist",
            "",
            "**NO LIVE TRADING**",
            "",
            "**NO REAL MONEY**",
            "",
            "**NO BROKER/API**",
            "",
            "**MANUAL PAPER ONLY**",
            "",
            "**THIS DOES NOT TEST PERFORMANCE**",
            "",
            "**THIS ONLY TESTS PROCESS DISCIPLINE**",
            "",
            "## Allowed Manual Decisions",
            "",
            "- `enter_paper_trade`",
            "- `skip_due_warning`",
            "- `skip_due_block`",
            "- `skip_user_choice`",
            "- `pending`",
            "",
            "## Allowed Execution Statuses",
            "",
            "- `not_entered`",
            "- `entered`",
            "- `skipped`",
            "- `blocked`",
            "",
            "## Checklist",
            "",
            "- Open `reports/paper_trading/finalist_tracking/finalist_daily_tracking_tear_sheet.md`.",
            "- Confirm no live trading.",
            "- Confirm no real money.",
            "- Confirm no broker/API.",
            "- Review data warnings.",
            "- Review BTC caveat if BTC target weight is greater than zero.",
            "- Review each candidate target.",
            "- Decide enter/skip for each candidate row.",
            "- If entering a paper trade, record fill price and quantity.",
            "- If skipping, record reason.",
            "- Do not override without writing an override reason.",
            "",
        ]
    )


def validate_manual_session(
    *,
    session: pd.DataFrame,
    warnings_present: bool,
    btc_positive_weight_present: bool,
    config: dict[str, Any],
    filled_session_file_present: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    require_tear = _bool_value(config.get("require_tear_sheet_review_acknowledgement", True))
    require_warning = _bool_value(config.get("require_warning_acknowledgement", True))
    require_btc = _bool_value(
        config.get("require_btc_acknowledgement_when_btc_weight_positive", True)
    )
    require_manual_decision = _bool_value(config.get("require_manual_decision", True))
    require_fill_fields = _bool_value(config.get("require_fill_fields_only_if_entered", True))

    if session.empty:
        return pd.DataFrame(
            [
                {
                    "filled_session_file_present": filled_session_file_present,
                    "row_index": pd.NA,
                    "canonical_candidate_id": "",
                    "asset": "",
                    "row_valid": False,
                    "session_complete": False,
                    "blocking_reasons": "session_file_empty_or_missing",
                    "actual_notional_usd": pd.NA,
                    "deviation_from_preview_usd": pd.NA,
                    "deviation_from_preview_pct": pd.NA,
                }
            ]
        )

    for idx, row in session.reset_index(drop=True).iterrows():
        blockers: list[str] = []
        decision = _text_value(row.get("manual_decision", "")).lower()
        status = _text_value(row.get("manual_execution_status", "")).lower()
        target_notional = _numeric(row.get("target_notional_usd", np.nan))
        fill_price = _numeric(row.get("paper_fill_price", np.nan))
        fill_qty = _numeric(row.get("paper_fill_quantity", np.nan))
        actual_notional = np.nan
        deviation_usd = np.nan
        deviation_pct = np.nan

        if require_tear and not _bool_value(row.get("tear_sheet_reviewed", False)):
            blockers.append("tear_sheet_review_missing")
        if warnings_present and require_warning and not _bool_value(
            row.get("warnings_acknowledged", False)
        ):
            blockers.append("warning_acknowledgement_missing")
        row_btc_positive = (
            _text_value(row.get("asset", "")) == "BTC-USD"
            and _numeric(row.get("target_weight", 0.0)) > 0
        )
        if (
            btc_positive_weight_present
            and row_btc_positive
            and require_btc
            and not _bool_value(row.get("btc_caveat_acknowledged", False))
        ):
            blockers.append("btc_caveat_acknowledgement_missing")
        if require_manual_decision and decision == "pending":
            blockers.append("manual_decision_pending")
        if decision and decision not in ALLOWED_MANUAL_DECISIONS:
            blockers.append("manual_decision_invalid")
        if status and status not in ALLOWED_EXECUTION_STATUSES:
            blockers.append("manual_execution_status_invalid")

        if status == "entered":
            if require_fill_fields and (not np.isfinite(fill_price) or fill_price <= 0):
                blockers.append("paper_fill_price_missing_or_non_positive")
            if require_fill_fields and (not np.isfinite(fill_qty) or fill_qty <= 0):
                blockers.append("paper_fill_quantity_missing_or_non_positive")
            if np.isfinite(fill_price) and np.isfinite(fill_qty):
                actual_notional = round(fill_price * fill_qty, 2)
                if np.isfinite(target_notional):
                    deviation_usd = round(actual_notional - target_notional, 2)
                    if abs(target_notional) > 1e-12:
                        deviation_pct = round(deviation_usd / target_notional * 100.0, 4)
        if status == "skipped":
            reason = _text_value(row.get("override_reason", ""))
            notes = _text_value(row.get("notes", ""))
            if not reason and not notes:
                blockers.append("skip_reason_or_notes_missing")
        if any(
            [
                _bool_value(row.get("live_trading_allowed", False)),
                _bool_value(row.get("real_money_allowed", False)),
                _bool_value(row.get("broker_api_integration_allowed", False)),
            ]
        ):
            blockers.append("safety_flag_true")

        rows.append(
            {
                "filled_session_file_present": filled_session_file_present,
                "row_index": idx,
                "canonical_candidate_id": row.get("canonical_candidate_id", ""),
                "asset": row.get("asset", ""),
                "row_valid": len(blockers) == 0,
                "session_complete": False,
                "blocking_reasons": ";".join(blockers),
                "actual_notional_usd": actual_notional,
                "deviation_from_preview_usd": deviation_usd,
                "deviation_from_preview_pct": deviation_pct,
            }
        )

    validation = pd.DataFrame(rows)
    validation["session_complete"] = bool(
        filled_session_file_present and validation["row_valid"].all()
    )
    return validation


def build_manual_session_status(
    *,
    session: pd.DataFrame,
    validation: pd.DataFrame,
    session_date: str,
    selected_signal_date: str,
    warnings_present: bool,
    btc_positive_weight_present: bool,
    config: dict[str, Any],
    template_written: bool,
    checklist_written: bool,
    live_trading_allowed: bool,
    real_money_allowed: bool,
    broker_api_integration_allowed: bool,
) -> pd.DataFrame:
    session_complete = bool(
        not validation.empty and validation["session_complete"].map(_bool_value).all()
    )
    blocking_reasons = []
    if not session_complete:
        blocking_reasons.append("manual_session_pending_or_invalid")
    if not validation.empty:
        for reason in validation["blocking_reasons"].dropna().astype(str):
            blocking_reasons.extend(_split_values(reason))
    if live_trading_allowed:
        blocking_reasons.append("live_trading_flag_true")
    if real_money_allowed:
        blocking_reasons.append("real_money_flag_true")
    if broker_api_integration_allowed:
        blocking_reasons.append("broker_api_flag_true")

    return pd.DataFrame(
        [
            {
                "session_date": session_date,
                "selected_signal_date": selected_signal_date,
                "session_template_written": template_written,
                "checklist_written": checklist_written,
                "candidate_count": session["canonical_candidate_id"].nunique()
                if not session.empty and "canonical_candidate_id" in session.columns
                else 0,
                "order_row_count": len(session),
                "warnings_present": warnings_present,
                "btc_positive_weight_present": btc_positive_weight_present,
                "tear_sheet_review_required": _bool_value(
                    config.get("require_tear_sheet_review_acknowledgement", True)
                ),
                "warning_ack_required": _bool_value(
                    config.get("require_warning_acknowledgement", True)
                ),
                "btc_ack_required": _bool_value(
                    config.get("require_btc_acknowledgement_when_btc_weight_positive", True)
                ),
                "manual_decision_required": _bool_value(
                    config.get("require_manual_decision", True)
                ),
                "session_complete": session_complete,
                "session_blocking_reasons": ";".join(sorted(set(blocking_reasons))),
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )


def build_dashboard_status(
    *,
    decision: str,
    status: pd.DataFrame,
    manual_entries_required: bool,
    notes: str,
) -> pd.DataFrame:
    row = status.iloc[0] if not status.empty else pd.Series(dtype=object)
    return pd.DataFrame(
        [
            {
                "phase20c_decision": decision,
                "session_date": row.get("session_date", ""),
                "selected_signal_date": row.get("selected_signal_date", ""),
                "session_complete": _bool_value(row.get("session_complete", False)),
                "candidate_count": int(row.get("candidate_count", 0) or 0),
                "order_row_count": int(row.get("order_row_count", 0) or 0),
                "warnings_present": _bool_value(row.get("warnings_present", False)),
                "btc_positive_weight_present": _bool_value(
                    row.get("btc_positive_weight_present", False)
                ),
                "manual_entries_required": manual_entries_required,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
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


def _failure_outputs(
    *,
    output_dir: Path,
    dashboard_dir: Path,
    missing_sources: list[str],
    live_trading_allowed: bool,
    real_money_allowed: bool,
    broker_api_integration_allowed: bool,
) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    decision = "manual_paper_session_failed_closed"
    gates = pd.DataFrame(
        [
            _gate_row("required_phase20_sources_present", False, ";".join(missing_sources)),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row("broker_api_integration_disabled", not broker_api_integration_allowed),
        ]
    )
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 20C",
                "phase20c_decision": decision,
                "all_gates_passed": False,
                "session_complete": False,
                "missing_sources": ";".join(missing_sources),
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
                "phase": "Phase 20C",
                "diagnostic": "Manual paper session enforcement",
                "phase20c_decision": decision,
                "all_gates_passed": False,
                "session_complete": False,
                "notes": "Failed closed because required Phase 20 source files are missing.",
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    validation = pd.DataFrame(
        [
            {
                "filled_session_file_present": False,
                "row_index": pd.NA,
                "canonical_candidate_id": "",
                "asset": "",
                "row_valid": False,
                "session_complete": False,
                "blocking_reasons": "missing_required_sources",
                "actual_notional_usd": pd.NA,
                "deviation_from_preview_usd": pd.NA,
                "deviation_from_preview_pct": pd.NA,
            }
        ]
    )
    status = pd.DataFrame(
        [
            {
                "session_date": _generated_date(),
                "selected_signal_date": "",
                "session_template_written": False,
                "checklist_written": False,
                "candidate_count": 0,
                "order_row_count": 0,
                "warnings_present": False,
                "btc_positive_weight_present": False,
                "tear_sheet_review_required": True,
                "warning_ack_required": True,
                "btc_ack_required": True,
                "manual_decision_required": True,
                "session_complete": False,
                "session_blocking_reasons": "missing_required_sources",
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    dashboard = build_dashboard_status(
        decision=decision,
        status=status,
        manual_entries_required=True,
        notes="missing required Phase 20 source files",
    )

    _write_csv(summary, output_dir / "phase20c_summary.csv")
    _write_csv(gates, output_dir / "phase20c_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase20c_conclusion.csv")
    _write_csv(
        pd.DataFrame(columns=SESSION_TEMPLATE_COLUMNS),
        output_dir / "manual_paper_session_template.csv",
    )
    _write_text(build_manual_session_checklist(), output_dir / "manual_paper_session_checklist.md")
    _write_csv(status, output_dir / "manual_paper_session_status.csv")
    _write_csv(validation, output_dir / "manual_paper_session_validation.csv")
    _write_csv(dashboard, dashboard_dir / "manual_paper_session_status.csv")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "manual_paper_session_status": status,
        "manual_paper_session_validation": validation,
        "manual_paper_session_dashboard_status": dashboard,
    }


def save_phase20c_manual_paper_session(
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
        reports_path / "paper_trading" / "manual_sessions",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        reports_path / "paper_trading" / "dashboard",
    )
    finalist_tracking_dir = _resolve_path(
        section.get("source_finalist_tracking_dir"),
        reports_path / "paper_trading" / "finalist_tracking",
    )
    cycle_tracker_dir = _resolve_path(
        section.get("source_cycle_tracker_dir"),
        reports_path / "paper_trading" / "cycle_tracker",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    source_paths = _source_paths(
        finalist_tracking_dir=finalist_tracking_dir,
        cycle_tracker_dir=cycle_tracker_dir,
        dashboard_dir=dashboard_dir,
    )
    missing_sources = _missing_source_paths(source_paths)
    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )
    if missing_sources:
        return _failure_outputs(
            output_dir=output_dir,
            dashboard_dir=dashboard_dir,
            missing_sources=missing_sources,
            live_trading_allowed=live_trading_allowed,
            real_money_allowed=real_money_allowed,
            broker_api_integration_allowed=broker_api_integration_allowed,
        )

    targets = _read_csv(source_paths["finalist_paper_targets"])
    orders = _read_csv(source_paths["finalist_paper_orders_preview"])
    tear_sheet = _read_csv(source_paths["finalist_daily_tracking_tear_sheet"])
    tracking_status = _read_csv(source_paths["finalist_tracking_status"])
    cycle_latest = _read_csv(source_paths["paper_cycle_latest"])

    session_date = _session_date(cycle_latest=cycle_latest, tracking_status=tracking_status)
    selected_signal_date = _selected_signal_date(
        orders=orders,
        cycle_latest=cycle_latest,
        tracking_status=tracking_status,
    )
    warnings_present = _warnings_present(tracking_status, tear_sheet)
    btc_positive = _btc_positive_weight_present(orders, targets)
    template = build_manual_session_template(
        orders=orders,
        session_date=session_date,
        selected_signal_date=selected_signal_date,
    )
    checklist = build_manual_session_checklist()
    template_path = output_dir / "manual_paper_session_template.csv"
    checklist_path = output_dir / "manual_paper_session_checklist.md"
    _write_csv(template, template_path)
    _write_text(checklist, checklist_path)

    filled_path = output_dir / "manual_paper_session_filled.csv"
    filled_present = filled_path.exists()
    session_for_validation = _read_csv(filled_path) if filled_present else template
    validation = validate_manual_session(
        session=session_for_validation,
        warnings_present=warnings_present,
        btc_positive_weight_present=btc_positive,
        config=section,
        filled_session_file_present=filled_present,
    )
    validation_path = output_dir / "manual_paper_session_validation.csv"
    _write_csv(validation, validation_path)
    status = build_manual_session_status(
        session=session_for_validation,
        validation=validation,
        session_date=session_date,
        selected_signal_date=selected_signal_date,
        warnings_present=warnings_present,
        btc_positive_weight_present=btc_positive,
        config=section,
        template_written=template_path.exists() and not template.empty,
        checklist_written=checklist_path.exists() and checklist_path.stat().st_size > 0,
        live_trading_allowed=live_trading_allowed,
        real_money_allowed=real_money_allowed,
        broker_api_integration_allowed=broker_api_integration_allowed,
    )
    status_path = output_dir / "manual_paper_session_status.csv"
    _write_csv(status, status_path)

    session_complete = _bool_value(status.iloc[0].get("session_complete", False))
    if session_complete:
        decision = "manual_paper_session_completed_manual_paper_only"
    else:
        decision = "manual_paper_session_template_written_pending_user_entries"

    dashboard = build_dashboard_status(
        decision=decision,
        status=status,
        manual_entries_required=True,
        notes=(
            "Manual paper entries pending."
            if not session_complete
            else "Manual paper session completed; no live trading or broker execution."
        ),
    )
    dashboard_path = dashboard_dir / "manual_paper_session_status.csv"
    _write_csv(dashboard, dashboard_path)

    safety_flags_clear = not any(
        [live_trading_allowed, real_money_allowed, broker_api_integration_allowed]
    )
    gates = pd.DataFrame(
        [
            _gate_row("required_phase20_sources_present", True),
            _gate_row(
                "manual_session_template_written",
                template_path.exists() and not template.empty,
            ),
            _gate_row(
                "checklist_written",
                checklist_path.exists() and checklist_path.stat().st_size > 0,
            ),
            _gate_row("status_report_written", status_path.exists() and not status.empty),
            _gate_row("validation_report_written", validation_path.exists() and not validation.empty),
            _gate_row("dashboard_status_written", dashboard_path.exists() and not dashboard.empty),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row("broker_api_integration_disabled", not broker_api_integration_allowed),
            _gate_row("no_safety_flags_true", safety_flags_clear),
        ]
    )
    all_gates_passed = bool(gates["passed"].all())
    failed_gates = ";".join(gates.loc[~gates["passed"], "gate_id"].astype(str).tolist())
    if not all_gates_passed:
        decision = "manual_paper_session_failed_closed"

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 20C",
                "phase20c_decision": decision,
                "all_gates_passed": all_gates_passed,
                "session_date": session_date,
                "selected_signal_date": selected_signal_date,
                "session_complete": session_complete,
                "candidate_count": int(status.iloc[0].get("candidate_count", 0)),
                "order_row_count": int(status.iloc[0].get("order_row_count", 0)),
                "warnings_present": warnings_present,
                "btc_positive_weight_present": btc_positive,
                "filled_session_file_present": filled_present,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
                "session_blocking_reasons": status.iloc[0].get(
                    "session_blocking_reasons",
                    "",
                ),
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 20C",
                "diagnostic": "Manual paper tracking session and journal enforcement",
                "phase20c_decision": decision,
                "all_gates_passed": all_gates_passed,
                "session_complete": session_complete,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": (
                    "Manual journal layer written. This tests process discipline only; "
                    "it does not place orders or test performance."
                ),
                "failure_reason": failed_gates,
            }
        ]
    )

    _write_csv(summary, output_dir / "phase20c_summary.csv")
    _write_csv(gates, output_dir / "phase20c_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase20c_conclusion.csv")
    outputs = {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "manual_paper_session_template": template,
        "manual_paper_session_status": status,
        "manual_paper_session_validation": validation,
        "manual_paper_session_dashboard_status": dashboard,
    }
    print("Wrote Phase 20C manual paper session reports.")
    return outputs
