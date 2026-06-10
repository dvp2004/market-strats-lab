from pathlib import Path

import pandas as pd

from market_strats.analysis.manual_paper_session_ingestion import (
    LEDGER_COLUMNS,
    save_phase20d_manual_paper_session_ingestion,
)


def _config(reports_dir: Path) -> dict:
    return {
        "phase20d_manual_paper_session_ingestion": {
            "enabled": True,
            "output_dir": str(reports_dir / "paper_trading" / "manual_sessions"),
            "dashboard_dir": str(reports_dir / "paper_trading" / "dashboard"),
            "source_manual_session_dir": str(
                reports_dir / "paper_trading" / "manual_sessions"
            ),
            "source_finalist_tracking_dir": str(
                reports_dir / "paper_trading" / "finalist_tracking"
            ),
            "filled_session_filename": "manual_paper_session_filled.csv",
            "ledger_filename": "manual_paper_session_ledger.csv",
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        }
    }


def _template_rows() -> list[dict]:
    return [
        {
            "session_date": "2026-06-10",
            "selected_signal_date": "2026-06-08",
            "canonical_candidate_id": "canonical_spy_qqq_60_40",
            "candidate_role": "primary_paper_candidate_clean_growth",
            "asset": "SPY",
            "target_weight": 0.60,
            "target_notional_usd": 6000.0,
            "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
            "paper_order_allowed": True,
            "candidate_caveats": "severe historical drawdown; not defensive",
            "tear_sheet_reviewed": False,
            "warnings_acknowledged": False,
            "btc_caveat_acknowledged": False,
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
        },
        {
            "session_date": "2026-06-10",
            "selected_signal_date": "2026-06-08",
            "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
            "candidate_role": "high_growth_high_caveat_btc_candidate",
            "asset": "BTC-USD",
            "target_weight": 0.05,
            "target_notional_usd": 500.0,
            "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
            "paper_order_allowed": True,
            "candidate_caveats": "BTC weekend/gap risk; BTC allocation caveat",
            "tear_sheet_reviewed": False,
            "warnings_acknowledged": False,
            "btc_caveat_acknowledged": False,
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
        },
    ]


def _write_required_sources(reports_dir: Path, *, warnings: bool = True) -> None:
    manual_dir = reports_dir / "paper_trading" / "manual_sessions"
    finalist_dir = reports_dir / "paper_trading" / "finalist_tracking"
    dashboard_dir = reports_dir / "paper_trading" / "dashboard"
    manual_dir.mkdir(parents=True, exist_ok=True)
    finalist_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    template = pd.DataFrame(_template_rows())
    template.to_csv(manual_dir / "manual_paper_session_template.csv", index=False)
    template.to_csv(finalist_dir / "finalist_paper_orders_preview.csv", index=False)
    pd.DataFrame(
        [
            {
                "category": "fresh_data_quality",
                "key": "warning_symbols",
                "value": "BTC-USD" if warnings else "none",
            }
        ]
    ).to_csv(finalist_dir / "finalist_daily_tracking_tear_sheet.csv", index=False)
    pd.DataFrame(
        [
            {
                "tracking_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "data_quality_status": "warning" if warnings else "pass",
                "warning_symbols": "BTC-USD" if warnings else "none",
                "blocking_symbols": "none",
            }
        ]
    ).to_csv(dashboard_dir / "finalist_tracking_status.csv", index=False)


def _filled_skip_session() -> pd.DataFrame:
    filled = pd.DataFrame(_template_rows())
    filled["tear_sheet_reviewed"] = True
    filled["warnings_acknowledged"] = True
    filled["btc_caveat_acknowledged"] = filled["asset"].eq("BTC-USD")
    filled["manual_decision"] = "skip_due_warning"
    filled["manual_execution_status"] = "skipped"
    filled["override_reason"] = "manual paper entry skipped for test"
    return filled


def _filled_entered_session() -> pd.DataFrame:
    filled = pd.DataFrame([_template_rows()[0]])
    filled["tear_sheet_reviewed"] = True
    filled["warnings_acknowledged"] = True
    filled["btc_caveat_acknowledged"] = False
    filled["manual_decision"] = "enter_paper_trade"
    filled["manual_execution_status"] = "entered"
    filled["paper_fill_price"] = 100.0
    filled["paper_fill_quantity"] = 61.0
    return filled


def test_missing_filled_file_writes_pending_status_but_passes_gate(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir)

    outputs = save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    result = outputs["manual_paper_session_ingestion_result"].iloc[0]
    gates = outputs["gate_report"]
    ledger_path = (
        reports_dir
        / "paper_trading"
        / "manual_sessions"
        / "manual_paper_session_ledger.csv"
    )

    assert result["filled_session_file_present"] is False or not bool(
        result["filled_session_file_present"]
    )
    assert result["session_ingestion_status"] == "pending_user_entries"
    assert not bool(result["session_valid"])
    assert bool(gates["passed"].all())
    assert ledger_path.exists()
    assert list(pd.read_csv(ledger_path).columns) == LEDGER_COLUMNS


def test_valid_filled_skip_session_passes_validation_and_updates_ledger(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir)
    filled_path = (
        reports_dir
        / "paper_trading"
        / "manual_sessions"
        / "manual_paper_session_filled.csv"
    )
    _filled_skip_session().to_csv(filled_path, index=False)

    outputs = save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    result = outputs["manual_paper_session_ingestion_result"].iloc[0]
    ledger = outputs["manual_paper_session_ledger"]
    assert result["session_ingestion_status"] == "valid_manual_paper_session"
    assert bool(result["session_valid"])
    assert int(result["rows_valid"]) == 2
    assert len(ledger) == 2
    assert not ledger["live_trading_allowed"].map(bool).any()
    assert not ledger["real_money_allowed"].map(bool).any()
    assert not ledger["broker_api_integration_allowed"].map(bool).any()


def test_valid_entered_session_computes_actual_notional_and_deviation(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir, warnings=False)
    manual_dir = reports_dir / "paper_trading" / "manual_sessions"
    pd.DataFrame([_template_rows()[0]]).to_csv(
        manual_dir / "manual_paper_session_template.csv",
        index=False,
    )
    _filled_entered_session().to_csv(
        manual_dir / "manual_paper_session_filled.csv",
        index=False,
    )

    outputs = save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    row_validation = outputs["manual_paper_session_row_validation"].iloc[0]
    assert bool(row_validation["row_valid"])
    assert row_validation["actual_notional_usd"] == 6100.0
    assert row_validation["deviation_from_preview_usd"] == 100.0
    assert round(float(row_validation["deviation_from_preview_pct"]), 4) == 1.6667


def test_missing_tear_sheet_acknowledgement_fails_validation(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir)
    filled = _filled_skip_session()
    filled["tear_sheet_reviewed"] = False
    filled.to_csv(
        reports_dir
        / "paper_trading"
        / "manual_sessions"
        / "manual_paper_session_filled.csv",
        index=False,
    )

    outputs = save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    row_validation = outputs["manual_paper_session_row_validation"]
    assert not row_validation["row_valid"].map(bool).all()
    assert "tear_sheet_review_missing" in ";".join(
        row_validation["row_blocking_reasons"].astype(str)
    )


def test_missing_warning_acknowledgement_fails_when_warnings_present(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir, warnings=True)
    filled = _filled_skip_session()
    filled["warnings_acknowledged"] = False
    filled.to_csv(
        reports_dir
        / "paper_trading"
        / "manual_sessions"
        / "manual_paper_session_filled.csv",
        index=False,
    )

    outputs = save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    assert "warning_acknowledgement_missing" in ";".join(
        outputs["manual_paper_session_row_validation"]["row_blocking_reasons"].astype(str)
    )


def test_missing_btc_acknowledgement_fails_when_btc_weight_positive(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir)
    filled = _filled_skip_session()
    filled["btc_caveat_acknowledged"] = False
    filled.to_csv(
        reports_dir
        / "paper_trading"
        / "manual_sessions"
        / "manual_paper_session_filled.csv",
        index=False,
    )

    outputs = save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    assert "btc_caveat_acknowledgement_missing" in ";".join(
        outputs["manual_paper_session_row_validation"]["row_blocking_reasons"].astype(str)
    )


def test_entered_row_missing_fill_price_or_quantity_fails(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir, warnings=False)
    manual_dir = reports_dir / "paper_trading" / "manual_sessions"
    pd.DataFrame([_template_rows()[0]]).to_csv(
        manual_dir / "manual_paper_session_template.csv",
        index=False,
    )
    filled = _filled_entered_session()
    filled["paper_fill_price"] = ""
    filled["paper_fill_quantity"] = ""
    filled.to_csv(manual_dir / "manual_paper_session_filled.csv", index=False)

    outputs = save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    blockers = outputs["manual_paper_session_row_validation"].iloc[0][
        "row_blocking_reasons"
    ]
    assert "paper_fill_price_missing_or_non_positive" in blockers
    assert "paper_fill_quantity_missing_or_non_positive" in blockers


def test_skipped_row_without_reason_or_notes_fails(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir)
    filled = _filled_skip_session()
    filled["override_reason"] = ""
    filled["notes"] = ""
    filled.to_csv(
        reports_dir
        / "paper_trading"
        / "manual_sessions"
        / "manual_paper_session_filled.csv",
        index=False,
    )

    outputs = save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    assert "skip_reason_or_notes_missing" in ";".join(
        outputs["manual_paper_session_row_validation"]["row_blocking_reasons"].astype(str)
    )


def test_ledger_dedupes_by_session_date_candidate_and_asset(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir)
    filled_path = (
        reports_dir
        / "paper_trading"
        / "manual_sessions"
        / "manual_paper_session_filled.csv"
    )
    _filled_skip_session().to_csv(filled_path, index=False)

    save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )
    outputs = save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    assert len(outputs["manual_paper_session_ledger"]) == 2


def test_dashboard_status_is_written_and_safety_flags_remain_false(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_required_sources(reports_dir)

    save_phase20d_manual_paper_session_ingestion(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    dashboard = pd.read_csv(
        reports_dir
        / "paper_trading"
        / "dashboard"
        / "manual_paper_session_ingestion_status.csv"
    )
    assert dashboard.iloc[0]["phase20d_decision"] == (
        "manual_paper_session_ingestion_pending_user_entries"
    )
    assert not bool(dashboard.iloc[0]["live_trading_allowed"])
    assert not bool(dashboard.iloc[0]["real_money_allowed"])
    assert not bool(dashboard.iloc[0]["broker_api_integration_allowed"])
