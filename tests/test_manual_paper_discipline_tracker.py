from pathlib import Path

import pandas as pd

from market_strats.analysis.manual_paper_discipline_tracker import (
    build_manual_paper_discipline_history,
    build_manual_paper_discipline_streak_report,
    save_phase20e_manual_paper_discipline_tracker,
)


def _config(reports_dir: Path) -> dict:
    return {
        "phase20e_manual_paper_discipline_tracker": {
            "enabled": True,
            "output_dir": str(reports_dir / "paper_trading" / "manual_sessions"),
            "dashboard_dir": str(reports_dir / "paper_trading" / "dashboard"),
            "source_manual_session_dir": str(
                reports_dir / "paper_trading" / "manual_sessions"
            ),
            "source_cycle_tracker_dir": str(
                reports_dir / "paper_trading" / "cycle_tracker"
            ),
            "source_finalist_tracking_dir": str(
                reports_dir / "paper_trading" / "finalist_tracking"
            ),
            "required_discipline_cycles": 10,
            "required_clean_signal_cycles": 10,
            "allow_warning_skip_as_valid_discipline_cycle": True,
            "require_btc_ack_when_btc_weight_positive": True,
            "require_no_unexplained_overrides": True,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        }
    }


def _ledger() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "session_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "candidate_role": "primary_paper_candidate_clean_growth",
                "asset": "SPY",
                "target_weight": 0.60,
                "target_notional_usd": 6000.0,
                "manual_decision": "skip_due_warning",
                "manual_execution_status": "skipped",
                "paper_fill_price": "",
                "paper_fill_quantity": "",
                "actual_notional_usd": "",
                "deviation_from_preview_usd": "",
                "deviation_from_preview_pct": "",
                "override_reason": "reviewed BTC warning and skipped first cycle",
                "notes": "",
                "warnings_acknowledged": True,
                "btc_caveat_acknowledged": True,
                "tear_sheet_reviewed": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            },
            {
                "session_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "high_growth_high_caveat_btc_candidate",
                "asset": "BTC-USD",
                "target_weight": 0.05,
                "target_notional_usd": 500.0,
                "manual_decision": "skip_due_warning",
                "manual_execution_status": "skipped",
                "paper_fill_price": "",
                "paper_fill_quantity": "",
                "actual_notional_usd": "",
                "deviation_from_preview_usd": "",
                "deviation_from_preview_pct": "",
                "override_reason": "reviewed BTC warning and skipped first cycle",
                "notes": "",
                "warnings_acknowledged": True,
                "btc_caveat_acknowledged": True,
                "tear_sheet_reviewed": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            },
        ]
    )


def _row_validation(valid: bool = True) -> pd.DataFrame:
    rows = []
    for row in _ledger().to_dict(orient="records"):
        rows.append(
            {
                "session_date": row["session_date"],
                "selected_signal_date": row["selected_signal_date"],
                "canonical_candidate_id": row["canonical_candidate_id"],
                "asset": row["asset"],
                "row_valid": valid,
                "row_blocking_reasons": "" if valid else "test_failure",
                "manual_decision": row["manual_decision"],
                "manual_execution_status": row["manual_execution_status"],
                "target_notional_usd": row["target_notional_usd"],
                "paper_fill_price": "",
                "paper_fill_quantity": "",
                "actual_notional_usd": "",
                "deviation_from_preview_usd": "",
                "deviation_from_preview_pct": "",
            }
        )
    return pd.DataFrame(rows)


def _cycle_history(warning_symbols: str = "BTC-USD") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cycle_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "warning_symbols": warning_symbols,
                "blocking_symbols": "none",
            }
        ]
    )


def _cycle_latest(warning_symbols: str = "BTC-USD") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cycle_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "warning_symbols": warning_symbols,
                "blocking_symbols": "none",
            }
        ]
    )


def _tear_sheet(warning_symbols: str = "BTC-USD") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"category": "fresh_data_quality", "key": "warning_symbols", "value": warning_symbols},
            {"category": "finalists", "key": "blocked_candidates", "value": "none"},
        ]
    )


def _tracking_status(warning_symbols: str = "BTC-USD") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tracking_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "data_quality_status": "warning" if warning_symbols != "none" else "pass",
                "warning_symbols": warning_symbols,
                "blocking_symbols": "none",
                "blocked_candidate_count": 0,
            }
        ]
    )


def _history(
    *,
    ledger: pd.DataFrame | None = None,
    warning_symbols: str = "BTC-USD",
) -> pd.DataFrame:
    return build_manual_paper_discipline_history(
        ledger=_ledger() if ledger is None else ledger,
        row_validation=_row_validation(),
        cycle_history=_cycle_history(warning_symbols),
        cycle_latest=_cycle_latest(warning_symbols),
        finalist_tracking_status=_tracking_status(warning_symbols),
        tear_sheet=_tear_sheet(warning_symbols),
    )


def _write_sources(reports_dir: Path, *, warning_symbols: str = "BTC-USD") -> None:
    manual_dir = reports_dir / "paper_trading" / "manual_sessions"
    cycle_dir = reports_dir / "paper_trading" / "cycle_tracker"
    finalist_dir = reports_dir / "paper_trading" / "finalist_tracking"
    dashboard_dir = reports_dir / "paper_trading" / "dashboard"
    manual_dir.mkdir(parents=True, exist_ok=True)
    cycle_dir.mkdir(parents=True, exist_ok=True)
    finalist_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    _ledger().to_csv(manual_dir / "manual_paper_session_ledger.csv", index=False)
    pd.DataFrame(
        [
            {
                "session_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "session_valid": True,
            }
        ]
    ).to_csv(manual_dir / "manual_paper_session_ingestion_result.csv", index=False)
    _row_validation().to_csv(
        manual_dir / "manual_paper_session_row_validation.csv",
        index=False,
    )
    _cycle_history(warning_symbols).to_csv(
        cycle_dir / "paper_cycle_history.csv",
        index=False,
    )
    _cycle_latest(warning_symbols).to_csv(
        cycle_dir / "paper_cycle_latest.csv",
        index=False,
    )
    _tear_sheet(warning_symbols).to_csv(
        finalist_dir / "finalist_daily_tracking_tear_sheet.csv",
        index=False,
    )
    _tracking_status(warning_symbols).to_csv(
        dashboard_dir / "finalist_tracking_status.csv",
        index=False,
    )


def test_missing_ledger_fails_closed(tmp_path):
    reports_dir = tmp_path / "reports"

    outputs = save_phase20e_manual_paper_discipline_tracker(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    summary = outputs["summary"].iloc[0]
    assert summary["phase20e_decision"] == "manual_paper_discipline_tracker_failed_closed"
    assert not bool(summary["all_gates_passed"])


def test_valid_warning_skip_counts_as_discipline_not_clean_signal():
    history = _history()
    row = history.iloc[0]

    assert bool(row["valid_discipline_cycle"])
    assert not bool(row["clean_signal_cycle"])
    assert bool(row["warnings_present"])
    assert bool(row["skipped_trade_present"])


def test_streak_report_tracks_discipline_separately_from_clean_signal():
    history = _history()
    streak = build_manual_paper_discipline_streak_report(
        history=history,
        required_discipline_cycles=10,
        required_clean_signal_cycles=10,
        live_trading_allowed=False,
        real_money_allowed=False,
        broker_api_integration_allowed=False,
    ).iloc[0]

    assert streak["valid_discipline_sessions"] == 1
    assert streak["clean_signal_sessions"] == 0
    assert streak["current_valid_discipline_streak"] == 1
    assert streak["current_clean_signal_streak"] == 0


def test_readiness_false_with_fewer_than_required_cycles():
    history = _history()
    streak = build_manual_paper_discipline_streak_report(
        history=history,
        required_discipline_cycles=10,
        required_clean_signal_cycles=10,
        live_trading_allowed=False,
        real_money_allowed=False,
        broker_api_integration_allowed=False,
    ).iloc[0]

    assert not bool(streak["ready_for_recurring_paper_tracking"])
    assert "insufficient_valid_discipline_cycles" in streak[
        "readiness_blocking_reasons"
    ]
    assert "insufficient_clean_signal_cycles" in streak["readiness_blocking_reasons"]


def test_btc_positive_rows_require_btc_acknowledgement():
    ledger = _ledger()
    ledger.loc[ledger["asset"] == "BTC-USD", "btc_caveat_acknowledged"] = False

    history = _history(ledger=ledger)

    assert not bool(history.iloc[0]["valid_discipline_cycle"])
    assert "btc_caveat_acknowledgement_missing" in history.iloc[0][
        "discipline_cycle_blocking_reasons"
    ]


def test_unexplained_override_prevents_valid_discipline_cycle():
    ledger = _ledger()
    ledger["override_reason"] = ""
    ledger["notes"] = ""

    history = _history(ledger=ledger)

    assert not bool(history.iloc[0]["valid_discipline_cycle"])
    assert "unexplained_override_present" in history.iloc[0][
        "discipline_cycle_blocking_reasons"
    ]


def test_candidate_summary_counts_skipped_and_warning_skip_rows(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_sources(reports_dir)

    outputs = save_phase20e_manual_paper_discipline_tracker(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )
    summary = outputs["manual_paper_candidate_discipline_summary"]

    assert set(summary["canonical_candidate_id"]) == {
        "canonical_spy_qqq_60_40",
        "canonical_inverse_vol_63d_btc_usd_qqq_spy",
    }
    assert summary["skipped_count"].sum() == 2
    assert summary["warning_skip_count"].sum() == 2
    assert summary["invalid_rows"].sum() == 0


def test_dashboard_markdown_and_status_are_written(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_sources(reports_dir)

    save_phase20e_manual_paper_discipline_tracker(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    markdown = (
        reports_dir
        / "paper_trading"
        / "manual_sessions"
        / "manual_paper_discipline_dashboard.md"
    ).read_text(encoding="utf-8")
    dashboard = pd.read_csv(
        reports_dir
        / "paper_trading"
        / "dashboard"
        / "manual_paper_discipline_status.csv"
    )

    assert "NO LIVE TRADING" in markdown
    assert "NO REAL MONEY" in markdown
    assert "NO BROKER/API" in markdown
    assert "MANUAL PAPER ONLY" in markdown
    assert "THIS TRACKS PROCESS DISCIPLINE" in markdown
    assert not bool(dashboard.iloc[0]["ready_for_recurring_paper_tracking"])
    assert not bool(dashboard.iloc[0]["live_trading_allowed"])
    assert not bool(dashboard.iloc[0]["real_money_allowed"])
    assert not bool(dashboard.iloc[0]["broker_api_integration_allowed"])
