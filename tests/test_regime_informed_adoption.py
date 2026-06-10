from pathlib import Path

import pandas as pd

from market_strats.analysis.regime_informed_adoption import (
    ACK_COLUMNS,
    ADOPTION_REQUIRED_COLUMNS,
    save_phase21d_regime_informed_adoption,
    validate_adoption_decision,
)


def _targets() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tracking_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "candidate_role": "provisional_core_candidate",
                "asset": "SPY",
                "target_weight": 1.0,
                "target_notional_usd": 10000.0,
            },
            {
                "tracking_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "provisional_high_caveat_candidate",
                "asset": "BTC-USD",
                "target_weight": 0.05,
                "target_notional_usd": 500.0,
            },
        ]
    )


def _orders() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tracking_date": "2026-06-10",
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "candidate_role": "provisional_core_candidate",
                "asset": "SPY",
                "target_weight": 1.0,
                "target_notional_usd": 10000.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "paper-only",
            },
            {
                "tracking_date": "2026-06-10",
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "provisional_high_caveat_candidate",
                "asset": "BTC-USD",
                "target_weight": 0.05,
                "target_notional_usd": 500.0,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": "BTC high-caveat",
            },
        ]
    )


def _adoption_status() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tracking_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
                "requires_manual_adoption": True,
                "phase20_outputs_modified": False,
                "adoption_status": "pending_manual_review",
            }
        ]
    )


def _dashboard_status() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "phase21c_decision": "regime_informed_paper_tracking_shortlist_written_pending_manual_adoption",
                "tracking_date": "2026-06-10",
                "selected_signal_date": "2026-06-08",
            }
        ]
    )


def _tear_sheet() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"category": "instruction", "key": "final_instruction", "value": "WARNINGS PRESENT"},
            {"category": "signal", "key": "selected_signal_date", "value": "2026-06-08"},
        ]
    )


def _write_sources(tmp_path: Path) -> dict:
    tracking_dir = tmp_path / "paper_trading" / "regime_informed_tracking"
    dashboard_dir = tmp_path / "paper_trading" / "dashboard"
    tracking_dir.mkdir(parents=True)
    dashboard_dir.mkdir(parents=True)
    _targets().to_csv(tracking_dir / "regime_informed_paper_targets.csv", index=False)
    _orders().to_csv(tracking_dir / "regime_informed_paper_orders_preview.csv", index=False)
    _tear_sheet().to_csv(tracking_dir / "regime_informed_daily_tracking_tear_sheet.csv", index=False)
    _adoption_status().to_csv(
        tracking_dir / "regime_informed_tracking_adoption_status.csv",
        index=False,
    )
    _dashboard_status().to_csv(dashboard_dir / "regime_informed_tracking_status.csv", index=False)
    return {
        "phase21d_regime_informed_adoption": {
            "enabled": True,
            "output_dir": str(tracking_dir),
            "dashboard_dir": str(dashboard_dir),
            "source_regime_informed_tracking_dir": str(tracking_dir),
            "adoption_decision_filename": "regime_informed_adoption_decision.csv",
            "adoption_template_filename": "regime_informed_adoption_decision_template.csv",
            "manual_session_template_filename": "regime_informed_manual_session_template.csv",
            "manual_session_checklist_filename": "regime_informed_manual_session_checklist.md",
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
            "require_manual_adoption": True,
            "require_adoption_reason": True,
        }
    }


def _decision(decision: str = "adopt_regime_informed_shortlist", **overrides) -> pd.DataFrame:
    row = {
        "decision_date": "2026-06-10",
        "selected_signal_date": "2026-06-08",
        "regime_informed_shortlist_version": "phase21c_regime_informed_shortlist_v1",
        "candidate_count": 4,
        "adoption_decision": decision,
        "adoption_reason": "Manual review completed.",
        "acknowledge_no_live_trading": True,
        "acknowledge_no_real_money": True,
        "acknowledge_no_broker_api": True,
        "acknowledge_no_strategy_promotion": True,
        "acknowledge_reference_only_candidate": True,
        "acknowledge_btc_high_caveat": True,
        "acknowledge_severe_drawdown_caveat": True,
        "acknowledge_inception_limited_candidates": True,
        "reviewed_regime_informed_tear_sheet": True,
        "reviewed_phase21b_reconciliation": True,
        "notes": "",
    }
    row.update(overrides)
    return pd.DataFrame([row], columns=ADOPTION_REQUIRED_COLUMNS)


def test_missing_phase21c_outputs_fail_closed(tmp_path):
    outputs = save_phase21d_regime_informed_adoption(
        config={
            "phase21d_regime_informed_adoption": {
                "enabled": True,
                "output_dir": str(tmp_path / "out"),
                "dashboard_dir": str(tmp_path / "dashboard"),
                "source_regime_informed_tracking_dir": str(tmp_path / "missing"),
            }
        },
        reports_dir=tmp_path,
    )
    summary = pd.read_csv(outputs["summary"]).iloc[0]

    assert summary["phase21d_decision"] == "regime_informed_adoption_failed_missing_sources"


def test_adoption_decision_template_is_written(tmp_path):
    outputs = save_phase21d_regime_informed_adoption(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    template = pd.read_csv(outputs["adoption_template"])

    assert template.iloc[0]["adoption_decision"] == "pending"
    assert set(ADOPTION_REQUIRED_COLUMNS).issubset(template.columns)


def test_no_adoption_file_produces_pending_status(tmp_path):
    outputs = save_phase21d_regime_informed_adoption(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    validation = pd.read_csv(outputs["adoption_validation"]).iloc[0]

    assert not bool(validation["decision_file_present"])
    assert validation["adoption_status"] == "pending_manual_adoption"


def test_pending_decision_is_invalid(tmp_path):
    path = tmp_path / "regime_informed_adoption_decision.csv"
    _decision("pending").to_csv(path, index=False)

    validation = validate_adoption_decision(
        decision_path=path,
        targets=_targets(),
        adoption_status=_adoption_status(),
        require_adoption_reason=True,
        require_manual_adoption=True,
    ).iloc[0]

    assert not bool(validation["adoption_valid"])
    assert "adoption_decision_pending" in validation["blocking_reasons"]


def test_invalid_acknowledgement_fails_validation(tmp_path):
    path = tmp_path / "regime_informed_adoption_decision.csv"
    _decision(acknowledge_btc_high_caveat=False).to_csv(path, index=False)

    validation = validate_adoption_decision(
        decision_path=path,
        targets=_targets(),
        adoption_status=_adoption_status(),
        require_adoption_reason=True,
        require_manual_adoption=True,
    ).iloc[0]

    assert not bool(validation["adoption_valid"])
    assert "acknowledge_btc_high_caveat_required" in validation["blocking_reasons"]


def test_valid_adoption_decision_passes(tmp_path):
    path = tmp_path / "regime_informed_adoption_decision.csv"
    _decision().to_csv(path, index=False)

    validation = validate_adoption_decision(
        decision_path=path,
        targets=_targets(),
        adoption_status=_adoption_status(),
        require_adoption_reason=True,
        require_manual_adoption=True,
    ).iloc[0]

    assert bool(validation["adoption_valid"])
    assert validation["adoption_status"] == "regime_informed_shortlist_adopted_manual_paper_only"


def test_declined_decision_passes_but_does_not_activate(tmp_path):
    config = _write_sources(tmp_path)
    tracking_dir = Path(config["phase21d_regime_informed_adoption"]["output_dir"])
    _decision("decline_keep_phase20_shortlist").to_csv(
        tracking_dir / "regime_informed_adoption_decision.csv",
        index=False,
    )

    outputs = save_phase21d_regime_informed_adoption(config=config, reports_dir=tmp_path)
    active = pd.read_csv(outputs["active_tracking_status"]).iloc[0]

    assert active["adoption_status"] == "declined_keep_existing_phase20_tracking"
    assert not bool(active["active_regime_informed_tracking"])
    assert not bool(active["manual_session_template_written"])


def test_adopted_decision_writes_manual_session_template(tmp_path):
    config = _write_sources(tmp_path)
    tracking_dir = Path(config["phase21d_regime_informed_adoption"]["output_dir"])
    _decision().to_csv(tracking_dir / "regime_informed_adoption_decision.csv", index=False)

    outputs = save_phase21d_regime_informed_adoption(config=config, reports_dir=tmp_path)

    assert "manual_session_template" in outputs
    session = pd.read_csv(outputs["manual_session_template"])
    for column in [
        "btc_caveat_acknowledged",
        "reference_only_acknowledged",
        "inception_limited_acknowledged",
    ]:
        assert column in session.columns


def test_checklist_includes_required_safety_language(tmp_path):
    config = _write_sources(tmp_path)
    tracking_dir = Path(config["phase21d_regime_informed_adoption"]["output_dir"])
    _decision().to_csv(tracking_dir / "regime_informed_adoption_decision.csv", index=False)

    outputs = save_phase21d_regime_informed_adoption(config=config, reports_dir=tmp_path)
    text = outputs["manual_session_checklist"].read_text(encoding="utf-8")

    for phrase in [
        "NO LIVE TRADING",
        "NO REAL MONEY",
        "NO BROKER/API",
        "NO STRATEGY PROMOTION",
        "MANUAL PAPER ONLY",
        "THIS TRACKS PROCESS DISCIPLINE",
    ]:
        assert phrase in text


def test_phase20_outputs_not_modified_and_safety_flags_false(tmp_path):
    outputs = save_phase21d_regime_informed_adoption(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    status = pd.read_csv(outputs["active_tracking_status"]).iloc[0]
    conclusion = pd.read_csv(outputs["conclusion"]).iloc[0]

    assert not bool(status["phase20_outputs_modified"])
    assert not bool(conclusion["promotion_allowed"])
    assert not bool(conclusion["live_trading_allowed"])
    assert not bool(conclusion["real_money_allowed"])
    assert not bool(conclusion["broker_api_integration_allowed"])


def test_dashboard_status_is_written(tmp_path):
    outputs = save_phase21d_regime_informed_adoption(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )

    assert outputs["dashboard_status"].exists()
    dashboard = pd.read_csv(outputs["dashboard_status"])
    assert "phase21d_decision" in dashboard.columns


def test_all_ack_columns_are_required():
    assert "acknowledge_no_live_trading" in ACK_COLUMNS
    assert "reviewed_phase21b_reconciliation" in ACK_COLUMNS
