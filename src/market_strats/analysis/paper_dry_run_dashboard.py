from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


VISUAL_ARTIFACTS = {
    "equity_curve": "phase14g_corrected_visual_equity_curve.csv",
    "drawdown_curve": "phase14g_corrected_visual_drawdown_curve.csv",
    "exposure_timeline": "phase14g_corrected_visual_exposure_timeline.csv",
    "rolling_relative_performance": (
        "phase14g_corrected_visual_rolling_relative_performance.csv"
    ),
}

CHART_OUTPUTS = {
    "equity_curve": "paper_equity_curve.png",
    "drawdown_curve": "paper_drawdown_curve.png",
    "exposure_timeline": "paper_exposure_timeline.png",
    "rolling_relative_performance": "paper_rolling_relative_performance.png",
}


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("phase16b_paper_dry_run_dashboard", {}) or {}


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


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _latest_by_date(frame: pd.DataFrame, columns: list[str]) -> pd.Series | None:
    if frame.empty:
        return None

    work = frame.copy()
    date_col = next((column for column in columns if column in work.columns), None)
    if date_col is None:
        return work.iloc[-1]

    work["_phase16b_sort_date"] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.sort_values("_phase16b_sort_date", na_position="first")
    return work.drop(columns=["_phase16b_sort_date"]).iloc[-1]


def _latest_signal(latest_signal_file: pd.DataFrame) -> pd.DataFrame:
    latest = _latest_by_date(latest_signal_file, ["signal_date", "data_as_of_date"])
    if latest is None:
        return pd.DataFrame()
    return pd.DataFrame([latest.to_dict()])


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(parsed):
        return default
    return parsed


def _safety_flags(section: dict[str, Any]) -> dict[str, bool]:
    return {
        "live_trading_allowed": _bool_value(section.get("live_trading_allowed", False)),
        "real_money_allowed": _bool_value(section.get("real_money_allowed", False)),
        "broker_api_integration_allowed": _bool_value(
            section.get("broker_api_integration_allowed", False)
        ),
    }


def _placeholder_frame(panel_id: str, warning: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "panel_id": panel_id,
                "placeholder": True,
                "status": "placeholder",
                "warning": warning,
            }
        ]
    )


def _copy_or_placeholder_visual(
    *,
    reports_dir: Path,
    dashboard_dir: Path,
    panel_id: str,
    configured_path: str | None,
) -> tuple[pd.DataFrame, bool, str]:
    source_path = _resolve_path(
        configured_path,
        reports_dir / VISUAL_ARTIFACTS[panel_id],
    )
    frame = _read_csv(source_path)
    if frame.empty:
        warning = f"missing_visual_artifact:{source_path}"
        out = _placeholder_frame(panel_id, warning)
        _write_csv(out, dashboard_dir / f"{panel_id}.csv")
        return out, False, warning

    out = frame.copy()
    out["panel_id"] = panel_id
    out["placeholder"] = False
    _write_csv(out, dashboard_dir / f"{panel_id}.csv")
    return out, True, ""


def _plot_placeholder(path: Path, title: str, warning: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.55, title, ha="center", va="center", fontsize=13)
    ax.text(0.5, 0.40, warning, ha="center", va="center", fontsize=9, wrap=True)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _date_axis(frame: pd.DataFrame) -> tuple[pd.Series | range, str | None]:
    date_col = next(
        (column for column in ["decision_date", "date", "signal_date"] if column in frame.columns),
        None,
    )
    if date_col is None:
        return range(len(frame)), None
    return pd.to_datetime(frame[date_col], errors="coerce"), date_col


def _plot_visual(panel_id: str, frame: pd.DataFrame, path: Path, warning: str) -> None:
    if frame.empty or bool(frame.get("placeholder", pd.Series([False])).iloc[0]):
        _plot_placeholder(path, panel_id.replace("_", " ").title(), warning)
        return

    x_values, _date_col = _date_axis(frame)
    fig, ax = plt.subplots(figsize=(9, 4.5))

    if panel_id == "equity_curve":
        for col, label in [
            ("candidate_equity", "Candidate"),
            ("benchmark_equity", "SPY benchmark"),
        ]:
            if col in frame.columns:
                ax.plot(x_values, frame[col], label=label)
        ax.set_ylabel("Equity")
    elif panel_id == "drawdown_curve":
        for col, label in [
            ("candidate_drawdown", "Candidate"),
            ("benchmark_drawdown", "SPY benchmark"),
        ]:
            if col in frame.columns:
                ax.plot(x_values, frame[col], label=label)
        ax.set_ylabel("Drawdown")
    elif panel_id == "exposure_timeline":
        if "exposure" in frame.columns:
            ax.step(x_values, frame["exposure"], where="post", label="Exposure")
        ax.set_ylabel("Exposure")
        ax.set_ylim(-0.05, 1.05)
    elif panel_id == "rolling_relative_performance":
        if "rolling_relative_return" in frame.columns:
            ax.plot(x_values, frame["rolling_relative_return"], label="Rolling relative return")
        ax.set_ylabel("Rolling relative return")

    ax.set_title(panel_id.replace("_", " ").title())
    ax.grid(True, alpha=0.25)
    if ax.get_legend_handles_labels()[0]:
        ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _signal_history(existing: pd.DataFrame, latest_signal: pd.DataFrame) -> pd.DataFrame:
    if latest_signal.empty:
        base = existing.copy()
    elif existing.empty:
        base = latest_signal.copy()
    else:
        base = pd.concat([existing, latest_signal], ignore_index=True)

    if base.empty:
        return base

    for column in ["candidate_system_id", "signal_date", "data_as_of_date"]:
        if column not in base.columns:
            base[column] = ""

    base = base.drop_duplicates(
        subset=["candidate_system_id", "signal_date", "data_as_of_date"],
        keep="last",
    )
    base["_phase16b_sort_date"] = pd.to_datetime(
        base["signal_date"].where(base["signal_date"].astype(str).str.len() > 0, base["data_as_of_date"]),
        errors="coerce",
    )
    base = base.sort_values("_phase16b_sort_date", na_position="first").drop(
        columns=["_phase16b_sort_date"]
    )
    return base.reset_index(drop=True)


def _paper_journal(existing: pd.DataFrame, latest_signal: pd.DataFrame, order: pd.DataFrame) -> pd.DataFrame:
    if latest_signal.empty:
        new_row = pd.DataFrame()
    else:
        signal = latest_signal.iloc[0]
        order_row = order.iloc[0] if not order.empty else {}
        new_row = pd.DataFrame(
            [
                {
                    "signal_date": signal.get("signal_date", ""),
                    "data_as_of_date": signal.get("data_as_of_date", ""),
                    "current_mode": signal.get("current_mode", ""),
                    "current_exposure": signal.get("current_exposure", ""),
                    "target_action": signal.get("target_action", ""),
                    "paper_order_action": order_row.get("order_action", ""),
                    "manual_execution_status": "not_entered",
                    "notes": "",
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                }
            ]
        )

    if existing.empty:
        out = new_row
    elif new_row.empty:
        out = existing.copy()
    else:
        out = pd.concat([existing, new_row], ignore_index=True)

    if out.empty:
        return out

    for column in ["signal_date", "data_as_of_date", "paper_order_action"]:
        if column not in out.columns:
            out[column] = ""

    return out.drop_duplicates(
        subset=["signal_date", "data_as_of_date", "paper_order_action"],
        keep="last",
    ).reset_index(drop=True)


def _portfolio_state(
    *,
    latest_signal: pd.DataFrame,
    order: pd.DataFrame,
    readiness: pd.DataFrame,
    paper_notional: float,
) -> pd.DataFrame:
    signal = latest_signal.iloc[0] if not latest_signal.empty else {}
    order_row = order.iloc[0] if not order.empty else {}
    readiness_row = readiness.iloc[0] if not readiness.empty else {}

    return pd.DataFrame(
        [
            {
                "paper_notional_usd": paper_notional,
                "target_symbol": order_row.get("symbol", ""),
                "target_weight": order_row.get("target_weight", 0.0),
                "target_notional_usd": order_row.get("target_notional_usd", 0.0),
                "current_mode": signal.get("current_mode", ""),
                "current_exposure": signal.get("current_exposure", ""),
                "readiness_status": signal.get(
                    "readiness_status",
                    readiness_row.get("readiness_status", ""),
                ),
                "order_placement_attempted": False,
                "paper_account_only": signal.get("paper_account_only", True),
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )


def _data_freshness(
    *,
    latest_signal: pd.DataFrame,
    fresh_stream: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    signal = latest_signal.iloc[0] if not latest_signal.empty else {}
    configured_audit_date = _text_value(
        config.get("phase15m_fresh_current_signal_generation", {}).get(
            "audit_current_date",
            "",
        )
    )
    data_as_of = pd.to_datetime(signal.get("data_as_of_date", ""), errors="coerce")
    signal_date = pd.to_datetime(signal.get("signal_date", ""), errors="coerce")

    fresh_max = pd.NaT
    fresh_rows = len(fresh_stream)
    if not fresh_stream.empty and "date" in fresh_stream.columns:
        dates = pd.to_datetime(fresh_stream["date"], errors="coerce")
        if dates.notna().any():
            fresh_max = dates.max()

    rows_after_signal = False
    if pd.notna(fresh_max) and pd.notna(data_as_of):
        rows_after_signal = bool(fresh_max > data_as_of)

    if configured_audit_date:
        policy = "configured_audit_date_caps_signal"
        warning = ""
    elif pd.notna(fresh_max) and pd.notna(data_as_of) and fresh_max == data_as_of:
        policy = "latest_available_fresh_row_used"
        warning = ""
    elif latest_signal.empty:
        policy = "latest_signal_missing"
        warning = "latest_signal_missing"
    else:
        policy = "latest_available_fresh_row_not_used"
        warning = "fresh_stream_newer_than_signal"

    return pd.DataFrame(
        [
            {
                "signal_date": signal_date.strftime("%Y-%m-%d") if pd.notna(signal_date) else "",
                "data_as_of_date": data_as_of.strftime("%Y-%m-%d") if pd.notna(data_as_of) else "",
                "configured_audit_date": configured_audit_date,
                "fresh_stream_rows": fresh_rows,
                "fresh_stream_max_date": fresh_max.strftime("%Y-%m-%d") if pd.notna(fresh_max) else "",
                "fresh_rows_beyond_signal_date": rows_after_signal,
                "date_selection_policy": policy,
                "blocking_warnings": warning,
            }
        ]
    )


def _latest_switch_event(switch_log: pd.DataFrame) -> pd.DataFrame:
    latest = _latest_by_date(switch_log, ["decision_date", "date"])
    if latest is None:
        return _placeholder_frame(
            "latest_switch_event",
            "missing_switch_event_log",
        )
    out = pd.DataFrame([latest.to_dict()])
    out["placeholder"] = False
    return out


def _stop_conditions(
    *,
    latest_signal: pd.DataFrame,
    order: pd.DataFrame,
    section: dict[str, Any],
    data_freshness: pd.DataFrame,
) -> pd.DataFrame:
    signal = latest_signal.iloc[0] if not latest_signal.empty else {}
    order_row = order.iloc[0] if not order.empty else {}
    safety = _safety_flags(section)
    freshness_warning = ""
    if not data_freshness.empty:
        freshness_warning = _text_value(data_freshness.iloc[0].get("blocking_warnings", ""))
    signal_warning = _text_value(signal.get("blocking_warnings", ""))

    rows = [
        {
            "stop_id": "latest_signal_missing",
            "triggered": latest_signal.empty,
            "detail": "latest_signal.csv missing or empty",
        },
        {
            "stop_id": "paper_dry_run_not_allowed",
            "triggered": not _bool_value(signal.get("paper_dry_run_allowed", False)),
            "detail": str(signal.get("paper_dry_run_allowed", "")),
        },
        {
            "stop_id": "live_trading_flag_true",
            "triggered": safety["live_trading_allowed"]
            or _bool_value(signal.get("live_trading_allowed", False)),
            "detail": str(safety["live_trading_allowed"]),
        },
        {
            "stop_id": "real_money_flag_true",
            "triggered": safety["real_money_allowed"]
            or _bool_value(signal.get("real_money_allowed", False)),
            "detail": str(safety["real_money_allowed"]),
        },
        {
            "stop_id": "broker_api_flag_true",
            "triggered": safety["broker_api_integration_allowed"]
            or _bool_value(signal.get("broker_api_integration_allowed", False)),
            "detail": str(safety["broker_api_integration_allowed"]),
        },
        {
            "stop_id": "data_freshness_warning_present",
            "triggered": bool(signal_warning or freshness_warning),
            "detail": signal_warning or freshness_warning,
        },
        {
            "stop_id": "order_placement_attempted",
            "triggered": _bool_value(order_row.get("order_placement_attempted", False)),
            "detail": str(order_row.get("order_placement_attempted", "")),
        },
    ]
    out = pd.DataFrame(rows)
    out["result"] = out["triggered"].map(lambda triggered: "Stop" if triggered else "Clear")
    out["any_stop_triggered"] = bool(out["triggered"].any())
    return out


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _write_index(
    *,
    path: Path,
    visual_status: dict[str, bool],
    stop_conditions: pd.DataFrame,
) -> None:
    available = [
        "current_signal_state",
        "paper_orders_preview",
        "data_freshness",
        "latest_switch_event",
        "stop_condition_status",
    ]
    available.extend(panel for panel, present in visual_status.items() if present)
    placeholders = [panel for panel, present in visual_status.items() if not present]
    if not placeholders:
        placeholders = ["paper_journal_status"]
    else:
        placeholders.append("paper_journal_status")

    stop_triggered = bool(stop_conditions["triggered"].any()) if not stop_conditions.empty else True
    lines = [
        "# Paper Dry-Run Dashboard",
        "",
        "Manual paper dry-run dashboard scaffold.",
        "",
        "Paper-only status:",
        "",
        "- Live trading allowed: False",
        "- Real money allowed: False",
        "- Broker/API integration allowed: False",
        "- Order placement attempted: False",
        "",
        "## Available Panels",
        "",
    ]
    lines.extend(f"- {panel}" for panel in available)
    lines.extend(
        [
            "",
            "## Missing Or Placeholder Panels",
            "",
        ]
    )
    lines.extend(f"- {panel}" for panel in placeholders)
    lines.extend(
        [
            "",
            "## Stop Conditions",
            "",
            f"- Any stop triggered: {stop_triggered}",
            "- Details: `stop_condition_status.csv`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_phase16b_paper_dry_run_dashboard(
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
        }

    reports_path = Path(reports_dir)
    output_dir = _resolve_path(section.get("output_dir"), reports_path / "paper_trading")
    dashboard_dir = _resolve_path(section.get("dashboard_dir"), output_dir / "dashboard")
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    sources = section.get("source_files", {}) or {}
    latest_signal_path = _resolve_path(
        sources.get("latest_signal"),
        output_dir / "latest_signal.csv",
    )
    orders_path = _resolve_path(
        sources.get("paper_orders_preview"),
        output_dir / "paper_orders_preview.csv",
    )
    readiness_path = _resolve_path(
        sources.get("paper_trading_readiness_status"),
        output_dir / "paper_trading_readiness_status.csv",
    )
    fresh_stream_path = _resolve_path(
        sources.get("wxyz_fresh_handoff"),
        Path("data/fresh/phase15q_rule_generated_candidate_stream.csv"),
    )
    switch_log_path = _resolve_path(
        sources.get("switch_event_log"),
        reports_path / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv",
    )

    latest_signal = _latest_signal(_read_csv(latest_signal_path))
    order_preview = _read_csv(orders_path)
    readiness = _read_csv(readiness_path)
    fresh_stream = _read_csv(fresh_stream_path)
    switch_log = _read_csv(switch_log_path)

    paper_notional = float(section.get("paper_notional_usd", 10000))

    data_freshness = _data_freshness(
        latest_signal=latest_signal,
        fresh_stream=fresh_stream,
        config=config,
    )
    latest_switch = _latest_switch_event(switch_log)
    stop_conditions = _stop_conditions(
        latest_signal=latest_signal,
        order=order_preview,
        section=section,
        data_freshness=data_freshness,
    )

    signal_history_path = output_dir / "paper_signal_history.csv"
    paper_signal_history = _signal_history(_read_csv(signal_history_path), latest_signal)
    paper_journal = _paper_journal(
        _read_csv(output_dir / "paper_journal.csv"),
        latest_signal,
        order_preview,
    )
    portfolio_state = _portfolio_state(
        latest_signal=latest_signal,
        order=order_preview,
        readiness=readiness,
        paper_notional=paper_notional,
    )

    _write_csv(paper_signal_history, signal_history_path)
    _write_csv(paper_journal, output_dir / "paper_journal.csv")
    _write_csv(portfolio_state, output_dir / "paper_portfolio_state.csv")
    _write_csv(latest_signal, dashboard_dir / "current_signal_state.csv")
    _write_csv(order_preview, dashboard_dir / "paper_orders_preview.csv")
    _write_csv(data_freshness, dashboard_dir / "data_freshness.csv")
    _write_csv(latest_switch, dashboard_dir / "latest_switch_event.csv")
    _write_csv(stop_conditions, dashboard_dir / "stop_condition_status.csv")

    visual_status: dict[str, bool] = {}
    visual_warnings: list[str] = []
    visual_sources = section.get("visual_artifacts", {}) or {}
    visual_outputs: dict[str, pd.DataFrame] = {}
    for panel_id in VISUAL_ARTIFACTS:
        frame, present, warning = _copy_or_placeholder_visual(
            reports_dir=reports_path,
            dashboard_dir=dashboard_dir,
            panel_id=panel_id,
            configured_path=visual_sources.get(panel_id),
        )
        visual_outputs[panel_id] = frame
        visual_status[panel_id] = present
        if warning:
            visual_warnings.append(warning)
        _plot_visual(
            panel_id,
            frame,
            dashboard_dir / CHART_OUTPUTS[panel_id],
            warning,
        )

    _write_index(
        path=dashboard_dir / "index.md",
        visual_status=visual_status,
        stop_conditions=stop_conditions,
    )

    safety = _safety_flags(section)
    no_stop_conditions = not bool(stop_conditions["triggered"].any())
    gates = [
        _gate_row("latest_signal_present", not latest_signal.empty, str(latest_signal_path)),
        _gate_row(
            "paper_dry_run_allowed",
            bool(
                not latest_signal.empty
                and _bool_value(latest_signal.iloc[0].get("paper_dry_run_allowed", False))
            ),
            "",
        ),
        _gate_row("paper_order_preview_present", not order_preview.empty, str(orders_path)),
        _gate_row("live_trading_disabled", not safety["live_trading_allowed"], ""),
        _gate_row("real_money_disabled", not safety["real_money_allowed"], ""),
        _gate_row(
            "broker_api_integration_disabled",
            not safety["broker_api_integration_allowed"],
            "",
        ),
        _gate_row("no_stop_conditions_triggered", no_stop_conditions, ""),
    ]
    gate_report = pd.DataFrame(gates)
    all_gates_passed = bool(gate_report["passed"].all())
    gate_report["all_gates_passed"] = all_gates_passed
    failure_reason = ";".join(
        gate_report.loc[~gate_report["passed"], "gate_id"].astype(str).tolist()
    )
    generated_at_utc = datetime.now(timezone.utc).isoformat()

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 16B",
                "paper_signal_history_rows": len(paper_signal_history),
                "paper_journal_rows": len(paper_journal),
                "latest_signal_date": (
                    latest_signal.iloc[0].get("signal_date", "") if not latest_signal.empty else ""
                ),
                "latest_data_as_of_date": (
                    latest_signal.iloc[0].get("data_as_of_date", "")
                    if not latest_signal.empty
                    else ""
                ),
                "paper_dry_run_dashboard_allowed": all_gates_passed,
                "charts_complete": all(visual_status.values()),
                "visual_placeholder_count": sum(not status for status in visual_status.values()),
                "stop_conditions_triggered": not no_stop_conditions,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failure_reason,
                "visual_warnings": ";".join(visual_warnings),
                "generated_at_utc": generated_at_utc,
            }
        ]
    )

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 16B",
                "diagnostic": "Paper dry-run execution journal and dashboard visual pack v1",
                "decision": (
                    "paper_dry_run_dashboard_written_manual_preview_only"
                    if all_gates_passed
                    else "blocked_paper_dry_run_dashboard"
                ),
                "all_gates_passed": all_gates_passed,
                "paper_dry_run_dashboard_allowed": all_gates_passed,
                "charts_complete": all(visual_status.values()),
                "paper_trading_ready": False,
                "paper_trading_deployment_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failure_reason,
            }
        ]
    )

    _write_csv(summary, output_dir / "phase16b_paper_dry_run_dashboard_summary.csv")
    _write_csv(gate_report, output_dir / "phase16b_paper_dry_run_dashboard_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase16b_paper_dry_run_dashboard_conclusion.csv")

    outputs = {
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
        "paper_signal_history": paper_signal_history,
        "paper_journal": paper_journal,
        "paper_portfolio_state": portfolio_state,
        "current_signal_state": latest_signal,
        "paper_orders_preview": order_preview,
        "data_freshness": data_freshness,
        "latest_switch_event": latest_switch,
        "stop_condition_status": stop_conditions,
        **visual_outputs,
    }
    print("Wrote Phase 16B paper dry-run dashboard reports.")
    return outputs
