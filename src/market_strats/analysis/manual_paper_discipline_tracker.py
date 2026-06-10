from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PHASE20E_SECTION = "phase20e_manual_paper_discipline_tracker"
ALLOWED_MANUAL_DECISIONS = {
    "enter_paper_trade",
    "skip_due_warning",
    "skip_due_block",
    "skip_user_choice",
}
ALLOWED_EXECUTION_STATUSES = {"entered", "skipped", "blocked"}
HISTORY_COLUMNS = [
    "session_date",
    "selected_signal_date",
    "candidate_count",
    "ledger_row_count",
    "manual_decisions",
    "execution_statuses",
    "warnings_present",
    "btc_positive_weight_present",
    "blocking_symbols_present",
    "clean_signal_cycle",
    "valid_discipline_cycle",
    "entered_trade_present",
    "skipped_trade_present",
    "all_rows_acknowledged",
    "all_manual_decisions_complete",
    "all_execution_statuses_valid",
    "unexplained_override_present",
    "safety_flags_valid",
    "discipline_cycle_blocking_reasons",
]
CANDIDATE_SUMMARY_COLUMNS = [
    "canonical_candidate_id",
    "candidate_role",
    "sessions_seen",
    "rows_seen",
    "entered_count",
    "skipped_count",
    "blocked_count",
    "warning_skip_count",
    "valid_rows",
    "invalid_rows",
    "latest_manual_decision",
    "latest_execution_status",
    "latest_session_date",
    "btc_positive_seen",
    "btc_acknowledged_when_required",
    "candidate_discipline_status",
    "candidate_discipline_notes",
]


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE20E_SECTION, {}) or {}


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
    return ";".join(unique)


def _unique_join(series: pd.Series) -> str:
    values = [
        _text_value(value)
        for value in series.dropna().tolist()
        if _text_value(value) != ""
    ]
    return _join_values(values)


def _source_paths(
    *,
    manual_session_dir: Path,
    cycle_tracker_dir: Path,
    finalist_tracking_dir: Path,
    dashboard_dir: Path,
) -> dict[str, Path]:
    return {
        "manual_paper_session_ledger": manual_session_dir
        / "manual_paper_session_ledger.csv",
        "manual_paper_session_ingestion_result": manual_session_dir
        / "manual_paper_session_ingestion_result.csv",
        "manual_paper_session_row_validation": manual_session_dir
        / "manual_paper_session_row_validation.csv",
        "paper_cycle_history": cycle_tracker_dir / "paper_cycle_history.csv",
        "paper_cycle_latest": cycle_tracker_dir / "paper_cycle_latest.csv",
        "finalist_daily_tracking_tear_sheet": finalist_tracking_dir
        / "finalist_daily_tracking_tear_sheet.csv",
        "finalist_tracking_status": dashboard_dir / "finalist_tracking_status.csv",
    }


def _missing_sources(source_paths: dict[str, Path]) -> list[str]:
    return [
        str(path)
        for path in source_paths.values()
        if not path.exists() or path.is_dir()
    ]


def _warning_symbols_for_session(
    *,
    session_date: str,
    selected_signal_date: str,
    cycle_history: pd.DataFrame,
    cycle_latest: pd.DataFrame,
    finalist_tracking_status: pd.DataFrame,
    tear_sheet: pd.DataFrame,
) -> list[str]:
    if not cycle_history.empty:
        history = cycle_history.copy()
        if {"cycle_date", "selected_signal_date", "warning_symbols"}.issubset(
            history.columns
        ):
            matches = history[
                (history["cycle_date"].astype(str) == session_date)
                & (history["selected_signal_date"].astype(str) == selected_signal_date)
            ]
            if not matches.empty:
                return _split_values(matches.iloc[-1].get("warning_symbols", ""))
    if not cycle_latest.empty and "warning_symbols" in cycle_latest.columns:
        return _split_values(cycle_latest.iloc[0].get("warning_symbols", ""))
    if not finalist_tracking_status.empty and "warning_symbols" in finalist_tracking_status:
        return _split_values(finalist_tracking_status.iloc[0].get("warning_symbols", ""))
    if not tear_sheet.empty and {"key", "value"}.issubset(tear_sheet.columns):
        rows = tear_sheet.loc[tear_sheet["key"].astype(str) == "warning_symbols", "value"]
        if not rows.empty:
            return _split_values(rows.iloc[-1])
    return []


def _blocking_symbols_for_session(
    *,
    session_date: str,
    selected_signal_date: str,
    cycle_history: pd.DataFrame,
    cycle_latest: pd.DataFrame,
    finalist_tracking_status: pd.DataFrame,
    tear_sheet: pd.DataFrame,
) -> list[str]:
    if not cycle_history.empty:
        history = cycle_history.copy()
        if {"cycle_date", "selected_signal_date", "blocking_symbols"}.issubset(
            history.columns
        ):
            matches = history[
                (history["cycle_date"].astype(str) == session_date)
                & (history["selected_signal_date"].astype(str) == selected_signal_date)
            ]
            if not matches.empty:
                return _split_values(matches.iloc[-1].get("blocking_symbols", ""))
    if not cycle_latest.empty and "blocking_symbols" in cycle_latest.columns:
        return _split_values(cycle_latest.iloc[0].get("blocking_symbols", ""))
    if (
        not finalist_tracking_status.empty
        and "blocking_symbols" in finalist_tracking_status.columns
    ):
        return _split_values(finalist_tracking_status.iloc[0].get("blocking_symbols", ""))
    if not tear_sheet.empty and {"key", "value"}.issubset(tear_sheet.columns):
        rows = tear_sheet.loc[tear_sheet["key"].astype(str) == "blocking_symbols", "value"]
        if not rows.empty:
            return _split_values(rows.iloc[-1])
    return []


def _candidate_blocks_present(
    *,
    finalist_tracking_status: pd.DataFrame,
    tear_sheet: pd.DataFrame,
) -> bool:
    if not finalist_tracking_status.empty:
        blocked_count = pd.to_numeric(
            pd.Series([finalist_tracking_status.iloc[0].get("blocked_candidate_count", 0)]),
            errors="coerce",
        ).iloc[0]
        if pd.notna(blocked_count) and float(blocked_count) > 0:
            return True
    if not tear_sheet.empty and {"key", "value"}.issubset(tear_sheet.columns):
        rows = tear_sheet.loc[tear_sheet["key"].astype(str) == "blocked_candidates", "value"]
        if not rows.empty and _split_values(rows.iloc[-1]):
            return True
    return False


def _session_row_validation(
    row_validation: pd.DataFrame,
    session_date: str,
    selected_signal_date: str,
) -> pd.DataFrame:
    if row_validation.empty:
        return row_validation
    required = {"session_date", "selected_signal_date"}
    if not required.issubset(row_validation.columns):
        return row_validation.iloc[0:0].copy()
    return row_validation[
        (row_validation["session_date"].astype(str) == session_date)
        & (row_validation["selected_signal_date"].astype(str) == selected_signal_date)
    ].copy()


def _unexplained_override_present(session_rows: pd.DataFrame) -> bool:
    for row in session_rows.to_dict(orient="records"):
        status = _text_value(row.get("manual_execution_status", "")).lower()
        decision = _text_value(row.get("manual_decision", "")).lower()
        reason = _text_value(row.get("override_reason", ""))
        notes = _text_value(row.get("notes", ""))
        if status in {"skipped", "blocked"} and not reason and not notes:
            return True
        if decision in {"skip_due_warning", "skip_due_block", "skip_user_choice"}:
            if not reason and not notes:
                return True
    return False


def build_manual_paper_discipline_history(
    *,
    ledger: pd.DataFrame,
    row_validation: pd.DataFrame,
    cycle_history: pd.DataFrame,
    cycle_latest: pd.DataFrame,
    finalist_tracking_status: pd.DataFrame,
    tear_sheet: pd.DataFrame,
    require_btc_ack_when_btc_weight_positive: bool = True,
    require_no_unexplained_overrides: bool = True,
    allow_warning_skip_as_valid_discipline_cycle: bool = True,
) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    rows: list[dict[str, Any]] = []
    ledger = ledger.copy()
    for column in [
        "session_date",
        "selected_signal_date",
        "canonical_candidate_id",
        "manual_decision",
        "manual_execution_status",
        "asset",
    ]:
        if column not in ledger.columns:
            ledger[column] = ""

    grouped = ledger.groupby(["session_date", "selected_signal_date"], dropna=False)
    for (session_date, selected_signal_date), session_rows in grouped:
        session_date_text = _text_value(session_date)
        signal_date_text = _text_value(selected_signal_date)
        validations = _session_row_validation(
            row_validation=row_validation,
            session_date=session_date_text,
            selected_signal_date=signal_date_text,
        )
        warning_symbols = _warning_symbols_for_session(
            session_date=session_date_text,
            selected_signal_date=signal_date_text,
            cycle_history=cycle_history,
            cycle_latest=cycle_latest,
            finalist_tracking_status=finalist_tracking_status,
            tear_sheet=tear_sheet,
        )
        blocking_symbols = _blocking_symbols_for_session(
            session_date=session_date_text,
            selected_signal_date=signal_date_text,
            cycle_history=cycle_history,
            cycle_latest=cycle_latest,
            finalist_tracking_status=finalist_tracking_status,
            tear_sheet=tear_sheet,
        )
        candidate_blocks = _candidate_blocks_present(
            finalist_tracking_status=finalist_tracking_status,
            tear_sheet=tear_sheet,
        )
        target_weights = pd.to_numeric(
            session_rows.get("target_weight", pd.Series(dtype=float)),
            errors="coerce",
        ).fillna(0.0)
        btc_positive = bool(
            (session_rows["asset"].astype(str) == "BTC-USD").to_numpy().any()
            and target_weights[session_rows["asset"].astype(str) == "BTC-USD"].gt(0).any()
        )
        all_rows_valid = (
            bool(validations["row_valid"].map(_bool_value).all())
            if not validations.empty and "row_valid" in validations.columns
            else False
        )
        all_tear_reviewed = (
            session_rows.get("tear_sheet_reviewed", pd.Series(dtype=bool))
            .map(_bool_value)
            .all()
        )
        warnings_ack = True
        if warning_symbols:
            warnings_ack = (
                session_rows.get("warnings_acknowledged", pd.Series(dtype=bool))
                .map(_bool_value)
                .all()
            )
        btc_ack = True
        if btc_positive and require_btc_ack_when_btc_weight_positive:
            btc_rows = session_rows[
                (session_rows["asset"].astype(str) == "BTC-USD") & target_weights.gt(0)
            ]
            btc_ack = bool(
                not btc_rows.empty
                and btc_rows.get("btc_caveat_acknowledged", pd.Series(dtype=bool))
                .map(_bool_value)
                .all()
            )
        decisions = session_rows["manual_decision"].astype(str).str.lower()
        statuses = session_rows["manual_execution_status"].astype(str).str.lower()
        manual_decisions_complete = bool(decisions.isin(ALLOWED_MANUAL_DECISIONS).all())
        execution_statuses_valid = bool(statuses.isin(ALLOWED_EXECUTION_STATUSES).all())
        unexplained_override = (
            _unexplained_override_present(session_rows)
            if require_no_unexplained_overrides
            else False
        )
        safety_flags_valid = True
        for column in [
            "live_trading_allowed",
            "real_money_allowed",
            "broker_api_integration_allowed",
        ]:
            if column in session_rows.columns:
                safety_flags_valid = safety_flags_valid and not bool(
                    session_rows[column].map(_bool_value).any()
                )
        all_ack = bool(all_tear_reviewed and warnings_ack and btc_ack)
        entered_present = bool(statuses.eq("entered").any())
        skipped_present = bool(statuses.eq("skipped").any())
        clean_signal_cycle = bool(
            not warning_symbols and not blocking_symbols and not candidate_blocks
        )
        discipline_blockers: list[str] = []
        if not all_rows_valid:
            discipline_blockers.append("phase20d_row_validation_failed_or_missing")
        if not all_tear_reviewed:
            discipline_blockers.append("tear_sheet_review_missing")
        if warning_symbols and not warnings_ack:
            discipline_blockers.append("warning_acknowledgement_missing")
        if btc_positive and require_btc_ack_when_btc_weight_positive and not btc_ack:
            discipline_blockers.append("btc_caveat_acknowledgement_missing")
        if not manual_decisions_complete:
            discipline_blockers.append("manual_decision_incomplete_or_invalid")
        if not execution_statuses_valid:
            discipline_blockers.append("execution_status_invalid")
        if (
            warning_symbols
            and not allow_warning_skip_as_valid_discipline_cycle
            and decisions.eq("skip_due_warning").any()
        ):
            discipline_blockers.append("warning_skip_not_allowed")
        if unexplained_override:
            discipline_blockers.append("unexplained_override_present")
        if not safety_flags_valid:
            discipline_blockers.append("safety_flag_true")
        valid_discipline_cycle = len(discipline_blockers) == 0
        rows.append(
            {
                "session_date": session_date_text,
                "selected_signal_date": signal_date_text,
                "candidate_count": session_rows["canonical_candidate_id"].nunique(),
                "ledger_row_count": len(session_rows),
                "manual_decisions": _unique_join(session_rows["manual_decision"]),
                "execution_statuses": _unique_join(session_rows["manual_execution_status"]),
                "warnings_present": bool(warning_symbols),
                "btc_positive_weight_present": btc_positive,
                "blocking_symbols_present": bool(blocking_symbols or candidate_blocks),
                "clean_signal_cycle": clean_signal_cycle,
                "valid_discipline_cycle": valid_discipline_cycle,
                "entered_trade_present": entered_present,
                "skipped_trade_present": skipped_present,
                "all_rows_acknowledged": all_ack,
                "all_manual_decisions_complete": manual_decisions_complete,
                "all_execution_statuses_valid": execution_statuses_valid,
                "unexplained_override_present": unexplained_override,
                "safety_flags_valid": safety_flags_valid,
                "discipline_cycle_blocking_reasons": _join_values(discipline_blockers),
            }
        )
    history = pd.DataFrame(rows, columns=HISTORY_COLUMNS)
    return history.sort_values(["session_date", "selected_signal_date"]).reset_index(
        drop=True
    )


def _current_streak(values: pd.Series) -> int:
    streak = 0
    for value in reversed(values.map(_bool_value).tolist()):
        if value:
            streak += 1
        else:
            break
    return streak


def build_manual_paper_discipline_streak_report(
    *,
    history: pd.DataFrame,
    required_discipline_cycles: int,
    required_clean_signal_cycles: int,
    live_trading_allowed: bool,
    real_money_allowed: bool,
    broker_api_integration_allowed: bool,
) -> pd.DataFrame:
    if history.empty:
        blockers = [
            "no_manual_paper_sessions_recorded",
            "insufficient_valid_discipline_cycles",
            "insufficient_clean_signal_cycles",
        ]
        return pd.DataFrame(
            [
                {
                    "total_sessions": 0,
                    "valid_discipline_sessions": 0,
                    "clean_signal_sessions": 0,
                    "current_valid_discipline_streak": 0,
                    "current_clean_signal_streak": 0,
                    "required_discipline_cycles": required_discipline_cycles,
                    "required_clean_signal_cycles": required_clean_signal_cycles,
                    "latest_session_date": "",
                    "latest_session_valid_discipline": False,
                    "latest_session_clean_signal": False,
                    "ready_for_recurring_paper_tracking": False,
                    "readiness_blocking_reasons": _join_values(blockers),
                }
            ]
        )

    history_sorted = history.sort_values(["session_date", "selected_signal_date"]).reset_index(
        drop=True
    )
    valid_series = history_sorted["valid_discipline_cycle"].map(_bool_value)
    clean_series = history_sorted["clean_signal_cycle"].map(_bool_value)
    valid_count = int(valid_series.sum())
    clean_count = int(clean_series.sum())
    valid_streak = _current_streak(history_sorted["valid_discipline_cycle"])
    clean_streak = _current_streak(history_sorted["clean_signal_cycle"])
    latest = history_sorted.iloc[-1]
    latest_valid = _bool_value(latest.get("valid_discipline_cycle", False))
    latest_clean = _bool_value(latest.get("clean_signal_cycle", False))
    blockers: list[str] = []
    if valid_streak < required_discipline_cycles:
        blockers.append("insufficient_valid_discipline_cycles")
    if clean_streak < required_clean_signal_cycles:
        blockers.append("insufficient_clean_signal_cycles")
    if not latest_valid:
        blockers.append("latest_session_not_valid_discipline")
    if any([live_trading_allowed, real_money_allowed, broker_api_integration_allowed]):
        blockers.append("safety_flag_true")
    ready = len(blockers) == 0
    return pd.DataFrame(
        [
            {
                "total_sessions": len(history_sorted),
                "valid_discipline_sessions": valid_count,
                "clean_signal_sessions": clean_count,
                "current_valid_discipline_streak": valid_streak,
                "current_clean_signal_streak": clean_streak,
                "required_discipline_cycles": required_discipline_cycles,
                "required_clean_signal_cycles": required_clean_signal_cycles,
                "latest_session_date": latest.get("session_date", ""),
                "latest_session_valid_discipline": latest_valid,
                "latest_session_clean_signal": latest_clean,
                "ready_for_recurring_paper_tracking": ready,
                "readiness_blocking_reasons": _join_values(blockers),
            }
        ]
    )


def build_manual_paper_candidate_discipline_summary(
    *,
    ledger: pd.DataFrame,
    row_validation: pd.DataFrame,
) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame(columns=CANDIDATE_SUMMARY_COLUMNS)
    rows: list[dict[str, Any]] = []
    validation = row_validation.copy()
    for candidate_id, candidate_rows in ledger.groupby("canonical_candidate_id", dropna=False):
        candidate_id_text = _text_value(candidate_id)
        candidate_validations = validation
        if not validation.empty and "canonical_candidate_id" in validation.columns:
            candidate_validations = validation[
                validation["canonical_candidate_id"].astype(str) == candidate_id_text
            ]
        statuses = candidate_rows["manual_execution_status"].astype(str).str.lower()
        decisions = candidate_rows["manual_decision"].astype(str).str.lower()
        target_weights = pd.to_numeric(
            candidate_rows.get("target_weight", pd.Series(dtype=float)),
            errors="coerce",
        ).fillna(0.0)
        btc_positive_rows = candidate_rows[
            (candidate_rows["asset"].astype(str) == "BTC-USD") & target_weights.gt(0)
        ]
        btc_ack = True
        if not btc_positive_rows.empty:
            btc_ack = bool(
                btc_positive_rows["btc_caveat_acknowledged"].map(_bool_value).all()
            )
        valid_rows = (
            int(candidate_validations["row_valid"].map(_bool_value).sum())
            if not candidate_validations.empty and "row_valid" in candidate_validations
            else 0
        )
        invalid_rows = len(candidate_rows) - valid_rows
        safety_flags_valid = True
        for column in [
            "live_trading_allowed",
            "real_money_allowed",
            "broker_api_integration_allowed",
        ]:
            if column in candidate_rows.columns:
                safety_flags_valid = safety_flags_valid and not bool(
                    candidate_rows[column].map(_bool_value).any()
                )
        status = "valid"
        notes: list[str] = []
        if invalid_rows > 0:
            status = "invalid"
            notes.append("row_validation_failed")
        if not btc_ack:
            status = "invalid"
            notes.append("btc_acknowledgement_missing")
        if not safety_flags_valid:
            status = "invalid"
            notes.append("safety_flag_true")
        latest_session_date = candidate_rows["session_date"].astype(str).max()
        latest_rows = candidate_rows[
            candidate_rows["session_date"].astype(str) == latest_session_date
        ]
        rows.append(
            {
                "canonical_candidate_id": candidate_id_text,
                "candidate_role": _text_value(candidate_rows.iloc[-1].get("candidate_role", "")),
                "sessions_seen": candidate_rows[
                    ["session_date", "selected_signal_date"]
                ].drop_duplicates().shape[0],
                "rows_seen": len(candidate_rows),
                "entered_count": int(statuses.eq("entered").sum()),
                "skipped_count": int(statuses.eq("skipped").sum()),
                "blocked_count": int(statuses.eq("blocked").sum()),
                "warning_skip_count": int(decisions.eq("skip_due_warning").sum()),
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "latest_manual_decision": _unique_join(latest_rows["manual_decision"]),
                "latest_execution_status": _unique_join(
                    latest_rows["manual_execution_status"]
                ),
                "latest_session_date": latest_session_date,
                "btc_positive_seen": bool(not btc_positive_rows.empty),
                "btc_acknowledged_when_required": btc_ack,
                "candidate_discipline_status": status,
                "candidate_discipline_notes": _join_values(notes) if notes else "ok",
            }
        )
    return pd.DataFrame(rows, columns=CANDIDATE_SUMMARY_COLUMNS)


def build_manual_paper_discipline_dashboard_markdown(
    *,
    history: pd.DataFrame,
    streak_report: pd.DataFrame,
    candidate_summary: pd.DataFrame,
) -> str:
    streak = streak_report.iloc[0] if not streak_report.empty else pd.Series(dtype=object)
    latest_session_date = _text_value(streak.get("latest_session_date", ""))
    ready = _bool_value(streak.get("ready_for_recurring_paper_tracking", False))
    lines = [
        "# Phase 20E Manual Paper Discipline Dashboard",
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
        "## Latest Session",
        "",
        f"- Latest session date: `{latest_session_date}`",
        f"- Latest valid discipline cycle: `{streak.get('latest_session_valid_discipline', False)}`",
        f"- Latest clean signal cycle: `{streak.get('latest_session_clean_signal', False)}`",
        "",
        "## Streaks",
        "",
        f"- Valid discipline streak: `{streak.get('current_valid_discipline_streak', 0)}`",
        f"- Clean signal streak: `{streak.get('current_clean_signal_streak', 0)}`",
        f"- Ready for recurring paper tracking: `{ready}`",
        f"- Blocking reasons: `{streak.get('readiness_blocking_reasons', '')}`",
        "",
        "## Candidate Status",
        "",
    ]
    if candidate_summary.empty:
        lines.append("- No candidate rows available.")
    else:
        for row in candidate_summary.to_dict(orient="records"):
            lines.append(
                "- "
                f"`{row.get('canonical_candidate_id', '')}`: "
                f"status `{row.get('candidate_discipline_status', '')}`, "
                f"skipped `{row.get('skipped_count', 0)}`, "
                f"entered `{row.get('entered_count', 0)}`, "
                f"BTC positive seen `{row.get('btc_positive_seen', False)}`"
            )
    lines.extend(
        [
            "",
            "## History",
            "",
            f"- Total sessions: `{streak.get('total_sessions', 0)}`",
            f"- Valid discipline sessions: `{streak.get('valid_discipline_sessions', 0)}`",
            f"- Clean signal sessions: `{streak.get('clean_signal_sessions', 0)}`",
        ]
    )
    if not history.empty:
        latest = history.iloc[-1]
        lines.extend(
            [
                f"- Latest warnings present: `{latest.get('warnings_present', False)}`",
                f"- Latest BTC positive weight present: `{latest.get('btc_positive_weight_present', False)}`",
                f"- Latest discipline blockers: `{latest.get('discipline_cycle_blocking_reasons', '')}`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


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
    decision = "manual_paper_discipline_tracker_failed_closed"
    history = pd.DataFrame(columns=HISTORY_COLUMNS)
    streak = build_manual_paper_discipline_streak_report(
        history=history,
        required_discipline_cycles=10,
        required_clean_signal_cycles=10,
        live_trading_allowed=live_trading_allowed,
        real_money_allowed=real_money_allowed,
        broker_api_integration_allowed=broker_api_integration_allowed,
    )
    candidates = pd.DataFrame(columns=CANDIDATE_SUMMARY_COLUMNS)
    dashboard_md = build_manual_paper_discipline_dashboard_markdown(
        history=history,
        streak_report=streak,
        candidate_summary=candidates,
    )
    dashboard = pd.DataFrame(
        [
            {
                "phase20e_decision": decision,
                "latest_session_date": "",
                "valid_discipline_sessions": 0,
                "clean_signal_sessions": 0,
                "current_valid_discipline_streak": 0,
                "current_clean_signal_streak": 0,
                "ready_for_recurring_paper_tracking": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "missing required sources: " + ";".join(missing_sources),
            }
        ]
    )
    gates = pd.DataFrame(
        [
            _gate_row("manual_session_ledger_exists", False, ";".join(missing_sources)),
            _gate_row("discipline_history_written", True),
            _gate_row("streak_report_written", True),
            _gate_row("candidate_summary_written", True),
            _gate_row("dashboard_markdown_written", True),
            _gate_row("dashboard_csv_written", True),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row("broker_api_integration_disabled", not broker_api_integration_allowed),
        ]
    )
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 20E",
                "phase20e_decision": decision,
                "all_gates_passed": False,
                "ready_for_recurring_paper_tracking": False,
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
                "phase": "Phase 20E",
                "diagnostic": "Manual paper discipline tracking",
                "phase20e_decision": decision,
                "all_gates_passed": False,
                "ready_for_recurring_paper_tracking": False,
                "notes": "Failed closed because required source files are missing.",
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    _write_csv(summary, output_dir / "phase20e_summary.csv")
    _write_csv(gates, output_dir / "phase20e_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase20e_conclusion.csv")
    _write_csv(history, output_dir / "manual_paper_discipline_history.csv")
    _write_csv(streak, output_dir / "manual_paper_discipline_streak_report.csv")
    _write_csv(candidates, output_dir / "manual_paper_candidate_discipline_summary.csv")
    _write_text(dashboard_md, output_dir / "manual_paper_discipline_dashboard.md")
    _write_csv(dashboard, dashboard_dir / "manual_paper_discipline_status.csv")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "manual_paper_discipline_history": history,
        "manual_paper_discipline_streak_report": streak,
        "manual_paper_candidate_discipline_summary": candidates,
        "manual_paper_discipline_dashboard_status": dashboard,
    }


def save_phase20e_manual_paper_discipline_tracker(
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
    manual_session_dir = _resolve_path(
        section.get("source_manual_session_dir"),
        reports_path / "paper_trading" / "manual_sessions",
    )
    cycle_tracker_dir = _resolve_path(
        section.get("source_cycle_tracker_dir"),
        reports_path / "paper_trading" / "cycle_tracker",
    )
    finalist_tracking_dir = _resolve_path(
        section.get("source_finalist_tracking_dir"),
        reports_path / "paper_trading" / "finalist_tracking",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    source_paths = _source_paths(
        manual_session_dir=manual_session_dir,
        cycle_tracker_dir=cycle_tracker_dir,
        finalist_tracking_dir=finalist_tracking_dir,
        dashboard_dir=dashboard_dir,
    )
    missing = _missing_sources(source_paths)
    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )
    if missing:
        return _failure_outputs(
            output_dir=output_dir,
            dashboard_dir=dashboard_dir,
            missing_sources=missing,
            live_trading_allowed=live_trading_allowed,
            real_money_allowed=real_money_allowed,
            broker_api_integration_allowed=broker_api_integration_allowed,
        )

    ledger = _read_csv(source_paths["manual_paper_session_ledger"])
    ingestion_result = _read_csv(source_paths["manual_paper_session_ingestion_result"])
    row_validation = _read_csv(source_paths["manual_paper_session_row_validation"])
    cycle_history = _read_csv(source_paths["paper_cycle_history"])
    cycle_latest = _read_csv(source_paths["paper_cycle_latest"])
    tear_sheet = _read_csv(source_paths["finalist_daily_tracking_tear_sheet"])
    finalist_tracking_status = _read_csv(source_paths["finalist_tracking_status"])

    history = build_manual_paper_discipline_history(
        ledger=ledger,
        row_validation=row_validation,
        cycle_history=cycle_history,
        cycle_latest=cycle_latest,
        finalist_tracking_status=finalist_tracking_status,
        tear_sheet=tear_sheet,
        require_btc_ack_when_btc_weight_positive=_bool_value(
            section.get("require_btc_ack_when_btc_weight_positive", True)
        ),
        require_no_unexplained_overrides=_bool_value(
            section.get("require_no_unexplained_overrides", True)
        ),
        allow_warning_skip_as_valid_discipline_cycle=_bool_value(
            section.get("allow_warning_skip_as_valid_discipline_cycle", True)
        ),
    )
    required_discipline_cycles = int(section.get("required_discipline_cycles", 10))
    required_clean_signal_cycles = int(section.get("required_clean_signal_cycles", 10))
    streak = build_manual_paper_discipline_streak_report(
        history=history,
        required_discipline_cycles=required_discipline_cycles,
        required_clean_signal_cycles=required_clean_signal_cycles,
        live_trading_allowed=live_trading_allowed,
        real_money_allowed=real_money_allowed,
        broker_api_integration_allowed=broker_api_integration_allowed,
    )
    candidate_summary = build_manual_paper_candidate_discipline_summary(
        ledger=ledger,
        row_validation=row_validation,
    )
    dashboard_md = build_manual_paper_discipline_dashboard_markdown(
        history=history,
        streak_report=streak,
        candidate_summary=candidate_summary,
    )

    history_path = output_dir / "manual_paper_discipline_history.csv"
    streak_path = output_dir / "manual_paper_discipline_streak_report.csv"
    candidate_path = output_dir / "manual_paper_candidate_discipline_summary.csv"
    dashboard_md_path = output_dir / "manual_paper_discipline_dashboard.md"
    dashboard_csv_path = dashboard_dir / "manual_paper_discipline_status.csv"
    _write_csv(history, history_path)
    _write_csv(streak, streak_path)
    _write_csv(candidate_summary, candidate_path)
    _write_text(dashboard_md, dashboard_md_path)

    streak_row = streak.iloc[0] if not streak.empty else pd.Series(dtype=object)
    ready = _bool_value(streak_row.get("ready_for_recurring_paper_tracking", False))
    decision = (
        "manual_paper_discipline_tracker_written_ready"
        if ready
        else "manual_paper_discipline_tracker_written_readiness_not_met"
    )
    dashboard = pd.DataFrame(
        [
            {
                "phase20e_decision": decision,
                "latest_session_date": streak_row.get("latest_session_date", ""),
                "valid_discipline_sessions": int(
                    streak_row.get("valid_discipline_sessions", 0) or 0
                ),
                "clean_signal_sessions": int(streak_row.get("clean_signal_sessions", 0) or 0),
                "current_valid_discipline_streak": int(
                    streak_row.get("current_valid_discipline_streak", 0) or 0
                ),
                "current_clean_signal_streak": int(
                    streak_row.get("current_clean_signal_streak", 0) or 0
                ),
                "ready_for_recurring_paper_tracking": ready,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": streak_row.get("readiness_blocking_reasons", ""),
            }
        ]
    )
    _write_csv(dashboard, dashboard_csv_path)

    gates = pd.DataFrame(
        [
            _gate_row("manual_session_ledger_exists", not ledger.empty),
            _gate_row("discipline_history_written", history_path.exists() and not history.empty),
            _gate_row("streak_report_written", streak_path.exists() and not streak.empty),
            _gate_row(
                "candidate_summary_written",
                candidate_path.exists() and not candidate_summary.empty,
            ),
            _gate_row(
                "dashboard_markdown_written",
                dashboard_md_path.exists() and dashboard_md_path.stat().st_size > 0,
            ),
            _gate_row("dashboard_csv_written", dashboard_csv_path.exists()),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row("broker_api_integration_disabled", not broker_api_integration_allowed),
        ]
    )
    all_gates_passed = bool(gates["passed"].map(_bool_value).all())
    failed_gates = _join_values(
        gates.loc[~gates["passed"].map(_bool_value), "gate_id"].astype(str).tolist()
    )
    if not all_gates_passed:
        decision = "manual_paper_discipline_tracker_failed_closed"
        dashboard.loc[0, "phase20e_decision"] = decision
        _write_csv(dashboard, dashboard_csv_path)

    history_latest = history.iloc[-1] if not history.empty else pd.Series(dtype=object)
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 20E",
                "phase20e_decision": decision,
                "all_gates_passed": all_gates_passed,
                "total_sessions": int(streak_row.get("total_sessions", 0) or 0),
                "valid_discipline_sessions": int(
                    streak_row.get("valid_discipline_sessions", 0) or 0
                ),
                "clean_signal_sessions": int(streak_row.get("clean_signal_sessions", 0) or 0),
                "current_valid_discipline_streak": int(
                    streak_row.get("current_valid_discipline_streak", 0) or 0
                ),
                "current_clean_signal_streak": int(
                    streak_row.get("current_clean_signal_streak", 0) or 0
                ),
                "latest_session_valid_discipline": _bool_value(
                    streak_row.get("latest_session_valid_discipline", False)
                ),
                "latest_session_clean_signal": _bool_value(
                    streak_row.get("latest_session_clean_signal", False)
                ),
                "ready_for_recurring_paper_tracking": ready,
                "ingestion_session_valid": _bool_value(
                    ingestion_result.iloc[0].get("session_valid", False)
                    if not ingestion_result.empty
                    else False
                ),
                "latest_warnings_present": _bool_value(
                    history_latest.get("warnings_present", False)
                ),
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
                "readiness_blocking_reasons": streak_row.get(
                    "readiness_blocking_reasons",
                    "",
                ),
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 20E",
                "diagnostic": "Manual paper session discipline and streak tracker",
                "phase20e_decision": decision,
                "all_gates_passed": all_gates_passed,
                "ready_for_recurring_paper_tracking": ready,
                "notes": (
                    "Discipline tracking written. This is manual paper only and does "
                    "not test performance or promote a strategy."
                ),
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
            }
        ]
    )
    _write_csv(summary, output_dir / "phase20e_summary.csv")
    _write_csv(gates, output_dir / "phase20e_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase20e_conclusion.csv")
    print("Wrote Phase 20E manual paper discipline tracker reports.")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "manual_paper_discipline_history": history,
        "manual_paper_discipline_streak_report": streak,
        "manual_paper_candidate_discipline_summary": candidate_summary,
        "manual_paper_discipline_dashboard_status": dashboard,
    }
