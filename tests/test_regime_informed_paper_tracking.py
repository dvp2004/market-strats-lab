from pathlib import Path

import pandas as pd

from market_strats.analysis.regime_informed_paper_tracking import (
    BTC_INVOL_ID,
    GLD_TLT_ID,
    PHASE6_ID,
    SPY_QQQ_60_40_ID,
    build_regime_informed_targets,
    save_phase21c_regime_informed_paper_tracking,
)


def _shortlist() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_candidate_id": PHASE6_ID,
                "recommended_role": "provisional_core_candidate",
            },
            {
                "canonical_candidate_id": GLD_TLT_ID,
                "recommended_role": "provisional_core_inception_limited",
            },
            {
                "canonical_candidate_id": BTC_INVOL_ID,
                "recommended_role": "provisional_high_caveat_candidate",
            },
            {
                "canonical_candidate_id": SPY_QQQ_60_40_ID,
                "recommended_role": "reference_only",
            },
        ]
    )


def _phase21a() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_candidate_id": PHASE6_ID,
                "master_strategy_classification": "provisional_core_candidate_for_further_research",
                "regime_robustness_score": 61.48,
            },
            {
                "canonical_candidate_id": GLD_TLT_ID,
                "master_strategy_classification": "provisional_core_inception_limited_for_further_research",
                "regime_robustness_score": 56.32,
            },
            {
                "canonical_candidate_id": BTC_INVOL_ID,
                "master_strategy_classification": "provisional_high_caveat_candidate_for_further_research",
                "regime_robustness_score": 51.82,
            },
            {
                "canonical_candidate_id": SPY_QQQ_60_40_ID,
                "master_strategy_classification": "rejected_regime_fragile",
                "regime_robustness_score": 13.39,
            },
        ]
    )


def _tear_sheet(signal: str = "mode=offensive_spy; exposure=1.0; action=risk_on_hold_preview") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"category": "signal", "key": "selected_signal_date", "value": "2026-06-08"},
            {"category": "baseline_phase6_signal", "key": "phase6_baseline_signal", "value": signal},
        ]
    )


def _quality(block_gld: bool = False) -> pd.DataFrame:
    rows = []
    for symbol in ["SPY", "QQQ", "GLD", "TLT"]:
        rows.append(
            {
                "symbol": symbol,
                "quality_status": "blocked" if block_gld and symbol == "GLD" else "",
                "warnings": "",
                "blocking_failures": "bad_price" if block_gld and symbol == "GLD" else "",
            }
        )
    rows.append(
        {
            "symbol": "BTC-USD",
            "quality_status": "warning",
            "warnings": "btc_weekend_data_available_common_date_caveat",
            "blocking_failures": "",
        }
    )
    return pd.DataFrame(rows)


def _dynamic() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_candidate_id": BTC_INVOL_ID,
                "asset": "SPY",
                "target_weight": 0.50,
                "allocation_status": "dynamic_allocation_resolved",
            },
            {
                "canonical_candidate_id": BTC_INVOL_ID,
                "asset": "QQQ",
                "target_weight": 0.45,
                "allocation_status": "dynamic_allocation_resolved",
            },
            {
                "canonical_candidate_id": BTC_INVOL_ID,
                "asset": "BTC-USD",
                "target_weight": 0.05,
                "allocation_status": "dynamic_allocation_resolved",
            },
        ]
    )


def _write_sources(tmp_path: Path) -> dict:
    reconciliation_dir = tmp_path / "strategy_factory" / "regime_reconciliation"
    regime_dir = tmp_path / "strategy_factory" / "regime_stress"
    tracking_dir = tmp_path / "paper_trading" / "finalist_tracking"
    hardening_dir = tmp_path / "paper_trading" / "operational_hardening"
    for directory in [reconciliation_dir, regime_dir, tracking_dir, hardening_dir]:
        directory.mkdir(parents=True)
    _shortlist().to_csv(reconciliation_dir / "phase21b_paper_shortlist_recommendation.csv", index=False)
    pd.DataFrame({"canonical_candidate_id": [SPY_QQQ_60_40_ID, BTC_INVOL_ID]}).to_csv(
        reconciliation_dir / "phase21b_current_paper_candidate_reconciliation.csv",
        index=False,
    )
    _phase21a().to_csv(regime_dir / "phase21a_master_strategy_candidates.csv", index=False)
    _phase21a().to_csv(regime_dir / "phase21a_regime_robustness_score_components.csv", index=False)
    _dynamic().to_csv(tracking_dir / "finalist_dynamic_allocations.csv", index=False)
    _tear_sheet().to_csv(hardening_dir / "daily_execution_tear_sheet.csv", index=False)
    _quality().to_csv(hardening_dir / "fresh_data_quality_report.csv", index=False)
    return {
        "phase21c_regime_informed_paper_tracking": {
            "enabled": True,
            "output_dir": str(tmp_path / "paper_trading" / "regime_informed_tracking"),
            "dashboard_dir": str(tmp_path / "paper_trading" / "dashboard"),
            "source_regime_reconciliation_dir": str(reconciliation_dir),
            "source_regime_stress_dir": str(regime_dir),
            "source_dynamic_allocation_dir": str(tracking_dir),
            "source_operational_hardening_dir": str(hardening_dir),
            "source_fresh_data_quality_report": str(
                hardening_dir / "fresh_data_quality_report.csv"
            ),
            "paper_notional_usd": 10000,
            "max_candidates": 4,
            "include_reference_only_candidate": True,
            "require_manual_adoption_before_replacing_phase20": True,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        }
    }


def test_missing_phase21b_recommendation_file_fails_closed(tmp_path):
    config = _write_sources(tmp_path)
    Path(
        config["phase21c_regime_informed_paper_tracking"]["source_regime_reconciliation_dir"],
        "phase21b_paper_shortlist_recommendation.csv",
    ).unlink()

    outputs = save_phase21c_regime_informed_paper_tracking(config=config, reports_dir=tmp_path)
    summary = pd.read_csv(outputs["summary"]).iloc[0]

    assert summary["phase21c_decision"] == "regime_informed_paper_tracking_failed_missing_sources"


def test_phase6_target_resolves_from_latest_operational_tear_sheet():
    targets = build_regime_informed_targets(
        shortlist=_shortlist(),
        phase21a=_phase21a(),
        dynamic_allocations=_dynamic(),
        tear_sheet=_tear_sheet(),
        fresh_quality=_quality(),
        paper_notional_usd=10000,
        max_candidates=4,
        include_reference_only=True,
    )
    phase6 = targets.loc[targets["canonical_candidate_id"] == PHASE6_ID]

    assert dict(zip(phase6["asset"], phase6["target_weight"], strict=False)) == {
        "SPY": 1.0,
        "CASH": 0.0,
    }
    assert phase6["paper_preview_allowed"].map(bool).all()


def test_phase6_fails_closed_if_latest_signal_cannot_be_resolved():
    targets = build_regime_informed_targets(
        shortlist=_shortlist(),
        phase21a=_phase21a(),
        dynamic_allocations=_dynamic(),
        tear_sheet=_tear_sheet(signal="mode=unknown"),
        fresh_quality=_quality(),
        paper_notional_usd=10000,
        max_candidates=4,
        include_reference_only=True,
    )
    phase6 = targets.loc[targets["canonical_candidate_id"] == PHASE6_ID]

    assert phase6["allocation_status"].eq("phase6_signal_source_missing").all()
    assert not phase6["paper_preview_allowed"].map(bool).any()


def test_gld_tlt_static_allocation_is_50_30_10_10():
    targets = build_regime_informed_targets(
        shortlist=_shortlist(),
        phase21a=_phase21a(),
        dynamic_allocations=_dynamic(),
        tear_sheet=_tear_sheet(),
        fresh_quality=_quality(),
        paper_notional_usd=10000,
        max_candidates=4,
        include_reference_only=True,
    )
    gld_tlt = targets.loc[targets["canonical_candidate_id"] == GLD_TLT_ID]

    assert dict(zip(gld_tlt["asset"], gld_tlt["target_weight"], strict=False)) == {
        "SPY": 0.5,
        "QQQ": 0.3,
        "GLD": 0.1,
        "TLT": 0.1,
    }


def test_inverse_vol_btc_allocation_is_consumed_from_phase20b_dynamic_file():
    targets = build_regime_informed_targets(
        shortlist=_shortlist(),
        phase21a=_phase21a(),
        dynamic_allocations=_dynamic(),
        tear_sheet=_tear_sheet(),
        fresh_quality=_quality(),
        paper_notional_usd=10000,
        max_candidates=4,
        include_reference_only=True,
    )
    btc = targets.loc[targets["canonical_candidate_id"] == BTC_INVOL_ID]

    assert dict(zip(btc["asset"], btc["target_weight"], strict=False)) == {
        "SPY": 0.5,
        "QQQ": 0.45,
        "BTC-USD": 0.05,
    }
    assert btc["allocation_source"].eq("phase20b_finalist_dynamic_allocations").all()


def test_spy_qqq_60_40_is_reference_only():
    targets = build_regime_informed_targets(
        shortlist=_shortlist(),
        phase21a=_phase21a(),
        dynamic_allocations=_dynamic(),
        tear_sheet=_tear_sheet(),
        fresh_quality=_quality(),
        paper_notional_usd=10000,
        max_candidates=4,
        include_reference_only=True,
    )
    spy = targets.loc[targets["canonical_candidate_id"] == SPY_QQQ_60_40_ID]

    assert spy["candidate_role"].eq("reference_only").all()


def test_btc_active_warning_true_only_when_btc_target_weight_positive():
    targets = build_regime_informed_targets(
        shortlist=_shortlist(),
        phase21a=_phase21a(),
        dynamic_allocations=_dynamic(),
        tear_sheet=_tear_sheet(),
        fresh_quality=_quality(),
        paper_notional_usd=10000,
        max_candidates=4,
        include_reference_only=True,
    )
    btc = targets.loc[targets["canonical_candidate_id"] == BTC_INVOL_ID]
    non_btc = targets.loc[targets["canonical_candidate_id"] != BTC_INVOL_ID]

    assert btc["active_btc_allocation_warning"].map(bool).all()
    assert not non_btc["active_btc_allocation_warning"].map(bool).any()


def test_gld_tlt_blocks_on_asset_data_quality_block():
    targets = build_regime_informed_targets(
        shortlist=_shortlist(),
        phase21a=_phase21a(),
        dynamic_allocations=_dynamic(),
        tear_sheet=_tear_sheet(),
        fresh_quality=_quality(block_gld=True),
        paper_notional_usd=10000,
        max_candidates=4,
        include_reference_only=True,
    )
    gld_tlt = targets.loc[targets["canonical_candidate_id"] == GLD_TLT_ID]

    assert gld_tlt["allocation_status"].eq("asset_data_quality_block").all()
    assert not gld_tlt["paper_preview_allowed"].map(bool).any()


def test_outputs_adoption_status_dashboard_and_safety_flags(tmp_path):
    outputs = save_phase21c_regime_informed_paper_tracking(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    adoption = pd.read_csv(outputs["regime_informed_tracking_adoption_status"]).iloc[0]
    dashboard = pd.read_csv(outputs["dashboard_status"]).iloc[0]
    conclusion = pd.read_csv(outputs["conclusion"]).iloc[0]

    assert bool(adoption["requires_manual_adoption"])
    assert not bool(adoption["phase20_outputs_modified"])
    assert adoption["adoption_status"] == "pending_manual_review"
    assert dashboard["phase21c_decision"] == (
        "regime_informed_paper_tracking_shortlist_written_pending_manual_adoption"
    )
    assert not bool(conclusion["live_trading_allowed"])
    assert not bool(conclusion["real_money_allowed"])
    assert not bool(conclusion["broker_api_integration_allowed"])


def test_tear_sheet_includes_required_safety_language(tmp_path):
    outputs = save_phase21c_regime_informed_paper_tracking(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    text = outputs["regime_informed_daily_tracking_tear_sheet_md"].read_text(encoding="utf-8")

    assert "NO LIVE TRADING" in text
    assert "NO REAL MONEY" in text
    assert "NO BROKER/API" in text
    assert "NO STRATEGY PROMOTION" in text
    assert "REGIME-INFORMED SHORTLIST - NOT FINAL MASTER BOT" in text
