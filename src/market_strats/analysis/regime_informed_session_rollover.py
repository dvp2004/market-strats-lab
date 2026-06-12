from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PHASE21G_SECTION = "phase21g_regime_informed_session_rollover"


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _resolve_path(value: object, default: Path) -> Path:
    return Path(value) if value else default


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE21G_SECTION, {}) or {}


def _first(frame: pd.DataFrame, column: str) -> str:
    if frame.empty or column not in frame.columns:
        return ""
    value = frame.iloc[0].get(column, "")
    return _text(value)


def _filled_matches_template(template: pd.DataFrame, filled: pd.DataFrame) -> bool:
    if template.empty or filled.empty:
        return False
    return (
        _first(template, "session_date") == _first(filled, "session_date")
        and _first(template, "selected_signal_date")
        == _first(filled, "selected_signal_date")
    )


def _filled_already_ingested(filled: pd.DataFrame, ledger: pd.DataFrame) -> bool:
    keys = ["session_date", "selected_signal_date", "canonical_candidate_id", "asset"]
    if filled.empty or ledger.empty or not set(keys).issubset(filled.columns) or not set(keys).issubset(ledger.columns):
        return False
    filled_keys = set(map(tuple, filled[keys].astype(str).to_numpy()))
    ledger_keys = set(map(tuple, ledger[keys].astype(str).to_numpy()))
    return bool(filled_keys) and filled_keys.issubset(ledger_keys)


def _session_valid(validation: pd.DataFrame) -> bool:
    return _bool_value(_first(validation, "session_valid"))


def _archive_path(archive_dir: Path, filled: pd.DataFrame) -> Path:
    session_date = _first(filled, "session_date") or "unknown"
    signal_date = _first(filled, "selected_signal_date") or "unknown"
    return (
        archive_dir
        / f"regime_informed_manual_session_filled_{session_date}_signal_{signal_date}.csv"
    )


def _append_archive_index(
    *,
    index_path: Path,
    source_path: Path,
    archive_path: Path,
    filled: pd.DataFrame,
    ledger: pd.DataFrame,
    session_valid: bool,
    archive_status: str,
    notes: str,
) -> pd.DataFrame:
    existing = _read_csv(index_path)
    row = {
        "archived_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source_path),
        "archive_path": str(archive_path),
        "session_date": _first(filled, "session_date"),
        "selected_signal_date": _first(filled, "selected_signal_date"),
        "row_count": len(filled),
        "session_valid": session_valid,
        "ledger_row_count_after_ingestion": len(ledger),
        "archive_status": archive_status,
        "notes": notes,
    }
    if existing.empty:
        archive_index = pd.DataFrame([row])
    else:
        archive_index = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        archive_index = archive_index.drop_duplicates(
            ["archive_path", "session_date", "selected_signal_date"],
            keep="last",
        )
    _write_csv(archive_index, index_path)
    return archive_index


def _runbook_text() -> str:
    return "\n".join(
        [
            "# Regime-Informed Next Session Runbook",
            "",
            "NO LIVE TRADING",
            "NO REAL MONEY",
            "NO BROKER/API",
            "NO STRATEGY PROMOTION",
            "MANUAL PAPER ONLY",
            "REGIME-INFORMED PAPER WORKFLOW",
            "",
            "1. Run `--daily-paper-only` after fresh data is available.",
            "2. Review the regime-informed tear sheet.",
            "3. Review the portfolio-performance notebook.",
            "4. Create the filled CSV from the latest template.",
            "5. Validate using Phase21E or the daily runner.",
            "6. Confirm ledger update.",
            "7. Do not reuse stale filled files.",
            "",
        ]
    )


def save_phase21g_regime_informed_session_rollover(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config)
    if not _bool_value(section.get("enabled", False)):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    output_dir = _resolve_path(
        section.get("output_dir"),
        reports_path / "paper_trading" / "regime_informed_tracking",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        reports_path / "paper_trading" / "dashboard",
    )
    archive_dir = _resolve_path(section.get("archive_dir"), output_dir / "archive")
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    template_path = output_dir / str(
        section.get("template_filename", "regime_informed_manual_session_template.csv")
    )
    filled_path = output_dir / str(
        section.get("filled_filename", "regime_informed_manual_session_filled.csv")
    )
    ledger_path = output_dir / str(
        section.get("ledger_filename", "regime_informed_manual_session_ledger.csv")
    )
    validation_path = output_dir / "regime_informed_session_validation.csv"

    template = _read_csv(template_path)
    filled_present = filled_path.exists() and filled_path.is_file()
    filled = _read_csv(filled_path) if filled_present else pd.DataFrame()
    ledger = _read_csv(ledger_path)
    validation = _read_csv(validation_path)

    matches_current = _filled_matches_template(template, filled) if filled_present else False
    already_ingested = _filled_already_ingested(filled, ledger) if filled_present else False
    session_valid = _session_valid(validation) if filled_present else False
    stale = bool(filled_present and not matches_current)
    archive_written = False
    archive_target = Path("")
    blocking_reason = ""

    if not filled_present:
        action = "no_filled_file_pending_user_entries"
    elif stale:
        action = "stale_filled_file_blocked"
        blocking_reason = "filled_file_session_or_signal_date_does_not_match_current_template"
    elif not session_valid:
        action = "invalid_filled_file_manual_review_required"
        blocking_reason = "filled_session_validation_not_valid"
    elif already_ingested:
        action = "valid_already_ingested_session_archived"
        if _bool_value(section.get("archive_completed_valid_sessions", True)):
            archive_target = _archive_path(archive_dir, filled)
            shutil.copy2(filled_path, archive_target)
            archive_written = True
    else:
        action = "current_filled_file_available_for_ingestion"

    archive_index_path = archive_dir / "regime_informed_session_archive_index.csv"
    if archive_written:
        archive_index = _append_archive_index(
            index_path=archive_index_path,
            source_path=filled_path,
            archive_path=archive_target,
            filled=filled,
            ledger=ledger,
            session_valid=session_valid,
            archive_status="archived",
            notes="valid already-ingested regime-informed filled session archived",
        )
    else:
        if archive_index_path.exists():
            archive_index = _read_csv(archive_index_path)
        else:
            archive_index = pd.DataFrame(
                columns=[
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
            )
            _write_csv(archive_index, archive_index_path)

    status = pd.DataFrame(
        [
            {
                "run_date": datetime.now(timezone.utc).date().isoformat(),
                "current_template_session_date": _first(template, "session_date"),
                "current_template_selected_signal_date": _first(
                    template, "selected_signal_date"
                ),
                "filled_file_present": filled_present,
                "filled_session_date": _first(filled, "session_date"),
                "filled_selected_signal_date": _first(filled, "selected_signal_date"),
                "filled_matches_current_template": matches_current,
                "filled_already_ingested": already_ingested,
                "filled_session_valid": session_valid,
                "filled_session_stale": stale,
                "rollover_action": action,
                "rollover_blocking_reason": blocking_reason,
                "archive_path": str(archive_target) if archive_written else "",
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    status_path = output_dir / "regime_informed_session_rollover_status.csv"
    _write_csv(status, status_path)

    runbook_path = output_dir / "regime_informed_next_session_runbook.md"
    runbook_path.write_text(_runbook_text(), encoding="utf-8")

    decision = f"regime_informed_session_rollover_{action.removesuffix('_for_ingestion')}"
    if action == "current_filled_file_available_for_ingestion":
        decision = "regime_informed_session_rollover_current_filled_file_available"
    elif action == "valid_already_ingested_session_archived":
        decision = "regime_informed_session_rollover_valid_session_archived"

    dashboard = pd.DataFrame(
        [
            {
                "phase21g_decision": decision,
                "run_date": status.loc[0, "run_date"],
                "filled_file_present": filled_present,
                "filled_matches_current_template": matches_current,
                "filled_already_ingested": already_ingested,
                "filled_session_valid": session_valid,
                "filled_session_stale": stale,
                "archive_written": archive_written,
                "archive_path": str(archive_target) if archive_written else "",
                "rollover_action": action,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": blocking_reason,
            }
        ]
    )
    dashboard_path = dashboard_dir / "regime_informed_session_rollover_status.csv"
    _write_csv(dashboard, dashboard_path)

    gates = pd.DataFrame(
        [
            {"gate_id": "rollover_status_written", "passed": status_path.exists()},
            {"gate_id": "archive_index_written", "passed": archive_index_path.exists()},
            {"gate_id": "next_session_runbook_written", "passed": runbook_path.exists()},
            {"gate_id": "dashboard_status_written", "passed": dashboard_path.exists()},
            {"gate_id": "stale_status_explicit", "passed": isinstance(stale, bool)},
            {"gate_id": "promotion_disabled", "passed": True},
            {"gate_id": "live_trading_disabled", "passed": True},
            {"gate_id": "real_money_disabled", "passed": True},
            {"gate_id": "broker_api_integration_disabled", "passed": True},
        ]
    )
    all_gates_passed = bool(gates["passed"].map(_bool_value).all())
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 21G",
                "phase21g_decision": decision,
                "all_gates_passed": all_gates_passed,
                "filled_file_present": filled_present,
                "filled_matches_current_template": matches_current,
                "filled_already_ingested": already_ingested,
                "filled_session_valid": session_valid,
                "filled_session_stale": stale,
                "archive_written": archive_written,
                "archive_path": str(archive_target) if archive_written else "",
                "rollover_action": action,
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 21G",
                "diagnostic": "Regime-informed manual session rollover and archive guard",
                "phase21g_decision": decision,
                "all_gates_passed": all_gates_passed,
                "rollover_action": action,
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "No orders placed. Filled file is copied to archive when already ingested and valid.",
            }
        ]
    )
    _write_csv(summary, output_dir / "phase21g_summary.csv")
    _write_csv(gates, output_dir / "phase21g_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase21g_conclusion.csv")
    print("Wrote Phase 21G regime-informed session rollover reports.")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "rollover_status": status,
        "archive_index": archive_index,
        "dashboard_status": dashboard,
    }
