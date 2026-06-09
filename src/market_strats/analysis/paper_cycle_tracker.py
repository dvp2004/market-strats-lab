from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PHASE18B_SECTION = "phase18b_paper_cycle_tracker"
TEAR_SHEET_CSV = "daily_execution_tear_sheet.csv"
TEAR_SHEET_MD = "daily_execution_tear_sheet.md"


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE18B_SECTION, {}) or {}


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


def _tear_sheet_values(tear_sheet: pd.DataFrame) -> dict[str, str]:
    if tear_sheet.empty or not {"key", "value"}.issubset(tear_sheet.columns):
        return {}
    return {
        _text_value(row["key"]): _text_value(row["value"])
        for row in tear_sheet.to_dict(orient="records")
    }


def _split_values(value: Any) -> list[str]:
    text = _text_value(value)
    if text == "" or text.lower() in {"none", "not_available"}:
        return []
    values: list[str] = []
    for chunk in text.replace(";", ",").split(","):
        stripped = chunk.strip()
        if stripped and stripped.lower() not in {"none", "not_available"}:
            values.append(stripped)
    return values


def _join_values(values: list[str]) -> str:
    unique = sorted({value for value in values if value})
    return ", ".join(unique) if unique else "none"


def _symbols_with_text(data_quality: pd.DataFrame, column: str) -> list[str]:
    if data_quality.empty or column not in data_quality.columns or "symbol" not in data_quality.columns:
        return []
    rows = data_quality[data_quality[column].map(_text_value).str.len() > 0]
    return sorted(rows["symbol"].astype(str).tolist())


def _phase18a_gate_passed(conclusion: pd.DataFrame) -> bool:
    if conclusion.empty:
        return False
    if "all_gates_passed" in conclusion.columns:
        return _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
    if "decision" in conclusion.columns:
        return "failed" not in _text_value(conclusion.iloc[0].get("decision", "")).lower()
    return False


def _phase18a_decision(conclusion: pd.DataFrame) -> str:
    if conclusion.empty or "decision" not in conclusion.columns:
        return "phase18a_conclusion_missing"
    return _text_value(conclusion.iloc[0].get("decision", ""))


def _manual_journal_status(template: pd.DataFrame, tear_values: dict[str, str]) -> str:
    if "manual_journal_status" in tear_values:
        return tear_values["manual_journal_status"]
    if template.empty or "manual_execution_status" not in template.columns:
        return "not_available"
    counts = template["manual_execution_status"].astype(str).value_counts()
    return ", ".join(f"{status}:{count}" for status, count in counts.items())


def _manual_journal_entries_complete(template: pd.DataFrame, required: bool) -> bool:
    if not required:
        return True
    if template.empty or "manual_execution_status" not in template.columns:
        return False
    statuses = template["manual_execution_status"].astype(str).str.strip().str.lower()
    incomplete = {"", "not_entered", "not entered", "pending", "not_available"}
    return bool(not statuses.isin(incomplete).any())


def build_current_cycle_row(
    *,
    tear_sheet: pd.DataFrame,
    phase18a_conclusion: pd.DataFrame,
    data_quality: pd.DataFrame,
    manual_journal_template: pd.DataFrame,
    tear_sheet_csv_available: bool,
    tear_sheet_md_available: bool,
    cycle_date: str | None = None,
) -> dict[str, Any]:
    values = _tear_sheet_values(tear_sheet)
    warning_symbols = _symbols_with_text(data_quality, "warnings") or _split_values(
        values.get("symbols_with_warnings", "")
    )
    blocking_symbols = _symbols_with_text(data_quality, "blocking_failures") or _split_values(
        values.get("symbols_with_blocking_failures", "")
    )
    phase18a_gate_passed = _phase18a_gate_passed(phase18a_conclusion)
    live_trading_allowed = _bool_value(values.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(values.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        values.get("broker_api_integration_allowed", False)
    )
    safety_flags_clear = not any(
        [live_trading_allowed, real_money_allowed, broker_api_integration_allowed]
    )
    warning_cycle = bool(warning_symbols and not blocking_symbols)
    blocked_cycle = bool(blocking_symbols)
    clean_cycle = bool(
        not warning_symbols
        and not blocking_symbols
        and phase18a_gate_passed
        and tear_sheet_csv_available
        and tear_sheet_md_available
        and safety_flags_clear
    )
    watchlist_preview_available = _text_value(
        values.get("nonzero_watchlist_preview_orders", "")
    ).lower() not in {"", "none", "not_available"}

    return {
        "cycle_date": cycle_date or _generated_date(),
        "selected_signal_date": values.get("selected_signal_date", ""),
        "data_as_of_date": values.get("data_as_of_date", ""),
        "fresh_data_status": values.get("fresh_data_quality_status", "not_available"),
        "warning_symbols": _join_values(warning_symbols),
        "blocking_symbols": _join_values(blocking_symbols),
        "final_manual_action": values.get("final_recommended_manual_action", ""),
        "phase18a_decision": _phase18a_decision(phase18a_conclusion),
        "recurring_paper_trading_ready_from_phase18a": _bool_value(
            values.get("recurring_paper_trading_ready", False)
        ),
        "manual_journal_status_summary": _manual_journal_status(
            manual_journal_template,
            values,
        ),
        "baseline_action": values.get("baseline_paper_action", ""),
        "watchlist_preview_available": watchlist_preview_available,
        "tear_sheet_csv_available": tear_sheet_csv_available,
        "tear_sheet_md_available": tear_sheet_md_available,
        "clean_cycle": clean_cycle,
        "warning_cycle": warning_cycle,
        "blocked_cycle": blocked_cycle,
        "live_trading_allowed": live_trading_allowed,
        "real_money_allowed": real_money_allowed,
        "broker_api_integration_allowed": broker_api_integration_allowed,
        "notes": values.get("final_recommended_manual_action", ""),
    }


def update_cycle_history(
    *,
    existing_history: pd.DataFrame,
    current_cycle: pd.DataFrame,
) -> pd.DataFrame:
    history = pd.concat([existing_history, current_cycle], ignore_index=True)
    if history.empty:
        return history
    key_columns = ["cycle_date", "selected_signal_date", "data_as_of_date"]
    for column in key_columns:
        if column not in history.columns:
            history[column] = ""
    history = history.drop_duplicates(subset=key_columns, keep="last")
    return history.sort_values(key_columns).reset_index(drop=True)


def _as_bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([False] * len(frame), index=frame.index)
    return frame[column].map(_bool_value)


def _current_consecutive_clean_cycles(history: pd.DataFrame) -> int:
    if history.empty:
        return 0
    count = 0
    clean = _as_bool_series(history, "clean_cycle")
    for is_clean in reversed(clean.tolist()):
        if not is_clean:
            break
        count += 1
    return count


def build_streak_report(
    *,
    history: pd.DataFrame,
    required_consecutive_clean_cycles: int,
    allow_warning_cycles_for_readiness: bool,
    require_manual_journal_entries: bool,
    manual_journal_entries_complete: bool,
) -> pd.DataFrame:
    latest = history.iloc[-1] if not history.empty else pd.Series(dtype=object)
    current_clean_streak = _current_consecutive_clean_cycles(history)
    latest_clean = _bool_value(latest.get("clean_cycle", False))
    latest_warning = _bool_value(latest.get("warning_cycle", False))
    latest_blocked = _bool_value(latest.get("blocked_cycle", False))
    safety_flags_clear = not any(
        [
            _bool_value(latest.get("live_trading_allowed", False)),
            _bool_value(latest.get("real_money_allowed", False)),
            _bool_value(latest.get("broker_api_integration_allowed", False)),
        ]
    )
    readiness_blockers: list[str] = []
    if current_clean_streak < required_consecutive_clean_cycles:
        readiness_blockers.append("insufficient_consecutive_clean_cycles")
    if not latest_clean:
        readiness_blockers.append("latest_cycle_not_clean")
    if latest_warning and not allow_warning_cycles_for_readiness:
        readiness_blockers.append("latest_cycle_has_warning")
    if latest_blocked:
        readiness_blockers.append("latest_cycle_blocked")
    if require_manual_journal_entries and not manual_journal_entries_complete:
        readiness_blockers.append("manual_journal_entries_incomplete")
    if not safety_flags_clear:
        readiness_blockers.append("execution_safety_flags_not_false")

    readiness = bool(not readiness_blockers)
    return pd.DataFrame(
        [
            {
                "total_cycles_recorded": len(history),
                "required_consecutive_clean_cycles": required_consecutive_clean_cycles,
                "current_consecutive_clean_cycles": current_clean_streak,
                "latest_cycle_clean": latest_clean,
                "latest_cycle_warning": latest_warning,
                "latest_cycle_blocked": latest_blocked,
                "warnings_allowed_for_readiness": allow_warning_cycles_for_readiness,
                "manual_journal_entries_required": require_manual_journal_entries,
                "manual_journal_entries_complete": manual_journal_entries_complete,
                "recurring_paper_readiness_candidate": readiness,
                "readiness_blocking_reasons": ";".join(readiness_blockers),
            }
        ]
    )


def build_warning_block_history(
    *,
    cycle_row: dict[str, Any],
    data_quality: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if data_quality.empty:
        return pd.DataFrame(
            columns=[
                "cycle_date",
                "selected_signal_date",
                "symbol",
                "severity",
                "warning_or_block_reason",
                "source_file",
                "notes",
            ]
        )
    for row in data_quality.to_dict(orient="records"):
        symbol = _text_value(row.get("symbol", ""))
        for reason in _split_values(row.get("warnings", "")):
            rows.append(
                {
                    "cycle_date": cycle_row["cycle_date"],
                    "selected_signal_date": cycle_row["selected_signal_date"],
                    "symbol": symbol,
                    "severity": "warning",
                    "warning_or_block_reason": reason,
                    "source_file": "fresh_data_quality_report.csv",
                    "notes": "fresh data warning recorded for cycle tracker",
                }
            )
        for reason in _split_values(row.get("blocking_failures", "")):
            rows.append(
                {
                    "cycle_date": cycle_row["cycle_date"],
                    "selected_signal_date": cycle_row["selected_signal_date"],
                    "symbol": symbol,
                    "severity": "block",
                    "warning_or_block_reason": reason,
                    "source_file": "fresh_data_quality_report.csv",
                    "notes": "fresh data block recorded for cycle tracker",
                }
            )
    return pd.DataFrame(rows)


def update_warning_block_history(
    *,
    existing_history: pd.DataFrame,
    current_warning_block_history: pd.DataFrame,
) -> pd.DataFrame:
    history = pd.concat(
        [existing_history, current_warning_block_history],
        ignore_index=True,
    )
    if history.empty:
        return history
    key_columns = [
        "cycle_date",
        "selected_signal_date",
        "symbol",
        "severity",
        "warning_or_block_reason",
    ]
    for column in key_columns:
        if column not in history.columns:
            history[column] = ""
    history = history.drop_duplicates(subset=key_columns, keep="last")
    return history.sort_values(key_columns).reset_index(drop=True)


def build_runbook_markdown() -> str:
    return "\n".join(
        [
            "# Phase 18B Paper Cycle Runbook",
            "",
            "**NO LIVE TRADING**",
            "",
            "**NO REAL MONEY**",
            "",
            "**NO BROKER/API**",
            "",
            "**MANUAL PAPER ONLY**",
            "",
            "## Recurring Manual Process",
            "",
            "1. Run WXYZ through Phase 18 pipeline:",
            "",
            "```powershell",
            '$env:MPLBACKEND="Agg"; .\\.venv\\Scripts\\python -m market_strats.run_backtest --config configs/spy_sma10.yaml --phase15wxyz-only',
            "```",
            "",
            "2. Open:",
            "",
            "```text",
            "reports/paper_trading/operational_hardening/daily_execution_tear_sheet.md",
            "```",
            "",
            "3. If action is `MANUAL REVIEW REQUIRED — HOLD CURRENT STATE`, do not paper-enter anything.",
            "4. If action is `WARNINGS PRESENT — MANUAL REVIEW BEFORE PAPER ENTRY`, review warnings manually before entering paper orders.",
            "5. If action is `NO BLOCKING ISSUES — MANUAL PAPER PREVIEW ONLY`, review preview orders and optionally enter them manually in paper account.",
            "6. Record any manual paper fills in:",
            "",
            "```text",
            "reports/paper_trading/operational_hardening/manual_execution_journal_template.csv",
            "```",
            "",
            "7. Re-run or archive the cycle tracker.",
            "8. Do not use live trading, real money, or broker/API.",
            "",
        ]
    )


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def save_phase18b_paper_cycle_tracker(
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
        reports_path / "paper_trading" / "cycle_tracker",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        reports_path / "paper_trading" / "dashboard",
    )
    phase18a_dir = _resolve_path(
        section.get("source_operational_hardening_dir"),
        reports_path / "paper_trading" / "operational_hardening",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    tear_sheet_path = phase18a_dir / TEAR_SHEET_CSV
    tear_sheet_md_path = phase18a_dir / TEAR_SHEET_MD
    phase18a_conclusion_path = phase18a_dir / "phase18a_conclusion.csv"
    data_quality_path = phase18a_dir / "fresh_data_quality_report.csv"
    manual_journal_path = phase18a_dir / "manual_execution_journal_template.csv"

    tear_sheet = _read_csv(tear_sheet_path)
    phase18a_conclusion = _read_csv(phase18a_conclusion_path)
    data_quality = _read_csv(data_quality_path)
    manual_journal_template = _read_csv(manual_journal_path)

    current_cycle_row = build_current_cycle_row(
        tear_sheet=tear_sheet,
        phase18a_conclusion=phase18a_conclusion,
        data_quality=data_quality,
        manual_journal_template=manual_journal_template,
        tear_sheet_csv_available=tear_sheet_path.exists(),
        tear_sheet_md_available=tear_sheet_md_path.exists(),
    )
    current_cycle = pd.DataFrame([current_cycle_row])

    history_path = output_dir / "paper_cycle_history.csv"
    existing_history = _read_csv(history_path)
    history = update_cycle_history(
        existing_history=existing_history,
        current_cycle=current_cycle,
    )
    latest_cycle = history.tail(1).reset_index(drop=True)

    required_clean_cycles = int(section.get("required_consecutive_clean_cycles", 10))
    allow_warning_cycles = _bool_value(section.get("allow_warning_cycles_for_readiness", False))
    require_manual_entries = _bool_value(section.get("require_manual_journal_entries", False))
    manual_entries_complete = _manual_journal_entries_complete(
        manual_journal_template,
        require_manual_entries,
    )
    streak_report = build_streak_report(
        history=history,
        required_consecutive_clean_cycles=required_clean_cycles,
        allow_warning_cycles_for_readiness=allow_warning_cycles,
        require_manual_journal_entries=require_manual_entries,
        manual_journal_entries_complete=manual_entries_complete,
    )

    warning_block_history_path = output_dir / "paper_cycle_warning_block_history.csv"
    existing_warning_block_history = _read_csv(warning_block_history_path)
    current_warning_block_history = build_warning_block_history(
        cycle_row=current_cycle_row,
        data_quality=data_quality,
    )
    warning_block_history = update_warning_block_history(
        existing_history=existing_warning_block_history,
        current_warning_block_history=current_warning_block_history,
    )

    runbook_path = output_dir / "paper_cycle_runbook.md"
    runbook = build_runbook_markdown()
    _write_text(runbook, runbook_path)

    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )
    history_path_candidate = output_dir / "paper_cycle_history.csv"
    latest_path = output_dir / "paper_cycle_latest.csv"
    streak_path = output_dir / "paper_cycle_streak_report.csv"

    _write_csv(history, history_path_candidate)
    _write_csv(latest_cycle, latest_path)
    _write_csv(streak_report, streak_path)
    _write_csv(warning_block_history, warning_block_history_path)

    history_written = history_path_candidate.exists() and not history.empty
    latest_written = latest_path.exists() and not latest_cycle.empty
    streak_written = streak_path.exists() and not streak_report.empty
    warning_history_written = warning_block_history_path.exists()
    runbook_written = runbook_path.exists() and runbook_path.stat().st_size > 0
    safety_flags_clear = not any(
        [live_trading_allowed, real_money_allowed, broker_api_integration_allowed]
    )
    gates = pd.DataFrame(
        [
            _gate_row("phase18a_tear_sheet_csv_exists", tear_sheet_path.exists()),
            _gate_row("phase18a_tear_sheet_md_exists", tear_sheet_md_path.exists()),
            _gate_row("cycle_history_written", history_written),
            _gate_row("latest_cycle_written", latest_written),
            _gate_row("streak_report_written", streak_written),
            _gate_row("warning_block_history_written", warning_history_written),
            _gate_row("runbook_written", runbook_written),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row(
                "broker_api_integration_disabled",
                not broker_api_integration_allowed,
            ),
            _gate_row("no_safety_flags_true", safety_flags_clear),
        ]
    )
    all_gates_passed = bool(gates["passed"].all())
    readiness_candidate = _bool_value(
        streak_report.iloc[0].get("recurring_paper_readiness_candidate", False)
    )
    recurring_ready = bool(all_gates_passed and readiness_candidate)
    if not all_gates_passed:
        decision = "paper_cycle_tracker_failed_closed"
    elif recurring_ready:
        decision = "paper_cycle_tracker_written_readiness_met"
    else:
        decision = "paper_cycle_tracker_written_readiness_not_met"
    failed_gates = ";".join(gates.loc[~gates["passed"], "gate_id"].astype(str).tolist())

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 18B",
                "decision": decision,
                "all_gates_passed": all_gates_passed,
                "total_cycles_recorded": len(history),
                "latest_cycle_clean": _bool_value(latest_cycle.iloc[0].get("clean_cycle", False))
                if not latest_cycle.empty
                else False,
                "latest_cycle_warning": _bool_value(
                    latest_cycle.iloc[0].get("warning_cycle", False)
                )
                if not latest_cycle.empty
                else False,
                "latest_cycle_blocked": _bool_value(
                    latest_cycle.iloc[0].get("blocked_cycle", False)
                )
                if not latest_cycle.empty
                else False,
                "required_consecutive_clean_cycles": required_clean_cycles,
                "current_consecutive_clean_cycles": int(
                    streak_report.iloc[0].get("current_consecutive_clean_cycles", 0)
                ),
                "recurring_paper_trading_ready": recurring_ready,
                "manual_paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
                "readiness_blocking_reasons": streak_report.iloc[0].get(
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
                "phase": "Phase 18B",
                "diagnostic": "Recurring paper-cycle tracking and readiness streak",
                "decision": decision,
                "all_gates_passed": all_gates_passed,
                "recurring_paper_trading_ready": recurring_ready,
                "manual_paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "readiness_blocking_reasons": streak_report.iloc[0].get(
                    "readiness_blocking_reasons",
                    "",
                ),
            }
        ]
    )
    dashboard_status = summary[
        [
            "phase",
            "decision",
            "all_gates_passed",
            "total_cycles_recorded",
            "latest_cycle_clean",
            "latest_cycle_warning",
            "latest_cycle_blocked",
            "current_consecutive_clean_cycles",
            "required_consecutive_clean_cycles",
            "recurring_paper_trading_ready",
            "readiness_blocking_reasons",
        ]
    ].copy()

    _write_csv(summary, output_dir / "phase18b_summary.csv")
    _write_csv(gates, output_dir / "phase18b_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase18b_conclusion.csv")
    _write_csv(dashboard_status, dashboard_dir / "paper_cycle_tracker_status.csv")

    outputs = {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "paper_cycle_history": history,
        "paper_cycle_latest": latest_cycle,
        "paper_cycle_streak_report": streak_report,
        "paper_cycle_warning_block_history": warning_block_history,
        "paper_cycle_tracker_status": dashboard_status,
    }
    print("Wrote Phase 18B paper-cycle tracker reports.")
    return outputs
