from pathlib import Path

import pandas as pd

import market_strats.run_backtest as run_backtest
from market_strats.analysis.regime_informed_session_rollover import (
    save_phase21g_regime_informed_session_rollover,
)


def _config(tmp_path: Path) -> dict:
    return {
        "phase21g_regime_informed_session_rollover": {
            "enabled": True,
            "output_dir": str(tmp_path / "tracking"),
            "dashboard_dir": str(tmp_path / "dashboard"),
            "archive_dir": str(tmp_path / "tracking" / "archive"),
            "template_filename": "regime_informed_manual_session_template.csv",
            "filled_filename": "regime_informed_manual_session_filled.csv",
            "ledger_filename": "regime_informed_manual_session_ledger.csv",
            "archive_completed_valid_sessions": True,
            "stale_filled_file_policy": "block_current_ingestion",
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        }
    }


def _session_rows(session_date: str = "2026-06-11", signal_date: str = "2026-06-08"):
    return pd.DataFrame(
        [
            {
                "session_date": session_date,
                "selected_signal_date": signal_date,
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "asset": "SPY",
                "manual_execution_status": "skipped",
            }
        ]
    )


def _write_base(tmp_path: Path, *, filled: bool = True, stale: bool = False, valid: bool = True, ingested: bool = False) -> Path:
    tracking = tmp_path / "tracking"
    tracking.mkdir(parents=True, exist_ok=True)
    template = _session_rows()
    template.to_csv(tracking / "regime_informed_manual_session_template.csv", index=False)
    filled_rows = _session_rows("2026-06-10" if stale else "2026-06-11")
    if filled:
        filled_rows.to_csv(tracking / "regime_informed_manual_session_filled.csv", index=False)
    pd.DataFrame(
        [
            {
                "session_date": "2026-06-11",
                "selected_signal_date": "2026-06-08",
                "session_valid": valid,
            }
        ]
    ).to_csv(tracking / "regime_informed_session_validation.csv", index=False)
    if ingested:
        filled_rows.to_csv(tracking / "regime_informed_manual_session_ledger.csv", index=False)
    else:
        pd.DataFrame(columns=filled_rows.columns).to_csv(
            tracking / "regime_informed_manual_session_ledger.csv",
            index=False,
        )
    return tracking


def test_no_filled_file_writes_pending_rollover_status(tmp_path):
    _write_base(tmp_path, filled=False)

    outputs = save_phase21g_regime_informed_session_rollover(
        config=_config(tmp_path),
        reports_dir=tmp_path,
    )

    status = outputs["rollover_status"]
    assert not status.loc[0, "filled_file_present"]
    assert status.loc[0, "rollover_action"] == "no_filled_file_pending_user_entries"


def test_current_matching_filled_file_available_for_ingestion(tmp_path):
    _write_base(tmp_path, filled=True, valid=True, ingested=False)

    outputs = save_phase21g_regime_informed_session_rollover(
        config=_config(tmp_path),
        reports_dir=tmp_path,
    )

    status = outputs["rollover_status"]
    assert status.loc[0, "filled_matches_current_template"]
    assert not status.loc[0, "filled_already_ingested"]
    assert status.loc[0, "rollover_action"] == "current_filled_file_available_for_ingestion"


def test_valid_already_ingested_filled_file_is_archived(tmp_path):
    _write_base(tmp_path, filled=True, valid=True, ingested=True)

    outputs = save_phase21g_regime_informed_session_rollover(
        config=_config(tmp_path),
        reports_dir=tmp_path,
    )

    status = outputs["rollover_status"]
    archive_path = Path(status.loc[0, "archive_path"])
    assert status.loc[0, "filled_already_ingested"]
    assert status.loc[0, "rollover_action"] == "valid_already_ingested_session_archived"
    assert archive_path.exists()
    assert not outputs["archive_index"].empty


def test_stale_filled_file_is_blocked(tmp_path):
    _write_base(tmp_path, filled=True, stale=True, valid=True, ingested=False)

    outputs = save_phase21g_regime_informed_session_rollover(
        config=_config(tmp_path),
        reports_dir=tmp_path,
    )

    status = outputs["rollover_status"]
    assert status.loc[0, "filled_session_stale"]
    assert status.loc[0, "rollover_action"] == "stale_filled_file_blocked"


def test_invalid_filled_file_is_not_archived(tmp_path):
    _write_base(tmp_path, filled=True, valid=False, ingested=True)

    outputs = save_phase21g_regime_informed_session_rollover(
        config=_config(tmp_path),
        reports_dir=tmp_path,
    )

    status = outputs["rollover_status"]
    assert status.loc[0, "rollover_action"] == "invalid_filled_file_manual_review_required"
    assert status.loc[0, "archive_path"] == ""


def test_runbook_and_dashboard_include_safety_language(tmp_path):
    tracking = _write_base(tmp_path, filled=False)

    save_phase21g_regime_informed_session_rollover(
        config=_config(tmp_path),
        reports_dir=tmp_path,
    )

    runbook = (tracking / "regime_informed_next_session_runbook.md").read_text(
        encoding="utf-8"
    )
    assert "NO LIVE TRADING" in runbook
    assert "NO REAL MONEY" in runbook
    assert "NO BROKER/API" in runbook
    assert "NO STRATEGY PROMOTION" in runbook
    assert "MANUAL PAPER ONLY" in runbook
    assert (tmp_path / "dashboard" / "regime_informed_session_rollover_status.csv").exists()


def test_daily_runner_calls_phase21g_before_phase21e():
    source = Path(run_backtest.__file__).read_text(encoding="utf-8")
    phase21g_call = source.index(
        "_run_phase21g_regime_informed_session_rollover(config=config, reports_dir=reports_dir)"
    )
    phase21e_call = source.index(
        "_run_phase21e_regime_informed_session_ingestion(config=config, reports_dir=reports_dir)"
    )
    assert phase21g_call < phase21e_call
