from pathlib import Path

import pandas as pd

from market_strats.analysis.paper_finalist_tracking import (
    DYNAMIC_BTC_CANDIDATE,
    STATIC_60_40_CANDIDATE,
    build_finalist_paper_orders_preview,
    build_finalist_paper_targets,
    save_phase20a_paper_finalist_tracking,
)


PHASE20A = "phase20a_paper_finalist_tracking"


def _recommended_tracking_set() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_candidate_id": STATIC_60_40_CANDIDATE,
                "representative_candidate_id": "sf19_spy_qqq_60_40",
                "paper_candidate_role": "primary_paper_candidate_clean_growth",
                "active_assets": "QQQ,SPY",
                "uses_btc": False,
                "major_caveats": "severe historical drawdown; not defensive",
                "selection_limitations": "severe historical drawdown; not defensive",
                "promotion_allowed": False,
                "paper_trading_ready": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            },
            {
                "canonical_candidate_id": DYNAMIC_BTC_CANDIDATE,
                "representative_candidate_id": "sf19_inverse_vol_63d_cap50_btc05",
                "paper_candidate_role": "high_growth_high_caveat_btc_candidate",
                "active_assets": "BTC-USD,QQQ,SPY",
                "uses_btc": True,
                "major_caveats": "BTC weekend/gap risk and BTC-cap dependency",
                "selection_limitations": "BTC weekend/gap risk; BTC allocation caveat; paper preview only",
                "promotion_allowed": False,
                "paper_trading_ready": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            },
        ]
    )


def _tear_sheet(*, warning_symbols: str = "BTC-USD", blocking_symbols: str = "none") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "category": "signal",
                "key": "selected_signal_date",
                "value": "2026-06-08",
            },
            {
                "category": "fresh_data_quality",
                "key": "symbols_with_warnings",
                "value": warning_symbols,
            },
            {
                "category": "fresh_data_quality",
                "key": "symbols_with_blocking_failures",
                "value": blocking_symbols,
            },
            {
                "category": "final_action",
                "key": "final_recommended_manual_action",
                "value": "WARNINGS PRESENT \u2014 MANUAL REVIEW BEFORE PAPER ENTRY",
            },
        ]
    )


def _quality(*, warning: bool = True, block: bool = False) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "warnings": "",
                "blocking_failures": "",
                "quality_status": "passed",
            },
            {
                "symbol": "BTC-USD",
                "warnings": "btc_weekend_data_available_common_date_caveat" if warning else "",
                "blocking_failures": "daily_return_outlier_block" if block else "",
                "quality_status": "blocked" if block else "warning" if warning else "passed",
            },
        ]
    )


def _cycle_latest() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cycle_date": "2026-06-09",
                "selected_signal_date": "2026-06-08",
                "data_as_of_date": "2026-06-08",
                "warning_cycle": True,
                "blocked_cycle": False,
            }
        ]
    )


def _config(tmp_path: Path) -> dict:
    return {
        PHASE20A: {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "paper_trading" / "finalist_tracking"),
            "dashboard_dir": str(tmp_path / "reports" / "paper_trading" / "dashboard"),
            "source_finalist_validation_dir": str(
                tmp_path / "reports" / "strategy_factory" / "finalist_validation"
            ),
            "source_operational_hardening_dir": str(
                tmp_path / "reports" / "paper_trading" / "operational_hardening"
            ),
            "source_cycle_tracker_dir": str(
                tmp_path / "reports" / "paper_trading" / "cycle_tracker"
            ),
            "paper_notional_usd": 10000,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "include_candidates": [STATIC_60_40_CANDIDATE, DYNAMIC_BTC_CANDIDATE],
        }
    }


def _write_sources(
    tmp_path: Path,
    *,
    write_recommended: bool = True,
    warning: bool = True,
    block: bool = False,
) -> None:
    finalist_dir = tmp_path / "reports" / "strategy_factory" / "finalist_validation"
    hardening_dir = tmp_path / "reports" / "paper_trading" / "operational_hardening"
    cycle_dir = tmp_path / "reports" / "paper_trading" / "cycle_tracker"
    finalist_dir.mkdir(parents=True, exist_ok=True)
    hardening_dir.mkdir(parents=True, exist_ok=True)
    cycle_dir.mkdir(parents=True, exist_ok=True)

    recommended = _recommended_tracking_set()
    if write_recommended:
        recommended.to_csv(
            finalist_dir / "phase19b_recommended_paper_tracking_set.csv",
            index=False,
        )
    recommended.to_csv(finalist_dir / "phase19b_paper_candidate_shortlist.csv", index=False)
    pd.DataFrame(
        [
            {
                "recommended_primary_roster": "QQQ,SPY",
                "recommended_secondary_roster": "BTC-USD,QQQ,SPY",
            }
        ]
    ).to_csv(finalist_dir / "phase19b_entity_roster_recommendation.csv", index=False)
    _tear_sheet(
        warning_symbols="BTC-USD" if warning else "none",
        blocking_symbols="BTC-USD" if block else "none",
    ).to_csv(hardening_dir / "daily_execution_tear_sheet.csv", index=False)
    (hardening_dir / "daily_execution_tear_sheet.md").write_text(
        "NO LIVE TRADING\nNO REAL MONEY\nNO BROKER/API\nMANUAL PAPER PREVIEW ONLY\n",
        encoding="utf-8",
    )
    _quality(warning=warning, block=block).to_csv(
        hardening_dir / "fresh_data_quality_report.csv",
        index=False,
    )
    _cycle_latest().to_csv(cycle_dir / "paper_cycle_latest.csv", index=False)


def test_missing_phase19b_recommended_tracking_set_fails_closed(tmp_path):
    _write_sources(tmp_path, write_recommended=False)

    outputs = save_phase20a_paper_finalist_tracking(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )

    assert outputs["summary"].loc[0, "phase20a_decision"] == (
        "paper_finalist_tracking_failed_closed"
    )
    assert not bool(outputs["summary"].loc[0, "all_gates_passed"])


def test_finalist_targets_are_written_and_60_40_is_static():
    targets = build_finalist_paper_targets(
        recommended_tracking_set=_recommended_tracking_set(),
        include_candidates=[STATIC_60_40_CANDIDATE],
        dynamic_allocations=pd.DataFrame(),
        selected_signal_date="2026-06-08",
        tracking_date="2026-06-09",
        paper_notional_usd=10000,
        data_quality_blocked=False,
    )

    weights = dict(zip(targets["asset"], targets["target_weight"], strict=False))
    assert weights["SPY"] == 0.60
    assert weights["QQQ"] == 0.40
    assert weights["BTC-USD"] == 0.0
    assert targets["paper_preview_allowed"].all()


def test_dynamic_btc_candidate_is_not_guessed_when_allocation_source_missing():
    targets = build_finalist_paper_targets(
        recommended_tracking_set=_recommended_tracking_set(),
        include_candidates=[DYNAMIC_BTC_CANDIDATE],
        dynamic_allocations=pd.DataFrame(),
        selected_signal_date="2026-06-08",
        tracking_date="2026-06-09",
        paper_notional_usd=10000,
        data_quality_blocked=False,
    )

    assert set(targets["asset"]) == {"BTC-USD", "QQQ", "SPY"}
    assert set(targets["allocation_status"]) == {"dynamic_weight_source_missing"}
    assert targets["target_weight"].isna().all()
    assert not targets["paper_preview_allowed"].any()
    assert targets["candidate_caveats"].str.contains("BTC", case=False).any()


def test_order_preview_blocks_candidate_when_dynamic_allocation_missing():
    targets = build_finalist_paper_targets(
        recommended_tracking_set=_recommended_tracking_set(),
        include_candidates=[DYNAMIC_BTC_CANDIDATE],
        dynamic_allocations=pd.DataFrame(),
        selected_signal_date="2026-06-08",
        tracking_date="2026-06-09",
        paper_notional_usd=10000,
        data_quality_blocked=False,
    )
    orders = build_finalist_paper_orders_preview(targets=targets, data_quality_blocked=False)

    assert not orders["paper_order_allowed"].any()
    assert orders["paper_order_blocking_reason"].str.contains(
        "dynamic_weight_source_missing"
    ).all()


def test_phase20a_consumes_phase20b_dynamic_allocation_when_available(tmp_path):
    _write_sources(tmp_path, warning=True, block=False)
    out_dir = tmp_path / "reports" / "paper_trading" / "finalist_tracking"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "canonical_candidate_id": DYNAMIC_BTC_CANDIDATE,
                "asset": "SPY",
                "target_weight": 0.50,
                "final_weight": 0.50,
                "allocation_status": "dynamic_allocation_resolved",
                "allocation_source": "phase20b_inverse_vol_dynamic_allocation",
                "paper_preview_allowed": True,
            },
            {
                "canonical_candidate_id": DYNAMIC_BTC_CANDIDATE,
                "asset": "QQQ",
                "target_weight": 0.45,
                "final_weight": 0.45,
                "allocation_status": "dynamic_allocation_resolved",
                "allocation_source": "phase20b_inverse_vol_dynamic_allocation",
                "paper_preview_allowed": True,
            },
            {
                "canonical_candidate_id": DYNAMIC_BTC_CANDIDATE,
                "asset": "BTC-USD",
                "target_weight": 0.05,
                "final_weight": 0.05,
                "allocation_status": "dynamic_allocation_resolved",
                "allocation_source": "phase20b_inverse_vol_dynamic_allocation",
                "paper_preview_allowed": True,
            },
        ]
    ).to_csv(out_dir / "finalist_dynamic_allocations.csv", index=False)

    outputs = save_phase20a_paper_finalist_tracking(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )
    targets = outputs["finalist_paper_targets"]
    dynamic = targets.loc[targets["canonical_candidate_id"] == DYNAMIC_BTC_CANDIDATE]

    assert set(dynamic["allocation_status"]) == {"dynamic_allocation_resolved"}
    assert set(dynamic["allocation_source"]) == {
        "phase20b_inverse_vol_dynamic_allocation"
    }
    assert dynamic["paper_preview_allowed"].all()
    assert dynamic["btc_capable_candidate"].all()
    assert dynamic["persistent_btc_caveat"].all()
    assert dynamic["active_btc_allocation_warning"].all()
    assert set(dynamic["current_btc_weight"].astype(float).round(2)) == {0.05}


def test_btc_capable_candidate_has_persistent_caveat_when_dynamic_file_missing():
    targets = build_finalist_paper_targets(
        recommended_tracking_set=_recommended_tracking_set(),
        include_candidates=[DYNAMIC_BTC_CANDIDATE],
        dynamic_allocations=pd.DataFrame(),
        selected_signal_date="2026-06-08",
        tracking_date="2026-06-09",
        paper_notional_usd=10000,
        data_quality_blocked=False,
    )

    assert targets["btc_capable_candidate"].all()
    assert targets["persistent_btc_caveat"].all()
    assert not targets["active_btc_allocation_warning"].any()


def test_order_preview_blocks_all_candidates_when_data_quality_blocks():
    targets = build_finalist_paper_targets(
        recommended_tracking_set=_recommended_tracking_set(),
        include_candidates=[STATIC_60_40_CANDIDATE, DYNAMIC_BTC_CANDIDATE],
        dynamic_allocations=pd.DataFrame(),
        selected_signal_date="2026-06-08",
        tracking_date="2026-06-09",
        paper_notional_usd=10000,
        data_quality_blocked=True,
    )
    orders = build_finalist_paper_orders_preview(targets=targets, data_quality_blocked=True)

    assert not orders["paper_order_allowed"].any()
    assert orders["paper_order_blocking_reason"].str.contains(
        "fresh_data_quality_blocking_failure"
    ).all()


def test_warning_run_writes_tear_sheet_dashboard_and_journal(tmp_path):
    _write_sources(tmp_path, warning=True, block=False)

    outputs = save_phase20a_paper_finalist_tracking(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )
    out_dir = tmp_path / "reports" / "paper_trading" / "finalist_tracking"
    dashboard = tmp_path / "reports" / "paper_trading" / "dashboard" / "finalist_tracking_status.csv"
    markdown = (out_dir / "finalist_daily_tracking_tear_sheet.md").read_text(encoding="utf-8")

    assert (out_dir / "finalist_paper_targets.csv").exists()
    assert (out_dir / "finalist_paper_orders_preview.csv").exists()
    assert (out_dir / "finalist_manual_paper_journal_template.csv").exists()
    assert dashboard.exists()
    assert "WARNINGS PRESENT \u2014 REVIEW BEFORE PAPER TRACKING" in markdown
    assert "NO LIVE TRADING" in markdown
    assert "NO REAL MONEY" in markdown
    assert "NO BROKER/API" in markdown
    assert "MANUAL PAPER TRACKING ONLY" in markdown
    assert outputs["summary"].loc[0, "phase20a_decision"] == (
        "paper_finalist_tracking_written_manual_preview_only"
    )
    journal = pd.read_csv(out_dir / "finalist_manual_paper_journal_template.csv")
    required = {
        "journal_date",
        "selected_signal_date",
        "canonical_candidate_id",
        "asset",
        "manual_execution_status",
    }
    assert required.issubset(journal.columns)
    assert set(journal["manual_execution_status"]) == {"not_entered"}


def test_blocked_data_quality_writes_hold_instruction(tmp_path):
    _write_sources(tmp_path, warning=True, block=True)

    save_phase20a_paper_finalist_tracking(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )
    markdown = (
        tmp_path
        / "reports"
        / "paper_trading"
        / "finalist_tracking"
        / "finalist_daily_tracking_tear_sheet.md"
    ).read_text(encoding="utf-8")

    assert "MANUAL REVIEW REQUIRED \u2014 HOLD CURRENT STATE" in markdown


def test_safety_flags_remain_false(tmp_path):
    _write_sources(tmp_path)

    outputs = save_phase20a_paper_finalist_tracking(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )

    targets = outputs["finalist_paper_targets"]
    assert not targets["live_trading_allowed"].any()
    assert not targets["real_money_allowed"].any()
    assert not targets["broker_api_integration_allowed"].any()
    assert not targets["promotion_allowed"].any()
