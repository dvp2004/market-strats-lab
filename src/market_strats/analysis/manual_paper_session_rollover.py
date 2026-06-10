from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PHASE20F_SECTION = "phase20f_manual_paper_session_rollover"
ARCHIVE_INDEX_COLUMNS = [
    "archived_at_utc",
    "source_path",
    "archive_path",
    "session_date",
    "selected_signal_date",
    "row_count",
    "session_valid",
    "ledger_row_count_after_ingestion",
    "archive_status",
    "notes",
]
ROLLOVER_STATUS_COLUMNS = [
    "run_date",
    "current_template_session_date",
    "current_template_selected_signal_date",
    "filled_session_file_present",
    "filled_session_session_date",
    "filled_session_selected_signal_date",
    "filled_session_matches_current_template",
    "filled_session_already_ingested",
    "filled_session_valid",
    "filled_session_stale",
    "rollover_action",
    "rollover_blocking_reason",
    "archive_path",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
]


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE20F_SECTION, {}) or {}


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


def _safe_date(value: str) -> str:
    text = _text_value(value)
    return text.replace("/", "-").replace("\\", "-").replace(":", "-") or "unknown"


def _first_available(frame: pd.DataFrame, column: str, fallback: str = "") -> str:
    if frame.empty or column not in frame.columns:
        return fallback
    value = _text_value(frame.iloc[0].get(column, ""))
    return value or fallback


def _ledger_contains_filled_session(*, ledger: pd.DataFrame, filled: pd.DataFrame) -> bool:
    required = {"session_date", "selected_signal_date", "canonical_candidate_id", "asset"}
    if ledger.empty or filled.empty or not required.issubset(ledger.columns):
        return False
    if not required.issubset(filled.columns):
        return False
    ledger_keys = set(
        ledger[list(required)].fillna("").astype(str).itertuples(index=False, name=None)
    )
    filled_keys = set(
        filled[list(required)].fillna("").astype(str).itertuples(index=False, name=None)
    )
    return bool(filled_keys) and filled_keys.issubset(ledger_keys)


def _filled_session_valid(ingestion_result: pd.DataFrame) -> bool:
    if ingestion_result.empty:
        return False
    return _bool_value(ingestion_result.iloc[0].get("session_valid", False))


def _archive_path_for(
    *,
    archive_dir: Path,
    session_date: str,
    selected_signal_date: str,
) -> Path:
    return archive_dir / (
        "manual_paper_session_filled_"
        f"{_safe_date(session_date)}_signal_{_safe_date(selected_signal_date)}.csv"
    )


def build_next_session_runbook() -> str:
    return "\n".join(
        [
            "# Phase 20F Next Manual Paper Session Runbook",
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
            "**THIS TRACKS PROCESS DISCIPLINE**",
            "",
            "## Daily Process",
            "",
            "1. Run the full pipeline after fresh data is available.",
            "2. Open `reports/paper_trading/finalist_tracking/finalist_daily_tracking_tear_sheet.md`.",
            "3. Open `reports/paper_trading/manual_sessions/manual_paper_session_template.csv`.",
            "4. Copy the template to `manual_paper_session_filled.csv`.",
            "5. Fill acknowledgements and manual decisions.",
            "6. If skipping, provide a reason or notes.",
            "7. If entering a paper trade, fill actual paper fill price and quantity.",
            "8. Rerun the pipeline to validate and append the ledger.",
            "9. Confirm Phase 20D ingestion status.",
            "10. Confirm Phase 20E discipline streak status.",
            "11. Do not reuse stale filled files.",
            "",
        ]
    )


def _append_archive_index(*, index_path: Path, row: dict[str, Any]) -> pd.DataFrame:
    existing = _read_csv(index_path)
    if existing.empty:
        existing = pd.DataFrame(columns=ARCHIVE_INDEX_COLUMNS)
    for column in ARCHIVE_INDEX_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    updated = pd.concat([existing[ARCHIVE_INDEX_COLUMNS], pd.DataFrame([row])])
    updated = updated.drop_duplicates(
        subset=["source_path", "archive_path", "session_date", "selected_signal_date"],
        keep="last",
    ).reset_index(drop=True)
    _write_csv(updated[ARCHIVE_INDEX_COLUMNS], index_path)
    return updated[ARCHIVE_INDEX_COLUMNS]


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def save_phase20f_manual_paper_session_rollover(
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
    source_manual_session_dir = _resolve_path(
        section.get("source_manual_session_dir"),
        reports_path / "paper_trading" / "manual_sessions",
    )
    archive_dir = _resolve_path(
        section.get("archive_dir"),
        reports_path / "paper_trading" / "manual_sessions" / "archive",
    )
    filled_filename = str(section.get("filled_session_filename", "manual_paper_session_filled.csv"))
    template_filename = str(section.get("template_filename", "manual_paper_session_template.csv"))
    archive_completed = _bool_value(section.get("archive_completed_valid_sessions", True))
    stale_policy = str(section.get("stale_filled_file_policy", "block_current_ingestion"))
    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    template_path = source_manual_session_dir / template_filename
    filled_path = source_manual_session_dir / filled_filename
    ingestion_result_path = source_manual_session_dir / "manual_paper_session_ingestion_result.csv"
    ledger_path = source_manual_session_dir / "manual_paper_session_ledger.csv"
    discipline_history_path = source_manual_session_dir / "manual_paper_discipline_history.csv"
    archive_index_path = archive_dir / "manual_paper_session_archive_index.csv"

    template = _read_csv(template_path)
    filled = _read_csv(filled_path)
    ingestion_result = _read_csv(ingestion_result_path)
    ledger = _read_csv(ledger_path)
    discipline_history = _read_csv(discipline_history_path)

    template_session_date = _first_available(template, "session_date")
    template_signal_date = _first_available(template, "selected_signal_date")
    filled_present = filled_path.exists() and filled_path.is_file()
    filled_session_date = _first_available(filled, "session_date") if filled_present else ""
    filled_signal_date = (
        _first_available(filled, "selected_signal_date") if filled_present else ""
    )
    matches_current = bool(
        filled_present
        and filled_session_date == template_session_date
        and filled_signal_date == template_signal_date
    )
    filled_valid = bool(filled_present and _filled_session_valid(ingestion_result))
    already_ingested = bool(
        filled_present and _ledger_contains_filled_session(ledger=ledger, filled=filled)
    )
    stale = bool(filled_present and not matches_current)
    archive_path = ""
    archive_written = False
    archive_status = "not_applicable"
    rollover_blocking_reason = ""

    if not filled_present:
        rollover_action = "no_filled_file_pending_user_entries"
    elif stale:
        rollover_action = "stale_file_blocked"
        rollover_blocking_reason = (
            "filled_session_does_not_match_current_template"
            if stale_policy == "block_current_ingestion"
            else "filled_session_stale"
        )
    elif filled_valid and already_ingested and archive_completed:
        archive_target = _archive_path_for(
            archive_dir=archive_dir,
            session_date=filled_session_date,
            selected_signal_date=filled_signal_date,
        )
        shutil.copy2(filled_path, archive_target)
        archive_path = str(archive_target)
        archive_written = True
        archive_status = "archived"
        rollover_action = "valid_session_archived"
    elif filled_valid and already_ingested:
        rollover_action = "valid_session_already_ingested_archive_disabled"
    elif filled_valid:
        rollover_action = "current_filled_file_available"
    else:
        rollover_action = "invalid_filled_file_manual_review_required"
        rollover_blocking_reason = "filled_session_invalid_or_not_ingested"
        archive_status = "not_archived_invalid_session"

    if archive_written:
        archive_index = _append_archive_index(
            index_path=archive_index_path,
            row={
                "archived_at_utc": _generated_at(),
                "source_path": str(filled_path),
                "archive_path": archive_path,
                "session_date": filled_session_date,
                "selected_signal_date": filled_signal_date,
                "row_count": len(filled),
                "session_valid": filled_valid,
                "ledger_row_count_after_ingestion": len(ledger),
                "archive_status": archive_status,
                "notes": "copied only; source filled file preserved",
            },
        )
    else:
        archive_index = _read_csv(archive_index_path)
        if archive_index.empty:
            archive_index = pd.DataFrame(columns=ARCHIVE_INDEX_COLUMNS)
            _write_csv(archive_index, archive_index_path)

    status = pd.DataFrame(
        [
            {
                "run_date": _generated_date(),
                "current_template_session_date": template_session_date,
                "current_template_selected_signal_date": template_signal_date,
                "filled_session_file_present": filled_present,
                "filled_session_session_date": filled_session_date,
                "filled_session_selected_signal_date": filled_signal_date,
                "filled_session_matches_current_template": matches_current,
                "filled_session_already_ingested": already_ingested,
                "filled_session_valid": filled_valid,
                "filled_session_stale": stale,
                "rollover_action": rollover_action,
                "rollover_blocking_reason": rollover_blocking_reason,
                "archive_path": archive_path,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ],
        columns=ROLLOVER_STATUS_COLUMNS,
    )
    status_path = output_dir / "manual_paper_session_rollover_status.csv"
    runbook_path = output_dir / "manual_paper_next_session_runbook.md"
    dashboard_path = dashboard_dir / "manual_paper_session_rollover_status.csv"
    _write_csv(status, status_path)
    _write_text(build_next_session_runbook(), runbook_path)

    if rollover_action == "no_filled_file_pending_user_entries":
        decision = "manual_paper_session_rollover_no_filled_file_pending_user_entries"
    elif rollover_action == "valid_session_archived":
        decision = "manual_paper_session_rollover_valid_session_archived"
    elif rollover_action == "stale_file_blocked":
        decision = "manual_paper_session_rollover_stale_file_blocked"
    elif rollover_action == "invalid_filled_file_manual_review_required":
        decision = "manual_paper_session_rollover_invalid_filled_file_manual_review_required"
    else:
        decision = "manual_paper_session_rollover_current_filled_file_available"

    dashboard = pd.DataFrame(
        [
            {
                "phase20f_decision": decision,
                "run_date": status.iloc[0]["run_date"],
                "filled_session_file_present": filled_present,
                "filled_session_matches_current_template": matches_current,
                "filled_session_stale": stale,
                "filled_session_valid": filled_valid,
                "archive_written": archive_written,
                "archive_path": archive_path,
                "rollover_action": rollover_action,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": rollover_blocking_reason or archive_status,
            }
        ]
    )
    _write_csv(dashboard, dashboard_path)

    stale_status_explicit = bool(not filled_present or rollover_action != "")
    gates = pd.DataFrame(
        [
            _gate_row("rollover_status_written", status_path.exists() and not status.empty),
            _gate_row("next_session_runbook_written", runbook_path.exists()),
            _gate_row("archive_index_written", archive_index_path.exists()),
            _gate_row("dashboard_status_written", dashboard_path.exists()),
            _gate_row("stale_filled_file_status_explicit", stale_status_explicit),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row("broker_api_integration_disabled", not broker_api_integration_allowed),
        ]
    )
    all_gates_passed = bool(gates["passed"].map(_bool_value).all())
    failed_gates = ";".join(gates.loc[~gates["passed"].map(_bool_value), "gate_id"])
    if not all_gates_passed:
        decision = "manual_paper_session_rollover_failed_closed"
        dashboard.loc[0, "phase20f_decision"] = decision
        _write_csv(dashboard, dashboard_path)

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 20F",
                "phase20f_decision": decision,
                "all_gates_passed": all_gates_passed,
                "filled_session_file_present": filled_present,
                "filled_session_matches_current_template": matches_current,
                "filled_session_already_ingested": already_ingested,
                "filled_session_valid": filled_valid,
                "filled_session_stale": stale,
                "rollover_action": rollover_action,
                "archive_written": archive_written,
                "archive_path": archive_path,
                "archive_index_rows": len(archive_index),
                "discipline_history_available": not discipline_history.empty,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 20F",
                "diagnostic": "Manual paper session rollover and stale-file guard",
                "phase20f_decision": decision,
                "all_gates_passed": all_gates_passed,
                "rollover_action": rollover_action,
                "archive_path": archive_path,
                "notes": (
                    "Filled file was copied to archive and preserved."
                    if archive_written
                    else "Rollover status written; source filled file preserved."
                ),
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
            }
        ]
    )
    _write_csv(summary, output_dir / "phase20f_summary.csv")
    _write_csv(gates, output_dir / "phase20f_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase20f_conclusion.csv")
    print("Wrote Phase 20F manual paper session rollover reports.")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "manual_paper_session_rollover_status": status,
        "manual_paper_session_archive_index": archive_index,
        "manual_paper_session_rollover_dashboard_status": dashboard,
    }
