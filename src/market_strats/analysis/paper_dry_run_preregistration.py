from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


DASHBOARD_PANELS = [
    "current_signal_state",
    "paper_orders_preview",
    "candidate_equity_vs_spy",
    "drawdown_vs_spy",
    "exposure_timeline",
    "rolling_relative_performance",
    "latest_switch_event",
    "data_freshness",
    "stop_condition_status",
    "paper_journal_status",
]


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("phase16a_paper_dry_run_preregistration", {}) or {}


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _text_value(value: Any) -> str:
    if value is None or pd.isna(value):
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


def _latest_signal_row(signal: pd.DataFrame) -> dict[str, Any]:
    if signal.empty:
        return {}

    work = signal.copy()
    sort_source = (
        work["signal_date"]
        if "signal_date" in work.columns
        else work.get("data_as_of_date", pd.Series(index=work.index, dtype=object))
    )
    work["_phase16a_sort_date"] = pd.to_datetime(sort_source, errors="coerce")
    work = work.sort_values("_phase16a_sort_date", na_position="first")
    return work.drop(columns=["_phase16a_sort_date"]).iloc[-1].to_dict()


def _parse_exposure(value: Any) -> float | None:
    try:
        exposure = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(exposure):
        return None
    return exposure


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _paper_safety_flags(section: dict[str, Any]) -> dict[str, bool]:
    return {
        "paper_account_only": _bool_value(section.get("paper_account_only", True)),
        "live_trading_allowed": _bool_value(section.get("live_trading_allowed", False)),
        "real_money_allowed": _bool_value(section.get("real_money_allowed", False)),
        "broker_api_integration_allowed": _bool_value(
            section.get("broker_api_integration_allowed", False)
        ),
    }


def _upstream_safety_flags(decision_row: dict[str, Any]) -> dict[str, bool]:
    return {
        "live_trading_allowed": _bool_value(decision_row.get("live_trading_allowed", False)),
        "real_money_allowed": _bool_value(decision_row.get("real_money_allowed", False)),
        "broker_api_integration_allowed": _bool_value(
            decision_row.get("broker_api_integration_allowed", False)
        ),
        "paper_trading_deployment_allowed": _bool_value(
            decision_row.get("paper_trading_deployment_allowed", False)
        ),
    }


def _build_latest_signal(
    *,
    latest_signal: dict[str, Any],
    section: dict[str, Any],
    gates_passed: bool,
    failure_reason: str,
    generated_at_utc: str,
) -> pd.DataFrame:
    safety = _paper_safety_flags(section)
    readiness_status = (
        "paper_dry_run_preregistered_manual_preview_only"
        if gates_passed
        else "blocked_paper_dry_run_preregistration"
    )

    return pd.DataFrame(
        [
            {
                "signal_date": _text_value(latest_signal.get("signal_date", "")),
                "data_as_of_date": _text_value(latest_signal.get("data_as_of_date", "")),
                "candidate_system_id": _text_value(
                    latest_signal.get(
                        "candidate_system_id",
                        section.get("candidate_system_id", ""),
                    )
                ),
                "current_mode": _text_value(latest_signal.get("current_mode", "")),
                "current_exposure": _text_value(latest_signal.get("current_exposure", "")),
                "target_action": _text_value(latest_signal.get("target_action", "")),
                "switch_triggered": _bool_value(latest_signal.get("switch_triggered", False)),
                "paper_dry_run_allowed": bool(gates_passed),
                "paper_account_only": safety["paper_account_only"],
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "readiness_status": readiness_status,
                "blocking_warnings": failure_reason
                or _text_value(latest_signal.get("blocking_warnings", "")),
                "generated_at_utc": generated_at_utc,
            }
        ]
    )


def _build_paper_orders_preview(
    *,
    latest_signal: pd.DataFrame,
    section: dict[str, Any],
    gates_passed: bool,
    failure_reason: str,
) -> pd.DataFrame:
    row = latest_signal.iloc[0] if not latest_signal.empty else {}
    mode = _text_value(row.get("current_mode", "")).lower()
    exposure = _parse_exposure(row.get("current_exposure", ""))
    notional = float(section.get("paper_notional_usd", 10000))

    symbol = ""
    target_weight = 0.0 if exposure is None else exposure
    target_notional = 0.0
    order_action = "PAPER_NO_ORDER_BLOCKED"
    instruction = "manual_review_only_no_order_placement"

    if gates_passed and exposure is not None:
        if mode == "offensive_spy" and exposure > 0:
            symbol = "SPY"
            target_notional = notional * exposure
            order_action = "PAPER_TARGET_WEIGHT_ONLY"
            instruction = "manual_paper_trade_only"
        elif exposure == 0 or "cash" in mode or "defensive" in mode:
            target_weight = 0.0
            target_notional = 0.0
            order_action = "PAPER_CASH_OR_DEFENSIVE_PREVIEW_ONLY"
            instruction = "manual_review_cash_defensive_state_only"
        else:
            order_action = "PAPER_UNSUPPORTED_MODE_PREVIEW_ONLY"
            instruction = "manual_review_only_unsupported_symbol_not_guessed"

    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "target_weight": target_weight,
                "paper_notional_usd": notional,
                "target_notional_usd": target_notional,
                "order_action": order_action,
                "execution_instruction": instruction,
                "order_placement_attempted": False,
                "preview_only": True,
                "paper_account_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "readiness_status": row.get(
                    "readiness_status",
                    "blocked_paper_dry_run_preregistration",
                ),
                "blocking_warnings": failure_reason,
            }
        ]
    )


def _build_dashboard_manifest(dashboard_dir: Path, output_dir: Path) -> pd.DataFrame:
    artifact_map = {
        "current_signal_state": output_dir / "latest_signal.csv",
        "paper_orders_preview": output_dir / "paper_orders_preview.csv",
        "candidate_equity_vs_spy": Path("reports/phase14g_visual_backtest_equity_curve_vs_spy.csv"),
        "drawdown_vs_spy": Path("reports/phase14g_visual_backtest_drawdown_curve.csv"),
        "exposure_timeline": Path("reports/phase14g_visual_backtest_exposure_timeline.csv"),
        "rolling_relative_performance": Path(
            "reports/phase14g_visual_backtest_rolling_relative_performance.csv"
        ),
        "latest_switch_event": Path(
            "reports/phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"
        ),
        "data_freshness": Path("reports/phase15n_fresh_signal_audit_fresh_signal_audit.csv"),
        "stop_condition_status": output_dir / "paper_trading_readiness_status.csv",
        "paper_journal_status": dashboard_dir / "paper_journal_placeholder.md",
    }
    generated_panels = {
        "current_signal_state",
        "paper_orders_preview",
        "stop_condition_status",
    }

    rows = []
    for panel in DASHBOARD_PANELS:
        artifact_path = artifact_map[panel]
        rows.append(
            {
                "panel_id": panel,
                "panel_title": panel.replace("_", " ").title(),
                "artifact_path": str(artifact_path),
                "artifact_type": artifact_path.suffix.lstrip(".") or "placeholder",
                "status": (
                    "available"
                    if panel in generated_panels or artifact_path.exists()
                    else "placeholder"
                ),
                "notes": (
                    "Phase 16A generated scaffold"
                    if panel in generated_panels
                    else "Expected MVP dashboard panel; source artifact may be added later"
                ),
            }
        )
    return pd.DataFrame(rows)


def _write_latest_signal_markdown(
    *,
    path: Path,
    latest_signal: pd.DataFrame,
    paper_orders_preview: pd.DataFrame,
) -> None:
    signal = latest_signal.iloc[0]
    order = paper_orders_preview.iloc[0]
    lines = [
        "# Latest Paper Dry-Run Signal",
        "",
        f"- Current mode: {signal['current_mode']}",
        f"- Current exposure: {signal['current_exposure']}",
        f"- Target action: {signal['target_action']}",
        f"- Paper dry-run allowed: {signal['paper_dry_run_allowed']}",
        f"- Readiness status: {signal['readiness_status']}",
        f"- Paper account only: {signal['paper_account_only']}",
        "- Live trading allowed: False",
        "- Real money allowed: False",
        "- Broker/API integration allowed: False",
        "",
        "## Manual Paper-Order Preview",
        "",
        f"- Symbol: {order['symbol']}",
        f"- Target weight: {order['target_weight']}",
        f"- Target notional USD: {order['target_notional_usd']}",
        f"- Order action: {order['order_action']}",
        f"- Execution instruction: {order['execution_instruction']}",
        "",
        "This is a manual paper-only preview. It does not place orders.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_dashboard_index(
    *,
    path: Path,
    manifest: pd.DataFrame,
) -> None:
    lines = [
        "# Paper Trading MVP Dashboard",
        "",
        "Static Phase 16A scaffold for manual paper dry-run review.",
        "",
        "No broker/API integration, live trading, or real-money deployment is enabled.",
        "",
        "## Generated Artifacts",
        "",
        "- [Latest signal](../latest_signal.csv)",
        "- [Latest signal summary](../latest_signal.md)",
        "- [Paper orders preview](../paper_orders_preview.csv)",
        "- [Readiness status](../paper_trading_readiness_status.csv)",
        "- [Dashboard manifest](dashboard_manifest.csv)",
        "",
        "## MVP Panels",
        "",
    ]
    for row in manifest.to_dict(orient="records"):
        lines.append(
            f"- {row['panel_id']}: {row['status']} ({row['artifact_path']})"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_phase16a_paper_dry_run_preregistration(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config)
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
            "latest_signal": empty,
            "paper_orders_preview": empty,
            "paper_trading_readiness_status": empty,
            "dashboard_manifest": empty,
        }

    reports_path = Path(reports_dir)
    output_dir = _resolve_path(
        section.get("output_dir"),
        reports_path / "paper_trading",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        output_dir / "dashboard",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    phase15n_reports = section.get("phase15n_reports", {}) or {}
    phase15m_reports = section.get("phase15m_reports", {}) or {}
    decision_path = _resolve_path(
        phase15n_reports.get("decision_report"),
        reports_path / "phase15n_fresh_signal_audit_decision_report.csv",
    )
    signal_path = _resolve_path(
        phase15m_reports.get("current_signal_file"),
        reports_path / "phase15m_current_signal_file.csv",
    )

    decision_report = _read_csv(decision_path)
    current_signal_file = _read_csv(signal_path)
    decision_row = decision_report.iloc[0].to_dict() if not decision_report.empty else {}
    latest_signal_raw = _latest_signal_row(current_signal_file)

    required_decision = section.get(
        "required_upstream_decision",
        "paper_dry_run_preregistration_allowed_next",
    )
    safety = _paper_safety_flags(section)
    upstream_safety = _upstream_safety_flags(decision_row)
    exposure = _parse_exposure(latest_signal_raw.get("current_exposure", ""))
    signal_required_fields_present = all(
        _text_value(latest_signal_raw.get(column, ""))
        for column in ["current_mode", "current_exposure", "target_action"]
    ) and exposure is not None
    candidate_system_matches = (
        not _text_value(section.get("candidate_system_id", ""))
        or _text_value(latest_signal_raw.get("candidate_system_id", ""))
        == _text_value(section.get("candidate_system_id", ""))
    )

    gate_rows = [
        _gate_row("phase15n_decision_report_present", not decision_report.empty, str(decision_path)),
        _gate_row(
            "phase15n_required_decision",
            _text_value(decision_row.get("decision", "")) == required_decision,
            _text_value(decision_row.get("decision", "")),
        ),
        _gate_row(
            "phase15n_preregistration_allowed",
            _bool_value(decision_row.get("paper_dry_run_preregistration_allowed_next", False)),
            str(decision_row.get("paper_dry_run_preregistration_allowed_next", "")),
        ),
        _gate_row("phase15m_current_signal_present", not current_signal_file.empty, str(signal_path)),
        _gate_row(
            "latest_signal_required_fields_present",
            signal_required_fields_present,
            "current_mode,current_exposure,target_action",
        ),
        _gate_row(
            "candidate_system_id_matches",
            candidate_system_matches,
            _text_value(latest_signal_raw.get("candidate_system_id", "")),
        ),
        _gate_row(
            "paper_account_only",
            safety["paper_account_only"],
            str(safety["paper_account_only"]),
        ),
        _gate_row(
            "config_live_trading_disabled",
            not safety["live_trading_allowed"],
            str(safety["live_trading_allowed"]),
        ),
        _gate_row(
            "config_real_money_disabled",
            not safety["real_money_allowed"],
            str(safety["real_money_allowed"]),
        ),
        _gate_row(
            "config_broker_api_disabled",
            not safety["broker_api_integration_allowed"],
            str(safety["broker_api_integration_allowed"]),
        ),
        _gate_row(
            "upstream_live_trading_disabled",
            not upstream_safety["live_trading_allowed"],
            str(upstream_safety["live_trading_allowed"]),
        ),
        _gate_row(
            "upstream_real_money_disabled",
            not upstream_safety["real_money_allowed"],
            str(upstream_safety["real_money_allowed"]),
        ),
        _gate_row(
            "upstream_broker_api_disabled",
            not upstream_safety["broker_api_integration_allowed"],
            str(upstream_safety["broker_api_integration_allowed"]),
        ),
        _gate_row(
            "upstream_paper_deployment_disabled",
            not upstream_safety["paper_trading_deployment_allowed"],
            str(upstream_safety["paper_trading_deployment_allowed"]),
        ),
    ]
    gate_report = pd.DataFrame(gate_rows)
    all_gates_passed = bool(gate_report["passed"].all())
    gate_report["all_gates_passed"] = all_gates_passed
    failure_reason = ";".join(
        gate_report.loc[~gate_report["passed"], "gate_id"].astype(str).tolist()
    )
    generated_at_utc = datetime.now(timezone.utc).isoformat()

    latest_signal = _build_latest_signal(
        latest_signal=latest_signal_raw,
        section=section,
        gates_passed=all_gates_passed,
        failure_reason=failure_reason,
        generated_at_utc=generated_at_utc,
    )
    paper_orders_preview = _build_paper_orders_preview(
        latest_signal=latest_signal,
        section=section,
        gates_passed=all_gates_passed,
        failure_reason=failure_reason,
    )

    readiness_status = pd.DataFrame(
        [
            {
                "phase": "Phase 16A",
                "paper_dry_run_preregistration_allowed": all_gates_passed,
                "paper_account_only": safety["paper_account_only"],
                "paper_trading_ready": False,
                "paper_trading_deployment_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "order_placement_attempted": False,
                "readiness_status": latest_signal.iloc[0]["readiness_status"],
                "failure_reason": failure_reason,
            }
        ]
    )

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 16A",
                "candidate_system_id": section.get("candidate_system_id", ""),
                "required_upstream_decision": required_decision,
                "phase15n_decision": _text_value(decision_row.get("decision", "")),
                "phase15n_decision_report": str(decision_path),
                "phase15m_current_signal_file": str(signal_path),
                "paper_dry_run_preregistration_allowed": all_gates_passed,
                "paper_account_only": safety["paper_account_only"],
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "paper_trading_ready": False,
                "readiness_status": latest_signal.iloc[0]["readiness_status"],
                "failure_reason": failure_reason,
                "generated_at_utc": generated_at_utc,
            }
        ]
    )

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 16A",
                "diagnostic": "Paper dry-run pre-registration and MVP dashboard scaffold",
                "decision": (
                    "paper_dry_run_manual_preview_registered"
                    if all_gates_passed
                    else "blocked_paper_dry_run_preregistration"
                ),
                "all_gates_passed": all_gates_passed,
                "paper_dry_run_preregistration_allowed": all_gates_passed,
                "paper_trading_ready": False,
                "paper_trading_deployment_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failure_reason,
            }
        ]
    )

    dashboard_manifest = _build_dashboard_manifest(dashboard_dir, output_dir)

    outputs = {
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
        "latest_signal": latest_signal,
        "paper_orders_preview": paper_orders_preview,
        "paper_trading_readiness_status": readiness_status,
        "dashboard_manifest": dashboard_manifest,
    }

    summary.to_csv(output_dir / "phase16a_paper_dry_run_preregistration_summary.csv", index=False)
    gate_report.to_csv(output_dir / "phase16a_paper_dry_run_gate_report.csv", index=False)
    conclusion.to_csv(output_dir / "phase16a_paper_dry_run_conclusion.csv", index=False)
    latest_signal.to_csv(output_dir / "latest_signal.csv", index=False)
    paper_orders_preview.to_csv(output_dir / "paper_orders_preview.csv", index=False)
    readiness_status.to_csv(output_dir / "paper_trading_readiness_status.csv", index=False)
    dashboard_manifest.to_csv(dashboard_dir / "dashboard_manifest.csv", index=False)

    _write_latest_signal_markdown(
        path=output_dir / "latest_signal.md",
        latest_signal=latest_signal,
        paper_orders_preview=paper_orders_preview,
    )
    _write_dashboard_index(path=dashboard_dir / "index.md", manifest=dashboard_manifest)

    print("Wrote Phase 16A paper dry-run pre-registration reports.")
    return outputs
