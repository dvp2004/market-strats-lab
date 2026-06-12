from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PHASE21E_SECTION = "phase21e_regime_informed_session_ingestion"
ALLOWED_MANUAL_DECISIONS = {
    "enter_paper_trade",
    "skip_due_warning",
    "skip_due_block",
    "skip_user_choice",
}
ALLOWED_EXECUTION_STATUSES = {"entered", "skipped", "blocked", "cash_residual"}
FILLED_REQUIRED_COLUMNS = [
    "session_date",
    "selected_signal_date",
    "canonical_candidate_id",
    "candidate_role",
    "asset",
    "target_weight",
    "target_notional_usd",
    "tear_sheet_reviewed",
    "warnings_acknowledged",
    "btc_caveat_acknowledged",
    "reference_only_acknowledged",
    "inception_limited_acknowledged",
    "manual_decision",
    "manual_execution_status",
    "paper_account_value",
    "paper_fill_price",
    "paper_fill_quantity",
    "override_reason",
    "notes",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
    "promotion_allowed",
]
ROW_VALIDATION_COLUMNS = [
    "row_id",
    "session_date",
    "selected_signal_date",
    "canonical_candidate_id",
    "candidate_role",
    "asset",
    "target_weight",
    "manual_decision",
    "manual_execution_status",
    "row_valid",
    "row_blocking_reasons",
    "requires_btc_ack",
    "requires_reference_ack",
    "requires_inception_ack",
    "requires_warning_ack",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
    "promotion_allowed",
    "target_notional_usd",
    "paper_fill_price",
    "paper_fill_quantity",
    "actual_notional_usd",
    "deviation_from_preview_usd",
    "deviation_from_preview_pct",
]
LEDGER_COLUMNS = [
    "session_date",
    "selected_signal_date",
    "canonical_candidate_id",
    "candidate_role",
    "asset",
    "target_weight",
    "target_notional_usd",
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
    "candidate_caveats",
    "promotion_allowed",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
]
LEDGER_KEY_COLUMNS = [
    "session_date",
    "selected_signal_date",
    "canonical_candidate_id",
    "asset",
]
VALIDATION_COLUMNS = [
    "session_date",
    "selected_signal_date",
    "filled_file_present",
    "session_valid",
    "rows_expected",
    "rows_received",
    "rows_valid",
    "rows_invalid",
    "validation_status",
    "blocking_reasons",
    "promotion_allowed",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
]
DISCIPLINE_COLUMNS = [
    "total_sessions",
    "valid_sessions",
    "entered_sessions",
    "skipped_sessions",
    "blocked_sessions",
    "latest_session_date",
    "latest_session_valid",
    "latest_manual_decisions",
    "latest_execution_statuses",
    "reference_only_acknowledged",
    "btc_caveat_acknowledged",
    "inception_limited_acknowledged",
    "warnings_acknowledged",
    "discipline_status",
    "discipline_blocking_reasons",
]


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE21E_SECTION, {}) or {}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (dict, list, tuple, set)):
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


def _numeric(value: Any) -> float:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(converted) if pd.notna(converted) else np.nan


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


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _split_values(value: Any) -> list[str]:
    text = _text_value(value)
    if text == "" or text.lower() in {"none", "nan", "not_available"}:
        return []
    values = []
    for chunk in text.replace(";", ",").split(","):
        clean = chunk.strip()
        if clean and clean.lower() not in {"none", "nan", "not_available"}:
            values.append(clean)
    return values


def _join_values(values: list[str]) -> str:
    return ";".join(sorted({value for value in values if value}))


def _unique_join(values: pd.Series) -> str:
    return _join_values([_text_value(value) for value in values.tolist()])


def _first_available(frame: pd.DataFrame, column: str, fallback: str = "") -> str:
    if frame.empty or column not in frame.columns:
        return fallback
    for value in frame[column].tolist():
        text = _text_value(value)
        if text:
            return text
    return fallback


def _warnings_present(tear_sheet: pd.DataFrame) -> bool:
    if tear_sheet.empty or not {"key", "value"}.issubset(tear_sheet.columns):
        return False
    keyed = {
        _text_value(row.get("key", "")): _text_value(row.get("value", ""))
        for row in tear_sheet.to_dict("records")
    }
    if _bool_value(keyed.get("warnings_present", False)):
        return True
    return bool(_split_values(keyed.get("warning_symbols", "")))


def _template_keys(frame: pd.DataFrame) -> set[tuple[str, str]]:
    if frame.empty or not {"canonical_candidate_id", "asset"}.issubset(frame.columns):
        return set()
    keys = frame[["canonical_candidate_id", "asset"]].fillna("").astype(str)
    return set(keys.itertuples(index=False, name=None))


def _template_lookup(template: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    if template.empty:
        return {}
    return {
        (_text_value(row.get("canonical_candidate_id", "")), _text_value(row.get("asset", ""))): row
        for row in template.to_dict("records")
    }


def _role_is_reference(row: dict[str, Any]) -> bool:
    role = _text_value(row.get("candidate_role", "")).lower()
    caveats = _text_value(row.get("candidate_caveats", "")).lower()
    return "reference_only" in role or "reference-only" in caveats


def _role_is_inception_limited(row: dict[str, Any]) -> bool:
    role = _text_value(row.get("candidate_role", "")).lower()
    caveats = _text_value(row.get("candidate_caveats", "")).lower()
    return "inception_limited" in role or "inception limited" in caveats or "inception-limited" in caveats


def _validate_required_sources(
    *,
    adoption_validation: pd.DataFrame,
    active_status: pd.DataFrame,
    template: pd.DataFrame,
    require_adoption_valid: bool,
) -> list[str]:
    blockers: list[str] = []
    if adoption_validation.empty:
        blockers.append("adoption_validation_missing")
    elif require_adoption_valid and not _bool_value(
        adoption_validation.iloc[0].get("adoption_valid", False)
    ):
        blockers.append("adoption_not_valid")
    if active_status.empty:
        blockers.append("active_tracking_status_missing")
    elif require_adoption_valid and not _bool_value(
        active_status.iloc[0].get("active_regime_informed_tracking", False)
    ):
        blockers.append("regime_informed_tracking_not_active")
    if template.empty:
        blockers.append("regime_informed_manual_session_template_missing")
    return blockers


def validate_regime_informed_filled_session(
    *,
    filled_session: pd.DataFrame,
    template: pd.DataFrame,
    warnings_present: bool,
    require_tear_sheet_review: bool = True,
    require_warning_acknowledgement: bool = True,
    require_btc_ack_when_btc_weight_positive: bool = True,
    require_reference_ack_for_reference_only: bool = True,
    require_inception_ack_for_inception_limited: bool = True,
    require_reason_for_skipped_or_blocked: bool = True,
) -> pd.DataFrame:
    missing_columns = [
        column for column in FILLED_REQUIRED_COLUMNS if column not in filled_session.columns
    ]
    if missing_columns:
        return pd.DataFrame(
            [
                {
                    "row_id": 0,
                    "session_date": _first_available(template, "session_date"),
                    "selected_signal_date": _first_available(template, "selected_signal_date"),
                    "canonical_candidate_id": "",
                    "candidate_role": "",
                    "asset": "",
                    "target_weight": np.nan,
                    "manual_decision": "",
                    "manual_execution_status": "",
                    "row_valid": False,
                    "row_blocking_reasons": "missing_required_columns:" + ",".join(missing_columns),
                    "requires_btc_ack": False,
                    "requires_reference_ack": False,
                    "requires_inception_ack": False,
                    "requires_warning_ack": warnings_present,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                    "promotion_allowed": False,
                    "target_notional_usd": np.nan,
                    "paper_fill_price": np.nan,
                    "paper_fill_quantity": np.nan,
                    "actual_notional_usd": np.nan,
                    "deviation_from_preview_usd": np.nan,
                    "deviation_from_preview_pct": np.nan,
                }
            ],
            columns=ROW_VALIDATION_COLUMNS,
        )

    template_lookup = _template_lookup(template)
    expected_keys = set(template_lookup)
    received_keys = _template_keys(filled_session)
    missing_expected_keys = expected_keys - received_keys
    unexpected_keys = received_keys - expected_keys if expected_keys else set()
    duplicate_keys = bool(
        filled_session.duplicated(["canonical_candidate_id", "asset"]).any()
        if {"canonical_candidate_id", "asset"}.issubset(filled_session.columns)
        else False
    )

    rows: list[dict[str, Any]] = []
    for row_id, row in enumerate(filled_session.to_dict("records"), start=1):
        blockers: list[str] = []
        candidate_id = _text_value(row.get("canonical_candidate_id", ""))
        asset = _text_value(row.get("asset", ""))
        template_row = template_lookup.get((candidate_id, asset), {})
        candidate_role = _text_value(
            row.get("candidate_role", template_row.get("candidate_role", ""))
        )
        target_weight = _numeric(row.get("target_weight", template_row.get("target_weight", np.nan)))
        target_notional = _numeric(
            row.get("target_notional_usd", template_row.get("target_notional_usd", np.nan))
        )
        decision = _text_value(row.get("manual_decision", "")).lower()
        status = _text_value(row.get("manual_execution_status", "")).lower()
        fill_price = _numeric(row.get("paper_fill_price", np.nan))
        fill_qty = _numeric(row.get("paper_fill_quantity", np.nan))
        actual_notional = np.nan
        deviation_usd = np.nan
        deviation_pct = np.nan
        requires_btc_ack = bool(asset == "BTC-USD" and target_weight > 0)
        merged_role_row = {**template_row, **row, "candidate_role": candidate_role}
        requires_reference_ack = _role_is_reference(merged_role_row)
        requires_inception_ack = _role_is_inception_limited(merged_role_row)
        requires_warning_ack = warnings_present

        if expected_keys and (candidate_id, asset) not in expected_keys:
            blockers.append("filled_row_not_found_in_template")
        if unexpected_keys:
            blockers.append("filled_session_has_unexpected_candidate_asset_rows")
        if missing_expected_keys:
            blockers.append("filled_session_missing_expected_template_rows")
        if duplicate_keys:
            blockers.append("duplicate_filled_candidate_asset_rows")
        if len(filled_session) != len(template):
            blockers.append("filled_row_count_does_not_match_template")

        if require_tear_sheet_review and not _bool_value(row.get("tear_sheet_reviewed", False)):
            blockers.append("tear_sheet_review_missing")
        if (
            require_warning_acknowledgement
            and requires_warning_ack
            and not _bool_value(row.get("warnings_acknowledged", False))
        ):
            blockers.append("warning_acknowledgement_missing")
        if (
            require_btc_ack_when_btc_weight_positive
            and requires_btc_ack
            and not _bool_value(row.get("btc_caveat_acknowledged", False))
        ):
            blockers.append("btc_caveat_acknowledgement_missing")
        if (
            require_reference_ack_for_reference_only
            and requires_reference_ack
            and not _bool_value(row.get("reference_only_acknowledged", False))
        ):
            blockers.append("reference_only_acknowledgement_missing")
        if (
            require_inception_ack_for_inception_limited
            and requires_inception_ack
            and not _bool_value(row.get("inception_limited_acknowledged", False))
        ):
            blockers.append("inception_limited_acknowledgement_missing")

        if not decision or decision == "pending":
            blockers.append("manual_decision_pending")
        elif decision not in ALLOWED_MANUAL_DECISIONS:
            blockers.append("manual_decision_invalid")
        if not status or status == "not_entered":
            blockers.append("manual_execution_status_pending")
        elif status not in ALLOWED_EXECUTION_STATUSES:
            blockers.append("manual_execution_status_invalid")
        if status == "entered":
            if asset == "CASH":
                blockers.append("cash_row_must_use_cash_residual_status")
            if not np.isfinite(fill_price) or fill_price <= 0:
                blockers.append("paper_fill_price_missing_or_non_positive")
            if not np.isfinite(fill_qty) or fill_qty <= 0:
                blockers.append("paper_fill_quantity_missing_or_non_positive")
            if np.isfinite(fill_price) and np.isfinite(fill_qty):
                actual_notional = round(fill_price * fill_qty, 2)
                if np.isfinite(target_notional):
                    deviation_usd = round(actual_notional - target_notional, 2)
                    if abs(target_notional) > 1e-12:
                        deviation_pct = round(deviation_usd / target_notional * 100.0, 4)
        if status == "cash_residual":
            if asset != "CASH":
                blockers.append("cash_residual_status_requires_cash_asset")
            actual_notional = round(target_notional, 2) if np.isfinite(target_notional) else 0.0
            deviation_usd = 0.0
            deviation_pct = 0.0
        if status in {"skipped", "blocked"} and require_reason_for_skipped_or_blocked:
            reason = _text_value(row.get("override_reason", ""))
            notes = _text_value(row.get("notes", ""))
            if not reason and not notes:
                blockers.append("skip_or_block_reason_or_notes_missing")
        if _bool_value(row.get("live_trading_allowed", False)):
            blockers.append("live_trading_flag_true")
        if _bool_value(row.get("real_money_allowed", False)):
            blockers.append("real_money_flag_true")
        if _bool_value(row.get("broker_api_integration_allowed", False)):
            blockers.append("broker_api_flag_true")
        if _bool_value(row.get("promotion_allowed", False)):
            blockers.append("promotion_flag_true")

        rows.append(
            {
                "row_id": row_id,
                "session_date": _text_value(row.get("session_date", "")),
                "selected_signal_date": _text_value(row.get("selected_signal_date", "")),
                "canonical_candidate_id": candidate_id,
                "candidate_role": candidate_role,
                "asset": asset,
                "target_weight": target_weight,
                "manual_decision": decision,
                "manual_execution_status": status,
                "row_valid": len(blockers) == 0,
                "row_blocking_reasons": ";".join(blockers),
                "requires_btc_ack": requires_btc_ack,
                "requires_reference_ack": requires_reference_ack,
                "requires_inception_ack": requires_inception_ack,
                "requires_warning_ack": requires_warning_ack,
                "live_trading_allowed": _bool_value(row.get("live_trading_allowed", False)),
                "real_money_allowed": _bool_value(row.get("real_money_allowed", False)),
                "broker_api_integration_allowed": _bool_value(
                    row.get("broker_api_integration_allowed", False)
                ),
                "promotion_allowed": _bool_value(row.get("promotion_allowed", False)),
                "target_notional_usd": target_notional,
                "paper_fill_price": fill_price,
                "paper_fill_quantity": fill_qty,
                "actual_notional_usd": actual_notional,
                "deviation_from_preview_usd": deviation_usd,
                "deviation_from_preview_pct": deviation_pct,
            }
        )
    return pd.DataFrame(rows, columns=ROW_VALIDATION_COLUMNS)


def build_session_validation_summary(
    *,
    template: pd.DataFrame,
    filled_session: pd.DataFrame,
    row_validation: pd.DataFrame,
    filled_file_present: bool,
    source_blockers: list[str],
) -> pd.DataFrame:
    rows_expected = len(template)
    rows_received = len(filled_session) if filled_file_present else 0
    rows_valid = (
        int(row_validation["row_valid"].map(_bool_value).sum())
        if not row_validation.empty and "row_valid" in row_validation.columns
        else 0
    )
    rows_invalid = rows_received - rows_valid if filled_file_present else 0
    blockers = [*source_blockers]
    if "row_blocking_reasons" in row_validation.columns:
        for value in row_validation["row_blocking_reasons"].tolist():
            blockers.extend(_split_values(value))
    session_valid = filled_file_present and rows_received > 0 and rows_invalid == 0 and not source_blockers
    if not filled_file_present and not source_blockers:
        status = "pending_user_entries"
    elif session_valid:
        status = "valid_manual_paper_session"
    elif source_blockers and not filled_file_present:
        status = "missing_adoption_or_template"
    else:
        status = "invalid_manual_review_required"
    session_date = _first_available(filled_session, "session_date") or _first_available(
        template,
        "session_date",
        _today(),
    )
    selected_signal_date = _first_available(
        filled_session,
        "selected_signal_date",
    ) or _first_available(template, "selected_signal_date")
    return pd.DataFrame(
        [
            {
                "session_date": session_date,
                "selected_signal_date": selected_signal_date,
                "filled_file_present": filled_file_present,
                "session_valid": session_valid,
                "rows_expected": rows_expected,
                "rows_received": rows_received,
                "rows_valid": rows_valid,
                "rows_invalid": rows_invalid,
                "validation_status": status,
                "blocking_reasons": _join_values(blockers),
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ],
        columns=VALIDATION_COLUMNS,
    )


def _ledger_from_filled(
    *,
    filled_session: pd.DataFrame,
    row_validation: pd.DataFrame,
) -> pd.DataFrame:
    if filled_session.empty:
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    computed = row_validation[
        [
            "canonical_candidate_id",
            "asset",
            "actual_notional_usd",
            "deviation_from_preview_usd",
            "deviation_from_preview_pct",
        ]
    ].copy()
    ledger = filled_session.merge(
        computed,
        on=["canonical_candidate_id", "asset"],
        how="left",
        suffixes=("", "_computed"),
    )
    for column in [
        "actual_notional_usd",
        "deviation_from_preview_usd",
        "deviation_from_preview_pct",
    ]:
        computed_col = f"{column}_computed"
        if computed_col in ledger.columns:
            ledger[column] = ledger[computed_col]
            ledger = ledger.drop(columns=[computed_col])
    for column in LEDGER_COLUMNS:
        if column not in ledger.columns:
            ledger[column] = ""
    return ledger[LEDGER_COLUMNS].copy()


def update_regime_informed_session_ledger(
    *,
    ledger_path: Path,
    filled_session: pd.DataFrame,
    row_validation: pd.DataFrame,
    session_valid: bool,
) -> tuple[pd.DataFrame, int]:
    existing = _read_csv(ledger_path)
    if existing.empty:
        existing = pd.DataFrame(columns=LEDGER_COLUMNS)
    else:
        for column in LEDGER_COLUMNS:
            if column not in existing.columns:
                existing[column] = ""
        existing = existing[LEDGER_COLUMNS].copy()
    before = len(existing)
    if session_valid:
        new_rows = _ledger_from_filled(
            filled_session=filled_session,
            row_validation=row_validation,
        )
        ledger = pd.concat([existing, new_rows], ignore_index=True)
        ledger = ledger.drop_duplicates(subset=LEDGER_KEY_COLUMNS, keep="last")
        ledger = ledger[LEDGER_COLUMNS].copy()
    else:
        ledger = existing
    _write_csv(ledger, ledger_path)
    changed = max(len(ledger) - before, 0)
    return ledger, changed


def build_regime_informed_discipline_summary(
    *,
    ledger: pd.DataFrame,
    validation_summary: pd.DataFrame,
    filled_session: pd.DataFrame,
) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame(
            [
                {
                    "total_sessions": 0,
                    "valid_sessions": 0,
                    "entered_sessions": 0,
                    "skipped_sessions": 0,
                    "blocked_sessions": 0,
                    "latest_session_date": validation_summary.iloc[0].get("session_date", "")
                    if not validation_summary.empty
                    else "",
                    "latest_session_valid": False,
                    "latest_manual_decisions": "",
                    "latest_execution_statuses": "",
                    "reference_only_acknowledged": False,
                    "btc_caveat_acknowledged": False,
                    "inception_limited_acknowledged": False,
                    "warnings_acknowledged": False,
                    "discipline_status": "pending_user_entries",
                    "discipline_blocking_reasons": validation_summary.iloc[0].get(
                        "blocking_reasons",
                        "",
                    )
                    if not validation_summary.empty
                    else "",
                }
            ],
            columns=DISCIPLINE_COLUMNS,
        )
    grouped = ledger.groupby(["session_date", "selected_signal_date"], dropna=False)
    total_sessions = len(grouped)
    sessions = []
    for (session_date, selected_signal_date), rows in grouped:
        statuses = rows["manual_execution_status"].astype(str).str.lower()
        sessions.append(
            {
                "session_date": _text_value(session_date),
                "selected_signal_date": _text_value(selected_signal_date),
                "entered": bool(statuses.eq("entered").any()),
                "skipped": bool(statuses.eq("skipped").any()),
                "blocked": bool(statuses.eq("blocked").any()),
            }
        )
    latest = sorted(sessions, key=lambda row: (row["session_date"], row["selected_signal_date"]))[-1]
    latest_rows = ledger[
        (ledger["session_date"].astype(str) == latest["session_date"])
        & (ledger["selected_signal_date"].astype(str) == latest["selected_signal_date"])
    ]
    session_valid = (
        _bool_value(validation_summary.iloc[0].get("session_valid", False))
        if not validation_summary.empty
        else False
    )
    ack_source = filled_session if session_valid and not filled_session.empty else latest_rows
    def ack_all(column: str) -> bool:
        return bool(column in ack_source.columns and ack_source[column].map(_bool_value).all())

    return pd.DataFrame(
        [
            {
                "total_sessions": total_sessions,
                "valid_sessions": total_sessions,
                "entered_sessions": sum(1 for row in sessions if row["entered"]),
                "skipped_sessions": sum(1 for row in sessions if row["skipped"]),
                "blocked_sessions": sum(1 for row in sessions if row["blocked"]),
                "latest_session_date": latest["session_date"],
                "latest_session_valid": session_valid,
                "latest_manual_decisions": _unique_join(latest_rows["manual_decision"]),
                "latest_execution_statuses": _unique_join(latest_rows["manual_execution_status"]),
                "reference_only_acknowledged": ack_all("reference_only_acknowledged"),
                "btc_caveat_acknowledged": ack_all("btc_caveat_acknowledged"),
                "inception_limited_acknowledged": ack_all("inception_limited_acknowledged"),
                "warnings_acknowledged": ack_all("warnings_acknowledged"),
                "discipline_status": "valid_manual_paper_discipline_session"
                if session_valid
                else "ledger_available_current_session_pending_or_invalid",
                "discipline_blocking_reasons": validation_summary.iloc[0].get(
                    "blocking_reasons",
                    "",
                )
                if not validation_summary.empty
                else "",
            }
        ],
        columns=DISCIPLINE_COLUMNS,
    )


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def save_phase21e_regime_informed_session_ingestion(
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
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    template_path = output_dir / str(
        section.get("template_filename", "regime_informed_manual_session_template.csv")
    )
    filled_path = output_dir / str(
        section.get("filled_filename", "regime_informed_manual_session_filled.csv")
    )
    ledger_path = output_dir / str(
        section.get("ledger_filename", "regime_informed_manual_session_ledger.csv")
    )
    adoption_validation_path = output_dir / "regime_informed_adoption_validation.csv"
    active_status_path = output_dir / "regime_informed_active_tracking_status.csv"
    tear_sheet_path = output_dir / "regime_informed_daily_tracking_tear_sheet.csv"
    orders_path = output_dir / "regime_informed_paper_orders_preview.csv"

    validation_path = output_dir / "regime_informed_session_validation.csv"
    row_validation_path = output_dir / "regime_informed_session_row_validation.csv"
    discipline_path = output_dir / "regime_informed_session_discipline_summary.csv"
    dashboard_path = dashboard_dir / "regime_informed_session_ingestion_status.csv"
    rollover_status_path = output_dir / "regime_informed_session_rollover_status.csv"

    live = _bool_value(section.get("live_trading_allowed", False))
    real = _bool_value(section.get("real_money_allowed", False))
    broker = _bool_value(section.get("broker_api_integration_allowed", False))
    promotion = _bool_value(section.get("promotion_allowed", False))

    adoption_validation = _read_csv(adoption_validation_path)
    active_status = _read_csv(active_status_path)
    template = _read_csv(template_path)
    tear_sheet = _read_csv(tear_sheet_path)
    orders = _read_csv(orders_path)
    rollover_status = _read_csv(rollover_status_path)
    filled_present = filled_path.exists() and filled_path.is_file()
    filled_session = _read_csv(filled_path) if filled_present else pd.DataFrame()
    source_blockers = _validate_required_sources(
        adoption_validation=adoption_validation,
        active_status=active_status,
        template=template,
        require_adoption_valid=_bool_value(section.get("require_adoption_valid", True)),
    )
    if tear_sheet.empty:
        source_blockers.append("regime_informed_tear_sheet_missing")
    if orders.empty:
        source_blockers.append("regime_informed_order_preview_missing")
    if live:
        source_blockers.append("live_trading_flag_true")
    if real:
        source_blockers.append("real_money_flag_true")
    if broker:
        source_blockers.append("broker_api_flag_true")
    if promotion:
        source_blockers.append("promotion_flag_true")
    if (
        not rollover_status.empty
        and "filled_session_stale" in rollover_status.columns
        and _bool_value(rollover_status.iloc[0].get("filled_session_stale", False))
    ):
        source_blockers.append("stale_filled_file_blocked_by_phase21g")

    warnings_present = _warnings_present(tear_sheet)
    if filled_present and not template.empty:
        row_validation = validate_regime_informed_filled_session(
            filled_session=filled_session,
            template=template,
            warnings_present=warnings_present,
            require_tear_sheet_review=_bool_value(
                section.get("require_tear_sheet_review", True)
            ),
            require_warning_acknowledgement=_bool_value(
                section.get("require_warning_acknowledgement", True)
            ),
            require_btc_ack_when_btc_weight_positive=_bool_value(
                section.get("require_btc_ack_when_btc_weight_positive", True)
            ),
            require_reference_ack_for_reference_only=_bool_value(
                section.get("require_reference_ack_for_reference_only", True)
            ),
            require_inception_ack_for_inception_limited=_bool_value(
                section.get("require_inception_ack_for_inception_limited", True)
            ),
            require_reason_for_skipped_or_blocked=_bool_value(
                section.get("require_reason_for_skipped_or_blocked", True)
            ),
        )
    else:
        row_validation = pd.DataFrame(columns=ROW_VALIDATION_COLUMNS)

    validation_summary = build_session_validation_summary(
        template=template,
        filled_session=filled_session,
        row_validation=row_validation,
        filled_file_present=filled_present,
        source_blockers=source_blockers,
    )
    session_valid = _bool_value(validation_summary.iloc[0].get("session_valid", False))
    ledger, ledger_delta = update_regime_informed_session_ledger(
        ledger_path=ledger_path,
        filled_session=filled_session,
        row_validation=row_validation,
        session_valid=session_valid,
    )
    discipline = build_regime_informed_discipline_summary(
        ledger=ledger,
        validation_summary=validation_summary,
        filled_session=filled_session,
    )

    _write_csv(validation_summary, validation_path)
    _write_csv(row_validation, row_validation_path)
    _write_csv(discipline, discipline_path)

    if source_blockers:
        decision = "regime_informed_session_ingestion_failed_missing_adoption_or_template"
    elif not filled_present:
        decision = "regime_informed_session_ingestion_pending_user_entries"
    elif session_valid:
        decision = "regime_informed_session_ingested_valid_manual_paper_only"
    else:
        decision = "regime_informed_session_ingested_invalid_manual_review_required"

    result = validation_summary.iloc[0]
    discipline_row = discipline.iloc[0] if not discipline.empty else pd.Series(dtype=object)
    dashboard = pd.DataFrame(
        [
            {
                "phase21e_decision": decision,
                "session_date": result.get("session_date", ""),
                "selected_signal_date": result.get("selected_signal_date", ""),
                "filled_file_present": filled_present,
                "session_valid": session_valid,
                "rows_valid": int(result.get("rows_valid", 0) or 0),
                "rows_invalid": int(result.get("rows_invalid", 0) or 0),
                "ledger_written": ledger_path.exists(),
                "ledger_row_count": len(ledger),
                "discipline_status": discipline_row.get("discipline_status", ""),
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": result.get("blocking_reasons", ""),
            }
        ]
    )
    _write_csv(dashboard, dashboard_path)

    gates = pd.DataFrame(
        [
            _gate_row("valid_adoption_exists", "adoption_not_valid" not in source_blockers),
            _gate_row(
                "manual_session_template_exists",
                "regime_informed_manual_session_template_missing" not in source_blockers,
            ),
            _gate_row("validation_file_written", validation_path.exists()),
            _gate_row("row_validation_file_written", row_validation_path.exists()),
            _gate_row("ledger_file_written", ledger_path.exists()),
            _gate_row("discipline_summary_written", discipline_path.exists()),
            _gate_row("dashboard_status_written", dashboard_path.exists()),
            _gate_row("promotion_disabled", not promotion),
            _gate_row("live_trading_disabled", not live),
            _gate_row("real_money_disabled", not real),
            _gate_row("broker_api_integration_disabled", not broker),
        ]
    )
    all_gates_passed = bool(gates["passed"].map(_bool_value).all())
    failed_gates = _join_values(
        gates.loc[~gates["passed"].map(_bool_value), "gate_id"].astype(str).tolist()
    )
    if not all_gates_passed and decision != "regime_informed_session_ingestion_failed_missing_adoption_or_template":
        decision = "regime_informed_session_ingested_invalid_manual_review_required"
        dashboard.loc[0, "phase21e_decision"] = decision
        _write_csv(dashboard, dashboard_path)

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 21E",
                "phase21e_decision": decision,
                "all_gates_passed": all_gates_passed,
                "session_date": result.get("session_date", ""),
                "selected_signal_date": result.get("selected_signal_date", ""),
                "filled_file_present": filled_present,
                "session_valid": session_valid,
                "rows_expected": int(result.get("rows_expected", 0) or 0),
                "rows_received": int(result.get("rows_received", 0) or 0),
                "rows_valid": int(result.get("rows_valid", 0) or 0),
                "rows_invalid": int(result.get("rows_invalid", 0) or 0),
                "ledger_row_count": len(ledger),
                "ledger_rows_appended_or_updated": ledger_delta,
                "discipline_status": discipline_row.get("discipline_status", ""),
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "blocking_reasons": result.get("blocking_reasons", ""),
                "failure_reason": failed_gates,
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 21E",
                "diagnostic": "Regime-informed manual session ingestion and discipline ledger",
                "phase21e_decision": decision,
                "all_gates_passed": all_gates_passed,
                "session_valid": session_valid,
                "filled_file_present": filled_present,
                "ledger_row_count": len(ledger),
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "No orders placed. Valid regime-informed filled sessions update only the regime-informed paper ledger.",
                "failure_reason": failed_gates,
            }
        ]
    )
    _write_csv(summary, output_dir / "phase21e_summary.csv")
    _write_csv(gates, output_dir / "phase21e_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase21e_conclusion.csv")
    print("Wrote Phase 21E regime-informed session ingestion reports.")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "regime_informed_session_validation": validation_summary,
        "regime_informed_session_row_validation": row_validation,
        "regime_informed_manual_session_ledger": ledger,
        "regime_informed_session_discipline_summary": discipline,
        "regime_informed_session_ingestion_dashboard_status": dashboard,
    }
