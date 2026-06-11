from pathlib import Path

import pandas as pd

from market_strats.analysis.regime_informed_session_ingestion import (
    FILLED_REQUIRED_COLUMNS,
    ROW_VALIDATION_COLUMNS,
    save_phase21e_regime_informed_session_ingestion,
    validate_regime_informed_filled_session,
)


def _template() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "session_date": "2026-06-11",
                "selected_signal_date": "2026-06-08",
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "candidate_role": "provisional_core_candidate",
                "asset": "SPY",
                "target_weight": 1.0,
                "target_notional_usd": 10000.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "original defensive overlay baseline; paper-only",
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
            },
            {
                "session_date": "2026-06-11",
                "selected_signal_date": "2026-06-08",
                "canonical_candidate_id": "canonical_spy_qqq_gld_tlt_50_30_10_10",
                "candidate_role": "provisional_core_inception_limited",
                "asset": "GLD",
                "target_weight": 0.1,
                "target_notional_usd": 1000.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "multi-asset survivability candidate; inception-limited",
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
            },
            {
                "session_date": "2026-06-11",
                "selected_signal_date": "2026-06-08",
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "provisional_high_caveat_candidate",
                "asset": "BTC-USD",
                "target_weight": 0.05,
                "target_notional_usd": 500.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "BTC high-caveat; inception-limited; paper-only",
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
            },
            {
                "session_date": "2026-06-11",
                "selected_signal_date": "2026-06-08",
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "candidate_role": "reference_only",
                "asset": "QQQ",
                "target_weight": 0.4,
                "target_notional_usd": 4000.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "reference-only growth benchmark; severe drawdown risk",
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
            },
        ]
    )


def _filled_skip(**overrides) -> pd.DataFrame:
    filled = _template()[FILLED_REQUIRED_COLUMNS].copy()
    filled["tear_sheet_reviewed"] = True
    filled["warnings_acknowledged"] = True
    filled["btc_caveat_acknowledged"] = True
    filled["reference_only_acknowledged"] = True
    filled["inception_limited_acknowledged"] = True
    filled["manual_decision"] = "skip_due_warning"
    filled["manual_execution_status"] = "skipped"
    filled["override_reason"] = "BTC warning reviewed; skipping manually."
    filled["notes"] = "Manual paper only."
    for column, value in overrides.items():
        filled[column] = value
    return filled


def _filled_entered() -> pd.DataFrame:
    filled = _filled_skip()
    filled["manual_decision"] = "enter_paper_trade"
    filled["manual_execution_status"] = "entered"
    filled["paper_fill_price"] = [100.0, 200.0, 50.0, 400.0]
    filled["paper_fill_quantity"] = [100.0, 5.0, 10.0, 10.0]
    filled["override_reason"] = ""
    filled["notes"] = "Entered in paper account."
    return filled


def _write_sources(tmp_path: Path, *, filled: pd.DataFrame | None = None) -> dict:
    tracking_dir = tmp_path / "paper_trading" / "regime_informed_tracking"
    dashboard_dir = tmp_path / "paper_trading" / "dashboard"
    tracking_dir.mkdir(parents=True)
    dashboard_dir.mkdir(parents=True)
    template = _template()
    template.to_csv(tracking_dir / "regime_informed_manual_session_template.csv", index=False)
    template.to_csv(tracking_dir / "regime_informed_paper_orders_preview.csv", index=False)
    pd.DataFrame(
        [
            {
                "decision_date": "2026-06-11",
                "selected_signal_date": "2026-06-08",
                "decision_file_present": True,
                "adoption_decision": "adopt_regime_informed_shortlist",
                "adoption_valid": True,
                "adoption_status": "regime_informed_shortlist_adopted_manual_paper_only",
                "blocking_reasons": "",
                "requires_manual_adoption": True,
                "phase20_outputs_modified": False,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    ).to_csv(tracking_dir / "regime_informed_adoption_validation.csv", index=False)
    pd.DataFrame(
        [
            {
                "tracking_date": "2026-06-11",
                "selected_signal_date": "2026-06-08",
                "adoption_valid": True,
                "active_regime_informed_tracking": True,
                "manual_session_template_written": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    ).to_csv(tracking_dir / "regime_informed_active_tracking_status.csv", index=False)
    pd.DataFrame(
        [
            {"category": "quality", "key": "warnings_present", "value": "True"},
            {"category": "quality", "key": "warning_symbols", "value": "BTC-USD"},
        ]
    ).to_csv(tracking_dir / "regime_informed_daily_tracking_tear_sheet.csv", index=False)
    if filled is not None:
        filled.to_csv(tracking_dir / "regime_informed_manual_session_filled.csv", index=False)
    return {
        "phase21e_regime_informed_session_ingestion": {
            "enabled": True,
            "output_dir": str(tracking_dir),
            "dashboard_dir": str(dashboard_dir),
            "template_filename": "regime_informed_manual_session_template.csv",
            "filled_filename": "regime_informed_manual_session_filled.csv",
            "ledger_filename": "regime_informed_manual_session_ledger.csv",
            "require_adoption_valid": True,
            "require_tear_sheet_review": True,
            "require_warning_acknowledgement": True,
            "require_btc_ack_when_btc_weight_positive": True,
            "require_reference_ack_for_reference_only": True,
            "require_inception_ack_for_inception_limited": True,
            "require_reason_for_skipped_or_blocked": True,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        }
    }


def test_missing_adoption_or_template_fails_closed(tmp_path):
    outputs = save_phase21e_regime_informed_session_ingestion(
        config={
            "phase21e_regime_informed_session_ingestion": {
                "enabled": True,
                "output_dir": str(tmp_path / "missing"),
                "dashboard_dir": str(tmp_path / "dashboard"),
            }
        },
        reports_dir=tmp_path,
    )

    assert (
        outputs["summary"].iloc[0]["phase21e_decision"]
        == "regime_informed_session_ingestion_failed_missing_adoption_or_template"
    )


def test_missing_filled_file_creates_pending_status(tmp_path):
    outputs = save_phase21e_regime_informed_session_ingestion(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    validation = outputs["regime_informed_session_validation"].iloc[0]

    assert validation["validation_status"] == "pending_user_entries"
    assert not bool(validation["filled_file_present"])
    assert outputs["regime_informed_manual_session_ledger"].empty


def test_valid_skipped_session_passes_and_appends_ledger(tmp_path):
    outputs = save_phase21e_regime_informed_session_ingestion(
        config=_write_sources(tmp_path, filled=_filled_skip()),
        reports_dir=tmp_path,
    )

    assert bool(outputs["regime_informed_session_validation"].iloc[0]["session_valid"])
    assert len(outputs["regime_informed_manual_session_ledger"]) == len(_template())
    assert (
        outputs["regime_informed_session_discipline_summary"].iloc[0]["discipline_status"]
        == "valid_manual_paper_discipline_session"
    )


def test_valid_entered_session_computes_notional_and_deviation(tmp_path):
    outputs = save_phase21e_regime_informed_session_ingestion(
        config=_write_sources(tmp_path, filled=_filled_entered()),
        reports_dir=tmp_path,
    )
    ledger = outputs["regime_informed_manual_session_ledger"]
    spy = ledger[ledger["asset"] == "SPY"].iloc[0]

    assert float(spy["actual_notional_usd"]) == 10000.0
    assert float(spy["deviation_from_preview_usd"]) == 0.0


def test_missing_btc_acknowledgement_fails_btc_rows():
    filled = _filled_skip()
    filled.loc[filled["asset"] == "BTC-USD", "btc_caveat_acknowledged"] = False

    rows = validate_regime_informed_filled_session(
        filled_session=filled,
        template=_template(),
        warnings_present=True,
    )
    btc = rows[rows["asset"] == "BTC-USD"].iloc[0]

    assert not bool(btc["row_valid"])
    assert "btc_caveat_acknowledgement_missing" in btc["row_blocking_reasons"]


def test_missing_reference_only_acknowledgement_fails_reference_rows():
    filled = _filled_skip()
    filled.loc[filled["candidate_role"] == "reference_only", "reference_only_acknowledged"] = False

    rows = validate_regime_informed_filled_session(
        filled_session=filled,
        template=_template(),
        warnings_present=True,
    )
    reference = rows[rows["candidate_role"] == "reference_only"].iloc[0]

    assert not bool(reference["row_valid"])
    assert "reference_only_acknowledgement_missing" in reference["row_blocking_reasons"]


def test_missing_inception_acknowledgement_fails_relevant_rows():
    filled = _filled_skip()
    filled.loc[
        filled["candidate_role"] == "provisional_core_inception_limited",
        "inception_limited_acknowledged",
    ] = False

    rows = validate_regime_informed_filled_session(
        filled_session=filled,
        template=_template(),
        warnings_present=True,
    )
    inception = rows[rows["candidate_role"] == "provisional_core_inception_limited"].iloc[0]

    assert not bool(inception["row_valid"])
    assert "inception_limited_acknowledgement_missing" in inception["row_blocking_reasons"]


def test_skipped_row_without_reason_fails():
    filled = _filled_skip()
    filled["override_reason"] = ""
    filled["notes"] = ""

    rows = validate_regime_informed_filled_session(
        filled_session=filled,
        template=_template(),
        warnings_present=True,
    )

    assert not bool(rows["row_valid"].all())
    assert "skip_or_block_reason_or_notes_missing" in ";".join(
        rows["row_blocking_reasons"].astype(str)
    )


def test_safety_flags_must_be_false():
    filled = _filled_skip(live_trading_allowed=True)

    rows = validate_regime_informed_filled_session(
        filled_session=filled,
        template=_template(),
        warnings_present=True,
    )

    assert "live_trading_flag_true" in ";".join(rows["row_blocking_reasons"].astype(str))


def test_invalid_rows_do_not_append_to_ledger(tmp_path):
    outputs = save_phase21e_regime_informed_session_ingestion(
        config=_write_sources(tmp_path, filled=_filled_skip(notes="", override_reason="")),
        reports_dir=tmp_path,
    )

    assert not bool(outputs["regime_informed_session_validation"].iloc[0]["session_valid"])
    assert outputs["regime_informed_manual_session_ledger"].empty


def test_ledger_dedupes_by_session_signal_candidate_asset(tmp_path):
    config = _write_sources(tmp_path, filled=_filled_skip())
    first = save_phase21e_regime_informed_session_ingestion(config=config, reports_dir=tmp_path)
    second = save_phase21e_regime_informed_session_ingestion(config=config, reports_dir=tmp_path)

    assert len(first["regime_informed_manual_session_ledger"]) == len(_template())
    assert len(second["regime_informed_manual_session_ledger"]) == len(_template())


def test_dashboard_status_is_written(tmp_path):
    outputs = save_phase21e_regime_informed_session_ingestion(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    dashboard_path = (
        tmp_path / "paper_trading" / "dashboard" / "regime_informed_session_ingestion_status.csv"
    )

    assert dashboard_path.exists()
    assert outputs["regime_informed_session_row_validation"].columns.tolist() == ROW_VALIDATION_COLUMNS
