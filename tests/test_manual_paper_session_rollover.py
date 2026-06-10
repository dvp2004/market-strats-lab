from pathlib import Path

import pandas as pd

from market_strats.analysis.manual_paper_session_rollover import (
    save_phase20f_manual_paper_session_rollover,
)


def _config(reports_dir: Path) -> dict:
    return {
        "phase20f_manual_paper_session_rollover": {
            "enabled": True,
            "output_dir": str(reports_dir / "paper_trading" / "manual_sessions"),
            "dashboard_dir": str(reports_dir / "paper_trading" / "dashboard"),
            "source_manual_session_dir": str(
                reports_dir / "paper_trading" / "manual_sessions"
            ),
            "filled_session_filename": "manual_paper_session_filled.csv",
            "template_filename": "manual_paper_session_template.csv",
            "archive_dir": str(
                reports_dir / "paper_trading" / "manual_sessions" / "archive"
            ),
            "archive_completed_valid_sessions": True,
            "stale_filled_file_policy": "block_current_ingestion",
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        }
    }


def _session_rows(
    *,
    session_date: str = "2026-06-10",
    selected_signal_date: str = "2026-06-08",
) -> list[dict]:
    return [
        {
            "session_date": session_date,
            "selected_signal_date": selected_signal_date,
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
            "override_reason": "reviewed warning and skipped first cycle",
            "notes": "",
            "warnings_acknowledged": True,
            "btc_caveat_acknowledged": True,
            "tear_sheet_reviewed": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        },
        {
            "session_date": session_date,
            "selected_signal_date": selected_signal_date,
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


def _write_template(reports_dir: Path, **kwargs) -> pd.DataFrame:
    manual_dir = reports_dir / "paper_trading" / "manual_sessions"
    manual_dir.mkdir(parents=True, exist_ok=True)
    template = pd.DataFrame(_session_rows(**kwargs))
    template.to_csv(manual_dir / "manual_paper_session_template.csv", index=False)
    return template


def _write_filled(reports_dir: Path, **kwargs) -> pd.DataFrame:
    manual_dir = reports_dir / "paper_trading" / "manual_sessions"
    manual_dir.mkdir(parents=True, exist_ok=True)
    filled = pd.DataFrame(_session_rows(**kwargs))
    filled.to_csv(manual_dir / "manual_paper_session_filled.csv", index=False)
    return filled


def _write_ingestion_result(reports_dir: Path, *, session_valid: bool) -> None:
    manual_dir = reports_dir / "paper_trading" / "manual_sessions"
    manual_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "session_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "filled_session_file_present": True,
                "session_ingestion_status": (
                    "valid_manual_paper_session"
                    if session_valid
                    else "invalid_manual_review_required"
                ),
                "session_valid": session_valid,
            }
        ]
    ).to_csv(manual_dir / "manual_paper_session_ingestion_result.csv", index=False)


def _write_ledger(reports_dir: Path, rows: pd.DataFrame) -> None:
    manual_dir = reports_dir / "paper_trading" / "manual_sessions"
    manual_dir.mkdir(parents=True, exist_ok=True)
    rows.to_csv(manual_dir / "manual_paper_session_ledger.csv", index=False)


def test_no_filled_file_writes_pending_status(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_template(reports_dir)

    outputs = save_phase20f_manual_paper_session_rollover(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    status = outputs["manual_paper_session_rollover_status"].iloc[0]
    assert not bool(status["filled_session_file_present"])
    assert status["rollover_action"] == "no_filled_file_pending_user_entries"
    assert bool(outputs["gate_report"]["passed"].all())


def test_current_matching_filled_file_is_recognised(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_template(reports_dir)
    _write_filled(reports_dir)
    _write_ingestion_result(reports_dir, session_valid=True)

    outputs = save_phase20f_manual_paper_session_rollover(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    status = outputs["manual_paper_session_rollover_status"].iloc[0]
    assert bool(status["filled_session_matches_current_template"])
    assert status["rollover_action"] == "current_filled_file_available"


def test_stale_filled_file_is_blocked(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_template(reports_dir, session_date="2026-06-11")
    _write_filled(reports_dir, session_date="2026-06-10")
    _write_ingestion_result(reports_dir, session_valid=True)
    _write_ledger(reports_dir, pd.DataFrame(_session_rows()))

    outputs = save_phase20f_manual_paper_session_rollover(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    status = outputs["manual_paper_session_rollover_status"].iloc[0]
    assert bool(status["filled_session_stale"])
    assert status["rollover_action"] == "stale_file_blocked"
    assert status["rollover_blocking_reason"] == (
        "filled_session_does_not_match_current_template"
    )


def test_valid_already_ingested_filled_file_is_archived(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_template(reports_dir)
    filled = _write_filled(reports_dir)
    _write_ingestion_result(reports_dir, session_valid=True)
    _write_ledger(reports_dir, filled)

    outputs = save_phase20f_manual_paper_session_rollover(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    status = outputs["manual_paper_session_rollover_status"].iloc[0]
    archive_path = Path(str(status["archive_path"]))
    archive_index = outputs["manual_paper_session_archive_index"]
    assert status["rollover_action"] == "valid_session_archived"
    assert archive_path.exists()
    assert len(pd.read_csv(archive_path)) == len(filled)
    assert len(archive_index) == 1
    assert archive_index.iloc[0]["archive_status"] == "archived"


def test_invalid_filled_file_is_not_archived(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_template(reports_dir)
    _write_filled(reports_dir)
    _write_ingestion_result(reports_dir, session_valid=False)

    outputs = save_phase20f_manual_paper_session_rollover(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    status = outputs["manual_paper_session_rollover_status"].iloc[0]
    assert status["rollover_action"] == "invalid_filled_file_manual_review_required"
    assert str(status["archive_path"]) == ""
    assert outputs["manual_paper_session_archive_index"].empty


def test_next_session_runbook_and_dashboard_are_written_with_safety_language(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_template(reports_dir)

    save_phase20f_manual_paper_session_rollover(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    manual_dir = reports_dir / "paper_trading" / "manual_sessions"
    dashboard_path = (
        reports_dir
        / "paper_trading"
        / "dashboard"
        / "manual_paper_session_rollover_status.csv"
    )
    runbook = (manual_dir / "manual_paper_next_session_runbook.md").read_text(
        encoding="utf-8"
    )
    dashboard = pd.read_csv(dashboard_path).iloc[0]
    for text in [
        "NO LIVE TRADING",
        "NO REAL MONEY",
        "NO BROKER/API",
        "MANUAL PAPER ONLY",
        "THIS TRACKS PROCESS DISCIPLINE",
    ]:
        assert text in runbook
    assert not bool(dashboard["live_trading_allowed"])
    assert not bool(dashboard["real_money_allowed"])
    assert not bool(dashboard["broker_api_integration_allowed"])
