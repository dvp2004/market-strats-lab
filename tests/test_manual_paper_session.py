from pathlib import Path

import pandas as pd

from market_strats.analysis.manual_paper_session import (
    SESSION_TEMPLATE_COLUMNS,
    build_manual_session_checklist,
    build_manual_session_template,
    save_phase20c_manual_paper_session,
    validate_manual_session,
)


def _orders() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "candidate_role": "primary_paper_candidate_clean_growth",
                "asset": "SPY",
                "target_weight": 0.60,
                "target_notional_usd": 6000.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "severe historical drawdown; not defensive",
            },
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "candidate_role": "primary_paper_candidate_clean_growth",
                "asset": "QQQ",
                "target_weight": 0.40,
                "target_notional_usd": 4000.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "severe historical drawdown; not defensive",
            },
            {
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "high_growth_high_caveat_btc_candidate",
                "asset": "SPY",
                "target_weight": 0.50,
                "target_notional_usd": 5000.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "BTC weekend/gap risk; BTC allocation caveat",
            },
            {
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "high_growth_high_caveat_btc_candidate",
                "asset": "QQQ",
                "target_weight": 0.45,
                "target_notional_usd": 4500.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "BTC weekend/gap risk; BTC allocation caveat",
            },
            {
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "high_growth_high_caveat_btc_candidate",
                "asset": "BTC-USD",
                "target_weight": 0.05,
                "target_notional_usd": 500.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "BTC weekend/gap risk; BTC allocation caveat",
            },
        ]
    )


def _targets() -> pd.DataFrame:
    targets = _orders().copy()
    targets["btc_capable_candidate"] = targets["canonical_candidate_id"].str.contains(
        "btc",
        case=False,
    )
    targets["current_btc_weight"] = targets.apply(
        lambda row: 0.05
        if row["canonical_candidate_id"] == "canonical_inverse_vol_63d_btc_usd_qqq_spy"
        else 0.0,
        axis=1,
    )
    return targets


def _config(reports_dir: Path) -> dict:
    return {
        "phase20c_manual_paper_session": {
            "enabled": True,
            "output_dir": str(reports_dir / "paper_trading" / "manual_sessions"),
            "dashboard_dir": str(reports_dir / "paper_trading" / "dashboard"),
            "source_finalist_tracking_dir": str(
                reports_dir / "paper_trading" / "finalist_tracking"
            ),
            "source_cycle_tracker_dir": str(
                reports_dir / "paper_trading" / "cycle_tracker"
            ),
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "require_tear_sheet_review_acknowledgement": True,
            "require_warning_acknowledgement": True,
            "require_btc_acknowledgement_when_btc_weight_positive": True,
            "require_manual_decision": True,
            "require_fill_fields_only_if_entered": True,
        }
    }


def _write_sources(reports_dir: Path, *, warnings: bool = True) -> None:
    finalist_dir = reports_dir / "paper_trading" / "finalist_tracking"
    dashboard_dir = reports_dir / "paper_trading" / "dashboard"
    cycle_dir = reports_dir / "paper_trading" / "cycle_tracker"
    finalist_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    cycle_dir.mkdir(parents=True, exist_ok=True)

    _targets().to_csv(finalist_dir / "finalist_paper_targets.csv", index=False)
    _orders().to_csv(finalist_dir / "finalist_paper_orders_preview.csv", index=False)
    pd.DataFrame(
        [
            {"key": "warning_symbols", "value": "BTC-USD" if warnings else "none"},
            {"key": "final_instruction", "value": "WARNINGS PRESENT"},
        ]
    ).to_csv(finalist_dir / "finalist_daily_tracking_tear_sheet.csv", index=False)
    (finalist_dir / "finalist_daily_tracking_tear_sheet.md").write_text(
        "NO LIVE TRADING\nNO REAL MONEY\nNO BROKER/API\nMANUAL PAPER TRACKING ONLY",
        encoding="utf-8",
    )
    pd.DataFrame(columns=["journal_date", "canonical_candidate_id"]).to_csv(
        finalist_dir / "finalist_manual_paper_journal_template.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "phase20a_decision": "paper_finalist_tracking_written_manual_preview_only",
                "tracking_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "data_quality_status": "warning" if warnings else "pass",
                "warning_symbols": "BTC-USD" if warnings else "none",
                "blocking_symbols": "none",
            }
        ]
    ).to_csv(dashboard_dir / "finalist_tracking_status.csv", index=False)
    pd.DataFrame(
        [
            {
                "cycle_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "warning_symbols": "BTC-USD" if warnings else "none",
            }
        ]
    ).to_csv(cycle_dir / "paper_cycle_latest.csv", index=False)


def test_missing_finalist_tracking_source_fails_closed(tmp_path):
    reports_dir = tmp_path / "reports"

    outputs = save_phase20c_manual_paper_session(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    summary = outputs["summary"]
    assert summary.iloc[0]["phase20c_decision"] == "manual_paper_session_failed_closed"
    assert "missing_sources" in summary.columns
    assert (reports_dir / "paper_trading" / "manual_sessions" / "phase20c_summary.csv").exists()


def test_manual_session_template_status_and_dashboard_are_written(tmp_path):
    reports_dir = tmp_path / "reports"
    _write_sources(reports_dir)

    outputs = save_phase20c_manual_paper_session(
        config=_config(reports_dir),
        reports_dir=reports_dir,
    )

    output_dir = reports_dir / "paper_trading" / "manual_sessions"
    dashboard_path = reports_dir / "paper_trading" / "dashboard" / "manual_paper_session_status.csv"
    template = pd.read_csv(output_dir / "manual_paper_session_template.csv")
    status = pd.read_csv(output_dir / "manual_paper_session_status.csv")
    dashboard = pd.read_csv(dashboard_path)

    assert list(template.columns) == SESSION_TEMPLATE_COLUMNS
    assert len(template) == len(_orders())
    assert status.iloc[0]["session_complete"] is False or not bool(
        status.iloc[0]["session_complete"]
    )
    assert status.iloc[0]["candidate_count"] == 2
    assert status.iloc[0]["warnings_present"] is True or bool(
        status.iloc[0]["warnings_present"]
    )
    assert status.iloc[0]["btc_positive_weight_present"] is True or bool(
        status.iloc[0]["btc_positive_weight_present"]
    )
    assert dashboard.iloc[0]["phase20c_decision"] == outputs["summary"].iloc[0][
        "phase20c_decision"
    ]
    assert not bool(status.iloc[0]["live_trading_allowed"])
    assert not bool(status.iloc[0]["real_money_allowed"])
    assert not bool(status.iloc[0]["broker_api_integration_allowed"])


def test_checklist_includes_required_safety_language():
    checklist = build_manual_session_checklist()

    assert "NO LIVE TRADING" in checklist
    assert "NO REAL MONEY" in checklist
    assert "NO BROKER/API" in checklist
    assert "MANUAL PAPER ONLY" in checklist
    assert "THIS DOES NOT TEST PERFORMANCE" in checklist
    assert "THIS ONLY TESTS PROCESS DISCIPLINE" in checklist


def test_initial_blank_template_requires_acknowledgements_and_decisions():
    template = build_manual_session_template(
        orders=_orders(),
        session_date="2026-06-10",
        selected_signal_date="2026-06-08",
    )

    validation = validate_manual_session(
        session=template,
        warnings_present=True,
        btc_positive_weight_present=True,
        config=_config(Path("reports"))["phase20c_manual_paper_session"],
        filled_session_file_present=False,
    )

    assert not bool(validation["session_complete"].iloc[0])
    blockers = ";".join(validation["blocking_reasons"].astype(str).tolist())
    assert "tear_sheet_review_missing" in blockers
    assert "warning_acknowledgement_missing" in blockers
    assert "manual_decision_pending" in blockers
    assert "btc_caveat_acknowledgement_missing" in blockers


def test_filled_session_missing_acknowledgement_fails_validation():
    session = build_manual_session_template(
        orders=_orders().head(1),
        session_date="2026-06-10",
        selected_signal_date="2026-06-08",
    )
    session.loc[0, "manual_decision"] = "skip_user_choice"
    session.loc[0, "manual_execution_status"] = "skipped"
    session.loc[0, "override_reason"] = "manual dry run not entered yet"

    validation = validate_manual_session(
        session=session,
        warnings_present=True,
        btc_positive_weight_present=False,
        config=_config(Path("reports"))["phase20c_manual_paper_session"],
        filled_session_file_present=True,
    )

    assert not bool(validation["session_complete"].iloc[0])
    assert "tear_sheet_review_missing" in validation.iloc[0]["blocking_reasons"]
    assert "warning_acknowledgement_missing" in validation.iloc[0]["blocking_reasons"]


def test_entered_trade_requires_positive_fill_price_and_quantity():
    session = build_manual_session_template(
        orders=_orders().head(1),
        session_date="2026-06-10",
        selected_signal_date="2026-06-08",
    )
    session.loc[0, "tear_sheet_reviewed"] = True
    session.loc[0, "warnings_acknowledged"] = True
    session.loc[0, "manual_decision"] = "enter_paper_trade"
    session.loc[0, "manual_execution_status"] = "entered"

    validation = validate_manual_session(
        session=session,
        warnings_present=True,
        btc_positive_weight_present=False,
        config=_config(Path("reports"))["phase20c_manual_paper_session"],
        filled_session_file_present=True,
    )

    blockers = validation.iloc[0]["blocking_reasons"]
    assert "paper_fill_price_missing_or_non_positive" in blockers
    assert "paper_fill_quantity_missing_or_non_positive" in blockers


def test_skipped_trade_requires_reason_or_notes():
    session = build_manual_session_template(
        orders=_orders().head(1),
        session_date="2026-06-10",
        selected_signal_date="2026-06-08",
    )
    session.loc[0, "tear_sheet_reviewed"] = True
    session.loc[0, "warnings_acknowledged"] = True
    session.loc[0, "manual_decision"] = "skip_user_choice"
    session.loc[0, "manual_execution_status"] = "skipped"

    validation = validate_manual_session(
        session=session,
        warnings_present=True,
        btc_positive_weight_present=False,
        config=_config(Path("reports"))["phase20c_manual_paper_session"],
        filled_session_file_present=True,
    )

    assert "skip_reason_or_notes_missing" in validation.iloc[0]["blocking_reasons"]


def test_valid_filled_session_passes_validation_and_computes_deviation():
    order = _orders().loc[lambda frame: frame["asset"] == "BTC-USD"].head(1)
    session = build_manual_session_template(
        orders=order,
        session_date="2026-06-10",
        selected_signal_date="2026-06-08",
    )
    session.loc[0, "tear_sheet_reviewed"] = True
    session.loc[0, "warnings_acknowledged"] = True
    session.loc[0, "btc_caveat_acknowledged"] = True
    session.loc[0, "manual_decision"] = "enter_paper_trade"
    session.loc[0, "manual_execution_status"] = "entered"
    session.loc[0, "paper_fill_price"] = "100.0"
    session.loc[0, "paper_fill_quantity"] = "5.0"

    validation = validate_manual_session(
        session=session,
        warnings_present=True,
        btc_positive_weight_present=True,
        config=_config(Path("reports"))["phase20c_manual_paper_session"],
        filled_session_file_present=True,
    )

    assert bool(validation.iloc[0]["row_valid"])
    assert bool(validation.iloc[0]["session_complete"])
    assert validation.iloc[0]["actual_notional_usd"] == 500.0
    assert validation.iloc[0]["deviation_from_preview_usd"] == 0.0
