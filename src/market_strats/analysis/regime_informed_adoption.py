from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PHASE21D_SECTION = "phase21d_regime_informed_adoption"
ALLOWED_ADOPTION_DECISIONS = {
    "adopt_regime_informed_shortlist",
    "decline_keep_phase20_shortlist",
    "adopt_for_research_only_no_manual_tracking",
    "pending",
}
ACK_COLUMNS = [
    "acknowledge_no_live_trading",
    "acknowledge_no_real_money",
    "acknowledge_no_broker_api",
    "acknowledge_no_strategy_promotion",
    "acknowledge_reference_only_candidate",
    "acknowledge_btc_high_caveat",
    "acknowledge_severe_drawdown_caveat",
    "acknowledge_inception_limited_candidates",
    "reviewed_regime_informed_tear_sheet",
    "reviewed_phase21b_reconciliation",
]
ADOPTION_REQUIRED_COLUMNS = [
    "decision_date",
    "selected_signal_date",
    "regime_informed_shortlist_version",
    "candidate_count",
    "adoption_decision",
    "adoption_reason",
    *ACK_COLUMNS,
    "notes",
]
SESSION_COLUMNS = [
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
    "reference_only_acknowledged",
    "inception_limited_acknowledged",
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
    "promotion_allowed",
]


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


def _today() -> str:
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
    return config.get(PHASE21D_SECTION, {}) or {}


def _source_paths(section: dict[str, Any], reports_dir: Path) -> dict[str, Path]:
    tracking_dir = Path(
        section.get(
            "source_regime_informed_tracking_dir",
            reports_dir / "paper_trading" / "regime_informed_tracking",
        )
    )
    dashboard_dir = Path(
        section.get("dashboard_dir", reports_dir / "paper_trading" / "dashboard")
    )
    return {
        "targets": tracking_dir / "regime_informed_paper_targets.csv",
        "orders": tracking_dir / "regime_informed_paper_orders_preview.csv",
        "tear_sheet": tracking_dir / "regime_informed_daily_tracking_tear_sheet.csv",
        "adoption_status": tracking_dir / "regime_informed_tracking_adoption_status.csv",
        "dashboard_status": dashboard_dir / "regime_informed_tracking_status.csv",
    }


def _load_sources(paths: dict[str, Path]) -> tuple[dict[str, pd.DataFrame], list[str]]:
    frames = {name: _read_csv(path) for name, path in paths.items()}
    missing = [name for name, frame in frames.items() if frame.empty]
    return frames, missing


def _selected_signal_date(targets: pd.DataFrame, adoption_status: pd.DataFrame) -> str:
    if not targets.empty and "selected_signal_date" in targets.columns:
        value = _text_value(targets["selected_signal_date"].iloc[0])
        if value:
            return value
    if not adoption_status.empty and "selected_signal_date" in adoption_status.columns:
        return _text_value(adoption_status["selected_signal_date"].iloc[0])
    return ""


def build_adoption_decision_template(
    *,
    targets: pd.DataFrame,
    adoption_status: pd.DataFrame,
) -> pd.DataFrame:
    candidate_count = int(targets["canonical_candidate_id"].nunique()) if not targets.empty else 0
    return pd.DataFrame(
        [
            {
                "decision_date": _today(),
                "selected_signal_date": _selected_signal_date(targets, adoption_status),
                "regime_informed_shortlist_version": "phase21c_regime_informed_shortlist_v1",
                "candidate_count": candidate_count,
                "adoption_decision": "pending",
                "adoption_reason": "",
                "acknowledge_no_live_trading": False,
                "acknowledge_no_real_money": False,
                "acknowledge_no_broker_api": False,
                "acknowledge_no_strategy_promotion": False,
                "acknowledge_reference_only_candidate": False,
                "acknowledge_btc_high_caveat": False,
                "acknowledge_severe_drawdown_caveat": False,
                "acknowledge_inception_limited_candidates": False,
                "reviewed_regime_informed_tear_sheet": False,
                "reviewed_phase21b_reconciliation": False,
                "notes": "",
            }
        ],
        columns=ADOPTION_REQUIRED_COLUMNS,
    )


def validate_adoption_decision(
    *,
    decision_path: Path,
    targets: pd.DataFrame,
    adoption_status: pd.DataFrame,
    require_adoption_reason: bool,
    require_manual_adoption: bool,
) -> pd.DataFrame:
    selected_signal_date = _selected_signal_date(targets, adoption_status)
    base = {
        "decision_date": _today(),
        "selected_signal_date": selected_signal_date,
        "decision_file_present": decision_path.exists(),
        "adoption_decision": "pending",
        "adoption_valid": False,
        "adoption_status": "pending_manual_adoption",
        "blocking_reasons": "adoption_decision_file_missing",
        "requires_manual_adoption": bool(require_manual_adoption),
        "phase20_outputs_modified": False,
        "promotion_allowed": False,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
    }
    if not decision_path.exists():
        return pd.DataFrame([base])

    decision = _read_csv(decision_path)
    blocking: list[str] = []
    if decision.empty:
        blocking.append("adoption_decision_file_empty")
        row = {}
    else:
        row = decision.iloc[0].to_dict()
    missing_cols = [col for col in ADOPTION_REQUIRED_COLUMNS if col not in decision.columns]
    if missing_cols:
        blocking.append(f"missing_required_columns:{','.join(missing_cols)}")
    if len(decision) != 1:
        blocking.append("decision_file_must_have_exactly_one_row")

    adoption_decision = _text_value(row.get("adoption_decision", "pending"))
    if adoption_decision not in ALLOWED_ADOPTION_DECISIONS:
        blocking.append("invalid_adoption_decision")
    if adoption_decision == "pending":
        blocking.append("adoption_decision_pending")
    if require_adoption_reason and not _text_value(row.get("adoption_reason", "")):
        blocking.append("adoption_reason_required")
    for col in ACK_COLUMNS:
        if not _bool_value(row.get(col, False)):
            blocking.append(f"{col}_required")

    valid = not blocking
    if valid and adoption_decision == "adopt_regime_informed_shortlist":
        status = "regime_informed_shortlist_adopted_manual_paper_only"
    elif valid and adoption_decision == "decline_keep_phase20_shortlist":
        status = "declined_keep_existing_phase20_tracking"
    elif valid and adoption_decision == "adopt_for_research_only_no_manual_tracking":
        status = "adopted_for_research_only_no_manual_tracking"
    else:
        status = "invalid_manual_review_required"

    return pd.DataFrame(
        [
            {
                **base,
                "decision_date": _text_value(row.get("decision_date", _today())) or _today(),
                "selected_signal_date": _text_value(
                    row.get("selected_signal_date", selected_signal_date)
                )
                or selected_signal_date,
                "decision_file_present": True,
                "adoption_decision": adoption_decision,
                "adoption_valid": valid,
                "adoption_status": status,
                "blocking_reasons": ";".join(blocking),
            }
        ]
    )


def build_manual_session_template(
    *,
    orders: pd.DataFrame,
    selected_signal_date: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in orders.to_dict("records"):
        rows.append(
            {
                "session_date": _today(),
                "selected_signal_date": selected_signal_date,
                "canonical_candidate_id": row.get("canonical_candidate_id"),
                "candidate_role": row.get("candidate_role"),
                "asset": row.get("asset"),
                "target_weight": row.get("target_weight"),
                "target_notional_usd": row.get("target_notional_usd"),
                "preview_action": row.get("preview_action"),
                "paper_order_allowed": row.get("paper_order_allowed"),
                "candidate_caveats": row.get("candidate_caveats"),
                "tear_sheet_reviewed": False,
                "warnings_acknowledged": False,
                "btc_caveat_acknowledged": False,
                "reference_only_acknowledged": False,
                "inception_limited_acknowledged": False,
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
                "promotion_allowed": False,
            }
        )
    return pd.DataFrame(rows, columns=SESSION_COLUMNS)


def _write_checklist(path: Path) -> Path:
    lines = [
        "# Phase 21D Regime-Informed Manual Session Checklist",
        "",
        "NO LIVE TRADING",
        "NO REAL MONEY",
        "NO BROKER/API",
        "NO STRATEGY PROMOTION",
        "MANUAL PAPER ONLY",
        "REGIME-INFORMED SHORTLIST ADOPTED ONLY AFTER MANUAL REVIEW",
        "THIS DOES NOT TEST PERFORMANCE",
        "THIS TRACKS PROCESS DISCIPLINE",
        "",
        "- Open the Phase 21C tear sheet.",
        "- Confirm the adoption decision was valid.",
        "- Review reference-only, BTC, severe drawdown, and inception-limited caveats.",
        "- Enter or skip manual paper rows only in a paper account.",
        "- Record fill price and quantity only for manually entered paper rows.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_active_tracking_status(
    *,
    validation: pd.DataFrame,
    targets: pd.DataFrame,
    manual_session_template_written: bool,
) -> pd.DataFrame:
    row = validation.iloc[0] if not validation.empty else pd.Series(dtype=object)
    adoption_decision = _text_value(row.get("adoption_decision", "pending"))
    adoption_valid = _bool_value(row.get("adoption_valid", False))
    active = adoption_valid and adoption_decision == "adopt_regime_informed_shortlist"
    return pd.DataFrame(
        [
            {
                "tracking_date": _today(),
                "selected_signal_date": _text_value(row.get("selected_signal_date", "")),
                "decision_file_present": _bool_value(row.get("decision_file_present", False)),
                "adoption_decision": adoption_decision,
                "adoption_valid": adoption_valid,
                "adoption_status": _text_value(row.get("adoption_status", "")),
                "active_regime_informed_tracking": active,
                "manual_session_template_written": bool(manual_session_template_written),
                "candidate_count": int(targets["canonical_candidate_id"].nunique())
                if not targets.empty
                else 0,
                "phase20_outputs_modified": False,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": (
                    "Regime-informed tracking active only after valid manual adoption."
                    if active
                    else "Pending or non-active adoption state; Phase20 outputs unchanged."
                ),
            }
        ]
    )


def _phase_decision(validation: pd.DataFrame, missing_sources: bool = False) -> str:
    if missing_sources:
        return "regime_informed_adoption_failed_missing_sources"
    row = validation.iloc[0] if not validation.empty else pd.Series(dtype=object)
    if not _bool_value(row.get("decision_file_present", False)):
        return "regime_informed_adoption_pending_manual_review"
    if not _bool_value(row.get("adoption_valid", False)):
        return "regime_informed_adoption_invalid_manual_review_required"
    decision = _text_value(row.get("adoption_decision"))
    if decision == "adopt_regime_informed_shortlist":
        return "regime_informed_adoption_validated_manual_paper_only"
    if decision == "decline_keep_phase20_shortlist":
        return "regime_informed_adoption_declined_keep_phase20"
    return "regime_informed_adoption_pending_manual_review"


def _empty_outputs(output_dir: Path, dashboard_dir: Path, decision: str, missing: list[str]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    validation = pd.DataFrame(
        [
            {
                "decision_date": _today(),
                "selected_signal_date": "",
                "decision_file_present": False,
                "adoption_decision": "pending",
                "adoption_valid": False,
                "adoption_status": "missing_sources",
                "blocking_reasons": ",".join(missing),
                "requires_manual_adoption": True,
                "phase20_outputs_modified": False,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    active = build_active_tracking_status(
        validation=validation,
        targets=pd.DataFrame(),
        manual_session_template_written=False,
    )
    gate = pd.DataFrame(
        [
            _gate_row("phase21c_outputs_present", False, ",".join(missing)),
            _gate_row("adoption_template_written", True),
            _gate_row("adoption_validation_written", True),
            _gate_row("active_tracking_status_written", True),
            _gate_row("dashboard_status_written", True),
            _gate_row("phase20_outputs_not_modified", True),
            _gate_row("promotion_disabled", True),
            _gate_row("live_trading_disabled", True),
            _gate_row("real_money_disabled", True),
            _gate_row("broker_api_integration_disabled", True),
        ]
    )
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 21D",
                "phase21d_decision": decision,
                "all_gates_passed": False,
                "decision_file_present": False,
                "adoption_valid": False,
                "active_regime_informed_tracking": False,
                "manual_session_template_written": False,
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
                "phase": "Phase 21D",
                "phase21d_decision": decision,
                "all_gates_passed": False,
                "promotion_allowed": False,
                "final_model_promoted": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": f"Failed closed due missing sources: {','.join(missing)}",
            }
        ]
    )
    template = build_adoption_decision_template(
        targets=pd.DataFrame(),
        adoption_status=pd.DataFrame(),
    )
    return {
        "summary": _write_csv(summary, output_dir / "phase21d_summary.csv"),
        "gate_report": _write_csv(gate, output_dir / "phase21d_gate_report.csv"),
        "conclusion": _write_csv(conclusion, output_dir / "phase21d_conclusion.csv"),
        "adoption_template": _write_csv(
            template,
            output_dir / "regime_informed_adoption_decision_template.csv",
        ),
        "adoption_validation": _write_csv(
            validation,
            output_dir / "regime_informed_adoption_validation.csv",
        ),
        "active_tracking_status": _write_csv(
            active,
            output_dir / "regime_informed_active_tracking_status.csv",
        ),
        "dashboard_status": _write_csv(
            active.assign(phase21d_decision=decision),
            dashboard_dir / "regime_informed_adoption_status.csv",
        ),
    }


def save_phase21d_regime_informed_adoption(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, Path]:
    section = _section(config)
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
        return _empty_outputs(output_dir, dashboard_dir, "phase21d_disabled", ["phase21d_disabled"])

    source_dir = Path(
        section.get(
            "source_regime_informed_tracking_dir",
            Path(reports_dir) / "paper_trading" / "regime_informed_tracking",
        )
    )
    source_paths = _source_paths(section, Path(reports_dir))
    sources, missing = _load_sources(source_paths)
    if missing:
        return _empty_outputs(
            output_dir,
            dashboard_dir,
            "regime_informed_adoption_failed_missing_sources",
            missing,
        )

    template = build_adoption_decision_template(
        targets=sources["targets"],
        adoption_status=sources["adoption_status"],
    )
    adoption_template_path = output_dir / section.get(
        "adoption_template_filename",
        "regime_informed_adoption_decision_template.csv",
    )
    _write_csv(template, adoption_template_path)

    decision_path = source_dir / section.get(
        "adoption_decision_filename",
        "regime_informed_adoption_decision.csv",
    )
    validation = validate_adoption_decision(
        decision_path=decision_path,
        targets=sources["targets"],
        adoption_status=sources["adoption_status"],
        require_adoption_reason=_bool_value(section.get("require_adoption_reason", True)),
        require_manual_adoption=_bool_value(section.get("require_manual_adoption", True)),
    )
    adoption_valid = _bool_value(validation.iloc[0]["adoption_valid"])
    adoption_decision = _text_value(validation.iloc[0]["adoption_decision"])
    adopted = adoption_valid and adoption_decision == "adopt_regime_informed_shortlist"
    manual_template_written = False
    manual_template_path = output_dir / section.get(
        "manual_session_template_filename",
        "regime_informed_manual_session_template.csv",
    )
    checklist_path = output_dir / section.get(
        "manual_session_checklist_filename",
        "regime_informed_manual_session_checklist.md",
    )
    if adopted:
        manual_session = build_manual_session_template(
            orders=sources["orders"],
            selected_signal_date=_text_value(validation.iloc[0]["selected_signal_date"]),
        )
        _write_csv(manual_session, manual_template_path)
        _write_checklist(checklist_path)
        manual_template_written = True

    active = build_active_tracking_status(
        validation=validation,
        targets=sources["targets"],
        manual_session_template_written=manual_template_written,
    )
    live = _bool_value(section.get("live_trading_allowed", False))
    real = _bool_value(section.get("real_money_allowed", False))
    broker = _bool_value(section.get("broker_api_integration_allowed", False))
    promotion = _bool_value(section.get("promotion_allowed", False))
    gate = pd.DataFrame(
        [
            _gate_row("phase21c_outputs_present", True),
            _gate_row("adoption_template_written", True),
            _gate_row("adoption_validation_written", True),
            _gate_row("active_tracking_status_written", True),
            _gate_row("dashboard_status_written", True),
            _gate_row("phase20_outputs_not_modified", True),
            _gate_row("promotion_disabled", not promotion),
            _gate_row("live_trading_disabled", not live),
            _gate_row("real_money_disabled", not real),
            _gate_row("broker_api_integration_disabled", not broker),
        ]
    )
    all_gates_passed = bool(gate["passed"].map(_bool_value).all())
    decision = _phase_decision(validation)
    if not all_gates_passed:
        decision = "regime_informed_adoption_invalid_manual_review_required"

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 21D",
                "phase21d_decision": decision,
                "all_gates_passed": all_gates_passed,
                "decision_file_present": _bool_value(validation.iloc[0]["decision_file_present"]),
                "adoption_decision": validation.iloc[0]["adoption_decision"],
                "adoption_valid": _bool_value(validation.iloc[0]["adoption_valid"]),
                "active_regime_informed_tracking": _bool_value(
                    active.iloc[0]["active_regime_informed_tracking"]
                ),
                "manual_session_template_written": manual_template_written,
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
                "phase": "Phase 21D",
                "phase21d_decision": decision,
                "all_gates_passed": all_gates_passed,
                "promotion_allowed": False,
                "final_model_promoted": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Adoption gate only. Phase20 outputs are unchanged.",
            }
        ]
    )
    dashboard = active.copy()
    dashboard.insert(0, "phase21d_decision", decision)
    outputs = {
        "summary": _write_csv(summary, output_dir / "phase21d_summary.csv"),
        "gate_report": _write_csv(gate, output_dir / "phase21d_gate_report.csv"),
        "conclusion": _write_csv(conclusion, output_dir / "phase21d_conclusion.csv"),
        "adoption_template": adoption_template_path,
        "adoption_validation": _write_csv(
            validation,
            output_dir / "regime_informed_adoption_validation.csv",
        ),
        "active_tracking_status": _write_csv(
            active,
            output_dir / "regime_informed_active_tracking_status.csv",
        ),
        "dashboard_status": _write_csv(
            dashboard,
            dashboard_dir / "regime_informed_adoption_status.csv",
        ),
    }
    if manual_template_written:
        outputs["manual_session_template"] = manual_template_path
        outputs["manual_session_checklist"] = checklist_path
    print("Wrote Phase 21D regime-informed adoption reports.")
    return outputs
