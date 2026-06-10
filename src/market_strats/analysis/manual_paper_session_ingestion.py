from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PHASE20D_SECTION = "phase20d_manual_paper_session_ingestion"
ALLOWED_FILLED_DECISIONS = {
    "enter_paper_trade",
    "skip_due_warning",
    "skip_due_block",
    "skip_user_choice",
}
ALLOWED_FILLED_STATUSES = {"entered", "skipped", "blocked"}
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
    "manual_decision",
    "manual_execution_status",
    "paper_fill_price",
    "paper_fill_quantity",
    "override_reason",
    "notes",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
]
ROW_VALIDATION_COLUMNS = [
    "session_date",
    "selected_signal_date",
    "canonical_candidate_id",
    "asset",
    "row_valid",
    "row_blocking_reasons",
    "manual_decision",
    "manual_execution_status",
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
    "paper_fill_price",
    "paper_fill_quantity",
    "actual_notional_usd",
    "deviation_from_preview_usd",
    "deviation_from_preview_pct",
    "override_reason",
    "notes",
    "warnings_acknowledged",
    "btc_caveat_acknowledged",
    "tear_sheet_reviewed",
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


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE20D_SECTION, {}) or {}


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
    return ";".join(unique)


def _first_available(frame: pd.DataFrame, column: str, fallback: str = "") -> str:
    if frame.empty or column not in frame.columns:
        return fallback
    value = _text_value(frame.iloc[0].get(column, ""))
    return value or fallback


def _warnings_present(
    *,
    finalist_tracking_status: pd.DataFrame,
    tear_sheet: pd.DataFrame,
) -> bool:
    if not finalist_tracking_status.empty:
        warning_symbols = _text_value(
            finalist_tracking_status.iloc[0].get("warning_symbols", "")
        )
        data_quality_status = _text_value(
            finalist_tracking_status.iloc[0].get("data_quality_status", "")
        )
        if warning_symbols.lower() not in {"", "none", "nan"}:
            return True
        if data_quality_status.lower() == "warning":
            return True
    if not tear_sheet.empty and {"key", "value"}.issubset(tear_sheet.columns):
        rows = tear_sheet.loc[tear_sheet["key"].astype(str) == "warning_symbols", "value"]
        if not rows.empty and _split_values(rows.iloc[0]):
            return True
    return False


def _template_key_set(template: pd.DataFrame) -> set[tuple[str, str]]:
    if template.empty or not {"canonical_candidate_id", "asset"}.issubset(template.columns):
        return set()
    keys = template[["canonical_candidate_id", "asset"]].fillna("").astype(str)
    return set(keys.itertuples(index=False, name=None))


def _has_duplicate_keys(frame: pd.DataFrame) -> bool:
    if frame.empty or not {"canonical_candidate_id", "asset"}.issubset(frame.columns):
        return False
    return bool(frame.duplicated(["canonical_candidate_id", "asset"]).any())


def _status_for_row(row: pd.Series) -> tuple[str, str]:
    decision = _text_value(row.get("manual_decision", "")).lower()
    status = _text_value(row.get("manual_execution_status", "")).lower()
    return decision, status


def validate_filled_manual_session(
    *,
    filled_session: pd.DataFrame,
    template: pd.DataFrame,
    warnings_present: bool,
) -> pd.DataFrame:
    missing_columns = [
        column for column in FILLED_REQUIRED_COLUMNS if column not in filled_session.columns
    ]
    if missing_columns:
        return pd.DataFrame(
            [
                {
                    "session_date": _first_available(template, "session_date"),
                    "selected_signal_date": _first_available(
                        template,
                        "selected_signal_date",
                    ),
                    "canonical_candidate_id": "",
                    "asset": "",
                    "row_valid": False,
                    "row_blocking_reasons": "missing_required_columns:"
                    + ",".join(missing_columns),
                    "manual_decision": "",
                    "manual_execution_status": "",
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

    expected_keys = _template_key_set(template)
    received_keys = _template_key_set(filled_session)
    missing_expected_keys = expected_keys - received_keys
    duplicate_filled_keys = _has_duplicate_keys(filled_session)

    rows: list[dict[str, Any]] = []
    for row in filled_session.reset_index(drop=True).to_dict(orient="records"):
        blockers: list[str] = []
        row_series = pd.Series(row)
        decision, status = _status_for_row(row_series)
        candidate_id = _text_value(row.get("canonical_candidate_id", ""))
        asset = _text_value(row.get("asset", ""))
        target_notional = _numeric(row.get("target_notional_usd", np.nan))
        target_weight = _numeric(row.get("target_weight", 0.0))
        fill_price = _numeric(row.get("paper_fill_price", np.nan))
        fill_qty = _numeric(row.get("paper_fill_quantity", np.nan))
        actual_notional = np.nan
        deviation_usd = np.nan
        deviation_pct = np.nan

        if expected_keys and (candidate_id, asset) not in expected_keys:
            blockers.append("filled_row_not_found_in_template")
        if duplicate_filled_keys:
            blockers.append("duplicate_filled_candidate_asset_rows")
        if missing_expected_keys:
            blockers.append("filled_session_missing_expected_template_rows")

        if not _bool_value(row.get("tear_sheet_reviewed", False)):
            blockers.append("tear_sheet_review_missing")
        if warnings_present and not _bool_value(row.get("warnings_acknowledged", False)):
            blockers.append("warning_acknowledgement_missing")
        if asset == "BTC-USD" and target_weight > 0 and not _bool_value(
            row.get("btc_caveat_acknowledged", False)
        ):
            blockers.append("btc_caveat_acknowledgement_missing")
        if decision == "pending" or not decision:
            blockers.append("manual_decision_pending")
        elif decision not in ALLOWED_FILLED_DECISIONS:
            blockers.append("manual_decision_invalid")
        if status == "not_entered" or not status:
            blockers.append("manual_execution_status_pending")
        elif status not in ALLOWED_FILLED_STATUSES:
            blockers.append("manual_execution_status_invalid")

        if status == "entered":
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
        if status in {"skipped", "blocked"}:
            reason = _text_value(row.get("override_reason", ""))
            notes = _text_value(row.get("notes", ""))
            if not reason and not notes:
                if status == "skipped":
                    blockers.append("skip_reason_or_notes_missing")
                else:
                    blockers.append("block_reason_or_notes_missing")
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
                "session_date": _text_value(row.get("session_date", "")),
                "selected_signal_date": _text_value(row.get("selected_signal_date", "")),
                "canonical_candidate_id": candidate_id,
                "asset": asset,
                "row_valid": len(blockers) == 0,
                "row_blocking_reasons": ";".join(blockers),
                "manual_decision": decision,
                "manual_execution_status": status,
                "target_notional_usd": target_notional,
                "paper_fill_price": fill_price,
                "paper_fill_quantity": fill_qty,
                "actual_notional_usd": actual_notional,
                "deviation_from_preview_usd": deviation_usd,
                "deviation_from_preview_pct": deviation_pct,
            }
        )

    return pd.DataFrame(rows, columns=ROW_VALIDATION_COLUMNS)


def build_ingestion_result(
    *,
    template: pd.DataFrame,
    filled_session: pd.DataFrame,
    row_validation: pd.DataFrame,
    filled_session_file_present: bool,
    blocking_reasons: list[str],
) -> pd.DataFrame:
    rows_expected = len(template)
    rows_received = len(filled_session) if filled_session_file_present else 0
    rows_valid = (
        int(row_validation["row_valid"].map(_bool_value).sum())
        if not row_validation.empty and "row_valid" in row_validation.columns
        else 0
    )
    rows_invalid = rows_received - rows_valid if filled_session_file_present else 0
    row_blockers = (
        row_validation["row_blocking_reasons"].dropna().astype(str).tolist()
        if "row_blocking_reasons" in row_validation.columns
        else []
    )
    all_blockers = [*blocking_reasons]
    for blocker_text in row_blockers:
        all_blockers.extend(_split_values(blocker_text))
    session_valid = filled_session_file_present and rows_received > 0 and rows_invalid == 0
    if not filled_session_file_present:
        status = "pending_user_entries"
    elif session_valid:
        status = "valid_manual_paper_session"
    else:
        status = "invalid_manual_review_required"

    session_date = _first_available(filled_session, "session_date") or _first_available(
        template,
        "session_date",
        _generated_date(),
    )
    selected_signal_date = _first_available(
        filled_session,
        "selected_signal_date",
    ) or _first_available(template, "selected_signal_date")

    warnings_acknowledged = (
        bool(filled_session["warnings_acknowledged"].map(_bool_value).all())
        if filled_session_file_present and "warnings_acknowledged" in filled_session.columns
        else False
    )
    btc_rows = (
        filled_session[
            (filled_session["asset"].astype(str) == "BTC-USD")
            & (pd.to_numeric(filled_session["target_weight"], errors="coerce").fillna(0) > 0)
        ]
        if filled_session_file_present
        and {"asset", "target_weight"}.issubset(filled_session.columns)
        else pd.DataFrame()
    )
    btc_acknowledged = (
        bool(btc_rows["btc_caveat_acknowledged"].map(_bool_value).all())
        if not btc_rows.empty and "btc_caveat_acknowledged" in btc_rows.columns
        else bool(btc_rows.empty)
    )
    manual_decisions_complete = (
        bool(
            filled_session["manual_decision"]
            .astype(str)
            .str.lower()
            .isin(ALLOWED_FILLED_DECISIONS)
            .all()
        )
        if filled_session_file_present and "manual_decision" in filled_session.columns
        else False
    )
    entered_rows = (
        filled_session[
            filled_session["manual_execution_status"].astype(str).str.lower() == "entered"
        ]
        if filled_session_file_present
        and "manual_execution_status" in filled_session.columns
        else pd.DataFrame()
    )
    fills_complete = True
    if not entered_rows.empty:
        prices = pd.to_numeric(entered_rows["paper_fill_price"], errors="coerce")
        quantities = pd.to_numeric(entered_rows["paper_fill_quantity"], errors="coerce")
        fills_complete = bool(prices.gt(0).all() and quantities.gt(0).all())
    safety_flags_valid = True
    for column in [
        "live_trading_allowed",
        "real_money_allowed",
        "broker_api_integration_allowed",
    ]:
        if filled_session_file_present and column in filled_session.columns:
            safety_flags_valid = safety_flags_valid and not bool(
                filled_session[column].map(_bool_value).any()
            )

    return pd.DataFrame(
        [
            {
                "session_date": session_date,
                "selected_signal_date": selected_signal_date,
                "filled_session_file_present": filled_session_file_present,
                "session_ingestion_status": status,
                "session_valid": session_valid,
                "rows_expected": rows_expected,
                "rows_received": rows_received,
                "rows_valid": rows_valid,
                "rows_invalid": rows_invalid,
                "warnings_acknowledged": warnings_acknowledged,
                "btc_acknowledged": btc_acknowledged,
                "manual_decisions_complete": manual_decisions_complete,
                "fills_complete_if_entered": fills_complete,
                "safety_flags_valid": safety_flags_valid,
                "blocking_reasons": _join_values(all_blockers),
            }
        ]
    )


def _normalise_ledger_rows(
    *,
    filled_session: pd.DataFrame,
    row_validation: pd.DataFrame,
) -> pd.DataFrame:
    if filled_session.empty or row_validation.empty:
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
        computed_column = f"{column}_computed"
        if computed_column in ledger.columns:
            ledger[column] = ledger[computed_column]
            ledger = ledger.drop(columns=[computed_column])
    for column in LEDGER_COLUMNS:
        if column not in ledger.columns:
            ledger[column] = ""
    return ledger[LEDGER_COLUMNS].copy()


def update_manual_session_ledger(
    *,
    ledger_path: Path,
    filled_session: pd.DataFrame,
    row_validation: pd.DataFrame,
    session_valid: bool,
) -> pd.DataFrame:
    existing = _read_csv(ledger_path)
    if existing.empty:
        existing = pd.DataFrame(columns=LEDGER_COLUMNS)
    else:
        for column in LEDGER_COLUMNS:
            if column not in existing.columns:
                existing[column] = ""
        existing = existing[LEDGER_COLUMNS].copy()

    if session_valid:
        new_rows = _normalise_ledger_rows(
            filled_session=filled_session,
            row_validation=row_validation,
        )
        combined = pd.concat([existing, new_rows], ignore_index=True)
        combined = combined.drop_duplicates(subset=LEDGER_KEY_COLUMNS, keep="last")
        ledger = combined[LEDGER_COLUMNS].copy()
    else:
        ledger = existing

    _write_csv(ledger, ledger_path)
    return ledger


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def save_phase20d_manual_paper_session_ingestion(
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
    source_finalist_tracking_dir = _resolve_path(
        section.get("source_finalist_tracking_dir"),
        reports_path / "paper_trading" / "finalist_tracking",
    )
    filled_filename = str(section.get("filled_session_filename", "manual_paper_session_filled.csv"))
    ledger_filename = str(section.get("ledger_filename", "manual_paper_session_ledger.csv"))
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    template_path = source_manual_session_dir / "manual_paper_session_template.csv"
    filled_path = source_manual_session_dir / filled_filename
    orders_path = source_finalist_tracking_dir / "finalist_paper_orders_preview.csv"
    tear_sheet_path = source_finalist_tracking_dir / "finalist_daily_tracking_tear_sheet.csv"
    tracking_status_path = dashboard_dir / "finalist_tracking_status.csv"
    ledger_path = output_dir / ledger_filename
    result_path = output_dir / "manual_paper_session_ingestion_result.csv"
    row_validation_path = output_dir / "manual_paper_session_row_validation.csv"
    dashboard_path = dashboard_dir / "manual_paper_session_ingestion_status.csv"

    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )

    template = _read_csv(template_path)
    orders = _read_csv(orders_path)
    tear_sheet = _read_csv(tear_sheet_path)
    finalist_tracking_status = _read_csv(tracking_status_path)
    filled_present = filled_path.exists() and filled_path.is_file()
    filled_session = _read_csv(filled_path) if filled_present else pd.DataFrame()
    warnings_present = _warnings_present(
        finalist_tracking_status=finalist_tracking_status,
        tear_sheet=tear_sheet,
    )

    blocking_reasons: list[str] = []
    if not template_path.exists() or template.empty:
        blocking_reasons.append("phase20c_template_missing")
    if not orders_path.exists() or orders.empty:
        blocking_reasons.append("phase20a_order_preview_missing")
    if not tear_sheet_path.exists() or tear_sheet.empty:
        blocking_reasons.append("phase20a_tear_sheet_missing")
    if not tracking_status_path.exists() or finalist_tracking_status.empty:
        blocking_reasons.append("phase20a_dashboard_status_missing")
    if live_trading_allowed:
        blocking_reasons.append("live_trading_flag_true")
    if real_money_allowed:
        blocking_reasons.append("real_money_flag_true")
    if broker_api_integration_allowed:
        blocking_reasons.append("broker_api_flag_true")

    if filled_present and not template.empty:
        row_validation = validate_filled_manual_session(
            filled_session=filled_session,
            template=template,
            warnings_present=warnings_present,
        )
    else:
        row_validation = pd.DataFrame(columns=ROW_VALIDATION_COLUMNS)

    ingestion_result = build_ingestion_result(
        template=template,
        filled_session=filled_session,
        row_validation=row_validation,
        filled_session_file_present=filled_present,
        blocking_reasons=blocking_reasons,
    )
    if blocking_reasons:
        ingestion_result.loc[0, "session_valid"] = False
        if not filled_present:
            ingestion_result.loc[0, "session_ingestion_status"] = "pending_user_entries"
        else:
            ingestion_result.loc[0, "session_ingestion_status"] = (
                "invalid_manual_review_required"
            )
    session_valid = _bool_value(ingestion_result.iloc[0].get("session_valid", False))
    ledger = update_manual_session_ledger(
        ledger_path=ledger_path,
        filled_session=filled_session,
        row_validation=row_validation,
        session_valid=session_valid,
    )

    _write_csv(ingestion_result, result_path)
    _write_csv(row_validation, row_validation_path)

    if not filled_present:
        decision = "manual_paper_session_ingestion_pending_user_entries"
    elif session_valid:
        decision = "manual_paper_session_ingested_valid_manual_paper_only"
    else:
        decision = "manual_paper_session_ingested_invalid_manual_review_required"

    gates = pd.DataFrame(
        [
            _gate_row("phase20c_template_exists", template_path.exists() and not template.empty),
            _gate_row("ingestion_result_written", result_path.exists() and not ingestion_result.empty),
            _gate_row("row_validation_written", row_validation_path.exists()),
            _gate_row("ledger_written", ledger_path.exists()),
            _gate_row("dashboard_status_written", True),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row("broker_api_integration_disabled", not broker_api_integration_allowed),
        ]
    )
    all_gates_passed = bool(gates["passed"].all())
    failed_gates = _join_values(gates.loc[~gates["passed"], "gate_id"].astype(str).tolist())
    if not all_gates_passed and filled_present:
        decision = "manual_paper_session_ingested_invalid_manual_review_required"
    elif not all_gates_passed:
        decision = "manual_paper_session_ingestion_failed_closed"

    result_row = ingestion_result.iloc[0]
    dashboard = pd.DataFrame(
        [
            {
                "phase20d_decision": decision,
                "session_date": result_row.get("session_date", ""),
                "selected_signal_date": result_row.get("selected_signal_date", ""),
                "filled_session_file_present": filled_present,
                "session_valid": session_valid,
                "rows_valid": int(result_row.get("rows_valid", 0) or 0),
                "rows_invalid": int(result_row.get("rows_invalid", 0) or 0),
                "ledger_written": ledger_path.exists(),
                "ledger_row_count": len(ledger),
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": (
                    "filled session pending"
                    if not filled_present
                    else "manual paper session valid"
                    if session_valid
                    else "manual review required"
                ),
            }
        ]
    )
    _write_csv(dashboard, dashboard_path)
    gates.loc[gates["gate_id"] == "dashboard_status_written", "passed"] = dashboard_path.exists()
    gates.loc[gates["gate_id"] == "dashboard_status_written", "result"] = (
        "Passed" if dashboard_path.exists() else "Failed"
    )
    all_gates_passed = bool(gates["passed"].map(_bool_value).all())
    failed_gates = _join_values(gates.loc[~gates["passed"].map(_bool_value), "gate_id"].astype(str).tolist())

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 20D",
                "phase20d_decision": decision,
                "all_gates_passed": all_gates_passed,
                "session_date": result_row.get("session_date", ""),
                "selected_signal_date": result_row.get("selected_signal_date", ""),
                "filled_session_file_present": filled_present,
                "session_ingestion_status": result_row.get("session_ingestion_status", ""),
                "session_valid": session_valid,
                "rows_expected": int(result_row.get("rows_expected", 0) or 0),
                "rows_received": int(result_row.get("rows_received", 0) or 0),
                "rows_valid": int(result_row.get("rows_valid", 0) or 0),
                "rows_invalid": int(result_row.get("rows_invalid", 0) or 0),
                "ledger_row_count": len(ledger),
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
                "blocking_reasons": result_row.get("blocking_reasons", ""),
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 20D",
                "diagnostic": "Filled manual paper session ingestion and ledger update",
                "phase20d_decision": decision,
                "all_gates_passed": all_gates_passed,
                "session_valid": session_valid,
                "filled_session_file_present": filled_present,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": (
                    "No orders placed. Valid filled sessions update the durable "
                    "manual paper ledger only."
                ),
                "failure_reason": failed_gates,
            }
        ]
    )

    _write_csv(summary, output_dir / "phase20d_summary.csv")
    _write_csv(gates, output_dir / "phase20d_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase20d_conclusion.csv")
    print("Wrote Phase 20D manual paper session ingestion reports.")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "manual_paper_session_ingestion_result": ingestion_result,
        "manual_paper_session_row_validation": row_validation,
        "manual_paper_session_ledger": ledger,
        "manual_paper_session_ingestion_dashboard_status": dashboard,
    }
